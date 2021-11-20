// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     小説家になろう book downloader
// @description Add `download all chapter` button to syosetu.com (you need login to download chapters )
// @grant    GM.xmlHttpRequest
// @include	 /^https?://ncode\.syosetu\.com/\w+/$/
// @include	 /^https?://novel18\.syosetu\.com/\w+/$/
// @run-at   document-end
// @version   2021.11.20+9cec66da
// ==/UserScript==

(() => {
  var __async = (__this, __arguments, generator) => {
    return new Promise((resolve, reject) => {
      var fulfilled = (value) => {
        try {
          step(generator.next(value));
        } catch (e) {
          reject(e);
        }
      };
      var rejected = (value) => {
        try {
          step(generator.throw(value));
        } catch (e) {
          reject(e);
        }
      };
      var step = (x) => x.done ? resolve(x.value) : Promise.resolve(x.value).then(fulfilled, rejected);
      step((generator = generator.apply(__this, __arguments)).next());
    });
  };

  // 小説家になろう_book_downloader.ts
  var __name__ = "小説家になろう book downloader";
  var statusIndicator = document.createElement("span");
  var finishedCount = 0;
  var totalCount = 0;
  function log(...v) {
    console.log(`${__name__}:`, ...v);
  }
  var messageNodes = [];
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
  var util;
  (function(util2) {
    function parseHeader(headers) {
      const ret = new Map();
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
    util2.parseHeader = parseHeader;
    let image;
    (function(image2) {
      function img2line(img) {
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);
        return `![${img.alt}](${canvas.toDataURL()} "${img.title}")`;
      }
      image2.img2line = img2line;
      function url2line(url) {
        return __async(this, null, function* () {
          return new Promise((resolve, reject) => {
            GM.xmlHttpRequest({
              method: "GET",
              url,
              overrideMimeType: "text/plain; charset=x-user-defined",
              onload: ({ responseText, responseHeaders }) => {
                var _a, _b;
                const headers = parseHeader(responseHeaders);
                const data = new Blob([
                  Uint8Array.from(responseText.split("").map((i) => i.charCodeAt(0)))
                ], { type: (_b = (_a = headers.get("content-type")) == null ? void 0 : _a[0]) != null ? _b : "image/jpeg" });
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
              }
            });
          });
        });
      }
      image2.url2line = url2line;
      function convertOnDemand(line) {
        return __async(this, null, function* () {
          const match = line.match(/^<(.+)\|(.+)>$/);
          if (match) {
            const url = `https://${match[2]}.mitemin.net/userpageimage/viewimagebig/icode/${match[1]}/`;
            try {
              return yield url2line(url);
            } catch (err) {
              addMessage([url, JSON.stringify(err)], "Image download failed", "orange");
              return `![${line}](${url})`;
            }
          }
          return line;
        });
      }
      image2.convertOnDemand = convertOnDemand;
    })(image = util2.image || (util2.image = {}));
  })(util || (util = {}));
  function updateStatus() {
    statusIndicator.innerText = `(${finishedCount}/${totalCount})`;
  }
  function downloadChapter(ncode, chapter) {
    return __async(this, null, function* () {
      const url = `https://${location.host}/txtdownload/dlstart/ncode/${ncode}/?no=${chapter}&hankaku=0&code=utf-8&kaigyo=lf`;
      log(`fetch chapter: ${chapter}`);
      const resp = yield fetch(url);
      if (resp.status !== 200) {
        addMessage([`${resp.status} ${resp.statusText}`, url], "Fetch chapter failed");
        throw new Error(`Fetch chapter failed: ${resp.status} ${resp.statusText} : ${url}`);
      }
      return yield resp.text();
    });
  }
  function clearMessage() {
    while (messageNodes.length) {
      messageNodes.pop().remove();
    }
  }
  function getMetaData() {
    const data = {
      link: document.location.href
    };
    const authorContainer = document.querySelector(".novel_writername");
    const authorAnchor = document.querySelector(".novel_writername > a:nth-child(1)");
    if (authorAnchor instanceof HTMLAnchorElement) {
      data["author"] = authorAnchor.innerText;
      data["author_link"] = authorAnchor.href;
    } else if (authorContainer instanceof HTMLDivElement) {
      data["author"] = authorContainer.innerText.replace(/^作者：/, "");
    }
    return [
      "---",
      ...Object.entries(data).map(([k, v]) => `${k}: ${v}`),
      "---"
    ].join("\n");
  }
  function getLatestPart(url) {
    return url.split("/").filter((i) => i).slice(-1)[0];
  }
  function unescapeHTML(input) {
    const doc = new DOMParser().parseFromString(input, "text/html");
    return doc.documentElement.textContent;
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
      URL.revokeObjectURL(anchor.href);
    }, 0);
  }
  function strip(str) {
    return str.replace(/^\s+|\s+$/g, "");
  }
  function sleep(duration) {
    return new Promise((resolve) => {
      setTimeout(resolve, duration);
    });
  }
  function downloadChapterChunk(ncode, chapters) {
    return __async(this, null, function* () {
      return Promise.all(chapters.map((i) => function() {
        return __async(this, null, function* () {
          const ret = yield Promise.all((yield downloadChapter(ncode, i.chapter)).split("\n").map(strip).filter((i2) => i2.length > 0).map(unescapeHTML).map(util.image.convertOnDemand));
          ret.splice(0, 0, `# ${i.title}`);
          finishedCount += 1;
          updateStatus();
          return ret;
        });
      }())).then((i) => {
        const ret = [];
        i.map((j) => {
          ret.push(...j);
        });
        return ret;
      });
    });
  }
  function main(button) {
    return __async(this, null, function* () {
      clearMessage();
      const ncode = getLatestPart(document.querySelector("#novel_footer > ul:nth-child(1) > li:nth-child(3) > a:nth-child(1)").href);
      log(`start downloading: ${ncode}`);
      const chapters = [];
      for (const i of document.querySelectorAll("dl.novel_sublist2 > dd:nth-child(1) > a:nth-child(1)")) {
        chapters.push({ chapter: getLatestPart(i.href), title: i.innerText });
      }
      finishedCount = 0;
      totalCount = chapters.length;
      updateStatus();
      const lines = [];
      const chunkSize = 10;
      for (let i = 0; i < chapters.length; i += chunkSize) {
        lines.push(...yield downloadChapterChunk(ncode, chapters.slice(i, i + chunkSize)));
        yield sleep(5e3);
      }
      log(`got ${lines.length} lines`);
      function download() {
        downloadFile(new Blob([getMetaData(), "\n\n", lines.join("\n\n")], {
          type: "text/markdown"
        }));
      }
      button.onclick = download;
      download();
    });
  }
  (function() {
    return __async(this, null, function* () {
      const button = document.createElement("button");
      button.innerText = "Download all chapters";
      button.className = "button";
      button.onclick = () => __async(this, null, function* () {
        try {
          button.disabled = true;
          button.style.opacity = "50%";
          yield main(button);
        } catch (err) {
          console.error(err);
        } finally {
          button.disabled = false;
          button.style.opacity = "";
        }
      });
      document.querySelector("#novel_ex").after(button, statusIndicator);
      log("activated");
    });
  })();
})();
