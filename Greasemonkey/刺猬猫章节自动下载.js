// ==UserScript==
// @name     刺猬猫章节自动下载
// @version  8
// @grant    none
// @include	 https://www.ciweimao.com/chapter/*
// @run-at   document-idle
// ==/UserScript==

"use strict";

const __name__ = "刺猬猫章节自动下载";

/** @param {HTMLImageElement} img  */
function image2line(img) {
const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0);
  return `![${img.alt}](${canvas.toDataURL()} "${img.title}")`;
}

/** @param {Element} element */
function getElementRootText(element) {
  let ret = "";
  for (const i of element.childNodes) {
    if (i.nodeType === i.TEXT_NODE) {
      ret += i.nodeValue;
    }
  }
  return strip(ret);
}

/** @param {string} url  */
async function imageUrl2line(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      resolve(image2line(img));
    };
    img.src = url;
  });
}

/** @param {string} str
 * @return {string} str
 */
function strip(str) {
  return str.replace(/^\s+|\s+$/g, "");
}

(async function() {
  const chapter = document.querySelector("#J_BookCnt h3.chapter").firstChild
    .textContent;
  let lines = [];

  // 收费章节
  for (const i of document.querySelectorAll("#J_BookImage")) {
    /** @type {string} */
    const url = i.style["background-image"].match(/(?:url\(")?(.+)(?:"\))?/)[1];
    const line = await imageUrl2line(url);
    lines.push(line);
  }
  // 免费章节
  for (const i of document.querySelectorAll("#J_BookRead p:not(.author_say)")) {
    let line = getElementRootText(i);
    lines.push(line);
    for (const img of i.querySelectorAll("img")) {
      lines.push(image2line(img));
    }
  }
  // 作者说
  for (const i of document.querySelectorAll("p.author_say")) {
    let line = getElementRootText(i);
    lines.push(`    ${line}`);
    for (const img of i.querySelectorAll("img")) {
      lines.push(image2line(img));
    }
  }

  // 下载文件
  lines = lines.filter(i => i.length > 0);
  console.log(`${__name__}: 获取到 ${lines.length} 行`);
  const file = new Blob([`# ${chapter}\n\n`, lines.join("\n\n")], {
    type: "text/markdown"
  });
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(file);
  anchor.download = `${location.pathname.split("/").slice(-1)[0]} ${
    document.title
  }.md`;
  anchor.style["display"] = "none";
  document.body.append(anchor);
  anchor.click();
  setTimeout(() => {
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, 0);
})();
