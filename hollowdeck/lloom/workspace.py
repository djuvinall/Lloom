"""Where the Lloom workspace is, which interpreter runs its jobs, and what it holds.

This module is an orchestration layer and nothing more: every capability it offers
is one of the workspace's own stage scripts (``scripts/*.py``) run in a child
process, under the workspace's own interpreter, with the workspace as its working
directory -- exactly as a person runs them by hand. So the module server never
imports the Lloom framework (or torch): it reads the workspace's files, and it
starts its scripts.

A **workspace** is a Lloom project: a folder with ``scripts/run_pipeline.py`` and a
``config/`` tree, like the reference project at the root of the Lloom checkout. It is
found, in order, from:

1. the module setting ``workspace`` (an absolute folder);
2. the environment variable ``LLOOM_WORKSPACE``;
3. walking **up from this file** for a folder holding the Lloom checkout's own files
   (``lloom/pipeline.py`` and ``scripts/run_pipeline.py``) -- never a folder that is
   merely *named* Lloom (INTEROP.md, *Converting an existing project*). That is what
   finds the checkout when HollowDeck scans ``<checkout>/hollowdeck`` in place.

The **interpreter** jobs run under needs torch and the workspace's requirements, which
the interpreter serving this module usually does not have. It is found from the
module setting ``python``, then ``LLOOM_PYTHON``, then a ``.venv``/``venv`` inside the
workspace, and last this module's own interpreter.
"""

from __future__ import annotations

import ast
import csv
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

CHECKOUT_MARKERS = ("lloom/pipeline.py", "scripts/run_pipeline.py")
WORKSPACE_MARKERS = ("scripts/run_pipeline.py",)

#: A name that becomes part of a path inside the workspace: a run, a recipe, a
#: preset, a stage, a dataset. No separators, no leading dot, so no traversal.
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")

#: The stages the reference project ships, in pipeline order.
REFERENCE_STAGES = (
    "prepare_data", "train_tokenizer", "tokenize_dataset", "preflight", "pretrain",
    "finetune_sft_lora", "finetune_sft_full", "evaluate", "judge", "quantize",
)

#: The checkpoint files worth listing. Rolling step_*.pt snapshots are left out.
CHECKPOINT_FILES = ("best.pt", "last.pt", "merged.pt", "adapter.pt", "model_int8.pt",
                    "model.safetensors")

#: The order `generate` and the library pick "the run's model" in: the newest
#: finished stage first. Mirrors scripts/generate.py.
PREFERRED_CHECKPOINTS = ("sft_lora/merged.pt", "sft_full/best.pt", "pretrain/best.pt")


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------

