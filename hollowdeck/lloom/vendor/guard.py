"""The request guard: which requests a listener on this machine answers at all.

**One implementation, two users, and that is the whole point of this file.** The core
imports it (``core/src-rust/src/guard.rs``, the core's own port) and every module
carries a **byte-identical
copy** under its own ``vendor/`` -- the same answer ``vendor/logsink.py`` and
``static/vendor/`` already give, for the same reason: *a module cannot borrow the
core's anything.* Not its URL, not its ``sys.path``, and not its language. A test
compares the bytes (``tests/test_module_guard.py``).

Stdlib only, and no framework import anywhere in it. A module that serves with
Starlette, with ``http.server``, or with nothing at all can wrap
:class:`ModuleGuard` around its ASGI app, and the pure functions below are callable
from a program that has no ASGI in it.

Three questions, and which ones apply depends on **who is asking**:

1. **Is this request addressed to this listener at all?** Every method, and a
   WebSocket handshake too. See :func:`host_allowed`. This is the DNS-rebinding
   defence (2026-09-12): a page on ``evil.example`` whose name is re-pointed at
   ``127.0.0.1`` is *same-origin* with a loopback service as far as the browser is
   concerned, so it sends ``Host: evil.example:<port>`` with a matching ``Origin``,
   every ``Origin == Host`` rule waves it through, and CORS withholds none of the
   responses. The one thing the attacker cannot choose is the name in ``Host``: it is
   the attacker's own.
2. **Did a foreign page send this write?** Writes only. See :func:`write_refusal`.
3. **Did this request come through the host at all?** A ``kind: process`` module only
   (2026-09-12). See :class:`ModuleGuard` and :data:`SECRET_ENV`.

The first two are the core's rule, implemented as a pure function of the method, the
headers and the bound port so that it can be compared case by case:
``tools/gen_rust_goldens.py`` recorded what the retired Python core answered for every
case in ``core/src-rust/tests/fixtures/request_guard.json``, and
``core/src-rust/src/guard.rs`` is asserted to reproduce that frozen golden.

The third exists because **the core's allowlist protects the core's port, and a
spawned module listens on a different one.** See :class:`ModuleGuard`.
"""

from __future__ import annotations

import hmac
import json
import os
from typing import Any, NamedTuple

# -- names and constants ----------------------------------------------------------

#: The only names a loopback service answers to. The port must be the one it is
#: bound to. See :func:`host_allowed`.
LOOPBACK_HOST_NAMES = ("127.0.0.1", "localhost", "[::1]")

#: What ``--host`` may be. The same three names an address can be *spelled* as when a
#: listener binds one, which is why ``::1`` appears unbracketed as well: a ``Host``
#: header brackets an IPv6 literal and a bind address does not. See
#: :func:`bind_refusal`.
LOOPBACK_BIND_NAMES = ("127.0.0.1", "localhost", "::1", "[::1]")

#: The methods that *do* something.
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")

#: Optional whitespace around a header value is legal HTTP (RFC 9110 5.5: "the field
#: value does not include leading or trailing whitespace") and is the parser's to
#: remove. The two cores' parsers disagreed about whether they had -- ``Host:
#: 127.0.0.1:8765 `` reached Python's guard with the space still on it and Rust's
#: without -- so both trim before deciding, and the header rules stay a property of
#: the value rather than of whichever parser delivered it.
OWS = " \t"

#: The ``reason`` field of a ``security.refused`` line. Spelled identically by both
#: cores -- the golden compares them -- so a filter on one finds the other's.
REASON_HOST = "Host is not a loopback address for this port"
REASON_SITE_TWICE = "Sec-Fetch-Site sent more than once"
REASON_ORIGIN_TWICE = "Origin sent more than once"
REASON_CROSS_SITE = "sec-fetch-site: cross-site"
REASON_ORIGIN_MISMATCH = "Origin does not match Host"
#: A module's own, and the only one the core never answers: the request did not come
#: through the host, so it is not one of the application's.
REASON_NO_SECRET = "no valid module secret: this request did not come through the host"

