// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     刺猬猫章节自动下载
// @description 打开刺猬猫章节页面时自动保存文章到本地, 支持付费章节。
// @grant    none
// @include	 https://www.ciweimao.com/chapter/*
// @run-at   document-idle
// ==/UserScript==

import elementRootText from "./utils/elementRootText";
import imageToMarkdown from "./utils/imageToMarkdown";
import loadImage from "./utils/loadImage";
import sleep from "./utils/sleep";

const __name__ = "刺猬猫章节自动下载";

(async function (): Promise<void> {
  const chapter = document.querySelector("#J_BookCnt .chapter").firstChild
    .textContent;
  let lines = [];

  let startTime = Date.now();

  while (lines.length === 0 && Date.now() - startTime < 60e3) {
    await sleep(1e3);
    // 收费章节
    for (const i of document.querySelectorAll<HTMLElement>("#J_BookImage")) {
      const url: string = i.style["background-image"].match(
        /(?:url\(")?(.+)(?:"\))?/
      )[1];
      const line = imageToMarkdown(await loadImage(url));
      lines.push(line);
    }
    // 免费章节
    for (const i of document.querySelectorAll("#J_BookRead p.chapter")) {
      const line = elementRootText(i);
      lines.push(line);
      for (const img of i.querySelectorAll("img")) {
        await img.decode();
        lines.push(imageToMarkdown(img));
      }
    }
    // 作者说
    for (const i of document.querySelectorAll("p.author_say")) {
      const line = elementRootText(i);
      lines.push(`    ${line}`);
      for (const img of i.querySelectorAll("img")) {
        await img.decode();
        lines.push(imageToMarkdown(img));
      }
    }
    lines = lines.filter((i) => i.length > 0);
  }

  // 下载文件
  console.log(`${__name__}: 获取到 ${lines.length} 行`);
  const file = new Blob([`# ${chapter}\n\n`, lines.join("\n\n") + "\n"], {
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
