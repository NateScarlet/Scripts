// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     Remove Global Filter 移除全局滤镜
// @description remove global filter (e.g. grayscale) 移除全局滤镜（例如黑白效果）
// @grant    none
// @run-at   document-idle
// @include	 *
// @version   2022.12.02+ce456bb8
// ==/UserScript==

(() => {
  // utils/injectStyle.ts
  function injectStyle(css) {
    const style = document.createElement("style");
    style.innerHTML = css;
    document.head.appendChild(style);
    const dispose = () => {
      style.remove();
    };
    return {
      dispose
    };
  }

  // remove_global_filter.ts
  injectStyle("html { filter: none !important; }");
})();