#: The status for a request addressed to a name this service does not answer to.
#: 421 is the precise one -- "this server is not able to produce a response for this
#: authority" -- and it keeps a wrong-name refusal distinguishable from a cross-site
#: write's 403 at a glance, in a log line or a browser's network tab.
MISDIRECTED = 421

#: The eighth handshake variable (``docs/arch/modules.md``): a secret the host mints
#: **per spawn**, hands to the module in its environment, and adds to every request
#: it proxies. A module that sees it set refuses anything arriving without it.
SECRET_ENV = "HDECK_MODULE_SECRET"

#: The header the host puts the secret in. Lowercase, because that is how ASGI and
#: HTTP/2 spell a header name and the comparison here is done on the raw bytes.
SECRET_HEADER = "x-hdeck-module-secret"


class Refusal(NamedTuple):
    status: int
    reason: str


# -- the pure decisions -----------------------------------------------------------


def header_values(headers: Any, name: bytes) -> list[str]:
    """Every value of one header in an ASGI header list, in order, as latin-1 text,
    with surrounding whitespace removed (see :data:`OWS`).

    Every value, not the first: *how many* there were is part of the decision. A
    request with two ``Host`` or two ``Origin`` headers is ambiguous, and a check that
    reads the first while something downstream reads the last is a check that can be
    walked around."""
    return [v.decode("latin-1").strip(OWS) for k, v in (headers or []) if k.lower() == name]


def origin_matches_host(origin: str, host_header: str | None) -> bool:
    """Is ``Origin`` the same host:port the request arrived on?

    Compared against ``Host`` rather than a configured origin because the port is
    chosen at runtime (``--port 0``, or the sidecar picking a free one), so there is
    no single correct origin to hardcode. Scheme is ignored on purpose: this service
    is loopback-only http, and an https page on the same host:port is not a case that
    can arise. ``Origin: null`` -- sent by a sandboxed frame or a ``file://`` page --
    never matches, which is the intent.
    """
    if not host_header:
        return False
    netloc = origin.split("://", 1)[-1] if "://" in origin else origin
    if netloc == host_header:
        return True
    # A default port may be present on one side and elided on the other.
    for default in (":80", ":443"):
        if netloc.removesuffix(default) == host_header.removesuffix(default):
            return True
    return False


def host_allowed(values: list[str], port: int | None) -> bool:
    """Is this the ``Host`` of a request meant for this service?

    **The DNS-rebinding defence**, and the reason it has to be on every request rather
    than on writes. A page on ``evil.example`` whose name is then re-pointed at
    ``127.0.0.1`` is, as far as the browser is concerned, *same-origin* with this
    service: it sends ``Host: evil.example:<port>`` and a matching ``Origin``, so the
    Origin==Host rule waves its writes through, and it can read every response,
    because same-origin is exactly what CORS does not withhold. The one thing the
    attacker cannot change is the name the browser puts in ``Host`` -- it is the
    attacker's own. So the answer is to accept only names that cannot be rebound.

    Accepted: exactly one ``Host`` header whose name is ``127.0.0.1``, ``localhost`` or
    ``[::1]`` (ASCII case-insensitive -- a host name is) and whose port is the bound
    port, spelled as a browser spells it. A missing port is accepted only when the
    bound port is 80, because that is the only case in which a browser omits it.
    Whitespace around the value is removed by :func:`header_values` before it gets
    here, because that is the parser's job and one of the two cores' parsers was
    already doing it.

    Refused, deliberately, with the reason for each:

    * **any other name**, including ``127.0.0.1.evil.example`` -- a name is only safe if
      nobody else's DNS can answer for it;
    * ``localhost.`` -- the trailing-dot form is more likely than bare ``localhost`` to
      be sent to a real resolver, which is the thing to avoid;
    * ``127.1``, ``[::ffff:127.0.0.1]``, a leading zero on the port -- a browser
      normalises all of these before sending, so only a hand-made request carries them,
      and an allowlist that parses alternative spellings is one that can be parsed
      differently from the socket;
    * ``127.0.0.2`` -- loopback, but not the address this service is bound to;
    * ``0.0.0.0`` -- historically a way for a public page to reach a loopback service;
    * no ``Host``, an empty one, or more than one.

    ``port`` is ``None`` when the server did not say which port the request arrived
    on; with nothing to compare against, nothing is accepted.
    """
    if port is None or len(values) != 1:
        return False
    # Trimmed again, harmlessly: `header_values` already did it for a request off the
    # wire, and a caller holding a raw `Host` value -- a test, a module asking about
    # what it was reached with -- gets the same answer as the middleware does rather
    # than a stricter one. Idempotent, and the Rust `host_allowed` trims in the same
    # place for the same reason.
    value = values[0].strip(OWS)
    if not value.isascii():
        return False
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            return False
        name, rest = value[: end + 1], value[end + 1 :]
    else:
        colon = value.find(":")
        name, rest = (value, "") if colon < 0 else (value[:colon], value[colon:])
    if name.lower() not in LOOPBACK_HOST_NAMES:
        return False
    if not rest:
        return port == 80
    return rest == f":{port}"


