"""Background jobs: one Lloom script run as a child process this module keeps track of.

Training outlives any one request -- a tool call may wait about five minutes, a
pretraining run takes hours -- so every piece of Lloom work is a **job**: started,
recorded, watched and answered for later. The rules it keeps, each from INTEROP.md:

* **Anything that matters is on disk** (§6). A job is ``<data dir>/jobs/<id>/job.json``
  plus ``output.log``, written as it changes, so a module that is stopped and started
  again still knows every job it ran.
* **Children cannot outlive the module** (§13, *Transport*). On Windows every job's
  process tree sits in its own job object with KILL_ON_JOB_CLOSE (the vendored
  ``ChildJail``): the module dying closes the handle and the tree goes with it, and a
  cancel closes it on purpose. On POSIX a job gets its own process group, signalled
  as a whole on cancel and at exit.
* **A job that was running when the module stopped is ``interrupted``**, never shown as
  running forever: its processes died with the module, so on start any job left
  ``queued`` or ``running`` by a previous process is marked so, with the reason.
* **The module holds itself alive only for work in flight** (§6): the lifecycle hook
  asks :meth:`JobManager.hold_reason`, which is non-empty exactly while a job is queued
  or running or a follow-up (a graph it triggered) is still going.

Jobs queue behind a concurrency limit (``max_concurrent``, default 1 -- one GPU), except
**immediate** jobs (generate, judge): short utility work a tool call is waiting on,
which must not sit behind a three-hour training run.
"""

from __future__ import annotations

import copy
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

ACTIVE = ("queued", "running")
TERMINAL = ("succeeded", "failed", "cancelled", "interrupted")

_STAGE_START = re.compile(r"^\[([A-Za-z0-9_.\-]+)\] \$ ")
_STAGE_SKIP = re.compile(r"^\[([A-Za-z0-9_.\-]+)\] skipped")
_TOTAL = re.compile(r"^(?:training|sft): (\d+) steps")
_STEP = re.compile(r"^step\s+(\d+) loss ([-+0-9.eE]+|nan|inf)")
_VAL = re.compile(r"^\s+val ([-+0-9.eE]+|nan|inf)(?: ppl ([-+0-9.eE]+|nan|inf))?")

IS_WINDOWS = os.name == "nt"
SAVE_EVERY = 2.0  # seconds between progress-only writes of job.json


def new_job_id() -> str:
    """Sortable by creation time, unique enough for one machine's job list."""
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)


