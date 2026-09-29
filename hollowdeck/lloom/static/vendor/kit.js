// Generated from ui/kit/src/ by tools/build_ui.mjs -- do not edit
"use strict";
(() => {
  var __defProp = Object.defineProperty;
  var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

  // ui/kit/src/core/element.ts
  var HdElement = class extends HTMLElement {
    static {
      __name(this, "HdElement");
    }
    built = false;
    building = false;
    pending = false;
    connectedCallback() {
      if (this.built) {
        this.connected();
        return;
      }
      if (document.readyState === "loading") {
        if (this.pending) return;
        this.pending = true;
        document.addEventListener(
          "DOMContentLoaded",
          () => {
            this.pending = false;
            if (this.isConnected) this.init();
          },
          { once: true }
        );
        return;
      }
      this.init();
    }
    disconnectedCallback() {
      if (this.built) this.disconnected();
    }
    attributeChangedCallback(name, oldValue, newValue) {
      if (this.built && oldValue !== newValue) this.changed(name);
    }
    init() {
      if (this.built || this.building) return;
      this.building = true;
      this.build();
      this.building = false;
      this.built = true;
      this.render();
      this.connected();
    }
    /** Paint from attributes and state. Called after build and on every observed change. */
    render() {
    }
    /** An observed attribute changed after the build. Default: render. */
    changed(_name) {
      this.render();
    }
    connected() {
    }
    disconnected() {
    }
    /** A property assigned before the element upgraded is an own property shadowing the
     *  accessor; move it through the accessor. */
    upgradeProperty(name) {
      if (Object.prototype.hasOwnProperty.call(this, name)) {
        const self = this;
        const value = self[name];
        delete self[name];
        self[name] = value;
      }
    }
    // ---- attribute helpers ---------------------------------------------------------------
    str(name, fallback2 = "") {
      const v = this.getAttribute(name);
      return v === null ? fallback2 : v;
    }
    flag(name) {
      const v = this.getAttribute(name);
      return v !== null && v !== "false";
    }
    num(name, fallback2) {
      const v = this.getAttribute(name);
      if (v === null || v.trim() === "") return fallback2;
      const n = Number(v);
      return Number.isFinite(n) ? n : fallback2;
    }
    setFlag(name, on) {
      if (on) this.setAttribute(name, "");
      else this.removeAttribute(name);
    }
    get disabled() {
      return this.flag("disabled");
    }
    set disabled(on) {
      this.setFlag("disabled", on);
    }
    /** Disabled, wired, or loading: the value cannot be changed from here. */
    get locked() {
      return this.flag("disabled") || this.flag("wired") || this.flag("loading");
    }
    /** `input` and `change` come from the host, whatever inner part caused them, so a
     *  listener reads `ev.target.value` off the element it listened to. */
    emit(type, detail) {
      const ev = detail === void 0 ? new Event(type, { bubbles: true, cancelable: true }) : new CustomEvent(type, { bubbles: true, cancelable: true, detail });
      return this.dispatchEvent(ev);
    }
  };
  function define(name, ctor) {
    if (!customElements.get(name)) customElements.define(name, ctor);
  }
  __name(define, "define");
  var seq = 0;
  function uid(prefix = "hd") {
    seq += 1;
    return `${prefix}-${seq}-${Math.random().toString(36).slice(2, 7)}`;
  }
  __name(uid, "uid");

  // ui/kit/src/core/dom.ts
  function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === void 0 || v === false) continue;
      if (k === "class") el.className = String(v);
      else if (k === "text") el.textContent = String(v);
      else el.setAttribute(k, v === true ? "" : String(v));
    }
    for (const c of children) {
      if (c === null || c === void 0 || c === false) continue;
      el.append(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return el;
  }
  __name(h, "h");
  function takeChildren(el) {
    const nodes = [...el.childNodes];
    for (const n of nodes) n.remove();
    return nodes;
  }
  __name(takeChildren, "takeChildren");
  function ownText(el) {
    return (el.textContent ?? "").replace(/\s+/g, " ").trim();
  }
  __name(ownText, "ownText");
  function editingText() {
    const a = document.activeElement;
    if (!a) return false;
    if (a instanceof HTMLTextAreaElement) return !a.readOnly && !a.disabled;
    if (a instanceof HTMLInputElement) {
      const t = a.type;
      const texty = t === "text" || t === "search" || t === "number" || t === "url" || t === "email" || t === "password" || t === "tel";
      return texty && !a.readOnly && !a.disabled;
    }
    return a.isContentEditable;
  }
  __name(editingText, "editingText");
  function mods(ev) {
    return { ctrl: ev.ctrlKey || !!ev.metaKey, shift: ev.shiftKey, alt: !!ev.altKey };
  }
  __name(mods, "mods");
  function viewRect() {
    return { x: 0, y: 0, width: document.documentElement.clientWidth || window.innerWidth, height: document.documentElement.clientHeight || window.innerHeight };
  }
  __name(viewRect, "viewRect");
  function rectOf(el) {
    const r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, width: r.width, height: r.height };
  }
  __name(rectOf, "rectOf");

  // ui/kit/src/core/pure/place.ts
  function clampToView(at, size, view, margin = 4) {
    const maxX = view.x + view.width - size.width - margin;
    const maxY = view.y + view.height - size.height - margin;
    return {
      x: Math.round(Math.max(view.x + margin, Math.min(at.x, maxX))),
      y: Math.round(Math.max(view.y + margin, Math.min(at.y, maxY)))
    };
  }
  __name(clampToView, "clampToView");
  function placeAtCursor(cursor, size, view, hotspot = { x: 0, y: 0 }) {
    return clampToView({ x: cursor.x - hotspot.x, y: cursor.y - hotspot.y }, size, view);
  }
  __name(placeAtCursor, "placeAtCursor");
  function placeAgainst(anchor, size, view, side = "below", gap = 2) {
    const fits = /* @__PURE__ */ __name((s) => {
      switch (s) {
        case "below":
          return anchor.y + anchor.height + gap + size.height <= view.y + view.height;
        case "above":
          return anchor.y - gap - size.height >= view.y;
        case "right":
          return anchor.x + anchor.width + gap + size.width <= view.x + view.width;
        case "left":
          return anchor.x - gap - size.width >= view.x;
      }
    }, "fits");
    const opposite = { below: "above", above: "below", right: "left", left: "right" };
    const chosen = fits(side) || !fits(opposite[side]) ? side : opposite[side];
    let at;
    switch (chosen) {
      case "below":
        at = { x: anchor.x, y: anchor.y + anchor.height + gap };
        break;
      case "above":
        at = { x: anchor.x, y: anchor.y - gap - size.height };
        break;
      case "right":
        at = { x: anchor.x + anchor.width + gap, y: anchor.y };
        break;
      case "left":
        at = { x: anchor.x - gap - size.width, y: anchor.y };
        break;
    }
    return { ...clampToView(at, size, view), side: chosen };
  }
  __name(placeAgainst, "placeAgainst");

  // ui/kit/src/dialog/controller.ts
  function confirmKey(key) {
    if (key === "Enter") return "confirm";
    if (key === "Escape") return "cancel";
    return null;
  }
  __name(confirmKey, "confirmKey");
  function pointerLeftPopup(popup, p, margin = 80) {
    return p.x < popup.x - margin || p.x > popup.x + popup.width + margin || p.y < popup.y - margin || p.y > popup.y + popup.height + margin;
  }
  __name(pointerLeftPopup, "pointerLeftPopup");
  function leaveStep(held, left, dragging) {
    if (dragging) return { close: false, held: true };
    if (held) return { close: false, held: left };
    return { close: left, held: false };
  }
  __name(leaveStep, "leaveStep");

  // ui/kit/src/core/layer.ts
  var stack = [];
  var root = null;
  var captured = /* @__PURE__ */ new Set();
  var ESCAPE_OWNERS = "[data-editing], hd-number[data-hd-dragging]";
  function escapeOwner() {
    const a = document.activeElement;
    return a instanceof Element ? a.closest(ESCAPE_OWNERS) : null;
  }
  __name(escapeOwner, "escapeOwner");
  var fallback = null;
  function deferTo(owner, esc, entry) {
    if (fallback) fallback.owner.removeEventListener("keydown", fallback.fn);
    const fn = /* @__PURE__ */ __name((ev) => {
      owner.removeEventListener("keydown", fn);
      if (fallback?.fn === fn) fallback = null;
      if (ev !== esc || ev.defaultPrevented || !entry.handle.open) return;
      ev.preventDefault();
      ev.stopPropagation();
      entry.handle.close("escape");
    }, "fn");
    fallback = { owner, fn };
    owner.addEventListener("keydown", fn);
  }
  __name(deferTo, "deferTo");
  var pointer = { x: 0, y: 0 };
  var installed = false;
  function lastPointer() {
    return { ...pointer };
  }
  __name(lastPointer, "lastPointer");
  function layer() {
    if (root && root.isConnected) return root;
    root = document.createElement("div");
    root.className = "hd-layer";
    document.body.append(root);
    return root;
  }
  __name(layer, "layer");
  function isEscape(ev) {
    return ev.key === "Escape" && !ev.isComposing && ev.keyCode !== 229;
  }
  __name(isEscape, "isEscape");
  function onEscape(ev) {
    if (!isEscape(ev) || ev.defaultPrevented) return;
    const passive = stack.filter((e) => e.opts.passive);
    const active = stack.filter((e) => !e.opts.passive);
    const top = active[active.length - 1];
    for (const e of [...passive].reverse()) e.handle.close("escape");
    const owner = escapeOwner();
    if (owner) {
      if (top) deferTo(owner, ev, top);
      return;
    }
    if (!top && passive.length === 0) return;
    ev.preventDefault();
    ev.stopPropagation();
    top?.handle.close("escape");
  }
  __name(onEscape, "onEscape");
  function install() {
    if (installed) return;
    installed = true;
    const track = /* @__PURE__ */ __name((ev) => {
      pointer = { x: ev.clientX, y: ev.clientY };
    }, "track");
    document.addEventListener("pointermove", track, true);
    document.addEventListener("pointerdown", track, true);
    document.addEventListener(
      "pointerdown",
      (ev) => {
        const active = stack.filter((e) => !e.opts.passive);
        if (active.length === 0) return;
        const target = ev.target;
        let keep = -1;
        active.forEach((e, i) => {
          if (target && (e.el.contains(target) || e.opts.owner && e.opts.owner.contains(target))) keep = i;
        });
        for (let i = active.length - 1; i > keep; i -= 1) active[i]?.handle.close("outside");
      },
      true
    );
    document.addEventListener("keydown", onEscape, true);
    document.addEventListener("gotpointercapture", (ev) => captured.add(ev.pointerId), true);
    document.addEventListener("lostpointercapture", (ev) => captured.delete(ev.pointerId), true);
    document.addEventListener(
      "pointermove",
      (ev) => {
        const dragging = captured.size > 0;
        for (const e of [...stack]) {
          if (!e.opts.leaveMargin) continue;
          const left = pointerLeftPopup(rectOf(e.el), { x: ev.clientX, y: ev.clientY }, e.opts.leaveMargin);
          const step = leaveStep(e.leaveHeld === true, left, dragging);
          e.leaveHeld = step.held;
          if (step.close) e.handle.close("leave");
        }
      },
      true
    );
    window.addEventListener("resize", () => {
      for (const e of stack) e.handle.reposition();
    });
  }
  __name(install, "install");
  function openFloating(el, opts) {
    install();
    el.classList.add("hd-float");
    el.style.visibility = "hidden";
    el.style.left = "0px";
    el.style.top = "0px";
    layer().append(el);
    let open2 = true;
    const place = /* @__PURE__ */ __name(() => {
      const size = { width: el.offsetWidth, height: el.offsetHeight };
      const view = viewRect();
      let at;
      if (opts.at) {
        at = placeAtCursor(opts.at, size, view, opts.hotspot ? opts.hotspot() : { x: 0, y: 0 });
      } else if (opts.anchor) {
        const r = opts.anchor instanceof Element ? rectOf(opts.anchor) : opts.anchor;
        const p = placeAgainst(r, size, view, opts.side ?? "below");
        el.dataset.side = p.side;
        at = p;
      } else {
        at = { x: (view.width - size.width) / 2, y: (view.height - size.height) / 3 };
      }
      el.style.left = `${at.x}px`;
      el.style.top = `${at.y}px`;
      el.style.visibility = "";
    }, "place");
    const handle = {
      el,
      get open() {
        return open2;
      },
      reposition: place,
      close(reason = "api") {
        if (!open2) return;
        open2 = false;
        const at = stack.findIndex((e) => e.handle === handle);
        if (at >= 0) {
          for (const e of stack.slice(at + 1).reverse()) if (!e.opts.passive) e.handle.close("replaced");
          const idx = stack.findIndex((e) => e.handle === handle);
          if (idx >= 0) stack.splice(idx, 1);
        }
        el.remove();
        opts.onClose?.(reason);
        if (opts.restoreFocus && (reason === "escape" || reason === "chosen") && opts.restoreFocus.isConnected) {
          opts.restoreFocus.focus({ preventScroll: true });
        }
      }
    };
    stack.push({ el, opts, handle });
    place();
    return handle;
  }
  __name(openFloating, "openFloating");
  function closeAll(reason = "api") {
    for (const e of [...stack].reverse()) e.handle.close(reason);
  }
  __name(closeAll, "closeAll");

  // ui/kit/src/dialog/element.ts
  var HdConfirm = class extends HdElement {
    static {
      __name(this, "HdConfirm");
    }
    static get observedAttributes() {
      return ["heading", "message", "confirm-label", "danger"];
    }
    okButton;
    cancelButton;
    titleEl;
    msgEl;
    build() {
      this.setAttribute("role", "alertdialog");
      this.titleEl = h("div", { class: "hd-confirm__title" });
      this.msgEl = h("div", { class: "hd-confirm__msg" });
      this.okButton = h("button", { type: "button", class: "btn primary hd-confirm__ok" });
      this.cancelButton = h("button", { type: "button", class: "btn ghost hd-confirm__cancel", text: "Cancel" });
      this.append(this.titleEl, this.msgEl, h("div", { class: "hd-confirm__actions" }, this.okButton, this.cancelButton));
      this.titleEl.id = `${this.id || "hd-confirm"}-title`;
      this.setAttribute("aria-labelledby", this.titleEl.id);
    }
    render() {
      this.titleEl.textContent = this.str("heading");
      this.msgEl.textContent = this.str("message");
      this.msgEl.hidden = !this.str("message");
      this.okButton.textContent = this.str("confirm-label", "OK");
      this.okButton.className = `btn ${this.flag("danger") ? "danger" : "primary"} hd-confirm__ok`;
    }
  };
  var open = null;
  function confirmDialog(opts) {
    open?.close("replaced");
    return new Promise((resolve) => {
      const body = document.createElement("hd-confirm");
      body.setAttribute("heading", opts.title);
      if (opts.message) body.setAttribute("message", opts.message);
      body.setAttribute("confirm-label", opts.confirm ?? "OK");
      if (opts.danger) body.setAttribute("danger", "");
      let settled = false;
      const finish = /* @__PURE__ */ __name((ok) => {
        if (settled) return;
        settled = true;
        resolve(ok);
      }, "finish");
      const focused = document.activeElement;
      const keyboard = !!focused && focused !== document.body && focused.matches(":focus-visible");
      let at = opts.at ?? lastPointer();
      if (!opts.at && keyboard && focused) {
        const r = rectOf(focused);
        at = { x: r.x + r.width / 2, y: r.y + r.height / 2 };
      }
      const handle = openFloating(body, {
        at,
        hotspot: /* @__PURE__ */ __name(() => {
          const b = body.okButton;
          return { x: b.offsetLeft + b.offsetWidth / 2, y: b.offsetTop + b.offsetHeight / 2 };
        }, "hotspot"),
        restoreFocus: opts.restoreFocus ?? focused,
        // Moving away cancels, as in Blender -- but not for a keyboard user, whose pointer
        // may be resting anywhere.
        leaveMargin: keyboard ? void 0 : 120,
        onClose: /* @__PURE__ */ __name(() => {
          open = null;
          finish(false);
        }, "onClose")
      });
      open = handle;
      handle.reposition();
      body.okButton.addEventListener("click", () => {
        finish(true);
        handle.close("chosen");
      });
      body.cancelButton.addEventListener("click", () => {
        finish(false);
        handle.close("chosen");
      });
      body.addEventListener("keydown", (ev) => {
        if (confirmKey(ev.key) === "confirm" && document.activeElement !== body.cancelButton) {
          ev.preventDefault();
          body.okButton.click();
        }
      });
      body.okButton.focus({ preventScroll: true });
    });
  }
  __name(confirmDialog, "confirmDialog");
  var HdPopup = class extends HdElement {
    static {
      __name(this, "HdPopup");
    }
    static get observedAttributes() {
      return ["heading"];
    }
    head;
    body;
    build() {
      const content = [...this.childNodes];
      this.setAttribute("role", "dialog");
      this.head = h("div", { class: "hd-popup__head" });
      this.body = h("div", { class: "hd-popup__body" });
      this.body.append(...content);
      this.append(this.head, this.body);
    }
    render() {
      this.head.textContent = this.str("heading");
      this.head.hidden = !this.str("heading");
      this.setAttribute("aria-label", this.str("heading") || "Properties");
    }
  };
  function openPopup(content, opts = {}) {
    const pop = document.createElement("hd-popup");
    if (opts.title) pop.setAttribute("heading", opts.title);
    pop.append(...Array.isArray(content) ? content : [content]);
    const focused = document.activeElement;
    const handle = openFloating(pop, { at: opts.at ?? lastPointer(), restoreFocus: focused, leaveMargin: 160, onClose: /* @__PURE__ */ __name(() => opts.onClose?.(), "onClose") });
    handle.reposition();
    const first = pop.querySelector("button, input, [tabindex='0'], hd-number, hd-text, hd-enum");
    first?.focus();
    return handle;
  }
  __name(openPopup, "openPopup");
  define("hd-confirm", HdConfirm);
  define("hd-popup", HdPopup);

  // ui/kit/src/core/pure/fuzzy.ts
  function words(q) {
    return q.toLocaleLowerCase().split(/\s+/).filter(Boolean);
  }
  __name(words, "words");
  function scoreItem(item, query) {
    const ws = words(query);
    const label = item.label.toLocaleLowerCase();
    if (item.hidden && !query.trimStart().startsWith(".")) return null;
    if (ws.length === 0) return { score: 0, ranges: [] };
    const rest = `${(item.path ?? "").toLocaleLowerCase()} ${(item.keywords ?? "").toLocaleLowerCase()}`;
    let score = 0;
    const ranges = [];
    for (const w of ws) {
      const at = label.indexOf(w);
      if (at >= 0) {
        ranges.push([at, at + w.length]);
        const wordStart = at === 0 || /[\s_\-/>.]/.test(label[at - 1] ?? "");
        score += at === 0 ? 0 : wordStart ? 1 : 3;
        continue;
      }
      if (rest.includes(w)) {
        score += 6;
        continue;
      }
      return null;
    }
    ranges.sort((a, b) => a[0] - b[0]);
    return { score: score + label.length / 1e3, ranges };
  }
  __name(scoreItem, "scoreItem");
  function search(items, query) {
    const out = [];
    items.forEach((item, index) => {
      const s = scoreItem(item, query);
      if (s) out.push({ item, index, score: s.score, ranges: s.ranges });
    });
    if (words(query).length === 0) return out;
    return out.sort((a, b) => a.score - b.score || a.index - b.index);
  }
  __name(search, "search");

  // ui/kit/src/core/pure/listbox.ts
  function selectable(items, i) {
    const it = items[i];
    return !!it && !it.disabled && !it.inert;
  }
  __name(selectable, "selectable");
  function navigate(items, from, key, opts = {}) {
    const n = items.length;
    if (n === 0) return -1;
    const firstSel = /* @__PURE__ */ __name(() => {
      for (let i = 0; i < n; i += 1) if (selectable(items, i)) return i;
      return -1;
    }, "firstSel");
    const lastSel = /* @__PURE__ */ __name(() => {
      for (let i = n - 1; i >= 0; i -= 1) if (selectable(items, i)) return i;
      return -1;
    }, "lastSel");
    switch (key) {
      case "first":
        return firstSel();
      case "last":
        return lastSel();
      case "next":
      case "prev": {
        const dir = key === "next" ? 1 : -1;
        if (from < 0) return dir > 0 ? firstSel() : lastSel();
        for (let step = 1; step <= n; step += 1) {
          let i = from + dir * step;
          if (i < 0 || i >= n) {
            if (!opts.wrap) return from;
            i = (i + n * 2) % n;
          }
          if (selectable(items, i)) return i;
        }
        return from;
      }
      case "pageDown":
      case "pageUp": {
        const dir = key === "pageDown" ? 1 : -1;
        const page = Math.max(1, opts.page ?? 10);
        let target = Math.max(0, Math.min(n - 1, (from < 0 ? 0 : from) + dir * page));
        while (target >= 0 && target < n && !selectable(items, target)) target -= dir;
        if (target < 0 || target >= n) return dir > 0 ? lastSel() : firstSel();
        return target;
      }
    }
  }
  __name(navigate, "navigate");
  function typeahead(labels, items, from, typed) {
    const q = typed.toLocaleLowerCase();
    if (!q) return from;
    const n = labels.length;
    const repeated = q.length > 1 && [...q].every((c) => c === q[0]);
    const needle = repeated ? q[0] : q;
    const start = repeated || q.length === 1 ? from + 1 : Math.max(0, from);
    for (let k = 0; k < n; k += 1) {
      const i = (start + k + n) % n;
      if (selectable(items, i) && (labels[i] ?? "").toLocaleLowerCase().startsWith(needle)) return i;
    }
    return from;
  }
  __name(typeahead, "typeahead");
  function navKeyFor(key, orientation = "vertical") {
    const nextKey = orientation === "vertical" ? "ArrowDown" : "ArrowRight";
    const prevKey = orientation === "vertical" ? "ArrowUp" : "ArrowLeft";
    if (key === nextKey) return "next";
    if (key === prevKey) return "prev";
    if (key === "Home") return "first";
    if (key === "End") return "last";
    if (key === "PageDown") return "pageDown";
    if (key === "PageUp") return "pageUp";
    return null;
  }
  __name(navKeyFor, "navKeyFor");

  // ui/kit/src/choice/controller.ts
  function cycleOption(options, current4, deltaY) {
    const at = options.findIndex((o) => o.value === current4);
    const next = navigate(options, at, deltaY > 0 ? "next" : "prev");
    return next >= 0 ? options[next].value : current4;
  }
  __name(cycleOption, "cycleOption");
  function dropdownKey(options, open2, active, key, typed = "") {
    if (!open2) {
      if (key === "Enter" || key === " " || key === "ArrowDown" || key === "ArrowUp" || key === "F4") return { kind: "open" };
      return null;
    }
    if (key === "Escape" || key === "Tab") return { kind: "close" };
    if (key === "Enter" || key === " ") return active >= 0 && selectable(options, active) ? { kind: "choose", index: active } : { kind: "close" };
    const nav = navKeyFor(key);
    if (nav) return { kind: "move", index: navigate(options, active, nav, { page: 8 }) };
    if (key.length === 1) {
      const i = typeahead(options.map((o) => o.label), options, active, typed + key);
      return { kind: "move", index: i };
    }
    return null;
  }
  __name(dropdownKey, "dropdownKey");
  function radioKey(options, current4, key) {
    const at = options.findIndex((o) => o.value === current4);
    let i;
    if (key === "ArrowRight" || key === "ArrowDown") i = navigate(options, at, "next", { wrap: true });
    else if (key === "ArrowLeft" || key === "ArrowUp") i = navigate(options, at, "prev", { wrap: true });
    else if (key === "Home") i = navigate(options, at, "first");
    else if (key === "End") i = navigate(options, at, "last");
    else return null;
    return i >= 0 ? options[i].value : null;
  }
  __name(radioKey, "radioKey");
  var Combobox = class {
    constructor(items) {
      this.items = items;
      this.setQuery("");
    }
    static {
      __name(this, "Combobox");
    }
    query = "";
    active = -1;
    results = [];
    setQuery(q) {
      this.query = q;
      this.results = search(this.items, q).filter((m) => !m.item.inert);
      this.active = navigate(this.results.map((m) => m.item), -1, "first");
    }
    matches() {
      return this.results;
    }
    /** A key in the search field. Returns the chosen item, "close", or null (handled or
     *  not ours). */
    key(key) {
      const rows = this.results.map((m) => m.item);
      if (key === "Escape") return "close";
      if (key === "Enter") {
        const m = this.results[this.active];
        return m && selectable(rows, this.active) ? { choose: m.item } : null;
      }
      const nav = key === "ArrowDown" ? "next" : key === "ArrowUp" ? "prev" : key === "PageDown" ? "pageDown" : key === "PageUp" ? "pageUp" : null;
      if (nav) {
        this.active = navigate(rows, this.active, nav, { page: 8 });
        return "moved";
      }
      return null;
    }
    /** Point at a row (hover). */
    hover(i) {
      if (selectable(this.results.map((m) => m.item), i)) this.active = i;
    }
  };

  // ui/kit/src/button/element.ts
  var VARIANTS = /* @__PURE__ */ new Set(["primary", "ghost", "danger"]);
  var HdButton = class extends HdElement {
    static {
      __name(this, "HdButton");
    }
    static get observedAttributes() {
      return ["variant", "icon", "disabled", "loading", "tooltip"];
    }
    button;
    iconEl;
    confirmed = false;
    build() {
      const content = takeChildren(this);
      this.iconEl = h("span", { class: "hd-icon", "aria-hidden": "true" });
      this.button = h("button", { type: "button", class: "btn" }, this.iconEl);
      const label = h("span", { class: "hd-btn__label" });
      label.append(...content);
      this.button.append(label);
      this.append(this.button);
      this.addEventListener(
        "click",
        (ev) => {
          const question = this.getAttribute("confirm");
          if (!question || this.confirmed) {
            this.confirmed = false;
            return;
          }
          ev.stopImmediatePropagation();
          ev.preventDefault();
          void confirmDialog({ title: question, confirm: this.getAttribute("confirm-label") || ownText(label) || "OK", danger: this.getAttribute("variant") === "danger", restoreFocus: this.button }).then((ok) => {
            if (!ok) return;
            this.confirmed = true;
            this.button.click();
          });
        },
        true
      );
    }
    render() {
      const variant = this.str("variant");
      const iconOnly = !this.button.querySelector(".hd-btn__label")?.textContent?.trim();
      this.button.className = ["btn", VARIANTS.has(variant) ? variant : "", iconOnly && this.hasAttribute("icon") ? "icon" : ""].filter(Boolean).join(" ");
      this.iconEl.textContent = this.str("icon");
      this.iconEl.hidden = !this.hasAttribute("icon");
      this.button.disabled = this.flag("disabled") || this.flag("loading");
      this.button.toggleAttribute("aria-busy", this.flag("loading"));
      if (iconOnly) this.button.setAttribute("aria-label", this.str("tooltip") || this.str("icon"));
      else this.button.removeAttribute("aria-label");
    }
    focus(options) {
      this.button.focus(options);
    }
    click() {
      this.button.click();
    }
  };
  var HdToggle = class extends HdElement {
    static {
      __name(this, "HdToggle");
    }
    static get observedAttributes() {
      return ["pressed", "icon", "disabled", "loading", "wired"];
    }
    button;
    iconEl;
    build() {
      this.upgradeProperty("pressed");
      const content = takeChildren(this);
      this.iconEl = h("span", { class: "hd-icon", "aria-hidden": "true" });
      const label = h("span", { class: "hd-btn__label" });
      label.append(...content);
      this.button = h("button", { type: "button", class: "btn hd-toggle" }, this.iconEl, label);
      this.append(this.button);
      this.button.addEventListener("click", () => {
        if (this.locked) return;
        this.pressed = !this.pressed;
        this.emit("input");
        this.emit("change");
      });
    }
    get pressed() {
      return this.flag("pressed");
    }
    set pressed(on) {
      this.setFlag("pressed", on);
    }
    get value() {
      return this.pressed;
    }
    set value(on) {
      this.pressed = on;
    }
    render() {
      this.button.setAttribute("aria-pressed", String(this.pressed));
      this.iconEl.textContent = this.str("icon");
      this.iconEl.hidden = !this.hasAttribute("icon");
      const iconOnly = !this.button.querySelector(".hd-btn__label")?.textContent?.trim();
      this.button.classList.toggle("icon", iconOnly);
      if (iconOnly) this.button.setAttribute("aria-label", this.str("tooltip") || this.str("icon"));
      this.button.disabled = this.flag("disabled") || this.flag("loading");
      this.button.toggleAttribute("aria-readonly", this.flag("wired"));
    }
    focus(options) {
      this.button.focus(options);
    }
  };
  var HdCheckbox = class extends HdElement {
    static {
      __name(this, "HdCheckbox");
    }
    static get observedAttributes() {
      return ["checked", "label", "disabled", "wired", "invalid", "switch", "loading"];
    }
    input;
    labelEl;
    build() {
      this.upgradeProperty("checked");
      const text = this.str("label") || ownText(this);
      takeChildren(this);
      this.input = h("input", { type: "checkbox", class: "hd-check__box" });
      this.labelEl = h("span", { class: "hd-check__label", text });
      this.append(h("label", { class: "hd-check" }, this.input, this.labelEl));
      this.input.addEventListener("change", (ev) => {
        ev.stopPropagation();
        if (this.locked) {
          this.input.checked = this.checked;
          return;
        }
        this.checked = this.input.checked;
        this.emit("change");
      });
      this.input.addEventListener("input", (ev) => {
        ev.stopPropagation();
        if (!this.locked) this.emit("input");
      });
      this.input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" && !ev.ctrlKey && !ev.altKey) {
          ev.preventDefault();
          if (!this.locked) this.input.click();
        }
      });
    }
    get checked() {
      return this.flag("checked");
    }
    set checked(on) {
      this.setFlag("checked", on);
    }
    get value() {
      return this.checked;
    }
    set value(on) {
      this.checked = on;
    }
    render() {
      this.input.checked = this.checked;
      this.input.disabled = this.flag("disabled") || this.flag("loading");
      this.input.classList.toggle("toggle", this.flag("switch"));
      this.input.classList.toggle("on", this.flag("switch") && this.checked);
      this.input.setAttribute("role", this.flag("switch") ? "switch" : "checkbox");
      this.input.toggleAttribute("aria-readonly", this.flag("wired"));
      this.input.setAttribute("aria-invalid", String(this.hasAttribute("invalid")));
      if (this.hasAttribute("label")) this.labelEl.textContent = this.str("label");
      this.labelEl.hidden = !this.labelEl.textContent;
    }
    focus(options) {
      this.input.focus(options);
    }
  };
  var HdRadioRow = class extends HdElement {
    static {
      __name(this, "HdRadioRow");
    }
    static get observedAttributes() {
      return ["value", "label", "disabled", "wired", "loading"];
    }
    options = [];
    group;
    buttons = [];
    build() {
      this.upgradeProperty("value");
      this.options = [...this.querySelectorAll("option")].map((o) => ({ value: o.value, label: ownText(o), disabled: o.disabled, icon: o.dataset.icon }));
      takeChildren(this);
      this.group = h("div", { class: "hd-radio", role: "radiogroup" });
      const label = this.str("label");
      if (label) {
        const id = uid("hd-radio");
        this.append(h("span", { class: "hd-field__label", id, text: label }));
        this.group.setAttribute("aria-labelledby", id);
      }
      this.append(this.group);
      this.buttons = this.options.map((o) => {
        const b = h("button", { type: "button", class: "hd-radio__opt", role: "radio", "data-value": o.value, disabled: o.disabled }, o.icon ? h("span", { class: "hd-icon", "aria-hidden": "true", text: o.icon }) : null, h("span", { text: o.label }));
        b.addEventListener("click", () => this.choose(o.value));
        this.group.append(b);
        return b;
      });
      this.group.addEventListener("keydown", (ev) => {
        if (this.locked) return;
        const next = radioKey(this.options, this.value, ev.key);
        if (next === null) return;
        ev.preventDefault();
        this.choose(next);
        this.buttons.find((b) => b.dataset.value === next)?.focus();
      });
    }
    choose(v) {
      if (this.locked || v === this.value) return;
      this.value = v;
      this.emit("input");
      this.emit("change");
    }
    get value() {
      return this.str("value", this.options[0]?.value ?? "");
    }
    set value(v) {
      this.setAttribute("value", v);
    }
    render() {
      const v = this.value;
      const disabled = this.flag("disabled") || this.flag("loading");
      for (const b of this.buttons) {
        const on = b.dataset.value === v;
        b.setAttribute("aria-checked", String(on));
        b.tabIndex = on ? 0 : -1;
        const opt = this.options.find((o) => o.value === b.dataset.value);
        b.disabled = disabled || !!opt?.disabled;
      }
      this.group.toggleAttribute("aria-readonly", this.flag("wired"));
    }
    focus(options) {
      (this.buttons.find((b) => b.tabIndex === 0) ?? this.buttons[0])?.focus(options);
    }
  };
  define("hd-button", HdButton);
  define("hd-toggle", HdToggle);
  define("hd-checkbox", HdCheckbox);
  define("hd-radio-row", HdRadioRow);

  // ui/kit/src/text/controller.ts
  var EditSession = class {
    static {
      __name(this, "EditSession");
    }
    phase = "idle";
    original = "";
    draft = "";
    begin(current4, seed) {
      this.phase = "editing";
      this.original = current4;
      this.draft = seed ?? current4;
      return { text: this.draft, selectAll: seed === void 0 };
    }
    input(text) {
      if (this.phase === "editing") this.draft = text;
    }
    /** Return, Tab or a click outside. The caller validates `value`; the session ends. */
    confirm() {
      const value = this.draft;
      const changed = this.phase === "editing" && value !== this.original;
      this.phase = "idle";
      return { value, changed };
    }
    /** Esc or RMB: the original comes back. */
    cancel() {
      this.phase = "idle";
      this.draft = this.original;
      return this.original;
    }
    get editing() {
      return this.phase === "editing";
    }
  };
  function editKeyAction(key, mods2) {
    if (mods2.composing) return null;
    if (key === "Enter") return "confirm";
    if (key === "Escape") return "cancel";
    if (key === "Tab") return mods2.shift ? "prev" : "next";
    if (mods2.ctrl && key === "Backspace") return "delete-word-before";
    if (mods2.ctrl && key === "Delete") return "delete-word-after";
    return null;
  }
  __name(editKeyAction, "editKeyAction");
  function wordChar(ch) {
    return !!ch && /[\p{L}\p{N}_]/u.test(ch);
  }
  __name(wordChar, "wordChar");
  function deleteWordBefore(text, start, end = start) {
    if (end > start) return { text: text.slice(0, start) + text.slice(end), caret: start };
    let i = start;
    while (i > 0 && /\s/.test(text[i - 1])) i -= 1;
    if (i > 0 && wordChar(text[i - 1])) {
      while (i > 0 && wordChar(text[i - 1])) i -= 1;
    } else {
      while (i > 0 && !wordChar(text[i - 1]) && !/\s/.test(text[i - 1])) i -= 1;
    }
    return { text: text.slice(0, i) + text.slice(start), caret: i };
  }
  __name(deleteWordBefore, "deleteWordBefore");
  function deleteWordAfter(text, start, end = start) {
    if (end > start) return { text: text.slice(0, start) + text.slice(end), caret: start };
    let i = start;
    if (i < text.length && wordChar(text[i])) {
      while (i < text.length && wordChar(text[i])) i += 1;
    } else {
      while (i < text.length && !wordChar(text[i]) && !/\s/.test(text[i])) i += 1;
    }
    while (i < text.length && /\s/.test(text[i])) i += 1;
    return { text: text.slice(0, start) + text.slice(i), caret: start };
  }
  __name(deleteWordAfter, "deleteWordAfter");
  function nextFieldIndex(count, current4, dir) {
    if (count <= 1 || current4 < 0) return -1;
    return (current4 + dir + count) % count;
  }
  __name(nextFieldIndex, "nextFieldIndex");
  function normalisePaste(text) {
    return text.replace(/\r\n?/g, "\n").replace(/^\n+|\n+$/g, "").replace(/\n/g, " ");
  }
  __name(normalisePaste, "normalisePaste");

  // ui/kit/src/core/dev.ts
  function isDevMode() {
    return document.documentElement.classList.contains("hd-dev");
  }
  __name(isDevMode, "isDevMode");
  function setDevMode(on) {
    document.documentElement.classList.toggle("hd-dev", on);
  }
  __name(setDevMode, "setDevMode");

  // ui/kit/src/core/fields.ts
  var EDITABLE = "hd-number, hd-text";
  function adjacentField(from, dir) {
    const scope = from.closest(".hd-float, hd-panel, .k-panel__body") ?? document.body;
    const all = [...scope.querySelectorAll(EDITABLE)].filter((f) => f === from || f.canEdit && f.offsetParent !== null);
    const i = nextFieldIndex(all.length, all.indexOf(from), dir);
    return i < 0 ? null : all[i] ?? null;
  }
  __name(adjacentField, "adjacentField");
  var FIELD_MENU_EVENT = "hd-field-menu";
  function fieldMenu(opts) {
    const clip = navigator.clipboard;
    const items = [
      { label: "&Reset to Default Value", shortcut: "Backspace", command: "ui.reset_default", action: opts.reset },
      { separator: true },
      {
        label: "&Copy Value",
        shortcut: "Ctrl+C",
        command: "ui.copy_value",
        action: /* @__PURE__ */ __name(() => {
          const t = opts.copyText();
          if (t !== null && clip) void clip.writeText(t).catch(() => void 0);
        }, "action")
      },
      {
        label: "&Paste Value",
        shortcut: "Ctrl+V",
        command: "ui.paste_value",
        disabled: !clip || typeof clip.readText !== "function",
        action: /* @__PURE__ */ __name(() => {
          void clip?.readText().then((t) => opts.paste(t)).catch(() => void 0);
        }, "action")
      }
    ];
    if (isDevMode() && opts.devId) {
      const id = opts.devId;
      items.push({ separator: true }, { label: "Copy &Id", command: "ui.copy_id", description: id, action: /* @__PURE__ */ __name(() => void clip?.writeText(id).catch(() => void 0), "action") });
    }
    if (opts.host) {
      const detail = { items, field: opts.host };
      try {
        opts.host.dispatchEvent(new CustomEvent(FIELD_MENU_EVENT, { bubbles: true, detail }));
      } catch {
      }
    }
    return items;
  }
  __name(fieldMenu, "fieldMenu");

  // ui/kit/src/core/hover.ts
  var hovered = null;
  var pendingCopy = null;
  var installed2 = false;
  function registerField(el) {
    install2();
    el.dataset.hdField = "";
    el.addEventListener("pointerenter", () => {
      hovered = el;
    });
    el.addEventListener("pointerleave", () => {
      if (hovered === el) hovered = null;
    });
  }
  __name(registerField, "registerField");
  function targetField() {
    const active = document.activeElement;
    const focused = active ? active.closest("[data-hd-field]") : null;
    if (focused) return focused.editingNow ? null : focused;
    if (editingText()) return null;
    if (hovered && hovered.isConnected && !hovered.editingNow) return hovered;
    return null;
  }
  __name(targetField, "targetField");
  function selectionOutsideFields() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) return false;
    const node = sel.anchorNode;
    const el = node instanceof Element ? node : node?.parentElement;
    return !el?.closest("[data-hd-field]");
  }
  __name(selectionOutsideFields, "selectionOutsideFields");
  function install2() {
    if (installed2) return;
    installed2 = true;
    document.addEventListener("keydown", (ev) => {
      if (ev.defaultPrevented || ev.altKey) return;
      const field = targetField();
      if (!field) return;
      const ctrl = ev.ctrlKey || ev.metaKey;
      if (ctrl && !ev.shiftKey && (ev.key === "c" || ev.key === "C" || ev.code === "KeyC")) {
        if (selectionOutsideFields()) return;
        const value = field.copyValue();
        if (value === null) return;
        pendingCopy = value;
        let copied = false;
        try {
          copied = document.execCommand("copy");
        } catch {
          copied = false;
        }
        if (!copied && navigator.clipboard) void navigator.clipboard.writeText(value).catch(() => void 0);
        pendingCopy = null;
        ev.preventDefault();
        return;
      }
      if (ctrl || ev.shiftKey) return;
      if (ev.key === "Backspace" || ev.key === "Delete") {
        if (field.resetToDefault()) ev.preventDefault();
        return;
      }
      if (ev.key === "-" && field.negate) {
        if (field.negate()) ev.preventDefault();
      }
    });
    document.addEventListener("copy", (ev) => {
      if (pendingCopy === null || !ev.clipboardData) return;
      ev.clipboardData.setData("text/plain", pendingCopy);
      ev.preventDefault();
    });
    document.addEventListener("paste", (ev) => {
      if (ev.defaultPrevented) return;
      const field = targetField();
      if (!field || !ev.clipboardData) return;
      const text = ev.clipboardData.getData("text/plain");
      field.pasteValue(text);
      ev.preventDefault();
    });
  }
  __name(install2, "install");

  // ui/kit/src/core/notice.ts
  var NOTICE_MS = 4e3;
  var current = null;
  var timer;
  function dismiss() {
    current?.close("api");
  }
  __name(dismiss, "dismiss");
  var onKey = /* @__PURE__ */ __name((ev) => {
    if (ev.key !== "Escape") dismiss();
  }, "onKey");
  function refuse(anchor, text) {
    dismiss();
    const report = document.createElement("hd-report");
    report.setAttribute("severity", "warning");
    report.setAttribute("text", text);
    const box = h("div", { class: "hd-notice" }, report);
    const handle = openFloating(box, {
      anchor,
      side: "below",
      passive: true,
      onClose: /* @__PURE__ */ __name(() => {
        if (current !== handle) return;
        current = null;
        window.clearTimeout(timer);
        window.removeEventListener("pointerdown", dismiss, true);
        window.removeEventListener("keydown", onKey, true);
      }, "onClose")
    });
    current = handle;
    handle.reposition();
    timer = window.setTimeout(dismiss, NOTICE_MS);
    window.addEventListener("pointerdown", dismiss, true);
    window.addEventListener("keydown", onKey, true);
    return handle;
  }
  __name(refuse, "refuse");
  function lockedReason(el) {
    const on = /* @__PURE__ */ __name((name) => {
      const v = el.getAttribute(name);
      return v !== null && v !== "false";
    }, "on");
    const label = el.getAttribute("label") || "This field";
    if (on("disabled")) return `${label} is disabled`;
    if (on("wired")) return `${label} is wired: its value comes from a link`;
    if (on("loading")) return `${label} is still loading`;
    return `${label} cannot be changed`;
  }
  __name(lockedReason, "lockedReason");

  // ui/kit/src/core/pure/rmb.ts
  var RightClickSwallow = class {
    static {
      __name(this, "RightClickSwallow");
    }
    armed = false;
    held = false;
    /** Is a contextmenu still to be swallowed? */
    get active() {
      return this.armed;
    }
    /** The right button went down and cancelled something. */
    arm() {
      this.armed = true;
      this.held = true;
    }
    /** The `buttons` mask of any pointer move or button change (`pointermove`, `pointerup`). */
    buttons(mask) {
      if (!this.armed) return;
      const right = (mask & 2) !== 0;
      if (this.held && !right) this.held = false;
      else if (!this.held && right) this.armed = false;
    }
    /** A `pointerdown`: every button was up, so the cancelling click is over. */
    press() {
      this.armed = false;
      this.held = false;
    }
    /** A key went down. Once the button is released, a key starts something new (Shift+F10
     *  and the Menu key raise a contextmenu of their own); while it is held it changes
     *  nothing, since the release's contextmenu is still to come. */
    key() {
      if (this.armed && !this.held) this.armed = false;
    }
    /** A `contextmenu` arrived. True when it is the cancelling click's own: swallow it. */
    contextmenu() {
      if (!this.armed) return false;
      this.armed = false;
      this.held = false;
      return true;
    }
  };

  // ui/kit/src/core/rmb.ts
  var swallow = new RightClickSwallow();
  var listening = false;
  var onDown = /* @__PURE__ */ __name(() => {
    swallow.press();
    settle();
  }, "onDown");
  var onButtons = /* @__PURE__ */ __name((ev) => {
    swallow.buttons(ev.buttons);
    settle();
  }, "onButtons");
  var onKey2 = /* @__PURE__ */ __name(() => {
    swallow.key();
    settle();
  }, "onKey");
  var onContext = /* @__PURE__ */ __name((ev) => {
    if (swallow.contextmenu()) {
      ev.preventDefault();
      ev.stopImmediatePropagation();
    }
    settle();
  }, "onContext");
  function settle() {
    if (swallow.active || !listening) return;
    listening = false;
    window.removeEventListener("pointerdown", onDown, true);
    window.removeEventListener("pointermove", onButtons, true);
    window.removeEventListener("pointerup", onButtons, true);
    window.removeEventListener("keydown", onKey2, true);
    window.removeEventListener("contextmenu", onContext, true);
  }
  __name(settle, "settle");
  function swallowRightClick() {
    swallow.arm();
    if (listening) return;
    listening = true;
    window.addEventListener("pointerdown", onDown, true);
    window.addEventListener("pointermove", onButtons, true);
    window.addEventListener("pointerup", onButtons, true);
    window.addEventListener("keydown", onKey2, true);
    window.addEventListener("contextmenu", onContext, true);
  }
  __name(swallowRightClick, "swallowRightClick");

  // ui/kit/src/core/pure/own.ts
  function own(table, key) {
    return Object.hasOwn(table, key) ? table[key] : void 0;
  }
  __name(own, "own");

  // ui/kit/src/core/pure/keys.ts
  var MODIFIER_KEYS = /* @__PURE__ */ new Set(["Control", "Shift", "Alt", "Meta", "AltGraph", "OS"]);
  var KEY_ALIASES = {
    " ": "Space",
    spacebar: "Space",
    space: "Space",
    esc: "Escape",
    escape: "Escape",
    return: "Enter",
    enter: "Enter",
    del: "Delete",
    delete: "Delete",
    backspace: "Backspace",
    tab: "Tab",
    up: "ArrowUp",
    down: "ArrowDown",
    left: "ArrowLeft",
    right: "ArrowRight",
    arrowup: "ArrowUp",
    arrowdown: "ArrowDown",
    arrowleft: "ArrowLeft",
    arrowright: "ArrowRight",
    pageup: "PageUp",
    pagedown: "PageDown",
    pgup: "PageUp",
    pgdn: "PageDown",
    home: "Home",
    end: "End",
    insert: "Insert",
    plus: "+",
    minus: "-"
  };
  var CODE_KEYS = {
    Equal: "=",
    Minus: "-",
    Slash: "/",
    Period: ".",
    Comma: ",",
    BracketLeft: "[",
    BracketRight: "]",
    Semicolon: ";",
    Quote: "'",
    Backquote: "`",
    Backslash: "\\",
    IntlBackslash: "\\",
    NumpadAdd: "=",
    NumpadSubtract: "-"
  };
  var SHIFTED = {
    "+": "=",
    _: "-",
    "?": "/",
    ">": ".",
    "<": ",",
    "{": "[",
    "}": "]",
    ":": ";",
    '"': "'",
    "~": "`",
    "|": "\\"
  };
  var KEY_DISPLAY = {
    ArrowUp: "Up",
    ArrowDown: "Down",
    ArrowLeft: "Left",
    ArrowRight: "Right",
    Escape: "Esc",
    PageUp: "PgUp",
    PageDown: "PgDn",
    Delete: "Del"
  };
  function normaliseKey(raw) {
    if (raw.length === 1) return raw === " " ? "Space" : own(SHIFTED, raw) ?? raw.toUpperCase();
    const alias = own(KEY_ALIASES, raw.toLowerCase());
    if (alias) return alias.length === 1 ? normaliseKey(alias) : alias;
    if (/^f\d{1,2}$/i.test(raw)) return raw.toUpperCase();
    return raw;
  }
  __name(normaliseKey, "normaliseKey");
  function parseChord(text) {
    const trimmed = text.trim();
    if (!trimmed) return null;
    const parts = trimmed === "+" ? ["+"] : trimmed.replace(/\+\+$/, "+Plus").split(/\s*\+\s*|\s+/).filter(Boolean);
    const chord = { ctrl: false, shift: false, alt: false, meta: false, key: "" };
    for (const part of parts) {
      const lower = part.toLowerCase();
      if (lower === "ctrl" || lower === "control" || lower === "cmd") chord.ctrl = true;
      else if (lower === "shift") chord.shift = true;
      else if (lower === "alt" || lower === "option") chord.alt = true;
      else if (lower === "meta" || lower === "win" || lower === "super") chord.meta = true;
      else if (chord.key) return null;
      else {
        chord.key = normaliseKey(part);
        const bare = part.length === 1 ? part : own(KEY_ALIASES, lower) ?? "";
        if (bare.length === 1 && own(SHIFTED, bare)) chord.shift = true;
      }
    }
    return chord.key ? chord : null;
  }
  __name(parseChord, "parseChord");
  function formatChord(chord) {
    const parts = [];
    if (chord.ctrl) parts.push("Ctrl");
    if (chord.shift) parts.push("Shift");
    if (chord.alt) parts.push("Alt");
    if (chord.meta) parts.push("Meta");
    parts.push(chord.key);
    return parts.join("+");
  }
  __name(formatChord, "formatChord");
  function displayChord(chordOrText) {
    const chord = typeof chordOrText === "string" ? parseChord(chordOrText) : chordOrText;
    if (!chord) return typeof chordOrText === "string" ? chordOrText : "";
    const parts = [];
    if (chord.ctrl) parts.push("Ctrl");
    if (chord.shift) parts.push("Shift");
    if (chord.alt) parts.push("Alt");
    if (chord.meta) parts.push("Meta");
    parts.push(own(KEY_DISPLAY, chord.key) ?? chord.key);
    return parts.join(" ");
  }
  __name(displayChord, "displayChord");
  function chordFromKey(ev) {
    if (MODIFIER_KEYS.has(ev.key)) return null;
    const code = ev.code ?? "";
    const letter = /^Key([A-Z])$/.exec(code);
    const digit = /^Digit(\d)$/.exec(code);
    let key;
    if (letter) key = letter[1];
    else if (digit) key = digit[1];
    else if (own(CODE_KEYS, code)) key = own(CODE_KEYS, code);
    else key = normaliseKey(ev.key);
    return {
      ctrl: !!ev.ctrlKey,
      shift: !!ev.shiftKey,
      alt: !!ev.altKey,
      meta: !!ev.metaKey,
      key
    };
  }
  __name(chordFromKey, "chordFromKey");
  function matchesChord(ev, chord) {
    const want = typeof chord === "string" ? parseChord(chord) : chord;
    const got = chordFromKey(ev);
    if (!want || !got) return false;
    return want.key === got.key && want.ctrl === got.ctrl && want.shift === got.shift && want.alt === got.alt && want.meta === got.meta;
  }
  __name(matchesChord, "matchesChord");
  function parseAccelerator(raw, taken = /* @__PURE__ */ new Set()) {
    let label = "";
    let marked = -1;
    for (let i = 0; i < raw.length; i += 1) {
      const ch = raw[i];
      if (ch === "&") {
        if (raw[i + 1] === "&") {
          label += "&";
          i += 1;
          continue;
        }
        if (marked === -1 && i + 1 < raw.length) marked = label.length;
        continue;
      }
      label += ch;
    }
    if (marked >= 0) {
      const accel = label[marked].toLowerCase();
      return { label, accel, index: marked };
    }
    for (let i = 0; i < label.length; i += 1) {
      const ch = label[i].toLowerCase();
      if (/[a-z0-9]/.test(ch) && !taken.has(ch)) return { label, accel: ch, index: i };
    }
    return { label, accel: "", index: -1 };
  }
  __name(parseAccelerator, "parseAccelerator");
  function assignAccelerators(labels) {
    const taken = /* @__PURE__ */ new Set();
    const out = labels.map(() => null);
    labels.forEach((raw, i) => {
      if (raw === null || !/&(?!&)/.test(raw.replace(/&&/g, ""))) return;
      const parsed = parseAccelerator(raw);
      if (parsed.accel && !taken.has(parsed.accel)) taken.add(parsed.accel);
      out[i] = parsed;
    });
    labels.forEach((raw, i) => {
      if (raw === null || out[i]) return;
      const parsed = parseAccelerator(raw, taken);
      if (parsed.accel) taken.add(parsed.accel);
      out[i] = parsed;
    });
    return out;
  }
  __name(assignAccelerators, "assignAccelerators");

  // ui/kit/src/menu/controller.ts
  function buildMenu(specs) {
    const labels = specs.map((s) => s.separator || s.heading ? null : s.label ?? "");
    const accels = assignAccelerators(labels);
    let ordinal = 0;
    return specs.map((spec, i) => {
      const inert = !!(spec.separator || spec.heading);
      const acc = accels[i];
      const clickable = !inert && !spec.disabled;
      if (clickable) ordinal += 1;
      return {
        spec,
        label: acc ? acc.label : (spec.label ?? "").replace(/&&/g, "&").replace(/&/g, ""),
        accel: acc && !inert ? acc.accel : "",
        accelIndex: acc && !inert ? acc.index : -1,
        shortcutText: spec.shortcut ? displayChord(spec.shortcut) : "",
        ordinal: clickable ? ordinal : 0,
        hasChildren: (spec.children?.length ?? 0) > 0,
        disabled: !!spec.disabled,
        inert
      };
    });
  }
  __name(buildMenu, "buildMenu");
  function ordinalFor(key, alt) {
    if (!/^[0-9]$/.test(key)) return 0;
    const n = key === "0" ? 10 : Number(key);
    return alt ? n + 10 : n;
  }
  __name(ordinalFor, "ordinalFor");
  function menuKey(entries, active, key, mods2, submenu = false) {
    if (mods2.ctrl) return null;
    switch (key) {
      case "ArrowDown":
        return { kind: "move", index: navigate(entries, active, "next", { wrap: true }) };
      case "ArrowUp":
        return { kind: "move", index: navigate(entries, active, "prev", { wrap: true }) };
      case "Home":
        return { kind: "move", index: navigate(entries, active, "first") };
      case "End":
        return { kind: "move", index: navigate(entries, active, "last") };
      case "ArrowRight":
        return active >= 0 && entries[active]?.hasChildren && selectable(entries, active) ? { kind: "open-sub", index: active } : null;
      case "ArrowLeft":
        return submenu ? { kind: "back" } : null;
      case "Escape":
        return { kind: "close" };
      case " ":
        return { kind: "search" };
      case "Enter":
        if (active < 0 || !selectable(entries, active)) return null;
        return entries[active]?.hasChildren ? { kind: "open-sub", index: active } : { kind: "activate", index: active };
    }
    const n = ordinalFor(key, mods2.alt);
    if (n > 0) {
      const i = entries.findIndex((e) => e.ordinal === n);
      if (i < 0) return null;
      return entries[i]?.hasChildren ? { kind: "open-sub", index: i } : { kind: "activate", index: i };
    }
    if (key.length === 1 && !mods2.alt) {
      const letter = key.toLowerCase();
      const i = entries.findIndex((e) => e.accel === letter && selectable(entries, entries.indexOf(e)));
      if (i >= 0) return entries[i]?.hasChildren ? { kind: "open-sub", index: i } : { kind: "activate", index: i };
    }
    return null;
  }
  __name(menuKey, "menuKey");
  function splitAccel(entry) {
    const { label, accelIndex: i } = entry;
    if (i < 0 || i >= label.length) return [label, "", ""];
    return [label.slice(0, i), label.slice(i, i + 1), label.slice(i + 1)];
  }
  __name(splitAccel, "splitAccel");

  // ui/kit/src/search/element.ts
  function highlighted(label, ranges) {
    const out = [];
    let at = 0;
    for (const [s, e] of ranges) {
      if (s < at) continue;
      if (s > at) out.push(document.createTextNode(label.slice(at, s)));
      out.push(h("mark", { class: "hd-hit", text: label.slice(s, e) }));
      at = e;
    }
    if (at < label.length) out.push(document.createTextNode(label.slice(at)));
    return out;
  }
  __name(highlighted, "highlighted");
  function openSearch(commands, opts = {}) {
    const rows = commands.filter((c) => !c.separator && !c.heading).map((c) => ({ spec: c, value: c.command ?? c.label ?? "", label: (c.label ?? "").replace(/&/g, ""), path: c.path, keywords: c.command, disabled: c.disabled }));
    const combo = new Combobox(rows);
    const listId = uid("hd-search-list");
    const input = h("input", { type: "text", class: "input hd-search__input", placeholder: opts.placeholder ?? "Search...", spellcheck: "false", autocomplete: "off", role: "combobox", "aria-expanded": "true", "aria-controls": listId, "aria-autocomplete": "list" });
    const list = h("div", { class: "hd-search__list", role: "listbox", id: listId });
    const box = h("div", { class: "hd-search" }, input, list);
    const optionIds = [];
    const paint2 = /* @__PURE__ */ __name(() => {
      list.replaceChildren();
      optionIds.length = 0;
      const matches = combo.matches();
      if (matches.length === 0) {
        list.append(h("div", { class: "hd-search__empty", text: `Nothing matches “${combo.query}”` }));
      }
      matches.forEach((m, i) => {
        const id = `${listId}-${i}`;
        optionIds.push(id);
        const row = h(
          "div",
          { class: "hd-search__row", role: "option", id, "aria-selected": String(i === combo.active), "aria-disabled": m.item.disabled ? "true" : null },
          h("span", { class: "hd-search__path", text: m.item.path ? `${m.item.path} ▸ ` : "" }),
          h("span", { class: "hd-search__label" }, ...highlighted(m.item.label, m.ranges)),
          h("kbd", { class: "hd-menu__key", text: m.item.spec.shortcut ? displayChord(m.item.spec.shortcut) : "" })
        );
        if (m.item.spec.command) {
          row.setAttribute("tooltip", m.item.label);
          row.setAttribute("command", m.item.spec.command);
        }
        row.classList.toggle("is-active", i === combo.active);
        row.addEventListener("pointerenter", () => {
          combo.hover(i);
          mark();
        });
        row.addEventListener("click", () => run(m.item));
        list.append(row);
      });
      mark();
    }, "paint");
    const mark = /* @__PURE__ */ __name(() => {
      [...list.children].forEach((r, i) => {
        r.classList.toggle("is-active", i === combo.active);
        r.setAttribute("aria-selected", String(i === combo.active));
      });
      const id = optionIds[combo.active];
      if (id) {
        input.setAttribute("aria-activedescendant", id);
        list.children[combo.active]?.scrollIntoView?.({ block: "nearest" });
      } else input.removeAttribute("aria-activedescendant");
    }, "mark");
    const run = /* @__PURE__ */ __name((row) => {
      if (row.disabled) return;
      handle.close("chosen");
      row.spec.action?.();
      (opts.origin ?? document).dispatchEvent(new CustomEvent("hd-command", { bubbles: true, detail: { command: row.spec.command ?? "", label: row.label, item: row.spec } }));
    }, "run");
    input.addEventListener("input", () => {
      combo.setQuery(input.value);
      paint2();
    });
    input.addEventListener("keydown", (ev) => {
      if (ev.isComposing || ev.keyCode === 229) return;
      const r = combo.key(ev.key);
      if (r === null) return;
      ev.preventDefault();
      if (r === "close") handle.close("escape");
      else if (r === "moved") mark();
      else run(r.choose);
    });
    const handle = openFloating(box, { at: opts.at ?? lastPointer(), restoreFocus: opts.restoreFocus ?? document.activeElement });
    paint2();
    handle.reposition();
    input.focus({ preventScroll: true });
    return handle;
  }
  __name(openSearch, "openSearch");
  var HdSearchMenu = class extends HdElement {
    static {
      __name(this, "HdSearchMenu");
    }
    static get observedAttributes() {
      return ["hotkey"];
    }
    commands = [];
    handle = null;
    onKey = /* @__PURE__ */ __name((ev) => {
      const hotkey = this.str("hotkey");
      if (!hotkey || ev.defaultPrevented || !matchesChord(ev, hotkey)) return;
      ev.preventDefault();
      this.open();
    }, "onKey");
    build() {
      this.upgradeProperty("commands");
      this.hidden = true;
    }
    connected() {
      document.addEventListener("keydown", this.onKey);
    }
    disconnected() {
      document.removeEventListener("keydown", this.onKey);
    }
    /** Open the search -- or, when it is already open (F3 pressed in it), keep that one:
     *  a second search stacked on the first would need a second Esc. */
    open(at) {
      if (this.handle?.open) {
        this.handle.el.querySelector(".hd-search__input")?.focus({ preventScroll: true });
        return this.handle;
      }
      this.handle = openSearch(this.commands, { at, origin: this });
      return this.handle;
    }
  };
  define("hd-search-menu", HdSearchMenu);

  // ui/kit/src/menu/element.ts
  var MenuView = class _MenuView {
    constructor(specs, opts) {
      this.specs = specs;
      this.opts = opts;
      this.entries = buildMenu(specs);
      this.el = h("div", { class: "hd-menu", role: "menu", tabindex: "-1", "aria-label": opts.label ?? "Menu" });
      this.entries.forEach((e, i) => this.el.append(this.row(e, i)));
      this.el.addEventListener("keydown", (ev) => this.key(ev));
    }
    static {
      __name(this, "MenuView");
    }
    el;
    entries;
    handle;
    active = -1;
    rows = [];
    sub = null;
    subTimer;
    row(e, i) {
      if (e.spec.separator) {
        const sep = h("div", { class: "hd-menu__sep", role: "separator" });
        this.rows.push(sep);
        return sep;
      }
      if (e.spec.heading) {
        const head = h("div", { class: "hd-menu__heading", role: "presentation", text: e.label });
        this.rows.push(head);
        return head;
      }
      const [before, letter, after] = splitAccel(e);
      const label = h("span", { class: "hd-menu__label" }, before, letter ? h("span", { class: "hd-accel", text: letter }) : null, after);
      const row = h(
        "div",
        {
          class: "hd-menu__item",
          role: e.spec.checked !== void 0 ? "menuitemcheckbox" : "menuitem",
          id: uid("hd-mi"),
          "aria-disabled": e.disabled ? "true" : null,
          "aria-checked": e.spec.checked !== void 0 ? String(!!e.spec.checked) : null,
          "aria-haspopup": e.hasChildren ? "menu" : null,
          "data-command": e.spec.command ?? null
        },
        h("span", { class: "hd-menu__check", "aria-hidden": "true", text: e.spec.checked ? "✓" : "" }),
        h("span", { class: "hd-menu__icon", "aria-hidden": "true", text: e.spec.icon ?? "" }),
        label,
        e.shortcutText ? h("kbd", { class: "hd-menu__key", text: e.shortcutText }) : h("span", { class: "hd-menu__key" }),
        h("span", { class: "hd-menu__sub", "aria-hidden": "true", text: e.hasChildren ? "▸" : "" })
      );
      if (e.ordinal > 0 && e.ordinal <= 10) row.dataset.ordinal = String(e.ordinal % 10);
      if (e.spec.description || e.spec.command) {
        row.setAttribute("tooltip", e.label);
        if (e.spec.description) row.setAttribute("description", e.spec.description);
        if (e.spec.command) row.setAttribute("command", e.spec.command);
      }
      row.addEventListener("pointerenter", () => {
        this.setActive(i);
        window.clearTimeout(this.subTimer);
        if (e.hasChildren && !e.disabled) this.subTimer = window.setTimeout(() => this.openSub(i, false), 180);
        else if (this.sub) this.subTimer = window.setTimeout(() => this.closeSub(), 180);
      });
      row.addEventListener("click", (ev) => {
        ev.stopPropagation();
        if (e.disabled) return;
        if (e.hasChildren) this.openSub(i, true);
        else this.choose(i);
      });
      this.rows.push(row);
      return row;
    }
    open() {
      const o = this.opts;
      this.handle = openFloating(this.el, {
        at: o.at,
        anchor: o.anchor,
        side: o.side ?? (o.parent ? "right" : "below"),
        restoreFocus: o.restoreFocus,
        owner: o.owner,
        onClose: /* @__PURE__ */ __name(() => {
          window.clearTimeout(this.subTimer);
          o.onClose?.();
        }, "onClose")
      });
      this.el.focus({ preventScroll: true });
      return this;
    }
    setActive(i) {
      this.active = i;
      this.rows.forEach((r, k) => r.classList.toggle("is-active", k === i));
      const row = this.rows[i];
      if (row && row.id) this.el.setAttribute("aria-activedescendant", row.id);
      else this.el.removeAttribute("aria-activedescendant");
      row?.scrollIntoView?.({ block: "nearest" });
    }
    openSub(i, focus) {
      const e = this.entries[i];
      if (!e?.spec.children) return;
      if (this.sub && this.sub.specs === e.spec.children && this.sub.handle.open) {
        if (focus) this.sub.focusFirst();
        return;
      }
      this.closeSub();
      const row = this.rows[i];
      this.sub = new _MenuView(e.spec.children, { anchor: row, side: "right", parent: this, origin: this.opts.origin, restoreFocus: this.el, label: e.label, onClose: /* @__PURE__ */ __name(() => row.setAttribute("aria-expanded", "false"), "onClose") }).open();
      row.setAttribute("aria-expanded", "true");
      if (focus) this.sub.focusFirst();
      else this.el.focus({ preventScroll: true });
    }
    closeSub() {
      if (this.sub) {
        this.sub.handle.close("replaced");
        this.sub = null;
      }
    }
    focusFirst() {
      this.el.focus({ preventScroll: true });
      const first = this.entries.findIndex((e) => !e.inert && !e.disabled);
      this.setActive(first);
    }
    /** The outermost menu in this chain. */
    root() {
      let m = this;
      while (m.opts.parent) m = m.opts.parent;
      return m;
    }
    choose(i) {
      const e = this.entries[i];
      if (!e || e.disabled || e.inert) return;
      this.root().handle.close("chosen");
      e.spec.action?.();
      (this.opts.origin ?? document).dispatchEvent(new CustomEvent("hd-command", { bubbles: true, detail: { command: e.spec.command ?? "", label: e.label, item: e.spec } }));
    }
    key(ev) {
      const action = menuKey(this.entries, this.active, ev.key, { alt: ev.altKey, ctrl: ev.ctrlKey || ev.metaKey, shift: ev.shiftKey }, !!this.opts.parent);
      if (!action) {
        if (this.opts.onUnhandledKey?.(ev) || this.root().opts.onUnhandledKey?.(ev)) ev.preventDefault();
        return;
      }
      ev.preventDefault();
      ev.stopPropagation();
      switch (action.kind) {
        case "move":
          this.setActive(action.index);
          break;
        case "activate":
          this.choose(action.index);
          break;
        case "open-sub":
          this.setActive(action.index);
          this.openSub(action.index, true);
          break;
        case "back":
        case "close":
          this.handle.close("escape");
          if (this.opts.parent) this.opts.parent.el.focus({ preventScroll: true });
          break;
        case "search": {
          const flat = flatten(this.specs);
          const origin = this.opts.origin;
          const at = rectOf(this.el);
          this.root().handle.close("replaced");
          openSearch(flat, { at: { x: at.x, y: at.y }, origin, restoreFocus: this.root().opts.restoreFocus ?? null });
          break;
        }
      }
    }
  };
  function flatten(specs, path = []) {
    const out = [];
    for (const s of specs) {
      if (s.separator || s.heading) continue;
      const label = (s.label ?? "").replace(/&&/g, "\0").replace(/&/g, "").replace(/\u0000/g, "&");
      if (s.children?.length) out.push(...flatten(s.children, [...path, label]));
      else out.push({ ...s, label, path: path.join(" ▸ ") });
    }
    return out;
  }
  __name(flatten, "flatten");
  function openMenu(items, opts) {
    const view = new MenuView(items, opts).open();
    if (opts.at || !opts.anchor) view.focusFirst();
    return view;
  }
  __name(openMenu, "openMenu");
  function parseItems(host) {
    const specs = [];
    for (const child of [...host.children]) {
      const tag = child.tagName.toLowerCase();
      if (tag === "hd-menu-separator") specs.push({ separator: true });
      else if (tag === "hd-menu-heading") specs.push({ heading: true, label: ownText(child) });
      else if (tag === "hd-menu-item") {
        const nested = parseItems(child);
        const direct = [...child.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent ?? "").join("").trim();
        const checked = child.getAttribute("checked");
        specs.push({
          label: child.getAttribute("label") ?? direct,
          shortcut: child.getAttribute("shortcut") ?? void 0,
          command: child.getAttribute("command") ?? void 0,
          description: child.getAttribute("description") ?? void 0,
          icon: child.getAttribute("icon") ?? void 0,
          disabled: child.hasAttribute("disabled"),
          checked: checked === null ? void 0 : checked !== "false",
          children: nested.length ? nested : void 0
        });
      }
    }
    return specs;
  }
  __name(parseItems, "parseItems");
  var HdMenu = class extends HdElement {
    static {
      __name(this, "HdMenu");
    }
    static get observedAttributes() {
      return ["label", "context-for"];
    }
    specs = null;
    view = null;
    bound = [];
    /** The items, parsed from markup, or set from script. */
    get items() {
      return this.specs ??= parseItems(this);
    }
    set items(v) {
      this.specs = v;
    }
    build() {
      this.upgradeProperty("items");
      this.hidden = true;
      this.bind();
    }
    changed(name) {
      if (name === "context-for") this.bind();
    }
    bind() {
      const sel = this.str("context-for");
      for (const el of this.bound) {
        el.removeEventListener("contextmenu", this.onContext);
        el.removeEventListener("keydown", this.onContextKey);
      }
      this.bound = sel ? [...document.querySelectorAll(sel)] : [];
      for (const el of this.bound) {
        el.addEventListener("contextmenu", this.onContext);
        el.addEventListener("keydown", this.onContextKey);
      }
    }
    onContext = /* @__PURE__ */ __name((ev) => {
      ev.preventDefault();
      this.open({ at: { x: ev.clientX, y: ev.clientY }, restoreFocus: ev.currentTarget });
    }, "onContext");
    /** The keyboard's way to a context menu: Shift+F10 or the Menu key, at the element. */
    onContextKey = /* @__PURE__ */ __name((ev) => {
      if (!(ev.shiftKey && ev.key === "F10" || ev.key === "ContextMenu")) return;
      ev.preventDefault();
      const r = rectOf(ev.currentTarget);
      this.open({ at: { x: r.x + 8, y: r.y + r.height / 2 }, restoreFocus: ev.currentTarget });
    }, "onContextKey");
    open(opts = {}) {
      this.view?.handle.close("replaced");
      const label = this.str("label").replace(/&/g, "");
      this.view = new MenuView(this.items, { ...opts, origin: this, label }).open();
      if (opts.at || !opts.anchor) this.view.focusFirst();
      this.setAttribute("aria-expanded", "true");
      const onClose = opts.onClose;
      this.view.opts.onClose = () => {
        this.removeAttribute("aria-expanded");
        onClose?.();
      };
      return this.view;
    }
    close() {
      this.view?.handle.close("api");
      this.view = null;
    }
    get isOpen() {
      return !!this.view?.handle.open;
    }
  };
  var HdMenuPart = class extends HTMLElement {
    static {
      __name(this, "HdMenuPart");
    }
    connectedCallback() {
      this.hidden = true;
    }
  };
  var HdMenubar = class extends HdElement {
    static {
      __name(this, "HdMenubar");
    }
    menus = [];
    buttons = [];
    openIndex = -1;
    build() {
      this.setAttribute("role", "menubar");
      this.menus = [...this.querySelectorAll(":scope > hd-menu")];
      this.menus.forEach((m, i) => {
        const raw = m.getAttribute("label") ?? `Menu ${i + 1}`;
        const [entry] = buildMenu([{ label: raw }]);
        const [before, letter, after] = entry ? splitAccel(entry) : [raw, "", ""];
        const btn = h("button", { type: "button", class: "hd-menubar__btn", role: "menuitem", "aria-haspopup": "menu", tabindex: i === 0 ? "0" : "-1" }, before, letter ? h("span", { class: "hd-accel", text: letter }) : null, after);
        btn.addEventListener("click", () => this.openIndex === i ? this.closeMenu() : this.openMenu(i, true));
        btn.addEventListener("pointerenter", () => {
          if (this.openIndex >= 0 && this.openIndex !== i) this.openMenu(i, false);
        });
        btn.addEventListener("keydown", (ev) => {
          if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") {
            ev.preventDefault();
            this.focusButton(i + (ev.key === "ArrowRight" ? 1 : -1));
          } else if (ev.key === "ArrowDown" || ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.openMenu(i, true);
          }
        });
        this.buttons.push(btn);
        this.insertBefore(btn, m);
      });
    }
    focusButton(i) {
      const n = this.buttons.length;
      const k = (i % n + n) % n;
      this.buttons.forEach((b, j) => b.tabIndex = j === k ? 0 : -1);
      this.buttons[k]?.focus();
    }
    openMenu(i, focus) {
      const menu = this.menus[i];
      const btn = this.buttons[i];
      if (!menu || !btn) return;
      this.closeMenu();
      this.openIndex = i;
      btn.setAttribute("aria-expanded", "true");
      btn.classList.add("is-open");
      const view = menu.open({
        anchor: btn,
        side: "below",
        owner: this,
        restoreFocus: btn,
        onClose: /* @__PURE__ */ __name(() => {
          btn.removeAttribute("aria-expanded");
          btn.classList.remove("is-open");
          if (this.openIndex === i) this.openIndex = -1;
        }, "onClose"),
        onUnhandledKey: /* @__PURE__ */ __name((ev) => {
          if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return false;
          const n = this.menus.length;
          this.openMenu((i + (ev.key === "ArrowRight" ? 1 : -1) + n) % n, true);
          return true;
        }, "onUnhandledKey")
      });
      if (focus) view.focusFirst();
    }
    closeMenu() {
      const m = this.menus[this.openIndex];
      if (m) m.close();
      this.openIndex = -1;
    }
  };
  define("hd-menu", HdMenu);
  define("hd-menu-item", class extends HdMenuPart {
  });
  define("hd-menu-separator", class extends HdMenuPart {
  });
  define("hd-menu-heading", class extends HdMenuPart {
  });
  define("hd-menubar", HdMenubar);

  // ui/kit/src/core/pure/expr.ts
  var MAX_LENGTH = 1e3;
  var MAX_DEPTH = 64;
  var CONSTANTS = {
    pi: Math.PI,
    e: Math.E,
    tau: Math.PI * 2
  };
  var FUNCTIONS = {
    sqrt: { arity: [1, 1], fn: Math.sqrt },
    abs: { arity: [1, 1], fn: Math.abs },
    floor: { arity: [1, 1], fn: Math.floor },
    ceil: { arity: [1, 1], fn: Math.ceil },
    round: { arity: [1, 1], fn: Math.round },
    sin: { arity: [1, 1], fn: Math.sin },
    cos: { arity: [1, 1], fn: Math.cos },
    tan: { arity: [1, 1], fn: Math.tan },
    log: { arity: [1, 2], fn: /* @__PURE__ */ __name((x, base) => base === void 0 ? Math.log(x) : Math.log(x) / Math.log(base), "fn") },
    exp: { arity: [1, 1], fn: Math.exp },
    pow: { arity: [2, 2], fn: Math.pow },
    min: { arity: [1, 32], fn: Math.min },
    max: { arity: [1, 32], fn: Math.max },
    radians: { arity: [1, 1], fn: /* @__PURE__ */ __name((d) => d * Math.PI / 180, "fn") },
    degrees: { arity: [1, 1], fn: /* @__PURE__ */ __name((r) => r * 180 / Math.PI, "fn") }
  };
  var ExprError = class extends Error {
    static {
      __name(this, "ExprError");
    }
  };
  function tokenize(src) {
    const out = [];
    let i = 0;
    while (i < src.length) {
      const ch = src[i];
      if (/\s/.test(ch)) {
        i += 1;
        continue;
      }
      if (/[0-9.]/.test(ch)) {
        const m = /^(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/.exec(src.slice(i));
        if (!m) throw new ExprError(`not a number at "${src.slice(i)}"`);
        out.push({ t: "num", v: Number(m[0]) });
        i += m[0].length;
        continue;
      }
      if (/[A-Za-z_°µ%"']/.test(ch)) {
        const m = /^(?:[A-Za-z_µ][A-Za-z_0-9]*|°|%|"|')/.exec(src.slice(i));
        const word = m ? m[0] : ch;
        out.push({ t: "id", v: word });
        i += word.length;
        continue;
      }
      if (ch === "*" && src[i + 1] === "*") {
        out.push({ t: "op", v: "^" });
        i += 2;
        continue;
      }
      if ("+-*/^".includes(ch)) {
        out.push({ t: "op", v: ch });
        i += 1;
        continue;
      }
      if (ch === "(") out.push({ t: "(" });
      else if (ch === ")") out.push({ t: ")" });
      else if (ch === ",") out.push({ t: "," });
      else throw new ExprError(`unexpected "${ch}"`);
      i += 1;
    }
    return out;
  }
  __name(tokenize, "tokenize");
  var Parser = class {
    constructor(tokens, units) {
      this.tokens = tokens;
      this.units = units;
    }
    static {
      __name(this, "Parser");
    }
    pos = 0;
    depth = 0;
    parse() {
      const v = this.expr();
      if (this.pos < this.tokens.length) throw new ExprError("unexpected text after the expression");
      return v;
    }
    peek() {
      return this.tokens[this.pos];
    }
    next() {
      const t = this.tokens[this.pos];
      this.pos += 1;
      return t;
    }
    // expr := term (('+' | '-') term)*
    expr() {
      let v = this.term();
      for (; ; ) {
        const t = this.peek();
        if (t && t.t === "op" && (t.v === "+" || t.v === "-")) {
          this.next();
          const r = this.term();
          v = t.v === "+" ? v + r : v - r;
        } else return v;
      }
    }
    // term := unary (('*' | '/' | '%'-as-modulo) unary)*
    term() {
      let v = this.unary();
      for (; ; ) {
        const t = this.peek();
        if (t && t.t === "op" && (t.v === "*" || t.v === "/")) {
          this.next();
          const r = this.unary();
          if (t.v === "/" && r === 0) throw new ExprError("division by zero");
          v = t.v === "*" ? v * r : v / r;
        } else if (t && t.t === "id" && t.v === "%" && this.startsOperand(this.tokens[this.pos + 1])) {
          this.next();
          const r = this.unary();
          if (r === 0) throw new ExprError("modulo by zero");
          v = v % r;
        } else return v;
      }
    }
    startsOperand(t) {
      return !!t && (t.t === "num" || t.t === "(" || t.t === "id" && t.v !== "%" || t.t === "op" && (t.v === "-" || t.v === "+"));
    }
    // unary := ('+' | '-') unary | power
    // Every level of nesting -- a bracket, a sign, a power, a call -- passes through here,
    // so this is where depth is counted.
    unary() {
      this.depth += 1;
      try {
        if (this.depth > MAX_DEPTH) throw new ExprError(`the expression nests too deeply (more than ${MAX_DEPTH} levels)`);
        return this.unaryInner();
      } finally {
        this.depth -= 1;
      }
    }
    unaryInner() {
      const t = this.peek();
      if (t && t.t === "op" && (t.v === "-" || t.v === "+")) {
        this.next();
        const v = this.unary();
        return t.v === "-" ? -v : v;
      }
      return this.power();
    }
    // power := postfix ('^' unary)?   -- right-associative, binds tighter than unary minus on its left
    power() {
      const base = this.postfix();
      const t = this.peek();
      if (t && t.t === "op" && t.v === "^") {
        this.next();
        return Math.pow(base, this.unary());
      }
      return base;
    }
    // postfix := primary unit?
    postfix() {
      let v = this.primary();
      const t = this.peek();
      if (t && t.t === "id" && this.units.has(t.v) && !(t.v === "%" && this.startsOperand(this.tokens[this.pos + 1]))) {
        this.next();
        v *= this.units.get(t.v);
      }
      return v;
    }
    primary() {
      const t = this.next();
      if (!t) throw new ExprError("the expression ends too soon");
      if (t.t === "num") return t.v;
      if (t.t === "(") {
        const v = this.expr();
        const close = this.next();
        if (!close || close.t !== ")") throw new ExprError("a bracket is not closed");
        return v;
      }
      if (t.t === "id") {
        const name = t.v.toLowerCase();
        const fn = own(FUNCTIONS, name);
        if (fn) {
          const open2 = this.next();
          if (!open2 || open2.t !== "(") throw new ExprError(`${name} needs brackets: ${name}(...)`);
          const args = [];
          if (this.peek()?.t !== ")") {
            args.push(this.expr());
            while (this.peek()?.t === ",") {
              this.next();
              args.push(this.expr());
            }
          }
          const close = this.next();
          if (!close || close.t !== ")") throw new ExprError(`${name}( is not closed`);
          const [lo, hi] = fn.arity;
          if (args.length < lo || args.length > hi) throw new ExprError(`${name} takes ${lo === hi ? lo : `${lo} to ${hi}`} argument(s)`);
          return fn.fn(...args);
        }
        const constant = own(CONSTANTS, name);
        if (constant !== void 0) return constant;
        throw new ExprError(`unknown name "${t.v}"`);
      }
      throw new ExprError("expected a number");
    }
  };
  function evaluate(text, units = []) {
    const src = text.trim();
    if (!src) return { ok: false, error: "empty" };
    if (src.length > MAX_LENGTH) return { ok: false, error: `the expression is too long (${src.length} characters; at most ${MAX_LENGTH})` };
    const table = /* @__PURE__ */ new Map();
    for (const u of units) for (const n of u.names) table.set(n, u.factor);
    try {
      const value = new Parser(tokenize(src), table).parse();
      if (!Number.isFinite(value)) return { ok: false, error: "the result is not a finite number" };
      return { ok: true, value };
    } catch (err) {
      if (err instanceof ExprError) return { ok: false, error: err.message };
      return { ok: false, error: `cannot evaluate that (${err instanceof Error ? err.name : "error"})` };
    }
  }
  __name(evaluate, "evaluate");

  // ui/kit/src/number/controller.ts
  var MAX_PRECISION = 6;
  function clampPrecision(p, integer) {
    if (p === void 0 || !Number.isFinite(p)) return integer ? 0 : 3;
    return Math.min(MAX_PRECISION, Math.max(0, Math.trunc(p)));
  }
  __name(clampPrecision, "clampPrecision");
  function makeSpec(partial = {}) {
    const integer = partial.integer ?? false;
    const precision = clampPrecision(partial.precision, integer);
    const min = partial.min ?? -Infinity;
    const max = partial.max ?? Infinity;
    const step = partial.step !== void 0 && Number.isFinite(partial.step) && partial.step > 0 ? partial.step : integer ? 1 : Math.pow(10, -Math.min(precision, 2));
    const factor = partial.displayFactor;
    return {
      min,
      max,
      softMin: partial.softMin,
      softMax: partial.softMax,
      step,
      precision,
      integer,
      default: partial.default ?? (Number.isFinite(min) && min > 0 ? min : 0),
      unit: partial.unit ?? "",
      displayFactor: factor !== void 0 && Number.isFinite(factor) && factor !== 0 ? factor : 1,
      slider: partial.slider ?? false
    };
  }
  __name(makeSpec, "makeSpec");
  function dragRange(spec) {
    const lo = spec.softMin ?? spec.min;
    const hi = spec.softMax ?? spec.max;
    return [Math.max(lo, spec.min), Math.min(hi, spec.max)];
  }
  __name(dragRange, "dragRange");
  function clamp(v, spec) {
    return Math.min(spec.max, Math.max(spec.min, v));
  }
  __name(clamp, "clamp");
  function quantize(v, spec) {
    if (spec.integer) return Math.round(v);
    const places = Math.min(12, spec.precision + 3);
    const q = Number(v.toFixed(places));
    return Object.is(q, -0) ? 0 : q;
  }
  __name(quantize, "quantize");
  function snap(v, unit) {
    if (!(unit > 0)) return v;
    return Math.round(v / unit) * unit;
  }
  __name(snap, "snap");
  function settle2(v, spec) {
    return quantize(clamp(v, spec), spec);
  }
  __name(settle2, "settle");
  function format(v, spec) {
    const shown = v * spec.displayFactor;
    const places = spec.integer && spec.displayFactor === 1 ? 0 : spec.precision;
    let text = shown.toFixed(places);
    if (/^-0(\.0*)?$/.test(text)) text = text.slice(1);
    return spec.unit ? `${text} ${spec.unit}` : text;
  }
  __name(format, "format");
  function editText(v, spec) {
    const shown = v * spec.displayFactor;
    if (spec.integer && spec.displayFactor === 1) return String(Math.round(shown));
    return String(Number(shown.toFixed(Math.min(12, spec.precision + 3))));
  }
  __name(editText, "editText");
  var FAMILIES = [
    { ms: 1e-3, s: 1, sec: 1, min: 60, h: 3600, hr: 3600 },
    { mm: 1e-3, cm: 0.01, m: 1, km: 1e3 },
    { B: 1, KB: 1024, MB: 1024 * 1024, GB: 1024 * 1024 * 1024 },
    { "°": 1, deg: 1, rad: 180 / Math.PI }
  ];
  function unitsFor(unit) {
    if (!unit) return [];
    for (const fam of FAMILIES) {
      const base = own(fam, unit);
      if (base !== void 0) {
        return Object.entries(fam).map(([name, f]) => ({ names: [name], factor: f / base }));
      }
    }
    return [{ names: [unit], factor: 1 }];
  }
  __name(unitsFor, "unitsFor");
  function parseTyped(text, spec) {
    const res = evaluate(text, unitsFor(spec.unit));
    if (!res.ok) return res;
    const v = res.value / spec.displayFactor;
    if (!Number.isFinite(v)) return { ok: false, error: "that is too large" };
    return { ok: true, value: settle2(v, spec) };
  }
  __name(parseTyped, "parseTyped");
  function stepValue(v, dir, spec) {
    return settle2(v + dir * spec.step, spec);
  }
  __name(stepValue, "stepValue");
  function resetValue(spec) {
    return settle2(spec.default, spec);
  }
  __name(resetValue, "resetValue");
  function negateValue(v, spec) {
    return settle2(-v, spec);
  }
  __name(negateValue, "negateValue");
  function fillFraction(v, spec) {
    const [lo, hi] = dragRange(spec);
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return 0;
    return Math.min(1, Math.max(0, (v - lo) / (hi - lo)));
  }
  __name(fillFraction, "fillFraction");
  function valuePerPixel(spec, fieldWidth, pxPerStep = 8) {
    if (spec.slider) {
      const [lo, hi] = dragRange(spec);
      if (Number.isFinite(lo) && Number.isFinite(hi) && fieldWidth > 0) return (hi - lo) / fieldWidth;
    }
    return spec.step / pxPerStep;
  }
  __name(valuePerPixel, "valuePerPixel");
  var FieldScrub = class {
    constructor(id, spec, start, perPx) {
      this.id = id;
      this.spec = spec;
      this.start = start;
      this.perPx = perPx;
      this.raw = start;
      this.value = start;
    }
    static {
      __name(this, "FieldScrub");
    }
    raw;
    value;
    apply(dx, mods2) {
      const precise = mods2.shift ? 0.1 : 1;
      const [lo, hi] = dragRange(this.spec);
      const low = this.start < lo ? this.spec.min : lo;
      const high = this.start > hi ? this.spec.max : hi;
      this.raw = Math.min(high, Math.max(low, this.raw + dx * this.perPx * precise));
      let v = this.raw;
      if (mods2.ctrl) v = snap(v, mods2.shift ? this.spec.step / 10 : this.spec.step);
      this.value = settle2(v, this.spec);
      return this.value;
    }
  };
  var ScrubSession = class {
    static {
      __name(this, "ScrubSession");
    }
    phase = "pending";
    fields = [];
    tx = 0;
    ty = 0;
    hx = 0;
    discardNext = false;
    threshold;
    multi;
    maxJump;
    constructor(first, opts = {}) {
      this.fields.push(first);
      this.threshold = opts.threshold ?? 3;
      this.multi = opts.multi ?? true;
      this.maxJump = opts.maxJump ?? Infinity;
    }
    /** The cursor was just moved by us (a wrap), or the lock just engaged: the next delta
     *  reports that jump and must not be read as drag distance. */
    warped() {
      this.discardNext = true;
    }
    /** Another field, crossed while collecting a multi-drag. Ignored if already in. */
    add(field) {
      if (this.phase !== "collect" || this.fields.some((f) => f.id === field.id)) return false;
      this.fields.push(field);
      return true;
    }
    /** Feed one pointer delta. Returns true when any value changed. */
    move(dx, dy, mods2) {
      if (this.discardNext) {
        this.discardNext = false;
        return false;
      }
      if (Math.abs(dx) > this.maxJump || Math.abs(dy) > this.maxJump) return false;
      switch (this.phase) {
        case "pending": {
          this.tx += dx;
          this.ty += dy;
          if (Math.max(Math.abs(this.tx), Math.abs(this.ty)) < this.threshold) return false;
          if (this.multi && Math.abs(this.ty) > Math.abs(this.tx)) {
            this.phase = "collect";
            return false;
          }
          this.phase = "scrub";
          return this.applyAll(this.tx, mods2);
        }
        case "collect": {
          this.hx += dx;
          if (Math.abs(this.hx) < this.threshold * 2) return false;
          this.phase = "multi";
          return this.applyAll(this.hx, mods2);
        }
        case "scrub":
        case "multi":
          return this.applyAll(dx, mods2);
      }
    }
    /** True once motion is being read as a value change (the view locks the pointer then). */
    get scrubbing() {
      return this.phase === "scrub" || this.phase === "multi";
    }
    applyAll(dx, mods2) {
      let changed = false;
      for (const f of this.fields) {
        const before = f.value;
        if (f.apply(dx, mods2) !== before) changed = true;
      }
      return changed;
    }
    values() {
      return new Map(this.fields.map((f) => [f.id, f.value]));
    }
    end() {
      if (this.phase === "pending") return { kind: "click" };
      if (this.phase === "collect") return { kind: "multi-type", ids: this.fields.map((f) => f.id) };
      return { kind: "scrub", values: this.values() };
    }
    /** Esc or RMB mid-drag: every field goes back to where it started. */
    cancel() {
      return new Map(this.fields.map((f) => [f.id, f.start]));
    }
  };

  // ui/kit/src/number/element.ts
  var byId = /* @__PURE__ */ new Map();
  function safeParse(text, spec) {
    try {
      return parseTyped(text, spec);
    } catch (err) {
      return { ok: false, error: `cannot evaluate that (${err instanceof Error ? err.name : "error"})` };
    }
  }
  __name(safeParse, "safeParse");
  var PX_PER_STEP = 8;
  var MAX_JUMP = 300;
  var HdNumber = class extends HdElement {
    static {
      __name(this, "HdNumber");
    }
    static get observedAttributes() {
      return ["value", "min", "max", "soft-min", "soft-max", "step", "precision", "integer", "default", "unit", "display-factor", "slider", "label", "disabled", "wired", "invalid", "loading"];
    }
    box;
    input;
    fieldId = uid("hd-num");
    fill;
    labelEl;
    outerLabel;
    valueEl;
    dec;
    inc;
    current = 0;
    edit = new EditSession();
    session = null;
    collected = [];
    multiTargets = [];
    last = { x: 0, y: 0 };
    lockAsked = false;
    releasing = false;
    onLockChange = /* @__PURE__ */ __name(() => this.lockChanged(), "onLockChange");
    onLateLock = /* @__PURE__ */ __name(() => this.lateLock(), "onLateLock");
    // ---- the spec, from attributes ---------------------------------------------------------
    spec() {
      const integer = this.flag("integer");
      return makeSpec({
        min: this.num("min", -Infinity),
        max: this.num("max", Infinity),
        softMin: this.hasAttribute("soft-min") ? this.num("soft-min", -Infinity) : void 0,
        softMax: this.hasAttribute("soft-max") ? this.num("soft-max", Infinity) : void 0,
        step: this.hasAttribute("step") ? this.num("step", 1) : void 0,
        precision: this.hasAttribute("precision") ? this.num("precision", 3) : integer ? 0 : void 0,
        integer,
        default: this.hasAttribute("default") ? this.num("default", 0) : void 0,
        unit: this.str("unit"),
        displayFactor: this.num("display-factor", 1),
        slider: this.flag("slider")
      });
    }
    get value() {
      if (!this.built && this.hasAttribute("value")) return this.num("value", 0);
      return this.current;
    }
    set value(v) {
      const n = Number(v);
      if (!Number.isFinite(n)) return;
      this.current = this.built ? settle2(n, this.spec()) : n;
      if (this.built) this.render();
    }
    get canEdit() {
      return !this.locked && !this.edit.editing;
    }
    get editingNow() {
      return this.edit.editing;
    }
    // ---- build -------------------------------------------------------------------------------
    build() {
      this.upgradeProperty("value");
      const spec = this.spec();
      this.current = settle2(this.hasAttribute("value") ? this.num("value", spec.default) : Number.isFinite(this.current) && this.current !== 0 ? this.current : spec.default, spec);
      byId.set(this.fieldId, this);
      this.outerLabel = h("span", { class: "hd-field__label", "aria-hidden": "true" });
      this.fill = h("span", { class: "hd-num__fill", "aria-hidden": "true" });
      this.dec = h("button", { type: "button", class: "hd-num__arrow hd-num__arrow--dec", tabindex: "-1", "aria-hidden": "true", text: "‹" });
      this.inc = h("button", { type: "button", class: "hd-num__arrow hd-num__arrow--inc", tabindex: "-1", "aria-hidden": "true", text: "›" });
      this.labelEl = h("span", { class: "hd-num__label" });
      this.valueEl = h("span", { class: "hd-num__value" });
      this.input = h("input", { type: "text", class: "hd-num__input", hidden: true, spellcheck: "false", autocomplete: "off", inputmode: "decimal", "aria-label": "" });
      this.box = h("div", { class: "hd-num", tabindex: "0" }, this.fill, this.dec, this.labelEl, this.valueEl, this.inc, this.input);
      this.replaceChildren(this.outerLabel, this.box);
      registerField(this);
      this.box.addEventListener("pointerdown", (ev) => this.down(ev));
      this.box.addEventListener("pointermove", (ev) => this.move(ev));
      this.box.addEventListener("pointerup", (ev) => this.up(ev));
      this.box.addEventListener("pointercancel", () => this.cancelDrag());
      this.box.addEventListener("keydown", (ev) => this.key(ev));
      this.box.addEventListener("wheel", (ev) => this.wheel(ev), { passive: false });
      this.box.addEventListener("dblclick", () => {
        if (!this.edit.editing) this.beginEdit();
      });
      this.box.addEventListener("contextmenu", (ev) => this.menu(ev));
      for (const [btn, dir] of [[this.dec, -1], [this.inc, 1]]) {
        btn.addEventListener("pointerdown", (ev) => ev.stopPropagation());
        btn.addEventListener("click", (ev) => {
          ev.stopPropagation();
          if (this.locked || this.edit.editing) return;
          this.commit(stepValue(this.current, dir, this.spec()));
          this.box.focus({ preventScroll: true });
        });
      }
      this.input.addEventListener("keydown", (ev) => this.editKey(ev));
      this.input.addEventListener("blur", () => this.editBlur());
      this.input.addEventListener("input", (ev) => {
        ev.stopPropagation();
        this.edit.input(this.input.value);
        this.input.removeAttribute("aria-invalid");
      });
      this.input.addEventListener("contextmenu", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        this.cancelEdit();
      });
    }
    changed(name) {
      if (name === "value" && !this.session && !this.edit.editing) {
        this.current = settle2(this.num("value", this.current), this.spec());
      }
      this.render();
    }
    disconnected() {
      if (this.session) this.cancelDrag();
    }
    render() {
      const spec = this.spec();
      const label = this.str("label");
      const wired = this.getAttribute("wired");
      const slider = spec.slider;
      this.labelEl.textContent = label;
      this.labelEl.hidden = !label;
      this.outerLabel.textContent = label;
      this.valueEl.textContent = wired ? `← ${wired}`.trim() : format(this.current, spec);
      if (wired === "") this.valueEl.textContent = format(this.current, spec);
      this.fill.hidden = !slider;
      this.fill.style.width = `${(fillFraction(this.current, spec) * 100).toFixed(2)}%`;
      this.dec.hidden = slider;
      this.inc.hidden = slider;
      const b = this.box;
      b.setAttribute("role", slider ? "slider" : "spinbutton");
      b.setAttribute("aria-label", label || this.str("tooltip") || "Number");
      b.setAttribute("aria-valuenow", String(this.current));
      b.setAttribute("aria-valuetext", format(this.current, spec));
      if (Number.isFinite(spec.min)) b.setAttribute("aria-valuemin", String(spec.min));
      else b.removeAttribute("aria-valuemin");
      if (Number.isFinite(spec.max)) b.setAttribute("aria-valuemax", String(spec.max));
      else b.removeAttribute("aria-valuemax");
      const disabled = this.flag("disabled");
      b.tabIndex = disabled ? -1 : 0;
      b.setAttribute("aria-disabled", String(disabled));
      b.toggleAttribute("aria-readonly", this.hasAttribute("wired") || this.flag("loading"));
      b.setAttribute("aria-invalid", String(this.hasAttribute("invalid")));
      b.setAttribute("aria-busy", String(this.flag("loading")));
      this.input.setAttribute("aria-label", label || "Number");
    }
    focus(options) {
      if (this.edit.editing) this.input.focus(options);
      else this.box.focus(options);
    }
    // ---- committing ------------------------------------------------------------------------
    /** Set, repaint and announce a new committed value. */
    commit(v) {
      const next = settle2(v, this.spec());
      if (next === this.current) return;
      this.current = next;
      this.render();
      this.emit("input");
      this.emit("change");
    }
    preview(v) {
      if (v === this.current) return;
      this.current = v;
      this.render();
      this.emit("input");
    }
    // ---- the drag --------------------------------------------------------------------------
    down(ev) {
      if (this.session && ev.button === 2) {
        ev.preventDefault();
        swallowRightClick();
        this.cancelDrag();
        return;
      }
      if (ev.button !== 0 || this.locked || this.edit.editing) return;
      ev.preventDefault();
      this.box.focus({ preventScroll: true });
      const spec = this.spec();
      this.session = new ScrubSession(new FieldScrub(this.fieldId, spec, this.current, valuePerPixel(spec, this.box.clientWidth, PX_PER_STEP)), { maxJump: MAX_JUMP });
      this.collected = [];
      this.last = { x: ev.clientX, y: ev.clientY };
      this.lockAsked = false;
      try {
        this.box.setPointerCapture(ev.pointerId);
      } catch {
      }
      this.stopAwaitingLateLock();
      document.addEventListener("pointerlockchange", this.onLockChange);
    }
    move(ev) {
      const s = this.session;
      if (!s) return;
      if (ev.buttons & 2) {
        ev.preventDefault();
        swallowRightClick();
        this.cancelDrag();
        return;
      }
      const locked = document.pointerLockElement === this.box;
      const dx = locked ? ev.movementX : ev.clientX - this.last.x;
      const dy = locked ? ev.movementY : ev.clientY - this.last.y;
      this.last = { x: ev.clientX, y: ev.clientY };
      const changed = s.move(dx, dy, mods(ev));
      if (s.phase === "collect") this.collect(ev.clientX, ev.clientY);
      if (s.scrubbing && !this.lockAsked) this.startGrab();
      if (changed) {
        for (const [id, v] of s.values()) byId.get(id)?.preview(v);
      }
    }
    /** Multi-drag: add every field the pointer crosses while moving down. */
    collect(x, y) {
      const s = this.session;
      if (!s) return;
      const hit = document.elementFromPoint(x, y)?.closest("hd-number");
      this.setAttribute("data-hd-multi", "");
      if (!hit || hit === this || this.collected.includes(hit) || !hit.canEdit) return;
      const spec = hit.spec();
      if (s.add(new FieldScrub(hit.fieldId, spec, hit.value, valuePerPixel(spec, hit.box.clientWidth, PX_PER_STEP)))) {
        this.collected.push(hit);
        hit.setAttribute("data-hd-multi", "");
      }
    }
    startGrab() {
      this.lockAsked = true;
      this.setAttribute("data-hd-dragging", "");
      for (const f of this.collected) f.setAttribute("data-hd-dragging", "");
      try {
        const p = this.box.requestPointerLock();
        if (p && typeof p.catch === "function") p.catch(() => void 0);
      } catch {
      }
    }
    lockChanged() {
      if (!this.session) return;
      if (document.pointerLockElement === this.box) return;
      if (!this.releasing) this.cancelDrag();
    }
    up(ev) {
      const s = this.session;
      if (!s || ev.button !== 0) return;
      const start = new Map(s.fields.map((f) => [f.id, f.start]));
      const end = s.end();
      this.finishDrag();
      if (end.kind === "click") {
        this.beginEdit();
      } else if (end.kind === "scrub") {
        for (const [id, v] of end.values) {
          const el = byId.get(id);
          if (el && v !== start.get(id)) el.emit("change");
        }
      } else {
        this.multiTargets = end.ids.map((id) => byId.get(id)).filter((e) => !!e && e !== this);
        this.beginEdit();
      }
    }
    cancelDrag() {
      const s = this.session;
      if (!s) return;
      const back = s.cancel();
      this.finishDrag();
      for (const [id, v] of back) byId.get(id)?.preview(v);
    }
    finishDrag() {
      const fields = [this, ...this.collected];
      this.session = null;
      document.removeEventListener("pointerlockchange", this.onLockChange);
      if (document.pointerLockElement === this.box) {
        this.releasing = true;
        document.exitPointerLock();
        window.setTimeout(() => this.releasing = false, 0);
      } else if (this.lockAsked) {
        document.addEventListener("pointerlockchange", this.onLateLock);
        document.addEventListener("pointerlockerror", this.onLateLock);
      }
      for (const f of fields) {
        f.removeAttribute("data-hd-dragging");
        f.removeAttribute("data-hd-multi");
      }
      this.collected = [];
    }
    /** The late grant (see `finishDrag`): the lock landed, or was refused, after the drag. */
    lateLock() {
      this.stopAwaitingLateLock();
      if (document.pointerLockElement === this.box) document.exitPointerLock();
    }
    stopAwaitingLateLock() {
      document.removeEventListener("pointerlockchange", this.onLateLock);
      document.removeEventListener("pointerlockerror", this.onLateLock);
    }
    // ---- keys and wheel --------------------------------------------------------------------
    key(ev) {
      if (this.edit.editing) return;
      if (this.session) {
        if (ev.key === "Escape") {
          ev.preventDefault();
          ev.stopPropagation();
          this.cancelDrag();
        }
        return;
      }
      if (this.locked || ev.altKey) return;
      const spec = this.spec();
      const ctrl = ev.ctrlKey || ev.metaKey;
      let handled = true;
      switch (ev.key) {
        case "Enter":
        case "F2":
          this.beginEdit();
          break;
        case "ArrowUp":
        case "ArrowRight":
          this.commit(stepValue(this.current, 1, spec));
          break;
        case "ArrowDown":
        case "ArrowLeft":
          this.commit(stepValue(this.current, -1, spec));
          break;
        case "PageUp":
          this.commit(stepValue(this.current, 10, spec));
          break;
        case "PageDown":
          this.commit(stepValue(this.current, -10, spec));
          break;
        case "Home":
          if (Number.isFinite(spec.min)) this.commit(spec.min);
          break;
        case "End":
          if (Number.isFinite(spec.max)) this.commit(spec.max);
          break;
        default:
          if (!ctrl && /^[0-9.,(]$/.test(ev.key)) this.beginEdit(ev.key === "," ? "." : ev.key);
          else handled = false;
      }
      if (handled) ev.preventDefault();
    }
    wheel(ev) {
      if (!(ev.ctrlKey || ev.metaKey) || !ev.deltaY || this.locked || this.edit.editing) return;
      ev.preventDefault();
      ev.stopPropagation();
      this.commit(stepValue(this.current, ev.deltaY < 0 ? 1 : -1, this.spec()));
    }
    menu(ev) {
      ev.preventDefault();
      if (this.session) return;
      const items = fieldMenu({
        reset: /* @__PURE__ */ __name(() => this.resetToDefault(), "reset"),
        copyText: /* @__PURE__ */ __name(() => this.copyValue(), "copyText"),
        paste: /* @__PURE__ */ __name((t) => this.pasteValue(t), "paste"),
        devId: this.str("command") || this.str("node-type"),
        host: this
      });
      for (const it of items) if (it.command === "ui.reset_default" || it.command === "ui.paste_value") it.disabled = it.disabled || this.locked;
      openMenu(items, { at: { x: ev.clientX, y: ev.clientY }, restoreFocus: this.box });
    }
    // ---- hover hotkeys (core/hover.ts) -------------------------------------------------------
    copyValue() {
      return editText(this.current, this.spec());
    }
    pasteValue(text) {
      if (this.locked) {
        refuse(this.box, lockedReason(this));
        return false;
      }
      const res = safeParse(normalisePaste(text), this.spec());
      if (!res.ok) {
        refuse(this.box, `Paste expected a number: ${res.error}`);
        return false;
      }
      this.commit(res.value);
      return true;
    }
    resetToDefault() {
      if (this.locked) return false;
      this.commit(resetValue(this.spec()));
      return true;
    }
    negate() {
      if (this.locked) return false;
      this.commit(negateValue(this.current, this.spec()));
      return true;
    }
    // ---- typing -----------------------------------------------------------------------------
    beginEdit(seed) {
      if (this.locked || this.edit.editing) return;
      const { text, selectAll } = this.edit.begin(editText(this.current, this.spec()), seed);
      this.input.value = text;
      this.input.hidden = false;
      this.input.removeAttribute("aria-invalid");
      this.setAttribute("data-editing", "");
      for (const t of this.multiTargets) t.setAttribute("data-hd-multi", "");
      this.input.focus({ preventScroll: true });
      if (selectAll) this.input.select();
      else this.input.setSelectionRange(text.length, text.length);
    }
    /** Apply the typed text. False (and still editing, marked invalid with the reason)
     *  when it does not parse. Never throws: a field that cannot confirm must still be
     *  able to say why and let go. */
    confirmEdit() {
      if (!this.edit.editing) return true;
      const text = this.input.value;
      const res = safeParse(text, this.spec());
      if (!res.ok) {
        this.input.setAttribute("aria-invalid", "true");
        this.input.title = res.error;
        return false;
      }
      this.edit.confirm();
      this.endEdit();
      const targets2 = [this, ...this.multiTargets];
      this.multiTargets = [];
      for (const t of targets2) {
        const r = t === this ? res : safeParse(text, t.spec());
        if (r.ok) t.commit(r.value);
      }
      return true;
    }
    cancelEdit() {
      if (!this.edit.editing) return;
      this.edit.cancel();
      this.endEdit();
      this.multiTargets = [];
      this.box.focus({ preventScroll: true });
    }
    endEdit() {
      this.input.hidden = true;
      this.input.removeAttribute("title");
      this.removeAttribute("data-editing");
      for (const t of this.multiTargets) t.removeAttribute("data-hd-multi");
    }
    editKey(ev) {
      const action = editKeyAction(ev.key, { ctrl: ev.ctrlKey || ev.metaKey, shift: ev.shiftKey, composing: ev.isComposing || ev.keyCode === 229 });
      if (!action) return;
      ev.preventDefault();
      ev.stopPropagation();
      switch (action) {
        case "confirm":
          if (this.confirmEdit()) this.box.focus({ preventScroll: true });
          break;
        case "cancel":
          this.cancelEdit();
          break;
        case "next":
        case "prev": {
          if (!this.confirmEdit()) break;
          const next = adjacentField(this, action === "next" ? 1 : -1);
          if (next && next !== this) next.beginEdit();
          else this.box.focus({ preventScroll: true });
          break;
        }
        case "delete-word-before":
        case "delete-word-after": {
          const fn = action === "delete-word-before" ? deleteWordBefore : deleteWordAfter;
          const r = fn(this.input.value, this.input.selectionStart ?? 0, this.input.selectionEnd ?? 0);
          this.input.value = r.text;
          this.input.setSelectionRange(r.caret, r.caret);
          this.edit.input(r.text);
          break;
        }
      }
    }
    editBlur() {
      if (!this.edit.editing) return;
      let applied = false;
      try {
        applied = this.confirmEdit();
      } catch {
        applied = false;
      }
      if (!applied) {
        this.edit.cancel();
        this.endEdit();
        this.multiTargets = [];
      }
    }
  };
  define("hd-number", HdNumber);

  // ui/kit/src/text/element.ts
  var HdText = class extends HdElement {
    static {
      __name(this, "HdText");
    }
    static get observedAttributes() {
      return ["value", "label", "placeholder", "disabled", "wired", "invalid", "loading", "mono"];
    }
    input;
    labelEl;
    outerLabel;
    current = "";
    edit = new EditSession();
    get value() {
      return this.built || !this.hasAttribute("value") ? this.current : this.str("value");
    }
    set value(v) {
      this.current = String(v ?? "");
      if (this.built && !this.edit.editing) this.input.value = this.current;
    }
    get canEdit() {
      return !this.locked && !this.edit.editing;
    }
    get editingNow() {
      return this.edit.editing;
    }
    build() {
      this.upgradeProperty("value");
      if (this.hasAttribute("value")) this.current = this.str("value");
      this.outerLabel = h("span", { class: "hd-field__label", "aria-hidden": "true" });
      this.labelEl = h("span", { class: "hd-txt__label" });
      this.input = h("input", { type: "text", class: "hd-txt__input", readonly: true, spellcheck: "false", autocomplete: "off" });
      this.input.value = this.current;
      const box = h("div", { class: "hd-txt" }, this.labelEl, this.input);
      this.replaceChildren(this.outerLabel, box);
      registerField(this);
      this.input.addEventListener("pointerdown", (ev) => {
        if (ev.button === 0 && !this.edit.editing && !this.locked) {
          ev.preventDefault();
          this.beginEdit();
        }
      });
      this.input.addEventListener("keydown", (ev) => this.key(ev));
      this.input.addEventListener("input", (ev) => {
        ev.stopPropagation();
        if (!this.edit.editing) return;
        this.edit.input(this.input.value);
        this.emit("input");
      });
      this.input.addEventListener("blur", () => {
        if (this.edit.editing) this.confirm();
      });
      this.input.addEventListener("contextmenu", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (this.edit.editing) {
          this.cancel();
          return;
        }
        const items = fieldMenu({
          reset: /* @__PURE__ */ __name(() => this.resetToDefault(), "reset"),
          copyText: /* @__PURE__ */ __name(() => this.copyValue(), "copyText"),
          paste: /* @__PURE__ */ __name((t) => this.pasteValue(t), "paste"),
          devId: this.str("command"),
          host: this
        });
        openMenu(items, { at: { x: ev.clientX, y: ev.clientY }, restoreFocus: this.input });
      });
      this.input.addEventListener("paste", (ev) => {
        if (!this.edit.editing || !ev.clipboardData) return;
        const text = normalisePaste(ev.clipboardData.getData("text/plain"));
        ev.preventDefault();
        ev.stopPropagation();
        this.input.setRangeText(text, this.input.selectionStart ?? 0, this.input.selectionEnd ?? 0, "end");
        this.edit.input(this.input.value);
        this.emit("input");
      });
    }
    changed(name) {
      if (name === "value" && !this.edit.editing) {
        this.current = this.str("value");
        this.input.value = this.current;
      }
      this.render();
    }
    render() {
      const label = this.str("label");
      this.labelEl.textContent = label;
      this.labelEl.hidden = !label;
      this.outerLabel.textContent = label;
      this.input.placeholder = this.str("placeholder");
      this.input.setAttribute("aria-label", label || this.str("placeholder") || "Text");
      const disabled = this.flag("disabled");
      this.input.disabled = disabled;
      this.input.setAttribute("aria-invalid", String(this.hasAttribute("invalid")));
      this.input.setAttribute("aria-busy", String(this.flag("loading")));
      const wired = this.getAttribute("wired");
      if (wired && !this.edit.editing) this.input.value = `← ${wired}`;
      else if (!this.edit.editing) this.input.value = this.current;
      this.input.classList.toggle("mono", this.flag("mono"));
    }
    focus(options) {
      this.input.focus(options);
    }
    // ---- editing ----------------------------------------------------------------------------
    beginEdit(seed) {
      if (this.locked || this.edit.editing) return;
      const { text, selectAll } = this.edit.begin(this.current, seed);
      this.input.readOnly = false;
      this.input.value = text;
      this.setAttribute("data-editing", "");
      this.input.focus({ preventScroll: true });
      if (selectAll) this.input.select();
      else this.input.setSelectionRange(text.length, text.length);
    }
    confirm() {
      const { value, changed } = this.edit.confirm();
      if (changed) this.current = value;
      this.end();
      if (changed) this.emit("change");
    }
    cancel() {
      const original = this.edit.cancel();
      this.end();
      this.input.value = original;
      this.emit("input");
    }
    end() {
      this.input.readOnly = true;
      this.removeAttribute("data-editing");
      this.render();
    }
    key(ev) {
      if (!this.edit.editing) {
        if (this.locked || ev.ctrlKey || ev.metaKey || ev.altKey) return;
        if (ev.key === "Enter" || ev.key === "F2") {
          ev.preventDefault();
          this.beginEdit();
        } else if (ev.key.length === 1 || ev.key === "Process") {
          this.beginEdit();
        }
        return;
      }
      const action = editKeyAction(ev.key, { ctrl: ev.ctrlKey || ev.metaKey, shift: ev.shiftKey, composing: ev.isComposing || ev.keyCode === 229 });
      if (!action) return;
      ev.preventDefault();
      ev.stopPropagation();
      switch (action) {
        case "confirm":
          this.confirm();
          break;
        case "cancel":
          this.cancel();
          break;
        case "next":
        case "prev": {
          this.confirm();
          const next = adjacentField(this, action === "next" ? 1 : -1);
          if (next && next !== this) next.beginEdit();
          break;
        }
        case "delete-word-before":
        case "delete-word-after": {
          const fn = action === "delete-word-before" ? deleteWordBefore : deleteWordAfter;
          const r = fn(this.input.value, this.input.selectionStart ?? 0, this.input.selectionEnd ?? 0);
          this.input.value = r.text;
          this.input.setSelectionRange(r.caret, r.caret);
          this.edit.input(r.text);
          this.emit("input");
          break;
        }
      }
    }
    // ---- hover hotkeys ----------------------------------------------------------------------
    copyValue() {
      return this.current;
    }
    pasteValue(text) {
      if (this.locked) {
        refuse(this.input, lockedReason(this));
        return false;
      }
      const t = normalisePaste(text);
      if (t === this.current) return true;
      this.current = t;
      this.input.value = t;
      this.emit("input");
      this.emit("change");
      return true;
    }
    resetToDefault() {
      if (this.locked) return false;
      return this.pasteValue(this.str("default"));
    }
  };
  define("hd-text", HdText);

  // ui/kit/src/choice/element.ts
  function readOptions(host) {
    const out = [];
    for (const child of [...host.children]) {
      if (child instanceof HTMLOptGroupElement) {
        for (const o of [...child.querySelectorAll("option")]) out.push(fromOption(o, child.label));
      } else if (child instanceof HTMLOptionElement) out.push(fromOption(child));
    }
    return out;
  }
  __name(readOptions, "readOptions");
  function fromOption(o, group) {
    return { value: o.value, label: ownText(o) || o.value, disabled: o.disabled, icon: o.dataset.icon, description: o.dataset.description, source: o.dataset.path, group };
  }
  __name(fromOption, "fromOption");
  var ChoiceBase = class extends HdElement {
    static {
      __name(this, "ChoiceBase");
    }
    static get observedAttributes() {
      return ["value", "label", "placeholder", "disabled", "wired", "invalid", "loading"];
    }
    options = [];
    button;
    valueEl;
    iconEl;
    labelEl;
    outerLabel;
    popup = null;
    get value() {
      return this.str("value", this.options.find((o) => !o.disabled)?.value ?? "");
    }
    set value(v) {
      this.setAttribute("value", v);
    }
    get selectedOption() {
      return this.options.find((o) => o.value === this.value);
    }
    buildButton(role) {
      this.upgradeProperty("value");
      if (this.options.length === 0) this.options = readOptions(this);
      this.replaceChildren();
      this.outerLabel = h("span", { class: "hd-field__label", "aria-hidden": "true" });
      this.labelEl = h("span", { class: "hd-choice__label" });
      this.iconEl = h("span", { class: "hd-choice__icon", "aria-hidden": "true" });
      this.valueEl = h("span", { class: "hd-choice__value" });
      this.button = h("button", { type: "button", class: "hd-choice", role, "aria-haspopup": "listbox", "aria-expanded": "false" }, this.labelEl, this.iconEl, this.valueEl, h("span", { class: "hd-choice__caret", "aria-hidden": "true", text: "▾" }));
      this.append(this.outerLabel, this.button);
      this.button.addEventListener("click", () => this.popup?.open ? this.close() : this.openPopup(true));
      this.button.addEventListener("wheel", (ev) => {
        if (!(ev.ctrlKey || ev.metaKey) || !ev.deltaY || this.locked) return;
        ev.preventDefault();
        ev.stopPropagation();
        this.choose(cycleOption(this.options, this.value, ev.deltaY));
      }, { passive: false });
    }
    render() {
      const opt = this.selectedOption;
      const label = this.str("label");
      this.labelEl.textContent = label;
      this.labelEl.hidden = !label;
      this.outerLabel.textContent = label;
      const wired = this.getAttribute("wired");
      this.valueEl.textContent = wired ? `← ${wired}` : opt?.label ?? this.str("placeholder", "–");
      this.valueEl.classList.toggle("is-placeholder", !opt && !wired);
      this.iconEl.textContent = opt?.icon ?? "";
      this.iconEl.hidden = !opt?.icon;
      this.button.disabled = this.flag("disabled") || this.flag("loading");
      this.button.setAttribute("aria-label", `${label || "Choice"}: ${opt?.label ?? "none"}`);
      this.button.toggleAttribute("aria-readonly", this.hasAttribute("wired"));
      this.button.setAttribute("aria-invalid", String(this.hasAttribute("invalid")));
      this.button.setAttribute("aria-busy", String(this.flag("loading")));
    }
    choose(v) {
      if (this.locked || v === this.value) return;
      this.value = v;
      this.emit("input");
      this.emit("change");
    }
    close() {
      this.popup?.close("api");
      this.popup = null;
    }
    closed() {
      this.popup = null;
      this.button.setAttribute("aria-expanded", "false");
      this.removeAttribute("data-open");
    }
    focus(options) {
      this.button.focus(options);
    }
  };
  var HdEnum = class extends ChoiceBase {
    static {
      __name(this, "HdEnum");
    }
    active = -1;
    rows = [];
    listbox = null;
    typed = "";
    typedAt = 0;
    build() {
      this.buildButton("combobox");
      this.button.addEventListener("keydown", (ev) => this.key(ev));
    }
    key(ev) {
      if (this.locked || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      const open2 = !!this.popup?.open;
      const now = performance.now();
      if (now - this.typedAt > 700) this.typed = "";
      const action = dropdownKey(this.options, open2, this.active, ev.key, this.typed);
      if (!action) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (ev.key.length === 1 && ev.key !== " ") {
        this.typed += ev.key;
        this.typedAt = now;
      }
      switch (action.kind) {
        case "open":
          this.openPopup(true);
          break;
        case "close":
          this.close();
          this.button.focus();
          break;
        case "move":
          this.setActive(action.index);
          break;
        case "choose": {
          const o = this.options[action.index];
          this.close();
          this.button.focus();
          if (o) this.choose(o.value);
          break;
        }
      }
    }
    setActive(i) {
      this.active = i;
      this.rows.forEach((r) => r.classList.toggle("is-active", Number(r.dataset.index) === i));
      const row = this.rows.find((r) => Number(r.dataset.index) === i);
      if (row) {
        this.button.setAttribute("aria-activedescendant", row.id);
        row.scrollIntoView?.({ block: "nearest" });
      }
    }
    openPopup(_focus) {
      if (this.locked) return;
      this.close();
      const listId = uid("hd-enum-list");
      this.listbox = h("div", { class: "hd-listbox", role: "listbox", id: listId, "aria-label": this.str("label") || "Options" });
      this.rows = [];
      let group;
      this.options.forEach((o, i) => {
        if (o.group && o.group !== group) {
          group = o.group;
          this.listbox?.append(h("div", { class: "hd-listbox__group", role: "presentation", text: o.group }));
        }
        const row = h(
          "div",
          { class: "hd-listbox__opt", role: "option", id: `${listId}-${i}`, "data-index": String(i), "aria-selected": String(o.value === this.value), "aria-disabled": o.disabled ? "true" : null },
          h("span", { class: "hd-listbox__icon", "aria-hidden": "true", text: o.icon ?? "" }),
          h("span", { class: "hd-listbox__text", text: o.label })
        );
        if (o.description) {
          row.setAttribute("tooltip", o.label);
          row.setAttribute("description", o.description);
        }
        row.addEventListener("pointerenter", () => {
          if (!o.disabled) this.setActive(i);
        });
        row.addEventListener("click", () => {
          if (o.disabled) return;
          this.close();
          this.button.focus();
          this.choose(o.value);
        });
        this.rows.push(row);
        this.listbox?.append(row);
      });
      this.listbox.style.minWidth = `${this.button.offsetWidth}px`;
      this.popup = openFloating(this.listbox, { anchor: this.button, side: "below", owner: this.button, restoreFocus: this.button, onClose: /* @__PURE__ */ __name(() => this.closed(), "onClose") });
      this.button.setAttribute("aria-expanded", "true");
      this.button.setAttribute("aria-controls", listId);
      this.setAttribute("data-open", "");
      const at = this.options.findIndex((o) => o.value === this.value);
      this.setActive(at >= 0 ? at : this.options.findIndex((o) => !o.disabled));
    }
    closed() {
      super.closed();
      this.button.removeAttribute("aria-activedescendant");
      this.listbox = null;
      this.rows = [];
    }
  };
  var HdSelect = class extends ChoiceBase {
    static {
      __name(this, "HdSelect");
    }
    build() {
      this.buildButton("combobox");
      this.button.addEventListener("keydown", (ev) => {
        if (this.locked) return;
        if (ev.key === "Enter" || ev.key === " " || ev.key === "ArrowDown" || ev.key === "F4") {
          ev.preventDefault();
          this.openPopup(true);
        } else if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
          ev.preventDefault();
          this.openPopup(true, ev.key);
        }
      });
    }
    openPopup(_focus, seed = "") {
      if (this.locked) return;
      this.close();
      const items = this.options.map((o) => ({ value: o.value, label: o.label, path: o.source ?? o.group, keywords: o.description, disabled: o.disabled, icon: o.icon, description: o.description, option: o }));
      const combo = new Combobox(items);
      const listId = uid("hd-select-list");
      const input = h("input", { type: "text", class: "input hd-select__search", placeholder: "Search", spellcheck: "false", autocomplete: "off", role: "combobox", "aria-expanded": "true", "aria-controls": listId, "aria-autocomplete": "list", "aria-label": `Search ${this.str("label") || "options"}` });
      const list = h("div", { class: "hd-listbox hd-select__list", role: "listbox", id: listId });
      const box = h("div", { class: "hd-select__popup" }, input, list);
      const paint2 = /* @__PURE__ */ __name(() => {
        list.replaceChildren();
        const matches = combo.matches();
        if (matches.length === 0) list.append(h("div", { class: "hd-search__empty", text: `Nothing matches “${combo.query}”` }));
        matches.forEach((m, i) => {
          const o = m.item;
          const row = h(
            "div",
            { class: "hd-listbox__opt", role: "option", id: `${listId}-${i}`, "aria-selected": String(o.value === this.value), "aria-disabled": o.disabled ? "true" : null },
            h("span", { class: "hd-listbox__icon", "aria-hidden": "true", text: o.icon ?? "" }),
            h("span", { class: "hd-listbox__text" }, ...highlighted(o.label, m.ranges)),
            h("span", { class: "hd-listbox__detail", text: o.path ?? "" })
          );
          row.classList.toggle("is-active", i === combo.active);
          row.addEventListener("pointerenter", () => {
            combo.hover(i);
            mark();
          });
          row.addEventListener("click", () => pick(o.value, !!o.disabled));
          list.append(row);
        });
        mark();
      }, "paint");
      const mark = /* @__PURE__ */ __name(() => {
        [...list.querySelectorAll(".hd-listbox__opt")].forEach((r, i) => r.classList.toggle("is-active", i === combo.active));
        const id = combo.active >= 0 ? `${listId}-${combo.active}` : "";
        if (id) {
          input.setAttribute("aria-activedescendant", id);
          document.getElementById(id)?.scrollIntoView?.({ block: "nearest" });
        } else input.removeAttribute("aria-activedescendant");
      }, "mark");
      const pick = /* @__PURE__ */ __name((v, disabled) => {
        if (disabled) return;
        this.popup?.close("chosen");
        this.choose(v);
      }, "pick");
      input.addEventListener("input", () => {
        combo.setQuery(input.value);
        paint2();
      });
      input.addEventListener("keydown", (ev) => {
        if (ev.isComposing || ev.keyCode === 229) return;
        const r = combo.key(ev.key);
        if (r === null) return;
        ev.preventDefault();
        if (r === "close") this.popup?.close("escape");
        else if (r === "moved") mark();
        else pick(r.choose.value, !!r.choose.disabled);
      });
      box.style.minWidth = `${Math.max(this.button.offsetWidth, 200)}px`;
      this.popup = openFloating(box, { anchor: this.button, side: "below", owner: this.button, restoreFocus: this.button, onClose: /* @__PURE__ */ __name(() => this.closed(), "onClose") });
      this.button.setAttribute("aria-expanded", "true");
      this.setAttribute("data-open", "");
      input.value = seed;
      combo.setQuery(seed);
      if (!seed) {
        const at = combo.matches().findIndex((m) => m.item.value === this.value);
        if (at >= 0) combo.hover(at);
      }
      paint2();
      this.popup.reposition();
      input.focus({ preventScroll: true });
    }
  };
  define("hd-enum", HdEnum);
  define("hd-select", HdSelect);

  // ui/kit/src/color/controller.ts
  var clamp01 = /* @__PURE__ */ __name((x) => Math.min(1, Math.max(0, x)), "clamp01");
  function rgbToHsv({ r, g, b }) {
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const d = max - min;
    let h2 = 0;
    if (d > 0) {
      if (max === r) h2 = (g - b) / d % 6;
      else if (max === g) h2 = (b - r) / d + 2;
      else h2 = (r - g) / d + 4;
      h2 /= 6;
      if (h2 < 0) h2 += 1;
    }
    return { h: h2, s: max === 0 ? 0 : d / max, v: max };
  }
  __name(rgbToHsv, "rgbToHsv");
  function hsvToRgb({ h: h2, s, v }) {
    const hh = (h2 % 1 + 1) % 1 * 6;
    const c = v * s;
    const x = c * (1 - Math.abs(hh % 2 - 1));
    const m = v - c;
    let rgb;
    if (hh < 1) rgb = [c, x, 0];
    else if (hh < 2) rgb = [x, c, 0];
    else if (hh < 3) rgb = [0, c, x];
    else if (hh < 4) rgb = [0, x, c];
    else if (hh < 5) rgb = [x, 0, c];
    else rgb = [c, 0, x];
    return { r: rgb[0] + m, g: rgb[1] + m, b: rgb[2] + m };
  }
  __name(hsvToRgb, "hsvToRgb");
  function rgbToHex({ r, g, b }) {
    const h2 = /* @__PURE__ */ __name((x) => Math.round(clamp01(x) * 255).toString(16).padStart(2, "0"), "h");
    return `#${h2(r)}${h2(g)}${h2(b)}`.toUpperCase();
  }
  __name(rgbToHex, "rgbToHex");
  function hexToRgb(text) {
    let t = text.trim().replace(/^#/, "");
    if (/^[0-9a-f]{3}$/i.test(t)) t = t.replace(/./g, (c) => c + c);
    if (!/^[0-9a-f]{6}$/i.test(t)) return null;
    const n = parseInt(t, 16);
    return { r: (n >> 16 & 255) / 255, g: (n >> 8 & 255) / 255, b: (n & 255) / 255 };
  }
  __name(hexToRgb, "hexToRgb");
  function wheelToHs(x, y) {
    const r = Math.hypot(x, y);
    let a = Math.atan2(-y, x) / (Math.PI * 2);
    if (a < 0) a += 1;
    return { h: a, s: clamp01(r) };
  }
  __name(wheelToHs, "wheelToHs");
  function hsToWheel(h2, s) {
    const a = h2 * Math.PI * 2;
    return { x: Math.cos(a) * s, y: -Math.sin(a) * s };
  }
  __name(hsToWheel, "hsToWheel");

  // ui/kit/src/color/element.ts
  var HdColor = class extends HdElement {
    static {
      __name(this, "HdColor");
    }
    static get observedAttributes() {
      return ["value", "label", "disabled", "wired", "invalid", "loading"];
    }
    button;
    swatch;
    hexEl;
    labelEl;
    outerLabel;
    popup = null;
    hsv = { h: 0, s: 0, v: 1 };
    get value() {
      const rgb = hexToRgb(this.str("value", "#FFFFFF"));
      return rgb ? rgbToHex(rgb) : "#FFFFFF";
    }
    set value(v) {
      const rgb = hexToRgb(v);
      if (rgb) this.setAttribute("value", rgbToHex(rgb));
    }
    build() {
      this.upgradeProperty("value");
      this.outerLabel = h("span", { class: "hd-field__label", "aria-hidden": "true" });
      this.labelEl = h("span", { class: "hd-choice__label" });
      this.swatch = h("span", { class: "hd-color__swatch", "aria-hidden": "true" });
      this.hexEl = h("span", { class: "hd-color__hex" });
      this.button = h("button", { type: "button", class: "hd-choice hd-color", "aria-haspopup": "dialog", "aria-expanded": "false" }, this.labelEl, this.swatch, this.hexEl);
      this.replaceChildren(this.outerLabel, this.button);
      this.button.addEventListener("click", () => this.popup?.open ? this.popup.close("api") : this.openPicker());
    }
    render() {
      const label = this.str("label");
      this.labelEl.textContent = label;
      this.labelEl.hidden = !label;
      this.outerLabel.textContent = label;
      const v = this.value;
      this.swatch.style.background = v;
      this.hexEl.textContent = this.getAttribute("wired") ? `← ${this.getAttribute("wired")}` : v;
      this.button.disabled = this.flag("disabled") || this.flag("loading");
      this.button.setAttribute("aria-label", `${label || "Colour"}: ${v}`);
      this.button.toggleAttribute("aria-readonly", this.hasAttribute("wired"));
      this.button.setAttribute("aria-invalid", String(this.hasAttribute("invalid")));
    }
    focus(options) {
      this.button.focus(options);
    }
    set(hex, final) {
      if (hex === this.value && !final) return;
      this.setAttribute("value", hex);
      this.emit("input");
      if (final) this.emit("change");
    }
    openPicker() {
      if (this.locked) return;
      const original = this.value;
      this.hsv = rgbToHsv(hexToRgb(original) ?? { r: 1, g: 1, b: 1 });
      const size = 150;
      const wheel = h("canvas", { class: "hd-color__wheel", width: String(size), height: String(size), tabindex: "0", role: "slider", "aria-label": "Hue and saturation" });
      const mark = h("span", { class: "hd-color__mark", "aria-hidden": "true" });
      const wheelBox = h("div", { class: "hd-color__wheelbox" }, wheel, mark);
      const val = document.createElement("hd-number");
      val.setAttribute("label", "Value");
      val.setAttribute("min", "0");
      val.setAttribute("max", "1");
      val.setAttribute("step", "0.01");
      val.setAttribute("slider", "");
      const hex = document.createElement("hd-text");
      hex.setAttribute("label", "Hex");
      hex.setAttribute("mono", "");
      const channel = /* @__PURE__ */ __name((c) => {
        const n = document.createElement("hd-number");
        n.setAttribute("label", c);
        n.setAttribute("min", "0");
        n.setAttribute("max", "255");
        n.setAttribute("step", "1");
        n.setAttribute("integer", "");
        return n;
      }, "channel");
      const cr = channel("R");
      const cg = channel("G");
      const cb = channel("B");
      const channels = [cr, cg, cb];
      const panel = h("div", { class: "hd-color__picker", role: "dialog", "aria-label": `${this.str("label") || "Colour"} picker` }, wheelBox, h("div", { class: "hd-color__fields" }, val, hex, ...channels));
      const drawWheel = /* @__PURE__ */ __name(() => {
        const ctx = wheel.getContext("2d");
        if (!ctx) return;
        const img = ctx.createImageData(size, size);
        const r = size / 2;
        for (let y = 0; y < size; y += 1) {
          for (let x = 0; x < size; x += 1) {
            const dx = (x - r + 0.5) / r;
            const dy = (y - r + 0.5) / r;
            const d = Math.hypot(dx, dy);
            const k = (y * size + x) * 4;
            if (d > 1) continue;
            const { h: hh, s } = wheelToHs(dx, dy);
            const rgb = hsvToRgb({ h: hh, s, v: this.hsv.v });
            img.data[k] = Math.round(rgb.r * 255);
            img.data[k + 1] = Math.round(rgb.g * 255);
            img.data[k + 2] = Math.round(rgb.b * 255);
            img.data[k + 3] = d > 0.985 ? Math.round((1 - d) / 0.015 * 255) : 255;
          }
        }
        ctx.putImageData(img, 0, 0);
      }, "drawWheel");
      const sync = /* @__PURE__ */ __name((from) => {
        const rgb = hsvToRgb(this.hsv);
        const code = rgbToHex(rgb);
        const p = hsToWheel(this.hsv.h, this.hsv.s);
        mark.style.left = `${50 + p.x * 50}%`;
        mark.style.top = `${50 + p.y * 50}%`;
        wheel.setAttribute("aria-valuetext", `hue ${Math.round(this.hsv.h * 360)} degrees, saturation ${Math.round(this.hsv.s * 100)}%`);
        if (from !== "value") val.value = this.hsv.v;
        if (from !== "hex") hex.value = code;
        if (from !== "rgb") {
          cr.value = Math.round(rgb.r * 255);
          cg.value = Math.round(rgb.g * 255);
          cb.value = Math.round(rgb.b * 255);
        }
        if (from === "value" || from === "init" || from === "hex" || from === "rgb") drawWheel();
        if (from !== "init") this.set(code, false);
      }, "sync");
      const fromWheel = /* @__PURE__ */ __name((ev) => {
        const r = wheel.getBoundingClientRect();
        const { h: hh, s } = wheelToHs((ev.clientX - r.left) / r.width * 2 - 1, (ev.clientY - r.top) / r.height * 2 - 1);
        this.hsv = { ...this.hsv, h: hh, s };
        sync("wheel");
      }, "fromWheel");
      wheel.addEventListener("pointerdown", (ev) => {
        wheel.setPointerCapture(ev.pointerId);
        fromWheel(ev);
      });
      wheel.addEventListener("pointermove", (ev) => {
        if (wheel.hasPointerCapture(ev.pointerId)) fromWheel(ev);
      });
      wheel.addEventListener("keydown", (ev) => {
        const step = ev.shiftKey ? 0.2 : 1;
        let { h: hh, s } = this.hsv;
        if (ev.key === "ArrowRight") hh = (hh + step / 72 + 1) % 1;
        else if (ev.key === "ArrowLeft") hh = (hh - step / 72 + 1) % 1;
        else if (ev.key === "ArrowUp") s = Math.min(1, s + 0.05 * step);
        else if (ev.key === "ArrowDown") s = Math.max(0, s - 0.05 * step);
        else return;
        ev.preventDefault();
        this.hsv = { ...this.hsv, h: hh, s };
        sync("wheel");
      });
      val.addEventListener("input", () => {
        this.hsv = { ...this.hsv, v: val.value };
        sync("value");
      });
      hex.addEventListener("change", () => {
        const rgb = hexToRgb(hex.value);
        if (!rgb) {
          hex.setAttribute("invalid", "not a hex colour");
          return;
        }
        hex.removeAttribute("invalid");
        this.hsv = rgbToHsv(rgb);
        sync("hex");
      });
      for (const n of channels) {
        n.addEventListener("input", () => {
          this.hsv = rgbToHsv({ r: cr.value / 255, g: cg.value / 255, b: cb.value / 255 });
          sync("rgb");
        });
      }
      this.popup = openFloating(panel, {
        anchor: this.button,
        side: "below",
        owner: this.button,
        restoreFocus: this.button,
        onClose: /* @__PURE__ */ __name((reason) => {
          this.popup = null;
          this.button.setAttribute("aria-expanded", "false");
          this.removeAttribute("data-open");
          if (reason === "escape") this.set(original, true);
          else if (this.value !== original) this.emit("change");
        }, "onClose")
      });
      this.button.setAttribute("aria-expanded", "true");
      this.setAttribute("data-open", "");
      sync("init");
      this.popup.reposition();
      wheel.focus({ preventScroll: true });
    }
  };
  define("hd-color", HdColor);

  // ui/kit/src/path/controller.ts
  function platformOf(navigatorPlatform, userAgent = "") {
    return /win/i.test(navigatorPlatform) || /windows/i.test(userAgent) ? "windows" : "posix";
  }
  __name(platformOf, "platformOf");
  function placeholderFor(platform, kind = "dir") {
    if (platform === "windows") return kind === "file" ? "C:\\path\\to\\file" : "C:\\path\\to\\folder";
    return kind === "file" ? "/path/to/file" : "/path/to/folder";
  }
  __name(placeholderFor, "placeholderFor");
  function normalisePath(text) {
    let t = text.trim();
    const m = /^(["'])(.*)\1$/s.exec(t);
    if (m) t = m[2].trim();
    return t;
  }
  __name(normalisePath, "normalisePath");
  function pathFromFileUri(uri, platform) {
    const m = /^file:\/\/([^/]*)(\/.*)$/i.exec(uri.trim());
    if (!m) return null;
    const host = m[1];
    let p;
    try {
      p = decodeURIComponent(m[2]);
    } catch {
      return null;
    }
    if (platform === "windows") {
      if (host) return `\\\\${host}${p.replace(/\//g, "\\")}`;
      return p.replace(/^\/([A-Za-z]:)/, "$1").replace(/\//g, "\\");
    }
    return host ? `//${host}${p}` : p;
  }
  __name(pathFromFileUri, "pathFromFileUri");
  function pathFromDrop(data, platform) {
    for (const line of (data.uriList ?? "").split(/\r?\n/)) {
      const l = line.trim();
      if (!l || l.startsWith("#")) continue;
      const p = pathFromFileUri(l, platform);
      if (p) return { path: p, nameOnly: false };
    }
    const text = normalisePath(data.text ?? "");
    if (text && !/[\r\n]/.test(text)) {
      const fromUri = pathFromFileUri(text, platform);
      return { path: fromUri ?? text, nameOnly: false };
    }
    const name = data.fileNames?.[0];
    if (name) return { path: name, nameOnly: true };
    return null;
  }
  __name(pathFromDrop, "pathFromDrop");

  // ui/kit/src/path/element.ts
  var HdPath = class extends HdElement {
    static {
      __name(this, "HdPath");
    }
    static get observedAttributes() {
      return ["value", "label", "kind", "placeholder", "disabled", "wired", "invalid", "loading"];
    }
    text;
    browse;
    picker;
    get value() {
      return this.built ? this.text.value : this.str("value");
    }
    set value(v) {
      if (this.built) this.text.value = normalisePath(v);
      else this.setAttribute("value", v);
    }
    build() {
      this.upgradeProperty("value");
      this.text = document.createElement("hd-text");
      this.text.setAttribute("mono", "");
      this.text.value = normalisePath(this.str("value"));
      this.browse = document.createElement("hd-button");
      this.browse.setAttribute("icon", "…");
      this.browse.setAttribute("tooltip", "Browse");
      this.browse.setAttribute("description", "Choose a file or folder");
      this.picker = h("input", { type: "file", class: "hd-path__picker", tabindex: "-1", "aria-hidden": "true" });
      this.replaceChildren(h("div", { class: "hd-path" }, this.text, this.browse), this.picker);
      this.setAttribute("data-hd-drop", "file uri text path");
      this.text.addEventListener("change", (ev) => {
        ev.stopPropagation();
        const clean = normalisePath(this.text.value);
        if (clean !== this.text.value) this.text.value = clean;
        this.removeAttribute("data-name-only");
        this.emit("change");
      });
      this.text.addEventListener("input", (ev) => {
        ev.stopPropagation();
        this.emit("input");
      });
      this.browse.addEventListener("click", () => {
        if (this.locked) return;
        const kind = this.str("kind", "file");
        if (!this.emit("hd-browse", { kind })) return;
        this.picker.toggleAttribute("webkitdirectory", kind === "dir");
        this.picker.click();
      });
      this.picker.addEventListener("change", () => {
        const f = this.picker.files?.[0];
        if (!f) return;
        const name = this.str("kind") === "dir" ? f.webkitRelativePath.split("/")[0] ?? f.name : f.name;
        this.setPath(name, true);
        this.picker.value = "";
      });
      this.addEventListener("hd-drop", (ev) => {
        const d = ev.detail;
        if (this.locked) return;
        const hit = pathFromDrop({ uriList: d.uriList, text: d.text, fileNames: d.files?.map((f) => f.name) }, platformOf(navigator.platform, navigator.userAgent));
        if (hit) this.setPath(hit.path, hit.nameOnly);
      });
    }
    setPath(p, nameOnly) {
      this.text.value = normalisePath(p);
      this.toggleAttribute("data-name-only", nameOnly);
      this.emit("input");
      this.emit("change");
    }
    render() {
      for (const a of ["label", "disabled", "wired", "invalid", "loading"]) {
        const v = this.getAttribute(a);
        if (v === null) this.text.removeAttribute(a);
        else this.text.setAttribute(a, v);
      }
      const kind = this.str("kind", "file") === "dir" ? "dir" : "file";
      this.text.setAttribute("placeholder", this.str("placeholder") || placeholderFor(platformOf(navigator.platform, navigator.userAgent), kind));
      if (this.flag("disabled") || this.flag("loading") || this.hasAttribute("wired")) this.browse.setAttribute("disabled", "");
      else this.browse.removeAttribute("disabled");
    }
    focus(options) {
      this.text.focus(options);
    }
  };
  define("hd-path", HdPath);

  // ui/kit/src/list/controller.ts
  var ListModel = class {
    static {
      __name(this, "ListModel");
    }
    items;
    activeId;
    filter = "";
    invert = false;
    sort = "none";
    reverse = false;
    constructor(items, activeId = null) {
      this.items = items.slice();
      this.activeId = activeId ?? items[0]?.id ?? null;
    }
    /** The rows a person sees, in the order they see them. */
    visible() {
      const q = this.filter.trim().toLocaleLowerCase();
      let rows = this.items.filter((it) => {
        if (!q) return true;
        const hit = it.label.toLocaleLowerCase().includes(q);
        return this.invert ? !hit : hit;
      });
      if (this.sort === "name") {
        rows = rows.slice().sort((a, b) => a.label.localeCompare(b.label, void 0, { sensitivity: "base", numeric: true }));
      }
      if (this.reverse) rows = rows.slice().reverse();
      return rows;
    }
    get canReorder() {
      return this.sort === "none" && !this.reverse && this.filter.trim() === "";
    }
    indexOf(id) {
      return this.items.findIndex((it) => it.id === id);
    }
    setActive(id) {
      if (id === null || this.indexOf(id) >= 0) this.activeId = id;
    }
    /** Move the active selection through the *visible* rows. */
    moveActive(dir) {
      const rows = this.visible().filter((r) => !r.disabled);
      if (rows.length === 0) return this.activeId;
      const at = rows.findIndex((r) => r.id === this.activeId);
      let next;
      if (dir === "first") next = 0;
      else if (dir === "last") next = rows.length - 1;
      else next = at < 0 ? dir > 0 ? 0 : rows.length - 1 : Math.max(0, Math.min(rows.length - 1, at + dir));
      this.activeId = rows[next].id;
      return this.activeId;
    }
    /** Move item `id` to index `to` of the underlying order. False when refused. */
    reorder(id, to) {
      if (!this.canReorder) return false;
      const from = this.indexOf(id);
      if (from < 0) return false;
      const target = Math.max(0, Math.min(this.items.length - 1, to));
      if (target === from) return false;
      const [item] = this.items.splice(from, 1);
      this.items.splice(target, 0, item);
      return true;
    }
    /** The move-up / move-down buttons, and Alt+Up / Alt+Down. */
    moveBy(id, delta) {
      const from = this.indexOf(id);
      return from >= 0 && this.reorder(id, from + delta);
    }
    /**
     * Where a row dragged by `id` lands when dropped at pointer offset `y` within the list,
     * given each visible row's height -- the index in the underlying order. Rows are the
     * visible ones; reorder is only possible when visible order equals the real order.
     */
    dropIndex(y, rowHeights) {
      let acc = 0;
      for (let i = 0; i < rowHeights.length; i += 1) {
        const h2 = rowHeights[i];
        if (y < acc + h2 / 2) return i;
        acc += h2;
      }
      return Math.max(0, rowHeights.length - 1);
    }
    /** Add after the active row (Blender adds at the end; the active row is where the
     *  person is looking, which is Blender's own rule for new slots). */
    add(item) {
      const at = this.activeId ? this.indexOf(this.activeId) : -1;
      this.items.splice(at < 0 ? this.items.length : at + 1, 0, item);
      this.activeId = item.id;
    }
    /** Remove `id`; the active row moves to the one that took its place, or the one above. */
    remove(id) {
      const at = this.indexOf(id);
      if (at < 0) return false;
      this.items.splice(at, 1);
      if (this.activeId === id) {
        const next = this.items[Math.min(at, this.items.length - 1)];
        this.activeId = next ? next.id : null;
      }
      return true;
    }
    rename(id, label) {
      const at = this.indexOf(id);
      const text = label.trim();
      if (at < 0 || !text) return false;
      this.items[at].label = text;
      return true;
    }
  };

  // ui/kit/src/list/element.ts
  var HdList = class extends HdElement {
    static {
      __name(this, "HdList");
    }
    static get observedAttributes() {
      return ["label", "disabled", "loading", "empty"];
    }
    model = new ListModel([]);
    listbox;
    side;
    filterRow;
    filterToggle;
    filterText;
    emptyEl;
    rowEls = /* @__PURE__ */ new Map();
    drag = null;
    counter = 1;
    get items() {
      return this.model.items;
    }
    set items(rows) {
      this.model = new ListModel(rows, this.model.activeId);
      if (this.built) this.render();
    }
    get active() {
      return this.model.activeId;
    }
    build() {
      this.upgradeProperty("items");
      if (this.model.items.length === 0) {
        const rows = [...this.querySelectorAll(":scope > hd-item")].map((el, i) => ({ id: el.id || `item-${i + 1}`, label: ownText(el), icon: el.getAttribute("icon") ?? void 0, detail: el.getAttribute("detail") ?? void 0, disabled: el.hasAttribute("disabled") }));
        this.model = new ListModel(rows);
      }
      if (this.hasAttribute("active")) this.model.activeId = this.str("active") || null;
      this.counter = this.model.items.length + 1;
      this.replaceChildren();
      const label = this.str("label");
      const labelId = uid("hd-list-label");
      if (label) this.append(h("div", { class: "hd-field__label hd-list__title", id: labelId, text: label }));
      this.listbox = h("div", { class: "hd-list__rows", role: "listbox", tabindex: "0", "aria-labelledby": label ? labelId : null, "aria-label": label ? null : "List" });
      this.emptyEl = h("div", { class: "hd-list__empty k-panel__empty" });
      this.side = h("div", { class: "hd-list__side" });
      const btn = /* @__PURE__ */ __name((icon, tip, shortcut, fn) => {
        const b = h("button", { type: "button", class: "btn icon ghost", tooltip: tip, shortcut, "aria-label": tip, text: icon });
        b.addEventListener("click", fn);
        return b;
      }, "btn");
      if (this.flag("addable")) this.side.append(btn("+", "Add", "Insert", () => this.addRow()));
      if (this.flag("removable")) this.side.append(btn("−", "Remove", "Delete", () => this.removeActive()));
      if (this.flag("reorderable")) {
        this.side.append(btn("▴", "Move Up", "Alt+Up", () => this.moveActive(-1)));
        this.side.append(btn("▾", "Move Down", "Alt+Down", () => this.moveActive(1)));
      }
      this.filterToggle = h("button", { type: "button", class: "hd-list__filtertoggle", "aria-expanded": "false", tooltip: "Filter", shortcut: "Ctrl+F", text: "▸ Filter" });
      this.filterText = document.createElement("hd-text");
      this.filterText.setAttribute("placeholder", "Filter by name");
      this.filterText.setAttribute("label", "🔍");
      const toggle = /* @__PURE__ */ __name((text, tip, get, set) => {
        const b = h("button", { type: "button", class: "btn icon ghost hd-toggle", "aria-pressed": "false", tooltip: tip, "aria-label": tip, text });
        b.addEventListener("click", () => {
          set(!get());
          b.setAttribute("aria-pressed", String(get()));
          this.render();
        });
        return b;
      }, "toggle");
      this.filterRow = h(
        "div",
        { class: "hd-list__filter", hidden: true },
        this.filterText,
        toggle("⇄", "Invert", () => this.model.invert, (v) => this.model.invert = v),
        toggle("A↓", "Sort by Name", () => this.model.sort === "name", (v) => this.model.sort = v ? "name" : "none"),
        toggle("⇅", "Reverse", () => this.model.reverse, (v) => this.model.reverse = v)
      );
      const body = h("div", { class: "hd-list__body" }, h("div", { class: "hd-list__main" }, this.listbox, this.emptyEl), this.side);
      this.append(body);
      if (this.flag("filterable")) this.append(this.filterToggle, this.filterRow);
      this.filterToggle.addEventListener("click", () => this.showFilter(this.filterRow.hidden));
      this.filterText.addEventListener("input", () => {
        this.model.filter = this.filterText.input.value;
        this.render();
      });
      this.listbox.addEventListener("keydown", (ev) => this.key(ev));
      this.addEventListener("keydown", (ev) => {
        if ((ev.ctrlKey || ev.metaKey) && (ev.key === "f" || ev.key === "F") && this.flag("filterable")) {
          ev.preventDefault();
          this.showFilter(true);
          this.filterText.beginEdit();
        }
      });
    }
    showFilter(open2) {
      this.filterRow.hidden = !open2;
      this.filterToggle.setAttribute("aria-expanded", String(open2));
      this.filterToggle.textContent = `${open2 ? "▾" : "▸"} Filter`;
    }
    render() {
      const rows = this.model.visible();
      this.rowEls.clear();
      this.listbox.replaceChildren();
      const reorder = this.flag("reorderable") && this.model.canReorder && !this.locked;
      for (const r of rows) {
        const el = h(
          "div",
          { class: "hd-list__row", role: "option", id: `${this.id || "hd-list"}-${r.id}`, "data-id": r.id, "aria-selected": String(r.id === this.model.activeId), "aria-disabled": r.disabled ? "true" : null },
          h("span", { class: "hd-list__icon", "aria-hidden": "true", text: r.icon ?? "" }),
          h("span", { class: "hd-list__label", text: r.label }),
          h("span", { class: "hd-list__detail", text: r.detail ?? "" }),
          this.flag("reorderable") ? h("span", { class: "hd-list__grip", "aria-hidden": "true", "data-disabled": reorder ? null : "true", text: "⁙⁙" }) : null
        );
        el.addEventListener("click", () => {
          if (r.disabled || this.locked) return;
          this.model.setActive(r.id);
          this.render();
          this.listbox.focus({ preventScroll: true });
          this.changedList();
        });
        el.addEventListener("dblclick", () => this.rename(r.id));
        el.querySelector(".hd-list__grip")?.addEventListener("pointerdown", (ev) => this.startDrag(ev, r.id));
        this.rowEls.set(r.id, el);
        this.listbox.append(el);
      }
      const active = this.model.activeId ? this.rowEls.get(this.model.activeId) : void 0;
      if (active) this.listbox.setAttribute("aria-activedescendant", active.id);
      else this.listbox.removeAttribute("aria-activedescendant");
      const empty = rows.length === 0;
      this.emptyEl.hidden = !empty;
      this.emptyEl.textContent = this.model.items.length === 0 ? this.str("empty", "Nothing here yet.") : "No row matches the filter.";
      this.listbox.hidden = empty;
      this.listbox.tabIndex = this.flag("disabled") ? -1 : 0;
      this.listbox.setAttribute("aria-disabled", String(this.flag("disabled")));
      this.listbox.setAttribute("aria-busy", String(this.flag("loading")));
      for (const b of this.side.querySelectorAll("button")) b.disabled = this.locked;
    }
    changedList() {
      this.emit("change", { order: this.model.items.map((i) => i.id), active: this.model.activeId });
    }
    key(ev) {
      if (this.locked) return;
      const reorder = this.flag("reorderable");
      let handled = true;
      if (ev.altKey && (ev.key === "ArrowUp" || ev.key === "ArrowDown") && reorder) this.moveActive(ev.key === "ArrowUp" ? -1 : 1);
      else if (ev.key === "ArrowUp") this.moveSelection(-1);
      else if (ev.key === "ArrowDown") this.moveSelection(1);
      else if (ev.key === "Home") this.moveSelection("first");
      else if (ev.key === "End") this.moveSelection("last");
      else if (ev.key === "F2" && this.model.activeId) this.rename(this.model.activeId);
      else if ((ev.key === "Delete" || ev.key === "Backspace") && this.flag("removable")) this.removeActive();
      else if (ev.key === "Insert" && this.flag("addable")) this.addRow();
      else handled = false;
      if (handled) {
        ev.preventDefault();
        ev.stopPropagation();
      }
    }
    moveSelection(dir) {
      this.model.moveActive(dir);
      this.render();
      this.changedList();
    }
    moveActive(delta) {
      const id = this.model.activeId;
      if (!id || !this.model.moveBy(id, delta)) return;
      this.render();
      this.changedList();
    }
    addRow(label) {
      const id = `new-${this.counter}`;
      const row = { id, label: label ?? `Item ${this.counter}` };
      this.counter += 1;
      if (!this.emit("hd-add", { row })) return;
      this.model.add(row);
      this.render();
      this.changedList();
      this.listbox.focus({ preventScroll: true });
    }
    removeActive() {
      const id = this.model.activeId;
      if (!id) return;
      if (!this.emit("hd-remove", { id })) return;
      this.model.remove(id);
      this.render();
      this.changedList();
      this.listbox.focus({ preventScroll: true });
    }
    /** Double-click or F2: the row's name becomes a text field, already editing. */
    rename(id) {
      const el = this.rowEls.get(id);
      const row = this.model.items.find((r) => r.id === id);
      if (!el || !row || this.locked || row.disabled) return;
      const labelEl = el.querySelector(".hd-list__label");
      if (!labelEl) return;
      const field = document.createElement("hd-text");
      field.value = row.label;
      field.classList.add("hd-list__rename");
      labelEl.replaceWith(field);
      const done = /* @__PURE__ */ __name(() => {
        this.model.rename(id, field.value);
        this.render();
        this.changedList();
        this.listbox.focus({ preventScroll: true });
      }, "done");
      field.addEventListener("change", done, { once: true });
      field.input.addEventListener("blur", () => window.setTimeout(() => field.isConnected && done(), 0), { once: true });
      field.beginEdit();
    }
    // ---- drag to reorder ------------------------------------------------------------------
    startDrag(ev, id) {
      if (ev.button !== 0 || this.locked || !this.model.canReorder) return;
      ev.preventDefault();
      ev.stopPropagation();
      const indicator = h("div", { class: "hd-list__drop", "aria-hidden": "true" });
      this.listbox.append(indicator);
      this.drag = { id, pointer: ev.pointerId, startY: ev.clientY, indicator };
      this.rowEls.get(id)?.setAttribute("data-hd-dragging", "");
      const move = /* @__PURE__ */ __name((e) => this.dragMove(e), "move");
      const up = /* @__PURE__ */ __name((e) => {
        document.removeEventListener("pointermove", move);
        document.removeEventListener("pointerup", up);
        this.dragEnd(e);
      }, "up");
      document.addEventListener("pointermove", move);
      document.addEventListener("pointerup", up);
    }
    dropAt(clientY) {
      const rows = [...this.rowEls.values()];
      const top = this.listbox.getBoundingClientRect().top + (rows[0]?.offsetTop ?? 0) - this.listbox.scrollTop;
      return this.model.dropIndex(clientY - top, rows.map((r) => r.offsetHeight));
    }
    dragMove(ev) {
      if (!this.drag) return;
      const i = this.dropAt(ev.clientY);
      const target = [...this.rowEls.values()][i];
      if (target) this.drag.indicator.style.top = `${target.offsetTop}px`;
    }
    dragEnd(ev) {
      const d = this.drag;
      this.drag = null;
      if (!d) return;
      d.indicator.remove();
      this.rowEls.get(d.id)?.removeAttribute("data-hd-dragging");
      if (Math.abs(ev.clientY - d.startY) < 3) return;
      if (this.model.reorder(d.id, this.dropAt(ev.clientY))) {
        this.model.setActive(d.id);
        this.render();
        this.changedList();
      }
    }
  };
  var HdItem = class extends HTMLElement {
    static {
      __name(this, "HdItem");
    }
  };
  define("hd-list", HdList);
  define("hd-item", HdItem);

  // ui/kit/src/tree/controller.ts
  var TreeModel = class {
    static {
      __name(this, "TreeModel");
    }
    roots;
    expanded = /* @__PURE__ */ new Set();
    selectedId = null;
    constructor(roots, expanded = []) {
      this.roots = roots;
      for (const id of expanded) this.expanded.add(id);
    }
    /** The rows showing, depth-first, collapsed branches skipped. */
    rows(filter = "") {
      const q = filter.trim().toLocaleLowerCase();
      const out = [];
      const matches = /* @__PURE__ */ __name((n) => !q || n.label.toLocaleLowerCase().includes(q) || (n.children ?? []).some(matches), "matches");
      const walk = /* @__PURE__ */ __name((nodes, depth2, parentId) => {
        const shown = nodes.filter(matches);
        shown.forEach((node, i) => {
          const hasChildren = (node.children?.length ?? 0) > 0;
          const expanded = hasChildren && (this.expanded.has(node.id) || !!q);
          out.push({ node, depth: depth2, parentId, hasChildren, expanded, pos: i + 1, size: shown.length });
          if (expanded) walk(node.children ?? [], depth2 + 1, node.id);
        });
      }, "walk");
      walk(this.roots, 0, null);
      return out;
    }
    find(id) {
      const walk = /* @__PURE__ */ __name((nodes, parent) => {
        for (const n of nodes) {
          if (n.id === id) return { node: n, parent };
          const hit = walk(n.children ?? [], n);
          if (hit) return hit;
        }
        return null;
      }, "walk");
      return walk(this.roots, null);
    }
    toggle(id, recursive = false) {
      const hit = this.find(id);
      if (!hit || !hit.node.children?.length) return;
      const open2 = !this.expanded.has(id);
      const apply = /* @__PURE__ */ __name((n) => {
        if (!n.children?.length) return;
        if (open2) this.expanded.add(n.id);
        else this.expanded.delete(n.id);
        if (recursive) n.children.forEach(apply);
      }, "apply");
      apply(hit.node);
    }
    expand(id) {
      if (this.find(id)?.node.children?.length) this.expanded.add(id);
    }
    collapse(id) {
      this.expanded.delete(id);
    }
    /** One key, applied to the selection. Returns the new selection. */
    key(key, filter = "") {
      const rows = this.rows(filter).filter((r) => !r.node.disabled);
      if (rows.length === 0) return this.selectedId;
      const at = rows.findIndex((r) => r.node.id === this.selectedId);
      const row = rows[at];
      switch (key) {
        case "ArrowDown":
          this.selectedId = rows[at < 0 ? 0 : Math.min(rows.length - 1, at + 1)].node.id;
          break;
        case "ArrowUp":
          this.selectedId = rows[at < 0 ? 0 : Math.max(0, at - 1)].node.id;
          break;
        case "Home":
          this.selectedId = rows[0].node.id;
          break;
        case "End":
          this.selectedId = rows[rows.length - 1].node.id;
          break;
        case "ArrowRight":
          if (!row) break;
          if (row.hasChildren && !row.expanded) this.expand(row.node.id);
          else if (row.hasChildren) this.selectedId = rows[at + 1].node.id;
          break;
        case "ArrowLeft":
          if (!row) break;
          if (row.hasChildren && row.expanded) this.collapse(row.node.id);
          else if (row.parentId) this.selectedId = row.parentId;
          break;
        case "*": {
          const parent = row?.parentId ? this.find(row.parentId)?.node.children : this.roots;
          for (const sib of parent ?? []) this.expand(sib.id);
          break;
        }
      }
      return this.selectedId;
    }
  };

  // ui/kit/src/tree/element.ts
  function parse(host) {
    const expanded = [];
    let n = 0;
    const walk = /* @__PURE__ */ __name((el) => [...el.children].filter((c) => c.tagName.toLowerCase() === "hd-node").map((c) => {
      n += 1;
      const id = c.id || `node-${n}`;
      if (c.hasAttribute("expanded")) expanded.push(id);
      const kids = walk(c);
      return { id, label: c.getAttribute("label") ?? "", icon: c.getAttribute("icon") ?? void 0, detail: c.getAttribute("detail") ?? void 0, disabled: c.hasAttribute("disabled"), children: kids.length ? kids : void 0 };
    }), "walk");
    return { nodes: walk(host), expanded };
  }
  __name(parse, "parse");
  var HdTree = class extends HdElement {
    static {
      __name(this, "HdTree");
    }
    static get observedAttributes() {
      return ["label", "disabled", "loading"];
    }
    model = new TreeModel([]);
    tree;
    filter = "";
    get nodes() {
      return this.model.roots;
    }
    set nodes(v) {
      this.model = new TreeModel(v, this.model.expanded);
      if (this.built) this.render();
    }
    get selected() {
      return this.model.selectedId;
    }
    build() {
      this.upgradeProperty("nodes");
      if (this.model.roots.length === 0) {
        const { nodes, expanded } = parse(this);
        this.model = new TreeModel(nodes, expanded);
      }
      if (this.hasAttribute("selected")) this.model.selectedId = this.str("selected") || null;
      this.replaceChildren();
      const label = this.str("label");
      const labelId = uid("hd-tree-label");
      if (label) this.append(h("div", { class: "hd-field__label hd-list__title", id: labelId, text: label }));
      if (this.flag("filterable")) {
        const f = document.createElement("hd-text");
        f.setAttribute("placeholder", "Search");
        f.setAttribute("label", "🔍");
        f.addEventListener("input", () => {
          this.filter = f.input.value;
          this.render();
        });
        this.append(f);
      }
      this.tree = h("div", { class: "hd-tree", role: "tree", tabindex: "0", "aria-labelledby": label ? labelId : null, "aria-label": label ? null : "Tree" });
      this.append(this.tree);
      this.tree.addEventListener("keydown", (ev) => {
        if (this.locked) return;
        if (ev.key === "Enter" && this.model.selectedId) {
          ev.preventDefault();
          this.emit("hd-activate", { id: this.model.selectedId });
          return;
        }
        if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "*"].includes(ev.key)) return;
        ev.preventDefault();
        ev.stopPropagation();
        const before = this.model.selectedId;
        this.model.key(ev.key, this.filter);
        this.render();
        if (this.model.selectedId !== before) this.emit("change", { selected: this.model.selectedId });
      });
      this.tree.addEventListener("focus", () => {
        if (!this.model.selectedId) {
          const first = this.model.rows(this.filter)[0];
          if (first) {
            this.model.selectedId = first.node.id;
            this.render();
          }
        }
      });
    }
    render() {
      const rows = this.model.rows(this.filter);
      this.tree.replaceChildren();
      for (const r of rows) {
        const node = r.node;
        const twisty = h("span", { class: "hd-tree__twisty", "aria-hidden": "true", text: r.hasChildren ? r.expanded ? "▾" : "▸" : "" });
        const row = h(
          "div",
          {
            class: "hd-tree__row",
            role: "treeitem",
            id: `${this.id || "hd-tree"}-${node.id}`,
            "data-id": node.id,
            "aria-level": String(r.depth + 1),
            "aria-setsize": String(r.size),
            "aria-posinset": String(r.pos),
            "aria-expanded": r.hasChildren ? String(r.expanded) : null,
            "aria-selected": String(node.id === this.model.selectedId),
            "aria-disabled": node.disabled ? "true" : null,
            style: `--hd-depth: ${r.depth}`
          },
          twisty,
          h("span", { class: "hd-tree__icon", "aria-hidden": "true", text: node.icon ?? "" }),
          h("span", { class: "hd-tree__label", text: node.label }),
          h("span", { class: "hd-list__detail", text: node.detail ?? "" })
        );
        twisty.addEventListener("click", (ev) => {
          ev.stopPropagation();
          if (this.locked) return;
          this.model.toggle(node.id, ev.shiftKey);
          this.render();
        });
        row.addEventListener("click", () => {
          if (node.disabled || this.locked) return;
          this.model.selectedId = node.id;
          this.render();
          this.tree.focus({ preventScroll: true });
          this.emit("change", { selected: node.id });
        });
        row.addEventListener("dblclick", () => {
          if (!node.disabled && !this.locked) this.emit("hd-activate", { id: node.id });
        });
        this.tree.append(row);
      }
      const sel = this.model.selectedId ? this.tree.querySelector(`[data-id="${CSS.escape(this.model.selectedId)}"]`) : null;
      if (sel) {
        this.tree.setAttribute("aria-activedescendant", sel.id);
        sel.scrollIntoView?.({ block: "nearest" });
      } else this.tree.removeAttribute("aria-activedescendant");
      this.tree.tabIndex = this.flag("disabled") ? -1 : 0;
      this.tree.setAttribute("aria-disabled", String(this.flag("disabled")));
      this.tree.setAttribute("aria-busy", String(this.flag("loading")));
    }
  };
  var HdNode = class extends HTMLElement {
    static {
      __name(this, "HdNode");
    }
  };
  define("hd-tree", HdTree);
  define("hd-node", HdNode);

  // ui/kit/src/grid/controller.ts
  function gridMove(index, key, columns, count, pageRows = 3) {
    if (count <= 0) return -1;
    const cols = Math.max(1, Math.floor(columns));
    const i = index < 0 ? 0 : Math.min(index, count - 1);
    switch (key) {
      case "ArrowRight":
        return Math.min(count - 1, i + 1);
      case "ArrowLeft":
        return Math.max(0, i - 1);
      case "ArrowDown":
        return i + cols < count ? i + cols : i;
      case "ArrowUp":
        return i - cols >= 0 ? i - cols : i;
      case "Home":
        return 0;
      case "End":
        return count - 1;
      case "PageDown":
        return Math.min(count - 1, i + cols * pageRows);
      case "PageUp":
        return Math.max(0, i - cols * pageRows);
      default:
        return i;
    }
  }
  __name(gridMove, "gridMove");
  function columnsFor(width, tile, gap) {
    if (tile <= 0) return 1;
    return Math.max(1, Math.floor((width + gap) / (tile + gap)));
  }
  __name(columnsFor, "columnsFor");

  // ui/kit/src/grid/element.ts
  var HdAssetGrid = class extends HdElement {
    static {
      __name(this, "HdAssetGrid");
    }
    static get observedAttributes() {
      return ["label", "disabled", "loading"];
    }
    assets = [];
    selected = -1;
    grid;
    tiles = [];
    build() {
      this.upgradeProperty("assets");
      if (this.assets.length === 0) {
        this.assets = [...this.querySelectorAll(":scope > hd-asset")].map((a, i) => ({ id: a.id || `asset-${i + 1}`, label: ownText(a), icon: a.getAttribute("icon") ?? void 0, detail: a.getAttribute("detail") ?? void 0, kind: a.getAttribute("kind") ?? "asset", disabled: a.hasAttribute("disabled") }));
      }
      if (this.hasAttribute("selected")) {
        const s = this.str("selected");
        const byId2 = this.assets.findIndex((a) => a.id === s);
        this.selected = byId2 >= 0 ? byId2 : Number.isInteger(Number(s)) ? Number(s) : -1;
      }
      this.replaceChildren();
      const label = this.str("label");
      const labelId = uid("hd-grid-label");
      if (label) this.append(h("div", { class: "hd-field__label hd-list__title", id: labelId, text: label }));
      this.grid = h("div", { class: "hd-grid", role: "listbox", tabindex: "0", "aria-orientation": "horizontal", "aria-labelledby": label ? labelId : null, "aria-label": label ? null : "Assets" });
      this.append(this.grid);
      this.grid.addEventListener("keydown", (ev) => {
        if (this.locked) return;
        if (ev.key === "Enter" && this.selected >= 0) {
          ev.preventDefault();
          this.emit("hd-activate", { id: this.assets[this.selected]?.id });
          return;
        }
        const cols = this.columns();
        const next = gridMove(this.selected, ev.key, cols, this.assets.length);
        if (next === this.selected && !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(ev.key)) return;
        ev.preventDefault();
        this.select(next);
      });
      this.grid.addEventListener("focus", () => {
        if (this.selected < 0 && this.assets.length) this.select(0);
      });
    }
    columns() {
      const first = this.tiles[0];
      if (!first) return 1;
      const gap = parseFloat(getComputedStyle(this.grid).columnGap) || 0;
      return columnsFor(this.grid.clientWidth, first.offsetWidth, gap);
    }
    select(i) {
      if (i < 0 || i >= this.assets.length || this.assets[i]?.disabled) return;
      const changed = i !== this.selected;
      this.selected = i;
      this.render();
      if (changed) this.emit("change", { selected: this.assets[i]?.id });
    }
    render() {
      this.grid.replaceChildren();
      this.tiles = this.assets.map((a, i) => {
        const tile = h(
          "div",
          { class: "hd-grid__tile", role: "option", id: `${this.id || "hd-grid"}-${a.id}`, "aria-selected": String(i === this.selected), "aria-disabled": a.disabled ? "true" : null, "data-hd-drag": JSON.stringify({ kind: a.kind ?? "asset", id: a.id, label: a.label }), tooltip: a.label, description: a.detail ?? null },
          h("span", { class: "hd-grid__thumb", "aria-hidden": "true", text: a.icon ?? a.label.charAt(0).toUpperCase() }),
          h("span", { class: "hd-grid__name", text: a.label })
        );
        tile.addEventListener("click", () => {
          if (this.locked) return;
          this.select(i);
          this.grid.focus({ preventScroll: true });
        });
        tile.addEventListener("dblclick", () => {
          if (!a.disabled && !this.locked) this.emit("hd-activate", { id: a.id });
        });
        this.grid.append(tile);
        return tile;
      });
      const sel = this.tiles[this.selected];
      if (sel) {
        this.grid.setAttribute("aria-activedescendant", sel.id);
        sel.scrollIntoView?.({ block: "nearest" });
      } else this.grid.removeAttribute("aria-activedescendant");
      this.grid.tabIndex = this.flag("disabled") ? -1 : 0;
      this.grid.setAttribute("aria-disabled", String(this.flag("disabled")));
      this.grid.setAttribute("aria-busy", String(this.flag("loading")));
    }
  };
  var HdAsset = class extends HTMLElement {
    static {
      __name(this, "HdAsset");
    }
  };
  define("hd-asset-grid", HdAssetGrid);
  define("hd-asset", HdAsset);

  // ui/kit/src/growing/controller.ts
  var GrowingList = class {
    static {
      __name(this, "GrowingList");
    }
    entries;
    constructor(entries = []) {
      this.entries = entries.slice();
    }
    /** Every row the view draws: each entry, then the one ghost. */
    rows() {
      return [...this.entries, { kind: "ghost" }];
    }
    /** The ghost received text: it becomes a real entry and a new ghost appears behind it. */
    fillGhost(value) {
      if (value === "") return -1;
      this.entries.push({ kind: "typed", value });
      return this.entries.length - 1;
    }
    /** A typed entry changed. It is not removed while it is being typed in, even when
     *  emptied -- `settle`, on leaving the row, is what removes an empty one. */
    edit(index, value) {
      const e = this.entries[index];
      if (e && e.kind === "typed") e.value = value;
    }
    /** Called when focus leaves row `index`: an empty typed entry is removed. */
    settle(index) {
      const e = this.entries[index];
      if (e && e.kind === "typed" && e.value.trim() === "") {
        this.entries.splice(index, 1);
        return true;
      }
      return false;
    }
    /** A link arrived: it fills a slot like typed text does, at the end. */
    wire(source) {
      this.entries.push({ kind: "wired", source });
      return this.entries.length - 1;
    }
    remove(index) {
      this.entries.splice(index, 1);
    }
    /** The value a consumer reads: typed strings as they are, wired entries as their source
     *  (the run resolves them). */
    values() {
      return this.entries.map((e) => e.kind === "typed" ? e.value : `@${e.source}`);
    }
  };

  // ui/kit/src/growing/element.ts
  var HdGrowingList = class extends HdElement {
    static {
      __name(this, "HdGrowingList");
    }
    static get observedAttributes() {
      return ["label", "placeholder", "disabled", "wired", "invalid", "loading"];
    }
    model = new GrowingList();
    rows;
    labelEl;
    get value() {
      return this.model.values();
    }
    set value(v) {
      this.model = new GrowingList(v.map((s) => s.startsWith("@") ? { kind: "wired", source: s.slice(1) } : { kind: "typed", value: s }));
      if (this.built) this.render();
    }
    /** A link arrived. */
    wire(source) {
      this.model.wire(source);
      this.render();
      this.emit("change");
    }
    build() {
      this.upgradeProperty("value");
      this.labelEl = h("span", { class: "hd-field__label" });
      this.rows = h("div", { class: "hd-grow", role: "list" });
      this.replaceChildren(this.labelEl, this.rows);
    }
    render(focusIndex = -1) {
      this.labelEl.textContent = this.str("label");
      this.rows.replaceChildren();
      this.rows.setAttribute("aria-label", this.str("label") || "List");
      const inert = this.locked;
      this.model.rows().forEach((e, i) => {
        if (e.kind === "wired") {
          this.rows.append(h("div", { class: "hd-grow__row hd-grow__wired", role: "listitem", tooltip: `Wired from ${e.source}` }, h("span", { class: "hd-grow__link", "aria-hidden": "true", text: "◆" }), h("span", { class: "hd-grow__src", text: e.source })));
          return;
        }
        const ghost = e.kind === "ghost";
        const input = h("input", { type: "text", class: `input hd-grow__input${ghost ? " is-ghost" : ""}`, spellcheck: "false", autocomplete: "off", placeholder: ghost ? this.str("placeholder", "Add an item") : "", "aria-label": ghost ? `New ${this.str("label") || "item"}` : `${this.str("label") || "Item"} ${i + 1}`, disabled: this.flag("disabled") || this.flag("loading"), readonly: this.hasAttribute("wired") });
        input.value = ghost ? "" : e.value;
        input.addEventListener("input", (ev) => {
          ev.stopPropagation();
          if (inert) return;
          if (ghost) {
            const at = this.model.fillGhost(input.value);
            if (at >= 0) {
              this.render(at);
              this.emit("change");
            }
          } else {
            this.model.edit(i, input.value);
            this.emit("input");
          }
        });
        input.addEventListener("change", (ev) => {
          ev.stopPropagation();
          this.emit("change");
        });
        input.addEventListener("blur", () => {
          if (!ghost && this.model.settle(i)) {
            this.render();
            this.emit("change");
          }
        });
        input.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter" && !ev.isComposing) {
            ev.preventDefault();
            const inputs = [...this.rows.querySelectorAll("input")];
            const k = inputs.indexOf(input);
            inputs[k + 1]?.focus();
          }
        });
        this.rows.append(h("div", { class: "hd-grow__row", role: "listitem" }, input));
        if (i === focusIndex) {
          queueMicrotask(() => {
            input.focus();
            input.setSelectionRange(input.value.length, input.value.length);
          });
        }
      });
    }
  };
  define("hd-growing-list", HdGrowingList);

  // ui/kit/src/panel/controller.ts
  var PanelStack = class {
    static {
      __name(this, "PanelStack");
    }
    panels;
    constructor(panels) {
      this.panels = panels.map((p) => ({ ...p }));
    }
    get(id) {
      return this.panels.find((p) => p.id === id);
    }
    toggle(id) {
      const p = this.get(id);
      if (!p) return false;
      p.collapsed = !p.collapsed;
      return !p.collapsed;
    }
    set(id, open2) {
      const p = this.get(id);
      if (p) p.collapsed = !open2;
    }
    /** Ctrl+click: this one open, every other one in the stack closed. */
    soloOpen(id) {
      for (const p of this.panels) p.collapsed = p.id !== id;
    }
    /** A drag across headers: every header crossed takes the state the first one took. */
    dragSet(ids, open2) {
      for (const id of ids) this.set(id, open2);
    }
    pin(id, on) {
      const p = this.get(id);
      if (!p) return false;
      p.pinned = on ?? !p.pinned;
      return p.pinned;
    }
    /** The grip: move `id` to position `to` in the stack. */
    move(id, to) {
      const from = this.panels.findIndex((p2) => p2.id === id);
      if (from < 0) return false;
      const target = Math.max(0, Math.min(this.panels.length - 1, to));
      if (target === from) return false;
      const [p] = this.panels.splice(from, 1);
      this.panels.splice(target, 0, p);
      return true;
    }
    /** The panels a sidebar shows under `tab`: its own, plus every pinned one, pinned first
     *  so a pinned panel stays where the eye left it when the tab changes. */
    visibleFor(tab) {
      const own2 = this.panels.filter((p) => !p.pinned && (p.tab === tab || p.tab === ""));
      const pinned = this.panels.filter((p) => p.pinned);
      return [...pinned, ...own2];
    }
    order() {
      return this.panels.map((p) => p.id);
    }
  };

  // ui/kit/src/panel/element.ts
  var dragSetting = null;
  var hoveredHeader = null;
  var installed3 = false;
  function install3() {
    if (installed3) return;
    installed3 = true;
    document.addEventListener("pointerup", () => dragSetting = null);
    document.addEventListener("keydown", (ev) => {
      if (ev.defaultPrevented || ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey) return;
      if (ev.key !== "a" && ev.key !== "A" || !hoveredHeader || !hoveredHeader.isConnected) return;
      const a = document.activeElement;
      if (a && (a instanceof HTMLInputElement || a instanceof HTMLTextAreaElement) && !a.readOnly) return;
      ev.preventDefault();
      hoveredHeader.toggle();
    });
  }
  __name(install3, "install");
  var HdPanel = class _HdPanel extends HdElement {
    static {
      __name(this, "HdPanel");
    }
    static get observedAttributes() {
      return ["heading", "collapsed", "pinned", "disabled", "loading"];
    }
    header;
    toggleButton;
    body;
    pinButton = null;
    grip = null;
    twisty;
    titleEl;
    get open() {
      return !this.flag("collapsed");
    }
    set open(on) {
      this.setFlag("collapsed", !on);
    }
    get pinned() {
      return this.flag("pinned");
    }
    build() {
      install3();
      const content = [...this.childNodes];
      const headerExtras = content.filter((n) => n instanceof Element && n.getAttribute("slot") === "header");
      const bodyContent = content.filter((n) => !headerExtras.includes(n));
      this.classList.add("k-panel");
      if (this.parentElement?.closest("hd-panel")) this.setAttribute("sub", "");
      const bodyId = uid("hd-panel-body");
      this.twisty = h("span", { class: "hd-panel__twisty", "aria-hidden": "true" });
      this.titleEl = h("span", { class: "hd-panel__title" });
      this.toggleButton = h("button", { type: "button", class: "hd-panel__toggle", "aria-controls": bodyId }, this.twisty, this.titleEl);
      this.header = h("div", { class: "k-panel__header hd-panel__header" }, this.toggleButton);
      for (const x of headerExtras) this.header.append(x);
      if (this.flag("pinnable")) {
        this.pinButton = h("button", { type: "button", class: "btn icon ghost hd-panel__pin", tooltip: "Pin", description: "A pinned panel shows under every tab", shortcut: "Shift+Click", "aria-label": "Pin panel", text: "○" });
        this.pinButton.addEventListener("click", (ev) => {
          ev.stopPropagation();
          this.pin(!this.pinned);
        });
        this.header.append(this.pinButton);
      }
      if (this.flag("reorderable")) {
        this.grip = h("span", { class: "hd-panel__grip", "aria-hidden": "true", tooltip: "Drag to reorder", shortcut: "Alt+Up", text: "⁙⁙" });
        this.grip.addEventListener("pointerdown", (ev) => this.startReorder(ev));
        this.header.append(this.grip);
      }
      this.body = h("div", { class: "k-panel__body hd-panel__body", id: bodyId });
      this.body.append(...bodyContent);
      this.replaceChildren(this.header, this.body);
      this.header.addEventListener("pointerdown", (ev) => {
        if (ev.button !== 0 || this.flag("disabled")) return;
        const t = ev.target;
        if (t.closest(".hd-panel__pin, .hd-panel__grip") || t.closest("button, input, hd-number, hd-text, hd-enum") && !t.closest(".hd-panel__toggle")) return;
        ev.preventDefault();
        this.toggleButton.focus({ preventScroll: true });
        if (ev.shiftKey && this.flag("pinnable")) {
          this.pin(!this.pinned);
          return;
        }
        if (ev.ctrlKey || ev.metaKey) {
          this.soloOpen();
          return;
        }
        this.toggle();
        dragSetting = { open: this.open, touched: /* @__PURE__ */ new Set([this]) };
      });
      this.header.addEventListener("pointerenter", () => {
        hoveredHeader = this;
        if (dragSetting && !dragSetting.touched.has(this)) {
          dragSetting.touched.add(this);
          if (this.open !== dragSetting.open) this.toggle();
        }
      });
      this.header.addEventListener("pointerleave", () => {
        if (hoveredHeader === this) hoveredHeader = null;
      });
      this.toggleButton.addEventListener("click", (ev) => {
        if (ev.detail !== 0 || this.flag("disabled")) return;
        if (ev.ctrlKey || ev.metaKey) this.soloOpen();
        else this.toggle();
      });
      this.toggleButton.addEventListener("keydown", (ev) => {
        if (ev.altKey && (ev.key === "ArrowUp" || ev.key === "ArrowDown") && this.flag("reorderable")) {
          ev.preventDefault();
          this.moveBy(ev.key === "ArrowUp" ? -1 : 1);
        }
      });
    }
    render() {
      const open2 = this.open;
      this.twisty.textContent = open2 ? "▾" : "▸";
      this.titleEl.textContent = this.str("heading");
      this.toggleButton.setAttribute("aria-expanded", String(open2));
      this.toggleButton.disabled = this.flag("disabled");
      this.body.hidden = !open2;
      if (this.pinButton) {
        this.pinButton.setAttribute("aria-pressed", String(this.pinned));
        this.pinButton.textContent = this.pinned ? "◉" : "○";
      }
      this.setAttribute("aria-busy", String(this.flag("loading")));
    }
    toggle() {
      this.setOpen(!this.open);
    }
    setOpen(open2) {
      if (open2 === this.open) return;
      this.open = open2;
      this.emit("toggle", { open: open2 });
    }
    /** The panels this one collapses with Ctrl+click and reorders among: its siblings. */
    siblings() {
      const parent = this.parentElement;
      if (!parent) return [this];
      return [...parent.children].filter((c) => c instanceof _HdPanel && !c.hidden);
    }
    soloOpen() {
      const all = this.siblings();
      const stack2 = new PanelStack(all.map((p) => ({ id: p.panelId, collapsed: !p.open, pinned: p.pinned, tab: "" })));
      stack2.soloOpen(this.panelId);
      for (const p of all) p.setOpen(!stack2.get(p.panelId)?.collapsed);
    }
    pin(on) {
      this.setFlag("pinned", on);
      this.emit("hd-pin", { pinned: on });
    }
    get panelId() {
      if (!this.id) this.id = uid("hd-panel");
      return this.id;
    }
    moveBy(delta) {
      const all = this.siblings();
      const stack2 = new PanelStack(all.map((p) => ({ id: p.panelId, collapsed: !p.open, pinned: p.pinned, tab: "" })));
      const from = all.indexOf(this);
      if (!stack2.move(this.panelId, from + delta)) return;
      this.applyOrder(stack2.order());
      this.toggleButton.focus({ preventScroll: true });
    }
    applyOrder(order) {
      const parent = this.parentElement;
      if (!parent) return;
      const all = this.siblings();
      const anchor = all[all.length - 1]?.nextSibling ?? null;
      for (const id of order) {
        const p = all.find((x) => x.panelId === id);
        if (p) parent.insertBefore(p, anchor);
      }
      parent.dispatchEvent(new CustomEvent("hd-reorder", { bubbles: true, detail: { order } }));
    }
    startReorder(ev) {
      if (ev.button !== 0) return;
      ev.preventDefault();
      ev.stopPropagation();
      const all = this.siblings();
      const startY = ev.clientY;
      const marker = h("div", { class: "hd-panel__drop", "aria-hidden": "true" });
      this.setAttribute("data-hd-dragging", "");
      const target = /* @__PURE__ */ __name((y) => {
        let i = 0;
        for (const p of all) {
          const r = p.getBoundingClientRect();
          if (y > r.top + r.height / 2) i += 1;
        }
        return i;
      }, "target");
      const move = /* @__PURE__ */ __name((e) => {
        const i = target(e.clientY);
        const ref = all[i] ?? null;
        if (ref) ref.before(marker);
        else all[all.length - 1]?.after(marker);
      }, "move");
      const up = /* @__PURE__ */ __name((e) => {
        document.removeEventListener("pointermove", move);
        document.removeEventListener("pointerup", up);
        marker.remove();
        this.removeAttribute("data-hd-dragging");
        if (Math.abs(e.clientY - startY) < 3) return;
        const stack2 = new PanelStack(all.map((p) => ({ id: p.panelId, collapsed: !p.open, pinned: p.pinned, tab: "" })));
        let to = target(e.clientY);
        const from = all.indexOf(this);
        if (to > from) to -= 1;
        if (stack2.move(this.panelId, to)) this.applyOrder(stack2.order());
      }, "up");
      document.addEventListener("pointermove", move);
      document.addEventListener("pointerup", up);
    }
  };
  var HdSidebar = class extends HdElement {
    static {
      __name(this, "HdSidebar");
    }
    static get observedAttributes() {
      return ["tab"];
    }
    tabs;
    content;
    build() {
      const panels = [...this.children].filter((c) => c.tagName.toLowerCase() === "hd-panel");
      const names = [];
      for (const p of panels) {
        const t = p.getAttribute("tab") ?? "";
        if (t && !names.includes(t)) names.push(t);
      }
      this.content = h("div", { class: "hd-sidebar__content" });
      this.content.append(...panels);
      this.tabs = document.createElement("hd-tabs");
      this.tabs.setAttribute("orientation", "vertical");
      for (const n of names) {
        const t = document.createElement("hd-tab");
        t.setAttribute("value", n);
        t.textContent = n;
        this.tabs.append(t);
      }
      this.replaceChildren(this.content, this.tabs);
      if (!this.hasAttribute("tab") && names[0]) this.setAttribute("tab", names[0]);
      this.tabs.addEventListener("change", (ev) => {
        ev.stopPropagation();
        this.setAttribute("tab", this.tabs.value);
        this.emit("change");
      });
      this.addEventListener("hd-pin", () => this.render());
    }
    render() {
      const tab = this.str("tab");
      if (this.tabs.value !== tab) this.tabs.value = tab;
      const panels = [...this.content.children].filter((c) => c.tagName.toLowerCase() === "hd-panel");
      const stack2 = new PanelStack(panels.map((p) => ({ id: p.panelId, collapsed: !p.open, pinned: p.pinned, tab: p.getAttribute("tab") ?? "" })));
      const show2 = stack2.visibleFor(tab).map((s) => s.id);
      for (const id of show2) {
        const p = panels.find((x) => x.panelId === id);
        if (p) this.content.append(p);
      }
      for (const p of panels) p.hidden = !show2.includes(p.panelId);
    }
  };
  define("hd-panel", HdPanel);
  define("hd-sidebar", HdSidebar);

  // ui/kit/src/tabs/controller.ts
  function tabKey(tabs, current4, key, orientation, mods2) {
    const next = orientation === "vertical" ? "ArrowDown" : "ArrowRight";
    const prev = orientation === "vertical" ? "ArrowUp" : "ArrowLeft";
    if (key === next) return navigate(tabs, current4, "next", { wrap: true });
    if (key === prev) return navigate(tabs, current4, "prev", { wrap: true });
    if (key === "Home") return navigate(tabs, current4, "first");
    if (key === "End") return navigate(tabs, current4, "last");
    if (mods2.ctrl && key === "Tab") return navigate(tabs, current4, mods2.shift ? "prev" : "next", { wrap: true });
    if (mods2.ctrl && key === "PageDown") return navigate(tabs, current4, "next", { wrap: true });
    if (mods2.ctrl && key === "PageUp") return navigate(tabs, current4, "prev", { wrap: true });
    return null;
  }
  __name(tabKey, "tabKey");
  function tabWheel(tabs, current4, deltaY) {
    if (!deltaY) return current4;
    return navigate(tabs, current4, deltaY > 0 ? "next" : "prev", { wrap: true });
  }
  __name(tabWheel, "tabWheel");

  // ui/kit/src/tabs/element.ts
  var HdTabs = class extends HdElement {
    static {
      __name(this, "HdTabs");
    }
    static get observedAttributes() {
      return ["value", "orientation", "disabled", "for"];
    }
    tabs = [];
    buttons = [];
    strip;
    dragging = false;
    get value() {
      return this.str("value", this.tabs.find((t) => !t.disabled)?.id ?? "");
    }
    set value(v) {
      this.setAttribute("value", v);
    }
    get orientation() {
      return this.str("orientation") === "vertical" ? "vertical" : "horizontal";
    }
    build() {
      this.upgradeProperty("value");
      this.tabs = [...this.querySelectorAll(":scope > hd-tab")].map((t) => ({ id: t.getAttribute("value") ?? ownText(t), label: ownText(t), disabled: t.hasAttribute("disabled"), icon: t.getAttribute("icon") ?? void 0 }));
      this.strip = h("div", { class: "hd-tabs__strip", role: "tablist" });
      this.replaceChildren(this.strip);
      this.buttons = this.tabs.map((t, i) => {
        const b = h("button", { type: "button", class: "hd-tab", role: "tab", id: uid("hd-tab"), "data-value": t.id, disabled: t.disabled }, t.icon ? h("span", { class: "hd-icon", "aria-hidden": "true", text: t.icon }) : null, h("span", { class: "hd-tab__label", text: t.label }));
        b.addEventListener("click", () => this.select(i));
        b.addEventListener("pointerdown", (ev) => {
          if (ev.button === 0) this.dragging = true;
        });
        b.addEventListener("pointerenter", () => {
          if (this.dragging) this.select(i);
        });
        b.addEventListener("dblclick", () => this.rename(i));
        this.strip.append(b);
        return b;
      });
      document.addEventListener("pointerup", () => this.dragging = false);
      this.strip.addEventListener("keydown", (ev) => {
        if (this.flag("disabled")) return;
        if (ev.key === "F2") {
          ev.preventDefault();
          this.rename(this.current());
          return;
        }
        const next = tabKey(this.tabs, this.current(), ev.key, this.orientation, { ctrl: ev.ctrlKey || ev.metaKey, shift: ev.shiftKey });
        if (next === null) return;
        ev.preventDefault();
        ev.stopPropagation();
        this.select(next);
        this.buttons[next]?.focus();
      });
      this.strip.addEventListener("wheel", (ev) => {
        if (!(ev.ctrlKey || ev.metaKey) || this.flag("disabled")) return;
        ev.preventDefault();
        ev.stopPropagation();
        this.select(tabWheel(this.tabs, this.current(), ev.deltaY));
      }, { passive: false });
    }
    current() {
      return this.tabs.findIndex((t) => t.id === this.value);
    }
    select(i) {
      const t = this.tabs[i];
      if (!t || t.disabled || this.flag("disabled") || t.id === this.value) return;
      this.value = t.id;
      this.emit("change");
    }
    rename(i) {
      const b = this.buttons[i];
      const t = this.tabs[i];
      if (!this.flag("renamable") || !b || !t) return;
      const input = h("input", { type: "text", class: "input hd-tab__rename", "aria-label": `Rename ${t.label}` });
      input.value = t.label;
      const label = b.querySelector(".hd-tab__label");
      if (!label) return;
      label.replaceWith(input);
      this.setAttribute("data-editing", "");
      input.focus();
      input.select();
      let done = false;
      const finish = /* @__PURE__ */ __name((keep) => {
        if (done) return;
        done = true;
        this.removeAttribute("data-editing");
        const text = input.value.trim();
        if (keep && text) t.label = text;
        input.replaceWith(h("span", { class: "hd-tab__label", text: t.label }));
        b.focus();
        if (keep && text) this.emit("hd-rename", { value: t.id, label: t.label });
      }, "finish");
      input.addEventListener("keydown", (ev) => {
        ev.stopPropagation();
        if (ev.key === "Enter") finish(true);
        else if (ev.key === "Escape") {
          ev.preventDefault();
          finish(false);
        }
      });
      input.addEventListener("blur", () => finish(true));
    }
    render() {
      const v = this.value;
      this.strip.setAttribute("aria-orientation", this.orientation);
      this.classList.toggle("is-vertical", this.orientation === "vertical");
      this.buttons.forEach((b, i) => {
        const on = this.tabs[i]?.id === v;
        b.setAttribute("aria-selected", String(on));
        b.tabIndex = on ? 0 : -1;
        b.disabled = this.flag("disabled") || !!this.tabs[i]?.disabled;
      });
      const target = this.str("for") ? document.querySelector(this.str("for")) : null;
      if (target) {
        for (const pane of target.querySelectorAll(":scope > [data-tab]")) {
          const show2 = pane.getAttribute("data-tab") === v;
          pane.hidden = !show2;
          pane.setAttribute("role", "tabpanel");
          const b = this.buttons.find((x) => x.dataset.value === pane.getAttribute("data-tab"));
          if (b) {
            if (!pane.id) pane.id = uid("hd-tabpanel");
            b.setAttribute("aria-controls", pane.id);
            pane.setAttribute("aria-labelledby", b.id);
          }
        }
      }
    }
    focus(options) {
      (this.buttons.find((b) => b.tabIndex === 0) ?? this.buttons[0])?.focus(options);
    }
  };
  var HdTab = class extends HTMLElement {
    static {
      __name(this, "HdTab");
    }
  };
  define("hd-tabs", HdTabs);
  define("hd-tab", HdTab);

  // ui/kit/src/props/element.ts
  var HdProps = class extends HdElement {
    static {
      __name(this, "HdProps");
    }
    static get observedAttributes() {
      return ["columns"];
    }
    build() {
      this.setAttribute("role", "group");
    }
    render() {
      const cols = this.str("columns", "1");
      this.dataset.columns = cols === "auto" ? "auto" : String(Math.max(1, Math.min(6, Number(cols) || 1)));
    }
  };
  define("hd-props", HdProps);

  // ui/kit/src/pie/controller.ts
  var PIE_ORDER = ["W", "E", "S", "N", "NW", "NE", "SW", "SE"];
  var ANGLE = {
    E: 0,
    NE: Math.PI / 4,
    N: Math.PI / 2,
    NW: 3 * Math.PI / 4,
    W: Math.PI,
    SW: -3 * Math.PI / 4,
    S: -Math.PI / 2,
    SE: -Math.PI / 4
  };
  var NUMPAD = { "4": "W", "6": "E", "2": "S", "8": "N", "7": "NW", "9": "NE", "1": "SW", "3": "SE" };
  function directionOfSlot(i) {
    return PIE_ORDER[i];
  }
  __name(directionOfSlot, "directionOfSlot");
  function slotVector(d) {
    const a = ANGLE[d];
    return { x: Math.cos(a), y: -Math.sin(a) };
  }
  __name(slotVector, "slotVector");
  function pieIndex(dx, dy, count, deadZone = 12) {
    if (Math.hypot(dx, dy) < deadZone || count <= 0) return -1;
    const angle = Math.atan2(-dy, dx);
    let best = -1;
    let bestDiff = Infinity;
    for (let i = 0; i < Math.min(count, PIE_ORDER.length); i += 1) {
      const d = PIE_ORDER[i];
      let diff = Math.abs(angle - ANGLE[d]);
      if (diff > Math.PI) diff = Math.PI * 2 - diff;
      if (diff < bestDiff) {
        bestDiff = diff;
        best = i;
      }
    }
    return best;
  }
  __name(pieIndex, "pieIndex");
  function pieKey(key, count) {
    const d = own(NUMPAD, key);
    if (!d) return -1;
    const i = PIE_ORDER.indexOf(d);
    return i < count ? i : -1;
  }
  __name(pieKey, "pieKey");
  function pieAccelerator(entries, key, mods2 = {}) {
    if (mods2.ctrl || mods2.alt || mods2.meta || key.length !== 1) return -1;
    const letter = key.toLowerCase();
    return entries.findIndex((e) => e.accel !== "" && e.accel === letter && !e.disabled);
  }
  __name(pieAccelerator, "pieAccelerator");
  function pieRelease(dx, dy, count, heldMs, deadZone = 12, tapMs = 250) {
    const i = pieIndex(dx, dy, count, deadZone);
    if (i >= 0) return { choose: i };
    if (heldMs < tapMs) return { stayOpen: true };
    return { close: true };
  }
  __name(pieRelease, "pieRelease");

  // ui/kit/src/pie/element.ts
  var ARROW_TO_NUMPAD = { ArrowLeft: "4", ArrowRight: "6", ArrowDown: "2", ArrowUp: "8" };
  function openPie(items, opts = {}) {
    const entries = buildMenu(items.slice(0, 8)).filter((e) => !e.inert);
    const center = opts.at ?? lastPointer();
    const radius = 96;
    const el = h("div", { class: "hd-pie", role: "menu", tabindex: "-1", "aria-label": opts.label ?? "Pie menu" });
    const pointerLine = h("span", { class: "hd-pie__pointer", "aria-hidden": "true" });
    pointerLine.hidden = true;
    el.append(h("span", { class: "hd-pie__center", "aria-hidden": "true" }), pointerLine);
    let active = -1;
    const rows = entries.map((e, i) => {
      const v = slotVector(directionOfSlot(i) ?? "W");
      const [before, letter, after] = splitAccel(e);
      const b = h(
        "button",
        { type: "button", class: "hd-pie__item", role: "menuitem", disabled: e.disabled, "data-dir": directionOfSlot(i) ?? "", style: `--x: ${Math.round(v.x * radius)}px; --y: ${Math.round(v.y * radius)}px` },
        // One span for the label, so the flex gap does not split the word at its accelerator.
        h("span", { class: "hd-pie__label" }, before, letter ? h("span", { class: "hd-accel", text: letter }) : null, after),
        e.shortcutText ? h("kbd", { class: "hd-menu__key", text: e.shortcutText }) : null
      );
      if (e.spec.command) {
        b.setAttribute("tooltip", e.label);
        b.setAttribute("command", e.spec.command);
      }
      b.addEventListener("click", () => choose(i));
      el.append(b);
      return b;
    });
    const setActive = /* @__PURE__ */ __name((i) => {
      active = i;
      rows.forEach((r, k) => r.classList.toggle("is-active", k === i));
    }, "setActive");
    const aim = /* @__PURE__ */ __name((angle) => {
      pointerLine.hidden = angle === null;
      if (angle !== null) pointerLine.style.setProperty("--angle", `${angle}rad`);
    }, "aim");
    const opened = performance.now();
    const choose = /* @__PURE__ */ __name((i) => {
      const e = entries[i];
      if (!e || e.disabled) return;
      handle.close("chosen");
      e.spec.action?.();
      (opts.origin ?? document).dispatchEvent(new CustomEvent("hd-command", { bubbles: true, detail: { command: e.spec.command ?? "", label: e.label, item: e.spec } }));
    }, "choose");
    const onMove = /* @__PURE__ */ __name((ev) => {
      const dx = ev.clientX - center.x;
      const dy = ev.clientY - center.y;
      const i = pieIndex(dx, dy, entries.length);
      setActive(i);
      aim(i >= 0 ? Math.atan2(dy, dx) : null);
    }, "onMove");
    const onUp = /* @__PURE__ */ __name((ev) => {
      if (!opts.held) return;
      opts.held = false;
      const r = pieRelease(ev.clientX - center.x, ev.clientY - center.y, entries.length, performance.now() - opened);
      if ("choose" in r) choose(r.choose);
      else if ("close" in r) handle.close("api");
    }, "onUp");
    el.addEventListener("keydown", (ev) => {
      const arrow = own(ARROW_TO_NUMPAD, ev.key);
      const i = pieKey(arrow ?? ev.key, entries.length);
      if (i >= 0) {
        ev.preventDefault();
        if (arrow) {
          setActive(i);
          const v = slotVector(directionOfSlot(i) ?? "W");
          aim(Math.atan2(v.y, v.x));
        } else choose(i);
      } else if (ev.key === "Enter" && active >= 0) {
        ev.preventDefault();
        choose(active);
      } else {
        const k = pieAccelerator(entries, ev.key, { ctrl: ev.ctrlKey, alt: ev.altKey, meta: ev.metaKey });
        if (k >= 0) {
          ev.preventDefault();
          choose(k);
        }
      }
    });
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
    const handle = openFloating(el, {
      at: center,
      hotspot: /* @__PURE__ */ __name(() => ({ x: el.offsetWidth / 2, y: el.offsetHeight / 2 }), "hotspot"),
      restoreFocus: document.activeElement,
      onClose: /* @__PURE__ */ __name(() => {
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
      }, "onClose")
    });
    handle.reposition();
    el.focus({ preventScroll: true });
    return handle;
  }
  __name(openPie, "openPie");
  var HdPie = class extends HdElement {
    static {
      __name(this, "HdPie");
    }
    static get observedAttributes() {
      return ["label"];
    }
    items = [];
    build() {
      this.upgradeProperty("items");
      if (this.items.length === 0) {
        this.items = [...this.querySelectorAll(":scope > hd-menu-item")].map((c) => ({ label: c.getAttribute("label") ?? (c.textContent ?? "").trim(), shortcut: c.getAttribute("shortcut") ?? void 0, command: c.getAttribute("command") ?? void 0, disabled: c.hasAttribute("disabled") }));
      }
      this.hidden = true;
    }
    open(at, held = false) {
      return openPie(this.items, { at, held, origin: this, label: this.str("label") });
    }
  };
  var HdPopover = class extends HdElement {
    static {
      __name(this, "HdPopover");
    }
    static get observedAttributes() {
      return ["for", "heading"];
    }
    content = [];
    handle = null;
    trigger = null;
    onTrigger = /* @__PURE__ */ __name(() => this.handle?.open ? this.close() : this.show(), "onTrigger");
    build() {
      this.content = [...this.childNodes];
      this.hidden = true;
      this.bind();
    }
    changed(name) {
      if (name === "for") this.bind();
    }
    bind() {
      this.trigger?.removeEventListener("click", this.onTrigger);
      const id = this.str("for");
      this.trigger = id ? document.getElementById(id) : null;
      const button = this.trigger?.matches("hd-button, hd-toggle") ? this.trigger.querySelector("button") : this.trigger;
      this.trigger?.addEventListener("click", this.onTrigger);
      button?.setAttribute("aria-haspopup", "dialog");
      button?.setAttribute("aria-expanded", "false");
    }
    show() {
      if (!this.trigger) return;
      const button = this.trigger.querySelector("button") ?? this.trigger;
      const panel = h("div", { class: "hd-popover", role: "dialog", "aria-label": this.str("heading") || "Options" });
      if (this.str("heading")) panel.append(h("div", { class: "hd-popup__head", text: this.str("heading") }));
      const body = h("div", { class: "hd-popup__body" });
      body.append(...this.content);
      panel.append(body);
      this.handle = openFloating(panel, {
        anchor: this.trigger,
        side: "below",
        owner: this.trigger,
        restoreFocus: button,
        leaveMargin: 120,
        onClose: /* @__PURE__ */ __name(() => {
          this.append(...this.content);
          button.setAttribute("aria-expanded", "false");
          this.handle = null;
        }, "onClose")
      });
      button.setAttribute("aria-expanded", "true");
      panel.querySelector("button, input, [tabindex='0'], hd-number, hd-text, hd-enum, hd-checkbox")?.focus();
    }
    close() {
      this.handle?.close("api");
    }
  };
  define("hd-pie", HdPie);
  define("hd-popover", HdPopover);

  // ui/kit/src/tooltip/controller.ts
  function tooltipLines(spec, dev) {
    const lines = [];
    const title = spec.title.trim();
    if (!title && !spec.description?.trim()) return lines;
    if (title) lines.push({ kind: "title", text: title });
    if (spec.shortcut?.trim()) lines.push({ kind: "shortcut", text: displayChord(spec.shortcut.trim()) });
    if (spec.description?.trim()) lines.push({ kind: "description", text: spec.description.trim() });
    if (spec.disabledReason?.trim()) lines.push({ kind: "disabled", text: `Disabled: ${spec.disabledReason.trim()}` });
    if (dev && spec.devId?.trim()) lines.push({ kind: "dev", text: `${spec.devKind?.trim() || "Command"}: ${spec.devId.trim()}` });
    return lines;
  }
  __name(tooltipLines, "tooltipLines");
  var TooltipTiming = class {
    constructor(delay = 600, grace = 400) {
      this.delay = delay;
      this.grace = grace;
    }
    static {
      __name(this, "TooltipTiming");
    }
    lastHidden = -Infinity;
    suppressed = false;
    shown = false;
    /** The pointer entered a control at `now`. Returns how long to wait before showing. */
    enter(now) {
      this.suppressed = false;
      return now - this.lastHidden <= this.grace ? 0 : this.delay;
    }
    /** The tooltip is now showing. */
    show() {
      if (this.suppressed) return false;
      this.shown = true;
      return true;
    }
    /** The pointer left, or focus moved on. */
    leave(now) {
      if (this.shown) this.lastHidden = now;
      this.shown = false;
    }
    /** A press on the control: hide, and stay hidden until the pointer leaves. */
    press(now) {
      this.leave(now);
      this.suppressed = true;
      this.lastHidden = -Infinity;
    }
  };

  // ui/kit/src/tooltip/element.ts
  var SELECTOR = "[tooltip]:not(hd-tooltip), [data-tooltip]";
  function read(el, name) {
    return el.getAttribute(name) ?? el.getAttribute(`data-${name}`) ?? "";
  }
  __name(read, "read");
  function specFor(el) {
    const nodeType = read(el, "node-type");
    const disabled = el.hasAttribute("disabled") || el.getAttribute("aria-disabled") === "true";
    const invalid = el.getAttribute("invalid");
    return {
      title: read(el, "tooltip"),
      description: [read(el, "description"), invalid ? `Invalid: ${invalid}` : "", el.hasAttribute("wired") && el.getAttribute("wired") ? `Wired from ${el.getAttribute("wired")}` : ""].filter(Boolean).join(" -- "),
      shortcut: read(el, "shortcut"),
      devId: nodeType || read(el, "command"),
      devKind: nodeType ? "Node type" : "Command",
      disabledReason: disabled ? read(el, "disabled-reason") : ""
    };
  }
  __name(specFor, "specFor");
  var HdTooltip = class extends HdElement {
    static {
      __name(this, "HdTooltip");
    }
    static get observedAttributes() {
      return ["tooltip", "description", "shortcut", "command", "node-type", "dev"];
    }
    lines = [];
    build() {
      this.setAttribute("role", "tooltip");
    }
    render() {
      const spec = {
        title: this.str("tooltip"),
        description: this.str("description"),
        shortcut: this.str("shortcut"),
        devId: this.str("node-type") || this.str("command"),
        devKind: this.str("node-type") ? "Node type" : "Command"
      };
      if (this.lines.length === 0 || this.hasAttribute("tooltip")) this.lines = tooltipLines(spec, this.flag("dev") || isDevMode());
      paint(this, this.lines);
    }
  };
  function paint(host, lines) {
    host.replaceChildren();
    const head = h("div", { class: "hd-tip__head" });
    for (const line of lines) {
      if (line.kind === "title") head.append(h("span", { class: "hd-tip__title", text: line.text }));
      else if (line.kind === "shortcut") head.append(h("kbd", { class: "hd-tip__key", text: line.text }));
    }
    host.append(head);
    for (const line of lines) {
      if (line.kind === "description") host.append(h("div", { class: "hd-tip__desc", text: line.text }));
      else if (line.kind === "disabled") host.append(h("div", { class: "hd-tip__disabled", text: line.text }));
      else if (line.kind === "dev") host.append(h("div", { class: "hd-tip__dev", text: line.text }));
    }
  }
  __name(paint, "paint");
  var timing = new TooltipTiming();
  var current2 = null;
  var timer2;
  var installed4 = false;
  function hide() {
    window.clearTimeout(timer2);
    timer2 = void 0;
    current2?.handle.close("api");
  }
  __name(hide, "hide");
  function closed(target, handle) {
    if (current2?.handle !== handle) return;
    target.removeAttribute("aria-describedby");
    current2 = null;
    timing.leave(performance.now());
  }
  __name(closed, "closed");
  function show(target) {
    if (!target.isConnected || !timing.show()) return;
    const lines = tooltipLines(specFor(target), isDevMode());
    if (lines.length === 0) return;
    const tip = document.createElement("hd-tooltip");
    tip.id = "hd-tooltip-live";
    tip.lines = lines;
    paint(tip, lines);
    tip.setAttribute("role", "tooltip");
    const handle = openFloating(tip, { anchor: target, side: "below", passive: true, onClose: /* @__PURE__ */ __name(() => closed(target, handle), "onClose") });
    target.setAttribute("aria-describedby", tip.id);
    current2 = { target, handle };
  }
  __name(show, "show");
  function schedule(target) {
    if (current2?.target === target) return;
    hide();
    const wait = timing.enter(performance.now());
    timer2 = window.setTimeout(() => show(target), wait);
  }
  __name(schedule, "schedule");
  function installTooltips() {
    if (installed4) return;
    installed4 = true;
    document.addEventListener("pointerover", (ev) => {
      const t = ev.target?.closest?.(SELECTOR);
      if (t) schedule(t);
    });
    document.addEventListener("pointerout", (ev) => {
      const from = ev.target?.closest?.(SELECTOR);
      const to = ev.relatedTarget?.closest?.(SELECTOR);
      if (from && from !== to) hide();
    });
    document.addEventListener("focusin", (ev) => {
      const t = ev.target?.closest?.(SELECTOR);
      if (t && ev.target.matches?.(":focus-visible")) schedule(t);
    });
    document.addEventListener("focusout", () => hide());
    document.addEventListener(
      "pointerdown",
      () => {
        window.clearTimeout(timer2);
        timing.press(performance.now());
        current2?.handle.close("api");
      },
      true
    );
    document.addEventListener(
      "keydown",
      (ev) => {
        if (ev.key !== "Escape") return;
        window.clearTimeout(timer2);
        timer2 = void 0;
      },
      true
    );
  }
  __name(installTooltips, "installTooltips");
  define("hd-tooltip", HdTooltip);

  // ui/kit/src/feedback/controller.ts
  var SEVERITIES = ["info", "success", "warning", "error"];
  function severityOf(raw) {
    const s = (raw ?? "").trim().toLowerCase();
    if (s === "ok") return "success";
    if (s === "warn") return "warning";
    return SEVERITIES.includes(s) ? s : "info";
  }
  __name(severityOf, "severityOf");
  function reportText(text) {
    const t = (text ?? "").replace(/\s+/g, " ").trim();
    return t ? t : null;
  }
  __name(reportText, "reportText");
  function reportTimeout(sev) {
    switch (sev) {
      case "error":
        return 0;
      case "warning":
        return 8e3;
      default:
        return 4e3;
    }
  }
  __name(reportTimeout, "reportTimeout");
  function progress(value, max = 1, label = "") {
    const lbl = label.trim();
    if (value === null || value === void 0 || !Number.isFinite(value) || !(max > 0)) {
      return { fraction: null, text: lbl || "Working" };
    }
    const fraction = Math.min(1, Math.max(0, value / max));
    const pct = `${Math.round(fraction * 100)}%`;
    return { fraction, text: lbl ? `${lbl} ${pct}` : pct };
  }
  __name(progress, "progress");
  function parseHints(text) {
    return text.split("|").map((part) => part.trim()).filter(Boolean).map((part) => {
      const at = part.indexOf(":");
      if (at < 0) return { key: part, label: "" };
      return { key: part.slice(0, at).trim(), label: part.slice(at + 1).trim() };
    }).filter((h2) => h2.key);
  }
  __name(parseHints, "parseHints");
  function modalHeader(parts) {
    return parts.map((p) => (p ?? "").trim()).filter(Boolean).join("  |  ");
  }
  __name(modalHeader, "modalHeader");

  // ui/kit/src/feedback/element.ts
  var GLYPH = { info: "i", success: "✓", warning: "!", error: "✕" };
  var HdReport = class extends HdElement {
    static {
      __name(this, "HdReport");
    }
    static get observedAttributes() {
      return ["severity", "text", "dismissible", "timeout"];
    }
    textEl;
    icon;
    close;
    timer;
    build() {
      const authored = ownText(this);
      takeChildren(this);
      if (!this.hasAttribute("text") && authored) this.setAttribute("text", authored);
      this.icon = h("span", { class: "hd-report__icon", "aria-hidden": "true" });
      this.textEl = h("span", { class: "hd-report__text" });
      this.close = h("button", { type: "button", class: "btn icon ghost hd-report__close", "aria-label": "Dismiss", tooltip: "Dismiss", text: "✕" });
      this.close.addEventListener("click", () => this.dismiss());
      this.append(this.icon, this.textEl, this.close);
    }
    render() {
      const sev = severityOf(this.getAttribute("severity"));
      const text = reportText(this.getAttribute("text"));
      this.hidden = text === null;
      this.dataset.severity = sev;
      this.setAttribute("role", sev === "error" || sev === "warning" ? "alert" : "status");
      this.icon.textContent = own(GLYPH, sev) ?? "i";
      this.textEl.textContent = text ?? "";
      this.close.hidden = !this.flag("dismissible");
      window.clearTimeout(this.timer);
      const ms = this.hasAttribute("timeout") ? this.num("timeout", 0) || reportTimeout(sev) : 0;
      if (text && ms > 0) this.timer = window.setTimeout(() => this.dismiss(), ms);
    }
    dismiss() {
      this.hidden = true;
      this.emit("hd-dismiss");
    }
  };
  var HdProgress = class extends HdElement {
    static {
      __name(this, "HdProgress");
    }
    static get observedAttributes() {
      return ["value", "max", "label", "cancelable"];
    }
    bar;
    fill;
    textEl;
    cancel;
    build() {
      this.setAttribute("role", "progressbar");
      this.fill = h("span", { class: "hd-progress__fill" });
      this.bar = h("div", { class: "hd-progress__bar" }, this.fill);
      this.textEl = h("span", { class: "hd-progress__text" });
      this.cancel = h("button", { type: "button", class: "btn icon ghost hd-progress__cancel", "aria-label": "Cancel", tooltip: "Cancel", shortcut: "Esc", text: "✕" });
      this.cancel.addEventListener("click", () => this.emit("hd-cancel"));
      this.append(this.bar, this.textEl, this.cancel);
    }
    render() {
      const raw = this.getAttribute("value");
      const p = progress(raw === null || raw.trim() === "" ? null : Number(raw), this.num("max", 1), this.str("label"));
      this.toggleAttribute("data-indeterminate", p.fraction === null);
      this.fill.style.width = p.fraction === null ? "" : `${(p.fraction * 100).toFixed(1)}%`;
      this.textEl.textContent = p.text;
      this.setAttribute("aria-valuetext", p.text);
      if (p.fraction === null) {
        this.removeAttribute("aria-valuenow");
      } else {
        this.setAttribute("aria-valuemin", "0");
        this.setAttribute("aria-valuemax", "100");
        this.setAttribute("aria-valuenow", String(Math.round(p.fraction * 100)));
      }
      this.cancel.hidden = !this.flag("cancelable");
    }
  };
  var HdStatusHints = class extends HdElement {
    static {
      __name(this, "HdStatusHints");
    }
    static get observedAttributes() {
      return ["hints"];
    }
    build() {
      this.setAttribute("role", "note");
    }
    render() {
      this.replaceChildren();
      for (const hint of parseHints(this.str("hints"))) {
        this.append(h("span", { class: "hd-hint" }, h("kbd", { class: "hd-hint__key", text: hint.key }), hint.label ? h("span", { class: "hd-hint__label", text: hint.label }) : null));
      }
    }
  };
  var HdModalHeader = class extends HdElement {
    static {
      __name(this, "HdModalHeader");
    }
    static get observedAttributes() {
      return ["parts"];
    }
    build() {
      this.setAttribute("role", "status");
      this.setAttribute("aria-live", "polite");
    }
    render() {
      const parts = this.str("parts").split("|");
      this.replaceChildren();
      const text = modalHeader(parts);
      text.split("  |  ").forEach((p, i) => {
        if (i > 0) this.append(h("span", { class: "hd-modal__sep", "aria-hidden": "true", text: "|" }));
        this.append(h("span", { class: i === 0 ? "hd-modal__op" : "hd-modal__part", text: p }));
      });
    }
  };
  define("hd-report", HdReport);
  define("hd-progress", HdProgress);
  define("hd-status-hints", HdStatusHints);
  define("hd-modal-header", HdModalHeader);

  // ui/kit/src/area/controller.ts
  function groupViews(views, coreName = "HollowDeck") {
    const map = /* @__PURE__ */ new Map();
    for (const v of views) {
      const list = map.get(v.module) ?? [];
      list.push(v);
      map.set(v.module, list);
    }
    return [...map.entries()].sort(([a], [b]) => a === coreName ? -1 : b === coreName ? 1 : a.localeCompare(b)).map(([module, list]) => ({ module, views: list }));
  }
  __name(groupViews, "groupViews");
  function viewGlyph(v) {
    if (v.icon && v.icon.trim()) return v.icon.trim();
    const ch = v.title.trim().charAt(0);
    return ch ? ch.toUpperCase() : "?";
  }
  __name(viewGlyph, "viewGlyph");
  function switcherItems(views) {
    return views.map((v) => ({ ...v, label: v.title, path: v.module, keywords: v.id }));
  }
  __name(switcherItems, "switcherItems");
  function regionShortcut(r) {
    switch (r) {
      case "toolbar":
        return "T";
      case "sidebar":
        return "N";
      default:
        return "";
    }
  }
  __name(regionShortcut, "regionShortcut");

  // ui/kit/src/area/element.ts
  var HdAreaHeader = class extends HdElement {
    static {
      __name(this, "HdAreaHeader");
    }
    build() {
      this.setAttribute("role", "toolbar");
      if (!this.hasAttribute("aria-label")) this.setAttribute("aria-label", "Area header");
    }
  };
  var HdViewSwitcher = class extends HdElement {
    static {
      __name(this, "HdViewSwitcher");
    }
    static get observedAttributes() {
      return ["value", "disabled"];
    }
    views = [];
    button;
    glyph;
    popup = null;
    get value() {
      return this.str("value");
    }
    set value(v) {
      this.setAttribute("value", v);
    }
    build() {
      this.upgradeProperty("views");
      this.upgradeProperty("value");
      if (this.views.length === 0) {
        this.views = [...this.querySelectorAll(":scope > option")].map((o) => ({ id: o.value, title: (o.textContent ?? "").trim(), module: o.getAttribute("data-module") ?? "HollowDeck", icon: o.getAttribute("data-icon") ?? void 0 }));
      }
      this.glyph = h("span", { class: "hd-switcher__glyph", "aria-hidden": "true" });
      this.button = h("button", { type: "button", class: "hd-switcher", "aria-haspopup": "listbox", "aria-expanded": "false" }, this.glyph, h("span", { class: "hd-choice__caret", "aria-hidden": "true", text: "▾" }));
      this.replaceChildren(this.button);
      this.button.addEventListener("click", () => this.popup?.open ? this.popup.close("api") : this.open());
      this.button.addEventListener("keydown", (ev) => {
        if (ev.key === "ArrowDown" || ev.key === "F4") {
          ev.preventDefault();
          this.open();
        }
      });
    }
    render() {
      const v = this.views.find((x) => x.id === this.value);
      this.glyph.textContent = v ? viewGlyph(v) : "?";
      this.button.setAttribute("tooltip", v ? v.title : "Choose a view");
      this.button.setAttribute("description", v ? `${v.module} — change the view shown in this area` : "Change the view shown in this area");
      this.button.setAttribute("aria-label", `View: ${v?.title ?? "none"}`);
      this.button.disabled = this.flag("disabled");
    }
    open() {
      if (this.flag("disabled")) return;
      const items = switcherItems(this.views).map((v) => ({ ...v, value: v.id }));
      const combo = new Combobox(items);
      const listId = uid("hd-switcher-list");
      const input = h("input", { type: "text", class: "input hd-select__search", placeholder: "Search views", spellcheck: "false", autocomplete: "off", role: "combobox", "aria-expanded": "true", "aria-controls": listId, "aria-label": "Search views" });
      const list = h("div", { class: "hd-listbox hd-select__list", role: "listbox", id: listId });
      const box = h("div", { class: "hd-select__popup hd-switcher__popup" }, input, list);
      const paint2 = /* @__PURE__ */ __name(() => {
        list.replaceChildren();
        const matches = combo.matches();
        const byId2 = new Map(matches.map((m, i) => [m.item.id, { m, i }]));
        const groups = groupViews(matches.map((m) => m.item));
        if (matches.length === 0) list.append(h("div", { class: "hd-search__empty", text: `No view matches “${combo.query}”` }));
        for (const g of groups) {
          list.append(h("div", { class: "hd-listbox__group", role: "presentation", text: g.module }));
          for (const v of g.views) {
            const hit = byId2.get(v.id);
            if (!hit) continue;
            const row = h(
              "div",
              { class: "hd-listbox__opt", role: "option", id: `${listId}-${hit.i}`, "data-i": String(hit.i), "aria-selected": String(v.id === this.value) },
              h("span", { class: "hd-listbox__icon hd-switcher__glyph", "aria-hidden": "true", text: viewGlyph(v) }),
              h("span", { class: "hd-listbox__text" }, ...highlighted(v.title, hit.m.ranges))
            );
            row.addEventListener("pointerenter", () => {
              combo.hover(hit.i);
              mark();
            });
            row.addEventListener("click", () => pick(v.id));
            list.append(row);
          }
        }
        mark();
      }, "paint");
      const mark = /* @__PURE__ */ __name(() => {
        for (const r of list.querySelectorAll(".hd-listbox__opt")) r.classList.toggle("is-active", Number(r.dataset.i) === combo.active);
        const active = list.querySelector(`[data-i="${combo.active}"]`);
        if (active) {
          input.setAttribute("aria-activedescendant", active.id);
          active.scrollIntoView?.({ block: "nearest" });
        }
      }, "mark");
      const pick = /* @__PURE__ */ __name((id) => {
        this.popup?.close("chosen");
        if (id !== this.value) {
          this.value = id;
          this.emit("change");
        }
      }, "pick");
      input.addEventListener("input", () => {
        combo.setQuery(input.value);
        paint2();
      });
      input.addEventListener("keydown", (ev) => {
        if (ev.isComposing || ev.keyCode === 229) return;
        const r = combo.key(ev.key);
        if (r === null) return;
        ev.preventDefault();
        if (r === "close") this.popup?.close("escape");
        else if (r === "moved") mark();
        else pick(r.choose.value);
      });
      this.popup = openFloating(box, {
        anchor: this.button,
        side: "below",
        owner: this.button,
        restoreFocus: this.button,
        onClose: /* @__PURE__ */ __name(() => {
          this.popup = null;
          this.button.setAttribute("aria-expanded", "false");
        }, "onClose")
      });
      this.button.setAttribute("aria-expanded", "true");
      const at = combo.matches().findIndex((m) => m.item.id === this.value);
      if (at >= 0) combo.hover(at);
      paint2();
      this.popup.reposition();
      input.focus({ preventScroll: true });
    }
    focus(options) {
      this.button.focus(options);
    }
  };
  var HdRegionToggle = class extends HdElement {
    static {
      __name(this, "HdRegionToggle");
    }
    static get observedAttributes() {
      return ["region", "pressed", "disabled"];
    }
    button;
    get pressed() {
      return this.flag("pressed");
    }
    set pressed(on) {
      this.setFlag("pressed", on);
    }
    build() {
      this.button = h("button", { type: "button", class: "btn icon ghost hd-region-toggle" });
      this.replaceChildren(this.button);
      this.button.addEventListener("click", () => {
        if (this.flag("disabled")) return;
        this.pressed = !this.pressed;
        this.emit("change");
      });
    }
    render() {
      const region = this.str("region", "sidebar") || "sidebar";
      const names = { toolbar: "Toolbar", sidebar: "Sidebar", header: "Header", footer: "Footer" };
      const name = own(names, region) ?? region;
      const glyphs = { toolbar: ["‹", "›"], sidebar: ["›", "‹"], header: ["˄", "˅"], footer: ["˅", "˄"] };
      const [shown, hidden] = own(glyphs, region) ?? ["‹", "›"];
      this.button.textContent = this.pressed ? shown : hidden;
      this.button.setAttribute("aria-pressed", String(this.pressed));
      this.button.setAttribute("aria-label", `${name} region`);
      this.button.setAttribute("tooltip", `${this.pressed ? "Hide" : "Show"} ${name}`);
      const key = regionShortcut(region);
      if (key) this.button.setAttribute("shortcut", key);
      this.button.disabled = this.flag("disabled");
    }
  };
  define("hd-area-header", HdAreaHeader);
  define("hd-view-switcher", HdViewSwitcher);
  define("hd-region-toggle", HdRegionToggle);

  // ui/kit/src/canvas/controller.ts
  var SHAPE_GLYPH = {
    single: "circle",
    list: "diamond",
    bundle: "square",
    item: "diamond-dot",
    handle: "ring"
  };
  var SOCKET_TYPES = ["any", "str", "int", "float", "bool", "model", "bundle", "item", "tool", "agent"];
  var NODE_CATEGORIES = ["source", "transform", "parallel", "human", "sink", "model", "logic", "bundle"];
  var CANVAS_PROPERTIES = [
    ...SOCKET_TYPES.map((t) => `--hd-socket-${t}`),
    "--hd-socket-unknown",
    ...NODE_CATEGORIES.map((c) => `--hd-node-header-${c}`),
    "--hd-node-header-default",
    "--hd-node-body",
    "--hd-node-text",
    "--hd-node-border",
    "--hd-node-selected",
    "--hd-link",
    "--hd-link-selected",
    "--hd-link-invalid",
    "--hd-reroute",
    "--hd-frame-fill",
    "--hd-frame-text",
    "--hd-frame-border",
    "--hd-canvas-bg",
    "--hd-canvas-grid"
  ];
  function readVocabulary(read2) {
    const get = /* @__PURE__ */ __name((p) => read2(p).trim(), "get");
    const socket = {};
    for (const t of SOCKET_TYPES) socket[t] = get(`--hd-socket-${t}`);
    socket.unknown = get("--hd-socket-unknown");
    const header = {};
    for (const c of NODE_CATEGORIES) header[c] = get(`--hd-node-header-${c}`);
    header.default = get("--hd-node-header-default");
    return {
      socket,
      header,
      node: { body: get("--hd-node-body"), text: get("--hd-node-text"), border: get("--hd-node-border"), selected: get("--hd-node-selected") },
      link: { normal: get("--hd-link"), selected: get("--hd-link-selected"), invalid: get("--hd-link-invalid") },
      reroute: get("--hd-reroute"),
      frame: { fill: get("--hd-frame-fill"), text: get("--hd-frame-text"), border: get("--hd-frame-border") },
      canvas: { bg: get("--hd-canvas-bg"), grid: get("--hd-canvas-grid") }
    };
  }
  __name(readVocabulary, "readVocabulary");
  function socketStyle(type, registered = DEFAULT_SHAPES) {
    let t = (type || "any").trim();
    let depth2 = 0;
    for (; ; ) {
      const m = /^list\[(.*)\]$/.exec(t);
      if (!m) break;
      t = m[1].trim();
      depth2 += 1;
    }
    const known = Object.hasOwn(registered, t);
    const shape = known ? registered[t] : void 0;
    return { base: known ? t : "unknown", shape: depth2 ? "list" : shape && Object.hasOwn(SHAPE_GLYPH, shape) ? shape : "single", known };
  }
  __name(socketStyle, "socketStyle");
  function headerColour(v, category) {
    return own(v.header, category) || own(v.header, "default") || "";
  }
  __name(headerColour, "headerColour");
  function socketColour(v, base) {
    return own(v.socket, base) || own(v.socket, "unknown") || "";
  }
  __name(socketColour, "socketColour");
  var DEFAULT_SHAPES = {
    any: "single",
    str: "single",
    int: "single",
    float: "single",
    bool: "single",
    model: "single",
    bundle: "bundle",
    item: "item",
    tool: "handle",
    agent: "handle"
  };
  function socketLabel(spec) {
    const l = (spec.label ?? "").trim();
    return l || spec.name;
  }
  __name(socketLabel, "socketLabel");
  function socketGeometry(shape, cx, cy, r, multi = false) {
    const glyph = own(SHAPE_GLYPH, shape) ?? "circle";
    const stretch = multi ? r * 1.6 : 0;
    const circle = /* @__PURE__ */ __name((x, y, rr) => [["A", x, y, rr]], "circle");
    switch (glyph) {
      case "circle":
        if (multi) {
          return { outline: capsule(cx, cy, r, stretch), inner: [], hollow: false };
        }
        return { outline: circle(cx, cy, r), inner: [], hollow: false };
      case "ring":
        return { outline: multi ? capsule(cx, cy, r, stretch) : circle(cx, cy, r), inner: [], hollow: true };
      case "diamond":
      case "diamond-dot": {
        const d = r * 1.25;
        const outline = [["M", cx, cy - d - stretch], ["L", cx + d, cy], ["L", cx, cy + d + stretch], ["L", cx - d, cy], ["Z"]];
        return { outline, inner: glyph === "diamond-dot" ? circle(cx, cy, r * 0.35) : [], hollow: false };
      }
      case "square": {
        const s = r * 0.95;
        return {
          outline: [["M", cx - s, cy - s - stretch], ["L", cx + s, cy - s - stretch], ["L", cx + s, cy + s + stretch], ["L", cx - s, cy + s + stretch], ["Z"]],
          inner: [],
          hollow: false
        };
      }
    }
  }
  __name(socketGeometry, "socketGeometry");
  function capsule(cx, cy, r, stretch) {
    const ops = [];
    const steps = 8;
    for (let i = 0; i <= steps; i += 1) {
      const a = Math.PI + Math.PI * i / steps;
      const x = cx + Math.cos(a) * r;
      const y = cy - stretch + Math.sin(a) * r;
      ops.push([i === 0 ? "M" : "L", round(x), round(y)]);
    }
    for (let i = 0; i <= steps; i += 1) {
      const a = Math.PI * i / steps;
      ops.push(["L", round(cx + Math.cos(a) * r), round(cy + stretch + Math.sin(a) * r)]);
    }
    ops.push(["Z"]);
    return ops;
  }
  __name(capsule, "capsule");
  function round(n) {
    return Math.round(n * 100) / 100;
  }
  __name(round, "round");
  function toSvgPath(ops) {
    return ops.map((op) => {
      if (op[0] === "Z") return "Z";
      if (op[0] === "A") {
        const [, x, y, r] = op;
        return `M ${x - r} ${y} A ${r} ${r} 0 1 0 ${x + r} ${y} A ${r} ${r} 0 1 0 ${x - r} ${y} Z`;
      }
      return `${op[0]} ${op[1]} ${op[2]}`;
    }).join(" ");
  }
  __name(toSvgPath, "toSvgPath");
  function linkCurve(x1, y1, x2, y2, curving = 0.5) {
    const dx = Math.max(24, Math.abs(x2 - x1) * curving);
    return [x1, y1, x1 + dx, y1, x2 - dx, y2, x2, y2];
  }
  __name(linkCurve, "linkCurve");

  // ui/kit/src/canvas/element.ts
  var SVG = "http://www.w3.org/2000/svg";
  function vocabulary(root2 = document.documentElement) {
    const cs = getComputedStyle(root2);
    return readVocabulary((p) => cs.getPropertyValue(p));
  }
  __name(vocabulary, "vocabulary");
  var HdSocket = class extends HdElement {
    static {
      __name(this, "HdSocket");
    }
    static get observedAttributes() {
      return ["type", "label", "name", "multi", "linked"];
    }
    svg;
    labelEl;
    build() {
      this.svg = document.createElementNS(SVG, "svg");
      this.svg.setAttribute("class", "hd-socket__glyph");
      this.svg.setAttribute("aria-hidden", "true");
      this.labelEl = h("span", { class: "hd-socket__label" });
      this.replaceChildren(this.svg, this.labelEl);
    }
    render() {
      const style = socketStyle(this.str("type", "any"));
      const multi = this.flag("multi");
      const r = 5;
      const w = 16;
      const hgt = multi ? 30 : 16;
      this.svg.setAttribute("viewBox", `0 0 ${w} ${hgt}`);
      this.svg.setAttribute("width", String(w));
      this.svg.setAttribute("height", String(hgt));
      this.svg.replaceChildren();
      const g = socketGeometry(style.shape, w / 2, hgt / 2, r, multi);
      const outline = document.createElementNS(SVG, "path");
      outline.setAttribute("d", toSvgPath(g.outline));
      outline.setAttribute("class", "hd-socket__shape");
      outline.style.setProperty("--hd-socket-color", `var(--hd-socket-${style.base})`);
      if (g.hollow) outline.setAttribute("data-hollow", "");
      this.svg.append(outline);
      if (g.inner.length) {
        const dot = document.createElementNS(SVG, "path");
        dot.setAttribute("d", toSvgPath(g.inner));
        dot.setAttribute("class", "hd-socket__dot");
        this.svg.append(dot);
      }
      const name = this.str("name");
      const text = name || this.hasAttribute("label") ? socketLabel({ name: name || this.str("type"), label: this.getAttribute("label") }) : "";
      this.labelEl.textContent = text;
      this.labelEl.hidden = !text;
      this.dataset.shape = style.shape;
      this.setAttribute("role", "img");
      this.setAttribute("aria-label", `${text || "socket"}: ${this.str("type", "any")}${multi ? ", multiple inputs" : ""}${this.flag("linked") ? ", linked" : ""}`);
    }
  };
  function trace(ctx, ops) {
    ctx.beginPath();
    for (const op of ops) {
      if (op[0] === "M") ctx.moveTo(op[1], op[2]);
      else if (op[0] === "L") ctx.lineTo(op[1], op[2]);
      else if (op[0] === "A") {
        ctx.moveTo(op[1] + op[3], op[2]);
        ctx.arc(op[1], op[2], op[3], 0, Math.PI * 2);
      } else ctx.closePath();
    }
  }
  __name(trace, "trace");
  function drawSocket(ctx, v, type, x, y, opts = {}) {
    const style = socketStyle(type);
    const g = socketGeometry(style.shape, x, y, opts.r ?? 5, opts.multi);
    const colour = socketColour(v, style.base);
    trace(ctx, g.outline);
    if (g.hollow) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = colour;
      ctx.stroke();
    } else {
      ctx.fillStyle = colour;
      ctx.fill();
      ctx.lineWidth = 1;
      ctx.strokeStyle = opts.outline ?? v.node.border;
      ctx.stroke();
    }
    if (g.inner.length) {
      trace(ctx, g.inner);
      ctx.fillStyle = v.node.body;
      ctx.fill();
    }
  }
  __name(drawSocket, "drawSocket");
  function drawLink(ctx, v, x1, y1, x2, y2, state = "normal", colour) {
    const [ax, ay, b1x, b1y, b2x, b2y, bx, by] = linkCurve(x1, y1, x2, y2);
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.bezierCurveTo(b1x, b1y, b2x, b2y, bx, by);
    ctx.lineWidth = state === "selected" ? 3 : 2;
    ctx.strokeStyle = state === "selected" ? v.link.selected : state === "invalid" ? v.link.invalid : colour ?? v.link.normal;
    if (state === "invalid") ctx.setLineDash([6, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  __name(drawLink, "drawLink");
  function drawReroute(ctx, v, x, y, selected = false) {
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fillStyle = v.reroute;
    ctx.fill();
    if (selected) {
      ctx.lineWidth = 2;
      ctx.strokeStyle = v.link.selected;
      ctx.stroke();
    }
  }
  __name(drawReroute, "drawReroute");
  function drawFrame(ctx, v, x, y, w, hgt, label, opts = {}) {
    ctx.fillStyle = opts.fill || v.frame.fill;
    ctx.strokeStyle = opts.selected ? v.node.selected : v.frame.border;
    ctx.lineWidth = opts.selected ? 2 : 1;
    ctx.beginPath();
    ctx.roundRect(x, y, w, hgt, 4);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = opts.text || v.frame.text;
    ctx.font = opts.font ?? "600 13px system-ui, sans-serif";
    ctx.textBaseline = "top";
    ctx.fillText(label, x + 8, y + 6);
  }
  __name(drawFrame, "drawFrame");
  function drawNodeHeader(ctx, v, category, x, y, w, title, opts = {}) {
    const hh = 22;
    const body = opts.bodyHeight ?? 26;
    ctx.beginPath();
    ctx.roundRect(x, y, w, hh + body, 5);
    ctx.fillStyle = v.node.body;
    ctx.fill();
    ctx.beginPath();
    ctx.roundRect(x, y, w, hh, [5, 5, 0, 0]);
    ctx.fillStyle = headerColour(v, category);
    ctx.fill();
    ctx.beginPath();
    ctx.roundRect(x, y, w, hh + body, 5);
    ctx.lineWidth = opts.selected ? 2 : 1;
    ctx.strokeStyle = opts.selected ? v.node.selected : v.node.border;
    ctx.stroke();
    ctx.fillStyle = v.node.text;
    ctx.font = opts.font ?? "600 12px system-ui, sans-serif";
    ctx.textBaseline = "middle";
    ctx.fillText(`▾ ${title}`, x + 8, y + hh / 2);
  }
  __name(drawNodeHeader, "drawNodeHeader");
  define("hd-socket", HdSocket);

  // ui/kit/src/hotkey/controller.ts
  var HotkeyCapture = class {
    static {
      __name(this, "HotkeyCapture");
    }
    listening = false;
    begin() {
      this.listening = true;
    }
    key(ev) {
      if (!this.listening) return { kind: "wait" };
      if (ev.key === "Escape" && !ev.ctrlKey && !ev.shiftKey && !ev.altKey && !ev.metaKey) {
        this.listening = false;
        return { kind: "cancel" };
      }
      const chord = chordFromKey(ev);
      if (!chord) return { kind: "wait" };
      this.listening = false;
      return { kind: "set", chord: formatChord(chord) };
    }
    cancel() {
      this.listening = false;
    }
  };

  // ui/kit/src/hotkey/element.ts
  var HdHotkey = class extends HdElement {
    static {
      __name(this, "HdHotkey");
    }
    static get observedAttributes() {
      return ["value", "label", "disabled", "invalid"];
    }
    button;
    capture = new HotkeyCapture();
    labelEl;
    outerLabel;
    keyEl;
    get value() {
      return this.str("value");
    }
    set value(v) {
      this.setAttribute("value", v);
    }
    get editingNow() {
      return this.capture.listening;
    }
    build() {
      this.upgradeProperty("value");
      this.outerLabel = h("span", { class: "hd-field__label", "aria-hidden": "true" });
      this.labelEl = h("span", { class: "hd-choice__label" });
      this.keyEl = h("kbd", { class: "hd-hotkey__key" });
      this.button = h("button", { type: "button", class: "hd-choice hd-hotkey" }, this.labelEl, this.keyEl);
      this.replaceChildren(this.outerLabel, this.button);
      registerField(this);
      this.button.addEventListener("click", () => {
        if (this.flag("disabled") || this.capture.listening) return;
        this.capture.begin();
        this.render();
      });
      this.button.addEventListener("keydown", (ev) => {
        if (!this.capture.listening) return;
        ev.preventDefault();
        ev.stopPropagation();
        const r = this.capture.key(ev);
        if (r.kind === "set") {
          this.value = r.chord;
          this.emit("change");
        }
        this.render();
      });
      this.button.addEventListener("blur", () => {
        if (this.capture.listening) {
          this.capture.cancel();
          this.render();
        }
      });
    }
    render() {
      const label = this.str("label");
      this.labelEl.textContent = label;
      this.labelEl.hidden = !label;
      this.outerLabel.textContent = label;
      const listening2 = this.capture.listening;
      this.keyEl.textContent = listening2 ? "Press a key…" : this.value ? displayChord(this.value) : "None";
      this.toggleAttribute("data-editing", listening2);
      this.button.setAttribute("aria-label", `${label || "Shortcut"}: ${listening2 ? "press a key" : this.value || "none"}`);
      this.button.disabled = this.flag("disabled");
      this.button.setAttribute("aria-invalid", String(this.hasAttribute("invalid")));
    }
    focus(options) {
      this.button.focus(options);
    }
    copyValue() {
      return this.value;
    }
    pasteValue(text) {
      if (this.flag("disabled")) {
        refuse(this.button, lockedReason(this));
        return false;
      }
      const chord = parseChord(text);
      if (!chord) {
        refuse(this.button, "Paste expected a shortcut, such as Ctrl+S");
        return false;
      }
      this.value = formatChord(chord);
      this.emit("change");
      return true;
    }
    resetToDefault() {
      if (this.flag("disabled")) return false;
      this.value = this.str("default");
      this.emit("change");
      return true;
    }
  };
  define("hd-hotkey", HdHotkey);

  // ui/kit/src/dnd/controller.ts
  var PAYLOAD_TYPE = "application/x-hdeck+json";
  var KIND_PREFIX = "application/x-hdeck-kind-";
  var KIND = /^[a-z][a-z0-9_-]{0,39}$/;
  function validKind(kind) {
    return KIND.test(kind);
  }
  __name(validKind, "validKind");
  function encodePayload(p) {
    if (!validKind(p.kind)) throw new Error(`invalid payload kind ${JSON.stringify(p.kind)}`);
    return [
      [PAYLOAD_TYPE, JSON.stringify(p)],
      [KIND_PREFIX + p.kind, ""],
      ["text/plain", typeof p.label === "string" ? p.label : p.kind]
    ];
  }
  __name(encodePayload, "encodePayload");
  function decodePayload(text) {
    if (!text) return null;
    try {
      const v = JSON.parse(text);
      if (v && typeof v === "object" && !Array.isArray(v) && typeof v.kind === "string" && validKind(v.kind)) {
        return v;
      }
    } catch {
    }
    return null;
  }
  __name(decodePayload, "decodePayload");
  function kindsFromTypes(types) {
    const kinds = /* @__PURE__ */ new Set();
    for (const t of types) {
      const lower = t.toLowerCase();
      if (lower.startsWith(KIND_PREFIX)) kinds.add(lower.slice(KIND_PREFIX.length));
      else if (lower === "files") kinds.add("file");
      else if (lower === "text/uri-list") kinds.add("uri");
      else if (lower === "text/plain") kinds.add("text");
    }
    return kinds;
  }
  __name(kindsFromTypes, "kindsFromTypes");
  function accepts(accepts2, kinds) {
    const want = accepts2.split(/\s+/).filter(Boolean);
    if (want.includes("*")) return kinds.size > 0;
    return want.some((k) => kinds.has(k));
  }
  __name(accepts, "accepts");

  // ui/kit/src/dnd/element.ts
  var installed5 = false;
  var depth = 0;
  var current3 = null;
  function targets() {
    return [...document.querySelectorAll("[data-hd-drop]")];
  }
  __name(targets, "targets");
  function clearStates() {
    for (const t of document.querySelectorAll("[data-hd-drop-state]")) t.removeAttribute("data-hd-drop-state");
    current3 = null;
  }
  __name(clearStates, "clearStates");
  function markReady(kinds) {
    for (const t of targets()) {
      if (t.hasAttribute("disabled")) continue;
      if (accepts(t.getAttribute("data-hd-drop") ?? "", kinds)) {
        if (t.getAttribute("data-hd-drop-state") !== "over") t.setAttribute("data-hd-drop-state", "ready");
      }
    }
  }
  __name(markReady, "markReady");
  function installDnd() {
    if (installed5) return;
    installed5 = true;
    document.addEventListener("dragstart", (ev) => {
      const src = ev.target?.closest?.("[data-hd-drag]");
      if (!src || !ev.dataTransfer) return;
      let payload = null;
      try {
        payload = decodePayload(src.getAttribute("data-hd-drag"));
      } catch {
        payload = null;
      }
      if (!payload) return;
      for (const [type, data] of encodePayload(payload)) ev.dataTransfer.setData(type, data);
      ev.dataTransfer.effectAllowed = "copyMove";
      src.setAttribute("data-hd-dragging", "");
    });
    document.addEventListener("dragend", (ev) => {
      ev.target?.removeAttribute?.("data-hd-dragging");
      depth = 0;
      clearStates();
    });
    document.addEventListener("dragenter", (ev) => {
      depth += 1;
      if (!ev.dataTransfer) return;
      markReady(kindsFromTypes([...ev.dataTransfer.types]));
    });
    document.addEventListener("dragleave", () => {
      depth = Math.max(0, depth - 1);
      if (depth === 0) clearStates();
    });
    document.addEventListener("dragover", (ev) => {
      if (!ev.dataTransfer) return;
      const kinds = kindsFromTypes([...ev.dataTransfer.types]);
      const t = ev.target?.closest?.("[data-hd-drop]") ?? null;
      if (current3 && current3 !== t) {
        current3.setAttribute("data-hd-drop-state", accepts(current3.getAttribute("data-hd-drop") ?? "", kinds) ? "ready" : "");
        if (current3.getAttribute("data-hd-drop-state") === "") current3.removeAttribute("data-hd-drop-state");
      }
      current3 = t;
      if (!t || t.hasAttribute("disabled")) return;
      if (accepts(t.getAttribute("data-hd-drop") ?? "", kinds)) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "copy";
        t.setAttribute("data-hd-drop-state", "over");
      } else {
        t.setAttribute("data-hd-drop-state", "reject");
      }
    });
    document.addEventListener("drop", (ev) => {
      const t = ev.target?.closest?.("[data-hd-drop]") ?? null;
      const dt = ev.dataTransfer;
      depth = 0;
      clearStates();
      if (!t || !dt) return;
      const kinds = kindsFromTypes([...dt.types]);
      if (!accepts(t.getAttribute("data-hd-drop") ?? "", kinds)) return;
      ev.preventDefault();
      t.dispatchEvent(
        new CustomEvent("hd-drop", {
          bubbles: true,
          detail: {
            payload: decodePayload(dt.getData(PAYLOAD_TYPE)),
            files: [...dt.files],
            uriList: dt.getData("text/uri-list"),
            text: dt.getData("text/plain"),
            kinds: [...kinds]
          }
        })
      );
    });
    const mark = /* @__PURE__ */ __name(() => {
      for (const s of document.querySelectorAll("[data-hd-drag]:not([draggable])")) s.setAttribute("draggable", "true");
    }, "mark");
    mark();
    new MutationObserver(mark).observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ["data-hd-drag"] });
  }
  __name(installDnd, "installDnd");

  // ui/kit/src/kit.ts
  var VERSION = "0.1.0";
  var api = {
    version: VERSION,
    /** "OK?" at the cursor. Resolves true when confirmed. */
    confirm: confirmDialog,
    /** A properties popup at the cursor. */
    popup: openPopup,
    /** A menu built in script: `hdkit.menu(items, {at: {x, y}})`. */
    menu: openMenu,
    pie: openPie,
    search: openSearch,
    closePopups: closeAll,
    isDevMode,
    setDevMode,
    keys: { parseChord, formatChord, displayChord, matchesChord },
    /** The canvas vocabulary: what P075 reads and draws. */
    canvas: { CANVAS_PROPERTIES, vocabulary, socketStyle, socketGeometry, socketLabel, toSvgPath, linkCurve, drawSocket, drawLink, drawReroute, drawFrame, drawNodeHeader }
  };
  if (!window.hdkit) {
    window.hdkit = api;
    const start = /* @__PURE__ */ __name(() => {
      install();
      installTooltips();
      installDnd();
    }, "start");
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
    else start();
  }
})();
