// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     小説家になろう book downloader
// @description Add `download all chapter` button to syosetu.com (you need login to download chapters )
// @grant    GM.xmlHttpRequest
// @include	 /^https?://ncode\.syosetu\.com/\w+/$/
// @include	 /^https?://novel18\.syosetu\.com/\w+/$/
// @run-at   document-end
// ==/UserScript==

import downloadFile from "./utils/downloadFile";
import imageToMarkdown from "./utils/imageToMarkdown";
import loadImageCORS from "./utils/loadImageCORS";
import sleep from "./utils/sleep";
import urlLastPart from "./utils/urlLastPart";

const __name__ = "小説家になろう book downloader";
const statusIndicator = document.createElement("span");
let finishedCount = 0;
let totalCount = 0;

function log(...v: unknown[]): void {
  console.log(`${__name__}:`, ...v);
}
const messageNodes: HTMLDivElement[] = [];
function addMessage(text: string[], title: string, color = "red"): void {
  const div = document.createElement("div");
  div.className = `ui ${color} message`;
  statusIndicator.after(div);
  messageNodes.push(div);
  if (title) {
    const header = document.createElement("div");
    header.innerText = title;
    header.className = "header";
    div.appendChild(header);
  }
  const lines = (typeof text === "string" ? [text] : text) || [];
  for (const i of lines) {
    const p = document.createElement("p");
    p.innerText = i;
    div.appendChild(p);
  }
}

async function chapterImageToMarkdown(line: string): Promise<string> {
  const match = line.match(/^<(.+)\|(.+)>$/);
  if (match) {
    const url = `https://${match[2]}.mitemin.net/userpageimage/viewimagebig/icode/${match[1]}/`;
    try {
      return imageToMarkdown(await loadImageCORS(url));
    } catch (err) {
      addMessage([url, JSON.stringify(err)], "Image download failed", "orange");
      return `![${line}](${url})`;
    }
  }
  return line;
}

function updateStatus(): void {
  statusIndicator.innerText = `(${finishedCount}/${totalCount})`;
}
async function downloadChapter(
  ncode: string,
  chapter: string
): Promise<string> {
  const url =
    `https://${location.host}/txtdownload/dlstart/ncode` +
    `/${ncode}/?no=${chapter}&hankaku=0&code=utf-8&kaigyo=lf`;
  log(`fetch chapter: ${chapter}: ${url}`);
  const resp = await fetch(url);
  if (resp.status !== 200) {
    addMessage(
      [`${resp.status} ${resp.statusText}`, url],
      "Fetch chapter failed"
    );
    throw new Error(
      `Fetch chapter failed: ${resp.status} ${resp.statusText} : ${url}`
    );
  }
  return await resp.text();
}

function clearMessage(): void {
  while (messageNodes.length) {
    messageNodes.pop().remove();
  }
}
function getMetaData(): string {
  const data: Record<string, string> = {
    link: document.location.href,
  };
  const authorContainer = document.querySelector(".novel_writername");
  const authorAnchor = document.querySelector(
    ".novel_writername > a:nth-child(1)"
  );
  if (authorAnchor instanceof HTMLAnchorElement) {
    data["author"] = authorAnchor.innerText;
    data["author_link"] = authorAnchor.href;
  } else if (authorContainer instanceof HTMLDivElement) {
    data["author"] = authorContainer.innerText.replace(/^作者：/, "");
  }

  return [
    "---",
    ...Object.entries(data).map(([k, v]) => `${k}: ${v}`),
    "---",
  ].join("\n");
}

async function downloadChapterChunk(
  ncode: string,
  chapters: { chapter: string; title: string }[]
): Promise<string[]> {
  return Promise.all(
    chapters.map((i) =>
      (async function (): Promise<string[]> {
        const ret = await Promise.all(
          (
            await downloadChapter(ncode, i.chapter)
          )
            .split("\n")
            .map((i) => i.trim())
            .filter((i) => i.length > 0)
            .map(chapterImageToMarkdown)
        );
        ret.splice(0, 0, `# ${i.title}`);
        finishedCount += 1;
        updateStatus();
        return ret;
      })()
    )
  ).then((i) => {
    /** @type {string[]} */
    const ret: string[] = [];
    i.map((j) => {
      ret.push(...j);
    });
    return ret;
  });
}

async function main(button: HTMLButtonElement): Promise<void> {
  clearMessage();
  const ncode = urlLastPart(
    document.querySelector<HTMLAnchorElement>(
      "#novel_footer > ul:nth-child(1) > li:nth-child(3) > a:nth-child(1)"
    ).href
  );
  log(`start downloading: ${ncode}`);
  const chapters = [];
  for (const i of document.querySelectorAll<HTMLAnchorElement>(
    "dl.novel_sublist2 > dd:nth-child(1) > a:nth-child(1)"
  )) {
    chapters.push({ chapter: urlLastPart(i.href), title: i.innerText });
  }

  finishedCount = 0;
  totalCount = chapters.length;
  updateStatus();
  const lines = [];
  const chunkSize = 10;
  for (let i = 0; i < chapters.length; i += chunkSize) {
    lines.push(
      ...(await downloadChapterChunk(ncode, chapters.slice(i, i + chunkSize)))
    );
    // Avoid rate limiter
    await sleep(5000);
  }
  log(`got ${lines.length} lines`);

  function download(): void {
    downloadFile(
      new Blob([getMetaData(), "\n\n", lines.join("\n\n")], {
        type: "text/markdown",
      })
    );
  }
  button.onclick = download;
  download();
}

(async function (): Promise<void> {
  const button = document.createElement("button");
  button.innerText = "Download all chapters";
  button.className = "button";
  button.onclick = async (): Promise<void> => {
    try {
      button.disabled = true;
      button.style.opacity = "50%";
      await main(button);
    } catch (err) {
      console.error(err);
    } finally {
      button.disabled = false;
      button.style.opacity = "";
    }
  };
  document.querySelector("#novel_ex").after(button, statusIndicator);
  log("activated");
})();
