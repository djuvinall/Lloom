// The Lloom panel. Plain JS, no build step.
//
// Contract, not taste (INTEROP.md):
//   * every URL is RELATIVE ("api/jobs"), so the page works at /m/lloom/ hosted and at /
//     standalone;
//   * the shell protocol goes through static/vendor/module.js (window.hdeck), which posts
//     only to location.origin and filters inbound messages on ev.origin;
//   * a destructive action asks first with hdkit.confirm (static/vendor/kit.js), never
//     window.confirm; what a person should read goes through hdeck:report, never alert().
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = {
    status: null,
    inventory: null,
    jobs: [],
    assets: 0,
    detail: null,      // the job whose log is open
    logOffset: 0,
    timer: null,
    busy: false,
  };

  // panel.css paints k-badge tones: success | warning | error | accent. Nothing else.
  const TONES = {
    queued: "accent",
    running: "accent",
    succeeded: "success",
    failed: "error",
    cancelled: "warning",
    interrupted: "warning",
  };

  // -- plumbing --------------------------------------------------------------------

  async function request(url, options) {
    const res = await fetch(url, Object.assign({ headers: { accept: "application/json" } }, options || {}));
    let body = null;
    try {
      body = await res.json();
    } catch (err) {
      body = null;
    }
    if (!res.ok) {
      const detail = body && body.detail !== undefined
        ? (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail))
        : `${url} returned ${res.status}`;
      throw new Error(detail);
    }
    return body;
  }

  function post(url, payload) {
    return request(url, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify(payload || {}),
    });
  }

  function setBadge(el, text, tone) {
    el.textContent = text;
    el.dataset.tone = tone;
  }

  function report(severity, message) {
    if (window.hdeck && typeof window.hdeck.post === "function") {
      window.hdeck.post("hdeck:report", { severity: severity, message: message });
    }
  }

  function showError(prefix, message) {
    $(prefix + "-error-text").textContent = message;
    $(prefix + "-error").hidden = false;
  }

  function text(value, fallback) {
    return value === null || value === undefined || value === "" ? (fallback || "–") : String(value);
  }

  function num(value, places) {
    return typeof value === "number" && isFinite(value) ? value.toFixed(places) : "–";
  }

  function when(seconds) {
    if (!seconds) return "–";
    const ago = Date.now() / 1000 - seconds;
    if (ago < 60) return "just now";
    if (ago < 3600) return Math.round(ago / 60) + "m ago";
    if (ago < 86400) return Math.round(ago / 3600) + "h ago";
    return new Date(seconds * 1000).toLocaleDateString();
  }

  function duration(seconds) {
    const s = Math.max(0, Math.round(seconds || 0));
    if (s < 60) return s + "s";
    const m = Math.floor(s / 60);
    if (m < 60) return m + "m " + String(s % 60).padStart(2, "0") + "s";
    return Math.floor(m / 60) + "h " + String(m % 60).padStart(2, "0") + "m";
  }

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (key === "text") node.textContent = value;
      else if (key === "class") node.className = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    }
    for (const child of children || []) if (child) node.append(child);
    return node;
  }

  function fillSelect(select, options, keep) {
    const previous = keep ? select.value : null;
    select.replaceChildren(...options.map(([value, label]) => el("option", { value: value, text: label })));
    if (previous !== null && options.some(([value]) => value === previous)) select.value = previous;
  }

  // -- overview --------------------------------------------------------------------

  async function loadOverview() {
    $("overview-error").hidden = true;
    try {
      state.status = await request("api/status");
    } catch (err) {
      $("overview-skeleton").hidden = true;
      $("overview").dataset.status = "error";
      setBadge($("status"), "error", "error");
      showError("overview", err.message || String(err));
      return false;
    }
    renderOverview();
    return Boolean(state.status.workspace.root);
  }

  function renderOverview() {
    const st = state.status;
    $("overview-skeleton").hidden = true;
    const configured = Boolean(st.workspace.root) && !st.python.problem;
    $("unconfigured").hidden = configured;
    $("overview-body").hidden = !configured;
    for (const id of ["launch", "jobs-panel", "runs-panel"]) $(id).hidden = !configured;
    $("doctor").disabled = !st.workspace.root;
    $("sync").disabled = !st.workspace.root;
    if (!configured) {
      $("overview").dataset.status = "empty";
      setBadge($("status"), "not set up", "warning");
      $("unconfigured-problem").textContent = st.workspace.problem || st.python.problem || "";
      return;
    }
    $("overview").dataset.status = "ready";
    $("ws-root").textContent = st.workspace.root + "  (" + st.workspace.source + ")";
    $("ws-python").textContent = st.python.path + "  (" + st.python.source + ")";
    const doc = st.doctor || {};
    if (!doc.checked) {
      $("ws-doctor").textContent = "not checked yet – press Check interpreter";
    } else if (doc.ok) {
      const pk = doc.packages || {};
      $("ws-doctor").textContent = "Python " + text(doc.python) + ", torch " + text(pk.torch) +
        (doc.cuda ? ", CUDA on " + text(doc.device) : ", CPU only") +
        ", lloom " + text(doc.lloom) + (pk.anthropic ? ", anthropic " + pk.anthropic : ", no anthropic SDK");
    } else {
      $("ws-doctor").textContent = "has a problem";
    }
    $("doctor-problem").hidden = !(doc.checked && !doc.ok);
    $("doctor-problem-text").textContent = doc.problem || "";
    const lib = st.library;
    $("ws-library").textContent = lib ? lib.summary + " · synced " + when(lib.synced_at) : "not synced yet";
    $("stat-active").textContent = String(st.jobs.active);
    const busy = st.jobs.active > 0;
    setBadge($("status"), busy ? st.jobs.hold : "ready", busy ? "accent" : "success");
  }

  // -- inventory: the launcher's choices and the runs table ---------------------------

  async function loadInventory() {
    $("runs-error").hidden = true;
    try {
      state.inventory = await request("api/inventory");
    } catch (err) {
      $("runs-skeleton").hidden = true;
      showError("runs", err.message || String(err));
      return;
    }
    const inv = state.inventory;
    fillSelect($("recipe"), inv.recipes.map((r) => [r.name, r.name + " – " + r.stages.map((s) => s.name).join(" → ")]), true);
    fillSelect($("stage"), inv.stages.map((s) => [s.name, s.name]), true);
    fillSelect($("preset"), [["", "none"]].concat(inv.presets.map((p) => [p.name, p.name + (p.approx_params ? " (~" + Math.round(p.approx_params / 1e6) + "M)" : "")])), true);
    $("stat-runs").textContent = String(inv.runs.length);
    $("stat-recipes").textContent = String(inv.recipes.length);
    renderRuns(inv.runs);
  }

  function renderRuns(runs) {
    $("runs-skeleton").hidden = true;
    $("runs-panel").dataset.status = runs.length ? "ready" : "empty";
    $("runs-empty").hidden = runs.length > 0;
    $("runs-wrap").hidden = runs.length === 0;
    $("runs").replaceChildren(...runs.map((run) => {
      const pre = (run.metrics && run.metrics.pretrain) || {};
      const sft = (run.metrics && run.metrics.sft) || {};
      const judge = run.judge || null;
      const best = sft.best_val_loss !== null && sft.best_val_loss !== undefined ? sft.best_val_loss : pre.best_val_loss;
      const use = el("button", {
        class: "btn ghost", type: "button", text: run.name, title: "Use this run name in the launcher",
        onclick: () => { $("run-name").value = run.name; $("run-name").focus(); },
      });
      return el("tr", {}, [
        el("td", {}, [use]),
        el("td", { text: when(run.updated_at) }),
        el("td", { class: "mono-sm", text: text(run.model, "no checkpoint") }),
        el("td", { class: "lloom-num", text: num(best, 4) }),
        el("td", { class: "lloom-num", text: num(pre.val_perplexity, 2) }),
        el("td", { class: "lloom-num", text: judge && judge.mean_score !== null && judge.mean_score !== undefined ? judge.mean_score.toFixed(2) + " / " + judge.max_score : "–" }),
      ]);
    }));
  }

  async function loadAssets() {
    try {
      const body = await request("api/assets");
      state.assets = (body.assets || []).length;
    } catch (err) {
      state.assets = 0;
    }
    $("stat-assets").textContent = String(state.assets);
  }

  // -- jobs ------------------------------------------------------------------------

  async function loadJobs() {
    $("jobs-error").hidden = true;
    try {
      const body = await request("api/jobs?limit=30");
      state.jobs = body.jobs || [];
      $("hold").hidden = !body.hold;
      if (body.hold) setBadge($("hold"), body.hold, "accent");
    } catch (err) {
      $("jobs-skeleton").hidden = true;
      showError("jobs", err.message || String(err));
      return;
    }
    renderJobs();
  }

  function progressCell(job) {
    if (job.done) return el("td", { text: job.ok ? "done" : "–" });
    const p = job.progress_detail || {};
    if (typeof job.progress === "number") {
      const bar = el("span", { class: "lloom-bar" }, [el("span", { style: "width:" + Math.round(job.progress * 100) + "%" })]);
      return el("td", { class: "lloom-num" }, [bar, " " + Math.round(job.progress * 100) + "%" + (typeof p.loss === "number" ? " · loss " + p.loss.toFixed(3) : "")]);
    }
    return el("td", { text: job.status === "queued" ? "waiting" : "working" });
  }

  function renderJobs() {
    $("jobs-skeleton").hidden = true;
    const jobs = state.jobs;
    $("jobs-panel").dataset.status = jobs.length ? "ready" : "empty";
    $("jobs-empty").hidden = jobs.length > 0;
    $("jobs-wrap").hidden = jobs.length === 0;
    $("jobs").replaceChildren(...jobs.map((job) => {
      const badge = el("span", { class: "k-badge", text: job.status });
      badge.dataset.tone = TONES[job.status] || "accent";
      const actions = [el("button", { class: "btn ghost", type: "button", text: "Log", onclick: () => openLog(job.job_id) })];
      if (!job.done) {
        actions.push(el("button", { class: "btn ghost danger", type: "button", text: "Cancel", onclick: () => cancelJob(job) }));
      }
      const row = el("tr", { class: state.detail === job.job_id ? "lloom-row-active" : "" }, [
        el("td", {}, [badge]),
        el("td", { text: job.title, title: job.error || job.job_id }),
        el("td", { text: text(job.stage) }),
        progressCell(job),
        el("td", { text: when(job.started_at || job.created_at) }),
        el("td", { class: "lloom-num", text: job.started_at ? duration(job.elapsed_seconds) : "–" }),
        el("td", {}, [el("div", { class: "actions" }, actions)]),
      ]);
      return row;
    }));
    const active = jobs.filter((j) => !j.done).length;
    $("stat-active").textContent = String(active);
  }

  async function cancelJob(job) {
    let ok = true;
    if (window.hdkit && typeof window.hdkit.confirm === "function") {
      ok = await window.hdkit.confirm({
        title: "Stop this job?",
        message: job.title + " and every process it started will be stopped. A pretraining run can resume from its last checkpoint.",
        confirm: "Stop job",
        danger: true,
      });
    }
    if (!ok) return;
    try {
      const out = await post("api/jobs/" + encodeURIComponent(job.job_id) + "/cancel");
      report(out.cancelled ? "warning" : "info", out.cancelled ? "Stopping " + job.title : job.title + " had already ended");
    } catch (err) {
      report("error", "Could not stop " + job.title + ": " + (err.message || err));
    }
    tick();
  }

  async function openLog(jobId) {
    state.detail = jobId;
    state.logOffset = 0;
    $("job-log").textContent = "";
    $("job-detail").hidden = false;
    await followLog();
    renderJobs();
    $("job-log").focus();
  }

  function closeLog() {
    state.detail = null;
    $("job-detail").hidden = true;
    renderJobs();
  }

  async function followLog() {
    const jobId = state.detail;
    if (!jobId) return;
    const job = state.jobs.find((j) => j.job_id === jobId);
    if (job) {
      $("job-detail-title").textContent = job.title;
      $("job-detail-id").textContent = job.job_id;
      const meta = ["status " + job.status];
      if (job.run_name) meta.push("run " + job.run_name);
      if (job.stages && job.stages.length) meta.push("stages " + job.stages.map((s) => s.name + " (" + s.status + ")").join(", "));
      if (job.error) meta.push(job.error);
      if (job.on_complete) meta.push("then graph " + job.on_complete.graph + ": " + job.on_complete.status);
      $("job-detail-meta").textContent = meta.join(" · ");
    }
    try {
      const chunk = await request("api/jobs/" + encodeURIComponent(jobId) + "/log?offset=" + state.logOffset);
      if (state.detail !== jobId) return;
      if (chunk.text) {
        const log = $("job-log");
        const atEnd = log.scrollTop + log.clientHeight >= log.scrollHeight - 8;
        log.append(document.createTextNode(chunk.text));
        if (atEnd) log.scrollTop = log.scrollHeight;
      }
      state.logOffset = chunk.offset;
    } catch (err) {
      $("job-detail-meta").textContent = "Could not read the log: " + (err.message || err);
    }
  }

  // -- launching -------------------------------------------------------------------

  function syncMode() {
    const stage = $("mode").value === "stage";
    $("recipe").hidden = stage;
    $("stage").hidden = !stage;
    $("checkpoint-row").hidden = !stage;
    $("dry-run-row").hidden = stage;
  }

  async function launch(ev) {
    ev.preventDefault();
    $("launch-error").hidden = true;
    const kind = $("mode").value;
    const payload = {
      kind: kind,
      run_name: $("run-name").value.trim(),
      preset: $("preset").value,
      sets: $("sets").value.split("\n").map((s) => s.trim()).filter(Boolean),
      on_complete_graph: $("graph").value.trim(),
    };
    if (kind === "pipeline") {
      payload.recipe = $("recipe").value;
      payload.dry_run = $("dry-run").checked;
    } else {
      payload.stage = $("stage").value;
      payload.checkpoint = $("checkpoint").value.trim();
    }
    $("start").disabled = true;
    try {
      const body = await post("api/jobs", payload);
      report("info", "Started " + body.job.title);
      await loadJobs();
      openLog(body.job.id);
    } catch (err) {
      showError("launch", err.message || String(err));
    } finally {
      $("start").disabled = false;
    }
  }

  // -- actions ---------------------------------------------------------------------

  async function runDoctor() {
    $("doctor").disabled = true;
    $("ws-doctor").textContent = "checking…";
    const job = "doctor";
    if (window.hdeck && typeof window.hdeck.post === "function") window.hdeck.post("hdeck:job", { id: job, label: "Checking the Lloom interpreter", state: "running" });
    try {
      const result = await post("api/doctor");
      report(result.ok ? "success" : "warning", result.ok ? "Lloom's interpreter is ready" : "Lloom's interpreter has a problem: " + result.problem);
    } catch (err) {
      report("error", "Could not check the interpreter: " + (err.message || err));
    } finally {
      if (window.hdeck && typeof window.hdeck.post === "function") window.hdeck.post("hdeck:job", { id: job, label: "", state: "done" });
      $("doctor").disabled = false;
      await loadOverview();
    }
  }

  async function runSync() {
    $("sync").disabled = true;
    try {
      const result = await post("api/library/sync");
      report("success", "Lloom library: " + result.summary);
    } catch (err) {
      report("error", "Library sync failed: " + (err.message || err));
    } finally {
      $("sync").disabled = false;
      await Promise.all([loadOverview(), loadAssets()]);
    }
  }

  // -- polling: fast while something runs, slow otherwise ------------------------------

  async function tick() {
    if (state.busy) return;
    state.busy = true;
    try {
      await loadJobs();
      if (state.detail) await followLog();
      const active = state.jobs.some((j) => !j.done);
      if (active || (state.status && state.status.jobs.active)) await loadOverview();
    } finally {
      state.busy = false;
    }
  }

  function schedule() {
    clearTimeout(state.timer);
    const active = state.jobs.some((j) => !j.done);
    state.timer = setTimeout(async () => {
      await tick();
      if (!state.jobs.some((j) => !j.done) && active) {
        await Promise.all([loadInventory(), loadAssets()]);  // a job ended: new checkpoints
      }
      schedule();
    }, active ? 2000 : 10000);
  }

  async function loadAll() {
    const configured = await loadOverview();
    if (!configured) return;
    await Promise.all([loadInventory(), loadJobs(), loadAssets()]);
  }

  $("refresh").addEventListener("click", loadAll);
  $("doctor").addEventListener("click", runDoctor);
  $("sync").addEventListener("click", runSync);
  $("mode").addEventListener("change", syncMode);
  $("launch-form").addEventListener("submit", launch);
  $("job-close").addEventListener("click", closeLog);
  if (window.hdeck && typeof window.hdeck.onRefresh === "function") window.hdeck.onRefresh(loadAll);

  // Escape is NOT handled here: the shell owns it inside same-origin frames.

  syncMode();
  loadAll().then(schedule);
})();
