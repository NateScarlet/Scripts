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
// @version  2+fedfc01e
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

  // SF轻小说章节自动下载.ts
  var __name__ = "SF轻小说章节自动下载";
  function image2line(img, bgStyle) {
    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    if (bgStyle) {
      ctx.fillStyle = bgStyle;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
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
  (function() {
    return __async(this, null, function* () {
      const chapter = document.querySelector("#article .article-title").textContent;
      let lines = [
        `# ${chapter}`,
        `[原始页面](${location.href})`,
        ...document.querySelector("#article .article-desc").textContent.split(/\n */).filter((i) => i),
        `---`
      ];
      const keywords = document.querySelector("meta[name='keywords']").content.split(",").filter((i) => !["小说下载", "TXT"].includes(i)).filter((i, index, keywords2) => index === 0 || !i.startsWith(keywords2[0]));
      for (const i of document.querySelectorAll("img#vipImage")) {
        console.log(`${__name__}: 等待图片加载`);
        yield i.decode();
        console.log(`${__name__}: 图片加载完毕`);
        const line = image2line(i, "white");
        lines.push(line);
      }
      for (const i of document.querySelectorAll("#ChapterBody p")) {
        const line = getElementRootText(i);
        lines.push(line);
        for (const img of i.querySelectorAll("img")) {
          lines.push(image2line(img));
        }
      }
      lines = lines.filter((i) => i.length > 0);
      console.log(`${__name__}: 获取到 ${lines.length} 行`);
      const file = new Blob([lines.join("\n\n"), "\n"], {
        type: "text/markdown"
      });
      const anchor = document.createElement("a");
      anchor.href = URL.createObjectURL(file);
      anchor.download = `${keywords.join(" ")}.md`;
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
