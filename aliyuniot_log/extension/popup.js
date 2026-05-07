const statusEl = document.getElementById("status");
const collectButton = document.getElementById("collect");
const searchTimerButton = document.getElementById("searchTimer");
const searchIntervalInput = document.getElementById("searchInterval");

let watchRunning = false;
let searchTimerRunning = false;

collectButton.addEventListener("click", toggleWatch);
searchTimerButton.addEventListener("click", toggleSearchTimer);
init();

async function init() {
  try {
    const tab = await currentLogTab();
    await ensureCollector(tab.id);
    const [watchStatus, timerStatus] = await Promise.all([
      chrome.tabs.sendMessage(tab.id, { type: "TABLE_WATCH_STATUS" }),
      chrome.tabs.sendMessage(tab.id, { type: "SEARCH_TIMER_STATUS" }),
    ]);
    setRunning(Boolean(watchStatus?.running));
    setSearchTimerRunning(Boolean(timerStatus?.running));
    if (timerStatus?.minutes) searchIntervalInput.value = timerStatus.minutes;
    statusEl.textContent = statusText();
  } catch (error) {
    statusEl.textContent = normalizeError(error);
    setRunning(false);
    setSearchTimerRunning(false);
  }
}

async function toggleWatch() {
  setBusy(true);
  statusEl.textContent = watchRunning ? "正在停止后台抓取" : "正在启动后台抓取";
  try {
    const tab = await currentLogTab();
    await ensureCollector(tab.id);
    const result = await chrome.tabs.sendMessage(tab.id, {
      type: watchRunning ? "STOP_TABLE_WATCH" : "START_TABLE_WATCH",
    });
    if (!result?.ok) throw new Error(result?.error || "操作失败");
    setRunning(Boolean(result.running));
    statusEl.textContent = result.running
      ? formatCollectResult("后台抓取已开启", result)
      : "后台抓取已停止";
  } catch (error) {
    statusEl.textContent = normalizeError(error);
  } finally {
    setBusy(false);
  }
}

async function toggleSearchTimer() {
  setBusy(true);
  statusEl.textContent = searchTimerRunning ? "正在停止定时搜索" : "正在启动定时搜索";
  try {
    const tab = await currentLogTab();
    await ensureCollector(tab.id);
    const minutes = Math.max(1, Number.parseInt(searchIntervalInput.value || "5", 10));
    const result = await chrome.tabs.sendMessage(tab.id, {
      type: searchTimerRunning ? "STOP_SEARCH_TIMER" : "START_SEARCH_TIMER",
      minutes,
    });
    if (!result?.ok) throw new Error(result?.error || "操作失败");
    setSearchTimerRunning(Boolean(result.running));
    statusEl.textContent = result.running
      ? formatCollectResult(`定时搜索已开启，每 ${result.minutes} 分钟`, result)
      : "定时搜索已停止";
  } catch (error) {
    statusEl.textContent = normalizeError(error);
  } finally {
    setBusy(false);
  }
}

async function currentLogTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !String(tab.url || "").startsWith("https://iot.console.aliyun.com/lk/monitor/log")) {
    throw new Error("请先打开阿里云 IoT 日志页。");
  }
  return tab;
}

async function ensureCollector(tabId) {
  const ping = await sendMessage(tabId, { type: "PING" });
  if (ping?.ok) return;
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["page_hook.js", "content.js"],
  });
  const retry = await sendMessage(tabId, { type: "PING" });
  if (!retry?.ok) {
    throw new Error("采集脚本没有注入成功，请刷新阿里云日志页后重试。");
  }
}

function sendMessage(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      if (chrome.runtime.lastError) {
        resolve(null);
        return;
      }
      resolve(response);
    });
  });
}

function setRunning(isRunning) {
  watchRunning = isRunning;
  collectButton.textContent = isRunning ? "停止后台抓取" : "开始后台抓取";
  collectButton.classList.toggle("secondary", isRunning);
}

function setSearchTimerRunning(isRunning) {
  searchTimerRunning = isRunning;
  searchTimerButton.textContent = isRunning ? "停止定时搜索" : "开始定时搜索";
  searchTimerButton.classList.toggle("secondary", isRunning);
  searchIntervalInput.disabled = isRunning;
}

function setBusy(isBusy) {
  collectButton.disabled = isBusy;
  searchTimerButton.disabled = isBusy;
  searchIntervalInput.disabled = isBusy || searchTimerRunning;
}

function statusText() {
  if (watchRunning && searchTimerRunning) return "后台抓取和定时搜索运行中";
  if (watchRunning) return "后台抓取运行中";
  if (searchTimerRunning) return "定时搜索运行中";
  return "后台任务未开启";
}

function formatCollectResult(prefix, result) {
  if (result.skipped) return `${prefix}，当前表格无变化`;
  const totalText = result.total_count == null ? "" : `，总数 ${result.total_count} 条`;
  return `${prefix}：看到 ${result.seen || 0} 条，新增 ${result.inserted || 0} 条${totalText}`;
}

function normalizeError(error) {
  const message = String(error?.message || error || "");
  if (message.includes("Receiving end does not exist")) {
    return "页面采集脚本未连接，请刷新阿里云日志页后重试。";
  }
  return message || "操作失败";
}
