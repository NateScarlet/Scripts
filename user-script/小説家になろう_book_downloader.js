// ==UserScript==
// @name     小説家になろう book downloader
// @version  4
// @grant    none
// @include	 /^https?://ncode\.syosetu\.com/\w+/$/
// @run-at   document-idle
// ==/UserScript==

const __name__ = "小説家になろう book downloader";
const statusIndicator = document.createElement("span");
let finishedCount = 0;
let totalCount = 0;
function updateStatus() {
  statusIndicator.innerText = `(${finishedCount}/${totalCount})`;
}
async function downloadChapter(ncode, chapter) {
  const url =
    `https://ncode.syosetu.com/txtdownload/dlstart/ncode` +
    `/${ncode}/?no=${chapter}&hankaku=0&code=utf-8&kaigyo=lf`;
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

/** @type {HTMLDivElement[]} */
const messageNodes = [];
function addMessage(text, title, color = "red") {
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
function clearMessage() {
  while (messageNodes.length) {
    messageNodes.pop().remove();
  }
}
function getMetaData() {
  /** @type {HTMLAnchorElement} */
  const anchor = document.querySelector(".novel_writername > a:nth-child(1)");
  return [
    "---",
    `author: ${anchor.innerText}`,
    `author_link: ${anchor.href}`,
    `link: ${document.location.href}`,
    "---"
  ].join("\n");
}

async function downloadChapterChunk(ncode, chapters) {
  return Promise.all(
    chapters.map(i =>
      (async function() {
        const ret = await Promise.all(
          (await downloadChapter(ncode, i.chapter))
            .split("\n")
            .map(strip)
            .filter(i => i.length > 0)
            .map(unescapeHTML)
            .map(convertImage)
        );
        ret.splice(0, 0, `# ${i.title}`);
        finishedCount += 1;
        updateStatus();
        return ret;
      })()
    )
  ).then(i => {
    /** @type {string[]} */
    const ret = [];
    i.map(j => {
      ret.push(...j);
    });
    return ret;
  });
}
/** @param {HTMLButtonElement} button */
async function main(button) {
  clearMessage();
  const ncode = getLatestPart(
    document.querySelector(
      "#novel_footer > ul:nth-child(1) > li:nth-child(3) > a:nth-child(1)"
    ).href
  );
  log(`"start downloading: ${ncode}`);
  const chapters = [];
  for (const i of document.querySelectorAll(
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

  function download() {
    downloadFile(
      new Blob([getMetaData(), "\n\n", lines.join("\n\n")], {
        type: "text/markdown"
      })
    );
  }
  button.onclick = download;
  download()
}

function downloadFile(file) {
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(file);
  anchor.download = `${getLatestPart(location.pathname)} ${document.title}.md`;
  anchor.style["display"] = "none";
  document.body.append(anchor);
  anchor.click();
  setTimeout(() => {
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, 0);
}
function injectStyleSheet(url) {
  const link = document.createElement("link");
  link.href = url;
  link.rel = "stylesheet";
  document.head.append(link);
}
(async function() {
  injectStyleSheet(
    "https://cdn.bootcss.com/semantic-ui/2.4.1/components/button.min.css"
  );
  injectStyleSheet(
    "https://cdn.bootcss.com/semantic-ui/2.4.1/components/message.min.css"
  );
  const button = document.createElement("button");
  button.innerText = "Download all chapter";
  button.className = "ui button";
  button.onclick = async () => {
    try {
      button.disabled = true;
      button.classList.add("loading");
      await main(button);
    } catch (err) {
      console.err(err);
    } finally {
      button.disabled = false;
      button.classList.remove("loading");
    }
  };
  document.querySelector("#novel_ex").after(button, statusIndicator);
  log("activated");
})();

function sleep(duration) {
  return new Promise(resolve => setTimeout(resolve, duration));
}

// Image utils

/** @param {string} url  */
async function imageUrl2line(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      resolve(image2line(img));
    };
    img.onerror = reject;
    img.src = url;
    img.alt = url;
  });
}
/** @param {HTMLImageElement} img  */
function image2line(img) {
  const canvas = document.createElement("canvas");
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0);
  return `![${img.alt}](${canvas.toDataURL()} "${img.title}")`;
}

/**
 * @param {string} line
 * @return {string}
 */
async function convertImage(line) {
  const match = line.match(/^<(.+)\|(.+)>$/);
  if (match) {
    const url = `https://${
      match[2]
    }.mitemin.net/userpageimage/viewimagebig/icode/${match[1]}/`;
    try {
      return await imageUrl2line(url);
    } catch (err) {
      addMessage([url, JSON.stringify(err)], "Image download failed", 'orange')
      return `![${line}](${url})`;
    }
  }
  return line;
}

// Text utils

/** @param {string} url */
function getLatestPart(url) {
  return url
    .split("/")
    .filter(i => i)
    .slice(-1)[0];
}
/** @param {string} str
 * @return {string} str
 */
function strip(str) {
  return str.replace(/^\s+|\s+$/g, "");
}

function log() {
  console.log(`${__name__}:`, ...arguments);
}
function unescapeHTML(input) {
  const doc = new DOMParser().parseFromString(input, "text/html");
  return doc.documentElement.textContent;
}