def host_refusal(headers: Any, port: int | None) -> Refusal | None:
    """The 421 for a request not addressed to this service, or ``None``."""
    if host_allowed(header_values(headers, b"host"), port):
        return None
    return Refusal(MISDIRECTED, REASON_HOST)


def write_refusal(method: str, headers: Any) -> Refusal | None:
    """The 403 for a write a foreign page sent, or ``None``. Reads always pass.

    The rule is deliberately narrow, so that nothing legitimate breaks:

    * Only **writes** are checked. A cross-origin *read* is already useless to an
      attacker -- the browser withholds the response body without CORS headers, which
      this application never sends -- and checking reads would be noise.
    * A request with **no** ``Origin`` passes: browsers always attach one to a
      cross-origin write, so its absence means a non-browser caller.
    * An ``Origin`` that **matches the Host** the request arrived on passes.
    * ``Sec-Fetch-Site: cross-site`` is refused outright, in any letter case.
    * An ``Origin`` or ``Sec-Fetch-Site`` sent **more than once** is refused rather
      than read as its first value. A browser sends neither twice; a check that picks
      one of two is a check something downstream may disagree with.

    **Origin==Host cannot see DNS rebinding**, because a rebound page is same-origin
    under the attacker's name. That is :func:`host_refusal`'s job.
    """
    if method not in WRITE_METHODS:
        return None
    sites = header_values(headers, b"sec-fetch-site")
    origins = header_values(headers, b"origin")
    if len(sites) > 1:
        return Refusal(403, REASON_SITE_TWICE)
    if len(origins) > 1:
        return Refusal(403, REASON_ORIGIN_TWICE)
    if sites and sites[0].strip().lower() == "cross-site":
        return Refusal(403, REASON_CROSS_SITE)
    hosts = header_values(headers, b"host")
    if origins and origins[0] and not origin_matches_host(origins[0], hosts[0] if hosts else None):
        return Refusal(403, REASON_ORIGIN_MISMATCH)
    return None


def request_refusal(method: str, headers: Any, port: int | None) -> Refusal | None:
    """Both of the core's questions, in the order the middleware stack asks them."""
    return host_refusal(headers, port) or write_refusal(method, headers)


def server_port(scope: Any) -> int | None:
    """The port this request arrived on, from the ASGI ``server`` pair.

    Per request rather than captured at startup, because the port is chosen at runtime
    (``--port 0``, the shell picking a free one, a test's ``uvicorn.Config``) and the
    application is built before any of them has decided."""
    server = (scope or {}).get("server")
    try:
        return int(server[1]) if server else None
    except (TypeError, IndexError, ValueError):
        return None


def host_refusal_detail(shown: str, port: int | None) -> str:
    """The sentence a 421 carries. Names the three spellings that would have worked,
    because "421" on its own tells nobody how to fix it."""
    if port is None:
        where = "this service could not tell which port the request arrived on"
    else:
        where = (
            f"this service answers only to 127.0.0.1:{port}, localhost:{port} and "
            f"[::1]:{port}"
        )
    return (
        f"refusing a request addressed to {shown!r}: {where}. A page reached under any "
        "other name -- which is what a DNS-rebinding page sends -- is not one of its own. "
        "See docs/arch/isolation.md."
    )


