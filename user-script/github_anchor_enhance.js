// ==UserScript==
// @name     Github anchor enhance
// @version  7
// @grant    GM.xmlHttpRequest
// @run-at   document-idle
// @include	 *
// ==/UserScript==

(async function() {
  document.addEventListener(
    'mouseover',
    async e => {
      if (e.target && e.target.nodeName == 'A') {
        /** @type {HTMLAnchorElement} */
        const el = e.target;
        try {
          await Promise.all([
            appendStarsBadge(el),
            appendLastCommitBadge(el),
            appendFollowersBadge(el),
          ]);
        } catch (err) {
          console.error(err);
        }
      }
    },
    {}
  );
})();

const reservedUsername = [
  'topics',
  'search',
  'ghost',
  'pulls',
  'issues',
  'marketplace',
  'explore',
  'discover',
  'notifications',
  'new',
  'organizations',
  'settings',
  'site',
  'about',
  'contact',
  'pricing',
];

/**
 *
 * @param {HTMLAnchorElement} el
 */
async function appendStarsBadge(el) {
  const match =
    el.href && el.href.match(/https:\/\/github.com\/([^\/]+)\/([^\/\?]+)$/);

  if (match) {
    const [_, user, repository] = match;
    if (reservedUsername.includes(user)) {
      return;
    }
    await appendBadge(
      el,
      'added-stars-badge',
      `https://img.shields.io/github/stars/${user}/${repository}.svg?style=social`
    );
  }
}
/**
 *
 * @param {HTMLAnchorElement} el
 */
async function appendLastCommitBadge(el) {
  const match =
    el.href && el.href.match(/https:\/\/github.com\/([^\/]+)\/([^\/\?]+)$/);

  if (match) {
    const [_, user, repository] = match;
    if (reservedUsername.includes(user)) {
      return;
    }
    await appendBadge(
      el,
      'added-last-commit-badge',
      `https://img.shields.io/github/last-commit/${user}/${repository}.svg`
    );
  }
}
/**
 *
 * @param {HTMLAnchorElement} el
 */
async function appendFollowersBadge(el) {
  const match = el.href && el.href.match(/https:\/\/github.com\/([^\/\?]+)$/);

  if (match) {
    const [_, user] = match;
    if (reservedUsername.includes(user)) {
      return;
    }
    await appendBadge(
      el,
      'added-followers-badge',
      `https://img.shields.io/github/followers/${user}.svg?style=social`
    );
  }
}

/**
 * @param {HTMLElement} el
 * @param {string} className
 * @param {string} url
 */
async function appendBadge(el, className, url) {
  if (el.classList.contains(className)) {
    return;
  }
  return new Promise((resolve, reject) => {
    GM.xmlHttpRequest({
      method: 'GET',
      url: url,
      onload: resp => {
        if (resp.status === 200) {
          if (!el.classList.contains(className)) {
            const img = document.createElement('img');
            const data = new Blob([resp.response], { type: 'image/svg+xml' });
            img.src = URL.createObjectURL(data);
            img.onload = () => {
              URL.revokeObjectURL(img.src);
            };
            el.append(img);
            el.classList.add(className);
          }
          resolve();
        }
        reject(`${resp.status}: ${url}`);
      },
      onerror: reject,
    });
  });
}
