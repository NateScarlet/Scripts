// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     B站用户屏蔽
// @description 避免看到指定用户上传的视频，在用户个人主页会多出一个屏蔽按钮。
// @version  4
// @grant    GM.getValue
// @grant    GM.setValue
// @include	 https://search.bilibili.com/*
// @include	 https://space.bilibili.com/*
// @include	 https://www.bilibili.com/*
// @run-at   document-idle
// ==/UserScript==

// spell-checker: word bili bilibili upname

import obtainHTMLElement from "./utils/obtainHTMLElement";
import toggleArrayItem from "./utils/toggleArrayItem";
import useGMValue from "./utils/useGMValue";
import usePolling from "./utils/usePolling";

export {};

const blockedUserIDs = useGMValue(
  "blockedUserIDs@7ced1613-89d7-4754-8989-2ad0d7cfa9db",
  [] as string[]
);

function renderBlockButton(userID: string) {
  const isBlocked = blockedUserIDs.value.includes(userID);
  const el = obtainHTMLElement("span", "7ced1613-89d7-4754-8989-2ad0d7cfa9db");
  el.classList.add("h-f-btn");
  el.textContent = isBlocked ? "取消屏蔽" : "屏蔽";
  el.onclick = async () => {
    const arr = blockedUserIDs.value.slice();
    toggleArrayItem(arr, userID);
    blockedUserIDs.value = arr;
    renderBlockButton(userID);
  };

  const parent = document.querySelector(".h-action") || document.body;
  parent.prepend(el);
}

function parseUserURL(rawURL: string | undefined): string | undefined {
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
    const rawURL = i
      .querySelector("a.bili-video-card__info--owner")
      ?.getAttribute("href");
    const userID = parseUserURL(rawURL);
    if (!userID) {
      return;
    }
    const isBlocked = blockedUserIDs.value.includes(userID);
    const container = i.parentElement.classList.contains("video-list-item")
      ? i.parentElement
      : i;
    if (isBlocked) {
      container.setAttribute("hidden", "");
    } else {
      container.removeAttribute("hidden");
    }
  });

  document.querySelectorAll(".video-page-card-small").forEach((i) => {
    const rawURL = i.querySelector(".upname a")?.getAttribute("href");
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
      update: () => renderBlockButton(userID),
    });
  } else {
    usePolling({
      update: () => renderVideoCard(),
    });
  }
}

main();
