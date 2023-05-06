// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     B站用户屏蔽
// @description 避免看到指定用户上传的视频，在用户个人主页会多出一个屏蔽按钮。
// @grant    GM.getValue
// @grant    GM.setValue
// @include	 https://search.bilibili.com/*
// @include	 https://space.bilibili.com/*
// @include	 https://www.bilibili.com/*
// @run-at   document-idle
// @version  3+753a485d
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

  // utils/obtainHTMLElement.ts
  function obtainHTMLElement(tag, id) {
    var _a;
    const el = (_a = document.getElementById(id)) != null ? _a : document.createElement(tag);
    el.id = id;
    return el;
  }

  // utils/toggleArrayItem.ts
  function toggleArrayItem(arr, item, {
    force,
    prepend = false,
    equal = (a, b) => a === b
  } = {}) {
    let index = arr.findIndex((i) => equal(item, i));
    const current = index >= 0;
    const wanted = force != null ? force : !current;
    if (current === wanted) {
      return;
    }
    if (wanted) {
      arr.splice(prepend ? 0 : -1, 0, item);
    } else {
      while (index >= 0) {
        arr.splice(index, 1);
        index = arr.findIndex((i) => equal(item, i));
      }
    }
  }

  // utils/usePolling.ts
  function usePolling({
    update,
    scheduleNext = requestAnimationFrame
  }) {
    let isCancelled = false;
    function run() {
      return __async(this, null, function* () {
        if (isCancelled) {
          return;
        }
        yield update();
        scheduleNext(run);
      });
    }
    function dispose() {
      isCancelled = true;
    }
    run();
    return {
      dispose
    };
  }

  // utils/useGMValue.ts
  function useGMValue(key, defaultValue) {
    const state = {
      value: defaultValue,
      loadingCount: 0
    };
    function read() {
      return __async(this, null, function* () {
        if (state.loadingCount > 0) {
          return;
        }
        state.loadingCount += 1;
        try {
          const value = yield GM.getValue(key);
          if (value != null) {
            try {
              state.value = JSON.parse(String(value));
            } catch (e) {
              state.value = defaultValue;
            }
          }
        } finally {
          state.loadingCount -= 1;
        }
      });
    }
    function write() {
      return __async(this, null, function* () {
        state.loadingCount += 1;
        try {
          if (state.value == null) {
            yield GM.deleteValue(key);
          } else {
            yield GM.setValue(key, JSON.stringify(state.value));
          }
        } finally {
          state.loadingCount -= 1;
        }
      });
    }
    read();
    const polling = usePolling({
      update: () => read(),
      scheduleNext: (update) => setTimeout(update, 500)
    });
    return {
      get value() {
        return state.value;
      },
      set value(v) {
        state.value = v;
        write();
      },
      get isLoading() {
        return state.loadingCount > 0;
      },
      dispose: polling.dispose
    };
  }

  // B站用户屏蔽.ts
  var blockedUserIDs = useGMValue("blockedUserIDs@7ced1613-89d7-4754-8989-2ad0d7cfa9db", []);
  function renderBlockButton(userID) {
    const isBlocked = blockedUserIDs.value.includes(userID);
    const el = obtainHTMLElement("button", "7ced1613-89d7-4754-8989-2ad0d7cfa9db");
    el.setAttribute("type", "button");
    el.classList.add("h-f-btn");
    el.style.width = "auto";
    el.style.minWidth = "76px";
    el.textContent = isBlocked ? "取消屏蔽" : "屏蔽";
    el.onclick = () => __async(this, null, function* () {
      const arr = blockedUserIDs.value.slice();
      toggleArrayItem(arr, userID);
      blockedUserIDs.value = arr;
      renderBlockButton(userID);
    });
    const parent = document.querySelector(".h-action") || document.body;
    parent.prepend(el);
  }
  function parseUserURL(rawURL) {
    if (!rawURL) {
      return;
    }
    const match = /^\/(\d+)\/?$/.exec(new URL(rawURL, window.location.href).pathname);
    if (!match) {
      return;
    }
    return match[1];
  }
  function renderVideoCard() {
    document.querySelectorAll(".bili-video-card").forEach((i) => {
      var _a;
      const rawURL = (_a = i.querySelector("a.bili-video-card__info--owner")) == null ? void 0 : _a.getAttribute("href");
      const userID = parseUserURL(rawURL);
      if (!userID) {
        return;
      }
      const isBlocked = blockedUserIDs.value.includes(userID);
      const container = i.parentElement.classList.contains("video-list-item") ? i.parentElement : i;
      if (isBlocked) {
        container.setAttribute("hidden", "");
      } else {
        container.removeAttribute("hidden");
      }
    });
    document.querySelectorAll(".video-page-card-small").forEach((i) => {
      var _a;
      const rawURL = (_a = i.querySelector(".upname a")) == null ? void 0 : _a.getAttribute("href");
      if (!rawURL) {
        return;
      }
      const userID = parseUserURL(rawURL);
      if (!userID) {
        return;
      }
      const isBlocked = blockedUserIDs.value.includes(userID);
      const container = i;
      if (isBlocked) {
        container.setAttribute("hidden", "");
      } else {
        container.removeAttribute("hidden");
      }
    });
  }
  function main() {
    if (window.location.host === "space.bilibili.com") {
      const userID = parseUserURL(window.location.href);
      if (!userID) {
        return;
      }
      usePolling({
        update: () => renderBlockButton(userID)
      });
    } else {
      usePolling({
        update: () => renderVideoCard()
      });
    }
  }
  main();
})();
