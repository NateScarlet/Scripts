// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     SF轻小说章节自动下载
// @description 打开SF轻小说章节页面时自动保存文章到本地, 支持付费章节。
// @grant    none
// @include	 http://book.sfacg.com/Novel/*/*/*/
// @include	 http://book.sfacg.com/vip/c/*/
// @include	 https://book.sfacg.com/Novel/*/*/*/
// @include	 https://book.sfacg.com/vip/c/*/
// @run-at   document-idle
// ==/UserScript==

import downloadFile from "./utils/downloadFile";
import elementRootText from "./utils/elementRootText";
import imageToMarkdown from "./utils/imageToMarkdown";

const __name__ = "SF轻小说章节自动下载";

(async function (): Promise<void> {
  const chapter = document.querySelector("#article .article-title").textContent;
  let lines = [
    `# ${chapter}`,
    `[原始页面](${location.href})`,
    ...document
      .querySelector("#article .article-desc")
      .textContent.split(/\n */)
      .filter((i) => i),
    `---`,
  ];
  const keywords = document
    .querySelector<HTMLMetaElement>("meta[name='keywords']")
    .content.split(",")
    .filter((i) => !["小说下载", "TXT"].includes(i))
    .filter((i, index, keywords) => index === 0 || !i.startsWith(keywords[0]));

  // 收费章节
  for (const i of document.querySelectorAll<HTMLImageElement>("img#vipImage")) {
    console.log(`${__name__}: 等待图片加载`);
    await i.decode();
    console.log(`${__name__}: 图片加载完毕`);
    const line = imageToMarkdown(i, { background: "white" });
    lines.push(line);
  }
  // 免费章节
  for (const i of document.querySelectorAll("#ChapterBody p")) {
    const line = elementRootText(i);
    lines.push(line);
    for (const img of i.querySelectorAll("img")) {
      lines.push(imageToMarkdown(img));
    }
  }

  // 下载文件
  lines = lines.filter((i) => i.length > 0);
  console.log(`${__name__}: 获取到 ${lines.length} 行`);

  const file = new Blob([lines.join("\n\n"), "\n"], {
    type: "text/markdown",
  });
  downloadFile(file, `${keywords.join(" ")}.md`);
})();
