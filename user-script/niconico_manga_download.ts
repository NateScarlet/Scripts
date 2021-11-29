// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     NicoNico manga download
// @description save loaded manga as html.
// @grant    none
// @include	 https://seiga.nicovideo.jp/watch/*
// @run-at   document-idle
// ==/UserScript==

import downloadFile from "./utils/downloadFile";
import sleep from "./utils/sleep";
import mangaReaderHTML from "./assets/manga_reader.html";
import mustache from "mustache";
import style from "./assets/style.css";
import imageToCanvas from "./utils/imageToCanvas";

const __name__ = "NicoNico manga download";

(async function (): Promise<void> {
  const images = [];

  const title =
    document.querySelector<HTMLMetaElement>("meta[property='og:title']")
      ?.content ?? document.title;

  const startTime = Date.now();
  const loopNext = () => {
    if (Date.now() - startTime < 300e3) {
      return true;
    }
    throw new Error(`${__name__}: timeout`);
  };
  const pages = document.querySelectorAll<HTMLLIElement>("li.page");
  for (let index = 0; index < pages.length; index += 1) {
    const li = pages.item(index);
    while (loopNext()) {
      const pageIndex = Number.parseInt(li.dataset.pageIndex, 10) || index;
      let canvas = li.querySelector<HTMLCanvasElement>("canvas:not(.balloon)");
      const image = li.querySelector<HTMLImageElement>("img[data-image-id]");
      if (image) {
        canvas ??= imageToCanvas(image);
      }
      if (!canvas || canvas.width === 1) {
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
  const data = mustache.render(mangaReaderHTML, {
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
