"""What this module publishes about the workspace: Library assets and pipeline nodes.

**Assets** (INTEROP.md, *Optional: own assets*). Every recipe, preset, stage script,
run and checkpoint in the workspace becomes one asset in this module's store, which
HollowDeck's Asset Library lists and a graph's Asset node emits. Each follows the
payload convention consumers rely on -- ``payload["outputs"][<output>]`` is the value
the asset stands for -- so an Asset node for *"Lloom preset: small"* emits ``"small"``,
which wires straight into a Run Pipeline node's ``preset``. They are stamped:

* ``origin: "ingested"`` -- derived from what the workspace says about itself, never
  guessed (§13, *Set origin explicitly on an ingested asset*);
* ``kind`` -- ``lloom.recipe``, ``lloom.preset``, ``script``, ``lloom.run``,
  ``lloom.checkpoint``: recorded here, at ingestion, never inferred from a payload;
* ``captured_against`` -- this module's version, so drift is legible;
* ``properties.synced: true`` -- which is how a sync knows an asset is its own. A sync
  rewrites and removes only those; an asset a person saved through ``POST api/assets``
  is never touched.

**Pipeline nodes** (§13, *tools_file*). Each recipe also becomes a tool node,
``lloom/pipeline_<recipe>``, whose preset and stage inputs are dropdowns of what the
workspace actually holds -- which a static manifest cannot offer. They are written to
``<data dir>/tools.json`` (the manifest's ``tools_file``), atomically, only when the
bytes change, and validated first: a bad declaration would make the whole module
``invalid`` and take this module's own panel with it.

Both are re-derived from disk on every sync: at start, when a job ends, and when a
person (or a graph, through ``sync_library``) asks.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

SYNC_TAG = "lloom"

# -- the declaration rules the core applies (INTEROP.md §12, §13), checked before a write

TOOL_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SOCKET_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
EFFECTS = ("none", "reads", "writes", "executes", "network")
WIDGETS = ("string", "text", "int", "float", "bool", "select", "path", "json")
BASE_TYPES = ("str", "int", "float", "bool", "any", "bundle", "item", "model", "agent")
DOC_KEYS = ("what", "how", "why", "best_uses")
MAX_TOOLS = 64
MAX_RECIPE_NODES = 32


def socket_type_ok(stype: Any) -> bool:
    if not isinstance(stype, str):
        return False
    if stype.startswith("list[") and stype.endswith("]"):
        return socket_type_ok(stype[5:-1])
    return stype in BASE_TYPES


def validate_tools(tools: Any, where: str = "tools") -> list[str]:
    """Every problem with a list of tool declarations, each naming its entry."""
    problems: list[str] = []
    if not isinstance(tools, list):
        return [f"{where} must be a list"]
    if len(tools) > MAX_TOOLS:
        problems.append(f"{where} declares {len(tools)} tools; at most {MAX_TOOLS}")
    seen: set[str] = set()
    for i, tool in enumerate(tools):
        at = f"{where}[{i}]"
        if not isinstance(tool, dict):
            problems.append(f"{at} must be an object")
            continue
        tid = tool.get("id")
        if not isinstance(tid, str) or not TOOL_ID_RE.match(tid):
            problems.append(f"{at}.id {tid!r} must match {TOOL_ID_RE.pattern}")
        elif tid in seen:
            problems.append(f"{at}.id {tid!r} is declared twice")
        else:
            seen.add(tid)
        if tool.get("effects") not in EFFECTS:
            problems.append(f"{at}.effects must be one of {list(EFFECTS)} (write it out)")
        if "calls_model" in tool and not isinstance(tool["calls_model"], bool):
            problems.append(f"{at}.calls_model must be true or false")
        doc = tool.get("doc")
        if doc is not None and not isinstance(doc, str):
            if not isinstance(doc, dict):
                problems.append(f"{at}.doc must be an object or a string")
            else:
                for key, value in doc.items():
                    if key not in DOC_KEYS:
                        problems.append(f"{at}.doc.{key} is not one of {list(DOC_KEYS)}")
                    elif key == "best_uses":
                        if not (isinstance(value, str) or (isinstance(value, list) and
                                                          all(isinstance(v, str) for v in value))):
                            problems.append(f"{at}.doc.best_uses must be a string or a list of strings")
                    elif not isinstance(value, str):
                        problems.append(f"{at}.doc.{key} must be a string")
        for side in ("inputs", "outputs"):
            sockets = tool.get(side, [])
            if not isinstance(sockets, list):
                problems.append(f"{at}.{side} must be a list")
                continue
            names: set[str] = set()
            for j, sock in enumerate(sockets):
                sat = f"{at}.{side}[{j}]"
                if not isinstance(sock, dict):
                    problems.append(f"{sat} must be an object")
                    continue
                name = sock.get("name")
                if not isinstance(name, str) or not SOCKET_RE.match(name):
                    problems.append(f"{sat}.name {name!r} must be an identifier")
                elif name in names:
                    problems.append(f"{sat}.name {name!r} is declared twice")
                else:
                    names.add(name)
                if name == "allow_unattended":
                    problems.append(f"{sat}: allow_unattended is a reserved input name")
                if not socket_type_ok(sock.get("type", "any")):
                    problems.append(f"{sat}.type {sock.get('type')!r} is not a socket type")
                widget = sock.get("widget")
                if widget is not None and widget not in WIDGETS:
                    problems.append(f"{sat}.widget {widget!r} is not one of {list(WIDGETS)}")
                if widget == "select":
                    options = sock.get("options")
                    if not (isinstance(options, list) and options and
                            all(isinstance(o, str) for o in options)):
                        problems.append(f"{sat}.options must be a non-empty list of strings")
                    elif "default" in sock and sock["default"] not in options:
                        problems.append(f"{sat}.default {sock['default']!r} is not an option")
    return problems


# -- ids ------------------------------------------------------------------------

def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return cleaned or "x"


def asset_id(prefix: str, *parts: str) -> str:
    """``prefix-part-part``, slugged to the store's id rule and at most 64 characters."""
    base = "-".join([prefix, *(_slug(p) for p in parts)])
    if len(base) <= 64:
        return base
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
    return base[:55].rstrip("-") + "-" + digest


