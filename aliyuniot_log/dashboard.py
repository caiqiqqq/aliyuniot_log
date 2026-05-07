from __future__ import annotations

from pathlib import Path
from typing import Any

from config import get_settings
from db import (
    clear_all_data,
    database,
    finish_run,
    insert_logs,
    insert_search_snapshot,
    latest_business_type_totals,
    latest_logs,
    latest_search_snapshots,
    rows,
    scalar,
    search_total_timeseries,
    start_run,
)
from extract import extract_from_json, extract_from_table_with_headers
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"

app = FastAPI(title="Aliyun IoT Log Monitor")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "https://iot.console.aliyun.com"],
    allow_origin_regex=r"chrome-extension://.*",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/summary")
def summary() -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        last_run = rows(
            conn,
            """
            SELECT started_at, finished_at, status, inserted_count, seen_count, message
            FROM crawler_runs
            ORDER BY id DESC
            LIMIT 1
            """,
        )
        return {
            "total": scalar(conn, "SELECT COUNT(*) FROM iot_logs") or 0,
            "latest_search_total": scalar(
                conn,
                """
                SELECT total_count
                FROM search_snapshots
                ORDER BY collected_at DESC, id DESC
                LIMIT 1
                """,
            ),
            "devices": scalar(
                conn,
                """
                SELECT COUNT(DISTINCT name)
                FROM (
                    SELECT
                        CASE
                            WHEN instr(TRIM(device_name), ' ') > 0
                              AND substr(TRIM(device_name), 1, instr(TRIM(device_name), ' ') - 1)
                                  = substr(TRIM(device_name), instr(TRIM(device_name), ' ') + 1)
                            THEN substr(TRIM(device_name), 1, instr(TRIM(device_name), ' ') - 1)
                            ELSE TRIM(device_name)
                        END AS name
                    FROM iot_logs
                    WHERE NULLIF(TRIM(device_name), '') IS NOT NULL
                )
                """,
            )
            or 0,
            "errors": scalar(
                conn,
                """
                SELECT COUNT(*) FROM iot_logs
                WHERE status IS NOT NULL
                  AND status NOT IN ('200', 'OK', 'Success', 'success', 'true')
                """,
            )
            or 0,
            "latest_log_time": scalar(
                conn,
                "SELECT MAX(COALESCE(log_time, collected_at)) FROM iot_logs",
            ),
            "last_run": last_run[0] if last_run else None,
        }


@app.post("/api/ingest")
async def ingest(request: Request) -> dict:
    payload = await request.json()
    source = str(payload.get("source") or "extension")
    records = _records_from_payload(payload, source)
    search_snapshot = _search_snapshot_from_payload(payload, source)
    settings = get_settings()
    with database(settings.db_path) as conn:
        run_id = start_run(conn)
        inserted = insert_logs(conn, records)
        snapshot_inserted = insert_search_snapshot(conn, search_snapshot) if search_snapshot else False
        finish_run(
            conn,
            run_id,
            "ok",
            inserted_count=inserted,
            seen_count=len(records),
            message=_run_message(source, search_snapshot),
        )
    return {"seen": len(records), "inserted": inserted, "snapshot_inserted": snapshot_inserted}


@app.get("/api/search-snapshots")
def search_snapshots(limit: int = Query(default=10, ge=1, le=100)) -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        return {"items": latest_search_snapshots(conn, limit=limit)}


@app.get("/api/business-type-totals")
def business_type_totals() -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        return {"items": latest_business_type_totals(conn)}


@app.get("/api/search-total-timeseries")
def search_total_trend(limit: int = Query(default=240, ge=1, le=1000)) -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        return {"items": search_total_timeseries(conn, limit=limit)}


@app.post("/api/clear")
def clear_data() -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        clear_all_data(conn)
    return {"ok": True}


