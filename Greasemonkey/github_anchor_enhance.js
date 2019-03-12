// ==UserScript==
// @name     Github anchor enhance
// @version  2
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

        appendStarsBadge(el);
        appendFollowersBadge(el);
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
  const className = 'added-stars-badge';
  if (el.classList.contains(className)) {
    return;
  }
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
          el.classList.add(className);
        }
      },
      onerror: console.error
    });
  }
}
/**
 *
 * @param {HTMLAnchorElement} el
 */
async function appendFollowersBadge(el) {
  const className = 'added-followers-badge';
  if (el.classList.contains(className)) {
    return;
  }
  const match = el.href && el.href.match(/https:\/\/github.com\/([^\/]+)$/);

  if (match) {
    const [_, user] = match;
    GM.xmlHttpRequest({
      method: 'GET',
      url: `https://img.shields.io/github/followers/${user}.svg?style=social`,
      onload: resp => {
        if (resp.status === 200) {
          el.innerHTML += resp.response;
          el.classList.add(className);
        }
      },
      onerror: console.error
    });
  }
}