def recipe_tool_id(name: str) -> str:
    return ("pipeline_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"))[:64].rstrip("_")


# -- assets ---------------------------------------------------------------------

def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:4000]


def _asset(aid: str, name: str, kind: str, output: tuple[str, str, str], value: Any,
           tags: list[str], properties: dict, payload: dict, version: str) -> dict:
    out_name, out_type, out_desc = output
    return {
        "id": aid,
        "name": name,
        "origin": "ingested",
        "kind": kind,
        "captured_against": version,
        "tags": [SYNC_TAG, *tags],
        "interface": {"inputs": [],
                      "outputs": [{"name": out_name, "type": out_type, "description": out_desc}]},
        "properties": {"synced": True, **{k: _scalar(v) for k, v in properties.items()}},
        "payload": {"outputs": {out_name: value}, **payload},
    }


def build_assets(inv: dict, version: str) -> list[dict]:
    assets: list[dict] = []
    for r in inv.get("recipes", []):
        assets.append(_asset(
            asset_id("recipe", r["name"]), f"Lloom recipe: {r['name']}", "lloom.recipe",
            ("recipe", "str", "the recipe name, for Run Lloom Pipeline"), r["name"],
            ["recipe"],
            {"path": r["path"], "stages": len(r["stages"]), "problem": r["problem"] or None},
            {"path": r["path"], "title": r["title"], "description": r["description"],
             "stages": r["stages"]}, version))
    for p in inv.get("presets", []):
        model = p.get("model") or {}
        assets.append(_asset(
            asset_id("preset", p["name"]), f"Lloom preset: {p['name']}", "lloom.preset",
            ("preset", "str", "the preset name, for Run Lloom Pipeline or Stage"), p["name"],
            ["preset"],
            {"path": p["path"], "d_model": model.get("d_model"),
             "n_layers": model.get("n_layers"), "n_heads": model.get("n_heads"),
             "n_experts": model.get("n_experts"),
             "approx_params": p.get("approx_params"),
             "approx_non_embedding_params": p.get("approx_non_embedding_params")},
            {"path": p["path"], "description": p["description"], "model": model,
             "training": p.get("training") or {}}, version))
    for s in inv.get("stages", []):
        assets.append(_asset(
            asset_id("script", s["name"]), f"Lloom stage script: {s['name']}", "script",
            ("stage", "str", "the stage name, for Run Lloom Stage"), s["name"],
            ["script", "stage"],
            {"path": s["path"], "reference": s.get("reference", False),
             "takes_overrides": s.get("takes_overrides", False),
             "default_config": s.get("default_config") or None},
            {"path": s["path"], "summary": s.get("summary", ""), "doc": s.get("doc", ""),
             "command": ["python", s["path"]], "cwd": "the workspace root",
             "default_config": s.get("default_config", "")}, version))
    for run in inv.get("runs", []):
        pre = (run.get("metrics") or {}).get("pretrain") or {}
        sft = (run.get("metrics") or {}).get("sft") or {}
        judge = run.get("judge") or {}
        assets.append(_asset(
            asset_id("run", run["name"]), f"Lloom run: {run['name']}", "lloom.run",
            ("run_name", "str", "the run name, for every Lloom tool that takes one"),
            run["name"], ["run"],
            {"model": run.get("model") or None, "checkpoints": len(run["checkpoints"]),
             "pretrain_best_val_loss": pre.get("best_val_loss"),
             "sft_best_val_loss": sft.get("best_val_loss"),
             "judge_mean_score": judge.get("mean_score") if isinstance(judge, dict) else None},
            {"path": run["path"], "model": run.get("model"), "checkpoints": run["checkpoints"],
             "metrics": run.get("metrics"), "eval": run.get("eval"), "judge": run.get("judge")},
            version))
        for ck in run["checkpoints"]:
            if ck["file"] == "last.pt":
                continue  # resume state, not a model to hand to anything
            assets.append(_asset(
                asset_id("ckpt", run["name"], ck["stage"], ck["file"]),
                f"Lloom checkpoint: {run['name']} / {ck['stage']} / {ck['file']}",
                "lloom.checkpoint",
                ("checkpoint", "str", "a workspace-relative checkpoint path"), ck["path"],
                ["checkpoint", ck["stage"]],
                {"run_name": run["name"], "stage": ck["stage"], "file": ck["file"],
                 "size_mb": ck["size_mb"]},
                {"run_name": run["name"], "stage": ck["stage"], "file": ck["file"],
                 "path": ck["path"], "size_mb": ck["size_mb"], "mtime": ck["mtime"]},
                version))
    return assets


