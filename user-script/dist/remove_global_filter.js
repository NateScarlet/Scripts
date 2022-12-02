// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     Remove Global Filter 移除全局滤镜
// @description remove global filter (e.g. grayscale) 移除全局滤镜（例如黑白效果）
// @grant    none
// @run-at   document-end
// @include	 *
// @version   2022.12.02+af3e7da6
// ==/UserScript==

(() => {
  // remove_global_filter.ts
  (function() {
    const style = new CSSStyleSheet();
    style.replaceSync("html { filter: none !important; }");
    document.adoptedStyleSheets.push(style);
  })();
})();
