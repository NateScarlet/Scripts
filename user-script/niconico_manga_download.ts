// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     NicoNico manga download
// @description save loaded manga as markdown.
// @grant    none
// @include	 https://seiga.nicovideo.jp/watch/*
// @run-at   document-idle
// ==/UserScript==

import canvasToMarkdown from "./utils/canvasToMarkdown";
import downloadFile from "./utils/downloadFile";
import sleep from "./utils/sleep";

const __name__ = "NicoNico manga download";

(async function (): Promise<void> {
  let lines = [];

  const title =
    document.querySelector<HTMLMetaElement>("meta[property='og:title']")
      ?.content ?? document.title;

  const startTime = Date.now();
  const timeout = () => {
    if (Date.now() - startTime < 300e3) {
      return true;
    }
    throw new Error(`${__name__}: timeout`);
  };
  while (timeout()) {
    const pages = document.querySelectorAll<HTMLLIElement>("li.page");
    for (let index = 0; index < pages.length; index += 1) {
      const li = pages.item(index);
      while (timeout()) {
        const canvas = li.querySelector<HTMLCanvasElement>(
          "canvas:not(.balloon)"
        );
        const pageIndex = Number.parseInt(li.dataset.pageIndex, 10) || index;
        if (!canvas) {
          li.scrollIntoView();
          console.log(`${__name__}: waiting page: ${pageIndex}`);
          await sleep(1e3);
          continue;
        }
        lines.push(canvasToMarkdown(canvas, li.id, `p${pageIndex + 1}`));
        break;
      }
    }
    pages.item(0)?.scrollIntoView();

    if (lines.length > 0) {
      break;
    }
    await sleep(1e3);
  }

  // 下载文件
  console.log(`${__name__}: got ${lines.length} page(s)`);
  const file = new Blob(
    [
      `# ${title}\n\n`,
      `${window.location.href}\n\n`,
      lines.join("\n\n") + "\n",
    ],
    { type: "text/markdown" }
  );
  downloadFile(file, `${title}.md`);
})();