def bind_refusal(host: str) -> str:
    """``""`` if ``host`` is a loopback bind; the sentence to refuse it with otherwise.

    **The listener is the decision, not a flag.** "Single user, loopback, no auth" is
    the posture every other decision in this project leans on, and CLAUDE.md says an
    inbound network listener is its own decision with its own auth work. Until that
    decision exists there is nothing for ``--host 0.0.0.0`` to mean except *the whole
    application, unauthenticated, to everyone who can route here* -- which, with a
    terminal module in the tree, is a remote shell.

    There is deliberately **no opt-in flag**. A switch that binds a no-auth service to
    the network is a switch someone sets once, for one afternoon, and forgets; and a
    flag would also have to answer what it does about the ``Host`` allowlist, which
    refuses a LAN address anyway -- so the flag's honest behaviour today is "start a
    listener that answers 421 to everything that reaches it".
    """
    name = (host or "").strip()
    if name.lower() in LOOPBACK_BIND_NAMES:
        return ""
    return (
        f"refusing to bind {name!r}: HollowDeck is single-user, loopback-only and has no "
        "authentication, so a listener anything else can reach is a different security "
        "posture -- one that needs its own decision and its own auth work (CLAUDE.md, "
        "Out of scope: inbound network listeners). There is no flag that turns this off. "
        f"Use --host 127.0.0.1, localhost or ::1. Every request a LAN client sent would "
        "be answered 421 in any case, because the Host allowlist accepts only those "
        "names (docs/arch/isolation.md)."
    )


# -- the module's own guard -------------------------------------------------------


def secret_from_env(env: Any = None, *, consume: bool = True) -> str:
    """The host's per-spawn secret, taken out of the environment.

    **Taken out**, not read: the default pops it, so the children a module starts --
    a CLI tool's ``--help``, a graph's ``tool/exec`` node, the shell a terminal opens
    -- do not inherit it. They have no use for it, and a secret that is not there
    cannot be read out of a process listing or an environment dump.

    Call this once, before anything is spawned or served.
    """
    environ = os.environ if env is None else env
    value = environ.pop(SECRET_ENV, "") if consume else environ.get(SECRET_ENV, "")
    return (value or "").strip()


def secret_ok(headers: Any, secret: str) -> bool:
    """Exactly one secret header, and it is the host's. Compared in constant time --
    not because a timing attack over loopback is likely, but because the comparison is
    one line either way and the version that leaks is the one people copy."""
    if not secret:
        return False
    values = [v for k, v in (headers or []) if k.lower() == SECRET_HEADER.encode("latin-1")]
    if len(values) != 1:
        return False
    return hmac.compare_digest(values[0].decode("latin-1").strip(OWS), secret)


def strip_secret(headers: Any) -> list:
    """The header list with every copy of the secret header removed.

    The module's own routes never need it, and a route that echoed its headers would
    otherwise hand the secret to whoever asked. Cheap, and it keeps the secret a fact
    about the hop rather than about the request.
    """
    name = SECRET_HEADER.encode("latin-1")
    return [(k, v) for k, v in (headers or []) if k.lower() != name]


