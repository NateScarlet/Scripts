// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     NicoNico manga download
// @description save loaded manga as markdown.
// @grant    none
// @include	 https://seiga.nicovideo.jp/watch/*
// @run-at   document-idle
// @version   2021.11.29+0f3d2aa2
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

  // utils/canvasToMarkdown.ts
  function canvasToMarkdown(canvas, alt = "", title = "") {
    return `![${alt}](${canvas.toDataURL()} "${title}")`;
  }

  // utils/urlLastPart.ts
  function urlLastPart(url) {
    return url.split("/").filter((i) => i).slice(-1)[0];
  }

  // utils/downloadFile.ts
  function downloadFile(file, filename = `${urlLastPart(location.pathname)} ${document.title}.md`) {
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(file);
    anchor.download = filename;
    anchor.style["display"] = "none";
    document.body.append(anchor);
    anchor.click();
    setTimeout(() => {
      document.body.removeChild(anchor);
      URL.revokeObjectURL(anchor.href);
    }, 0);
  }

  // utils/sleep.ts
  function sleep(duration) {
    return __async(this, null, function* () {
      return new Promise((resolve) => {
        setTimeout(resolve, duration);
      });
    });
  }

  // niconico_manga_download.ts
  var __name__ = "NicoNico manga download";
  (function() {
    return __async(this, null, function* () {
      var _a, _b, _c;
      let lines = [];
      const title = (_b = (_a = document.querySelector("meta[property='og:title']")) == null ? void 0 : _a.content) != null ? _b : document.title;
      const startTime = Date.now();
      const timeout = () => {
        if (Date.now() - startTime < 3e5) {
          return true;
        }
        throw new Error(`${__name__}: timeout`);
      };
      while (timeout()) {
        const pages = document.querySelectorAll("li.page");
        for (let index = 0; index < pages.length; index += 1) {
          const li = pages.item(index);
          while (timeout()) {
            const canvas = li.querySelector("canvas:not(.balloon)");
            const pageIndex = Number.parseInt(li.dataset.pageIndex, 10) || index;
            if (!canvas) {
              li.scrollIntoView();
              console.log(`${__name__}: waiting page: ${pageIndex}`);
              yield sleep(1e3);
              continue;
            }
            lines.push(canvasToMarkdown(canvas, li.id, `p${pageIndex + 1}`));
            break;
          }
        }
        (_c = pages.item(0)) == null ? void 0 : _c.scrollIntoView();
        if (lines.length > 0) {
          break;
        }
        yield sleep(1e3);
      }
      console.log(`${__name__}: got ${lines.length} page(s)`);
      const file = new Blob([
        `# ${title}

`,
        `${window.location.href}

`,
        lines.join("\n\n") + "\n"
      ], { type: "text/markdown" });
      downloadFile(file, `${title}.md`);
    });
  })();
})();
