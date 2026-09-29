"""HollowDeck code this module carries a **verbatim copy** of, because it cannot import it.

A module imports nothing from the core (INTEROP.md section 10): not its config, not a
value type, not a helper. Where one implementation must be shared, the module keeps a
byte-identical snapshot and a test compares the bytes. ``../VENDORED.json`` lists every
copied file, where it came from in the HollowDeck checkout, and its sha256.

* ``guard.py``  -- ``shared/python/guard.py``: refuses every request that did not come
  through the host (the per-spawn secret), or, standalone, anything not addressed to this
  port by a loopback name.
* ``assets.py`` -- ``shared/python/assets.py``: the asset envelope and store, and the
  ``api/assets`` routes the Asset Library reads.
* ``proc.py``   -- ``shared/python/proc.py``: ``no_window()`` so a job opens no console
  window, and ``ChildJail`` (a Windows job object with KILL_ON_JOB_CLOSE) so a job's
  process tree cannot outlive this module or be left behind by a cancel.

Never edit a copy. Re-vendor from upstream and update the hash in ``VENDORED.json``.
This file is the module's own and is not vendored.
"""
