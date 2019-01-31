// ==UserScript==
// @name     刺猬猫公共章节自动下载
// @version  2
// @grant    none
// @include	 https://www.ciweimao.com/chapter/*
// @run-at   document-idle
// ==/UserScript==

(function() {
  const element = document.querySelector("#J_BookRead");
  const chapter = document.querySelector("#J_BookCnt h3.chapter").firstChild
    .textContent;
  const lines = [];
  for (const i of element.querySelectorAll("p:not(.author-say)")) {
    let line = i.firstChild.textContent.replace(/^\s+|\s+$/g, "");
    if (line.length === 0) {
      continue;
    }
    if (i.classList.contains("author_say")) {
      line = `    ${line}`;
    }
    lines.push(line);
  }

  const file = new Blob([`# ${chapter}\n\n`, lines.join("\n\n")], {
    type: "text/markdown"
  });
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(file);
  anchor.download = `${location.pathname.split("/").slice(-1)[0]} ${
    document.title
  }.md`;
  anchor.style["display"] = "none";
  document.body.append(anchor);
  anchor.click();
  setTimeout(() => {
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, 0);
})();
