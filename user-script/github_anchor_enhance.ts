// ==UserScript==
// @name     Github anchor enhance
// @version  15
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

class URLParseResult {
  static EMPTY = new URLParseResult({});

  public readonly user?: string;
  public readonly repo?: string;
  constructor({ user, repo }: { user?: string; repo?: string }) {
    this.user = user;
    this.repo = repo;
  }
  public equals(other: URLParseResult): boolean {
    return other.repo === this.repo && other.user === this.user;
  }
}

function parseURL(v: string): URLParseResult {
  const match = v.match(
    /^https?:\/\/github.com\/([^/]*?)(?:\/([^/]*?))?(?:\.git)?(?:[#?].*)?$/
  );
  if (!match) {
    return URLParseResult.EMPTY;
  }
  if (reservedUsername.includes(match[1])) {
    return URLParseResult.EMPTY;
  }
  return new URLParseResult({
    user: match[1],
    repo: match[2],
  });
}

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
  const { repo, user } = parseURL(el.href);

  if (!(user && repo)) {
    return;
  }
  await appendBadge(
    el,
    "added-stars-badge",
    `https://img.shields.io/github/stars/${user}/${repo}.svg?style=social`
  );
}

async function appendLastCommitBadge(el: HTMLAnchorElement): Promise<void> {
  const { repo, user } = parseURL(el.href);

  if (!(user && repo)) {
    return;
  }

  await appendBadge(
    el,
    "added-last-commit-badge",
    `https://img.shields.io/github/last-commit/${user}/${repo}.svg`
  );
}

async function appendFollowersBadge(el: HTMLAnchorElement): Promise<void> {
  const { user } = parseURL(el.href);
  if (!user) {
    return;
  }
  await appendBadge(
    el,
    "added-followers-badge",
    `https://img.shields.io/github/followers/${user}.svg?style=social`
  );
}

(async function(): Promise<void> {
  document.addEventListener(
    "mouseover",
    async e => {
      if (e.target instanceof HTMLAnchorElement) {
        const el = e.target;

        if (parseURL(location.href).equals(parseURL(el.href))) {
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
