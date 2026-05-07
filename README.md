# Aliyun IoT Log Monitor

Local dashboard and Chrome extension for collecting and analyzing Alibaba Cloud
IoT console log data.

The project lives in [`aliyuniot_log`](aliyuniot_log/).

## Quick Start

```bash
cd aliyuniot_log
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn dashboard:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Install the Chrome extension from [`aliyuniot_log/extension`](aliyuniot_log/extension/).

## Documentation

- [Project README](aliyuniot_log/README.md)
- [Architecture](aliyuniot_log/docs/ARCHITECTURE.md)
- [Contributing](aliyuniot_log/CONTRIBUTING.md)
- [Security](aliyuniot_log/SECURITY.md)
- [Changelog](aliyuniot_log/CHANGELOG.md)

## Data Safety

Do not commit local runtime data such as `.env`, `data/`, `.venv/`,
screenshots, browser profiles, cookies, or exported production logs.
