// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     Remove Global Filter 移除全局滤镜
// @description remove global filter (e.g. grayscale) 移除全局滤镜（例如黑白效果）
// @grant    none
// @run-at   document-idle
// @include	 *
// ==/UserScript==

export {};

declare global {
  interface CSSStyleSheet {
    replaceSync(body: string): string;
  }
  interface Document {
    readonly adoptedStyleSheets: CSSStyleSheet[];
  }
}

(function () {
  const style = new CSSStyleSheet();
  style.replaceSync("html { filter: none !important; }");
  document.adoptedStyleSheets.push(style);
})();
