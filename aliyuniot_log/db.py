from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS iot_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  collected_at TEXT NOT NULL,
  log_time TEXT,
  trace_id TEXT,
  message_id TEXT,
  device_name TEXT,
  biz_type TEXT,
  operation TEXT,
  content TEXT,
  status TEXT,
  source TEXT NOT NULL DEFAULT 'unknown',
  raw_text TEXT,
  raw_json TEXT,
  fingerprint TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_iot_logs_log_time ON iot_logs(log_time);
CREATE INDEX IF NOT EXISTS idx_iot_logs_collected_at ON iot_logs(collected_at);
CREATE INDEX IF NOT EXISTS idx_iot_logs_device_name ON iot_logs(device_name);
CREATE INDEX IF NOT EXISTS idx_iot_logs_trace_id ON iot_logs(trace_id);
CREATE INDEX IF NOT EXISTS idx_iot_logs_message_id ON iot_logs(message_id);
CREATE INDEX IF NOT EXISTS idx_iot_logs_status ON iot_logs(status);

CREATE TABLE IF NOT EXISTS crawler_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  inserted_count INTEGER NOT NULL DEFAULT 0,
  seen_count INTEGER NOT NULL DEFAULT 0,
  message TEXT
);

CREATE TABLE IF NOT EXISTS search_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  collected_at TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'unknown',
  active_tab TEXT,
  total_count INTEGER,
  page INTEGER,
  page_count INTEGER,
  page_size INTEGER,
  filters_json TEXT,
  raw_text TEXT,
  fingerprint TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_search_snapshots_collected_at ON search_snapshots(collected_at);
CREATE INDEX IF NOT EXISTS idx_search_snapshots_total_count ON search_snapshots(total_count);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    migrate_log_identity(conn)
    return conn


def migrate_log_identity(conn: sqlite3.Connection) -> None:
    rows_to_normalize = conn.execute(
        """
        SELECT id, trace_id, device_name
        FROM iot_logs
        WHERE trace_id IS NOT NULL OR device_name IS NOT NULL
        """
    ).fetchall()
    for row in rows_to_normalize:
        trace_id = _normalize_repeated_token(row["trace_id"])
        device_name = _normalize_repeated_token(row["device_name"])
        if trace_id != row["trace_id"] or device_name != row["device_name"]:
            conn.execute(
                "UPDATE iot_logs SET trace_id = ?, device_name = ? WHERE id = ?",
                (trace_id, device_name, row["id"]),
            )
    conn.execute(
        """
        DELETE FROM iot_logs
        WHERE trace_id IS NOT NULL
          AND TRIM(trace_id) <> ''
          AND id NOT IN (
            SELECT MIN(id)
            FROM iot_logs
            WHERE trace_id IS NOT NULL
              AND TRIM(trace_id) <> ''
            GROUP BY trace_id
          )
        """
    )


@contextmanager
def database(db_path: Path):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def start_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO crawler_runs(started_at, status) VALUES (?, ?)",
        (utc_now(), "running"),
    )
    return int(cur.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    inserted_count: int,
    seen_count: int,
    message: str = "",
) -> None:
    conn.execute(
        """
        UPDATE crawler_runs
        SET finished_at = ?, status = ?, inserted_count = ?, seen_count = ?, message = ?
        WHERE id = ?
        """,
        (utc_now(), status, inserted_count, seen_count, message[:2000], run_id),
    )


def insert_logs(conn: sqlite3.Connection, records: Iterable[dict[str, Any]]) -> int:
    inserted = 0
    collected_at = utc_now()
    for record in records:
        raw_trace_id = _clean(record.get("trace_id"))
        trace_id = _normalize_repeated_token(record.get("trace_id"))
        trace_values = tuple(dict.fromkeys(value for value in (trace_id, raw_trace_id) if value))
        if trace_values:
            placeholders = ",".join("?" for _ in trace_values)
            if scalar(conn, f"SELECT 1 FROM iot_logs WHERE trace_id IN ({placeholders}) LIMIT 1", trace_values):
                continue
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO iot_logs (
              collected_at, log_time, trace_id, message_id, device_name, biz_type,
              operation, content, status, source, raw_text, raw_json, fingerprint
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                collected_at,
                _clean(record.get("log_time")),
                trace_id,
                _clean(record.get("message_id")),
                _normalize_repeated_token(record.get("device_name")),
                _clean(record.get("biz_type")),
                _clean(record.get("operation")),
                _clean(record.get("content")),
                _clean(record.get("status")),
                _clean(record.get("source")) or "unknown",
                _clean(record.get("raw_text")),
                _json(record.get("raw_json")),
                str(record["fingerprint"]),
            ),
        )
        inserted += cur.rowcount
    return inserted


