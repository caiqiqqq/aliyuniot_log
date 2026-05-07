from __future__ import annotations

import hashlib
import json
import re
from typing import Any


KEY_ALIASES = {
    "log_time": {
        "__time__",
        "time",
        "timestamp",
        "gmtcreate",
        "gmt_create",
        "logtime",
        "log_time",
        "eventtime",
        "occurtime",
    },
    "trace_id": {"traceid", "trace_id", "tracingid"},
    "message_id": {"messageid", "message_id", "msgid", "msg_id"},
    "device_name": {"devicename", "device_name", "device"},
    "biz_type": {"biztype", "biz_type", "bizcode", "biz_code", "category", "type"},
    "operation": {"operation", "action", "event", "method", "name"},
    "content": {"content", "payload", "message", "data", "body", "detail"},
    "status": {"status", "statuscode", "status_code", "code", "result"},
}

LOG_LIKE_KEYS = set().union(*KEY_ALIASES.values())


def extract_from_json(payload: Any, source: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in _walk(payload):
        if not isinstance(item, dict):
            continue
        if not _is_log_like(item):
            continue
        normalized = normalize_record(item, source=source, raw_json=item)
        records.append(normalized)
    return _dedupe(records)


def extract_from_table(rows: list[list[str]], source: str = "dom_table") -> list[dict[str, Any]]:
    records = []
    for cells in rows:
        clean_cells = [cell.strip() for cell in cells if cell and cell.strip()]
        if len(clean_cells) < 2:
            continue
        record = _guess_from_cells(clean_cells)
        record["source"] = source
        record["raw_text"] = " | ".join(clean_cells)
        record["fingerprint"] = fingerprint(record)
        records.append(record)
    return _dedupe(records)


def extract_from_table_with_headers(
    headers: list[str],
    rows: list[list[str]],
    source: str = "dom_table",
) -> list[dict[str, Any]]:
    normalized_headers = [_field_for_header(header) for header in headers]
    if not any(normalized_headers):
        return extract_from_table(rows, source=source)

    records = []
    for cells in rows:
        clean_cells = [cell.strip() for cell in cells]
        if len([cell for cell in clean_cells if cell]) < 2:
            continue
        record: dict[str, Any] = {"source": source, "raw_text": " | ".join(clean_cells)}
        for index, field in enumerate(normalized_headers):
            if field and index < len(clean_cells):
                record[field] = clean_cells[index]
        if not any(record.get(key) for key in ("log_time", "trace_id", "message_id", "device_name")):
            record.update(_guess_from_cells(clean_cells))
            record["source"] = source
        record["fingerprint"] = fingerprint(record)
        records.append(record)
    return _dedupe(records)


def normalize_record(raw: dict[str, Any], source: str, raw_json: Any = None) -> dict[str, Any]:
    lowered = {_normalize_key(key): value for key, value in raw.items()}
    record: dict[str, Any] = {"source": source, "raw_json": raw_json or raw}
    for field, aliases in KEY_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                record[field] = _stringify(lowered[alias])
                break
    if "raw_text" not in record:
        record["raw_text"] = _compact_json(raw)
    record["fingerprint"] = fingerprint(record)
    return record


def fingerprint(record: dict[str, Any]) -> str:
    parts = [
        record.get("log_time") or "",
        record.get("trace_id") or "",
        record.get("message_id") or "",
        record.get("device_name") or "",
        record.get("operation") or "",
        record.get("status") or "",
        record.get("raw_text") or _compact_json(record.get("raw_json")),
    ]
    digest = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return digest[:32]


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _is_log_like(value: dict[str, Any]) -> bool:
    keys = {_normalize_key(key) for key in value}
    hits = keys & LOG_LIKE_KEYS
    if len(hits) >= 2:
        return True
    return bool({"traceid", "messageid"} & keys)


def _guess_from_cells(cells: list[str]) -> dict[str, Any]:
    text = " | ".join(cells)
    record: dict[str, Any] = {"raw_text": text}
    for cell in cells:
        if "trace" in cell.lower() and not record.get("trace_id"):
            record["trace_id"] = cell
        if re.fullmatch(r"[a-fA-F0-9]{16,}", cell) and not record.get("message_id"):
            record["message_id"] = cell
        if re.search(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2}|20\d{2}-\d{1,2}-\d{1,2}T)", cell):
            record.setdefault("log_time", cell)
        if re.fullmatch(r"\d{3}", cell):
            record.setdefault("status", cell)
    if len(cells) >= 1:
        record.setdefault("log_time", cells[0])
    if len(cells) >= 2:
        record.setdefault("biz_type", cells[1])
    if len(cells) >= 3:
        record.setdefault("operation", cells[2])
    if len(cells) >= 4:
        record.setdefault("device_name", cells[3])
    if len(cells) >= 5:
        record.setdefault("content", cells[-1])
    return record


def _normalize_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9_]", "", str(key).strip().lower())


def _field_for_header(header: str) -> str | None:
    normalized = _normalize_key(header)
    chinese_map = {
        "时间": "log_time",
        "日志时间": "log_time",
        "追踪": "trace_id",
        "消息": "message_id",
        "设备": "device_name",
        "业务": "biz_type",
        "类型": "biz_type",
        "操作": "operation",
        "内容": "content",
        "状态": "status",
    }
    for text, field in chinese_map.items():
        if text in header:
            return field
    for field, aliases in KEY_ALIASES.items():
        if normalized in aliases:
            return field
    return None


def _stringify(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return _compact_json(value)
    return str(value)


def _compact_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return str(value)


def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for record in records:
        key = record.get("fingerprint")
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result
