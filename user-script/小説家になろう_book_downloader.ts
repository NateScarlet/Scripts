// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     小説家になろう book downloader
// @description Add `download all chapter` button to syosetu.com
// @version  2021.01.15
// @grant    GM.xmlHttpRequest
// @include	 /^https?://ncode\.syosetu\.com/\w+/$/
// @include	 /^https?://novel18\.syosetu\.com/\w+/$/
// @run-at   document-end
// ==/UserScript==

export {};

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

namespace util {
  export function parseHeader(headers: string): Map<string, string[]> {
    const ret: Map<string, string[]> = new Map();
    for (const line of headers.split("\r\n")) {
      if (!line) {
        continue;
      }
      const match = /^(.+?): ?(.+)$/.exec(line);
      if (!match) {
        throw new Error(`malformed header: ${line}`);
      }
      const [_, key, value] = match;
      if (!ret.has(key)) {
        ret.set(key, []);
      }
      ret.get(key).push(value);
    }
    return ret;
  }
  export namespace image {
    export function img2line(img: HTMLImageElement): string {
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0);
      return `![${img.alt}](${canvas.toDataURL()} "${img.title}")`;
    }
    export async function url2line(url: string): Promise<string> {
      return new Promise((resolve, reject): void => {
        const img = new Image();
        img.onload = (): void => {
          resolve(img2line(img));
        };
        img.onerror = reject;
        img.alt = url;
        GM.xmlHttpRequest({
          method: "GET",
          url,
          // https://github.com/greasemonkey/greasemonkey/issues/1834#issuecomment-37084558
          overrideMimeType: "text/plain; charset=x-user-defined",
          onload: ({ responseText, responseHeaders }) => {
            const headers = parseHeader(responseHeaders);
            const data = new Blob(
              [
                Uint8Array.from(
                  responseText.split("").map((i) => i.charCodeAt(0))
                ),
              ],
              { type: headers.get("content-type")?.[0] ?? "image/jpeg" }
            );
            const src = URL.createObjectURL(data);
            const img = new Image();
            img.onload = () => {
              resolve(img2line(img));
              URL.revokeObjectURL(src);
            };
            img.onerror = reject;
            img.alt = url;
            img.src = src;
          },
          onerror: ({ context }) => {
            reject({ context });
          },
        });
      });
    }

    export async function convertOnDemand(line: string): Promise<string> {
      const match = line.match(/^<(.+)\|(.+)>$/);
      if (match) {
        const url = `https://${match[2]}.mitemin.net/userpageimage/viewimagebig/icode/${match[1]}/`;
        try {
          return await url2line(url);
        } catch (err) {
          addMessage(
            [url, JSON.stringify(err)],
            "Image download failed",
            "orange"
          );
          return `![${line}](${url})`;
        }
      }
      return line;
    }
  }
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
  log(`fetch chapter: ${chapter}`);
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
  /** @type {HTMLAnchorElement} */
  const anchor: HTMLAnchorElement = document.querySelector(
    ".novel_writername > a:nth-child(1)"
  );
  return [
    "---",
    `author: ${anchor.innerText}`,
    `author_link: ${anchor.href}`,
    `link: ${document.location.href}`,
    "---",
  ].join("\n");
}
// Text utils

function getLatestPart(url: string): string {
  return url
    .split("/")
    .filter((i) => i)
    .slice(-1)[0];
}

function unescapeHTML(input: string): string {
  const doc = new DOMParser().parseFromString(input, "text/html");
  return doc.documentElement.textContent;
}
function downloadFile(file: Blob): void {
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(file);
  anchor.download = `${getLatestPart(location.pathname)} ${document.title}.md`;
  anchor.style["display"] = "none";
  document.body.append(anchor);
  anchor.click();
  setTimeout(() => {
    document.body.removeChild(anchor);
    URL.revokeObjectURL(anchor.href);
  }, 0);
}
function strip(str: string): string {
  return str.replace(/^\s+|\s+$/g, "");
}

function sleep(duration: number): Promise<void> {
  return new Promise((resolve): void => {
    setTimeout(resolve, duration);
  });
}

async function downloadChapterChunk(
  ncode: string,
  chapters: { chapter: string; title: string }[]
): Promise<string[]> {
  return Promise.all(
    chapters.map((i) =>
      (async function (): Promise<string[]> {
        const ret = await Promise.all(
          (await downloadChapter(ncode, i.chapter))
            .split("\n")
            .map(strip)
            .filter((i) => i.length > 0)
            .map(unescapeHTML)
            .map(util.image.convertOnDemand)
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
  const ncode = getLatestPart(
    document.querySelector<HTMLAnchorElement>(
      "#novel_footer > ul:nth-child(1) > li:nth-child(3) > a:nth-child(1)"
    ).href
  );
  log(`start downloading: ${ncode}`);
  const chapters = [];
  for (const i of document.querySelectorAll<HTMLAnchorElement>(
    "dl.novel_sublist2 > dd:nth-child(1) > a:nth-child(1)"
  )) {
    chapters.push({ chapter: getLatestPart(i.href), title: i.innerText });
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