def _comparable(data: dict) -> str:
    return json.dumps({k: v for k, v in data.items() if k not in ("created_at", "api_version",
                                                                  "owner")},
                      sort_keys=True, default=str)


def sync_assets(store: Any, asset_cls: Any, inv: dict, version: str) -> dict:
    """Make the store's synced assets match the workspace. Returns what changed."""
    desired = {a["id"]: a for a in build_assets(inv, version)}
    existing, broken = store.load_all()
    by_id = {a.id: a for a in existing}
    created, updated, removed, kept_foreign = [], [], [], []
    for asset in existing:
        if asset.properties.get("synced") and asset.id not in desired:
            store.delete(asset.id)
            removed.append(asset.id)
    for aid, data in desired.items():
        current = by_id.get(aid)
        if current is not None and not current.properties.get("synced"):
            kept_foreign.append(aid)  # a person's asset under this id: never overwrite it
            continue
        new = asset_cls.from_dict(data)
        if current is not None:
            new.created_at = current.created_at
            if _comparable(current.to_dict()) == _comparable(new.to_dict()):
                continue
            updated.append(aid)
        else:
            created.append(aid)
        store.save(new)
    return {"created": created, "updated": updated, "removed": removed,
            "skipped": kept_foreign, "broken": [b.id for b in broken],
            "assets": sorted(desired), "synced_at": time.time()}


# -- pipeline nodes (the tools_file) ---------------------------------------------

_JOB_OUTPUTS = [
    {"name": "job_id", "type": "str", "description": "the job's id, for Lloom Job Status and Cancel"},
    {"name": "status", "type": "str", "description": "queued, running, succeeded, failed, cancelled or interrupted"},
    {"name": "done", "type": "bool", "description": "true once the job has ended"},
    {"name": "ok", "type": "bool", "description": "true only when the job succeeded"},
    {"name": "run_name", "type": "str", "description": "the run the job writes to"},
    {"name": "log_tail", "type": "str", "description": "the last lines of the job's output"},
    {"name": "job", "type": "any", "description": "the whole job record"},
]

NO_PRESET, FIRST, LAST, ALL = "none", "first", "last", "all"