def _num(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


class _Live:
    """What only exists while a job's process does."""

    def __init__(self, process: subprocess.Popen, jail: Any, logf: Any, log_path: Path):
        self.process = process
        self.jail = jail
        self.logf = logf
        self.log_path = log_path
        self.read_pos = 0
        self.partial = ""
        self.kill_deadline: float | None = None
        self.last_save = 0.0


class JobManager:
    def __init__(self, data_dir: Path | str, *, proc: Any = None, max_concurrent: int = 1,
                 keep: int = 100, poll_interval: float = 0.5,
                 on_finish: list[Callable[[dict], None]] | None = None,
                 base_env: dict | None = None):
        self.root = Path(data_dir) / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.proc = proc
        self.max_concurrent = max(1, int(max_concurrent or 1))
        self.keep = max(10, int(keep or 100))
        self.poll_interval = poll_interval
        self.on_finish: list[Callable[[dict], None]] = list(on_finish or [])
        self.base_env = base_env
        self._cond = threading.Condition(threading.RLock())
        self._records: dict[str, dict] = {}
        self._live: dict[str, _Live] = {}
        self._env: dict[str, dict] = {}
        self._followups = 0
        self._to_fire: list[dict] = []  # ended jobs whose follow-ups run once the lock is free
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.recovered = self._recover()

    # -- persistence ---------------------------------------------------------

    def _dir(self, job_id: str) -> Path:
        return self.root / job_id

    def _save(self, rec: dict) -> None:
        job_dir = self._dir(rec["id"])
        job_dir.mkdir(parents=True, exist_ok=True)
        target = job_dir / "job.json"
        temp = target.with_suffix(".json.tmp")
        temp.write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(target)

    def _recover(self) -> list[str]:
        """Load every job on disk; any left active by a previous process is interrupted."""
        recovered = []
        for job_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            try:
                rec = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rec, dict) or rec.get("id") != job_dir.name:
                continue
            if rec.get("status") in ACTIVE:
                was = rec["status"]
                rec.update(status="interrupted", finished_at=time.time(),
                           error=(f"the module stopped while this job was {was}; its "
                                  "processes stopped with it"))
                for stage in rec.get("stages") or []:
                    if stage.get("status") == "running":
                        stage["status"] = "interrupted"
                self._save(rec)
                recovered.append(rec["id"])
            self._records[rec["id"]] = rec
        return recovered

    def _prune(self) -> None:
        ended = sorted((r for r in self._records.values() if r.get("status") in TERMINAL),
                       key=lambda r: r.get("created_at") or 0, reverse=True)
        for rec in ended[self.keep:]:
            shutil.rmtree(self._dir(rec["id"]), ignore_errors=True)
            self._records.pop(rec["id"], None)

    # -- the thread ----------------------------------------------------------

    def start(self) -> "JobManager":
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="lloom-jobs", daemon=True)
            self._thread.start()
        return self

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_interval):
            try:
                self.tick()
            except Exception as exc:  # pragma: no cover - the watcher must not die
                print(f"[lloom] job watcher error: {type(exc).__name__}: {exc}", flush=True)

    def tick(self) -> None:
        """One pass: read new output, notice ended processes, start queued jobs."""
        with self._cond:
            now = time.monotonic()
            for job_id, live in list(self._live.items()):
                rec = self._records[job_id]
                changed = self._scan_log(rec, live)
                code = live.process.poll()
                if code is None:
                    if live.kill_deadline is not None and now >= live.kill_deadline:
                        self._signal_group(live, hard=True)
                        live.kill_deadline = None
                    if changed == "stage" or (changed and now - live.last_save >= SAVE_EVERY):
                        live.last_save = now
                        self._save(rec)
                    continue
                self._scan_log(rec, live, final=True)
                if rec.get("cancel_requested"):
                    status = "cancelled"
                else:
                    status = "succeeded" if code == 0 else "failed"
                self._close(job_id)
                self._finish(rec, status, code)
            self._pump()
        self._drain()

    def _drain(self) -> None:
        """Run the follow-ups of every job that ended, outside the lock."""
        with self._cond:
            pending, self._to_fire = self._to_fire, []
        for rec in pending:
            self._fire(rec)

    def _fire(self, rec: dict) -> None:
        for callback in self.on_finish:
            try:
                callback(rec)
            except Exception as exc:  # a follow-up never breaks the watcher
                print(f"[lloom] job {rec['id']} follow-up failed: {type(exc).__name__}: {exc}",
                      flush=True)

    # -- submitting and starting ---------------------------------------------

    def submit(self, *, kind: str, title: str, argv: list[str], cwd: Path | str,
               run_name: str = "", params: dict | None = None, env: dict | None = None,
               immediate: bool = False, on_complete_graph: str = "",
               stage: str = "") -> dict:
        rec = {
            "id": new_job_id(), "kind": kind, "title": title,
            "argv": [str(a) for a in argv], "cwd": str(cwd), "run_name": run_name,
            "params": params or {}, "status": "queued", "created_at": time.time(),
            "started_at": None, "finished_at": None, "exit_code": None, "pid": None,
            "stage": stage, "stages": [], "progress": None, "error": None,
            "immediate": bool(immediate), "on_complete_graph": on_complete_graph or "",
            "on_complete": None, "log": "output.log",
        }
        with self._cond:
            self._records[rec["id"]] = rec
            self._env[rec["id"]] = dict(env or {})
            self._save(rec)
            if immediate:
                self._spawn(rec)
            else:
                self._pump()
            self._prune()
            self._cond.notify_all()
            result = copy.deepcopy(rec)
        self._drain()
        return result

    def _pump(self) -> None:
        running = sum(1 for r in self._records.values()
                      if r["status"] == "running" and not r.get("immediate"))
        queued = sorted((r for r in self._records.values() if r["status"] == "queued"),
                        key=lambda r: r["created_at"])
        for rec in queued:
            if running >= self.max_concurrent:
                break
            self._spawn(rec)
            if rec["status"] == "running":
                running += 1

    def _child_env(self, rec: dict) -> dict:
        env = dict(self.base_env if self.base_env is not None else os.environ)
        # guard.secret_from_env() already took it out of this process's environment;
        # a job must never be able to read the host's per-spawn secret.
        env.pop("HDECK_MODULE_SECRET", None)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["LLOOM_JOB_ID"] = rec["id"]
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = rec["cwd"] + (os.pathsep + existing if existing else "")
        env.update(self._env.pop(rec["id"], {}))
        return env

    def _spawn(self, rec: dict) -> None:
        job_dir = self._dir(rec["id"])
        job_dir.mkdir(parents=True, exist_ok=True)
        log_path = job_dir / "output.log"
        logf = open(log_path, "ab")
        logf.write(f"$ {' '.join(rec['argv'])}\n  (in {rec['cwd']})\n".encode("utf-8"))
        logf.flush()
        kwargs: dict = {}
        if IS_WINDOWS:
            if self.proc is not None:
                kwargs.update(self.proc.no_window())
        else:
            kwargs["start_new_session"] = True
        try:
            process = subprocess.Popen(
                rec["argv"], cwd=rec["cwd"], stdout=logf, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, env=self._child_env(rec), **kwargs)
        except OSError as exc:
            logf.write(f"could not start: {exc}\n".encode("utf-8"))
            logf.close()
            self._finish(rec, "failed", None, f"could not start {rec['argv'][0]}: {exc}")
            return
        jail = None
        if IS_WINDOWS and self.proc is not None:
            jail = self.proc.ChildJail()
            problem = jail.adopt(process.pid)
            if problem:
                rec["jail_problem"] = problem
                logf.write(f"[lloom] {problem}\n".encode("utf-8"))
                logf.flush()
        self._live[rec["id"]] = _Live(process, jail, logf, log_path)
        rec.update(status="running", started_at=time.time(), pid=process.pid)
        self._save(rec)

    # -- reading the log -----------------------------------------------------

    def _scan_log(self, rec: dict, live: _Live, final: bool = False) -> str:
        """Read what the job wrote since last time; return "stage", "progress" or ""."""
        try:
            with open(live.log_path, "rb") as f:
                f.seek(live.read_pos)
                chunk = f.read(1 << 20)
                live.read_pos = f.tell()
        except OSError:
            return ""
        if not chunk:
            return ""
        text = live.partial + chunk.decode("utf-8", errors="replace").replace("\r\n", "\n")
        lines = text.split("\n")
        live.partial = "" if final else lines.pop()
        changed = ""
        for line in lines:
            kind = self._apply_line(rec, line)
            if kind == "stage" or (kind and not changed):
                changed = kind
        return changed

    def _apply_line(self, rec: dict, line: str) -> str:
        stages = rec.setdefault("stages", [])
        match = _STAGE_START.match(line)
        if match:
            for stage in stages:
                if stage["status"] == "running":
                    stage["status"] = "done"
                    stage["finished_at"] = time.time()
            stages.append({"name": match.group(1), "status": "running",
                           "started_at": time.time(), "finished_at": None})
            rec["stage"] = match.group(1)
            rec["progress"] = None
            return "stage"
        match = _STAGE_SKIP.match(line)
        if match:
            stages.append({"name": match.group(1), "status": "skipped",
                           "started_at": None, "finished_at": time.time()})
            return "stage"
        progress = rec.get("progress") or {}
        match = _TOTAL.match(line)
        if match:
            progress["total_steps"] = int(match.group(1))
        else:
            match = _STEP.match(line)
            if match:
                progress["step"] = int(match.group(1))
                progress["loss"] = _num(match.group(2))
            else:
                match = _VAL.match(line)
                if not match:
                    return ""
                progress["val_loss"] = _num(match.group(1))
                if match.group(2):
                    progress["val_perplexity"] = _num(match.group(2))
        total, step = progress.get("total_steps"), progress.get("step")
        if total and step is not None:
            progress["fraction"] = round(min(step / total, 1.0), 4)
        rec["progress"] = progress
        return "progress"

    # -- ending --------------------------------------------------------------

    def _close(self, job_id: str) -> None:
        live = self._live.pop(job_id, None)
        if live is None:
            return
        try:
            live.logf.close()
        except OSError:
            pass
        if live.jail is not None:
            live.jail.release()

    def _finish(self, rec: dict, status: str, code: int | None, error: str | None = None) -> None:
        rec.update(status=status, exit_code=code, finished_at=time.time())
        if error:
            rec["error"] = error
        elif status == "failed" and not rec.get("error"):
            rec["error"] = f"exited with code {code}"
        final = {"succeeded": "done", "cancelled": "cancelled"}.get(status, "failed")
        for stage in rec.get("stages") or []:
            if stage["status"] == "running":
                stage["status"] = final
                stage["finished_at"] = rec["finished_at"]
        self._save(rec)
        self._to_fire.append(copy.deepcopy(rec))
        self._cond.notify_all()

    # -- cancelling ----------------------------------------------------------

    def cancel(self, job_id: str) -> tuple[dict, bool]:
        """``(record, whether this call stopped it)``. Raises KeyError for no such job."""
        with self._cond:
            rec = self._records[job_id]
            if rec["status"] == "queued":
                self._finish(rec, "cancelled", None, "cancelled before it started")
                stopped = True
            elif rec["status"] == "running" and not rec.get("cancel_requested"):
                rec["cancel_requested"] = True
                self._save(rec)
                live = self._live.get(job_id)
                if live is not None:
                    self._kill(live)
                stopped = True
            else:
                stopped = False
            result = copy.deepcopy(rec)
        self._drain()
        return result, stopped

    def _kill(self, live: _Live) -> None:
        if IS_WINDOWS:
            if live.jail is not None and live.jail.handle is not None:
                live.jail.release()  # terminates the job's whole process tree
                return
            subprocess.run(["taskkill", "/PID", str(live.process.pid), "/T", "/F"],
                           capture_output=True, check=False,
                           **(self.proc.no_window() if self.proc is not None else {}))
            return
        self._signal_group(live, hard=False)
        live.kill_deadline = time.monotonic() + 10.0

    @staticmethod
    def _signal_group(live: _Live, hard: bool) -> None:
        try:
            os.killpg(live.process.pid, signal.SIGKILL if hard else signal.SIGTERM)
        except (ProcessLookupError, PermissionError, AttributeError, OSError):
            try:
                live.process.kill() if hard else live.process.terminate()
            except OSError:
                pass

    def shutdown(self) -> None:
        """Stop watching and stop every job's processes. For exit and for tests."""
        self._stop.set()
        with self._cond:
            for job_id, live in list(self._live.items()):
                rec = self._records[job_id]
                rec["cancel_requested"] = True
                self._kill(live)
                if not IS_WINDOWS:
                    self._signal_group(live, hard=True)
                try:
                    live.process.wait(timeout=10)
                except subprocess.TimeoutExpired:  # pragma: no cover
                    live.process.kill()
                self._scan_log(rec, live, final=True)
                self._close(job_id)
                self._finish(rec, "cancelled", live.process.returncode,
                             "the module shut down while this job ran")
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    # -- reading -------------------------------------------------------------

    def get(self, job_id: str) -> dict | None:
        with self._cond:
            rec = self._records.get(job_id)
            return copy.deepcopy(rec) if rec else None

    def list(self, limit: int = 100) -> list[dict]:
        with self._cond:
            recs = sorted(self._records.values(), key=lambda r: r.get("created_at") or 0,
                          reverse=True)
            return [copy.deepcopy(r) for r in recs[:limit]]

    def latest(self) -> dict | None:
        items = self.list(limit=1)
        return items[0] if items else None

    def active(self) -> list[dict]:
        with self._cond:
            return [copy.deepcopy(r) for r in self._records.values() if r["status"] in ACTIVE]

    def update(self, job_id: str, **fields: Any) -> None:
        """Record something about a job from outside the watcher (a follow-up's result)."""
        with self._cond:
            rec = self._records.get(job_id)
            if rec is not None:
                rec.update(fields)
                self._save(rec)

    def wait(self, job_id: str, timeout: float) -> dict:
        """The record once the job has ended, or as it stands after ``timeout`` seconds."""
        deadline = time.monotonic() + max(0.0, float(timeout or 0))
        with self._cond:
            while True:
                rec = self._records.get(job_id)
                if rec is None:
                    raise KeyError(job_id)
                remaining = deadline - time.monotonic()
                if rec["status"] in TERMINAL or remaining <= 0:
                    return copy.deepcopy(rec)
                self._cond.wait(min(remaining, 1.0))

    def log_path(self, job_id: str) -> Path:
        return self._dir(job_id) / "output.log"

    def read_log(self, job_id: str, offset: int = 0, limit: int = 256 * 1024) -> dict:
        path = self.log_path(job_id)
        size = path.stat().st_size if path.is_file() else 0
        offset = max(0, min(int(offset or 0), size))
        data = b""
        if size > offset:
            with open(path, "rb") as f:
                f.seek(offset)
                data = f.read(max(1, int(limit)))
        return {"text": data.decode("utf-8", errors="replace"), "offset": offset + len(data),
                "size": size}

    def tail(self, job_id: str, lines: int = 40) -> str:
        if lines <= 0:
            return ""
        path = self.log_path(job_id)
        if not path.is_file():
            return ""
        size = path.stat().st_size
        with open(path, "rb") as f:
            f.seek(max(0, size - 64 * 1024))
            text = f.read().decode("utf-8", errors="replace").replace("\r\n", "\n")
        return "\n".join(text.rstrip("\n").split("\n")[-lines:])

    # -- staying alive -------------------------------------------------------

    @contextmanager
    def holding(self) -> Iterator[None]:
        """Hold the module alive while a follow-up (a graph it triggered) runs."""
        with self._cond:
            self._followups += 1
        try:
            yield
        finally:
            with self._cond:
                self._followups -= 1

    def hold_reason(self) -> str:
        with self._cond:
            running = sum(1 for r in self._records.values() if r["status"] == "running")
            queued = sum(1 for r in self._records.values() if r["status"] == "queued")
            follow = self._followups
        parts = []
        if running:
            parts.append(f"{running} job{'s' if running != 1 else ''} running")
        if queued:
            parts.append(f"{queued} queued")
        if follow:
            parts.append(f"{follow} follow-up graph{'s' if follow != 1 else ''} running")
        return ", ".join(parts)


def summarize(rec: dict, tail: str = "") -> dict:
    """The fields a tool answers with, from a job record."""
    now = time.time()
    started = rec.get("started_at")
    ended = rec.get("finished_at")
    elapsed = (ended or now) - started if started else 0.0
    progress = rec.get("progress") or {}
    return {
        "job_id": rec["id"],
        "status": rec["status"],
        "done": rec["status"] in TERMINAL,
        "ok": rec["status"] == "succeeded",
        "exit_code": rec["exit_code"] if rec.get("exit_code") is not None else -1,
        "stage": rec.get("stage") or "",
        "run_name": rec.get("run_name") or "",
        "progress": progress.get("fraction"),
        "elapsed_seconds": round(max(elapsed, 0.0), 1),
        "log_tail": tail,
    }
