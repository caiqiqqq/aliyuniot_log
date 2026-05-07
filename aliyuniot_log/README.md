# Aliyun IoT Log Monitor

[中文使用说明](#中文使用说明) | [English Guide](#english-guide)

## 中文使用说明

Aliyun IoT Log Monitor 是一个本地运行的阿里云 IoT 控制台日志采集和分析工具。它不保存浏览器登录态，也不需要 Playwright。采集由 Chrome 扩展完成：扩展运行在你已经登录的阿里云 IoT 日志页面中，把当前页面表格、搜索总数、部分日志接口响应发送到本地服务，然后由本地页面展示趋势图和排行图。

### 功能

- 在阿里云 IoT 日志页中采集当前表格数据。
- 支持后台持续抓取当前表格，避免手动点击。
- 支持定时自动点击页面搜索按钮，并记录每次搜索总数。
- 按 TraceID 去重写入 SQLite，避免重复日志污染设备排行。
- 展示搜索总数曲线、搜索差值曲线、状态分布、设备排行、设备异常排行。
- 点击设备排行或设备异常排行的柱子，可以复制设备 ID。
- 支持导出 CSV / JSON，便于进一步分析。

### 项目结构

```text
aliyuniot_log/
├── dashboard.py              # FastAPI 服务、API 接口、静态页面入口
├── db.py                     # SQLite 表结构、迁移、写入、查询
├── extract.py                # JSON / 表格数据标准化
├── config.py                 # 本地配置读取
├── static/index.html         # ECharts 仪表盘
├── extension/                # Chrome 扩展
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js
│   ├── content.js
│   ├── page_hook.js
│   └── page_bridge.js
├── docs/ARCHITECTURE.md      # 架构解析
├── SECURITY.md               # 安全说明
├── CONTRIBUTING.md           # 贡献指南
├── CHANGELOG.md              # 变更记录
└── .env.example              # 配置模板
```

### 环境要求

- Python 3.10 或更新版本，推荐 Python 3.12+
- Google Chrome 或 Chromium 系浏览器
- 可以访问阿里云 IoT 控制台的账号

### 安装依赖

```bash
cd aliyuniot_log
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell 可使用：

```powershell
cd aliyuniot_log
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 配置

复制配置模板：

```bash
cp .env.example .env
```

默认配置如下：

```dotenv
ALIYUN_IOT_LOG_URL="https://iot.console.aliyun.com/lk/monitor/log"
ALIYUN_NETWORK_URL_KEYWORDS="iot.console.aliyun.com,log"
ALIYUN_DB_PATH="data/iot_logs.db"
```

配置说明：

| 配置项 | 说明 |
| --- | --- |
| `ALIYUN_IOT_LOG_URL` | 阿里云 IoT 日志页面地址。 |
| `ALIYUN_NETWORK_URL_KEYWORDS` | 插件拦截 JSON 响应时使用的 URL 关键词，默认要求 URL 同时包含 `iot.console.aliyun.com` 和 `log`。 |
| `ALIYUN_DB_PATH` | SQLite 数据库路径，默认写入 `data/iot_logs.db`。 |

### 启动本地服务

```bash
python3 -m uvicorn dashboard:app --host 127.0.0.1 --port 8000
```

打开页面：

```text
http://127.0.0.1:8000
```

注意：不要直接打开 `static/index.html`，页面需要调用本地 API。

### 安装 Chrome 扩展

1. 打开 Chrome 扩展管理页：

```text
chrome://extensions
```

2. 打开右上角的 `开发者模式`。
3. 点击 `加载已解压的扩展程序`。
4. 选择项目中的 `aliyuniot_log/extension` 目录。
5. 打开阿里云 IoT 日志页面：

```text
https://iot.console.aliyun.com/lk/monitor/log
```

6. 确认本地服务 `http://127.0.0.1:8000` 正在运行。
7. 点击浏览器工具栏中的扩展图标，使用弹窗里的采集功能。

### 使用方法

#### 1. 打开后台抓取

在阿里云 IoT 日志页面点击扩展图标，然后点击：

```text
开始后台抓取
```

开启后，扩展会每 5 秒检查当前表格。如果表格内容发生变化，就发送到本地 `/api/ingest`。后端会按 TraceID 去重写入数据库。

再次点击：

```text
停止后台抓取
```

即可停止。

#### 2. 打开定时搜索

在扩展弹窗里设置间隔分钟数，例如：

```text
5
```

然后点击：

```text
开始定时搜索
```

扩展会定时点击阿里云页面上的搜索按钮，等待结果稳定后采集：

- 当前表格数据
- 搜索总数
- 当前筛选信息

这些数据会用于：

- 搜索总数 / 差值曲线
- 搜索差值曲线
- 设备排行
- 设备异常排行

#### 3. 查看仪表盘

打开：

```text
http://127.0.0.1:8000
```

页面包含：

- 顶部统计：总日志、设备数、异常状态、最近筛选总数
- 采集状态：最近一次接收状态、看到条数、新增条数
- 搜索总数 / 差值曲线
- 搜索差值曲线
- 状态分布
- 设备排行
- 设备异常排行

#### 4. 复制设备 ID

在 `设备排行` 或 `设备异常排行` 中，点击某个柱子即可复制设备 ID。复制成功后，页面顶部会显示：

```text
已复制设备ID：xxxx
```

#### 5. 导出数据

点击页面顶部按钮：

```text
导出 CSV
导出 JSON
```

导出内容包括：

- 搜索总数和差值
- 状态分布
- 设备排行
- 设备异常排行

导出文件可能包含真实设备 ID 和日志统计信息，分享前请先检查。

#### 6. 清除本地数据

点击：

```text
清除数据
```

会清空本地数据库中的日志、搜索统计和运行记录。这个操作不可恢复。

### 数据口径

#### TraceID 去重

日志写入时会按 TraceID 去重：

- 如果 TraceID 已存在，跳过该条日志。
- 如果 TraceID 不存在，写入数据库。
- 如果页面文本出现 `TraceID TraceID`，会先归一化为单个 TraceID。

#### 设备排行

设备排行基于去重后的 `iot_logs` 统计：

```text
设备日志数 = 该设备在去重日志表中的记录数
```

#### 设备异常排行

以下状态视为正常：

```text
200 / OK / Success / success / true
```

其他非空状态视为异常：

```text
异常数 = 该设备下异常状态日志条数
异常率 = 异常数 / 该设备总日志数
```

#### 搜索差值

```text
差值 = 当前搜索总数 - 上一次搜索总数
```

第一条记录的差值显示为 `0`。

### 常见问题

#### 页面提示不能直接打开 HTML

请使用：

```text
http://127.0.0.1:8000
```

不要使用：

```text
file:///.../static/index.html
```

#### 扩展提示“请先打开阿里云 IoT 日志页”

请确认当前浏览器标签页地址以此开头：

```text
https://iot.console.aliyun.com/lk/monitor/log
```

#### 扩展提示采集脚本没有注入成功

刷新阿里云日志页后再打开扩展弹窗。如果仍然失败，到 `chrome://extensions` 中重新加载扩展。

#### 仪表盘没有数据

确认：

- 本地服务正在运行。
- 已通过 `http://127.0.0.1:8000` 打开仪表盘。
- Chrome 扩展已经加载。
- 阿里云 IoT 日志页已打开且已登录。
- 扩展中已开启后台抓取或定时搜索。

#### 数据重复或排行不对

当前版本按 TraceID 去重。请确认日志表格中能采集到 TraceID 字段。如果页面列名或结构变化导致无法识别 TraceID，需要调整 `extract.py` 中的字段识别逻辑。

### 开源和数据安全

不要提交以下内容：

- `.env`
- `data/`
- `artifacts/`
- `.venv/`
- `__pycache__/`
- 浏览器 profile
- Cookie
- 登录态
- 截图
- 导出的真实生产日志

其中 `data/iot_logs.db` 会包含真实 TraceID、设备 ID、状态和日志内容，不能公开。

### 更多文档

- [架构解析](docs/ARCHITECTURE.md)
- [贡献指南](CONTRIBUTING.md)
- [安全说明](SECURITY.md)
- [变更记录](CHANGELOG.md)
- [许可证](LICENSE)

## English Guide

Aliyun IoT Log Monitor is a local Alibaba Cloud IoT console log collection and
analysis tool. It does not store browser login state and does not require
Playwright. Collection is handled by a Chrome extension running in your already
logged-in Alibaba Cloud IoT log page. The extension sends table data, search
totals, and selected JSON responses to a local FastAPI service. The dashboard
then visualizes the data with ECharts.

### Features

- Collect table data from the Alibaba Cloud IoT log page.
- Watch the current table in the background.
- Run timed searches and record search total counts.
- Deduplicate logs by TraceID before writing to SQLite.
- Show search total trends, delta trends, status distribution, device ranking,
  and device error ranking.
- Click a device ranking bar to copy the device ID.
- Export CSV / JSON for further analysis.

### Project Structure

```text
aliyuniot_log/
├── dashboard.py              # FastAPI app, APIs, static dashboard
├── db.py                     # SQLite schema, migration, insert/query helpers
├── extract.py                # JSON/table normalization
├── config.py                 # Local configuration
├── static/index.html         # ECharts dashboard
├── extension/                # Chrome extension
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js
│   ├── content.js
│   ├── page_hook.js
│   └── page_bridge.js
├── docs/ARCHITECTURE.md
├── SECURITY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── .env.example
```

### Requirements

- Python 3.10 or newer, Python 3.12+ recommended
- Google Chrome or a Chromium-based browser
- An Alibaba Cloud account with access to the IoT console log page

### Install Dependencies

```bash
cd aliyuniot_log
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For Windows PowerShell:

```powershell
cd aliyuniot_log
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Default configuration:

```dotenv
ALIYUN_IOT_LOG_URL="https://iot.console.aliyun.com/lk/monitor/log"
ALIYUN_NETWORK_URL_KEYWORDS="iot.console.aliyun.com,log"
ALIYUN_DB_PATH="data/iot_logs.db"
```

| Variable | Description |
| --- | --- |
| `ALIYUN_IOT_LOG_URL` | Alibaba Cloud IoT log page URL. |
| `ALIYUN_NETWORK_URL_KEYWORDS` | URL keywords used by the extension when capturing JSON responses. |
| `ALIYUN_DB_PATH` | SQLite database path. Defaults to `data/iot_logs.db`. |

### Start the Local Server

```bash
python3 -m uvicorn dashboard:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Do not open `static/index.html` directly. The dashboard needs the local API.

### Install the Chrome Extension

1. Open:

```text
chrome://extensions
```

2. Enable `Developer mode`.
3. Click `Load unpacked`.
4. Select the `aliyuniot_log/extension` directory.
5. Open the Alibaba Cloud IoT log page:

```text
https://iot.console.aliyun.com/lk/monitor/log
```

6. Keep the local service running at `http://127.0.0.1:8000`.
7. Click the extension icon and use the popup controls.

### Usage

#### 1. Start Background Collection

Open the extension popup on the Alibaba Cloud IoT log page and click:

```text
开始后台抓取
```

The extension checks the current table every 5 seconds. If the table changes,
it sends the new table to `/api/ingest`. The backend deduplicates records by
TraceID.

Click again to stop:

```text
停止后台抓取
```

#### 2. Start Timed Search

Set the interval in minutes, for example:

```text
5
```

Then click:

```text
开始定时搜索
```

The extension periodically clicks the search button on the Alibaba Cloud page,
waits for the result to settle, and collects:

- current table data
- search total count
- current filter metadata

This data powers:

- search total and delta trend
- search delta trend
- device ranking
- device error ranking

#### 3. View the Dashboard

Open:

```text
http://127.0.0.1:8000
```

The dashboard includes:

- summary metrics: total logs, device count, error count, latest search total
- receive status: last ingest status, seen count, inserted count
- search total / delta trend
- search delta trend
- status distribution
- device ranking
- device error ranking

#### 4. Copy Device ID

Click a bar in `设备排行` or `设备异常排行`. The device ID will be copied to
your clipboard, and the dashboard header will show:

```text
已复制设备ID：xxxx
```

#### 5. Export Data

Use:

```text
导出 CSV
导出 JSON
```

Exports include:

- search totals and deltas
- status distribution
- device ranking
- device error ranking

Exports may contain real device IDs and operational data. Review before sharing.

#### 6. Clear Local Data

Click:

```text
清除数据
```

This clears local logs, search snapshots, and ingest history. This action cannot
be undone.

### Metric Definitions

#### TraceID Deduplication

Logs are deduplicated by TraceID:

- If the TraceID already exists, the record is skipped.
- If the TraceID does not exist, the record is inserted.
- If the page shows duplicated text such as `TraceID TraceID`, it is normalized
  before comparison.

#### Device Ranking

Device ranking is based on deduplicated records in `iot_logs`:

```text
device log count = number of deduplicated records for that device
```

#### Device Error Ranking

These statuses are considered normal:

```text
200 / OK / Success / success / true
```

Any other non-empty status is treated as an error:

```text
error count = error records for the device
error rate  = error count / total records for the device
```

#### Search Delta

```text
delta = current search total - previous search total
```

The first delta point is `0`.

### Troubleshooting

#### The dashboard says not to open HTML directly

Use:

```text
http://127.0.0.1:8000
```

Do not use:

```text
file:///.../static/index.html
```

#### The extension says to open the IoT log page first

Make sure the active tab URL starts with:

```text
https://iot.console.aliyun.com/lk/monitor/log
```

#### The collector script failed to inject

Refresh the Alibaba Cloud IoT log page and try again. If it still fails, reload
the extension from `chrome://extensions`.

#### The dashboard has no data

Check that:

- the local server is running
- the dashboard was opened via `http://127.0.0.1:8000`
- the Chrome extension is loaded
- the Alibaba Cloud IoT log page is open and logged in
- background collection or timed search is enabled

#### Ranking looks duplicated or wrong

The current version deduplicates by TraceID. Confirm that the table includes a
TraceID field and that it can be recognized. If the console page changes its
column names or layout, update the field mapping in `extract.py`.

### Open Source and Data Safety

Do not commit:

- `.env`
- `data/`
- `artifacts/`
- `.venv/`
- `__pycache__/`
- browser profiles
- cookies
- login state
- screenshots
- exported production logs

`data/iot_logs.db` can contain real TraceIDs, device IDs, statuses, and log
content. Never publish it.

### More Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)
