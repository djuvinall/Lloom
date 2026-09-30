"""The Lloom service: every tool, and every panel action, in one place.

``POST tools/<id>`` (the core's broker, on behalf of a graph or another module) and the
panel's ``api/*`` routes both call into :class:`LloomService`, so a job started from the
panel and one started by a graph are the same job, recorded the same way.

A tool answers ``{"outputs": {...}}`` with every declared output (INTEROP.md §12), or
raises :class:`ToolError`, which the route turns into ``{"detail": ...}`` with a 4xx or
5xx. Details are short: the broker cuts a module's refusal at a fixed length.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from . import grading, library
from . import workspace as ws
from .core_client import CoreClient
from .jobs import TERMINAL, JobManager, summarize

MAX_WAIT = 280          # seconds a tool may block: under the engine's 300 s per call
SPECIAL_EVAL_FILES = ("retrieval_pairs", "themed")
_PROMPT_KEYS = ("prompt", "instruction", "question")
_RESPONSE_KEYS = ("response", "output", "completion", "answer")

DOCTOR_CODE = r"""
import importlib, json, sys
out = {"python": sys.version.split()[0], "executable": sys.executable, "packages": {}}
for name in ("torch", "numpy", "yaml", "sentencepiece", "safetensors",
             "matplotlib", "wandb"):
    try:
        mod = importlib.import_module(name)
        out["packages"][name] = str(getattr(mod, "__version__", "installed"))
    except Exception:
        out["packages"][name] = None
try:
    import torch
    out["cuda"] = bool(torch.cuda.is_available())
    out["device"] = torch.cuda.get_device_name(0) if out["cuda"] else "cpu"
except Exception:
    out["cuda"] = False
    out["device"] = None
try:
    import lloom
    out["lloom"] = lloom.__version__
except Exception as exc:
    out["lloom"] = None
    out["lloom_problem"] = f"{type(exc).__name__}: {exc}"
print(json.dumps(out))
"""
REQUIRED_PACKAGES = ("torch", "numpy", "yaml", "sentencepiece", "safetensors")


class ToolError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


# -- input readers ---------------------------------------------------------------

def clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def parse_list(value: Any) -> list[str]:
    """A list of strings from a list, a JSON list typed as text, or one item per line."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return parse_list(data)
        except ValueError:
            pass
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_items(value: Any) -> list:
    """Objects from a list, a single object, a JSON value typed as text, or JSONL."""
    if value is None or value == "" or value == []:
        return []
    if isinstance(value, dict):
        if "$bundle" in value and isinstance(value["$bundle"], dict):
            return [value["$bundle"]]
        return [value]
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(parse_items(item) if isinstance(item, (dict, str)) else [])
        return out
    text = str(value).strip()
    if not text:
        return []
    if text[0] in "[{":
        try:
            return parse_items(json.loads(text))
        except ValueError:
            pass
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.extend(parse_items(json.loads(line)))
        except ValueError:
            raise ToolError(400, f"not JSON or JSONL: {line[:60]!r}") from None
    return rows


def _first(row: dict, keys: tuple) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


