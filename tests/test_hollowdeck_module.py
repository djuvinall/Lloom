"""The ``lloom`` HollowDeck module (``hollowdeck/lloom``): its contract and its behaviour.

The module is loaded exactly as HollowDeck loads it -- by file location, never by name
-- because its directory shares a name with the ``lloom`` framework package, and an
``import lloom`` would pick whichever one the path happened to favour.

Two halves:

* **The contract** (HollowDeck's INTEROP.md): the manifest and its tool declarations,
  the guard's two modes, the required routes, relative URLs at the right depth, the UI
  kit rules, the byte-identical vendored files, the entry point.
* **The behaviour**, against a throwaway fake workspace: the *real* ``run_pipeline.py``
  / ``judge.py`` and the real ``lloom`` config, pipeline and judge code, with stage
  scripts replaced by fakes that print what a real stage prints and write what it
  writes -- so jobs, stage and progress parsing, runs, metrics, generation, judging (a
  fake Ollama), SFT data, the Library sync, the per-recipe nodes and the follow-up graph
  run (a fake core) are all exercised without torch, a GPU or a network.
"""
from __future__ import annotations

import hashlib
import http.server
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")  # the serve extra
pytest.importorskip("httpx")    # FastAPI's TestClient (the dev extra)
pytest.importorskip("yaml")
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "hollowdeck" / "lloom"
STATIC = MODULE_DIR / "static"
OWN_STATIC = [p for p in STATIC.rglob("*") if p.is_file() and "vendor" not in p.parts]
MANIFEST = json.loads((MODULE_DIR / "module.json").read_text(encoding="utf-8"))


def _load_main():
    name = "hdeck_lloom_main_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / "__main__.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


