(function injectBridge() {
  const script = document.createElement("script");
  script.src = chrome.runtime.getURL("page_bridge.js");
  script.onload = () => script.remove();
  (document.documentElement || document.head).appendChild(script);
})();

