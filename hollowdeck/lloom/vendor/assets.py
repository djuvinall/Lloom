"""Assets: saved reusable logic, as a first-class object type (P038).

**One implementation, many owners, and that is the whole point of this file.** An
asset is *a* way logic moves between modules (D1/D2), and every module that wants to
own assets carries a **byte-identical copy** of this file under its own ``vendor/`` --
the same answer ``vendor/semver.py``, ``vendor/logsink.py`` and ``vendor/guard.py``
already give, for the same reason: *a module cannot borrow the core's anything.* Not
its URL, not its ``sys.path``, and not its language. A test compares the bytes
(``tests/test_assets.py``).

The top of this file is **stdlib only**, so a module that serves with Starlette, with
``http.server``, or with nothing at all can hold an :class:`AssetStore`. The one
FastAPI-shaped convenience, :func:`mount_asset_api`, imports FastAPI *inside itself*,
so importing this module never drags a web framework in.

## The shape (D3): a thin envelope over an opaque module payload

An asset record is an **envelope** the core (and any consumer) understands, wrapped
around a **payload** that belongs to the owning module and is **never parsed here**.
The store reads and writes the payload as bytes-of-JSON; it does not know or care what
is in it. Organisation is **tags plus a saving convention** (D3), never a fixed
taxonomy -- different modules have genuinely different asset use-cases, and installing
a new module widens the space again.

The **legible** part of the envelope is a typed **socket interface** in P001's
``SocketSpec`` vocabulary (D4) -- inputs and outputs, each a ``{name, type, ...}``
object whose ``type`` is one of the graph editor's socket type strings (``any``,
``str``, ``int``, ``float``, ``bool``, ``model``, ``bundle``, ``list[...]``). This is
what lets a wiring against an asset be validated *before it runs*. We store the socket
dicts and validate them shallowly (a ``name`` that is an identifier, a non-empty
``type`` string); we do **not** import ``SocketSpec`` -- reusing the *vocabulary* does
not mean importing the *type*, and the core imports nothing from the engine any more
than from a module.

## Ownership and the version stamp

* **Each module owns its own assets (D5).** They live under
  ``HDECK_DATA_DIR/module_data/<owner>/assets/<id>.json`` -- the per-module runtime
  directory D24 placed there, never inside the module's own installed directory (which
  is packed and hashed, so a write there breaks ``modules verify``). The library is a
  *view* over these, not a second store.
* **``origin`` is ``ingested`` or ``authored`` (D9/D38)** -- deliberately not
  *provenance*, which is a word that belongs to modules (P040). An asset ingested from
  something (a captured CLI ``--help``, a PowerShell function) versus one a human
  authored by hand.
* **``kind`` says which convention the payload follows (P097).** An **open registry,
  never an enum**: the envelope checks that it is a lexically sane string and carries
  the meaning verbatim, exactly as the core carries socket keys it does not understand.
  ``WELL_KNOWN_KINDS`` below is *documentation*, not a gate -- any module may coin one,
  and a value nothing here has heard of is accepted. This **narrows D3 rather than
  reversing it**: there is still no fixed taxonomy, and organisation is still tags plus
  a saving convention; what there is now is a registry a reader can check against
  instead of a convention nothing can.

  **A kind is recorded at ingestion and never inferred from payload shape.** The source
  knows: an MCP server states that its tools are tools, a CLI's ``--help`` states that
  its options are options. Sniffing a payload later is guessing at something that was
  thrown away.

  **It is not what interoperability rests on.** ``interface`` is -- it is typed and
  validated and it is what a compiler consumes. ``kind`` answers only *"which convention
  does this opaque payload follow"*, which matters the moment a module reads a payload
  it did not write. Absent means unknown, and a pre-``kind`` asset therefore still loads
  unchanged: this added an optional field with a documented absent value, which is not
  a breaking change, so ``ASSET_API_VERSION`` did not move.
* **``captured_against`` stamps the owner-module version the asset was captured
  against.** Assets carry no semver of their own (D6), but their owner module does
  (P022), and nothing else detects the drift between them -- the highest-severity gap
  the design log named, because it surfaces at run time in someone else's graph. The
  stamp is the cheap half of the fix (``decisions.md``, 2026-09-12): a consumer that
  knows the owner's *current* version can compare, and say "this asset was made for
  cli_apps 0.4.0, you have 0.5.0" as a **warning**, rather than trusting it silently.
  Making the mismatch legible is the point; blocking on it is not.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The record schema marker, so a future reader can tell what it is looking at without
#: guessing -- a record with no schema marker is precisely the thing that needs a
#: migration later. Bumped only by a breaking change to the envelope.
ASSET_API_VERSION = 1

#: The two origins an asset can have (D9/D38). Not *provenance*: that word is a
#: module's, and two axes converging on one word is the failure P038/P040 exist to
#: untangle.
ORIGINS = ("ingested", "authored")

#: An asset id is a file stem and a URL segment, so it obeys the same rule cli_apps'
#: tool ids do.
ASSET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

#: The kinds this repository ships or expects, written down **so a reader has something
#: to check against** (P097). It is deliberately *not* a validation list: nothing here
#: compares against it, and a module in another repository may coin its own.
#:
#: * ``tool``       -- a callable capability: an MCP tool, a module tool
#: * ``command``    -- a CLI invocation: a mapped ``cli_apps`` catalogue entry
#: * ``script``     -- a file that is run: PowerShell, Python, a shell script
#: * ``agent``      -- a persona plus a tool set, on the ``model`` wire (P071)
#: * ``model``      -- a provider and its parameters
#: * ``mcp_server`` -- a connection to an MCP server, plus what it enumerated
WELL_KNOWN_KINDS = ("tool", "command", "script", "agent", "model", "mcp_server")

#: What a ``kind`` may look like. **A lexical rule, not a membership test** -- the same
#: treatment an id gets. A kind is a registry key: it is filtered on, grouped by and
#: written into a log line, so an unbounded string with newlines in it would make the
#: registry unusable. Any value matching this is accepted, whoever coined it.
KIND_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")

#: A socket name in the interface has to be a plain identifier -- it is P001's rule
#: for a per-instance socket name (``graph_editor/types.py`` ``_SOCKET_NAME_RE``),
#: because a consumer turns it into a channel key and a TypedDict field.
SOCKET_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MAX_NAME = 200
MAX_TAG = 64
MAX_TAGS = 64
MAX_SOCKETS = 64
MAX_PROPS = 100
MAX_PROP_LEN = 4096


class AssetError(ValueError):
    """An asset that will not load or will not validate. Carried to a client as 400."""


# ---------------------------------------------------------------------------
# coercion helpers -- every one exists because a POST/PUT body is untrusted
# ---------------------------------------------------------------------------

def _text(value: Any, what: str, limit: int = MAX_NAME) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AssetError(f"{what} must be a string, got {type(value).__name__}")
    return value.strip()[:limit]


def _kind(value: Any) -> str:
    """The open registry key (P097). Absent is ``""`` and means *unknown*.

    Checked for shape and never for membership: see :data:`WELL_KNOWN_KINDS`.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AssetError(f"kind must be a string, got {type(value).__name__}")
    kind = value.strip()
    if not kind:
        return ""
    if not KIND_RE.match(kind):
        raise AssetError(
            f"kind {kind!r} must match {KIND_RE.pattern} -- it is a registry key, not "
            "prose. Any value of that shape is accepted; there is no list to be on."
        )
    return kind