MAIN = _load_main()
PKG = MAIN.load_package()
GUARD = MAIN.load_guard()
WS = importlib.import_module(PKG.__name__ + ".workspace")
JOBS = importlib.import_module(PKG.__name__ + ".jobs")
LIBRARY = importlib.import_module(PKG.__name__ + ".library")
PROC = importlib.import_module(PKG.__name__ + ".vendor.proc")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _until(predicate, timeout=20.0, step=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    raise AssertionError("timed out waiting")


# ======================================================================================
# the contract
# ======================================================================================

def test_manifest_required_keys_and_identity():
    for key in ("id", "version", "kind", "command"):
        assert key in MANIFEST, key
    assert MANIFEST["id"] == MODULE_DIR.name == "lloom"
    assert re.fullmatch(r"[a-z][a-z0-9_]{0,63}", MANIFEST["id"])
    assert MANIFEST["kind"] == "process"
    assert re.fullmatch(r"\d+\.\d+\.\d+", MANIFEST["version"])
    assert MANIFEST["api_version"] == 1
    assert MANIFEST["provenance"] == "custom"


def test_command_and_verify_name_no_absolute_path():
    for key in ("command", "verify"):
        for arg in MANIFEST[key]:
            assert not os.path.isabs(arg) and not re.match(r"^[A-Za-z]:", arg), arg


def test_tools_file_is_relative_inside_the_data_dir():
    tools_file = MANIFEST["tools_file"]
    assert not os.path.isabs(tools_file) and not re.match(r"^[A-Za-z]:", tools_file)
    assert not tools_file.startswith(("/", "\\"))
    assert all(part not in (".", "..") for part in re.split(r"[\\/]", tools_file))


def test_every_tool_declaration_passes_the_cores_rules():
    assert LIBRARY.validate_tools(MANIFEST["tools"], "module.json tools") == []


def test_every_tool_writes_effects_and_a_full_doc():
    # An absent effects is `undeclared`, and gated like executes (P098): write it out.
    for tool in MANIFEST["tools"]:
        assert tool["effects"] in ("none", "reads", "writes", "executes", "network"), tool["id"]
        assert set(tool["doc"]) == {"what", "how", "why", "best_uses"}, tool["id"]
        assert tool.get("description"), tool["id"]


def test_tools_that_ask_a_model_say_so():
    by_id = {t["id"]: t for t in MANIFEST["tools"]}
    assert by_id["generate"]["calls_model"] is True
    assert by_id["judge"]["calls_model"] is True
    assert by_id["judge"]["effects"] == "network"  # the anthropic provider leaves the machine


def test_manifest_ids_leave_the_recipe_node_namespace_free():
    # tools_file nodes are pipeline_<recipe>; the manifest wins a collision, so it must
    # never use that prefix itself.
    assert not any(t["id"].startswith("pipeline_") for t in MANIFEST["tools"])


def test_every_declared_tool_has_a_handler_and_every_handler_is_declared(tmp_path):
    app = _app(tmp_path, workspace=None)
    try:
        declared = {t["id"] for t in MANIFEST["tools"]}
        assert declared == set(app.state.service.tools)
    finally:
        app.state.service.shutdown()


# -- the guard, both modes -------------------------------------------------------------

def _guarded(tmp_path, secret=""):
    app = _app(tmp_path, workspace=None)
    return app, TestClient(GUARD.ModuleGuard(app, secret, module_id="lloom"))


def test_hosted_refuses_a_request_without_the_secret(tmp_path):
    app, client = _guarded(tmp_path, "per-spawn")
    try:
        assert client.get("/health").status_code == 421
        assert client.get("/health", headers={"X-HDeck-Module-Secret": "nope"}).status_code == 421
    finally:
        app.state.service.shutdown()


def test_hosted_answers_the_secret_whatever_the_host_says(tmp_path):
    app, client = _guarded(tmp_path, "per-spawn")
    try:
        res = client.get("/health", headers={"X-HDeck-Module-Secret": "per-spawn",
                                             "Host": "127.0.0.1:61234"})
        assert res.status_code == 200
    finally:
        app.state.service.shutdown()


def test_standalone_allows_only_loopback_on_its_own_port(tmp_path):
    app, client = _guarded(tmp_path)
    try:
        assert client.get("/health", headers={"Host": "evil.example"}).status_code == 421
        # TestClient's server is port 80: the one case where a browser omits the port.
        assert client.get("/health", headers={"Host": "127.0.0.1"}).status_code == 200
    finally:
        app.state.service.shutdown()


# -- the routes --------------------------------------------------------------------------

def test_health_module_json_panel_favicon_lifecycle(tmp_path):
    app = _app(tmp_path, workspace=None)
    client = TestClient(app)
    try:
        health = client.get("/health").json()
        assert health["ok"] is True and health["module"] == "lloom"
        assert client.get("/module.json").json() == MANIFEST
        assert client.get("/").status_code == 200
        assert client.get("/favicon.ico").status_code == 204
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/lifecycle").json()["hold"] is False
    finally:
        app.state.service.shutdown()


# -- relative URLs, and at the right depth -----------------------------------------------

_ABSOLUTE = re.compile(r"""(?:href|src|action)\s*=\s*["']/(?!/)|fetch\(\s*["'`]/(?!/)|request\(\s*["'`]/(?!/)|post\(\s*["'`]/(?!/)""")


def test_no_root_absolute_url_in_the_panel():
    for path in OWN_STATIC:
        if path.suffix in {".html", ".js"}:
            assert not _ABSOLUTE.search(_read(path)), f"root-absolute URL in {path.name}"


def test_asset_links_carry_the_static_prefix():
    refs = re.findall(r'(?:href|src)="([^"#:]+)"', _read(STATIC / "index.html"))
    assert refs
    for ref in refs:
        assert ref.startswith("static/"), ref


# -- the kit: nothing that fails silently ----------------------------------------------

def test_every_darkglass_token_used_is_defined():
    defined = set(re.findall(r"(--darkglass-[a-z0-9-]+)\s*:", _read(STATIC / "vendor/darkglass.css")))
    for path in OWN_STATIC:
        if path.suffix == ".css":
            for token in re.findall(r"var\((--darkglass-[a-z0-9-]+)", _read(path)):
                assert token in defined, f"{token} is not a kit token ({path.name})"


def test_every_badge_tone_used_exists_in_the_kit():
    tones = set(re.findall(r'\[data-tone="([a-z]+)"\]', _read(STATIC / "vendor/panel.css")))
    js = _read(STATIC / "app.js")
    block = re.search(r"const TONES = \{(.*?)\};", js, re.S)
    assert block, "the TONES map moved; update this test"
    used = set(re.findall(r':\s*"([a-z]+)"', block.group(1)))
    used |= set(re.findall(r'setBadge\([^;]*?,\s*"([a-z]+)"\)', js))
    used |= set(re.findall(r'data-tone="([a-z]+)"', _read(STATIC / "index.html")))
    assert used, "found no tones to check"
    assert used <= tones, f"not kit tones: {used - tones}"


def test_every_kit_class_used_exists():
    css = _read(STATIC / "vendor/panel.css") + _read(STATIC / "vendor/module.css") + _read(STATIC / "app.css")
    html = _read(STATIC / "index.html") + _read(STATIC / "app.js")
    used = set()
    for attr in re.findall(r'class(?:Name)?\s*[:=]\s*"([^"]+)"', html):
        used.update(attr.split())
    for name in used:
        assert re.search(r"\." + re.escape(name) + r"(?![a-zA-Z0-9_-])", css), f".{name} is not defined"


def test_no_literal_colour_or_px_in_own_css():
    for path in OWN_STATIC:
        if path.suffix != ".css":
            continue
        css = re.sub(r"/\*.*?\*/", "", _read(path), flags=re.S)
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", css), path.name
        for line in css.splitlines():
            if "px" in line:
                assert "border" in line, f"px outside a border in {path.name}: {line.strip()}"


def test_postmessage_rules_and_no_browser_dialogs():
    js = _read(STATIC / "app.js")
    code = "\n".join(line.split("//", 1)[0] for line in js.splitlines())  # not the comments
    assert '"*"' not in code and "ev.source" not in code
    assert "window.confirm" not in code and "alert(" not in code and "prompt(" not in code


def test_first_control_is_marked_and_the_title_is_marked():
    html = _read(STATIC / "index.html")
    assert "data-hdeck-focus-first" in html
    assert "data-view-title" in html


# -- vendored files: byte-identical, never edited ----------------------------------------

def _vendored() -> dict:
    return json.loads(_read(MODULE_DIR / "VENDORED.json"))["files"]


def test_vendored_files_match_their_recorded_hashes():
    for local, meta in _vendored().items():
        digest = hashlib.sha256((MODULE_DIR / local).read_bytes()).hexdigest()
        assert digest == meta["sha256"], f"{local} was edited; re-vendor it from upstream"


def test_vendored_files_match_a_live_checkout_when_one_is_given():
    checkout = os.environ.get("HDECK_CHECKOUT")
    if not checkout:
        pytest.skip("set HDECK_CHECKOUT to a HollowDeck checkout to compare against it")
    for local, meta in _vendored().items():
        upstream = Path(checkout) / meta["upstream"]
        assert (MODULE_DIR / local).read_bytes() == upstream.read_bytes(), (
            f"{local} has drifted from upstream {meta['upstream']}")


def test_vendored_files_are_protected_from_line_ending_rewrites():
    attributes = _read(ROOT / ".gitattributes")
    for local in _vendored():
        rule = "hollowdeck/lloom/static/vendor/**" if local.startswith("static/vendor/") \
            else f"hollowdeck/lloom/{local}"
        assert re.search(re.escape(rule) + r"\s+-text", attributes), local


# -- the entry point ---------------------------------------------------------------------

def test_entry_point_binds_loopback_literally_and_takes_the_secret_first():
    source = _read(MODULE_DIR / "__main__.py")
    assert 'host="127.0.0.1"' in source
    main_body = source[source.index("def main("):]
    assert main_body.index("secret_from_env()") < main_body.index("create_app(")


def test_no_absolute_machine_path_in_the_module():
    for path in [*OWN_STATIC, MODULE_DIR / "module.json", *MODULE_DIR.glob("*.py")]:
        text = _read(path)
        assert not re.search(r"\b[A-Za-z]:\\\\", text), f"absolute Windows path in {path.name}"
        assert "localRepositories" not in text, path.name


def test_selfcheck_passes():
    done = subprocess.run([sys.executable, str(MODULE_DIR / "selfcheck.py")], capture_output=True,
                          text=True, timeout=120, **PROC.no_window())
    assert done.returncode == 0, done.stderr


# ======================================================================================
# the workspace
# ======================================================================================

def test_walking_up_from_the_module_finds_this_checkout():
    root, source, problem = WS.resolve_workspace({}, MODULE_DIR, env={})
    assert root == ROOT.resolve() and problem == "" and source == "this module's location"


def test_walk_up_looks_for_files_not_a_folder_name(tmp_path):
    module_dir = tmp_path / "Lloom" / "hollowdeck" / "lloom"
    module_dir.mkdir(parents=True)
    root, _, problem = WS.resolve_workspace({}, module_dir, env={})
    assert root is None and "workspace" in problem


def test_the_setting_wins_and_is_checked(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    root, source, problem = WS.resolve_workspace({"workspace": f'"{ws}"'}, MODULE_DIR, env={})
    assert root == ws.resolve() and source == "the workspace setting" and problem == ""
    _, _, problem = WS.resolve_workspace({"workspace": "relative/dir"}, MODULE_DIR, env={})
    assert "relative path" in problem
    (tmp_path / "plain").mkdir()
    _, _, problem = WS.resolve_workspace({"workspace": str(tmp_path / "plain")}, MODULE_DIR, env={})
    assert "not a Lloom project" in problem
    root, source, _ = WS.resolve_workspace({}, MODULE_DIR, env={"LLOOM_WORKSPACE": str(ws)})
    assert root == ws.resolve() and source == "LLOOM_WORKSPACE"


def test_python_resolution(tmp_path):
    py, source, problem = WS.resolve_python({"python": sys.executable}, None, env={})
    assert py == sys.executable and problem == ""
    _, _, problem = WS.resolve_python({"python": str(tmp_path / "nope.exe")}, None, env={})
    assert "does not exist" in problem
    _, _, problem = WS.resolve_python({"python": "sub/python"}, None, env={})
    assert "relative path" in problem
    venv = tmp_path / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    venv.parent.mkdir(parents=True)
    venv.write_text("")
    py, source, _ = WS.resolve_python({}, tmp_path, env={})
    assert Path(py) == venv and "virtual environment" in source


def test_unquote_follows_the_path_rule():
    assert WS.unquote('  "C:\\a b.txt" ') == "C:\\a b.txt"
    assert WS.unquote("'x'") == "x"
    assert WS.unquote('"one-sided') == '"one-sided'


def test_names_and_workspace_files_cannot_escape(tmp_path):
    for bad in ("../x", "a/b", ".hidden", "", "a..b"):
        with pytest.raises(ValueError):
            WS.safe_name(bad, "run name")
    with pytest.raises(ValueError, match="outside the workspace"):
        WS.workspace_file(tmp_path, "../elsewhere.pt", "checkpoint")
    assert WS.workspace_file(tmp_path, "runs/a/best.pt", "checkpoint") == tmp_path / "runs/a/best.pt"


def test_metrics_summary_reads_interleaved_rows(tmp_path):
    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text("step,time,loss/total,lr,val/loss/total,val/perplexity/total\n"
                        "5,1,3.0,0.001,,\n5,1,,,2.5,12.2\n10,2,2.0,0.001,,\n10,2,,,2.6,13.5\n",
                        encoding="utf-8")
    m = WS.metrics_summary(csv_path)
    assert m["step"] == 10 and m["train_loss"] == 2.0 and m["val_loss"] == 2.6
    assert m["best_val_loss"] == 2.5 and m["val_perplexity"] == 13.5
    sft = tmp_path / "sft.csv"
    sft.write_text("step,time,loss/train,grad_norm,lr,loss/val\n1,1,4.0,1,0.1,\n1,1,,,,3.5\n",
                   encoding="utf-8")
    assert WS.metrics_summary(sft)["val_loss"] == 3.5
    assert WS.metrics_summary(tmp_path / "missing.csv") is None


def test_real_workspace_inventory_reads():
    inv = WS.inventory(ROOT)
    names = {r["name"] for r in inv["recipes"]}
    assert {"pretrain", "sft", "release"} <= names
    assert all(not r["problem"] for r in inv["recipes"])
    presets = {p["name"]: p for p in inv["presets"]}
    assert presets["nano"]["approx_non_embedding_params"] < presets["small"]["approx_non_embedding_params"]
    stages = {s["name"]: s for s in inv["stages"]}
    for stage in WS.REFERENCE_STAGES:
        assert stage in stages, stage
    assert stages["pretrain"]["takes_overrides"] and not stages["prepare_data"]["takes_overrides"]


# ======================================================================================
# jobs
# ======================================================================================

def _manager(tmp_path, **kw):
    kw.setdefault("poll_interval", 0.05)
    return JOBS.JobManager(tmp_path / "data", proc=PROC, **kw).start()


def _py(code: str) -> list[str]:
    return [sys.executable, "-c", textwrap.dedent(code)]


def test_a_job_runs_logs_and_parses_progress(tmp_path):
    finished = []
    jobs = _manager(tmp_path, on_finish=[finished.append])
    try:
        rec = jobs.submit(kind="stage", title="t", cwd=tmp_path, argv=_py("""
            print("[pretrain] $ python scripts/pretrain.py", flush=True)
            print("training: 10 steps x 64 tok", flush=True)
            print("step      5 loss 2.5000 lr 1e-3", flush=True)
            print("  val 2.1000 ppl 8.17 (best 2.1)", flush=True)
            print("step     10 loss 2.0000 lr 1e-3", flush=True)
        """))
        done = jobs.wait(rec["id"], 30)
        assert done["status"] == "succeeded" and done["exit_code"] == 0
        assert done["stages"][0]["name"] == "pretrain" and done["stages"][0]["status"] == "done"
        p = done["progress"]
        assert p["total_steps"] == 10 and p["step"] == 10 and p["fraction"] == 1.0
        assert p["loss"] == 2.0 and p["val_loss"] == 2.1 and p["val_perplexity"] == 8.17
        assert "step     10 loss" in jobs.tail(rec["id"], 5)
        first = jobs.read_log(rec["id"], 0, 10)
        rest = jobs.read_log(rec["id"], first["offset"])
        assert first["text"] + rest["text"] == jobs.read_log(rec["id"])["text"]
        _until(lambda: finished)
        assert finished[0]["id"] == rec["id"] and finished[0]["status"] == "succeeded"
        on_disk = json.loads((tmp_path / "data/jobs" / rec["id"] / "job.json").read_text())
        assert on_disk["status"] == "succeeded"
    finally:
        jobs.shutdown()


def test_a_failing_job_says_why(tmp_path):
    jobs = _manager(tmp_path)
    try:
        rec = jobs.submit(kind="stage", title="t", cwd=tmp_path, argv=_py("import sys; sys.exit(3)"))
        done = jobs.wait(rec["id"], 30)
        assert done["status"] == "failed" and done["exit_code"] == 3
        assert done["error"] == "exited with code 3"
    finally:
        jobs.shutdown()


def test_a_job_that_cannot_start_fails_and_fires_its_follow_ups(tmp_path):
    finished = []
    jobs = _manager(tmp_path, on_finish=[finished.append])
    try:
        rec = jobs.submit(kind="stage", title="t", cwd=tmp_path,
                          argv=["definitely-not-a-real-program-lloom"])
        assert rec["status"] == "failed" and "could not start" in rec["error"]
        assert finished and finished[0]["id"] == rec["id"]
    finally:
        jobs.shutdown()


def test_jobs_queue_behind_the_limit_and_immediate_ones_do_not(tmp_path):
    jobs = _manager(tmp_path, max_concurrent=1)
    try:
        slow = _py("import time; time.sleep(1.0)")
        a = jobs.submit(kind="stage", title="a", cwd=tmp_path, argv=slow)
        b = jobs.submit(kind="stage", title="b", cwd=tmp_path, argv=slow)
        assert a["status"] == "running" and b["status"] == "queued"
        assert "1 job running, 1 queued" == jobs.hold_reason()
        quick = jobs.submit(kind="generate", title="q", cwd=tmp_path, immediate=True,
                            argv=_py("print('hi')"))
        assert quick["status"] == "running"
        assert jobs.wait(quick["id"], 30)["status"] == "succeeded"
        assert jobs.get(a["id"])["status"] == "running"  # the quick one did not wait for it
        done_b = jobs.wait(b["id"], 30)
        done_a = jobs.get(a["id"])
        assert done_b["status"] == "succeeded"
        assert done_b["started_at"] >= done_a["finished_at"] - 0.2
        assert jobs.hold_reason() == ""
    finally:
        jobs.shutdown()


def test_cancel_stops_the_whole_process_tree(tmp_path):
    beat = tmp_path / "beat.txt"
    jobs = _manager(tmp_path)
    try:
        rec = jobs.submit(kind="stage", title="spin", cwd=tmp_path, argv=_py(f"""
            import subprocess, sys, time
            code = "import sys, time\\nfrom pathlib import Path\\np = Path(sys.argv[1])\\nwhile True:\\n    p.write_text(str(time.time()))\\n    time.sleep(0.1)\\n"
            subprocess.Popen([sys.executable, "-c", code, {str(beat)!r}])
            time.sleep(120)
        """))
        _until(lambda: beat.exists() and beat.read_text())
        rec, stopped = jobs.cancel(rec["id"])
        assert stopped
        done = jobs.wait(rec["id"], 30)
        assert done["status"] == "cancelled"
        time.sleep(0.5)
        before = beat.read_text()
        time.sleep(0.8)
        assert beat.read_text() == before, "the grandchild outlived the cancel"
        _, again = jobs.cancel(rec["id"])
        assert again is False
    finally:
        jobs.shutdown()


def test_cancel_a_queued_job_never_starts_it(tmp_path):
    jobs = _manager(tmp_path, max_concurrent=1)
    try:
        a = jobs.submit(kind="stage", title="a", cwd=tmp_path, argv=_py("import time; time.sleep(1)"))
        b = jobs.submit(kind="stage", title="b", cwd=tmp_path, argv=_py("print('ran')"))
        rec, stopped = jobs.cancel(b["id"])
        assert stopped and rec["status"] == "cancelled" and rec["started_at"] is None
        jobs.wait(a["id"], 30)
        assert jobs.get(b["id"])["status"] == "cancelled"
    finally:
        jobs.shutdown()


def test_wait_returns_early_as_the_job_stands(tmp_path):
    jobs = _manager(tmp_path)
    try:
        rec = jobs.submit(kind="stage", title="t", cwd=tmp_path, argv=_py("import time; time.sleep(3)"))
        started = time.monotonic()
        mid = jobs.wait(rec["id"], 0.3)
        assert mid["status"] == "running" and time.monotonic() - started < 2
    finally:
        jobs.shutdown()


def test_a_job_left_running_by_a_previous_process_is_interrupted(tmp_path):
    job_dir = tmp_path / "data/jobs/20260101-000000-abcdef"
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(json.dumps({
        "id": "20260101-000000-abcdef", "status": "running", "created_at": 1, "title": "old",
        "kind": "pipeline", "stages": [{"name": "pretrain", "status": "running"}]}))
    jobs = JOBS.JobManager(tmp_path / "data", proc=PROC)
    rec = jobs.get("20260101-000000-abcdef")
    assert rec["status"] == "interrupted" and "stopped" in rec["error"]
    assert rec["stages"][0]["status"] == "interrupted"
    assert jobs.recovered == ["20260101-000000-abcdef"]


def test_a_job_never_sees_the_hosts_secret(tmp_path):
    env = dict(os.environ, HDECK_MODULE_SECRET="s3cret-value")
    jobs = JOBS.JobManager(tmp_path / "data", proc=PROC, poll_interval=0.05, base_env=env).start()
    try:
        rec = jobs.submit(kind="stage", title="t", cwd=tmp_path, argv=_py(
            "import os; print('secret=' + repr(os.environ.get('HDECK_MODULE_SECRET')))"))
        jobs.wait(rec["id"], 30)
        log = jobs.read_log(rec["id"])["text"]
        assert "secret=None" in log and "s3cret-value" not in log
    finally:
        jobs.shutdown()


# ======================================================================================
# the fake workspace, and the module over it
# ======================================================================================

FAKE_PREPARE = '''"""Fake prepare_data stage."""
import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--config", default="config/data_config.yaml")
ap.parse_args()
print("prepare_data ran", flush=True)
'''

# `add_config_args(` in the source is how the module tells a stage takes --preset/--set.
FAKE_TRAINER = '''"""Fake {name} stage."""
# add_config_args(ap, "config/training_config.yaml") -- the real stage calls this.
import argparse, json, os, sys
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument("--config", default="config/training_config.yaml")
ap.add_argument("--preset", default=None)
ap.add_argument("--set", dest="sets", action="append", default=[])
ap.add_argument("--checkpoint", default=None)
ap.add_argument("--wandb", action="store_true")
args = ap.parse_args()
sets = dict(s.split("=", 1) for s in args.sets)
run = sets.get("run_name", "default")
print("ARGS " + json.dumps({{"preset": args.preset, "sets": args.sets, "checkpoint": args.checkpoint}}), flush=True)
if "{name}" == "pretrain":
    print("training: 10 steps x 64 tok = 0M tokens | opt adamw | sched cosine", flush=True)
    print("step      5 loss 3.0000 lr 1.00e-03", flush=True)
    print("  val 2.4000 ppl 11.02 (best 2.4000) [0.1s]", flush=True)
    print("step     10 loss 2.0000 lr 1.00e-03", flush=True)
    print("  val 2.1000 ppl 8.17 (best 2.1000) [0.1s]", flush=True)
    out = Path("runs") / run / "checkpoints" / "pretrain"
    out.mkdir(parents=True, exist_ok=True)
    (out / "best.pt").write_bytes(b"x" * 2048)
    (out / "last.pt").write_bytes(b"x")
    logs = Path("runs") / run / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "metrics.csv").write_text(
        "step,time,loss/total,lr,val/loss/total,val/perplexity/total\\n"
        "5,1,3.0,0.001,,\\n5,1,,,2.4,11.02\\n10,2,2.0,0.001,,\\n10,2,,,2.1,8.17\\n")
if "{name}" == "evaluate":
    out = Path("runs") / run / "eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval_results.json").write_text(json.dumps({{"checkpoint": args.checkpoint, "perplexity/total": 8.2}}))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
'''

FAKE_GENERATE = '''"""Fake generate: completions are the prompts upper-cased, JSON in / JSON out."""
import argparse, json
from pathlib import Path
ap = argparse.ArgumentParser()
for flag in ("--checkpoint", "--prompts_file", "--out", "--device", "--max_new_tokens",
             "--temperature", "--top_p", "--top_k", "--min_p", "--repetition_penalty", "--seed"):
    ap.add_argument(flag, default=None)
ap.add_argument("--chat", action="store_true")
args = ap.parse_args()
prompts = json.loads(Path(args.prompts_file).read_text(encoding="utf-8"))
results = [{"prompt": p, "input": p, "completion": ("chat:" if args.chat else "") + p.upper(),
            "n_tokens": len(p)} for p in prompts]
payload = {"checkpoint": args.checkpoint, "device": args.device, "seconds": 0, "results": results}
Path(args.out).write_text(json.dumps(payload), encoding="utf-8")
print(json.dumps(payload))
'''

FAKE_SPIN = '''"""Fake long stage: runs until it is stopped."""
import time
print("spinning", flush=True)
time.sleep(120)
'''


def make_workspace(root: Path, ollama_url: str = "http://127.0.0.1:9") -> Path:
    (root / "lloom").mkdir(parents=True)
    for name in ("__init__.py", "config.py", "pipeline.py", "judge.py"):
        shutil.copy(ROOT / "lloom" / name, root / "lloom" / name)
    scripts = root / "scripts"
    scripts.mkdir()
    for name in ("run_pipeline.py", "judge.py"):
        shutil.copy(ROOT / "scripts" / name, scripts / name)
    (scripts / "prepare_data.py").write_text(FAKE_PREPARE, encoding="utf-8")
    for name in ("pretrain", "evaluate"):
        (scripts / f"{name}.py").write_text(FAKE_TRAINER.format(name=name), encoding="utf-8")
    (scripts / "generate.py").write_text(FAKE_GENERATE, encoding="utf-8")
    (scripts / "spin.py").write_text(FAKE_SPIN, encoding="utf-8")
    config = root / "config"
    (config / "pipelines").mkdir(parents=True)
    (config / "presets").mkdir()
    (config / "pipelines" / "pretrain.yaml").write_text(textwrap.dedent("""\
        # Fake pretraining recipe.
        name: pretrain
        stages:
          - name: prepare_data
            cmd: [scripts/prepare_data.py]
          - name: pretrain
            cmd: [scripts/pretrain.py]
            pass_overrides: true
        """), encoding="utf-8")
    for name, d in (("nano", 64), ("small", 128)):
        (config / "presets" / f"{name}.yaml").write_text(
            f"# {name} preset\nmodel:\n  d_model: {d}\n  n_layers: 2\n  n_heads: 2\n",
            encoding="utf-8")
    (config / "training_config.yaml").write_text(
        "model:\n  vocab_size: 512\n  d_model: 64\n  n_layers: 2\n  n_heads: 2\n", encoding="utf-8")
    (config / "tokenizer_config.yaml").write_text("vocab_size: 512\n", encoding="utf-8")
    (config / "data_config.yaml").write_text("sft_dir: data/sft\ntest_dir: data/test\n",
                                            encoding="utf-8")
    (config / "judge_config.yaml").write_text(textwrap.dedent(f"""\
        run_name: null
        input: runs/${{run_name}}/eval/generations.jsonl
        out_dir: runs/${{run_name}}/eval
        provider: ollama
        model: null
        effort: medium
        fallbacks: true
        ollama_url: {ollama_url}
        max_items: 100
        max_score: 10
        pass_threshold: 7
        rubric: |
          Workspace rubric.
        """), encoding="utf-8")
    return root


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.calls.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        status, out = self.server.answer(self.path, body)
        data = json.dumps(out).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@contextmanager
def fake_server(answer):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.calls = []
    server.answer = answer
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _app(tmp_path, workspace, settings=None, core_url=None):
    data = tmp_path / "moddata"
    merged = {"python": sys.executable}
    if workspace is not None:
        merged["workspace"] = str(workspace)
    merged.update(settings or {})
    ctx = SimpleNamespace(module_id="lloom", module_dir=MODULE_DIR if workspace is not None
                          else tmp_path / "nowhere", data_dir=data, settings=merged,
                          core_url=core_url)
    app = PKG.create_app(ctx, start=False)
    app.state.service.jobs.poll_interval = 0.05
    app.state.service.start(background_sync=False)
    return app


@pytest.fixture
def mod(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    app = _app(tmp_path, ws)
    yield SimpleNamespace(app=app, svc=app.state.service, client=TestClient(app), ws=ws,
                          data=tmp_path / "moddata", tmp=tmp_path)
    app.state.service.shutdown()


def tool(client, name, **inputs):
    res = client.post(f"/tools/{name}", json={"inputs": inputs,
                                              "base_dir": "", "base_dir_source": "executable"})
    body = res.json()
    return res.status_code, (body.get("outputs") if res.status_code == 200 else body.get("detail"))


def _args_line(log: str) -> dict:
    line = next(line for line in log.splitlines() if line.startswith("ARGS "))
    return json.loads(line[5:])


# -- status and unconfigured -------------------------------------------------------------

def test_status_tool_lists_the_workspace(mod):
    code, out = tool(mod.client, "status")
    assert code == 200 and out["configured"] is True and out["problem"] == ""
    assert out["recipes"] == ["pretrain"] and out["presets"] == ["nano", "small"]
    assert "pretrain" in out["stages"] and out["runs"] == [] and out["active_jobs"] == 0


def test_an_unconfigured_module_still_loads_and_says_why(tmp_path):
    app = _app(tmp_path, workspace=tmp_path / "missing")
    client = TestClient(app)
    try:
        assert client.get("/health").json()["ok"] is True
        code, out = tool(client, "status")
        assert code == 200 and out["configured"] is False and "not a folder" in out["problem"]
        code, detail = tool(client, "run_pipeline", recipe="pretrain")
        assert code == 409 and "not a folder" in detail
        assert client.get("/api/status").json()["workspace"]["problem"]
    finally:
        app.state.service.shutdown()


def test_an_unknown_tool_is_404(mod):
    assert tool(mod.client, "nope")[0] == 404


# -- pipelines ---------------------------------------------------------------------------

def test_run_pipeline_runs_the_real_runner_and_forwards_overrides(mod):
    code, out = tool(mod.client, "run_pipeline", recipe="pretrain", run_name="t1", preset="nano",
                     sets=["training.max_steps=10"], wait_seconds=60)
    assert code == 200, out
    assert out["status"] == "succeeded" and out["done"] and out["ok"] and out["run_name"] == "t1"
    job = out["job"]
    assert [(s["name"], s["status"]) for s in job["stages"]] == \
        [("prepare_data", "done"), ("pretrain", "done")]
    assert job["progress"]["fraction"] == 1.0
    log = mod.svc.jobs.read_log(out["job_id"])["text"]
    args = _args_line(log)
    assert args["preset"] == "nano"
    assert args["sets"] == ["run_name=t1", "training.max_steps=10"]
    assert (mod.ws / "runs/t1/checkpoints/pretrain/best.pt").is_file()


def test_run_pipeline_refuses_bad_input_readably(mod):
    code, detail = tool(mod.client, "run_pipeline", recipe="nope")
    assert code == 404 and "have: pretrain" in detail
    code, detail = tool(mod.client, "run_pipeline", preset="huge")
    assert code == 404 and "have: nano, small" in detail
    code, detail = tool(mod.client, "run_pipeline", sets=["no_equals_sign"])
    assert code == 400 and "key.path=value" in detail
    code, detail = tool(mod.client, "run_pipeline", only="evaluate")
    assert code == 400 and "prepare_data, pretrain" in detail
    code, detail = tool(mod.client, "run_pipeline", run_name="../escape")
    assert code == 400
    code, detail = tool(mod.client, "run_pipeline", recipe="../../etc/passwd.yaml")
    assert code == 400 and "outside the workspace" in detail


def test_a_newline_string_of_overrides_is_a_list(mod):
    code, out = tool(mod.client, "run_pipeline", run_name="t2", sets="a.b=1\nc=2", wait_seconds=60)
    assert code == 200 and out["ok"], out
    assert _args_line(mod.svc.jobs.read_log(out["job_id"])["text"])["sets"] == ["run_name=t2", "a.b=1", "c=2"]


def test_a_failed_pipeline_reports_the_stage(mod, monkeypatch):
    monkeypatch.setenv("FAKE_EXIT", "5")
    code, out = tool(mod.client, "run_pipeline", run_name="bad", wait_seconds=60)
    assert code == 200 and out["status"] == "failed" and not out["ok"]
    stages = {s["name"]: s["status"] for s in out["job"]["stages"]}
    assert stages == {"prepare_data": "done", "pretrain": "failed"}


# -- stages ------------------------------------------------------------------------------

def test_run_stage_with_a_preset_and_a_checkpoint(mod):
    code, out = tool(mod.client, "run_stage", stage="pretrain", run_name="s1", preset="small",
                     sets=["device=cpu"], wait_seconds=60)
    assert code == 200 and out["ok"], out
    assert _args_line(mod.svc.jobs.read_log(out["job_id"])["text"]) == \
        {"preset": "small", "sets": ["run_name=s1", "device=cpu"], "checkpoint": None}
    code, out = tool(mod.client, "run_stage", stage="evaluate", run_name="s1",
                     checkpoint="runs/s1/checkpoints/pretrain/best.pt", wait_seconds=60)
    assert code == 200 and out["ok"], out
    assert _args_line(mod.svc.jobs.read_log(out["job_id"])["text"])["checkpoint"] == \
        "runs/s1/checkpoints/pretrain/best.pt"
    assert (mod.ws / "runs/s1/eval/eval_results.json").is_file()


def test_run_stage_refusals(mod):
    code, detail = tool(mod.client, "run_stage", stage="prepare_data", preset="nano")
    assert code == 400 and "takes no preset" in detail
    code, detail = tool(mod.client, "run_stage", stage="nope")
    assert code == 404 and "scripts/nope.py" in detail
    code, detail = tool(mod.client, "run_stage", stage="evaluate", checkpoint="../x.pt")
    assert code == 400 and "outside the workspace" in detail
    code, detail = tool(mod.client, "run_stage", stage="evaluate", checkpoint="runs/none/best.pt")
    assert code == 404
    code, detail = tool(mod.client, "run_stage", stage="prepare_data", checkpoint="x.pt")
    assert code == 400 and "takes no checkpoint" in detail


# -- watching and stopping ---------------------------------------------------------------

def test_job_status_waits_and_carries_the_runs_numbers(mod):
    code, started = tool(mod.client, "run_stage", stage="pretrain", run_name="w1")
    assert code == 200 and started["status"] == "running"
    code, out = tool(mod.client, "job_status", job_id=started["job_id"], wait_seconds=60)
    assert code == 200 and out["ok"] and out["exit_code"] == 0 and out["stage"] == "pretrain"
    assert out["progress"] == 1.0 and out["elapsed_seconds"] >= 0
    assert out["metrics"]["metrics"]["pretrain"]["best_val_loss"] == 2.1
    code, latest = tool(mod.client, "job_status")
    assert latest["job_id"] == started["job_id"]
    assert tool(mod.client, "job_status", job_id="nope")[0] == 404


def test_cancel_job_and_the_lifecycle_hold(mod):
    code, out = tool(mod.client, "run_stage", stage="spin")
    assert code == 200 and out["status"] == "running"
    hold = mod.client.get("/lifecycle").json()
    assert hold["hold"] is True and "1 job running" in hold["reason"] and out["job_id"] in hold["jobs"]
    code, cancel = tool(mod.client, "cancel_job", job_id=out["job_id"])
    assert code == 200 and cancel["cancelled"] is True
    code, done = tool(mod.client, "job_status", job_id=out["job_id"], wait_seconds=30)
    assert done["status"] == "cancelled" and done["done"] and not done["ok"]
    assert mod.client.get("/lifecycle").json()["hold"] is False
    assert tool(mod.client, "cancel_job", job_id=out["job_id"])[1]["cancelled"] is False
    assert tool(mod.client, "cancel_job")[0] == 400


# -- runs --------------------------------------------------------------------------------

def test_list_runs_and_run_metrics(mod):
    tool(mod.client, "run_stage", stage="pretrain", run_name="m1", wait_seconds=60)
    code, runs = tool(mod.client, "list_runs")
    assert code == 200 and runs["runs"] == ["m1"] and runs["latest_run"] == "m1"
    assert runs["details"][0]["model"] == "runs/m1/checkpoints/pretrain/best.pt"
    code, m = tool(mod.client, "run_metrics", run_name="m1")
    assert code == 200
    assert (m["step"], m["train_loss"], m["val_loss"], m["best_val_loss"], m["val_perplexity"]) == \
        (10, 2.0, 2.1, 2.1, 8.17)
    assert "runs/m1/checkpoints/pretrain/best.pt" in m["checkpoints"]
    assert m["summary"].startswith("run m1") and "val loss 2.1000" in m["summary"]
    code, sft = tool(mod.client, "run_metrics", run_name="m1", phase="sft")
    assert sft["step"] == -1 and sft["train_loss"] is None
    code, detail = tool(mod.client, "run_metrics", run_name="nope")
    assert code == 404 and "have: m1" in detail


# -- generate and judge ------------------------------------------------------------------

def test_generate_uses_the_runs_model(mod):
    code, detail = tool(mod.client, "generate", prompt="hi", run_name="nothing")
    assert code == 409 and "no finished checkpoint" in detail
    tool(mod.client, "run_stage", stage="pretrain", run_name="g1", wait_seconds=60)
    code, out = tool(mod.client, "generate", prompt="hello", prompts=["two", "three"],
                     run_name="g1", chat=True, seed=3)
    assert code == 200, out
    assert out["texts"] == ["chat:HELLO", "chat:TWO", "chat:THREE"] and out["text"] == "chat:HELLO"
    assert out["checkpoint"] == "runs/g1/checkpoints/pretrain/best.pt"
    assert out["results"][1] == {"prompt": "two", "completion": "chat:TWO", "n_tokens": 3}
    assert not any((mod.data / "work").iterdir()), "generate left its work files behind"
    assert tool(mod.client, "generate", run_name="g1")[0] == 400
    assert tool(mod.client, "generate", prompt="x", run_name="g1", device="tpu")[0] == 400


def _ollama(path, body):
    user = body["messages"][1]["content"]
    response = re.search(r"<response>\n(.*?)\n</response>", user, re.S).group(1)
    score = 9 if "good" in response else 2
    return 200, {"message": {"content": json.dumps({"score": score, "justification": f"saw {response}"})}}


def test_judge_runs_the_real_judge_against_a_local_model(tmp_path):
    with fake_server(_ollama) as (server, url):
        ws = make_workspace(tmp_path / "ws", ollama_url=url)
        app = _app(tmp_path, ws)
        client = TestClient(app)
        try:
            items = [{"prompt": "p1", "completion": "a good answer"},
                     {"prompt": "p2", "completion": "bad"}]
            code, out = tool(client, "judge", items=items, provider="ollama",
                             rubric="Custom rubric here.", pass_threshold=7)
            assert code == 200, out
            assert out["scores"] == [9.0, 2.0] and out["score"] == 5.5 and out["pass_rate"] == 0.5
            assert out["verdicts"][0]["justification"] == "saw a good answer"
            assert "ollama" in out["summary"] and "5.50/10" in out["summary"]
            sent = server.calls[0][2]
            assert "Custom rubric here." in sent["messages"][1]["content"]
            assert sent["format"]["required"] == ["score", "justification"]
            code, single = tool(client, "judge", prompt="q", response="good", provider="ollama")
            assert code == 200 and single["scores"] == [9.0]
            assert tool(client, "judge", provider="ollama")[0] == 400
            assert tool(client, "judge", response="x", provider="openai")[0] == 400
        finally:
            app.state.service.shutdown()


def test_judge_fails_the_node_when_nothing_could_be_judged(tmp_path):
    with fake_server(lambda p, b: (500, {"error": "boom"})) as (_, url):
        ws = make_workspace(tmp_path / "ws", ollama_url=url)
        app = _app(tmp_path, ws)
        try:
            code, detail = tool(TestClient(app), "judge", response="x", provider="ollama")
            assert code == 500 and "judge failed" in detail
        finally:
            app.state.service.shutdown()


# -- SFT data ----------------------------------------------------------------------------

def test_add_sft_data_appends_and_guards_replace(mod, tmp_path):
    pairs = [{"prompt": "a", "response": "b"}, {"instruction": "c", "output": "d"}, {"prompt": "only"}]
    code, out = tool(mod.client, "add_sft_data", pairs=pairs, dataset="gen")
    assert code == 200 and out == {"path": "data/sft/gen.jsonl", "added": 2, "skipped": 1, "total": 2}
    code, out = tool(mod.client, "add_sft_data", prompt="e", response="f", dataset="gen")
    assert out["total"] == 3
    rows = [json.loads(line) for line in (mod.ws / "data/sft/gen.jsonl").read_text().splitlines()]
    assert rows[1] == {"prompt": "c", "response": "d"}
    code, detail = tool(mod.client, "add_sft_data", prompt="x", response="y", dataset="gen", mode="replace")
    assert code == 403 and "allow_replace_data" in detail
    code, out = tool(mod.client, "add_sft_data", pairs='{"prompt": "t", "response": "u"}',
                     dataset="held", split="test")
    assert code == 200 and out["path"] == "data/test/held.jsonl"
    assert tool(mod.client, "add_sft_data", prompt="x", response="y", dataset="themed")[0] == 400
    assert tool(mod.client, "add_sft_data", prompt="x", response="y", dataset="../up")[0] == 400
    assert tool(mod.client, "add_sft_data", pairs=[{"prompt": "x"}])[0] == 400


def test_replace_works_when_the_setting_allows_it(tmp_path):
    ws = make_workspace(tmp_path / "ws")
    app = _app(tmp_path, ws, settings={"allow_replace_data": True})
    client = TestClient(app)
    try:
        tool(client, "add_sft_data", pairs=[{"prompt": "a", "response": "b"}] * 3, dataset="d")
        code, out = tool(client, "add_sft_data", prompt="x", response="y", dataset="d", mode="replace")
        assert code == 200 and out["total"] == 1
    finally:
        app.state.service.shutdown()


# -- the Library and the recipe nodes ----------------------------------------------------

def _assets(client) -> dict:
    return {a["id"]: a for a in client.get("/api/assets").json()["assets"]}


def test_sync_publishes_the_workspace_as_assets(mod):
    tool(mod.client, "run_stage", stage="pretrain", run_name="lib", wait_seconds=60)
    # A finished job also syncs in the background, so this sync may create nothing new.
    code, out = tool(mod.client, "sync_library")
    assert code == 200 and out["removed"] == 0 and "run-lib" in out["assets"]
    assets = _assets(mod.client)
    expect = {"recipe-pretrain": "lloom.recipe", "preset-nano": "lloom.preset",
              "script-pretrain": "script", "run-lib": "lloom.run",
              "ckpt-lib-pretrain-best-pt": "lloom.checkpoint"}
    for aid, kind in expect.items():
        assert assets[aid]["kind"] == kind, aid
        assert assets[aid]["origin"] == "ingested" and assets[aid]["owner"] == "lloom"
        assert assets[aid]["captured_against"] == MANIFEST["version"]
        assert assets[aid]["properties"]["synced"] is True
    assert "ckpt-lib-pretrain-last-pt" not in assets  # resume state, not a model
    full = mod.client.get("/api/assets/preset-nano").json()["asset"]
    assert full["payload"]["outputs"] == {"preset": "nano"}
    assert full["interface"]["outputs"][0]["name"] == "preset"
    ckpt = mod.client.get("/api/assets/ckpt-lib-pretrain-best-pt").json()["asset"]
    assert ckpt["payload"]["outputs"] == {"checkpoint": "runs/lib/checkpoints/pretrain/best.pt"}
    code, again = tool(mod.client, "sync_library")
    assert (again["created"], again["updated"], again["removed"]) == (0, 0, 0)


def test_sync_removes_stale_assets_and_never_touches_a_persons(mod):
    tool(mod.client, "sync_library")
    res = mod.client.post("/api/assets", json={"id": "my-notes", "name": "Mine", "payload": {}})
    assert res.status_code == 201 and res.json()["asset"]["origin"] == "ingested"
    mod.client.post("/api/assets", json={"id": "preset-tiny", "name": "Hand-made",
                                         "origin": "authored", "payload": {}})
    (mod.ws / "config/presets/small.yaml").unlink()
    (mod.ws / "config/presets/tiny.yaml").write_text("model:\n  d_model: 8\n", encoding="utf-8")
    result = mod.svc.sync()
    assets = _assets(mod.client)
    assert "preset-small" in result["removed"] and "preset-small" not in assets
    assert "my-notes" in assets and assets["preset-tiny"]["name"] == "Hand-made"
    assert result["skipped"] == ["preset-tiny"]


def test_sync_writes_one_node_per_recipe_with_the_workspaces_choices(mod):
    mod.svc.sync()
    declaration = json.loads((mod.data / "tools.json").read_text())
    assert LIBRARY.validate_tools(declaration["tools"], "tools.json") == []
    node = {t["id"]: t for t in declaration["tools"]}["pipeline_pretrain"]
    inputs = {i["name"]: i for i in node["inputs"]}
    assert inputs["preset"]["options"] == ["none", "nano", "small"]
    assert inputs["from_stage"]["options"] == ["first", "prepare_data", "pretrain"]
    assert node["effects"] == "executes"
    stamp = (mod.data / "tools.json").stat().st_mtime_ns
    time.sleep(0.05)
    assert mod.svc.sync()["tools_file_written"] is False
    assert (mod.data / "tools.json").stat().st_mtime_ns == stamp


def test_a_recipe_node_runs_its_recipe(mod):
    code, out = tool(mod.client, "pipeline_pretrain", run_name="node", preset="none",
                     from_stage="first", until="last", only="all", wait_seconds=60)
    assert code == 200 and out["ok"], out
    assert "--preset" not in out["job"]["argv"] and out["job"]["params"]["recipe"] == "pretrain"
    code, out = tool(mod.client, "pipeline_pretrain", run_name="node2", preset="small",
                     only="pretrain", wait_seconds=60)
    assert code == 200 and out["ok"] and [s["name"] for s in out["job"]["stages"]] == ["pretrain"]
    code, detail = tool(mod.client, "pipeline_gone")
    assert code == 404 and "Sync Lloom Library" in detail


def test_the_tools_file_exists_from_the_first_start(tmp_path):
    app = _app(tmp_path, workspace=None)
    try:
        declaration = json.loads((tmp_path / "moddata" / "tools.json").read_text())
        assert declaration["tools"] == [] and declaration["api_version"] == 1
    finally:
        app.state.service.shutdown()


def test_a_broken_recipe_is_reported_not_published(mod):
    (mod.ws / "config/pipelines/broken.yaml").write_text("stages: [unclosed", encoding="utf-8")
    result = mod.svc.sync()
    assert result["nodes"] == ["pipeline_pretrain"]
    assert any(d.startswith("broken:") for d in result["nodes_dropped"])


# -- the panel's API ---------------------------------------------------------------------

def test_panel_api_start_list_log_cancel(mod):
    res = mod.client.post("/api/jobs", json={"kind": "pipeline", "recipe": "pretrain",
                                             "run_name": "ui", "dry_run": True})
    assert res.status_code == 201
    job_id = res.json()["job"]["id"]
    assert mod.svc.jobs.wait(job_id, 60)["status"] == "succeeded"
    listing = mod.client.get("/api/jobs").json()
    assert listing["jobs"][0]["job_id"] == job_id and listing["jobs"][0]["params"]["source"] == "panel"
    log = mod.client.get(f"/api/jobs/{job_id}/log").json()
    assert "--dry-run" in log["text"] and log["offset"] == log["size"]
    assert mod.client.get(f"/api/jobs/{job_id}/log?offset={log['offset']}").json()["text"] == ""
    assert mod.client.post(f"/api/jobs/{job_id}/cancel").json()["cancelled"] is False
    assert mod.client.post("/api/jobs", json={"kind": "other"}).status_code == 400
    assert mod.client.get("/api/jobs/nope").status_code == 404
    status = mod.client.get("/api/status").json()
    assert status["workspace"]["root"] == str(mod.ws.resolve()) and status["jobs"]["active"] == 0
    inv = mod.client.get("/api/inventory").json()
    assert [r["name"] for r in inv["recipes"]] == ["pretrain"]


def test_doctor_checks_the_interpreter(mod):
    result = mod.client.post("/api/doctor").json()
    assert result["checked"] is True and result["python_path"] == sys.executable
    assert result["lloom"] is not None  # the workspace's own lloom package imports
    assert result["ok"] == ("problem" not in result)
    assert mod.client.get("/api/status").json()["doctor"]["checked"] is True


# -- the core: logging, reports and a follow-up graph --------------------------------------

def _core(path, body):
    if path == "/api/run":
        return 200, {"id": "run-7", "status": "finished", "run_dir": "/runs/run-7"}
    return 200, {}


def test_a_finished_job_logs_reports_and_runs_its_follow_up_graph(tmp_path):
    with fake_server(_core) as (server, url):
        ws = make_workspace(tmp_path / "ws")
        app = _app(tmp_path, ws, core_url=url)
        client = TestClient(app)
        try:
            code, out = tool(client, "run_stage", stage="prepare_data",
                             on_complete_graph="judge-graph", wait_seconds=60)
            assert code == 200 and out["ok"], out
            job = _until(lambda: (lambda j: j if (j.get("on_complete") or {}).get("status")
                                  == "finished" else None)(app.state.service.jobs.get(out["job_id"])))
            assert job["on_complete"]["run_id"] == "run-7"
            runs = [c for c in server.calls if c[0] == "/api/run"]
            assert runs[0][2] == {"graph": "judge-graph", "trigger": "lloom"}
            events = [c for c in server.calls if c[0] == "/m/event_log/api/events"]
            assert {e[2]["event"] for e in events} >= {"lloom.job_started", "lloom.job_finished"}
            assert all(e[2]["source"] == "lloom" for e in events)
            assert all("origin" not in c[1] for c in server.calls), "a process sends no Origin"
            reports = [c for c in server.calls if c[0] == "/api/reports"]
            assert reports and reports[0][2]["severity"] == "success"
        finally:
            app.state.service.shutdown()


def test_a_failed_job_skips_its_follow_up_graph(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_EXIT", "1")
    with fake_server(_core) as (server, url):
        ws = make_workspace(tmp_path / "ws")
        app = _app(tmp_path, ws, core_url=url)
        try:
            code, out = tool(TestClient(app), "run_stage", stage="pretrain",
                             on_complete_graph="judge-graph", wait_seconds=60)
            assert out["status"] == "failed"
            job = _until(lambda: (lambda j: j if j.get("on_complete") else None)(
                app.state.service.jobs.get(out["job_id"])))
            assert job["on_complete"]["status"] == "skipped"
            assert not [c for c in server.calls if c[0] == "/api/run"]
        finally:
            app.state.service.shutdown()
