# Architecture

## Purpose

Aliyun IoT Log Monitor is a local analysis tool for Alibaba Cloud IoT console
logs. It avoids storing browser login state in the project. Collection happens
inside a user-controlled Chrome tab through a Chrome extension, and analysis is
served by a local FastAPI app.

## Components

| Path | Role |
| --- | --- |
| `extension/manifest.json` | Chrome extension permissions and content script registration. |
| `extension/content.js` | Reads the IoT log page table, triggers timed search, builds payloads, and posts to local `/api/ingest`. |
| `extension/page_hook.js` | Injects the page bridge into the console page. |
| `extension/page_bridge.js` | Intercepts matching fetch/XHR JSON responses and forwards them to the content script. |
| `extension/popup.*` | Extension popup controls for background collection and timed search. |
| `dashboard.py` | FastAPI app, ingest endpoint, summary APIs, chart data APIs, and static dashboard serving. |
| `db.py` | SQLite schema, migrations, insert logic, TraceID deduplication, and query helpers. |
| `extract.py` | Normalizes JSON/table data into log records. |
| `static/index.html` | ECharts dashboard and export/copy interactions. |
| `config.py` | Minimal local configuration loaded from `.env`. |

## Data Flow

```text
Alibaba Cloud IoT log page
  -> Chrome extension content/page bridge
  -> POST http://127.0.0.1:8000/api/ingest
  -> FastAPI normalization
  -> SQLite data/iot_logs.db
  -> Dashboard APIs
  -> ECharts dashboard
```

## Storage

SQLite stores three logical groups:

- `iot_logs`: normalized log records. Logs are deduplicated by normalized
  `trace_id`; records without a TraceID still use their generated fingerprint.
- `search_snapshots`: timed search totals and filter metadata. These records
  drive the total/delta trend charts.
- `crawler_runs`: ingest history used for the "recent receive" status panel.

`data/iot_logs.db` is local runtime data and must not be committed.

## Deduplication

The ingest path normalizes duplicated text such as:

```text
TraceID TraceID -> TraceID
device device   -> device
```

If a normalized TraceID already exists, the incoming record is ignored. This
keeps device ranking and device error ranking from being inflated by repeated
searches over the same log rows.

## Dashboard Metrics

- Search total trend: total count from timed search snapshots.
- Delta trend: current search total minus previous search total.
- Status distribution: status counts from deduplicated log records.
- Device ranking: deduplicated log counts grouped by normalized device ID.
- Device error ranking: records whose status is not `200`, `OK`, `Success`,
  `success`, or `true`, grouped by normalized device ID.

## Local-Only Assumptions

- The API is designed for `127.0.0.1`.
- The extension expects the user to be logged into Alibaba Cloud in their own
  Chrome session.
- The project does not need Chrome profile directories, cookies, or Playwright
  browser automation.