@app.get("/api/logs")
def logs(
    limit: int = Query(default=10, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    device_name: str = "",
    trace_id: str = "",
    message_id: str = "",
    status: str = "",
) -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        offset = (page - 1) * limit
        items, total = latest_logs(
            conn,
            limit=limit,
            offset=offset,
            device_name=device_name,
            trace_id=trace_id,
            message_id=message_id,
            status=status,
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total else 0,
        }


@app.get("/api/timeseries")
def timeseries() -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        items = rows(
            conn,
            """
            SELECT substr(COALESCE(log_time, collected_at), 1, 16) AS bucket, COUNT(*) AS count
            FROM iot_logs
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT 120
            """,
        )
        items.reverse()
        return {"items": items}


@app.get("/api/statuses")
def statuses() -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        return {
            "items": rows(
                conn,
                """
                SELECT NULLIF(TRIM(status), '') AS name, COUNT(*) AS value
                FROM iot_logs
                WHERE NULLIF(TRIM(status), '') IS NOT NULL
                GROUP BY NULLIF(TRIM(status), '')
                ORDER BY value DESC
                LIMIT 20
                """,
            )
        }


@app.get("/api/devices")
def devices() -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        return {
            "items": rows(
                conn,
                """
                SELECT name, COUNT(*) AS value
                FROM (
                    SELECT
                        CASE
                            WHEN instr(TRIM(device_name), ' ') > 0
                              AND substr(TRIM(device_name), 1, instr(TRIM(device_name), ' ') - 1)
                                  = substr(TRIM(device_name), instr(TRIM(device_name), ' ') + 1)
                            THEN substr(TRIM(device_name), 1, instr(TRIM(device_name), ' ') - 1)
                            ELSE TRIM(device_name)
                        END AS name
                    FROM iot_logs
                    WHERE NULLIF(TRIM(device_name), '') IS NOT NULL
                )
                GROUP BY name
                ORDER BY value DESC, name ASC
                LIMIT 20
                """,
            )
        }


@app.get("/api/device-error-rank")
def device_error_rank() -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        return {
            "items": rows(
                conn,
                """
                WITH normalized AS (
                    SELECT
                        CASE
                            WHEN instr(TRIM(device_name), ' ') > 0
                              AND substr(TRIM(device_name), 1, instr(TRIM(device_name), ' ') - 1)
                                  = substr(TRIM(device_name), instr(TRIM(device_name), ' ') + 1)
                            THEN substr(TRIM(device_name), 1, instr(TRIM(device_name), ' ') - 1)
                            ELSE TRIM(device_name)
                        END AS name,
                        status
                    FROM iot_logs
                    WHERE NULLIF(TRIM(device_name), '') IS NOT NULL
                )
                SELECT
                    name,
                    COUNT(*) AS total_count,
                    SUM(
                        CASE
                            WHEN status IS NOT NULL
                              AND status NOT IN ('200', 'OK', 'Success', 'success', 'true')
                            THEN 1
                            ELSE 0
                        END
                    ) AS error_count,
                    ROUND(
                        SUM(
                            CASE
                                WHEN status IS NOT NULL
                                  AND status NOT IN ('200', 'OK', 'Success', 'success', 'true')
                                THEN 1
                                ELSE 0
                            END
                        ) * 100.0 / COUNT(*),
                        2
                    ) AS error_rate
                FROM normalized
                GROUP BY name
                HAVING error_count > 0
                ORDER BY error_count DESC, error_rate DESC, total_count DESC
                LIMIT 20
                """,
            )
        }


@app.get("/api/categories")
def categories() -> dict:
    settings = get_settings()
    with database(settings.db_path) as conn:
        return {
            "items": rows(
                conn,
                """
                SELECT name, COUNT(*) AS value
                FROM (
                    SELECT COALESCE(NULLIF(TRIM(biz_type), ''), NULLIF(TRIM(operation), '')) AS name
                    FROM iot_logs
                )
                WHERE name IS NOT NULL
                GROUP BY name
                ORDER BY value DESC
                LIMIT 20
                """,
            )
        }


def _records_from_payload(payload: dict[str, Any], source: str) -> list[dict[str, Any]]:
    if isinstance(payload.get("records"), list):
        records = []
        for item in payload["records"]:
            if isinstance(item, dict) and item.get("fingerprint"):
                item.setdefault("source", source)
                records.append(item)
        if records:
            return records

    if "json" in payload:
        return extract_from_json(payload["json"], source=source)

    rows_payload = payload.get("rows")
    if isinstance(rows_payload, list):
        headers = payload.get("headers") if isinstance(payload.get("headers"), list) else []
        rows_data = [
            [str(cell) for cell in row]
            for row in rows_payload
            if isinstance(row, list)
        ]
        return extract_from_table_with_headers([str(item) for item in headers], rows_data, source=source)

    if "search_snapshot" in payload or "search" in payload:
        return []

    return extract_from_json(payload, source=source)


def _search_snapshot_from_payload(payload: dict[str, Any], source: str) -> dict[str, Any] | None:
    snapshot = payload.get("search_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = payload.get("search")
    if not isinstance(snapshot, dict):
        return None
    result = dict(snapshot)
    result.setdefault("source", source)
    return result


def _run_message(source: str, search_snapshot: dict[str, Any] | None) -> str:
    if search_snapshot and search_snapshot.get("total_count") is not None:
        return f"extension ingest source={source} total={search_snapshot.get('total_count')}"
    return f"extension ingest source={source}"
