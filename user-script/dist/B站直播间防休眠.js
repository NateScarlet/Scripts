"use strict";
// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     B站直播间防休眠
// @description 防止B站直播间自动停止播放
// @version  4
// @grant    none
// @include	 https://live.bilibili.com/*
// @include	 https://www.bilibili.com/blackboard/live/*
// @run-at   document-idle
// ==/UserScript==
(() => {
    setInterval(() => {
        setTimeout(() => {
            document.body.dispatchEvent(new MouseEvent("mousemove", { bubbles: true }));
        }, Math.random() * 2e3);
    }, 10e3);
    window.addEventListener("visibilitychange", (e) => {
        e.stopPropagation();
    }, { capture: true });
})();
