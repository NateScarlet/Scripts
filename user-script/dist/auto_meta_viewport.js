// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     Auto meta viewport
// @description Use <meta name="viewport" content="width=device-width, initial-scale=1"> as default.
// @run-at   document-end
// @include	 *
// @version  2+20d59d4b
// ==/UserScript==

(() => {
  // auto_meta_viewport.ts
  function main() {
    if (document.querySelector('meta[name="viewport"]')) {
      return;
    }
    const el = document.createElement("meta");
    el.name = "viewport";
    el.content = "width=device-width, initial-scale=1";
    document.head.append(el);
  }
  main();
})();
