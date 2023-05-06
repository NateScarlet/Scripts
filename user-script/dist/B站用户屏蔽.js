// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     B站用户屏蔽
// @description 避免看到指定用户上传的视频，在用户个人主页会多出一个屏蔽按钮。
// @grant    GM.getValue
// @grant    GM.setValue
// @grant    GM.deleteValue
// @include	 https://search.bilibili.com/*
// @include	 https://space.bilibili.com/*
// @include	 https://www.bilibili.com/*
// @run-at   document-idle
// @version   2023.05.07+beab61e9
// ==/UserScript==

(() => {
  var __defProp = Object.defineProperty;
  var __defProps = Object.defineProperties;
  var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
  var __getOwnPropSymbols = Object.getOwnPropertySymbols;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __propIsEnum = Object.prototype.propertyIsEnumerable;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __spreadValues = (a, b) => {
    for (var prop in b || (b = {}))
      if (__hasOwnProp.call(b, prop))
        __defNormalProp(a, prop, b[prop]);
    if (__getOwnPropSymbols)
      for (var prop of __getOwnPropSymbols(b)) {
        if (__propIsEnum.call(b, prop))
          __defNormalProp(a, prop, b[prop]);
      }
    return a;
  };
  var __spreadProps = (a, b) => __defProps(a, __getOwnPropDescs(b));
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
  var blockedUsers = useGMValue("blockedUsers@206ceed9-b514-4902-ad70-aa621fed5cd4", {});
  function migrateV1() {
    return __async(this, null, function* () {
      const key = "blockedUserIDs@7ced1613-89d7-4754-8989-2ad0d7cfa9db";
      const oldValue = yield GM.getValue(key);
      if (!oldValue) {
        return;
      }
      const newValue = __spreadValues({}, blockedUsers.value);
      JSON.parse(String(oldValue)).forEach((i) => {
        newValue[i] = true;
      });
      blockedUsers.value = newValue;
      yield GM.deleteValue(key);
    });
  }
  function renderBlockButton(userID) {
    const isBlocked = blockedUsers.value[userID];
    const el = obtainHTMLElement("span", "7ced1613-89d7-4754-8989-2ad0d7cfa9db");
    el.classList.add("h-f-btn");
    el.textContent = isBlocked ? "取消屏蔽" : "屏蔽";
    el.onclick = () => __async(this, null, function* () {
      blockedUsers.value = __spreadProps(__spreadValues({}, blockedUsers.value), {
        [userID]: !isBlocked || void 0
      });
      renderBlockButton(userID);
    });
    const parent = document.querySelector(".h-action") || document.body;
    parent.prepend(el);
  }
  function parseUserURL(rawURL) {
    if (!rawURL) {
      return;
    }
    const url = new URL(rawURL, window.location.href);
    if (url.host !== "space.bilibili.com") {
      return;
    }
    const match = /^\/(\d+)\/?/.exec(url.pathname);
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
      const isBlocked = blockedUsers.value[userID];
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
      const isBlocked = blockedUsers.value[userID];
      const container = i;
      if (isBlocked) {
        container.setAttribute("hidden", "");
      } else {
        container.removeAttribute("hidden");
      }
    });
  }
  function main() {
    return __async(this, null, function* () {
      yield migrateV1();
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
    });
  }
  main();
})();
