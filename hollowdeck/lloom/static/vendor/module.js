/* `window.hdeck` -- the panel side of the shell <-> panel protocol, written once.
 *
 * Every panel the shell shows is a same-origin iframe with the shell above it, and
 * until this file each page invented its own plumbing for talking upward. The module
 * manager got it right; the welcome panel got it right a second time, independently;
 * the System Monitor did not implement it at all and is rescued only because the
 * shell reaches into the frame; and the starter module -- the one every future module
 * is copied from -- got it wrong three ways at once. Four surfaces, four answers to
 * one question. This is the answer, and vendoring it is what stops the fifth.
 *
 * Two of those rules are security, not tidiness, so they are stated at the call site
 * as well as here:
 *
 *   * `post` always targets `location.origin`, never `"*"`. A panel is same-origin
 *     with its host by construction, so naming the origin costs nothing -- and `"*"`
 *     would hand the message to *whatever* page happened to frame this one.
 *   * `on` always checks `ev.origin`, never `ev.source`. `ev.source` says which
 *     window sent a message, not which origin it came from; any page that can get a
 *     handle on this window satisfies it. It is not a security check and must not be
 *     used as one.
 *
 * What it refuses to do:
 *
 *   * Nothing runs on load. `focusFirst` is offered, not invoked -- a panel that
 *     grabs focus while the shell restores a saved layout fights whoever is typing.
 *   * No automatic Escape handling. The shell already attaches a `keydown` listener
 *     inside every same-origin frame and returns focus to the area, so most modules
 *     need nothing; `bindEscape` exists for the rest and yields to a page that has
 *     already consumed the key.
 *   * There is no focus-shell message, under any name. The starter module invented
 *     one and posted it for years; nothing in the repo has ever listened for it. The
 *     messages below are the whole protocol, and a panel that needs another one needs
 *     the shell to grow a receiver first -- which is exactly what P031's zoom pair did:
 *     `hdeck:zoom-capable` has a receiver in shell.js before `onZoom` sends it.
 *
 *   * Nothing here applies Resolution Scale. The shell writes `--hd-ui-scale` straight
 *     onto each same-origin frame's root element, the same reach it already uses to
 *     hear Escape inside a view -- so a panel gets the scale whether or not it links
 *     this file, and a page opened standalone keeps 1. Per-*view* zoom is the opposite
 *     case: only the view knows what its own zoom means, so that one is a message.
 *
 * A classic script: no build step, no dependency, no module system. It attaches one
 * global and tolerates being linked twice. Like `darkglass.css` and `panel.css`, it
 * is a snapshot -- copied verbatim into each surface that renders, never linked
 * across origins or mount prefixes, because a module served at `/m/<id>/` may only
 * use relative URLs. See `docs/arch/modules.md`.
 */
