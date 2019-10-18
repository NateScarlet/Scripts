// ==UserScript==
// @name     Github anchor enhance
// @description Enhance all github link with badges
// @version  16
// @grant    GM.xmlHttpRequest
// @run-at   document-end
// @include	 *
// ==/UserScript==
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
    constructor({ user, repo }) {
        this.user = user;
        this.repo = repo;
    }
    equals(other) {
        return other.repo === this.repo && other.user === this.user;
    }
}
URLParseResult.EMPTY = new URLParseResult({});
function parseURL(v) {
    const match = v.match(/^https?:\/\/github.com\/([^/]*?)(?:\/([^/]*?))?(?:\.git)?(?:[#?].*)?$/);
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
async function appendBadge(el, className, url) {
    if (el.classList.contains(className)) {
        return;
    }
    return new Promise((resolve, reject) => {
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
                        const container = el.querySelector(selector) || document.createElement("span");
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
async function appendStarsBadge(el) {
    const { repo, user } = parseURL(el.href);
    if (!(user && repo)) {
        return;
    }
    await appendBadge(el, "added-stars-badge", `https://img.shields.io/github/stars/${user}/${repo}.svg?style=social`);
}
async function appendLastCommitBadge(el) {
    const { repo, user } = parseURL(el.href);
    if (!(user && repo)) {
        return;
    }
    await appendBadge(el, "added-last-commit-badge", `https://img.shields.io/github/last-commit/${user}/${repo}.svg`);
}
async function appendFollowersBadge(el) {
    const { user } = parseURL(el.href);
    if (!user) {
        return;
    }
    await appendBadge(el, "added-followers-badge", `https://img.shields.io/github/followers/${user}.svg?style=social`);
}
(async function () {
    document.addEventListener("mouseover", async (e) => {
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
            }
            catch (err) {
                console.error(err);
            }
        }
    }, {});
})();