def recipe_tool(recipe: dict, presets: list[str]) -> dict:
    stages = [s["name"] for s in recipe["stages"] if s.get("name")]
    listing = " -> ".join(stages)
    return {
        "id": recipe_tool_id(recipe["name"]),
        "title": f"Lloom: {recipe['title']} pipeline",
        "category": "lloom",
        "description": (f"Runs the Lloom recipe '{recipe['name']}' ({listing}) as a background "
                        f"job, like Run Lloom Pipeline with the recipe fixed and the presets "
                        f"and stages this workspace holds offered as choices. "
                        f"{recipe['description']}").strip(),
        "inputs": [
            {"name": "run_name", "type": "str", "label": "Run name",
             "description": "names the run; outputs land in runs/<run_name>/. Empty means 'default'",
             "widget": "string", "default": "", "required": False},
            {"name": "preset", "type": "str", "label": "Preset",
             "description": "a model preset from config/presets, or none",
             "widget": "select", "options": [NO_PRESET, *presets], "default": NO_PRESET,
             "required": False},
            {"name": "sets", "type": "list[str]", "label": "Overrides",
             "description": "dotted config overrides, one per item",
             "widget": "json", "default": [], "required": False},
            {"name": "from_stage", "type": "str", "label": "From stage",
             "description": "start here (resume a run that died)", "widget": "select",
             "options": [FIRST, *stages], "default": FIRST, "required": False},
            {"name": "until", "type": "str", "label": "Until stage",
             "description": "stop after this stage", "widget": "select",
             "options": [LAST, *stages], "default": LAST, "required": False},
            {"name": "only", "type": "str", "label": "Only stage",
             "description": "run just this stage", "widget": "select",
             "options": [ALL, *stages], "default": ALL, "required": False},
            {"name": "dry_run", "type": "bool", "label": "Dry run",
             "description": "print the stage commands without running them",
             "widget": "bool", "default": False, "required": False},
            {"name": "wait_seconds", "type": "int", "label": "Wait (s)",
             "description": "wait up to this long for the job to finish; at most 280",
             "widget": "int", "default": 0, "min": 0, "max": 280, "step": 10, "required": False},
            {"name": "on_complete_graph", "type": "str", "label": "Then run graph",
             "description": "a saved graph (slug) the core runs, unattended, when this job succeeds",
             "widget": "string", "default": "", "required": False},
        ],
        "outputs": [dict(o) for o in _JOB_OUTPUTS],
        "effects": "executes",
        "doc": {
            "what": f"Starts the '{recipe['name']}' Lloom pipeline as a background job.",
            "how": (f"Runs scripts/run_pipeline.py --pipeline {recipe['path']} in the workspace "
                    "under the configured interpreter, forwarding the preset and overrides to "
                    "every stage that takes them."),
            "why": "The recipe's own node offers the workspace's presets and stages as choices.",
            "best_uses": [f"Stages: {listing}" if listing else "An empty recipe"],
        },
    }


def build_tools_file(inv: dict) -> dict:
    presets = [p["name"] for p in inv.get("presets", []) if not p.get("problem")]
    tools, seen, dropped = [], set(), []
    for recipe in inv.get("recipes", []):
        if recipe.get("problem"):
            dropped.append(f"{recipe['name']}: {recipe['problem']}")
            continue
        tool = recipe_tool(recipe, presets)
        if not TOOL_ID_RE.match(tool["id"]) or tool["id"] in seen:
            dropped.append(f"{recipe['name']}: its node id {tool['id']!r} is taken or invalid")
            continue
        if len(tools) >= MAX_RECIPE_NODES:
            dropped.append(f"{recipe['name']}: more than {MAX_RECIPE_NODES} recipes")
            continue
        seen.add(tool["id"])
        tools.append(tool)
    return {
        "api_version": 1,
        "kind": "lloom.recipe",
        "source": "lloom workspace",
        "captured_against": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tools": tools,
        "panels": [],
        "dropped": dropped,
    }


def write_tools_file(path: Path, declaration: dict) -> bool:
    """Write atomically, only if the tools changed. ``True`` if it wrote."""
    problems = validate_tools(declaration.get("tools", []), "tools_file.tools")
    if problems:
        raise ValueError("refusing to write an invalid tools file: " + "; ".join(problems[:5]))
    body = {k: v for k, v in declaration.items() if k != "dropped"}
    if path.is_file():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
            if current.get("tools") == body["tools"] and current.get("panels") == body["panels"]:
                return False
        except (OSError, ValueError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)
    return True


def ensure_tools_file(path: Path) -> None:
    """Write an empty declaration at start if there is none (INTEROP.md §13, P105)."""
    if not path.is_file():
        write_tools_file(path, {"api_version": 1, "kind": "lloom.recipe",
                                "source": "lloom workspace", "captured_against": "",
                                "tools": [], "panels": []})


def find_recipe(inv_recipes: list[dict], tool_id: str) -> dict | None:
    for recipe in inv_recipes:
        if recipe_tool_id(recipe["name"]) == tool_id:
            return recipe
    return None


__all__ = ["validate_tools", "build_assets", "sync_assets", "build_tools_file",
           "write_tools_file", "ensure_tools_file", "find_recipe", "recipe_tool_id",
           "asset_id"]
