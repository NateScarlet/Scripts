// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     刺猬猫章节自动下载
// @description 打开刺猬猫章节页面时自动保存文章到本地, 支持付费章节。
// @grant    none
// @include	 https://www.ciweimao.com/chapter/*
// @run-at   document-idle
// @version   v2021.11.20+caf75223
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

  // utils/sleep.ts
  function sleep(duration) {
    return __async(this, null, function* () {
      return new Promise((resolve) => {
        setTimeout(resolve, duration);
      });
    });
  }

  // 刺猬猫章节自动下载.ts
  var __name__ = "刺猬猫章节自动下载";
  function image2line(img) {
    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);
    return `![${img.alt}](${canvas.toDataURL()} "${img.title}")`;
  }
  function strip(str) {
    return str.replace(/^\s+|\s+$/g, "");
  }
  function getElementRootText(element) {
    let ret = "";
    for (const i of element.childNodes) {
      if (i.nodeType === i.TEXT_NODE) {
        ret += i.nodeValue;
      }
    }
    return strip(ret);
  }
  function imageUrl2line(url) {
    return __async(this, null, function* () {
      return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
          resolve(image2line(img));
        };
        img.src = url;
      });
    });
  }
  (function() {
    return __async(this, null, function* () {
      const chapter = document.querySelector("#J_BookCnt .chapter").firstChild.textContent;
      let lines = [];
      let startTime = Date.now();
      while (lines.length === 0 && Date.now() - startTime < 6e4) {
        yield sleep(1e3);
        for (const i of document.querySelectorAll("#J_BookImage")) {
          const url = i.style["background-image"].match(/(?:url\(")?(.+)(?:"\))?/)[1];
          const line = yield imageUrl2line(url);
          lines.push(line);
        }
        for (const i of document.querySelectorAll("#J_BookRead p.chapter")) {
          const line = getElementRootText(i);
          lines.push(line);
          for (const img of i.querySelectorAll("img")) {
            lines.push(image2line(img));
          }
        }
        for (const i of document.querySelectorAll("p.author_say")) {
          const line = getElementRootText(i);
          lines.push(`    ${line}`);
          for (const img of i.querySelectorAll("img")) {
            lines.push(image2line(img));
          }
        }
        lines = lines.filter((i) => i.length > 0);
      }
      console.log(`${__name__}: 获取到 ${lines.length} 行`);
      const file = new Blob([`# ${chapter}

`, lines.join("\n\n") + "\n"], {
        type: "text/markdown"
      });
      const anchor = document.createElement("a");
      anchor.href = URL.createObjectURL(file);
      anchor.download = `${location.pathname.split("/").slice(-1)[0]} ${document.title}.md`;
      anchor.style["display"] = "none";
      document.body.append(anchor);
      anchor.click();
      setTimeout(() => {
        document.body.removeChild(anchor);
        URL.revokeObjectURL(anchor.href);
      }, 0);
    });
  })();
})();