def unquote(raw: Any) -> str:
    """Trim, strip one matching pair of surrounding quotes, trim (INTEROP.md §12, P090).

    Explorer's *Copy as path* wraps a path in quotes; a one-sided or mismatched quote
    is left alone, because it may be part of a name.
    """
    text = str(raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def check_workspace(path: Path, source: str) -> tuple[Path | None, str]:
    if not path.is_dir():
        return None, f'the workspace "{path}" (from {source}) is not a folder'
    missing = [m for m in WORKSPACE_MARKERS if not (path / m).is_file()]
    if missing:
        return None, (f'"{path}" (from {source}) is not a Lloom project: it has no '
                      f'{", ".join(missing)}')
    return path.resolve(), ""


def resolve_workspace(settings: dict, module_dir: Path,
                      env: dict | None = None) -> tuple[Path | None, str, str]:
    """``(root or None, where it came from, problem or "")``."""
    env = os.environ if env is None else env
    for raw, source in ((settings.get("workspace"), "the workspace setting"),
                        (env.get("LLOOM_WORKSPACE"), "LLOOM_WORKSPACE")):
        text = unquote(raw)
        if not text:
            continue
        path = Path(os.path.expanduser(text))
        if not path.is_absolute():
            return None, source, (f'{source} "{text}" is a relative path; give the absolute '
                                  f"folder of a Lloom project")
        root, problem = check_workspace(path, source)
        return root, source, problem
    here = Path(module_dir).resolve()
    for parent in (here, *here.parents):
        if all((parent / m).is_file() for m in CHECKOUT_MARKERS):
            return parent, "this module's location", ""
    return None, "", ("no Lloom workspace: set this module's 'workspace' setting to the "
                      "folder of a Lloom project (the one holding scripts/ and config/), "
                      "then reload the module")


def resolve_python(settings: dict, root: Path | None,
                   env: dict | None = None) -> tuple[str, str, str]:
    """``(interpreter, where it came from, problem or "")``."""
    env = os.environ if env is None else env
    for raw, source in ((settings.get("python"), "the python setting"),
                        (env.get("LLOOM_PYTHON"), "LLOOM_PYTHON")):
        text = unquote(raw)
        if text:
            return _check_python(text, source)
    if root is not None:
        for rel in (".venv/Scripts/python.exe", ".venv/bin/python",
                    "venv/Scripts/python.exe", "venv/bin/python"):
            if (root / rel).is_file():
                return str(root / rel), "the workspace's virtual environment", ""
    return sys.executable, "this module's own interpreter", ""


def _check_python(text: str, source: str) -> tuple[str, str, str]:
    path = Path(os.path.expanduser(text))
    if path.is_absolute():
        if path.is_file():
            return str(path), source, ""
        return str(path), source, f'{source} "{text}" does not exist'
    if os.sep in text or (os.altsep and os.altsep in text):
        return text, source, (f'{source} "{text}" is a relative path; give an absolute path '
                              f"or a command name on PATH")
    found = shutil.which(text)
    if found:
        return found, source, ""
    return text, source, f'{source} "{text}" is not on PATH'


# ---------------------------------------------------------------------------
# small readers
# ---------------------------------------------------------------------------

def rel(path: Path, root: Path) -> str:
    """A workspace-relative path with forward slashes: portable across machines."""
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def load_yaml(path: Path) -> Any:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - listed in requires
        raise RuntimeError("reading Lloom's YAML needs PyYAML in the interpreter serving "
                           "this module (pip install pyyaml)") from exc
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def leading_comment(path: Path, limit: int = 6) -> str:
    """The ``#`` comment block a YAML file opens with -- its description."""
    lines = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped.startswith("#"):
                    break
                lines.append(stripped.lstrip("#").strip())
                if len(lines) >= limit:
                    break
    except OSError:
        return ""
    return " ".join(x for x in lines if x)


def safe_name(value: Any, what: str) -> str:
    text = unquote(value)
    if not NAME_RE.match(text) or ".." in text:
        raise ValueError(f'{what} "{text}" is not a plain name (letters, digits, ., _ and -)')
    return text


def inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def workspace_file(root: Path, value: Any, what: str) -> Path:
    """A workspace-relative path the caller named, refused if it leaves the workspace."""
    text = unquote(value).replace("\\", "/")
    if not text:
        raise ValueError(f"{what} is empty")
    path = Path(text)
    full = path if path.is_absolute() else root / path
    if not inside(root, full):
        raise ValueError(f'{what} "{text}" is outside the workspace {root}')
    return full


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------

def list_recipes(root: Path) -> list[dict]:
    out = []
    for path in sorted((root / "config" / "pipelines").glob("*.y*ml")):
        entry: dict = {"name": path.stem, "path": rel(path, root), "title": path.stem,
                       "description": leading_comment(path), "stages": [], "problem": ""}
        try:
            data = load_yaml(path) or {}
            entry["title"] = str(data.get("name") or path.stem)
            for stage in data.get("stages") or []:
                cmd = [str(c) for c in stage.get("cmd") or []]
                entry["stages"].append({
                    "name": str(stage.get("name", "")),
                    "script": cmd[0] if cmd else "",
                    "args": cmd[1:],
                    "pass_overrides": bool(stage.get("pass_overrides")),
                    "skip_if": stage.get("skip_if") or "",
                })
            if not entry["stages"]:
                entry["problem"] = "the recipe has no stages"
        except Exception as exc:  # a broken recipe is shown, not fatal
            entry["problem"] = f"{type(exc).__name__}: {exc}"
        out.append(entry)
    return out


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def estimate_params(model: dict, vocab: int) -> dict:
    """A rough parameter count from a resolved ``model:`` block -- for the Library, not
    for anything that must be exact. Norms and biases are ignored."""
    try:
        d = int(model.get("d_model") or 0)
        layers = int(model.get("n_layers") or 0)
        heads = int(model.get("n_heads") or 1)
        kv = int(model.get("n_kv_heads") or heads)
        ff = int(model.get("intermediate_size") or 4 * d)
        experts = int(model.get("n_experts") or 0)
        vocab = int(max(vocab, int(model.get("vocab_size") or 0)))
    except (TypeError, ValueError):
        return {}
    if not (d and layers):
        return {}
    head_dim = d // max(heads, 1)
    attn = 2 * d * d + 2 * d * kv * head_dim
    mlp_one = (2 if model.get("mlp_type") == "gelu" else 3) * d * ff
    mlp = experts * mlp_one + d * experts if experts else mlp_one
    body = layers * (attn + mlp)
    embed = vocab * d * (1 if model.get("tie_embeddings", True) else 2)
    return {"approx_params": body + embed, "approx_non_embedding_params": body}


def list_presets(root: Path) -> list[dict]:
    base_model: dict = {}
    vocab = 0
    try:
        base = load_yaml(root / "config" / "training_config.yaml") or {}
        base_model = base.get("model") or {}
    except Exception:
        pass
    try:
        vocab = int((load_yaml(root / "config" / "tokenizer_config.yaml") or {}).get("vocab_size") or 0)
    except Exception:
        pass
    out = []
    for path in sorted((root / "config" / "presets").glob("*.y*ml")):
        entry: dict = {"name": path.stem, "path": rel(path, root),
                       "description": leading_comment(path), "model": {}, "training": {},
                       "problem": ""}
        try:
            data = load_yaml(path) or {}
            entry["model"] = data.get("model") or {}
            entry["training"] = data.get("training") or {}
            entry.update(estimate_params(_deep_merge(base_model, entry["model"]), vocab))
        except Exception as exc:
            entry["problem"] = f"{type(exc).__name__}: {exc}"
        out.append(entry)
    return out


_DEFAULT_CONFIG_RE = re.compile(
    r"""add_config_args\(\s*\w+\s*,\s*["']([^"']+)["']|["']--config["']\s*,\s*default\s*=\s*["']([^"']+)["']""")


def describe_script(path: Path) -> dict:
    source = path.read_text(encoding="utf-8", errors="replace")
    doc = ""
    try:
        doc = ast.get_docstring(ast.parse(source)) or ""
    except SyntaxError:
        pass
    summary = doc.split("\n\n", 1)[0].replace("\n", " ").strip()
    match = _DEFAULT_CONFIG_RE.search(source)
    return {
        "name": path.stem,
        "path": path.name,
        "summary": summary,
        "doc": doc,
        "default_config": (match.group(1) or match.group(2)) if match else "",
        "takes_overrides": "add_config_args(" in source,
        "reference": path.stem in REFERENCE_STAGES,
    }


def list_stages(root: Path) -> list[dict]:
    out = []
    for path in sorted((root / "scripts").glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            entry = describe_script(path)
        except OSError as exc:
            entry = {"name": path.stem, "path": path.name, "summary": "", "doc": "",
                     "default_config": "", "takes_overrides": False,
                     "reference": path.stem in REFERENCE_STAGES, "problem": str(exc)}
        entry["path"] = rel(path, root)
        out.append(entry)
    return out


def _float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def metrics_summary(path: Path) -> dict | None:
    """The newest train and validation numbers from a Lloom metrics CSV, or ``None``.

    Train and validation rows are interleaved in one file whose header grows as new
    columns appear. Pretraining logs ``loss/total`` and ``val/loss/total`` (+
    ``val/perplexity/total``); SFT logs ``loss/train`` and ``loss/val``.
    """
    if not path.is_file():
        return None
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except (OSError, csv.Error):
        return None
    out: dict = {"rows": len(rows), "step": None, "train_loss": None, "val_loss": None,
                 "val_perplexity": None, "best_val_loss": None, "lr": None,
                 "updated_at": path.stat().st_mtime}
    for row in rows:
        step = _float(row.get("step"))
        if step is not None:
            out["step"] = int(step)
        train = _float(row.get("loss/total"))
        if train is None:
            train = _float(row.get("loss/train"))
        if train is not None:
            out["train_loss"] = train
            out["lr"] = _float(row.get("lr")) if row.get("lr") else out["lr"]
        val = _float(row.get("val/loss/total"))
        if val is None:
            val = _float(row.get("loss/val"))
        if val is not None:
            out["val_loss"] = val
            ppl = _float(row.get("val/perplexity/total"))
            if ppl is not None:
                out["val_perplexity"] = ppl
            best = out["best_val_loss"]
            out["best_val_loss"] = val if best is None else min(best, val)
    return out


def list_checkpoints(run_dir: Path, root: Path) -> list[dict]:
    out = []
    ckpt_dir = run_dir / "checkpoints"
    if not ckpt_dir.is_dir():
        return out
    for stage_dir in sorted(p for p in ckpt_dir.iterdir() if p.is_dir()):
        for name in CHECKPOINT_FILES:
            path = stage_dir / name
            if path.is_file():
                stat = path.stat()
                out.append({"stage": stage_dir.name, "file": name, "path": rel(path, root),
                            "size_mb": round(stat.st_size / 1e6, 2), "mtime": stat.st_mtime})
    return out


def preferred_checkpoint(run_dir: Path, root: Path) -> str:
    for candidate in PREFERRED_CHECKPOINTS:
        if (run_dir / "checkpoints" / candidate).is_file():
            return rel(run_dir / "checkpoints" / candidate, root)
    return ""


def describe_run(run_dir: Path, root: Path) -> dict:
    checkpoints = list_checkpoints(run_dir, root)
    mtimes = [c["mtime"] for c in checkpoints]
    metrics = {"pretrain": metrics_summary(run_dir / "logs" / "metrics.csv"),
               "sft": metrics_summary(run_dir / "logs" / "sft_metrics.csv")}
    for m in metrics.values():
        if m:
            mtimes.append(m["updated_at"])
    eval_path = run_dir / "eval" / "eval_results.json"
    judge_path = run_dir / "eval" / "judge_results.json"
    for p in (eval_path, judge_path):
        if p.is_file():
            mtimes.append(p.stat().st_mtime)
    try:
        mtimes.append(run_dir.stat().st_mtime)
    except OSError:
        pass
    return {
        "name": run_dir.name,
        "path": rel(run_dir, root),
        "checkpoints": checkpoints,
        "model": preferred_checkpoint(run_dir, root),
        "metrics": metrics,
        "eval": read_json(eval_path) if eval_path.is_file() else None,
        "judge": read_json(judge_path) if judge_path.is_file() else None,
        "updated_at": max(mtimes) if mtimes else 0.0,
    }


def list_runs(root: Path) -> list[dict]:
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return []
    runs = [describe_run(p, root) for p in runs_dir.iterdir()
            if p.is_dir() and NAME_RE.match(p.name)]
    runs.sort(key=lambda r: (-r["updated_at"], r["name"]))
    return runs


def run_dir(root: Path, run_name: Any) -> Path:
    return root / "runs" / safe_name(run_name or "default", "run name")


def inventory(root: Path) -> dict:
    started = time.monotonic()
    return {
        "recipes": list_recipes(root),
        "presets": list_presets(root),
        "stages": list_stages(root),
        "runs": list_runs(root),
        "seconds": round(time.monotonic() - started, 3),
    }