def _tags(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AssetError("tags must be a list of strings")
    out: list[str] = []
    for item in value[:MAX_TAGS]:
        if not isinstance(item, str):
            raise AssetError("tags must be a list of strings")
        tag = item.strip()[:MAX_TAG]
        if tag and tag not in out:
            out.append(tag)
    return out


def _sockets(value: Any, what: str) -> list[dict]:
    """One side of the interface -- a list of ``SocketSpec``-shaped dicts (D4).

    Validated shallowly: each entry is an object with an identifier ``name`` and a
    non-empty string ``type``, both from P001's vocabulary. Extra keys (``description``,
    ``required``, ``default``, ``widget``, ``map_over``, ``accumulate``, ...) are
    carried verbatim -- the whole ``SocketSpec.to_dict()`` shape round-trips -- because
    the consumer, not the envelope, is the authority on them.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise AssetError(f"{what} must be a list of socket objects")
    if len(value) > MAX_SOCKETS:
        raise AssetError(f"{what} may not declare more than {MAX_SOCKETS} sockets")
    out: list[dict] = []
    seen: set[str] = set()
    for entry in value:
        if not isinstance(entry, dict):
            raise AssetError(f"{what} entries must be objects")
        name = entry.get("name")
        if not isinstance(name, str) or not SOCKET_NAME_RE.match(name):
            raise AssetError(
                f"{what} socket name {name!r} must be an identifier "
                "(letters, digits and '_', not starting with a digit)"
            )
        if name in seen:
            raise AssetError(f"{what} socket {name!r} is declared twice")
        seen.add(name)
        stype = entry.get("type")
        if not isinstance(stype, str) or not stype.strip():
            raise AssetError(f"{what} socket {name!r} needs a non-empty 'type' string")
        # Carried verbatim, with name/type normalised. The core does not interpret the
        # type string; the graph editor's coercion table does.
        socket = {k: v for k, v in entry.items()}
        socket["name"] = name.strip()
        socket["type"] = stype.strip()
        out.append(socket)
    return out


def _interface(value: Any) -> dict:
    if value is None:
        return {"inputs": [], "outputs": []}
    if not isinstance(value, dict):
        raise AssetError("interface must be an object with 'inputs' and 'outputs'")
    return {
        "inputs": _sockets(value.get("inputs"), "interface.inputs"),
        "outputs": _sockets(value.get("outputs"), "interface.outputs"),
    }


def _properties(value: Any) -> dict:
    """Custom properties (D3): a flat object of JSON scalars. Open, not schema'd -- a
    module organises with tags plus whatever it needs to carry here."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise AssetError("properties must be an object")
    if len(value) > MAX_PROPS:
        raise AssetError(f"properties may not exceed {MAX_PROPS} keys")
    out: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise AssetError("property keys must be strings")
        if isinstance(item, str) and len(item) > MAX_PROP_LEN:
            raise AssetError(f"property {key!r} is longer than {MAX_PROP_LEN} characters")
        if not isinstance(item, (str, int, float, bool)) and item is not None:
            raise AssetError(
                f"property {key!r} must be a string, number, boolean or null"
            )
        out[key] = item
    return out


def slug(text: str) -> str:
    """A filename-safe id from whatever a caller typed. Same rule as cli_apps' slug."""
    normal = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", normal).strip("-").lower()
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned[:48] or "asset"


# ---------------------------------------------------------------------------
# the envelope
# ---------------------------------------------------------------------------

@dataclass
class Asset:
    """The envelope over an opaque module payload (D3).

    ``payload`` is any JSON value and is **never parsed here** -- it is the owning
    module's, stored and served as-is. Everything else is the common envelope a
    consumer reads: the identity, the tags for organisation, the typed socket
    ``interface`` for wiring (D4), the ``origin`` (D9), and ``captured_against`` -- the
    owner-module version this was captured against, so drift can be told (D6, the
    version-drift resolution).
    """

    id: str = ""
    name: str = ""
    owner: str = ""
    origin: str = "authored"
    #: Which convention the opaque ``payload`` follows (P097). An **open registry**, not
    #: an enum -- see :data:`WELL_KNOWN_KINDS`. Empty means *unknown*, which is what a
    #: record written before this field existed reads as.
    kind: str = ""
    #: The owner-module version this asset was captured against (D6 resolution). Empty
    #: only for a record written before the stamp existed, which a consumer reads as
    #: "unknown" rather than "matches".
    captured_against: str = ""
    tags: list[str] = field(default_factory=list)
    #: ``{"inputs": [socket, ...], "outputs": [socket, ...]}`` in P001's vocabulary.
    interface: dict = field(default_factory=lambda: {"inputs": [], "outputs": []})
    #: Open custom properties (D3). Flat JSON scalars.
    properties: dict = field(default_factory=dict)
    #: The opaque module payload. Any JSON. Not parsed by the envelope.
    payload: Any = None
    created_at: float = 0.0
    api_version: int = ASSET_API_VERSION

    def summary(self) -> dict:
        """What a listing shows: the envelope without the payload, which can be large
        and which the library view has no business rendering."""
        return {
            "id": self.id,
            "name": self.name,
            "owner": self.owner,
            "origin": self.origin,
            "kind": self.kind,
            "captured_against": self.captured_against,
            "tags": list(self.tags),
            "interface": {
                "inputs": [dict(s) for s in self.interface.get("inputs", [])],
                "outputs": [dict(s) for s in self.interface.get("outputs", [])],
            },
            "properties": dict(self.properties),
            "created_at": self.created_at,
            "api_version": self.api_version,
        }

    def to_dict(self) -> dict:
        return {**self.summary(), "payload": self.payload}

    @classmethod
    def from_dict(cls, data: Any) -> "Asset":
        if not isinstance(data, dict):
            raise AssetError("an asset must be an object")
        origin = _text(data.get("origin"), "origin") or "authored"
        if origin not in ORIGINS:
            raise AssetError(f"origin must be one of {list(ORIGINS)}, got {origin!r}")
        created_at = data.get("created_at") or 0.0
        if not isinstance(created_at, (int, float)) or isinstance(created_at, bool):
            raise AssetError("created_at must be a number")
        api_version = data.get("api_version", ASSET_API_VERSION)
        if not isinstance(api_version, int) or isinstance(api_version, bool):
            raise AssetError("api_version must be an integer")
        return cls(
            id=_text(data.get("id"), "id", 64),
            name=_text(data.get("name"), "name") or _text(data.get("id"), "id", 64),
            owner=_text(data.get("owner"), "owner", 64),
            origin=origin,
            kind=_kind(data.get("kind")),
            captured_against=_text(data.get("captured_against"), "captured_against", 64),
            tags=_tags(data.get("tags")),
            interface=_interface(data.get("interface")),
            properties=_properties(data.get("properties")),
            payload=data.get("payload"),
            created_at=float(created_at),
            api_version=api_version,
        )


class BrokenAsset:
    """A file on disk that will not load. Shown, not swallowed -- the library view is
    the page you would use to fix it, so it must not be the page that breaks."""

    def __init__(self, asset_id: str, reason: str):
        self.id = asset_id
        self.reason = reason

    def summary(self) -> dict:
        return {"id": self.id, "name": self.id, "broken": True, "reason": self.reason}


# ---------------------------------------------------------------------------
# the module-owned store
# ---------------------------------------------------------------------------

class AssetStore:
    """One file per asset under ``<data_dir>/assets/<id>.json``.

    ``data_dir`` is the module's own runtime directory -- ``ctx.data_dir`` under the
    host, ``HDECK_MODULE_DATA_DIR`` for a spawned process module -- never the module's
    installed directory (D24). A module holds one of these and it is the *only* place
    that module's assets live; the library is a view over many of them (D5).
    """

    def __init__(self, data_dir: Path | str | None, *, owner: str = ""):
        self.data_dir = Path(data_dir) if data_dir is not None else Path.cwd()
        self.assets_dir = self.data_dir / "assets"
        self.owner = owner

    def path_for(self, asset_id: str) -> Path:
        if not ASSET_ID_RE.match(asset_id or ""):
            raise AssetError(f"{asset_id!r} is not a valid asset id")
        return self.assets_dir / f"{asset_id}.json"

    def ids(self) -> list[str]:
        if not self.assets_dir.is_dir():
            return []
        return sorted(p.stem for p in self.assets_dir.glob("*.json") if ASSET_ID_RE.match(p.stem))

    def new_id(self, base: str) -> str:
        candidate = slug(base)
        existing = set(self.ids())
        if candidate not in existing:
            return candidate
        for n in range(2, 1000):
            attempt = f"{candidate}-{n}"
            if attempt not in existing:
                return attempt
        raise AssetError(f"too many assets named {candidate!r}")

    def get(self, asset_id: str) -> Asset | None:
        path = self.path_for(asset_id)
        if not path.is_file():
            return None
        asset = Asset.from_dict(json.loads(path.read_text(encoding="utf-8")))
        asset.id = asset_id
        if self.owner and not asset.owner:
            asset.owner = self.owner
        return asset

    def load_all(self) -> tuple[list[Asset], list[BrokenAsset]]:
        assets: list[Asset] = []
        broken: list[BrokenAsset] = []
        for asset_id in self.ids():
            try:
                asset = self.get(asset_id)
            except (OSError, ValueError) as exc:
                broken.append(BrokenAsset(asset_id, str(exc)))
                continue
            if asset is not None:
                assets.append(asset)
        assets.sort(key=lambda a: (a.name.lower(), a.id))
        return assets, broken

    def save(self, asset: Asset) -> Asset:
        if self.owner:
            asset.owner = self.owner
        if not asset.created_at:
            asset.created_at = time.time()
        if not asset.id:
            asset.id = self.new_id(asset.name or "asset")
        path = self.path_for(asset.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(asset.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(path)
        return asset

    def delete(self, asset_id: str) -> bool:
        path = self.path_for(asset_id)
        if not path.is_file():
            return False
        path.unlink()
        return True


# ---------------------------------------------------------------------------
# the FastAPI surface -- the one thing here that is not stdlib
# ---------------------------------------------------------------------------

def mount_asset_api(
    app: Any,
    store: "AssetStore",
    *,
    owner: str,
    origin_default: str = "authored",
    log: Any = None,
    prefix: str = "/api/assets",
) -> Any:
    """Add the asset surface -- create, list, read, delete -- to a module's FastAPI app.

    The routes a consumer and the library view depend on (relative URLs, so they serve
    at ``/m/<owner>/api/assets`` hosted and ``/api/assets`` standalone):

    * ``GET  /api/assets``            -> ``{"assets": [summary, ...], "broken": [...]}``
    * ``POST /api/assets``            -> create; body is an asset object; ``201``
    * ``GET  /api/assets/{id}``       -> the full asset, payload included
    * ``DELETE /api/assets/{id}``     -> ``{"ok": true, "id": ...}``

    FastAPI is imported here rather than at module scope so that importing ``assets``
    never drags in a web framework -- the store and envelope above are stdlib-only, for
    a module that serves with something else or in another language entirely.

    ``log`` is an optional ``log(level, event, message, **fields)`` callable; a create
    or delete is worth one line, and a module that has ``ctx.log`` passes it.
    """
    from fastapi import Body, HTTPException
    from fastapi.responses import JSONResponse

    def _emit(level: str, event: str, message: str, **fields: Any) -> None:
        if callable(log):
            try:
                log(level, event, message, **fields)
            except Exception:  # pragma: no cover - logging never breaks a request
                pass

    @app.get(prefix)
    def list_assets() -> dict:
        assets, broken = store.load_all()
        return {
            "owner": owner,
            "assets": [a.summary() for a in assets],
            "broken": [b.summary() for b in broken],
        }

    @app.post(prefix, status_code=201)
    def create_asset(payload: dict = Body(default_factory=dict)) -> dict:
        body = dict(payload or {})
        body.setdefault("origin", origin_default)
        body["owner"] = owner
        try:
            asset = Asset.from_dict(body)
        except AssetError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        asset.id = store.new_id(asset.id or asset.name or "asset")
        saved = store.save(asset)
        _emit(
            "info",
            "assets.created",
            f"created asset {saved.name or saved.id}",
            asset=saved.id,
            origin=saved.origin,
            kind=saved.kind,
            captured_against=saved.captured_against,
        )
        return {"asset": saved.to_dict()}

    @app.get(prefix + "/{asset_id}")
    def get_asset(asset_id: str) -> dict:
        try:
            asset = store.get(asset_id)
        except AssetError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=f"{asset_id} will not load: {exc}") from exc
        if asset is None:
            raise HTTPException(status_code=404, detail=f"no asset {asset_id!r}")
        return {"asset": asset.to_dict()}

    @app.delete(prefix + "/{asset_id}")
    def delete_asset(asset_id: str) -> dict:
        try:
            removed = store.delete(asset_id)
        except AssetError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not removed:
            raise HTTPException(status_code=404, detail=f"no asset {asset_id!r}")
        _emit("warning", "assets.deleted", f"removed asset {asset_id}", asset=asset_id)
        return {"ok": True, "id": asset_id}

    @app.exception_handler(AssetError)
    def _asset_error(_request, exc: AssetError) -> JSONResponse:  # pragma: no cover
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app
