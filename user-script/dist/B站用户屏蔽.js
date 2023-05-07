// ==UserScript==
// @namespace https://github.com/NateScarlet/Scripts/tree/master/user-script
// @name     B站用户屏蔽
// @description 避免看到指定用户上传的视频，在用户个人主页会多出屏蔽按钮。
// @grant    GM.getValue
// @grant    GM.setValue
// @grant    GM.deleteValue
// @include	 https://search.bilibili.com/*
// @include	 https://space.bilibili.com/*
// @include	 https://www.bilibili.com/*
// @run-at   document-idle
// @version   2023.05.07+4717b6fe
// ==/UserScript==

(() => {
  var __defProp = Object.defineProperty;
  var __defProps = Object.defineProperties;
  var __getOwnPropDescs = Object.getOwnPropertyDescriptors;
  var __getOwnPropSymbols = Object.getOwnPropertySymbols;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __propIsEnum = Object.prototype.propertyIsEnumerable;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __spreadValues = (a2, b2) => {
    for (var prop in b2 || (b2 = {}))
      if (__hasOwnProp.call(b2, prop))
        __defNormalProp(a2, prop, b2[prop]);
    if (__getOwnPropSymbols)
      for (var prop of __getOwnPropSymbols(b2)) {
        if (__propIsEnum.call(b2, prop))
          __defNormalProp(a2, prop, b2[prop]);
      }
    return a2;
  };
  var __spreadProps = (a2, b2) => __defProps(a2, __getOwnPropDescs(b2));
  var __async = (__this, __arguments, generator) => {
    return new Promise((resolve, reject) => {
      var fulfilled = (value) => {
        try {
          step(generator.next(value));
        } catch (e2) {
          reject(e2);
        }
      };
      var rejected = (value) => {
        try {
          step(generator.throw(value));
        } catch (e2) {
          reject(e2);
        }
      };
      var step = (x2) => x2.done ? resolve(x2.value) : Promise.resolve(x2.value).then(fulfilled, rejected);
      step((generator = generator.apply(__this, __arguments)).next());
    });
  };

  // utils/compare.ts
  function compare(a2, b2) {
    if (a2 > b2) {
      return 1;
    }
    if (a2 < b2) {
      return -1;
    }
    return 0;
  }

  // utils/obtainHTMLElement.ts
  function obtainHTMLElement(tag, id) {
    const match = document.getElementById(id);
    if (match) {
      return { el: match, isCreated: false };
    }
    const el = document.createElement(tag);
    el.id = id;
    return {
      el,
      isCreated: true
    };
  }

  // utils/usePolling.ts
  function usePolling({
    update,
    scheduleNext = requestAnimationFrame
  }) {
    let isCancelled = false;
    function run() {
      return __async(this, null, function* () {
        if (isCancelled) {
          return;
        }
        yield update();
        scheduleNext(run);
      });
    }
    function dispose() {
      isCancelled = true;
    }
    run();
    return {
      dispose
    };
  }

  // utils/useGMValue.ts
  function useGMValue(key, defaultValue) {
    const state = {
      value: defaultValue,
      loadingCount: 0
    };
    function read() {
      return __async(this, null, function* () {
        if (state.loadingCount > 0) {
          return;
        }
        state.loadingCount += 1;
        try {
          const value = yield GM.getValue(key);
          if (value != null) {
            try {
              state.value = JSON.parse(String(value));
            } catch (e2) {
              state.value = defaultValue;
            }
          }
        } finally {
          state.loadingCount -= 1;
        }
      });
    }
    function write() {
      return __async(this, null, function* () {
        state.loadingCount += 1;
        try {
          if (state.value == null) {
            yield GM.deleteValue(key);
          } else {
            yield GM.setValue(key, JSON.stringify(state.value));
          }
        } finally {
          state.loadingCount -= 1;
        }
      });
    }
    read();
    const polling = usePolling({
      update: () => read(),
      scheduleNext: (update) => setTimeout(update, 500)
    });
    return {
      get value() {
        return state.value;
      },
      set value(v2) {
        state.value = v2;
        write();
      },
      get isLoading() {
        return state.loadingCount > 0;
      },
      dispose: polling.dispose
    };
  }

  // node_modules/.pnpm/lit-html@2.7.3/node_modules/lit-html/lit-html.js
  var t;
  var i = window;
  var s = i.trustedTypes;
  var e = s ? s.createPolicy("lit-html", { createHTML: (t2) => t2 }) : void 0;
  var o = "$lit$";
  var n = `lit$${(Math.random() + "").slice(9)}$`;
  var l = "?" + n;
  var h = `<${l}>`;
  var r = document;
  var d = () => r.createComment("");
  var u = (t2) => t2 === null || typeof t2 != "object" && typeof t2 != "function";
  var c = Array.isArray;
  var v = (t2) => c(t2) || typeof (t2 == null ? void 0 : t2[Symbol.iterator]) == "function";
  var a = "[ 	\n\f\r]";
  var f = /<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g;
  var _ = /-->/g;
  var m = />/g;
  var p = RegExp(`>|${a}(?:([^\\s"'>=/]+)(${a}*=${a}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`, "g");
  var g = /'/g;
  var $ = /"/g;
  var y = /^(?:script|style|textarea|title)$/i;
  var w = (t2) => (i2, ...s2) => ({ _$litType$: t2, strings: i2, values: s2 });
  var x = w(1);
  var b = w(2);
  var T = Symbol.for("lit-noChange");
  var A = Symbol.for("lit-nothing");
  var E = new WeakMap();
  var C = r.createTreeWalker(r, 129, null, false);
  var P = (t2, i2) => {
    const s2 = t2.length - 1, l2 = [];
    let r2, d2 = i2 === 2 ? "<svg>" : "", u2 = f;
    for (let i3 = 0; i3 < s2; i3++) {
      const s3 = t2[i3];
      let e2, c3, v2 = -1, a2 = 0;
      for (; a2 < s3.length && (u2.lastIndex = a2, c3 = u2.exec(s3), c3 !== null); )
        a2 = u2.lastIndex, u2 === f ? c3[1] === "!--" ? u2 = _ : c3[1] !== void 0 ? u2 = m : c3[2] !== void 0 ? (y.test(c3[2]) && (r2 = RegExp("</" + c3[2], "g")), u2 = p) : c3[3] !== void 0 && (u2 = p) : u2 === p ? c3[0] === ">" ? (u2 = r2 != null ? r2 : f, v2 = -1) : c3[1] === void 0 ? v2 = -2 : (v2 = u2.lastIndex - c3[2].length, e2 = c3[1], u2 = c3[3] === void 0 ? p : c3[3] === '"' ? $ : g) : u2 === $ || u2 === g ? u2 = p : u2 === _ || u2 === m ? u2 = f : (u2 = p, r2 = void 0);
      const w2 = u2 === p && t2[i3 + 1].startsWith("/>") ? " " : "";
      d2 += u2 === f ? s3 + h : v2 >= 0 ? (l2.push(e2), s3.slice(0, v2) + o + s3.slice(v2) + n + w2) : s3 + n + (v2 === -2 ? (l2.push(void 0), i3) : w2);
    }
    const c2 = d2 + (t2[s2] || "<?>") + (i2 === 2 ? "</svg>" : "");
    if (!Array.isArray(t2) || !t2.hasOwnProperty("raw"))
      throw Error("invalid template strings array");
    return [e !== void 0 ? e.createHTML(c2) : c2, l2];
  };
  var V = class {
    constructor({ strings: t2, _$litType$: i2 }, e2) {
      let h2;
      this.parts = [];
      let r2 = 0, u2 = 0;
      const c2 = t2.length - 1, v2 = this.parts, [a2, f2] = P(t2, i2);
      if (this.el = V.createElement(a2, e2), C.currentNode = this.el.content, i2 === 2) {
        const t3 = this.el.content, i3 = t3.firstChild;
        i3.remove(), t3.append(...i3.childNodes);
      }
      for (; (h2 = C.nextNode()) !== null && v2.length < c2; ) {
        if (h2.nodeType === 1) {
          if (h2.hasAttributes()) {
            const t3 = [];
            for (const i3 of h2.getAttributeNames())
              if (i3.endsWith(o) || i3.startsWith(n)) {
                const s2 = f2[u2++];
                if (t3.push(i3), s2 !== void 0) {
                  const t4 = h2.getAttribute(s2.toLowerCase() + o).split(n), i4 = /([.?@])?(.*)/.exec(s2);
                  v2.push({ type: 1, index: r2, name: i4[2], strings: t4, ctor: i4[1] === "." ? k : i4[1] === "?" ? I : i4[1] === "@" ? L : R });
                } else
                  v2.push({ type: 6, index: r2 });
              }
            for (const i3 of t3)
              h2.removeAttribute(i3);
          }
          if (y.test(h2.tagName)) {
            const t3 = h2.textContent.split(n), i3 = t3.length - 1;
            if (i3 > 0) {
              h2.textContent = s ? s.emptyScript : "";
              for (let s2 = 0; s2 < i3; s2++)
                h2.append(t3[s2], d()), C.nextNode(), v2.push({ type: 2, index: ++r2 });
              h2.append(t3[i3], d());
            }
          }
        } else if (h2.nodeType === 8)
          if (h2.data === l)
            v2.push({ type: 2, index: r2 });
          else {
            let t3 = -1;
            for (; (t3 = h2.data.indexOf(n, t3 + 1)) !== -1; )
              v2.push({ type: 7, index: r2 }), t3 += n.length - 1;
          }
        r2++;
      }
    }
    static createElement(t2, i2) {
      const s2 = r.createElement("template");
      return s2.innerHTML = t2, s2;
    }
  };
  function N(t2, i2, s2 = t2, e2) {
    var o2, n2, l2, h2;
    if (i2 === T)
      return i2;
    let r2 = e2 !== void 0 ? (o2 = s2._$Co) === null || o2 === void 0 ? void 0 : o2[e2] : s2._$Cl;
    const d2 = u(i2) ? void 0 : i2._$litDirective$;
    return (r2 == null ? void 0 : r2.constructor) !== d2 && ((n2 = r2 == null ? void 0 : r2._$AO) === null || n2 === void 0 || n2.call(r2, false), d2 === void 0 ? r2 = void 0 : (r2 = new d2(t2), r2._$AT(t2, s2, e2)), e2 !== void 0 ? ((l2 = (h2 = s2)._$Co) !== null && l2 !== void 0 ? l2 : h2._$Co = [])[e2] = r2 : s2._$Cl = r2), r2 !== void 0 && (i2 = N(t2, r2._$AS(t2, i2.values), r2, e2)), i2;
  }
  var S = class {
    constructor(t2, i2) {
      this._$AV = [], this._$AN = void 0, this._$AD = t2, this._$AM = i2;
    }
    get parentNode() {
      return this._$AM.parentNode;
    }
    get _$AU() {
      return this._$AM._$AU;
    }
    u(t2) {
      var i2;
      const { el: { content: s2 }, parts: e2 } = this._$AD, o2 = ((i2 = t2 == null ? void 0 : t2.creationScope) !== null && i2 !== void 0 ? i2 : r).importNode(s2, true);
      C.currentNode = o2;
      let n2 = C.nextNode(), l2 = 0, h2 = 0, d2 = e2[0];
      for (; d2 !== void 0; ) {
        if (l2 === d2.index) {
          let i3;
          d2.type === 2 ? i3 = new M(n2, n2.nextSibling, this, t2) : d2.type === 1 ? i3 = new d2.ctor(n2, d2.name, d2.strings, this, t2) : d2.type === 6 && (i3 = new z(n2, this, t2)), this._$AV.push(i3), d2 = e2[++h2];
        }
        l2 !== (d2 == null ? void 0 : d2.index) && (n2 = C.nextNode(), l2++);
      }
      return o2;
    }
    v(t2) {
      let i2 = 0;
      for (const s2 of this._$AV)
        s2 !== void 0 && (s2.strings !== void 0 ? (s2._$AI(t2, s2, i2), i2 += s2.strings.length - 2) : s2._$AI(t2[i2])), i2++;
    }
  };
  var M = class {
    constructor(t2, i2, s2, e2) {
      var o2;
      this.type = 2, this._$AH = A, this._$AN = void 0, this._$AA = t2, this._$AB = i2, this._$AM = s2, this.options = e2, this._$Cp = (o2 = e2 == null ? void 0 : e2.isConnected) === null || o2 === void 0 || o2;
    }
    get _$AU() {
      var t2, i2;
      return (i2 = (t2 = this._$AM) === null || t2 === void 0 ? void 0 : t2._$AU) !== null && i2 !== void 0 ? i2 : this._$Cp;
    }
    get parentNode() {
      let t2 = this._$AA.parentNode;
      const i2 = this._$AM;
      return i2 !== void 0 && (t2 == null ? void 0 : t2.nodeType) === 11 && (t2 = i2.parentNode), t2;
    }
    get startNode() {
      return this._$AA;
    }
    get endNode() {
      return this._$AB;
    }
    _$AI(t2, i2 = this) {
      t2 = N(this, t2, i2), u(t2) ? t2 === A || t2 == null || t2 === "" ? (this._$AH !== A && this._$AR(), this._$AH = A) : t2 !== this._$AH && t2 !== T && this._(t2) : t2._$litType$ !== void 0 ? this.g(t2) : t2.nodeType !== void 0 ? this.$(t2) : v(t2) ? this.T(t2) : this._(t2);
    }
    k(t2) {
      return this._$AA.parentNode.insertBefore(t2, this._$AB);
    }
    $(t2) {
      this._$AH !== t2 && (this._$AR(), this._$AH = this.k(t2));
    }
    _(t2) {
      this._$AH !== A && u(this._$AH) ? this._$AA.nextSibling.data = t2 : this.$(r.createTextNode(t2)), this._$AH = t2;
    }
    g(t2) {
      var i2;
      const { values: s2, _$litType$: e2 } = t2, o2 = typeof e2 == "number" ? this._$AC(t2) : (e2.el === void 0 && (e2.el = V.createElement(e2.h, this.options)), e2);
      if (((i2 = this._$AH) === null || i2 === void 0 ? void 0 : i2._$AD) === o2)
        this._$AH.v(s2);
      else {
        const t3 = new S(o2, this), i3 = t3.u(this.options);
        t3.v(s2), this.$(i3), this._$AH = t3;
      }
    }
    _$AC(t2) {
      let i2 = E.get(t2.strings);
      return i2 === void 0 && E.set(t2.strings, i2 = new V(t2)), i2;
    }
    T(t2) {
      c(this._$AH) || (this._$AH = [], this._$AR());
      const i2 = this._$AH;
      let s2, e2 = 0;
      for (const o2 of t2)
        e2 === i2.length ? i2.push(s2 = new M(this.k(d()), this.k(d()), this, this.options)) : s2 = i2[e2], s2._$AI(o2), e2++;
      e2 < i2.length && (this._$AR(s2 && s2._$AB.nextSibling, e2), i2.length = e2);
    }
    _$AR(t2 = this._$AA.nextSibling, i2) {
      var s2;
      for ((s2 = this._$AP) === null || s2 === void 0 || s2.call(this, false, true, i2); t2 && t2 !== this._$AB; ) {
        const i3 = t2.nextSibling;
        t2.remove(), t2 = i3;
      }
    }
    setConnected(t2) {
      var i2;
      this._$AM === void 0 && (this._$Cp = t2, (i2 = this._$AP) === null || i2 === void 0 || i2.call(this, t2));
    }
  };
  var R = class {
    constructor(t2, i2, s2, e2, o2) {
      this.type = 1, this._$AH = A, this._$AN = void 0, this.element = t2, this.name = i2, this._$AM = e2, this.options = o2, s2.length > 2 || s2[0] !== "" || s2[1] !== "" ? (this._$AH = Array(s2.length - 1).fill(new String()), this.strings = s2) : this._$AH = A;
    }
    get tagName() {
      return this.element.tagName;
    }
    get _$AU() {
      return this._$AM._$AU;
    }
    _$AI(t2, i2 = this, s2, e2) {
      const o2 = this.strings;
      let n2 = false;
      if (o2 === void 0)
        t2 = N(this, t2, i2, 0), n2 = !u(t2) || t2 !== this._$AH && t2 !== T, n2 && (this._$AH = t2);
      else {
        const e3 = t2;
        let l2, h2;
        for (t2 = o2[0], l2 = 0; l2 < o2.length - 1; l2++)
          h2 = N(this, e3[s2 + l2], i2, l2), h2 === T && (h2 = this._$AH[l2]), n2 || (n2 = !u(h2) || h2 !== this._$AH[l2]), h2 === A ? t2 = A : t2 !== A && (t2 += (h2 != null ? h2 : "") + o2[l2 + 1]), this._$AH[l2] = h2;
      }
      n2 && !e2 && this.j(t2);
    }
    j(t2) {
      t2 === A ? this.element.removeAttribute(this.name) : this.element.setAttribute(this.name, t2 != null ? t2 : "");
    }
  };
  var k = class extends R {
    constructor() {
      super(...arguments), this.type = 3;
    }
    j(t2) {
      this.element[this.name] = t2 === A ? void 0 : t2;
    }
  };
  var H = s ? s.emptyScript : "";
  var I = class extends R {
    constructor() {
      super(...arguments), this.type = 4;
    }
    j(t2) {
      t2 && t2 !== A ? this.element.setAttribute(this.name, H) : this.element.removeAttribute(this.name);
    }
  };
  var L = class extends R {
    constructor(t2, i2, s2, e2, o2) {
      super(t2, i2, s2, e2, o2), this.type = 5;
    }
    _$AI(t2, i2 = this) {
      var s2;
      if ((t2 = (s2 = N(this, t2, i2, 0)) !== null && s2 !== void 0 ? s2 : A) === T)
        return;
      const e2 = this._$AH, o2 = t2 === A && e2 !== A || t2.capture !== e2.capture || t2.once !== e2.once || t2.passive !== e2.passive, n2 = t2 !== A && (e2 === A || o2);
      o2 && this.element.removeEventListener(this.name, this, e2), n2 && this.element.addEventListener(this.name, this, t2), this._$AH = t2;
    }
    handleEvent(t2) {
      var i2, s2;
      typeof this._$AH == "function" ? this._$AH.call((s2 = (i2 = this.options) === null || i2 === void 0 ? void 0 : i2.host) !== null && s2 !== void 0 ? s2 : this.element, t2) : this._$AH.handleEvent(t2);
    }
  };
  var z = class {
    constructor(t2, i2, s2) {
      this.element = t2, this.type = 6, this._$AN = void 0, this._$AM = i2, this.options = s2;
    }
    get _$AU() {
      return this._$AM._$AU;
    }
    _$AI(t2) {
      N(this, t2);
    }
  };
  var j = i.litHtmlPolyfillSupport;
  j == null || j(V, M), ((t = i.litHtmlVersions) !== null && t !== void 0 ? t : i.litHtmlVersions = []).push("2.7.3");
  var B = (t2, i2, s2) => {
    var e2, o2;
    const n2 = (e2 = s2 == null ? void 0 : s2.renderBefore) !== null && e2 !== void 0 ? e2 : i2;
    let l2 = n2._$litPart$;
    if (l2 === void 0) {
      const t3 = (o2 = s2 == null ? void 0 : s2.renderBefore) !== null && o2 !== void 0 ? o2 : null;
      n2._$litPart$ = l2 = new M(i2.insertBefore(d(), t3), t3, void 0, s2 != null ? s2 : {});
    }
    return l2._$AI(t2), l2;
  };

  // B站用户屏蔽.ts
  var blockedUsers = useGMValue("blockedUsers@206ceed9-b514-4902-ad70-aa621fed5cd4", {});
  function migrateV1() {
    return __async(this, null, function* () {
      const key = "blockedUserIDs@7ced1613-89d7-4754-8989-2ad0d7cfa9db";
      const oldValue = yield GM.getValue(key);
      if (!oldValue) {
        return;
      }
      const newValue = __spreadValues({}, blockedUsers.value);
      JSON.parse(String(oldValue)).forEach((i2) => {
        newValue[i2] = true;
      });
      blockedUsers.value = newValue;
      yield GM.deleteValue(key);
    });
  }
  function renderActions(userID) {
    const parent = document.querySelector(".h-action");
    if (!parent) {
      return;
    }
    const { el: container, isCreated } = obtainHTMLElement("div", "7ced1613-89d7-4754-8989-2ad0d7cfa9db");
    if (isCreated) {
      container.style.display = "inline";
      parent.prepend(container);
    }
    const isBlocked = !!blockedUsers.value[userID];
    const count = Object.keys(blockedUsers.value).length;
    B(x`
      <a
        class="h-f-btn"
        target="_blank"
        @click="${(e2) => {
      e2.stopPropagation();
      const el = e2.target;
      el.href = blockedUsersURL();
    }}"
      >
        已屏蔽 ${count}
      </a>
      <span
        class="h-f-btn"
        @click="${(e2) => {
      var _a, _b;
      e2.stopPropagation();
      const isBlocked2 = !!blockedUsers.value[userID];
      blockedUsers.value = __spreadProps(__spreadValues({}, blockedUsers.value), {
        [userID]: !isBlocked2 ? {
          name: (_b = (_a = document.getElementById("h-name")) == null ? void 0 : _a.innerText) != null ? _b : "",
          blockedAt: Date.now()
        } : void 0
      });
    }}"
      >
        ${isBlocked ? "取消屏蔽" : "屏蔽"}
      </span>
    `, container);
  }
  function parseUserURL(rawURL) {
    if (!rawURL) {
      return;
    }
    const url = new URL(rawURL, window.location.href);
    if (url.host !== "space.bilibili.com") {
      return;
    }
    const match = /^\/(\d+)\/?/.exec(url.pathname);
    if (!match) {
      return;
    }
    return match[1];
  }
  function renderVideoCard() {
    document.querySelectorAll(".bili-video-card").forEach((i2) => {
      var _a;
      const rawURL = (_a = i2.querySelector("a.bili-video-card__info--owner")) == null ? void 0 : _a.getAttribute("href");
      const userID = parseUserURL(rawURL);
      if (!userID) {
        return;
      }
      const isBlocked = blockedUsers.value[userID];
      const container = i2.parentElement.classList.contains("video-list-item") ? i2.parentElement : i2;
      if (isBlocked) {
        container.setAttribute("hidden", "");
      } else {
        container.removeAttribute("hidden");
      }
    });
    document.querySelectorAll(".video-page-card-small").forEach((i2) => {
      var _a;
      const rawURL = (_a = i2.querySelector(".upname a")) == null ? void 0 : _a.getAttribute("href");
      if (!rawURL) {
        return;
      }
      const userID = parseUserURL(rawURL);
      if (!userID) {
        return;
      }
      const isBlocked = blockedUsers.value[userID];
      const container = i2;
      if (isBlocked) {
        container.setAttribute("hidden", "");
      } else {
        container.removeAttribute("hidden");
      }
    });
  }
  function blockedUsersHTML() {
    const userIDs = Object.keys(blockedUsers.value);
    const now = new Date();
    function getData(id) {
      const value = blockedUsers.value[id];
      const { blockedAt: rawBlockedAt = 0, name = id } = typeof value === "boolean" ? {} : value;
      const blockedAt = new Date(rawBlockedAt);
      return {
        id,
        blockedAt,
        name,
        idAsNumber: Number.parseInt(id),
        isFallback: rawBlockedAt === 0
      };
    }
    return [
      "<html>",
      "<head>",
      "<title>已屏蔽的用户</title>",
      `<script id="data" lang="application/json">
    ${JSON.stringify(blockedUsers.value, void 0, 2)}
    <\/script>`,
      "</head>",
      "<body>",
      "<div>",
      `  <h1>已屏蔽 ${userIDs.length} 用户</h1>`,
      `  <time datetime="${now.toISOString()}">${now.toLocaleString()}</time>`,
      "  <ul>",
      ...userIDs.map(getData).sort((a2, b2) => {
        const dateCompare = compare(a2.blockedAt, b2.blockedAt);
        if (dateCompare !== 0) {
          return -dateCompare;
        }
        return compare(a2.idAsNumber, b2.idAsNumber);
      }).map(({ id, name, blockedAt, isFallback }) => {
        return [
          "<li>",
          `<a href="https://space.bilibili.com/${id}" target="_blank">${name}</a>`,
          ...!isFallback ? [
            `<span>屏蔽于<time datetime="${blockedAt.toISOString()}">${blockedAt.toLocaleString()}</time></span>`
          ] : [],
          "</li>"
        ].join("\n");
      }),
      "  </ul>",
      "</div>",
      "</body>",
      "</html>"
    ].join("\n");
  }
  function blockedUsersURL() {
    const b2 = new Blob([blockedUsersHTML()], {
      type: "text/html;charset=UTF-8"
    });
    return URL.createObjectURL(b2);
  }
  function main() {
    return __async(this, null, function* () {
      yield migrateV1();
      if (window.location.host === "space.bilibili.com") {
        const userID = parseUserURL(window.location.href);
        if (!userID) {
          return;
        }
        usePolling({
          update: () => renderActions(userID)
        });
      } else {
        usePolling({
          update: () => renderVideoCard()
        });
      }
    });
  }
  main();
})();
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
