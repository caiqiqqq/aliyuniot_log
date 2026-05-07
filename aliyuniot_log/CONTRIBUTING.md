# Contributing

Thanks for considering a contribution.

## Development Setup

```bash
cd aliyuniot_log
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn dashboard:app --host 127.0.0.1 --port 8000
```

Load the Chrome extension from `aliyuniot_log/extension` in Chrome developer mode.

## Checks

Run these before opening a pull request:

```bash
cd aliyuniot_log
python3 -m py_compile config.py dashboard.py db.py extract.py
perl -0777 -ne 'print $1 if /<script>(.*)<\\/script>/s' static/index.html | node --check
```

## Data Safety

Do not commit local runtime data:

- `.env`
- `data/`
- `artifacts/`
- `.venv/`
- Browser profiles, cookies, storage state, screenshots, exported reports, or real log data

## Pull Requests

- Keep changes focused.
- Explain user-visible behavior changes.
- Include screenshots for dashboard UI changes when useful.
- Mention any database schema or data-retention changes.