class LloomService:
    def __init__(self, *, module_id: str, version: str, module_dir: Path, data_dir: Path,
                 settings: dict | None, core: CoreClient, proc: Any, store: Any,
                 asset_cls: Any, env: dict | None = None):
        self.module_id = module_id
        self.version = version
        self.module_dir = Path(module_dir)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings = dict(settings or {})
        self.core = core
        self.proc = proc
        self.store = store
        self.asset_cls = asset_cls
        self.env = os.environ if env is None else env
        self.root, self.root_source, self.root_problem = ws.resolve_workspace(
            self.settings, self.module_dir, self.env)
        self.python, self.python_source, self.python_problem = ws.resolve_python(
            self.settings, self.root, self.env)
        self.max_concurrent = clamp_int(self.settings.get("max_concurrent_jobs"), 1, 8, 1)
        self.allow_replace = as_bool(self.settings.get("allow_replace_data"), False)
        self.report_jobs = as_bool(self.settings.get("report_jobs"), True)
        self.jobs = JobManager(self.data_dir, proc=proc, max_concurrent=self.max_concurrent,
                               keep=clamp_int(self.settings.get("keep_jobs"), 10, 1000, 100),
                               on_finish=[self._job_finished])
        self.work_dir = self.data_dir / "work"
        self.tools_path = self.data_dir / "tools.json"
        self._sync_lock = threading.Lock()
        self.last_sync: dict | None = None
        self._doctor: dict | None = None
        self.tools = {
            "status": self.tool_status,
            "run_pipeline": self.tool_run_pipeline,
            "run_stage": self.tool_run_stage,
            "job_status": self.tool_job_status,
            "cancel_job": self.tool_cancel_job,
            "list_runs": self.tool_list_runs,
            "run_metrics": self.tool_run_metrics,
            "generate": self.tool_generate,
            "judge_request": self.tool_judge_request,
            "judge_scores": self.tool_judge_scores,
            "add_sft_data": self.tool_add_sft_data,
            "sync_library": self.tool_sync_library,
        }

    # -- lifecycle -------------------------------------------------------------

    def start(self, background_sync: bool = True) -> "LloomService":
        where = f"{self.root} (from {self.root_source})" if self.root else "none"
        print(f"[lloom] workspace: {where}", flush=True)
        if self.root_problem:
            print(f"[lloom] workspace problem: {self.root_problem}", flush=True)
        print(f"[lloom] interpreter: {self.python} (from {self.python_source})"
              + (f" -- {self.python_problem}" if self.python_problem else ""), flush=True)
        for job_id in self.jobs.recovered:
            self.core.log("warning", "lloom.job_interrupted",
                          f"job {job_id} was running when the module stopped", job=job_id)
        self.jobs.start()
        library.ensure_tools_file(self.tools_path)
        if background_sync:
            self.sync_async()
        return self

    def shutdown(self) -> None:
        self.jobs.shutdown()

    def hold(self) -> dict:
        reason = self.jobs.hold_reason()
        return {"hold": bool(reason), "reason": reason or "no jobs in flight",
                "jobs": [r["id"] for r in self.jobs.active()]}

    # -- plumbing ----------------------------------------------------------------

    def require_root(self) -> Path:
        if self.root is None:
            raise ToolError(409, self.root_problem)
        if self.python_problem:
            raise ToolError(409, self.python_problem)
        return self.root

    def call(self, tool_id: str, body: Any) -> dict:
        inputs = body.get("inputs") if isinstance(body, dict) else None
        inputs = inputs if isinstance(inputs, dict) else {}
        handler = self.tools.get(tool_id)
        if handler is not None:
            return handler(inputs)
        if tool_id.startswith("pipeline_"):
            return self.tool_recipe(tool_id, inputs)
        raise ToolError(404, f"lloom has no tool {tool_id!r}")

    def _work(self, suffix: str) -> Path:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        return self.work_dir / f"{uuid.uuid4().hex[:12]}{suffix}"

    def _data_config(self, root: Path) -> dict:
        try:
            return ws.load_yaml(root / "config" / "data_config.yaml") or {}
        except Exception:
            return {}

    # -- starting jobs ------------------------------------------------------------

    def _recipe_path(self, root: Path, value: Any) -> Path:
        text = ws.unquote(value) or "pretrain"
        if ws.NAME_RE.match(text) and not text.endswith((".yaml", ".yml")):
            for suffix in (".yaml", ".yml"):
                candidate = root / "config" / "pipelines" / f"{text}{suffix}"
                if candidate.is_file():
                    return candidate
            have = ", ".join(r["name"] for r in ws.list_recipes(root)) or "none"
            raise ToolError(404, f'no recipe "{text}" in config/pipelines (have: {have})')
        try:
            path = ws.workspace_file(root, text, "recipe")
        except ValueError as exc:
            raise ToolError(400, str(exc)) from None
        if not path.is_file() or path.suffix not in (".yaml", ".yml"):
            raise ToolError(404, f'recipe "{text}" is not a YAML file in the workspace')
        return path

    def _preset(self, root: Path, value: Any) -> str:
        text = ws.unquote(value)
        if text in ("", "none"):
            return ""
        if ws.NAME_RE.match(text) and not text.endswith((".yaml", ".yml")):
            if (root / "config" / "presets" / f"{text}.yaml").is_file():
                return text
            have = ", ".join(p["name"] for p in ws.list_presets(root)) or "none"
            raise ToolError(404, f'no preset "{text}" in config/presets (have: {have})')
        try:
            path = ws.workspace_file(root, text, "preset")
        except ValueError as exc:
            raise ToolError(400, str(exc)) from None
        if not path.is_file():
            raise ToolError(404, f'preset "{text}" does not exist in the workspace')
        return ws.rel(path, root)

    @staticmethod
    def _sets(value: Any) -> list[str]:
        sets = parse_list(value)
        for item in sets:
            if "=" not in item or item.startswith("="):
                raise ToolError(400, f'override "{item}" is not key.path=value')
        return sets

    @staticmethod
    def _graph(value: Any) -> str:
        text = ws.unquote(value)
        if len(text) > 300 or "\n" in text:
            raise ToolError(400, "on_complete_graph must be one saved graph's slug or path")
        return text

    def _run_name(self, value: Any) -> str:
        try:
            return ws.safe_name(value or "default", "run name")
        except ValueError as exc:
            raise ToolError(400, str(exc)) from None

    def start_pipeline(self, params: dict, source: str = "tool") -> dict:
        root = self.require_root()
        recipe_path = self._recipe_path(root, params.get("recipe"))
        run_name = self._run_name(params.get("run_name"))
        preset = self._preset(root, params.get("preset"))
        sets = self._sets(params.get("sets"))
        try:
            data = ws.load_yaml(recipe_path) or {}
        except Exception as exc:
            raise ToolError(400, f"recipe {recipe_path.name} will not parse: {exc}") from None
        stage_names = [str(s.get("name")) for s in data.get("stages") or []]
        if not stage_names:
            raise ToolError(400, f"recipe {recipe_path.name} has no stages")
        argv = [self.python, "scripts/run_pipeline.py", "--pipeline", ws.rel(recipe_path, root),
                "--run-name", run_name]
        if preset:
            argv += ["--preset", preset]
        for item in sets:
            argv += ["--set", item]
        for key, flag in (("only", "--only"), ("from_stage", "--from"), ("until", "--until")):
            value = ws.unquote(params.get(key))
            if value:
                if value not in stage_names:
                    raise ToolError(400, f'{key} "{value}" is not a stage of {recipe_path.stem} '
                                         f'({", ".join(stage_names)})')
                argv += [flag, value]
        if as_bool(params.get("dry_run")):
            argv.append("--dry-run")
        recipe_name = recipe_path.stem
        rec = self.jobs.submit(
            kind="pipeline", title=f"pipeline {recipe_name} / {run_name}", argv=argv, cwd=root,
            run_name=run_name, on_complete_graph=self._graph(params.get("on_complete_graph")),
            params={"recipe": recipe_name, "preset": preset, "sets": sets, "source": source,
                    "stages": stage_names})
        self._started(rec)
        return rec

    def start_stage(self, params: dict, source: str = "tool") -> dict:
        root = self.require_root()
        try:
            stage = ws.safe_name(params.get("stage"), "stage")
        except ValueError as exc:
            raise ToolError(400, str(exc)) from None
        script = root / "scripts" / f"{stage}.py"
        if not script.is_file():
            have = ", ".join(s["name"] for s in ws.list_stages(root))
            raise ToolError(404, f'no stage script scripts/{stage}.py (have: {have})')
        info = ws.describe_script(script)
        preset = self._preset(root, params.get("preset"))
        sets = self._sets(params.get("sets"))
        argv = [self.python, f"scripts/{stage}.py"]
        run_name = ""
        if info["takes_overrides"]:
            run_name = self._run_name(params.get("run_name"))
            if preset:
                argv += ["--preset", preset]
            argv += ["--set", f"run_name={run_name}"]
            for item in sets:
                argv += ["--set", item]
        elif preset or sets:
            raise ToolError(400, f"stage {stage} takes no preset or overrides; it reads "
                                 f"{info['default_config'] or 'its own config file'}")
        checkpoint = ws.unquote(params.get("checkpoint"))
        if checkpoint:
            if "--checkpoint" not in script.read_text(encoding="utf-8", errors="replace"):
                raise ToolError(400, f"stage {stage} takes no checkpoint")
            try:
                path = ws.workspace_file(root, checkpoint, "checkpoint")
            except ValueError as exc:
                raise ToolError(400, str(exc)) from None
            if not path.is_file():
                raise ToolError(404, f'checkpoint "{checkpoint}" does not exist in the workspace')
            argv += ["--checkpoint", ws.rel(path, root)]
        argv += parse_list(params.get("args"))
        title = f"stage {stage}" + (f" / {run_name}" if run_name else "")
        rec = self.jobs.submit(
            kind="stage", title=title, argv=argv, cwd=root, run_name=run_name, stage=stage,
            on_complete_graph=self._graph(params.get("on_complete_graph")),
            params={"stage": stage, "preset": preset, "sets": sets, "source": source,
                    "checkpoint": checkpoint})
        self._started(rec)
        return rec

    def _started(self, rec: dict) -> None:
        self.core.log("info", "lloom.job_started", f"started {rec['title']}", job=rec["id"],
                      kind=rec["kind"], run_name=rec["run_name"], status=rec["status"])

    def _job_answer(self, rec: dict, wait: Any) -> dict:
        seconds = clamp_int(wait, 0, MAX_WAIT, 0)
        if seconds and rec["status"] not in TERMINAL:
            rec = self.jobs.wait(rec["id"], seconds)
        out = summarize(rec, self.jobs.tail(rec["id"], 20))
        return {"job_id": out["job_id"], "status": out["status"], "done": out["done"],
                "ok": out["ok"], "run_name": out["run_name"], "log_tail": out["log_tail"],
                "job": rec}

    # -- the tools --------------------------------------------------------------

    def tool_status(self, inputs: dict) -> dict:
        inv = self.inventory() if self.root else {}
        return {"outputs": {
            "configured": self.root is not None and not self.python_problem,
            "workspace": str(self.root or ""),
            "python": self.python,
            "recipes": [r["name"] for r in inv.get("recipes", [])],
            "presets": [p["name"] for p in inv.get("presets", [])],
            "stages": [s["name"] for s in inv.get("stages", [])],
            "runs": [r["name"] for r in inv.get("runs", [])],
            "active_jobs": len(self.jobs.active()),
            "problem": self.root_problem or self.python_problem or "",
        }}

    def tool_run_pipeline(self, inputs: dict) -> dict:
        rec = self.start_pipeline(inputs)
        return {"outputs": self._job_answer(rec, inputs.get("wait_seconds"))}

    def tool_run_stage(self, inputs: dict) -> dict:
        rec = self.start_stage(inputs)
        return {"outputs": self._job_answer(rec, inputs.get("wait_seconds"))}

    def tool_recipe(self, tool_id: str, inputs: dict) -> dict:
        root = self.require_root()
        recipe = library.find_recipe(ws.list_recipes(root), tool_id)
        if recipe is None:
            raise ToolError(404, f"the recipe behind lloom/{tool_id} is gone from "
                                 f"config/pipelines; run Sync Lloom Library")
        placeholders = {"preset": library.NO_PRESET, "from_stage": library.FIRST,
                        "until": library.LAST, "only": library.ALL}
        params = dict(inputs, recipe=recipe["name"])
        for key, placeholder in placeholders.items():
            if ws.unquote(params.get(key)) == placeholder:
                params[key] = ""
        rec = self.start_pipeline(params)
        return {"outputs": self._job_answer(rec, inputs.get("wait_seconds"))}

    def tool_job_status(self, inputs: dict) -> dict:
        job_id = ws.unquote(inputs.get("job_id"))
        rec = self.jobs.get(job_id) if job_id else self.jobs.latest()
        if rec is None:
            raise ToolError(404, f"no job {job_id!r}" if job_id else "no jobs have run yet")
        wait = clamp_int(inputs.get("wait_seconds"), 0, MAX_WAIT, 0)
        if wait and rec["status"] not in TERMINAL:
            rec = self.jobs.wait(rec["id"], wait)
        out = summarize(rec, self.jobs.tail(rec["id"], clamp_int(inputs.get("tail_lines"),
                                                                  0, 500, 40)))
        out["metrics"] = self.run_numbers(rec.get("run_name") or "")
        out["job"] = rec
        return {"outputs": out}

    def tool_cancel_job(self, inputs: dict) -> dict:
        job_id = ws.unquote(inputs.get("job_id"))
        if not job_id:
            raise ToolError(400, "job_id is required")
        try:
            rec, stopped = self.jobs.cancel(job_id)
        except KeyError:
            raise ToolError(404, f"no job {job_id!r}") from None
        if stopped:
            self.core.log("warning", "lloom.job_cancel", f"cancel requested for {rec['title']}",
                          job=job_id)
        return {"outputs": {"job_id": job_id, "status": rec["status"], "cancelled": stopped}}

    def tool_list_runs(self, inputs: dict) -> dict:
        runs = ws.list_runs(self.require_root())
        details = [{k: r[k] for k in ("name", "model", "checkpoints", "metrics", "eval", "judge",
                                      "updated_at")} for r in runs]
        return {"outputs": {"runs": [r["name"] for r in runs],
                            "latest_run": runs[0]["name"] if runs else "",
                            "details": details}}

    def run_numbers(self, run_name: str) -> dict | None:
        if not run_name or self.root is None:
            return None
        try:
            run_dir = ws.run_dir(self.root, run_name)
        except ValueError:
            return None
        if not run_dir.is_dir():
            return None
        info = ws.describe_run(run_dir, self.root)
        return {"metrics": info["metrics"], "eval": info["eval"], "judge": info["judge"],
                "model": info["model"]}

    def tool_run_metrics(self, inputs: dict) -> dict:
        root = self.require_root()
        name = self._run_name(inputs.get("run_name"))
        run_dir = root / "runs" / name
        if not run_dir.is_dir():
            have = ", ".join(r["name"] for r in ws.list_runs(root)) or "none"
            raise ToolError(404, f'no run "{name}" under runs/ (have: {have})')
        info = ws.describe_run(run_dir, root)
        phase = "sft" if ws.unquote(inputs.get("phase")) == "sft" else "pretrain"
        m = info["metrics"].get(phase) or {}
        return {"outputs": {
            "step": m.get("step") if m.get("step") is not None else -1,
            "train_loss": m.get("train_loss"),
            "val_loss": m.get("val_loss"),
            "val_perplexity": m.get("val_perplexity"),
            "best_val_loss": m.get("best_val_loss"),
            "checkpoints": [c["path"] for c in info["checkpoints"]],
            "eval": info["eval"],
            "judge": info["judge"],
            "generations": read_generations(run_dir / "eval" / "generations.jsonl"),
            "summary": run_summary(info, phase),
        }}

    # -- utility jobs: a tool call waits for them --------------------------------

    def _utility(self, kind: str, title: str, argv: list[str], out_path: Path,
                 timeout: int, params: dict) -> tuple[dict, Any]:
        root = self.require_root()
        rec = self.jobs.submit(kind=kind, title=title, argv=argv, cwd=root, immediate=True,
                               params=params)
        rec = self.jobs.wait(rec["id"], timeout)
        if rec["status"] not in TERMINAL:
            raise ToolError(504, f"{kind} is still running after {timeout}s (job {rec['id']}); "
                                 f"read it with Lloom Job Status")
        if rec["status"] != "succeeded":
            # The script's last line says why (a sys.exit message, or an exception's own
            # line); the broker cuts a module's refusal short, so send that and no more.
            lines = [line.strip() for line in self.jobs.tail(rec["id"], 20).splitlines()
                     if line.strip()]
            reason = lines[-1] if lines else rec.get("error") or "no output"
            raise ToolError(500, f"{kind} failed (job {rec['id']}): {reason[:300]}")
        try:
            return rec, json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ToolError(500, f"{kind} wrote no readable result (job {rec['id']}): {exc}") from None

    def tool_generate(self, inputs: dict) -> dict:
        root = self.require_root()
        if not (root / "scripts" / "generate.py").is_file():
            raise ToolError(409, "this workspace has no scripts/generate.py")
        prompts = []
        if isinstance(inputs.get("prompt"), str) and inputs["prompt"].strip():
            prompts.append(inputs["prompt"])
        prompts += parse_list(inputs.get("prompts"))
        if not prompts:
            raise ToolError(400, "nothing to generate from: give a prompt or prompts")
        if len(prompts) > 500:
            raise ToolError(400, f"{len(prompts)} prompts is too many for one call (at most 500)")
        checkpoint = ws.unquote(inputs.get("checkpoint"))
        if checkpoint:
            try:
                path = ws.workspace_file(root, checkpoint, "checkpoint")
            except ValueError as exc:
                raise ToolError(400, str(exc)) from None
            if not path.is_file():
                raise ToolError(404, f'checkpoint "{checkpoint}" does not exist in the workspace')
            ckpt = ws.rel(path, root)
        else:
            run_name = self._run_name(inputs.get("run_name"))
            ckpt = ws.preferred_checkpoint(root / "runs" / run_name, root)
            if not ckpt:
                raise ToolError(409, f'run "{run_name}" has no finished checkpoint yet')
        device = ws.unquote(inputs.get("device")) or "auto"
        if device not in ("auto", "cpu", "cuda"):
            raise ToolError(400, f'device "{device}" is not auto, cpu or cuda')
        src, out = self._work(".prompts.json"), self._work(".out.json")
        src.write_text(json.dumps(prompts), encoding="utf-8")
        argv = [self.python, "scripts/generate.py", "--checkpoint", ckpt,
                "--prompts_file", str(src), "--out", str(out), "--device", device,
                "--max_new_tokens", str(clamp_int(inputs.get("max_new_tokens"), 1, 4096, 150)),
                "--temperature", str(max(0.0, as_float(inputs.get("temperature"), 0.7))),
                "--top_p", str(min(1.0, max(0.0, as_float(inputs.get("top_p"), 0.9)))),
                "--top_k", str(clamp_int(inputs.get("top_k"), 0, 100000, 0)),
                "--min_p", str(min(1.0, max(0.0, as_float(inputs.get("min_p"), 0.05)))),
                "--repetition_penalty",
                str(max(1.0, as_float(inputs.get("repetition_penalty"), 1.2)))]
        if as_bool(inputs.get("chat"), True):
            argv.append("--chat")
        seed = clamp_int(inputs.get("seed"), -1, 2**31 - 1, -1)
        if seed >= 0:
            argv += ["--seed", str(seed)]
        timeout = clamp_int(inputs.get("timeout_seconds"), 10, MAX_WAIT, 240)
        try:
            short = ckpt.replace("runs/", "", 1).replace("/checkpoints/", "/", 1)
            _, payload = self._utility("generate", f"generate / {short}", argv, out, timeout,
                                       {"checkpoint": ckpt, "prompts": len(prompts)})
        finally:
            src.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        results = [{"prompt": r.get("prompt", ""), "completion": r.get("completion", ""),
                    "n_tokens": r.get("n_tokens", 0)} for r in payload.get("results", [])]
        texts = [r["completion"] for r in results]
        return {"outputs": {"text": texts[0] if texts else "", "texts": texts,
                            "results": results, "checkpoint": payload.get("checkpoint", ckpt)}}

    # -- judging: Lloom builds the request and reads the answer; HollowDeck's model
    #    nodes make the call (see grading.py). No model, provider or URL lives here.

    def tool_judge_request(self, inputs: dict) -> dict:
        try:
            items = grading.normalize_items(inputs.get("items"))
            single = inputs.get("response")
            if isinstance(single, str) and single.strip():
                items.append({"prompt": str(inputs.get("prompt") or ""), "response": single,
                              "reference": str(inputs.get("reference") or "")})
            items = items[:clamp_int(inputs.get("max_items"), 1, grading.MAX_ITEMS, 50)]
            rubric = inputs.get("rubric") if isinstance(inputs.get("rubric"), str) else ""
            request = grading.build_request(items, rubric or self._workspace_rubric(),
                                            clamp_int(inputs.get("max_score"), 1, 100, 10))
        except grading.GradingError as exc:
            raise ToolError(400, str(exc)) from None
        return {"outputs": request}

    def _workspace_rubric(self) -> str:
        """The rubric in the workspace's config/judge_config.yaml, if it has one."""
        if self.root is None:
            return ""
        try:
            config = ws.load_yaml(self.root / "config" / "judge_config.yaml") or {}
        except Exception:
            return ""
        rubric = config.get("rubric")
        return rubric if isinstance(rubric, str) else ""

    def tool_judge_scores(self, inputs: dict) -> dict:
        max_score = clamp_int(inputs.get("max_score"), 1, 100, 10)
        threshold = as_float(inputs.get("pass_threshold"), 7.0)
        threshold = None if threshold < 0 else threshold
        try:
            items = grading.normalize_items(inputs.get("items"))
            if not items:
                raise grading.GradingError("items is empty: wire Lloom Judge Request's items")
            verdicts = grading.parse_verdicts(inputs.get("verdicts"))
        except grading.GradingError as exc:
            raise ToolError(400, str(exc)) from None
        result = grading.score(items, verdicts, max_score=max_score, pass_threshold=threshold,
                               provider=ws.unquote(inputs.get("provider")),
                               model=ws.unquote(inputs.get("model")))
        summary = result["summary"]
        saved = ""
        run_name = ws.unquote(inputs.get("run_name"))
        if run_name:
            root = self.require_root()
            out_dir = root / "runs" / self._run_name(run_name) / "eval"
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(out_dir / "judgements.jsonl", "w", encoding="utf-8") as f:
                for row in result["verdicts"]:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            record = dict(summary, input="a HollowDeck graph",
                          verdicts=ws.rel(out_dir / "judgements.jsonl", root))
            temp = out_dir / "judge_results.json.tmp"
            temp.write_text(json.dumps(record, indent=2), encoding="utf-8")
            temp.replace(out_dir / "judge_results.json")
            saved = ws.rel(out_dir / "judge_results.json", root)
            self.core.log("info", "lloom.judged", f"judged {run_name}: {judge_summary(summary)}",
                          run_name=run_name, mean_score=summary["mean_score"],
                          n_scored=summary["n_scored"], model=summary["model"])
            self.sync_async()
        return {"outputs": {
            "score": summary["mean_score"],
            "pass_rate": summary["pass_rate"],
            "scores": [row["score"] for row in result["verdicts"]],
            "verdicts": result["verdicts"],
            "summary": judge_summary(summary),
            "saved": saved,
        }}

    def tool_add_sft_data(self, inputs: dict) -> dict:
        root = self.require_root()
        try:
            dataset = ws.safe_name(inputs.get("dataset") or "orchestrator", "dataset")
        except ValueError as exc:
            raise ToolError(400, str(exc)) from None
        dataset = dataset[:-6] if dataset.endswith(".jsonl") else dataset
        if dataset in SPECIAL_EVAL_FILES:
            raise ToolError(400, f"{dataset}.jsonl is an evaluation file with its own format; "
                                 f"pick another dataset name")
        split = "test" if ws.unquote(inputs.get("split")) == "test" else "train"
        mode = "replace" if ws.unquote(inputs.get("mode")) == "replace" else "append"
        if mode == "replace" and not self.allow_replace:
            raise ToolError(403, "replace is off: turn on this module's allow_replace_data "
                                 "setting to let a graph overwrite a dataset")
        data_cfg = self._data_config(root)
        folder = data_cfg.get("test_dir" if split == "test" else "sft_dir") or \
            ("data/test" if split == "test" else "data/sft")
        try:
            target = ws.workspace_file(root, f"{folder}/{dataset}.jsonl", "dataset")
        except ValueError as exc:
            raise ToolError(400, str(exc)) from None
        rows = parse_items(inputs.get("pairs"))
        if isinstance(inputs.get("response"), str) and inputs["response"].strip():
            rows.append({"prompt": inputs.get("prompt") or "", "response": inputs["response"]})
        pairs, skipped = [], 0
        for row in rows:
            prompt, response = _first(row, _PROMPT_KEYS), _first(row, _RESPONSE_KEYS)
            if prompt.strip() and response.strip():
                pairs.append({"prompt": prompt, "response": response})
            else:
                skipped += 1
        if not pairs:
            raise ToolError(400, f"no usable pairs: every item needs a prompt and a response "
                                 f"({skipped} skipped)")
        if len(pairs) > 20000:
            raise ToolError(400, f"{len(pairs)} pairs is too many for one call (at most 20000)")
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pairs)
        if mode == "replace":
            temp = target.with_suffix(".jsonl.tmp")
            temp.write_text(lines, encoding="utf-8")
            temp.replace(target)
        else:
            needs_newline = target.is_file() and target.stat().st_size > 0 and \
                not target.read_bytes().endswith(b"\n")
            with open(target, "a", encoding="utf-8", newline="\n") as f:
                if needs_newline:
                    f.write("\n")
                f.write(lines)
        total = sum(1 for line in target.read_text(encoding="utf-8").splitlines() if line.strip())
        path = ws.rel(target, root)
        self.core.log("info", "lloom.sft_data_added", f"{mode} {len(pairs)} pair(s) to {path}",
                      path=path, added=len(pairs), total=total, mode=mode)
        return {"outputs": {"path": path, "added": len(pairs), "skipped": skipped,
                            "total": total}}

    def tool_sync_library(self, inputs: dict) -> dict:
        self.require_root()
        result = self.sync()
        return {"outputs": {"created": len(result["created"]), "updated": len(result["updated"]),
                            "removed": len(result["removed"]), "assets": result["assets"],
                            "summary": result["summary"]}}

    # -- the library ---------------------------------------------------------------

    def inventory(self) -> dict:
        root = self.require_root()
        return ws.inventory(root)

    def sync(self) -> dict:
        root = self.require_root()
        with self._sync_lock:
            inv = ws.inventory(root)
            result = library.sync_assets(self.store, self.asset_cls, inv, self.version)
            declaration = library.build_tools_file(inv)
            wrote = library.write_tools_file(self.tools_path, declaration)
            result["nodes"] = [t["id"] for t in declaration["tools"]]
            result["nodes_dropped"] = declaration["dropped"]
            result["tools_file_written"] = wrote
            result["summary"] = (
                f"{len(result['assets'])} assets ({len(result['created'])} new, "
                f"{len(result['updated'])} changed, {len(result['removed'])} removed); "
                f"{len(result['nodes'])} pipeline node(s)")
            self.last_sync = result
        if result["created"] or result["updated"] or result["removed"] or wrote:
            self.core.log("info", "lloom.library_synced", result["summary"],
                          created=len(result["created"]), updated=len(result["updated"]),
                          removed=len(result["removed"]), nodes=len(result["nodes"]))
        return result

    def sync_async(self) -> None:
        if self.root is None:
            return

        def run() -> None:
            try:
                self.sync()
            except Exception as exc:
                self.core.log("warning", "lloom.library_sync_failed",
                              f"library sync failed: {type(exc).__name__}: {exc}")

        threading.Thread(target=run, name="lloom-sync", daemon=True).start()

    # -- follow-ups when a job ends --------------------------------------------------

    def _job_finished(self, rec: dict) -> None:
        status = rec["status"]
        level = {"succeeded": "info", "failed": "error"}.get(status, "warning")
        seconds = round((rec.get("finished_at") or 0) - (rec.get("started_at") or
                                                         rec.get("finished_at") or 0), 1)
        self.core.log(level, "lloom.job_finished", f"{rec['title']} {status}", job=rec["id"],
                      kind=rec["kind"], run_name=rec.get("run_name"), status=status,
                      exit_code=rec.get("exit_code"), seconds=seconds)
        if rec["kind"] in ("pipeline", "stage"):
            if self.report_jobs:
                severity = {"succeeded": "success", "failed": "error"}.get(status, "warning")
                self.core.report(severity, f"Lloom: {rec['title']} {status} "
                                           f"after {format_duration(seconds)}",
                                 rec.get("error") or None)
            self.sync_async()
        graph = rec.get("on_complete_graph")
        if not graph:
            return
        if status != "succeeded":
            self.jobs.update(rec["id"], on_complete={"graph": graph, "status": "skipped",
                                                     "reason": f"the job {status}"})
            return
        threading.Thread(target=self._run_follow_up, args=(rec, graph),
                         name="lloom-follow-up", daemon=True).start()

    def _run_follow_up(self, rec: dict, graph: str) -> None:
        with self.jobs.holding():
            started = time.time()
            self.jobs.update(rec["id"], on_complete={"graph": graph, "status": "running",
                                                     "started_at": started})
            result = self.core.run_graph(graph, trigger="lloom")
            outcome = {"graph": graph, "status": result.get("status", "failed"),
                       "run_id": result.get("id"), "run_dir": result.get("run_dir"),
                       "error": result.get("error"), "started_at": started,
                       "finished_at": time.time()}
            self.jobs.update(rec["id"], on_complete=outcome)
            ok = outcome["status"] == "finished"
            self.core.log("info" if ok else "warning", "lloom.follow_up_graph",
                          f"graph {graph} after {rec['title']}: {outcome['status']}",
                          job=rec["id"], graph=graph, run=outcome["run_id"],
                          status=outcome["status"])

    # -- the interpreter check -------------------------------------------------------

    def doctor(self, refresh: bool = False) -> dict:
        cache = self.data_dir / "doctor.json"
        if not refresh:
            if self._doctor is not None:
                return self._doctor
            cached = ws.read_json(cache)
            if isinstance(cached, dict) and cached.get("python_path") == self.python:
                self._doctor = cached
                return cached
            return {"checked": False, "python_path": self.python}
        env = dict(self.env)
        env.pop("HDECK_MODULE_SECRET", None)
        if self.root is not None:
            existing = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(self.root) + (os.pathsep + existing if existing else "")
        result: dict = {"checked": True, "python_path": self.python, "checked_at": time.time()}
        try:
            done = subprocess.run([self.python, "-c", DOCTOR_CODE], capture_output=True,
                                  text=True, timeout=120, env=env,
                                  cwd=str(self.root) if self.root else None,
                                  **(self.proc.no_window() if self.proc else {}))
            if done.returncode != 0:
                result["problem"] = (done.stderr or done.stdout).strip()[-600:] or \
                    f"exited with code {done.returncode}"
            else:
                result.update(json.loads(done.stdout.strip().splitlines()[-1]))
        except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
            result["problem"] = f"{type(exc).__name__}: {exc}"
        packages = result.get("packages") or {}
        missing = [p for p in REQUIRED_PACKAGES if not packages.get(p)]
        if "problem" not in result and missing:
            result["problem"] = (f"{self.python} is missing {', '.join(missing)}; set this "
                                 f"module's python setting to the interpreter you train with")
        elif "problem" not in result and not result.get("lloom"):
            result["problem"] = f"lloom does not import: {result.get('lloom_problem', '')}"
        result["ok"] = "problem" not in result
        tmp = cache.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
        tmp.replace(cache)
        self._doctor = result
        return result

    def status(self) -> dict:
        return {
            "module": self.module_id,
            "version": self.version,
            "workspace": {"root": str(self.root) if self.root else None,
                          "source": self.root_source, "problem": self.root_problem or None},
            "python": {"path": self.python, "source": self.python_source,
                       "problem": self.python_problem or None},
            "doctor": self.doctor(),
            "settings": {"workspace": self.settings.get("workspace"),
                         "python": self.settings.get("python"),
                         "max_concurrent_jobs": self.max_concurrent,
                         "allow_replace_data": self.allow_replace,
                         "report_jobs": self.report_jobs},
            "core": {"connected": self.core.available},
            "jobs": {"active": len(self.jobs.active()), "hold": self.jobs.hold_reason()},
            "library": {k: v for k, v in (self.last_sync or {}).items()
                        if k in ("summary", "synced_at", "nodes", "nodes_dropped", "skipped",
                                 "broken")} or None,
        }


