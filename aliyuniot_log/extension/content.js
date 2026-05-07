const API_BASE = "http://127.0.0.1:8000";
const TABLE_WATCH_INTERVAL_MS = 5000;
const CONTENT_FEATURES = ["tableWatch", "searchTimer"];

if (!globalThis.__ALIYUN_IOT_LOG_COLLECTOR_CONTENT_V5__) {
  globalThis.__ALIYUN_IOT_LOG_COLLECTOR_CONTENT_V5__ = true;

  let lastSnapshotKey = "";
  let lastTableWatchKey = "";
  let tableWatchTimer = 0;
  let searchTimer = 0;
  let searchTimerMinutes = 0;

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.type !== "ALIYUN_IOT_LOG_JSON") return;
    setTimeout(() => {
      ingest({
        source: `extension:${String(data.url || "").slice(0, 180)}`,
        json: data.json,
        search_snapshot: collectSearchSnapshot("extension:json_response"),
      }).catch(() => {});
    }, 600);
  });

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "COLLECT_TABLE") {
      collectTable("extension:dom_table")
        .then((result) => sendResponse(result))
        .catch((error) => sendResponse({ ok: false, error: error.message }));
      return true;
    }
    if (message?.type === "START_TABLE_WATCH") {
      startTableWatch()
        .then((result) => sendResponse(result))
        .catch((error) => sendResponse({ ok: false, error: error.message }));
      return true;
    }
    if (message?.type === "STOP_TABLE_WATCH") {
      stopTableWatch();
      sendResponse({ ok: true, running: false });
      return false;
    }
    if (message?.type === "TABLE_WATCH_STATUS") {
      sendResponse({ ok: true, running: Boolean(tableWatchTimer), interval_ms: TABLE_WATCH_INTERVAL_MS });
      return false;
    }
    if (message?.type === "START_SEARCH_TIMER") {
      startSearchTimer(message.minutes)
        .then((result) => sendResponse(result))
        .catch((error) => sendResponse({ ok: false, error: error.message }));
      return true;
    }
    if (message?.type === "STOP_SEARCH_TIMER") {
      stopSearchTimer();
      sendResponse({ ok: true, running: false });
      return false;
    }
    if (message?.type === "SEARCH_TIMER_STATUS") {
      sendResponse({ ok: true, running: Boolean(searchTimer), minutes: searchTimerMinutes });
      return false;
    }
    if (message?.type === "PING") {
      sendResponse({ ok: true, url: location.href, features: CONTENT_FEATURES });
      return false;
    }
    return false;
  });

  startSnapshotWatcher();

  async function startTableWatch() {
    if (tableWatchTimer) {
      return { ok: true, running: true, skipped: true };
    }
    lastTableWatchKey = "";
    const first = await collectTableIfChanged(true);
    tableWatchTimer = window.setInterval(() => {
      collectTableIfChanged(false).catch((error) => console.warn("[Aliyun IoT Log Collector]", error));
    }, TABLE_WATCH_INTERVAL_MS);
    return { ok: true, running: true, ...first };
  }

  function stopTableWatch() {
    if (!tableWatchTimer) return;
    window.clearInterval(tableWatchTimer);
    tableWatchTimer = 0;
  }

  async function startSearchTimer(minutes) {
    const normalizedMinutes = Math.max(1, Number.parseInt(String(minutes || "5"), 10));
    stopSearchTimer();
    searchTimerMinutes = normalizedMinutes;
    const first = await searchAndCollect();
    searchTimer = window.setInterval(() => {
      searchAndCollect().catch((error) => console.warn("[Aliyun IoT Log Collector]", error));
    }, normalizedMinutes * 60 * 1000);
    return { ok: true, running: true, minutes: normalizedMinutes, ...first };
  }

  function stopSearchTimer() {
    if (searchTimer) {
      window.clearInterval(searchTimer);
      searchTimer = 0;
    }
  }

  async function searchAndCollect() {
    const before = pageSignature();
    const searchButton = findSearchButton();
    if (!searchButton) throw new Error("没有找到阿里云页面上的“搜索”按钮");
    dispatchClick(searchButton);
    await waitForSearchSettled(before);
    const fingerprint = `search_timer:${Date.now()}:${pageSignature()}`;
    return collectTable("extension:search_timer", { fingerprint });
  }

  async function collectTable(source, snapshotPatch = {}) {
    const payload = tablePayload(source, snapshotPatch);
    const result = await ingest({
      source,
      headers: payload.headers,
      rows: payload.rows,
      search_snapshot: payload.snapshot,
    });
    return { ok: true, total_count: payload.snapshot.total_count, ...result };
  }

  async function collectTableIfChanged(force) {
    const payload = tablePayload("extension:table_watch");
    const key = JSON.stringify({
      headers: payload.headers,
      rows: payload.rows,
      filters: payload.snapshot.filters,
      page: payload.snapshot.page,
      page_count: payload.snapshot.page_count,
      total_count: payload.snapshot.total_count,
    });
    if (!force && key === lastTableWatchKey) {
      return { ok: true, skipped: true, seen: 0, inserted: 0, total_count: payload.snapshot.total_count };
    }
    lastTableWatchKey = key;
    const result = await ingest({
      source: "extension:table_watch",
      headers: payload.headers,
      rows: payload.rows,
      search_snapshot: payload.snapshot,
    });
    return { ok: true, total_count: payload.snapshot.total_count, ...result };
  }

  function tablePayload(source, snapshotPatch = {}) {
    const table = document.querySelector("table");
    if (!table) throw new Error("当前页面没有找到表格");
    const snapshot = { ...collectSearchSnapshot(source), ...snapshotPatch };
    const headers = Array.from(table.querySelectorAll("thead th")).map((cell) => normalizeText(cell.innerText));
    const rows = Array.from(table.querySelectorAll("tbody tr")).map((row) =>
      Array.from(row.querySelectorAll("th,td")).map((cell) => normalizeText(cell.innerText))
    );
    return { headers, rows, snapshot };
  }

  function startSnapshotWatcher() {
    const send = debounce(() => sendSearchSnapshot("extension:dom_watch"), 900);
    if (document.body) {
      new MutationObserver(send).observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
      });
      setTimeout(send, 1200);
      return;
    }
    window.addEventListener("DOMContentLoaded", () => startSnapshotWatcher(), { once: true });
  }

  async function sendSearchSnapshot(source) {
    const snapshot = collectSearchSnapshot(source);
    if (snapshot.total_count == null) return;
    const key = JSON.stringify({
      active_tab: snapshot.active_tab,
      filters: snapshot.filters,
      page: snapshot.page,
      page_count: snapshot.page_count,
      page_size: snapshot.page_size,
      total_count: snapshot.total_count,
    });
    if (key === lastSnapshotKey) return;
    lastSnapshotKey = key;
    await ingest({ source, search_snapshot: snapshot });
  }

  async function ingest(payload) {
    const response = await fetch(`${API_BASE}/api/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || `本地服务返回 ${response.status}`);
    }
    return data;
  }

  function collectSearchSnapshot(source) {
    const pageText = normalizeText(document.body?.innerText || "");
    return {
      source,
      active_tab: getActiveTab(),
      total_count: extractTotalCount(pageText),
      page: extractCurrentPage(pageText),
      page_count: extractPageCount(pageText),
      page_size: extractPageSize(),
      filters: collectFilters(),
      raw_text: extractPaginationText(pageText),
    };
  }

  function collectFilters() {
    const filters = {};
    for (const element of document.querySelectorAll("input, textarea, select")) {
      const value = normalizeText(element.value || element.getAttribute("value") || "");
      if (!value || isDefaultFilterValue(value)) continue;
      const key = fieldNameFor(element);
      filters[key] = value;
    }
    collectSelectLikeFilters(filters);
    return filters;
  }

  function collectSelectLikeFilters(filters) {
    const nodes = Array.from(
      document.querySelectorAll('[role="combobox"], [class*="select"][title], [class*="select"] [title]')
    );
    let index = 1;
    for (const node of nodes) {
      if (node.closest('[role="option"], [class*="menu"], [class*="overlay"], [class*="popup"]')) continue;
      const value = normalizeText(node.getAttribute("title") || node.innerText || "");
      if (!value || value.length > 50 || isDefaultFilterValue(value)) continue;
      if (/请选择|搜索|输入|查看|确定/.test(value)) continue;
      if (Object.values(filters).includes(value)) continue;
      if (isLikelyBusinessType(value)) {
        filters.bizType = value;
      } else {
        filters[`select_${index}`] = value;
        index += 1;
      }
    }
  }

  function fieldNameFor(element) {
    const text = [
      element.getAttribute("placeholder"),
      element.getAttribute("aria-label"),
      element.getAttribute("name"),
      element.id,
      element.className,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    if (text.includes("device")) return "deviceName";
    if (text.includes("trace")) return "traceId";
    if (text.includes("message")) return "messageId_or_content";
    if (text.includes("status") || text.includes("状态")) return "status";
    return `field_${element.tagName.toLowerCase()}`;
  }

  function getActiveTab() {
    const candidates = Array.from(document.querySelectorAll('[class*="active"], [aria-selected="true"]'))
      .map((node) => normalizeText(node.innerText))
      .filter((text) => text && text.length <= 30);
    return candidates.find((text) => text.includes("日志") || text.includes("轨迹")) || "";
  }

  function extractTotalCount(text) {
    const patterns = [/共有\s*([\d,]+)\s*条/, /共\s*([\d,]+)\s*条/, /total\s*:?\s*([\d,]+)/i];
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) return Number(match[1].replaceAll(",", ""));
    }
    return null;
  }

  function extractCurrentPage(text) {
    const match = text.match(/(?:^|\s)(\d+)\s*\/\s*\d+(?:\s|$)/);
    return match ? Number(match[1]) : null;
  }

  function extractPageCount(text) {
    const match = text.match(/(?:^|\s)\d+\s*\/\s*(\d+)(?:\s|$)/);
    return match ? Number(match[1]) : null;
  }

  function extractPageSize() {
    const selected = Array.from(document.querySelectorAll("select option:checked"))
      .map((item) => normalizeText(item.innerText || item.value))
      .find((text) => /\d+\s*条/.test(text));
    const match = selected?.match(/\d+/);
    return match ? Number(match[0]) : null;
  }

  function extractPaginationText(text) {
    const match = text.match(/.{0,40}(?:共有|共)\s*[\d,]+\s*条.{0,40}/);
    return match ? match[0] : "";
  }

  function findSearchButton() {
    const candidates = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'));
    for (const node of candidates) {
      if (!isVisible(node)) continue;
      if (normalizeText(node.innerText || node.textContent) !== "搜索") continue;
      const clickable = node.closest("button, [role='button'], a") || node;
      if (isVisible(clickable)) return clickable;
    }
    return null;
  }

  function waitForSearchSettled(before) {
    return new Promise((resolve) => {
      const startedAt = Date.now();
      let stableSince = 0;
      const timer = window.setInterval(() => {
        const current = pageSignature();
        const changed = current !== before;
        if (changed && !stableSince) stableSince = Date.now();
        if ((changed && Date.now() - stableSince > 1000) || Date.now() - startedAt > 8000) {
          window.clearInterval(timer);
          resolve();
        }
      }, 250);
    });
  }

  function pageSignature() {
    const tableText = normalizeText(document.querySelector("table")?.innerText || "").slice(0, 500);
    const snapshot = collectSearchSnapshot("extension:signature");
    return JSON.stringify({
      tableText,
      total_count: snapshot.total_count,
      page: snapshot.page,
      page_count: snapshot.page_count,
      filters: snapshot.filters,
    });
  }

  function dispatchClick(node) {
    const rect = node.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const target = document.elementFromPoint(x, y) || node;
    const eventInit = {
      bubbles: true,
      cancelable: true,
      view: window,
      clientX: x,
      clientY: y,
      button: 0,
      buttons: 1,
    };
    target.dispatchEvent(new MouseEvent("mousedown", eventInit));
    target.dispatchEvent(new MouseEvent("mouseup", { ...eventInit, buttons: 0 }));
    target.dispatchEvent(new MouseEvent("click", { ...eventInit, buttons: 0 }));
    if (target !== node) node.click();
  }

  function isVisible(node) {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  }

  function isDefaultFilterValue(value) {
    return /^(全部状态|全部业务类型)$/.test(value) || /\d+\s*(分钟|小时|天)$/.test(value);
  }

  function isLikelyBusinessType(value) {
    if (isDefaultFilterValue(value)) return false;
    if (/日志服务|LoRa|产品|云端运行日志|设备本地日志|消息轨迹|转储/.test(value)) return false;
    return /OTA|消息|物模型|时序|远程|拓扑|设备行为|设备到云|云到设备|API|服务端订阅|设备影子|云产品|订阅|取消订阅|设备任务|安全隧道|文件上传|其它/.test(value);
  }

  function debounce(fn, wait) {
    let timer = 0;
    return () => {
      clearTimeout(timer);
      timer = setTimeout(fn, wait);
    };
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }
}