class ModuleGuard:
    """ASGI middleware a module wraps its own app in, before it serves.

    **Why a module needs one at all.** The core answers only to its own loopback name
    on its own port, so a DNS-rebinding page cannot reach anything *through* the core.
    A ``kind: process`` module is not behind that: it listens on its own ephemeral
    loopback port, and a page that finds that port -- by scanning, which is cheap --
    reaches the module's routes directly, with the core's allowlist and the core's
    CSRF check both one process away. That was true of every module here until
    2026-09-12: ``/health`` and ``/`` answered 200 to a rebound page on every module,
    Logging wrote an event, the scheduler created and ran a schedule, and the editor
    ran a graph.

    Two modes, and the module does not choose between them -- the environment does:

    * **Hosted** (:data:`SECRET_ENV` is set). Every request must carry the host's
      secret in :data:`SECRET_HEADER`; nothing else is answered, whatever its
      ``Host``. A browser cannot learn the secret: it never appears in a response, in
      a log line, in ``/api/modules`` or in a page. The check is therefore not about
      *names* at all, which is what makes it independent of how well the module
      reasons about ``Host`` -- and it closes the second hole in the same motion, a
      cross-site write straight to the module's port with a perfectly loopback
      ``Host``.
    * **Standalone** (no secret in the environment -- ``python modules/<id>/__main__.py
      8765``). There is no host to have set one, so the module applies **the core's own
      rule to its own port**: exactly one loopback ``Host`` on the port it is listening
      on, plus the core's cross-site write check. That is :func:`request_refusal`,
      which is literally the same function the core calls.

    Reads are refused as firmly as writes in both modes, because a rebound page can
    read: it is same-origin under its own name, so CORS withholds nothing from it.

    A refused WebSocket handshake is answered with a real status when the server
    offers the ``websocket.http.response`` extension -- uvicorn does -- and with a
    pre-accept close otherwise, which a server turns into a 403.

    **How a module uses it**, and the order is the whole of the usage::

        guard = load_guard()          # vendor/guard.py, by file location
        secret = guard.secret_from_env()   # *before* anything is built or spawned
        app = create_app(ctx)
        uvicorn.run(guard.ModuleGuard(app, secret, module_id=ctx.module_id), ...)

    Two steps rather than one wrapper call, because the secret has to leave the
    environment before the module builds anything that could spawn a child -- a
    scheduler's tick thread, a terminal's shell, a graph's ``tool/exec`` node -- and a
    convenience that hid the ordering would be a convenience that got it wrong.
    """

    def __init__(self, app: Any, secret: str = "", *, module_id: str = "") -> None:
        self.app = app
        self.secret = (secret or "").strip()
        #: For the refusal sentence only. A hosted module's mount path is not visible
        #: from inside it, so the id is what lets the sentence name the right URL.
        self.module_id = (module_id or "").strip() or "<id>"

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        kind = scope.get("type")
        if kind not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = scope.get("headers")
        refusal = self.refusal_for(scope)
        if refusal is None:
            if self.secret:
                # The hop's header, gone before the module's own code sees the request.
                scope = dict(scope)
                scope["headers"] = strip_secret(headers)
            await self.app(scope, receive, send)
            return
        await self._refuse(scope, receive, send, refusal)

    def refusal_for(self, scope: Any) -> Refusal | None:
        """The refusal this request earns, or ``None``. Pure: a test can ask it
        without a server, and this is where the two modes are chosen between."""
        headers = scope.get("headers")
        if self.secret:
            if secret_ok(headers, self.secret):
                return None
            return Refusal(MISDIRECTED, REASON_NO_SECRET)
        method = scope.get("method") or "GET"
        return request_refusal(method, headers, server_port(scope))

    def detail_for(self, scope: Any, refusal: Refusal) -> str:
        if refusal.reason == REASON_NO_SECRET:
            return (
                "refusing a request that did not come through the HollowDeck host: this "
                "module is hosted, so every request it answers arrives through the "
                f"core at /m/{self.module_id}/ and carries the host's per-spawn "
                "secret. A page that found this port directly -- which is what a "
                "DNS-rebinding or port-scanning page does -- has no way to have one. "
                "See docs/arch/modules.md."
            )
        if refusal.reason == REASON_HOST:
            shown = ", ".join(header_values(scope.get("headers"), b"host"))
            return host_refusal_detail(shown, server_port(scope))
        return (
            f"refusing this request: {refusal.reason}. See docs/arch/isolation.md."
        )

    async def _refuse(self, scope: Any, receive: Any, send: Any, refusal: Refusal) -> None:
        payload = {"detail": self.detail_for(scope, refusal)}
        body = json.dumps(payload).encode("utf-8")
        if scope.get("type") == "http":
            await send(
                {
                    "type": "http.response.start",
                    "status": refusal.status,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        # The handshake's own `websocket.connect` first, as the ASGI spec orders it.
        await receive()
        if "websocket.http.response" in (scope.get("extensions") or {}):
            await send(
                {
                    "type": "websocket.http.response.start",
                    "status": refusal.status,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "websocket.http.response.body", "body": body})
            return
        await send({"type": "websocket.close", "code": 1008})
