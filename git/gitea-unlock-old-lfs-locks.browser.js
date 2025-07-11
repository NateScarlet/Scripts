// 在浏览器中对应仓库页面运行，解锁所有大于指定时长前锁定的 lfs 锁
(function () {
  const match = /^\/(?<owner>[^\/]+)\/(?<repo>[^\/]+)/.exec(location.pathname);
  if (!match?.groups) {
    throw new Error("无法从当前页面识别到仓库");
  }
  const { owner, repo } = match.groups;

  const csrfToken = JSON.parse(
    document.body.getAttribute("hx-headers") || "{}"
  )["x-csrf-token"];
  if (!csrfToken) {
    throw new Error("找不到 CSRF Token");
  }

  async function forceUnlock(id) {
    const formData = new URLSearchParams();
    formData.append("_csrf", csrfToken);

    const resp = await fetch(
      `/${owner}/${repo}/settings/lfs/locks/${id}/unlock`,
      {
        method: "POST",
        body: formData,
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      }
    );
    if (resp.status !== 200) {
      throw new Error(`${id} 解锁失败，状态码 ${resp.status}`);
    }
  }

  function parseUnlockURL(url) {
    if (!url) {
      return;
    }
    const match =
      /^\/(?<owner>[^\/]+)\/(?<repo>[^\/]+)\/settings\/lfs\/locks\/(?<lockID>[^\/]+)\/unlock/.exec(
        url
      );
    if (match?.groups) {
      const { owner, repo, lockID } = match.groups;
      return {
        owner,
        repo,
        lockID,
      };
    }
  }

  async function listLocks(page) {
    console.log(`加载锁，第${page}页`);
    const locksResp = await fetch(
      `/${owner}/${repo}/settings/lfs/locks?page=${page}`
    );
    const locksHtml = await locksResp.text();
    const parser = new DOMParser();
    const doc = parser.parseFromString(locksHtml, "text/html");

    const lockRows = doc.querySelectorAll("tbody tr");

    const locks = [];

    lockRows.forEach((row) => {
      const id = parseUnlockURL(
        row.querySelector("td:nth-child(4) form")?.getAttribute("action")
      )?.lockID;
      const lockedAtText = row
        .querySelector("td:nth-child(3) relative-time")
        ?.getAttribute("datetime");

      if (!id || !lockedAtText) return;

      const lockedAt = new Date(lockedAtText);
      if (!Number.isFinite(lockedAt.getTime())) {
        console.warn(`无法解析日期时间，将忽略锁 ${id}`);
        return;
      }

      locks.push({
        id,
        lockedAt,
        path: row.querySelector("td:first-child")?.textContent?.trim() || "",
      });
    });
    const lastPageRawURL = doc
      .querySelector("div.center.page.buttons > div > a:last-child")
      ?.getAttribute("href");
    let lastPage;
    if (!lastPageRawURL) {
      // 最后一页没有链接
      lastPage = page;
    } else {
      const lastPageURL = new URL(lastPageRawURL, document.location);
      const pageStr = lastPageURL.searchParams.get("page");
      if (!pageStr) {
        throw new Error("无法识别分页");
      }
      lastPage = Number.parseInt(pageStr);
      if (!Number.isFinite(lastPage)) {
        throw new Error("无法识别分页");
      }
    }
    return {
      locks,
      lastPage,
    };
  }

  // 获取所有符合条件的锁并解锁
  async function unlockOldLocks(maxAgeMs) {
    try {
      const until = Date.now() - maxAgeMs;

      const locksToUnlock = [];
      for (let page = 1; ; page += 1) {
        const { locks, lastPage } = await listLocks(page);

        locksToUnlock.push(
          ...locks.filter((i) => i.lockedAt.getTime() <= until)
        );
        console.log(`共${lastPage}页，待处理: ${locksToUnlock.length}`);
        if (page >= lastPage) {
          break;
        }
      }

      if (locksToUnlock.length === 0) {
        console.log("没有找到1小时前锁定的文件");
        return;
      }

      // 执行解锁
      await Promise.all(
        locksToUnlock.map(async (lock, index, array) => {
          try {
            console.log(`${index}/${array.length} 将解锁`, lock);
            await forceUnlock(lock.id);
            console.log(`成功解锁: ${lock.path} (ID: ${lock.id})`);
          } catch (error) {
            console.error(`解锁失败 [${lock.id}]: ${error.message}`);
          }
        })
      );
    } catch (error) {
      console.error("解锁过程中出错:", error);
      console.error(`错误: ${error.message}`);
    }
  }

  // 默认解锁 1小时前　(3600秒), 运行前可修改
  unlockOldLocks(3600e3);
})();
