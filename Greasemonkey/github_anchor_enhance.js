// ==UserScript==
// @name     Github anchor enhance
// @version  1
// @grant    GM.xmlHttpRequest
// @run-at   document-idle
// @include	 *
// ==/UserScript==

(async function() {
  document.addEventListener(
    'mouseover',
    e => {
      if (e.target && e.target.nodeName == 'A') {
        /** @type {HTMLAnchorElement} */
        const el = e.target;
        if (el.classList.contains('added-starts-badge')) {
          return;
        }
        appendStarsBadge(el);
        el.classList.add('added-starts-badge');
      }
    },
    {}
  );
})();

/**
 *
 * @param {HTMLAnchorElement} el
 */
async function appendStarsBadge(el) {
  const match =
    el.href && el.href.match(/https:\/\/github.com\/([^\/]+)\/([^\/]+)$/);

  if (match) {
    const [_, user, repository] = match;
    GM.xmlHttpRequest({
      method: 'GET',
      url: `https://img.shields.io/github/stars/${user}/${repository}.svg?style=social`,
      onload: resp => {
        if (resp.status === 200) {
          el.innerHTML += resp.response;
        }
      },
      onerror: console.error
    });
  }
}
