"""``verify``: what ``hollowdeck modules update-deps`` runs to ask "does this module work?"

Fast, offline and side-effect-free (INTEROP.md, *Packaging*): it binds no port, starts
no job and writes nothing. Exit 0 when the module is fine; non-zero, with the reason on
stderr, when it is not. It checks what this module would be broken without:

* the package imports, by location, and exposes ``create_app``;
* the vendored guard, asset store and process helpers import;
* ``module.json`` parses and every tool declaration passes the core's rules;
* the panel's files exist.

Run it by hand exactly as the host would::

    python selfcheck.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path, *, package: bool = False):
    search = [str(path.parent)] if package else None
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=search)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build an import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    try:
        package = _load("lloom_module_selfcheck", HERE / "__init__.py", package=True)
    except Exception as exc:  # noqa: BLE001 - an import error is the thing to catch
        print(f"lloom: the package does not import: {exc}", file=sys.stderr)
        return 1
    if not callable(getattr(package, "create_app", None)):
        print("lloom: create_app is missing or not callable", file=sys.stderr)
        return 1
    for name in ("guard", "assets", "proc"):
        try:
            _load(f"lloom_selfcheck_vendor_{name}", HERE / "vendor" / f"{name}.py")
        except Exception as exc:  # noqa: BLE001
            print(f"lloom: vendor/{name}.py does not import: {exc}", file=sys.stderr)
            return 1
    try:
        manifest = json.loads((HERE / "module.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"lloom: module.json does not parse: {exc}", file=sys.stderr)
        return 1
    try:
        library = importlib.import_module("lloom_module_selfcheck.library")
    except Exception as exc:  # noqa: BLE001
        print(f"lloom: library.py does not import: {exc}", file=sys.stderr)
        return 1
    problems = library.validate_tools(manifest.get("tools", []))
    if problems:
        print("lloom: module.json tools are invalid: " + "; ".join(problems), file=sys.stderr)
        return 1
    for rel in ("static/index.html", "static/app.js", "static/app.css"):
        if not (HERE / rel).is_file():
            print(f"lloom: {rel} is missing", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
