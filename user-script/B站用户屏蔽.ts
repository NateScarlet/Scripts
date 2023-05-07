// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     B站用户屏蔽
// @description 避免看到指定用户上传的视频，在用户个人主页会多出屏蔽按钮。
// @grant    GM.getValue
// @grant    GM.setValue
// @grant    GM.deleteValue
// @include	 https://search.bilibili.com/*
// @include	 https://space.bilibili.com/*
// @include	 https://www.bilibili.com/*
// @run-at   document-idle
// ==/UserScript==

// spell-checker: word bili bilibili upname datetime

import compare from "./utils/compare";
import obtainHTMLElement from "./utils/obtainHTMLElement";
import useGMValue from "./utils/useGMValue";
import usePolling from "./utils/usePolling";
import { render, html } from "lit-html";

export {};

const blockedUsers = useGMValue(
  "blockedUsers@206ceed9-b514-4902-ad70-aa621fed5cd4",
  {} as Record<
    string,
    | {
        name: string;
        blockedAt: number;
      }
    | true
    | undefined
  >
);

async function migrateV1() {
  const key = "blockedUserIDs@7ced1613-89d7-4754-8989-2ad0d7cfa9db";
  const oldValue = await GM.getValue(key);
  if (!oldValue) {
    return;
  }
  const newValue = { ...blockedUsers.value };
  (JSON.parse(String(oldValue)) as string[]).forEach((i) => {
    newValue[i] = true;
  });
  blockedUsers.value = newValue;
  await GM.deleteValue(key);
}

function renderActions(userID: string) {
  const parent = document.querySelector(".h-action");
  if (!parent) {
    return;
  }

  const { el: container, isCreated } = obtainHTMLElement(
    "div",
    "7ced1613-89d7-4754-8989-2ad0d7cfa9db"
  );
  if (isCreated) {
    container.style.display = "inline";
    parent.prepend(container);
  }
  const isBlocked = !!blockedUsers.value[userID];
  const count = Object.keys(blockedUsers.value).length;

  render(
    html`
      <a
        class="h-f-btn"
        target="_blank"
        @click="${(e: Event) => {
          e.stopPropagation();
          const el = e.target as HTMLAnchorElement;
          el.href = blockedUsersURL();
        }}"
      >
        已屏蔽 ${count}
      </a>
      <span
        class="h-f-btn"
        @click="${(e: MouseEvent) => {
          e.stopPropagation();
          const isBlocked = !!blockedUsers.value[userID];
          blockedUsers.value = {
            ...blockedUsers.value,
            [userID]: !isBlocked
              ? {
                  name: document.getElementById("h-name")?.innerText ?? "",
                  blockedAt: Date.now(),
                }
              : undefined,
          };
        }}"
      >
        ${isBlocked ? "取消屏蔽" : "屏蔽"}
      </span>
    `,
    container
  );
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
    const isBlocked = blockedUsers.value[userID];
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
    const isBlocked = blockedUsers.value[userID];
    const container = i;
    if (isBlocked) {
      container.setAttribute("hidden", "");
    } else {
      container.removeAttribute("hidden");
    }
  });
}

function blockedUsersHTML() {
  const userIDs = Object.keys(blockedUsers.value);
  const now = new Date();
  function getData(id: string) {
    const value = blockedUsers.value[id];
    const { blockedAt: rawBlockedAt = 0, name = id } =
      typeof value === "boolean" ? {} : value;
    const blockedAt = new Date(rawBlockedAt);
    return {
      id,
      blockedAt,
      name,
      idAsNumber: Number.parseInt(id),
      isFallback: rawBlockedAt === 0,
    };
  }
  return [
    "<html>",
    "<head>",
    "<title>已屏蔽的用户</title>",
    `<script id="data" lang="application/json">
    ${JSON.stringify(blockedUsers.value, undefined, 2)}
    </script>`,
    "</head>",
    "<body>",
    "<div>",
    `  <h1>已屏蔽 ${userIDs.length} 用户</h1>`,
    `  <time datetime="${now.toISOString()}">${now.toLocaleString()}</time>`,
    "  <ul>",
    ...userIDs
      .map(getData)
      .sort((a, b) => {
        const dateCompare = compare(a.blockedAt, b.blockedAt);
        if (dateCompare !== 0) {
          return -dateCompare;
        }
        return compare(a.idAsNumber, b.idAsNumber);
      })
      .map(({ id, name, blockedAt, isFallback }) => {
        return [
          "<li>",
          `<a href="https://space.bilibili.com/${id}" target="_blank">${name}</a>`,
          ...(!isFallback
            ? [
                `<span>屏蔽于<time datetime="${blockedAt.toISOString()}">${blockedAt.toLocaleString()}</time></span>`,
              ]
            : []),
          "</li>",
        ].join("\n");
      }),
    "  </ul>",
    "</div>",
    "</body>",
    "</html>",
  ].join("\n");
}

function blockedUsersURL() {
  const b = new Blob([blockedUsersHTML()], {
    type: "text/html;charset=UTF-8",
  });
  return URL.createObjectURL(b);
}

async function main() {
  await migrateV1();
  if (window.location.host === "space.bilibili.com") {
    const userID = parseUserURL(window.location.href);
    if (!userID) {
      return;
    }
    usePolling({
      update: () => renderActions(userID),
    });
  } else {
    usePolling({
      update: () => renderVideoCard(),
    });
  }
}

main();
