// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     刺猬猫章节自动下载
// @description 打开刺猬猫章节页面时自动保存文章到本地, 支持付费章节。
// @version  9
// @grant    none
// @include	 https://www.ciweimao.com/chapter/*
// @run-at   document-idle
// ==/UserScript==

export {};

const __name__ = "刺猬猫章节自动下载";

function image2line(img: HTMLImageElement): string {
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0);
  return `![${img.alt}](${canvas.toDataURL()} "${img.title}")`;
}

function strip(str: string): string {
  return str.replace(/^\s+|\s+$/g, "");
}

function getElementRootText(element: Element): string {
  let ret = "";
  for (const i of element.childNodes) {
    if (i.nodeType === i.TEXT_NODE) {
      ret += i.nodeValue;
    }
  }
  return strip(ret);
}

async function imageUrl2line(url: string): Promise<string> {
  return new Promise((resolve): void => {
    const img = new Image();
    img.onload = (): void => {
      resolve(image2line(img));
    };
    img.src = url;
  });
}

(async function(): Promise<void> {
  const chapter = document.querySelector("#J_BookCnt h3.chapter").firstChild
    .textContent;
  let lines = [];

  // 收费章节
  for (const i of document.querySelectorAll<HTMLElement>("#J_BookImage")) {
    const url: string = i.style["background-image"].match(
      /(?:url\(")?(.+)(?:"\))?/
    )[1];
    const line = await imageUrl2line(url);
    lines.push(line);
  }
  // 免费章节
  for (const i of document.querySelectorAll("#J_BookRead p:not(.author_say)")) {
    const line = getElementRootText(i);
    lines.push(line);
    for (const img of i.querySelectorAll("img")) {
      lines.push(image2line(img));
    }
  }
  // 作者说
  for (const i of document.querySelectorAll("p.author_say")) {
    const line = getElementRootText(i);
    lines.push(`    ${line}`);
    for (const img of i.querySelectorAll("img")) {
      lines.push(image2line(img));
    }
  }

  // 下载文件
  lines = lines.filter(i => i.length > 0);
  console.log(`${__name__}: 获取到 ${lines.length} 行`);
  const file = new Blob([`# ${chapter}\n\n`, lines.join("\n\n")], {
    type: "text/markdown",
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
    URL.revokeObjectURL(anchor.href);
  }, 0);
})();
