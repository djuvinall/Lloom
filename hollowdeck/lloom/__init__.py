"""Lloom as a HollowDeck module: train, finetune, evaluate and judge from graphs.

``__main__.py`` builds the handshake context and serves ``create_app(ctx)`` behind the
vendored guard. What this module offers:

* **Tools** (``module.json``), which the Orchestrator shows as ``lloom/<tool>`` nodes
  and any module reaches through the core's broker: start a pipeline or a stage as a
  background job, wait on it, cancel it, read runs and metrics, generate from a
  checkpoint, have Claude or a local model judge outputs, add SFT data, sync the
  Library. Plus one ``lloom/pipeline_<recipe>`` node per recipe the workspace holds,
  declared in the ``tools_file`` this module writes (see ``library.py``).
* **Library assets**: the workspace's recipes, presets, stage scripts, runs and
  checkpoints, served on ``api/assets`` for HollowDeck's Asset Library.
* **A panel** (``static/``): workspace and interpreter status, a launcher, live jobs
  with their logs, runs and their numbers, and the Library.
* **The lifecycle hook** ``GET /lifecycle``, which holds the module alive exactly while
  a job is queued or running -- training must not be reaped by an idle timeout.

Every URL a page or script uses is relative (INTEROP.md §7); every file of the module's
own is found from ``MODULE_DIR`` (§8); state lives under ``ctx.data_dir`` (§6).
"""

from __future__ import annotations

import atexit
import json
from pathlib import Path
from typing import Any

MODULE_DIR = Path(__file__).resolve().parent
STATIC_DIR = MODULE_DIR / "static"
MANIFEST_PATH = MODULE_DIR / "module.json"


def read_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


MODULE_VERSION = read_manifest()["version"]


def create_app(ctx: Any = None, *, start: bool = True) -> Any:
    """The contract's load hook. ``ctx`` is duck-typed and read with ``getattr``.

    ``start=False`` builds the app without starting the job watcher or the first
    library sync -- for tests that drive :class:`LloomService` themselves.
    """
    from fastapi import Body, FastAPI, Query
    from fastapi.responses import FileResponse, JSONResponse, Response
    from fastapi.staticfiles import StaticFiles

    from .core_client import CoreClient
    from .jobs import summarize
    from .service import LloomService, ToolError
    from .vendor import proc
    from .vendor.assets import Asset, AssetStore, mount_asset_api

    module_id = getattr(ctx, "module_id", None) or "lloom"
    module_dir = Path(getattr(ctx, "module_dir", None) or MODULE_DIR)
    # Never the module directory itself: it is packed and hashed, so a write there
    # would break `modules verify` (INTEROP.md §13).
    data_dir = Path(getattr(ctx, "data_dir", None) or (Path.cwd() / "module_data" / module_id))
    settings = dict(getattr(ctx, "settings", None) or {})
    core = CoreClient(getattr(ctx, "core_url", None), module_id)
    store = AssetStore(data_dir, owner=module_id)
    service = LloomService(module_id=module_id, version=MODULE_VERSION, module_dir=module_dir,
                           data_dir=data_dir, settings=settings, core=core, proc=proc,
                           store=store, asset_cls=Asset, env=getattr(ctx, "env", None))

    app = FastAPI(title=module_id, version=MODULE_VERSION)
    app.state.ctx = ctx
    app.state.service = service
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def fail(exc: ToolError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    # -- the contract's routes ----------------------------------------------------

    @app.get("/")
    def panel_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/health")
    def health() -> dict:
        # The host reads only the status; the body keeps `ok` for every other reader.
        return {"ok": True, "module": module_id, "version": MODULE_VERSION,
                "workspace": service.root is not None}

    @app.get("/module.json")
    def module_manifest() -> dict:
        return read_manifest()

    @app.get("/lifecycle")
    def lifecycle() -> dict:
        return service.hold()

    # -- tools: POST tools/<id>, through the core's broker ---------------------------

    @app.post("/tools/{tool_id}")
    def call_tool(tool_id: str, payload: dict = Body(default_factory=dict)) -> Any:
        try:
            return service.call(tool_id, payload)
        except ToolError as exc:
            return fail(exc)

    # -- the panel's API -------------------------------------------------------------

    @app.get("/api/status")
    def api_status() -> dict:
        return service.status()

    @app.post("/api/doctor")
    def api_doctor() -> dict:
        return service.doctor(refresh=True)

    @app.get("/api/inventory")
    def api_inventory() -> Any:
        try:
            return service.inventory()
        except ToolError as exc:
            return fail(exc)

    @app.get("/api/jobs")
    def api_jobs(limit: int = Query(50, ge=1, le=500)) -> dict:
        jobs = service.jobs.list(limit)
        return {"jobs": [dict(summarize(j), title=j["title"], kind=j["kind"],
                              created_at=j["created_at"], started_at=j.get("started_at"),
                              finished_at=j.get("finished_at"), error=j.get("error"),
                              stages=j.get("stages") or [], progress_detail=j.get("progress"),
                              on_complete=j.get("on_complete"), params=j.get("params"))
                         for j in jobs],
                "hold": service.jobs.hold_reason()}

    @app.post("/api/jobs", status_code=201)
    def api_start(payload: dict = Body(default_factory=dict)) -> Any:
        kind = payload.get("kind")
        try:
            if kind == "pipeline":
                rec = service.start_pipeline(payload, source="panel")
            elif kind == "stage":
                rec = service.start_stage(payload, source="panel")
            else:
                raise ToolError(400, 'kind must be "pipeline" or "stage"')
        except ToolError as exc:
            return fail(exc)
        return {"job": rec}

    @app.get("/api/jobs/{job_id}")
    def api_job(job_id: str) -> Any:
        rec = service.jobs.get(job_id)
        if rec is None:
            return fail(ToolError(404, f"no job {job_id!r}"))
        return {"job": rec, "summary": summarize(rec)}

    @app.get("/api/jobs/{job_id}/log")
    def api_job_log(job_id: str, offset: int = Query(0, ge=0),
                    limit: int = Query(262144, ge=1, le=4194304)) -> Any:
        rec = service.jobs.get(job_id)
        if rec is None:
            return fail(ToolError(404, f"no job {job_id!r}"))
        return dict(service.jobs.read_log(job_id, offset, limit), status=rec["status"])

    @app.post("/api/jobs/{job_id}/cancel")
    def api_cancel(job_id: str) -> Any:
        try:
            return service.tool_cancel_job({"job_id": job_id})["outputs"]
        except ToolError as exc:
            return fail(exc)

    @app.get("/api/runs/{run_name}")
    def api_run(run_name: str) -> Any:
        try:
            return service.tool_run_metrics({"run_name": run_name})["outputs"]
        except ToolError as exc:
            return fail(exc)

    @app.post("/api/library/sync")
    def api_sync() -> Any:
        try:
            result = service.sync()
        except ToolError as exc:
            return fail(exc)
        return {k: v for k, v in result.items() if k != "assets"} | {"count": len(result["assets"])}

    # Library assets (INTEROP.md, *Optional: own assets*). Everything a sync writes is
    # derived from the workspace, so the surface's default origin is "ingested"; a
    # person who saves their own asset through POST api/assets can say "authored".
    mount_asset_api(app, store, owner=module_id, origin_default="ingested",
                    log=lambda level, event, message, **fields: core.log(level, event, message,
                                                                         **fields))

    if start:
        service.start()
        atexit.register(service.shutdown)
    return app
