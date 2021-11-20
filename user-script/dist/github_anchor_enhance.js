// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     Github anchor enhance
// @description Enhance all github link with badges
// @grant    GM.xmlHttpRequest
// @run-at   document-end
// @include	 *
// @version  18+67f89173
// ==/UserScript==

(() => {
  var __async = (__this, __arguments, generator) => {
    return new Promise((resolve, reject) => {
      var fulfilled = (value) => {
        try {
          step(generator.next(value));
        } catch (e) {
          reject(e);
        }
      };
      var rejected = (value) => {
        try {
          step(generator.throw(value));
        } catch (e) {
          reject(e);
        }
      };
      var step = (x) => x.done ? resolve(x.value) : Promise.resolve(x.value).then(fulfilled, rejected);
      step((generator = generator.apply(__this, __arguments)).next());
    });
  };

  // github_anchor_enhance.ts
  var reservedUsername = [
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
    "trending",
    "collections",
    "events"
  ];
  var allBadgeClasses = [
    "added-stars-badge",
    "added-last-commit-badge",
    "added-followers-badge"
  ];
  var _URLParseResult = class {
    constructor({ user, repo }) {
      this.user = user;
      this.repo = repo;
    }
    equals(other) {
      return other.repo === this.repo && other.user === this.user;
    }
  };
  var URLParseResult = _URLParseResult;
  URLParseResult.EMPTY = new _URLParseResult({});
  function parseURL(v) {
    const match = v.match(/^https?:\/\/github.com\/([^/]*?)(?:\/([^/]*?))?(?:\.git)?(?:[#?].*)?(?:$|\/)/);
    if (!match) {
      return URLParseResult.EMPTY;
    }
    if (reservedUsername.includes(match[1])) {
      return URLParseResult.EMPTY;
    }
    return new URLParseResult({
      user: match[1],
      repo: match[2]
    });
  }
  function appendBadge(el, className, url) {
    return __async(this, null, function* () {
      if (el.classList.contains(className)) {
        return;
      }
      return new Promise((resolve, reject) => {
        GM.xmlHttpRequest({
          method: "GET",
          url,
          onload: (resp) => {
            if (resp.status === 200) {
              if (!el.classList.contains(className)) {
                const img = document.createElement("img");
                img.src = `data:image/svg+xml;base64,${btoa(resp.response)}`;
                const containerClassNames = [
                  "natescarlet-gmail-com",
                  "badge-container"
                ];
                const selector = containerClassNames.map((i) => "." + i).join("");
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
          onerror: reject
        });
      });
    });
  }
  function appendStarsBadge(el) {
    return __async(this, null, function* () {
      const { repo, user } = parseURL(el.href);
      if (!(user && repo)) {
        return;
      }
      yield appendBadge(el, "added-stars-badge", `https://img.shields.io/github/stars/${user}/${repo}.svg?style=social`);
    });
  }
  function appendLastCommitBadge(el) {
    return __async(this, null, function* () {
      const { repo, user } = parseURL(el.href);
      if (!(user && repo)) {
        return;
      }
      yield appendBadge(el, "added-last-commit-badge", `https://img.shields.io/github/last-commit/${user}/${repo}.svg`);
    });
  }
  function appendFollowersBadge(el) {
    return __async(this, null, function* () {
      const { user } = parseURL(el.href);
      if (!user) {
        return;
      }
      yield appendBadge(el, "added-followers-badge", `https://img.shields.io/github/followers/${user}.svg?style=social`);
    });
  }
  (function() {
    return __async(this, null, function* () {
      document.addEventListener("mouseover", (e) => __async(this, null, function* () {
        if (e.target instanceof HTMLAnchorElement) {
          const el = e.target;
          if (parseURL(location.href).equals(parseURL(el.href))) {
            return;
          }
          try {
            yield Promise.all([
              appendStarsBadge(el),
              appendLastCommitBadge(el),
              appendFollowersBadge(el)
            ]);
          } catch (err) {
            console.error(err);
          }
        }
      }), {});
    });
  })();
})();
