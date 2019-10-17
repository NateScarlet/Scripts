"use strict";
// ==UserScript==
// @name     Auto meta viewport
// @version  1
// @run-at   document-idle
// @include	 *
// ==/UserScript==
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