def insert_search_snapshot(conn: sqlite3.Connection, snapshot: dict[str, Any]) -> bool:
    total_count = _int_or_none(snapshot.get("total_count"))
    if total_count is None:
        return False
    filters = snapshot.get("filters")
    fingerprint_value = _clean(snapshot.get("fingerprint")) or search_snapshot_fingerprint(snapshot)
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO search_snapshots (
          collected_at, source, active_tab, total_count, page, page_count, page_size,
          filters_json, raw_text, fingerprint
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            utc_now(),
            _clean(snapshot.get("source")) or "unknown",
            _clean(snapshot.get("active_tab")),
            total_count,
            _int_or_none(snapshot.get("page")),
            _int_or_none(snapshot.get("page_count")),
            _int_or_none(snapshot.get("page_size")),
            _json(filters) if filters is not None else None,
            _clean(snapshot.get("raw_text")),
            fingerprint_value,
        ),
    )
    return cur.rowcount > 0


def latest_search_snapshots(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    items = rows(
        conn,
        """
        SELECT *
        FROM search_snapshots
        ORDER BY collected_at DESC, id DESC
        LIMIT ?
        """,
        (min(max(limit, 1), 100),),
    )
    for item in items:
        item["filters"] = _loads_json(item.pop("filters_json", None))
    return items


def latest_business_type_totals(conn: sqlite3.Connection, limit: int = 500) -> list[dict[str, Any]]:
    snapshots = latest_search_snapshots(conn, limit=limit)
    latest_by_type: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        biz_type = _business_type_from_filters(snapshot.get("filters"))
        if not biz_type or biz_type in latest_by_type:
            continue
        latest_by_type[biz_type] = {
            "name": biz_type,
            "total_count": snapshot.get("total_count"),
            "collected_at": snapshot.get("collected_at"),
            "active_tab": snapshot.get("active_tab"),
        }
    return sorted(
        latest_by_type.values(),
        key=lambda item: (item.get("total_count") or 0, item.get("name") or ""),
        reverse=True,
    )


def search_total_timeseries(conn: sqlite3.Connection, limit: int = 240) -> list[dict[str, Any]]:
    items = rows(
        conn,
        """
        SELECT collected_at, total_count, active_tab, filters_json, source
        FROM search_snapshots
        WHERE total_count IS NOT NULL
          AND source = 'extension:search_timer'
        ORDER BY collected_at DESC, id DESC
        LIMIT ?
        """,
        (min(max(limit, 1), 1000),),
    )
    items.reverse()
    previous_total = None
    for item in items:
        item["filters"] = _loads_json(item.pop("filters_json", None))
        current_total = item.get("total_count")
        item["delta_count"] = 0 if previous_total is None else (current_total or 0) - (previous_total or 0)
        previous_total = current_total
    return items


def clear_all_data(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM iot_logs")
    conn.execute("DELETE FROM search_snapshots")
    conn.execute("DELETE FROM crawler_runs")


def search_snapshot_fingerprint(snapshot: dict[str, Any]) -> str:
    parts = [
        _clean(snapshot.get("active_tab")) or "",
        str(_int_or_none(snapshot.get("total_count")) or ""),
        str(_int_or_none(snapshot.get("page_count")) or ""),
        _json(snapshot.get("filters")) or "",
    ]
    return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()[:32]


def latest_logs(
    conn: sqlite3.Connection,
    limit: int = 100,
    offset: int = 0,
    device_name: str = "",
    trace_id: str = "",
    message_id: str = "",
    status: str = "",
) -> tuple[list[dict[str, Any]], int]:
    where = []
    params: list[Any] = []
    for column, value in {
        "device_name": device_name,
        "trace_id": trace_id,
        "message_id": message_id,
        "status": status,
    }.items():
        if value:
            where.append(f"{column} LIKE ?")
            params.append(f"%{value}%")
    where_sql = ""
    if where:
        where_sql = " WHERE " + " AND ".join(where)
    total = scalar(conn, "SELECT COUNT(*) FROM iot_logs" + where_sql, tuple(params)) or 0
    sql = "SELECT * FROM iot_logs" + where_sql
    sql += " ORDER BY COALESCE(log_time, collected_at) DESC LIMIT ?"
    params.append(min(max(limit, 1), 1000))
    sql += " OFFSET ?"
    params.append(max(offset, 0))
    return [dict(row) for row in conn.execute(sql, params).fetchall()], int(total)


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_repeated_token(value: Any) -> str | None:
    text = _clean(value)
    if not text:
        return None
    parts = text.split()
    if len(parts) == 2 and parts[0] == parts[1]:
        return parts[0]
    return text


def _json(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def _loads_json(value: Any) -> Any:
    if not value:
        return None
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _business_type_from_filters(filters: Any) -> str | None:
    if not isinstance(filters, dict):
        return None
    preferred_keys = ("bizType", "businessType", "biz_type", "业务类型")
    for key in preferred_keys:
        value = _clean(filters.get(key))
        if value and value != "全部业务类型":
            return value
    for key, value in filters.items():
        key_text = str(key).lower()
        if "biz" in key_text or "business" in key_text or "业务" in key_text:
            text = _clean(value)
            if text and text != "全部业务类型":
                return text
    return None
