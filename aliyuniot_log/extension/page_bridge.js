(function () {
  const TARGET_KEYWORDS = ["iot.console.aliyun.com", "log"];

  function shouldCapture(url) {
    const text = String(url || "").toLowerCase();
    return TARGET_KEYWORDS.every((keyword) => text.includes(keyword));
  }

  function publish(url, json) {
    window.postMessage(
      {
        type: "ALIYUN_IOT_LOG_JSON",
        url,
        json,
      },
      "*"
    );
  }

  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const response = await originalFetch.apply(this, args);
    const url = response.url || args[0];
    if (shouldCapture(url)) {
      response
        .clone()
        .json()
        .then((json) => publish(String(url), json))
        .catch(() => {});
    }
    return response;
  };

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__aliyunIotLogUrl = url;
    return originalOpen.call(this, method, url, ...rest);
  };

  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener("load", function () {
      const url = this.responseURL || this.__aliyunIotLogUrl;
      if (!shouldCapture(url)) return;
      try {
        const contentType = this.getResponseHeader("content-type") || "";
        if (!contentType.toLowerCase().includes("json")) return;
        publish(String(url), JSON.parse(this.responseText));
      } catch (_) {}
    });
    return originalSend.apply(this, args);
  };
})();

