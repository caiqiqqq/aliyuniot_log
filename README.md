# Aliyun IoT Log Monitor

[中文说明](#中文) | [English](#english)

## 中文

Aliyun IoT Log Monitor 是一个本地运行的阿里云 IoT 控制台日志采集和分析工具。它通过 Chrome 扩展在你已经登录的阿里云 IoT 日志页面中采集数据，再发送到本地 FastAPI 服务，由 SQLite 存储并通过 ECharts 仪表盘展示。

项目目录：

```text
aliyuniot_log/
```

详细使用方法请看：

- [完整中文使用说明](aliyuniot_log/README.md#中文使用说明)
- [架构解析](aliyuniot_log/docs/ARCHITECTURE.md)
- [安全说明](aliyuniot_log/SECURITY.md)
- [贡献指南](aliyuniot_log/CONTRIBUTING.md)

快速启动：

```bash
cd aliyuniot_log
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn dashboard:app --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

然后在 Chrome 扩展管理页加载 `aliyuniot_log/extension` 目录。

## English

Aliyun IoT Log Monitor is a local dashboard and Chrome extension for collecting
and analyzing Alibaba Cloud IoT console logs. The extension runs in your already
logged-in Alibaba Cloud IoT log page and sends collected data to a local FastAPI
service backed by SQLite and ECharts.

Project directory:

```text
aliyuniot_log/
```

Detailed documentation:

- [Full English usage guide](aliyuniot_log/README.md#english-guide)
- [Architecture](aliyuniot_log/docs/ARCHITECTURE.md)
- [Security](aliyuniot_log/SECURITY.md)
- [Contributing](aliyuniot_log/CONTRIBUTING.md)

Quick start:

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

Then load the Chrome extension from `aliyuniot_log/extension`.

## Data Safety

Do not commit or publish local runtime data:

- `.env`
- `data/`
- `.venv/`
- screenshots
- exported production logs
- browser profiles, cookies, or storage state
