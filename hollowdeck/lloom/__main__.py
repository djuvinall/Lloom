"""Entry point HollowDeck spawns for the ``lloom`` module (``kind: process``).

Also runnable by hand for development::

    python __main__.py 8790        # or HDECK_MODULE_PORT=8790

The load-bearing rules, each from the HollowDeck interop contract (INTEROP.md):

* **Everything resolves relative to this file.** The package beside it and the
  vendored guard are imported by file *location*, never by name. This directory is
  called ``lloom`` -- the same name as the Lloom framework's own Python package -- so
  an ``import lloom`` here could pick up either one depending on how the process was
  started. Loading by location makes that impossible. (This module never imports the
  framework at all: everything Lloom does runs as the workspace's own scripts, in
  child processes, under the workspace's own interpreter.)
* **Loopback only.** ``127.0.0.1`` is written out, not defaulted.
* **The guard goes on before anything else.** ``secret_from_env`` takes the host's
  per-spawn secret *out* of the environment, so no job this module ever starts can
  inherit it.
* **An unusable port is an error, never a fallback.**
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

#: Only for running by hand. Under the host, HDECK_MODULE_PORT is always set.
DEFAULT_PORT = 8790


class EnvContext:
    """The handshake, rebuilt from the environment.

    Deliberately a plain object: nothing hands a process module a context, and it
    imports nothing from the core. ``create_app`` reads it with ``getattr``.

    There is no ``log`` method on purpose. Out of process, logging is a POST to
    ``{core_url}/m/event_log/api/events``, and ``core_url`` is ``None`` when no core
    is listening -- a real state the caller has to notice, not paper over.
    """

    def __init__(self, env: dict | None = None) -> None:
        env = os.environ if env is None else env
        self.module_id = env.get("HDECK_MODULE_ID") or HERE.name
        self.module_dir = Path(env.get("HDECK_MODULE_DIR") or HERE)
        self.mount_path = f"/m/{self.module_id}"
        shared = env.get("HDECK_DATA_DIR")
        self.shared_data_dir = Path(shared) if shared else Path.cwd()
        data = env.get("HDECK_MODULE_DATA_DIR")
        self.data_dir = (
            Path(data) if data else self.shared_data_dir / "module_data" / self.module_id
        )
        self.core_version = (env.get("HDECK_CORE_VERSION") or "").strip() or None
        self.core_bind = (env.get("HDECK_CORE_BIND") or "").strip()
        self.core_url = (env.get("HDECK_CORE_URL") or "").strip() or None
        #: Not in the handshake: the module manager writes these to
        #: <HDECK_DATA_DIR>/module_settings/<id>.json, and a change takes effect the
        #: next time this process starts.
        self.settings = read_settings(self.shared_data_dir, self.module_id)


def read_settings(shared_data_dir: Path, module_id: str) -> dict:
    """The user's settings for this module, or ``{}``. Never raises."""
    path = Path(shared_data_dir) / "module_settings" / f"{module_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _load(name: str, path: Path, package_dir: Path | None = None) -> Any:
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    locations = [str(package_dir)] if package_dir is not None else None
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=locations)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot build an import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_package() -> Any:
    """``__init__.py`` beside this file, by location -- never ``import lloom``."""
    return _load(f"hdeck_module_{HERE.name}", HERE / "__init__.py", package_dir=HERE)


def load_guard() -> Any:
    """``vendor/guard.py``, by location. A byte-identical copy of HollowDeck's."""
    return _load(f"hdeck_guard_{HERE.name}", HERE / "vendor" / "guard.py")


def resolve_port(argv: list | None = None, env: dict | None = None) -> int:
    env = os.environ if env is None else env
    argv = sys.argv if argv is None else argv
    raw = env.get("HDECK_MODULE_PORT") or (argv[1] if len(argv) > 1 else "")
    if not raw:
        return DEFAULT_PORT
    try:
        port = int(raw)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"HDECK_MODULE_PORT/argv port is not an integer: {raw!r}") from exc
    if not 1 <= port <= 65535:
        raise SystemExit(f"port out of range: {port}")
    return port


def main(argv: list | None = None) -> int:
    import uvicorn

    port = resolve_port(argv)
    guard = load_guard()
    # Before the app is built and before any job is spawned: takes the secret out of
    # the environment, so no child process inherits it. See vendor/guard.py.
    secret = guard.secret_from_env()
    ctx = EnvContext()
    app = guard.ModuleGuard(load_package().create_app(ctx), secret, module_id=ctx.module_id)
    # log_level="warning": stdout/stderr go to this module's process.log, and an access
    # line per health poll would grow it for as long as the panel is open.
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