def read_generations(path: Path, limit: int = 200) -> list:
    """What evaluate.py generated for the run ({question, reference, generated} rows),
    ready for Lloom Judge Request; empty when the run has not been evaluated."""
    rows: list = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
                if len(rows) >= limit:
                    break
    except OSError:
        return []
    return rows


# -- text for a model or a person to read ----------------------------------------------

def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds or 0))
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _fmt(value: Any, places: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{places}f}" if isinstance(value, float) else str(value)


def run_summary(info: dict, phase: str = "pretrain") -> str:
    lines = [f"run {info['name']}"]
    for name in ("pretrain", "sft"):
        m = (info.get("metrics") or {}).get(name)
        if not m:
            continue
        marker = " (selected)" if name == phase else ""
        lines.append(f"{name}{marker}: step {m.get('step')}, train loss {_fmt(m.get('train_loss'))}, "
                     f"val loss {_fmt(m.get('val_loss'))} (best {_fmt(m.get('best_val_loss'))})"
                     + (f", val perplexity {_fmt(m.get('val_perplexity'), 2)}"
                        if m.get("val_perplexity") is not None else ""))
    if info.get("checkpoints"):
        lines.append("checkpoints: " + ", ".join(
            f"{c['stage']}/{c['file']} ({c['size_mb']:.0f} MB)" for c in info["checkpoints"]))
    ev = info.get("eval")
    if isinstance(ev, dict):
        keys = [k for k in ev if k.startswith(("perplexity/", "retrieval/", "clustering/"))]
        if keys:
            lines.append("eval: " + ", ".join(f"{k} {_fmt(ev[k], 3)}" for k in keys[:8]))
    judge = info.get("judge")
    if isinstance(judge, dict):
        lines.append(judge_summary(judge))
    return "\n".join(lines)


def judge_summary(summary: dict) -> str:
    if not summary:
        return "judge: no result"
    model = summary.get("model") or ""
    provider = summary.get("provider") or ""
    # A HollowDeck model string already carries its provider ("ollama:qwen3.5:9b").
    grader = model if (not provider or model.startswith(provider + ":")) else f"{provider}:{model}"
    text = (f"judge ({grader or 'unnamed model'}): mean "
            f"{_fmt(summary.get('mean_score'), 2)}/{summary.get('max_score')} over "
            f"{summary.get('n_scored')} of {summary.get('n_items')} item(s)")
    if summary.get("pass_rate") is not None:
        text += f", pass rate {summary['pass_rate']:.0%} at {summary.get('pass_threshold')}"
    if summary.get("n_errors"):
        text += f", {summary['n_errors']} error(s)"
    return text
