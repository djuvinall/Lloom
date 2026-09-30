"""The route back to the HollowDeck core: the event log, reports, and graph runs.

``HDECK_CORE_URL`` is the only way back (INTEROP.md §2), and it is *absent* when no
core is listening -- a real state, not an error. Every call here answers ``False`` /
``None`` then, and says so in this module's own ``process.log`` (stdout), so nothing
believes it logged when it did not.

Requests go to the core's loopback origin with **no Origin header** (§11): this is a
process, not a browser, and the core's cross-site check lets a header-less write
through for exactly that reason.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable


class CoreClient:
    def __init__(self, core_url: str | None, module_id: str, *, timeout: float = 5.0,
                 opener: Callable | None = None):
        self.core_url = (core_url or "").rstrip("/") or None
        self.module_id = module_id
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen

    @property
    def available(self) -> bool:
        return self.core_url is not None

    def _post(self, path: str, body: dict, timeout: float | None = None) -> tuple[int, Any]:
        if self.core_url is None:
            return 0, None
        request = urllib.request.Request(
            self.core_url + path, data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"content-type": "application/json", "accept": "application/json"})
        try:
            with self._open(request, timeout=timeout or self.timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(), exc.code
        try:
            return status, json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            return status, raw.decode("utf-8", "replace")

    def log(self, level: str, event: str, message: str, **fields: Any) -> bool:
        """One line in HollowDeck's event log -- and always one in process.log."""
        print(f"[lloom] {level} {event}: {message}", flush=True)
        if self.core_url is None:
            return False
        try:
            status, _ = self._post("/m/event_log/api/events", {
                "event": event, "level": level, "message": message,
                "source": self.module_id, "fields": fields})
        except (OSError, ValueError):
            return False
        return 200 <= status < 300

    def report(self, severity: str, message: str, detail: str | None = None) -> bool:
        """Something a person should read: the status bar and the Info log (P081)."""
        if self.core_url is None:
            return False
        body = {"severity": severity, "message": message, "source": self.module_id}
        if detail:
            body["detail"] = detail
        try:
            status, _ = self._post("/api/reports", body)
        except (OSError, ValueError):
            return False
        return 200 <= status < 300

    def run_graph(self, graph: str, *, trigger: str = "lloom",
                  timeout: float = 6 * 3600) -> dict:
        """Run a saved graph through the core's ``POST /api/run`` -- unattended, always.

        The core answers when the run ends, with its run record; a refused or failed run
        is a record with ``"status": "failed"``, not an HTTP error. Blocks, so call it
        from a thread.
        """
        if self.core_url is None:
            return {"status": "failed", "error": "no HollowDeck core is listening "
                                                 "(HDECK_CORE_URL is not set)"}
        try:
            status, body = self._post("/api/run", {"graph": graph, "trigger": trigger},
                                      timeout=timeout)
        except (OSError, ValueError) as exc:
            return {"status": "failed", "error": f"the core could not be reached: {exc}"}
        if not isinstance(body, dict):
            return {"status": "failed", "error": f"the core answered {status}: {body!r:.200}"}
        if status >= 400:
            return {"status": "failed", "error": str(body.get("detail") or body)}
        return body
