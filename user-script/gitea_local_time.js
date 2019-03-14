// ==UserScript==
// @name     Gitea local time
// @version  1
// @run-at   document-end
// @include  *
// ==/UserScript==

(function() {
  /**
   * @type {HTMLMetaElement}
   */
  const meta = document.querySelector('meta[name=keywords]');
  if (!(meta && meta.content.split(',').includes('gitea'))) {
    return;
  }
  /**
   * @type {NodeListOf<HTMLSpanElement>}
   */
  const times = document.querySelectorAll('span.time-since.poping.up');
  for (const i of times) {
    const localTime = new Date(i.dataset.content);
    if (isNaN(localTime)) {
      continue;
    }
    i.dataset.content = localTime.toLocaleString();
  }
})();
