// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     NicoNico manga download
// @description save loaded manga as markdown.
// @grant    none
// @include	 https://seiga.nicovideo.jp/watch/*
// @run-at   document-idle
// ==/UserScript==

import downloadFile from "./utils/downloadFile";
import sleep from "./utils/sleep";
import mangaReaderHTML from "./assets/manga_reader.html";
import { template } from "lodash-es";
import style from "./assets/style.css";

const __name__ = "NicoNico manga download";

(async function (): Promise<void> {
  const images = [];

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
      images.push({
        src: canvas.toDataURL(),
        alt: li.id,
        title: `p${pageIndex + 1}`,
      });
      break;
    }
  }
  pages.item(0)?.scrollIntoView();

  // render
  const data = template(mangaReaderHTML)({
    title,
    window,
    images,
    style,
  });

  // download
  console.log(`${__name__}: got ${images.length} page(s)`);
  const file = new Blob([data], { type: "text/html" });
  downloadFile(file, `${title}.html`);
})();