(function () {
  "use strict";

  if (window.hdeck) return; // linked twice: the first copy wins, and they are equal

  // The whole protocol. A panel sends CHANGED, OPEN_PANEL, ZOOM_CAPABLE, UI_SCALE and
  // DOCUMENT, and receives REFRESH and ZOOM. Kept as literals so a typo is a name
  // error, not a silent no-op -- and every one of them has a receiver in shell.js.
  const CHANGED = "hdeck:modules-changed";
  const OPEN_PANEL = "hdeck:open-panel";
  const REFRESH = "hdeck:refresh";
  const ZOOM = "hdeck:zoom";
  const ZOOM_CAPABLE = "hdeck:zoom-capable";
  const UI_SCALE = "hdeck:ui-scale";
  const DOCUMENT = "hdeck:document";

  // Where focus goes when a panel asks for it: the author's explicit mark, else the
  // first control that is actually reachable by Tab.
  const FOCUS_MARK = "[data-hdeck-focus-first]";
  const FOCUS_FALLBACK = ".btn, .input, [tabindex]";

  /* Is there a shell above us? Reading `window.parent` can throw when the parent is
   * cross-origin, which is a "no" and not a crash: the same page has to work opened
   * directly, where the parent is this window. */
  function inShell() {
    try {
      return !!window.parent && window.parent !== window;
    } catch (e) {
      return false; // cross-origin parent, or none: standalone as far as we care
    }
  }

  /* Send one message up to the shell. Returns false when there is no shell to send
   * to, which is a normal standalone page and not an error worth throwing over.
   *
   * The target origin is `location.origin` -- never `"*"`. See the header. `type`
   * is applied last so a payload key called `type` cannot rewrite the message's
   * own name. */
  function post(type, payload) {
    if (!inShell()) return false;
    try {
      window.parent.postMessage(Object.assign({}, payload || {}, { type: type }), location.origin);
      return true;
    } catch (e) {
      return false; // the shell went away mid-call, or the origin is opaque
    }
  }

  /* Listen for one message type from the shell. Returns the unsubscribe -- keep it
   * if the panel ever tears its view down, ignore it if it lives for the page.
   *
   * The origin check is the security boundary: `ev.origin === location.origin`, and
   * deliberately NOT `ev.source === window.parent`. See the header. */
  function on(type, handler) {
    const listener = function (ev) {
      if (ev.origin !== location.origin) return;
      const data = ev.data;
      if (!data || data.type !== type) return;
      handler(data, ev);
    };
    window.addEventListener("message", listener);
    return function off() {
      window.removeEventListener("message", listener);
    };
  }

  /* Tell the shell the module set may have changed, so it can refetch its panel
   * list and drop frames whose panel is gone. `reason` is what the verb was. */
  function notifyChanged(reason) {
    return post(CHANGED, { reason: reason || "change" });
  }

  /* Ask the shell to show a panel in the area this request came from. Standalone
   * there is no area, so `fallbackUrl` is a plain navigation to the same view. */
  function openPanel(panelId, fallbackUrl) {
    if (post(OPEN_PANEL, { panel: panelId })) return;
    if (fallbackUrl) location.href = fallbackUrl;
  }

  /* The shell asks every other frame showing the same view to refetch after a
   * change made from the dock or a second window. Refetch; do not notify back, or
   * two panels ping-pong. */
  function onRefresh(handler) {
    return on(REFRESH, handler);
  }

  /* Ask the shell to change Resolution Scale for every window and every frame it is
   * showing (P031). Only the settings panel has any business calling this; it is here
   * rather than in that page so the one rule about `targetOrigin` keeps holding for it
   * too. Returns false standalone, where there is no shell to ask and the caller should
   * fall back to setting `--hd-ui-scale` on its own root. */
  function setUiScale(scale) {
    if (typeof scale !== "number" || !isFinite(scale)) return false;
    return post(UI_SCALE, { scale: scale });
  }

  /* Name the document this view is editing, for the shell's title bar -- Blender's
   * `<logo> (Unsaved) - Blender 5.1.2`, where the *document* is the part worth reading
   * (P031). `null` or an empty name means "this view has no document", which is the
   * normal case: a monitor, a log, a terminal and a settings page all edit nothing, and
   * the title bar says `(Unsaved)` until something says otherwise. `dirty` marks unsaved
   * changes. Sent, not asked for: the shell shows whatever the focused area last said. */
  function setDocument(name, dirty) {
    return post(DOCUMENT, { name: name || null, dirty: dirty === true });
  }

  /* Per-view zoom (P031). A view MAY declare that Ctrl +/-/0 and Ctrl+Wheel mean
   * something inside it -- the terminal scales its font, and nothing else has to. Call
   * this once with a handler taking a step: +1 in, -1 out, 0 reset.
   *
   * Two routes reach the handler and both are needed. The key or the wheel lands in
   * whichever document has focus, so a view whose own document is focused hears it
   * directly here; when the *shell* has focus -- straight after a chord, or a click on
   * an area header -- the shell forwards the same step as a message. Declaring capability
   * upward is what lets the shell know whether to intercept the key at all: a view that
   * never calls this keeps browser zoom, which is the correct fallback and not a bug.
   *
   * `preventDefault` is deliberate and only ever runs for a view that asked for the key:
   * the browser would otherwise zoom the whole window, which is the thing this replaces.
   * Returns the unsubscribe. */
  function onZoom(handler) {
    if (typeof handler !== "function") return function off() {};
    const step = function (n, ev) {
      if (ev && ev.cancelable) ev.preventDefault();
      handler(n);
    };
    const keys = function (ev) {
      if (!ev.ctrlKey || ev.altKey || ev.metaKey || ev.defaultPrevented) return;
      // Matched on the physical key, like the shell's own chord table, so `=` is `=`
      // whatever Shift makes of it on the current layout.
      const code = ev.code || "";
      if (code === "Equal" || code === "NumpadAdd" || ev.key === "+" || ev.key === "=") step(1, ev);
      else if (code === "Minus" || code === "NumpadSubtract" || ev.key === "-" || ev.key === "_") step(-1, ev);
      else if (code === "Digit0" || code === "Numpad0" || ev.key === "0") step(0, ev);
    };
    const wheel = function (ev) {
      if (!ev.ctrlKey || !ev.deltaY) return;
      step(ev.deltaY < 0 ? 1 : -1, ev);
    };
    document.addEventListener("keydown", keys);
    // Not passive: the whole point is to stop the browser zooming instead.
    window.addEventListener("wheel", wheel, { passive: false });
    const offMessage = on(ZOOM, function (data) {
      const n = typeof data.step === "number" ? data.step : 0;
      handler(n);
    });
    post(ZOOM_CAPABLE, {});
    return function off() {
      document.removeEventListener("keydown", keys);
      window.removeEventListener("wheel", wheel);
      offMessage();
    };
  }

  function reachable(node) {
    if (!node || node.disabled) return false;
    if (typeof node.closest === "function" && node.closest("[hidden]")) return false;
    return typeof node.focus === "function";
  }

  /* Put focus somewhere sensible. Call it from a button, a route change, or an
   * explicit "the panel is now showing" -- NOT on load; see the header.
   *
   * `[data-hdeck-focus-first]` is honoured as written, including `tabindex="-1"`,
   * because the author said so on purpose. The fallback scan skips `tabindex="-1"`:
   * an element held out of the tab order is not what "the first control" means. */
  function focusFirst(root) {
    const scope = root || document;
    const marked = scope.querySelector(FOCUS_MARK);
    let target = reachable(marked) ? marked : null;
    if (!target) {
      const candidates = scope.querySelectorAll(FOCUS_FALLBACK);
      for (let i = 0; i < candidates.length; i += 1) {
        const node = candidates[i];
        if (node.getAttribute("tabindex") === "-1") continue;
        if (reachable(node)) { target = node; break; }
      }
    }
    if (!target) return false;
    try {
      target.focus();
      return true;
    } catch (e) {
      return false;
    }
  }

  /* Escape, for the rare panel that wants it. The shell already handles Escape for
   * same-origin frames by returning focus to the area, so reach for this only when
   * the panel has its own meaning for the key -- restoring a draft, closing an
   * editor -- and let it bubble the rest of the time.
   *
   * `defaultPrevented` is the yield: a page that already consumed Escape (the
   * module manager's roots editor restores its saved list that way) has said the
   * key is spoken for, and a second handler firing on the same press is the bug
   * this guard exists to prevent. Returns the unsubscribe. */
  function bindEscape(handler) {
    const listener = function (ev) {
      if (ev.key !== "Escape" || ev.defaultPrevented) return;
      handler(ev);
    };
    document.addEventListener("keydown", listener);
    return function off() {
      document.removeEventListener("keydown", listener);
    };
  }

  /* Build an element with a class and text. `textContent`, never `innerHTML`: a
   * panel renders module names, file paths, and error strings it did not write. */
  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  /* Run `fn` once the DOM is there. Safe whether the script is in `<head>`, at the
   * end of `<body>`, or added late -- the last case would never see the event. */
  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn, { once: true });
    } else {
      fn();
    }
  }

  window.hdeck = {
    inShell: inShell,
    post: post,
    on: on,
    notifyChanged: notifyChanged,
    openPanel: openPanel,
    onRefresh: onRefresh,
    onZoom: onZoom,
    setUiScale: setUiScale,
    setDocument: setDocument,
    bindEscape: bindEscape,
    focusFirst: focusFirst,
    el: el,
    ready: ready,
  };
})();
