// ==UserScript==
// @name     Github anchor enhance
// @version  13
// @grant    GM.xmlHttpRequest
// @run-at   document-idle
// @include	 *
// ==/UserScript==

export {};

const reservedUsername = [
  "topics",
  "search",
  "ghost",
  "pulls",
  "issues",
  "marketplace",
  "explore",
  "discover",
  "notifications",
  "new",
  "organizations",
  "settings",
  "site",
  "about",
  "contact",
  "pricing",
  "apps",
  "features",
  "password_reset",
];

const allBadgeClasses = [
  "added-stars-badge",
  "added-last-commit-badge",
  "added-followers-badge",
];

async function appendBadge(
  el: HTMLElement,
  className: string,
  url: string
): Promise<void> {
  if (el.classList.contains(className)) {
    return;
  }
  return new Promise((resolve, reject): void => {
    GM.xmlHttpRequest({
      method: "GET",
      url: url,
      onload: resp => {
        if (resp.status === 200) {
          if (!el.classList.contains(className)) {
            const img = document.createElement("img");
            img.src = `data:image/svg+xml;base64,${btoa(resp.response)}`;
            const containerClassNames = [
              "natescarlet-gmail-com",
              "badge-container",
            ];
            const selector = containerClassNames.map(i => "." + i).join("");
            /** @type {HTMLElement} */
            const container: HTMLElement =
              el.querySelector(selector) || document.createElement("span");
            el.appendChild(container);
            container.classList.add(...containerClassNames);
            container.append(img);

            img.style.order = allBadgeClasses.indexOf(className).toString();
            container.style.display = "inline-flex";
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

async function appendStarsBadge(el: HTMLAnchorElement): Promise<void> {
  const match =
    el.href && el.href.match(/https:\/\/github.com\/([^/]+)\/([^/?]+)$/);

  if (match) {
    const [, user, repository] = match;
    if (reservedUsername.includes(user)) {
      return;
    }
    await appendBadge(
      el,
      "added-stars-badge",
      `https://img.shields.io/github/stars/${user}/${repository}.svg?style=social`
    );
  }
}

async function appendLastCommitBadge(el: HTMLAnchorElement): Promise<void> {
  const match =
    el.href && el.href.match(/https:\/\/github.com\/([^/]+)\/([^/?]+)$/);

  if (match) {
    const [, user, repository] = match;
    if (reservedUsername.includes(user)) {
      return;
    }
    await appendBadge(
      el,
      "added-last-commit-badge",
      `https://img.shields.io/github/last-commit/${user}/${repository}.svg`
    );
  }
}

async function appendFollowersBadge(el: HTMLAnchorElement): Promise<void> {
  const match = el.href && el.href.match(/https:\/\/github.com\/([^/?]+)$/);

  if (match) {
    const [, user] = match;
    if (reservedUsername.includes(user)) {
      return;
    }
    await appendBadge(
      el,
      "added-followers-badge",
      `https://img.shields.io/github/followers/${user}.svg?style=social`
    );
  }
}

(async function(): Promise<void> {
  document.addEventListener(
    "mouseover",
    async e => {
      if (e.target instanceof HTMLAnchorElement) {
        const el = e.target;
        const u = new URL(el.href);
        if (
          location.hostname === u.hostname &&
          location.pathname === u.pathname
        ) {
          // Skip self link
          return;
        }
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
