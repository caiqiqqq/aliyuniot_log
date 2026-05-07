# Aliyun IoT Log Monitor

一个本地运行的阿里云 IoT 控制台日志分析工具。采集侧使用 Chrome 扩展直接运行在已经登录的阿里云 IoT 日志页面里，把当前页面表格、搜索总数和接口响应发送到本地 FastAPI 服务；展示侧使用 ECharts 做趋势、排行和分布分析。

## 功能

- 插件后台采集当前日志页表格，按 TraceID 去重写入 SQLite。
- 定时自动搜索并记录搜索总数，生成总数曲线和差值曲线。
- 展示状态分布、设备排行、设备异常排行。
- 支持点击设备排行柱子复制设备 ID。
- 支持导出 CSV / JSON。

## 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 启动本地服务

```bash
python3 -m uvicorn dashboard:app --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000
```

不要直接打开 `static/index.html`，页面需要后端 API。

## 安装 Chrome 扩展

1. 打开 Chrome 扩展管理页：

```text
chrome://extensions
```

2. 打开右上角 `开发者模式`。
3. 点击 `加载已解压的扩展程序`。
4. 选择项目里的 `extension` 目录。
5. 在正常 Chrome 里打开阿里云 IoT 日志页面：

```text
https://iot.console.aliyun.com/lk/monitor/log
```

6. 保持本地服务 `http://127.0.0.1:8000` 运行。

## 配置

```bash
cp .env.example .env
```

默认配置：

```dotenv
ALIYUN_IOT_LOG_URL="https://iot.console.aliyun.com/lk/monitor/log"
ALIYUN_NETWORK_URL_KEYWORDS="iot.console.aliyun.com,log"
ALIYUN_DB_PATH="data/iot_logs.db"
```

## 开源注意

不要提交以下本地运行数据：

- `.env`
- `data/`
- `artifacts/`
- `.venv/`
- `__pycache__/`

其中 `data/` 可能包含真实日志数据库，`artifacts/` 可能包含页面截图。

## 限制

- 这是控制台页面采集，不是阿里云官方稳定 API。
- 登录态由用户自己的 Chrome 页面负责，扩展不会保存登录 Cookie。
- 控制台页面结构变化后，可能需要调整采集逻辑。
