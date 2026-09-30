"""Spawning child processes without throwing a console window at the user.

Why this exists, since it is four lines and could have been inlined fifteen times.

On Windows, a console-subsystem executable -- ``python.exe``, ``pwsh.exe``, most CLI
tools -- needs a console. If the spawning process has one, the child inherits it and
nothing appears. If the spawning process **does not**, Windows allocates a fresh
console for the child, and a **window pops up on the user's screen**.

That second case is not exotic; it is the normal case for this project:

* the test suite, when pytest is run from a tool that has no console of its own --
  every ``subprocess.run([sys.executable, ...])`` in ``tests/`` flashes a window, and
  there are a dozen of them;
* a ``kind: process`` module spawned by the core, which the user
  never asked to see a console for;
* anything a module shells out to, such as capturing ``--help`` output.

Reported by Devon, 2026-09-05: *"I'm having a lot of terminals popup on my screen
right now ... Even as I type this I'm being interrupted."* Windows stealing focus
mid-keystroke is the actual harm, and it is worse than cosmetic.

``CREATE_NO_WINDOW`` says "give the child a console, but do not show it", which is
what every non-interactive spawn in this project wants. It is Windows-only; on POSIX
:func:`no_window` returns an empty dict and callers are unchanged.

**``DETACHED_PROCESS`` is a trap, and this file used to fall into it.** Until
2026-09-08 :func:`no_window` took ``detached=True`` and returned
``DETACHED_PROCESS | CREATE_NO_WINDOW``, on the reasoning that detachment gives the
child no console and the second flag keeps the console it later allocates silent.
The reasoning is wrong, and Win32 says so: ``CREATE_NO_WINDOW`` *"is ignored if the
application is not a console application, or if it is used with either
CREATE_NEW_CONSOLE or DETACHED_PROCESS"*. Measured on Windows 11, spawning
``.venv/Scripts/python.exe`` from a parent with no console of its own::

    no flags at all                      -> new visible windows: none
    CREATE_NO_WINDOW                     -> new visible windows: none
    DETACHED_PROCESS                     -> CASCADIA_HOSTING_WINDOW_CLASS
                                            (WindowsTerminal.exe) + PseudoConsoleWindow
    DETACHED_PROCESS | CREATE_NO_WINDOW  -> the same two windows
    the same, plus STARTUPINFO SW_HIDE   -> the same two windows

So the combination that was meant to be the *quiet* one was the only one that was
loud, and ``STARTUPINFO``/``SW_HIDE`` does not rescue it either -- the window is
opened by the console host for the grandchild, which never sees our ``STARTUPINFO``.

Four call sites paid for that: three passing ``detached=True`` in
``core/src-rust/tests/hosting.rs`` and one spelling the combination raw as
``0x08000008`` in ``tests/test_terminal.py``. Two of them wanted *the probe they
spawn* to hold no console, so that a module **it** spawns is in the position a module
is in under the Tauri shell -- that is :func:`drop_console`, called from inside the
probe: spawn quietly with ``CREATE_NO_WINDOW``, then let the child put itself where
the test needs it. One never needed detaching at all. And the fourth wanted a
grandchild *outside* its parent's pseudoconsole, which ``CREATE_NO_WINDOW`` alone also
gives it, because a new console of its own is as far outside as no console at all.

**This is not for the terminal's PTY.** A pseudoconsole is not a console window and
never shows one -- ConPTY on Windows, ``openpty`` on POSIX. Do not add these flags
there; the PTY child must keep the pseudoconsole it was given.

P042 added the second half of a spawn's lifetime to this file: :class:`ChildJail`,
the Windows job object that makes a ``kind: process`` module die when the core dies.
``_unload`` already asks a child to stop politely; a job object is what covers the
case where the core is never asked anything -- ``taskkill /F``, a crash, a debugger
detaching. See the class docstring for why it is duplicated rather than imported.
"""

from __future__ import annotations

import os
from typing import Any

#: Windows ``CREATE_NO_WINDOW``. Spelled out rather than taken from ``subprocess``
#: because that attribute does not exist on POSIX, so importing it unguarded is an
#: ``AttributeError`` on the platform where this is a no-op.
CREATE_NO_WINDOW = 0x08000000

#: Windows ``DETACHED_PROCESS`` -- the child gets **no** console at all, and so
#: allocates a fresh one, **with a visible window**, the moment anything in its tree
#: needs it. Kept here only so the trap has a name to be warned about: **nothing in
#: this repo may pass it.** ``CREATE_NO_WINDOW`` is documented as ignored when it is
#: combined with this flag, and measurement agrees -- see the module docstring for
#: the numbers. If you want a console-less process, call :func:`drop_console` from
#: inside it.
DETACHED_PROCESS = 0x00000008

IS_WINDOWS = os.name == "nt"


def no_window() -> dict:
    """Keyword arguments for ``subprocess.Popen``/``run`` that show no window.

    Returns ``{}`` on POSIX, so a call site reads the same on both platforms::

        subprocess.run([sys.executable, "-c", src], **no_window())

    There is deliberately no ``detached=`` argument. One existed until 2026-09-08 and
    was the one spelling of this helper that *did* throw a window; the module
    docstring has the measurement, and :func:`drop_console` is what its callers
    wanted instead.
    """
    if not IS_WINDOWS:
        return {}
    return {"creationflags": CREATE_NO_WINDOW}


def drop_console() -> bool:
    """Detach **this** process from whatever console it holds. ``True`` if it had one.

    The counterpart to :func:`no_window`, and the honest way to get what
    ``no_window(detached=True)`` promised. A spawn flag cannot produce a quiet
    console-less child, because Windows will not accept "no console" and "and be
    quiet about the one you make" in the same ``CreateProcess`` call. Calling
    ``FreeConsole`` from inside the child does produce it: the parent spawns with
    ``CREATE_NO_WINDOW`` (a new console, never shown), the child immediately drops
    it, and from then on the child is a process with no console at all -- which is
    the position a module is in under the Tauri shell, and therefore the only
    position from which "did the host's spawn open a window?" is a real question.

    Measured, not assumed: from a process that has called this, a child spawned with
    ``**no_window()`` opens no visible window and a child spawned with no flags opens
    two (the console host's, and the child's own ``PseudoConsoleWindow``). That is
    what makes the tests built on it tripwires rather than decoration.

    A no-op returning ``False`` on POSIX, where a controlling terminal is a different
    thing with a different answer (``setsid``), and where none of this is a problem.
    """
    if not IS_WINDOWS:
        return False
    import ctypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    # GetConsoleCP() is 0 when the process is not attached to a console.
    # GetConsoleWindow() is not the probe to use: a CREATE_NO_WINDOW console has a
    # window handle of 0 while the process is very much still attached to it.
    had = bool(k32.GetConsoleCP())
    k32.FreeConsole()
    return had


# ---------------------------------------------------------------------------
# Keeping a spawned module from outliving the core
# ---------------------------------------------------------------------------

class ChildJail:
    """One Windows **job object** per host, with ``KILL_ON_JOB_CLOSE``.

    ``ModuleHost._unload`` already does the polite half of the lifecycle:
    ``terminate()``, then ``kill()`` after a grace period. That covers every exit the
    core participates in. It covers none of the exits it does not -- ``taskkill /F``,
    a segfault in a native extension, a debugger detaching, the shell being killed
    from Task Manager. In all of those the core's shutdown never runs, and a
    ``kind: process`` module is left running on a loopback port with nothing pointing
    at it. An orphan like that is not merely untidy: it holds the port, so the *next*
    core boot spawns a second copy, and the user has no panel that shows either.

    A job object closes that hole because the guarantee is the operating system's,
    not ours. Every process assigned to the job dies when the last handle to the job
    closes, and Windows closes every handle a process held when that process dies --
    however it died. So:

    * a clean shutdown closes the handle in :meth:`release` and the tree goes;
    * a hard kill closes it too, because the OS does it, and the tree still goes.

    Children of a job member join the job by inheritance, so a module that shells out
    is covered as well without anything here knowing about it.

    **Nested jobs are fine.** The Tauri shell already puts the core itself in a
    kill-on-close job (``shell/src-tauri/src/sidecar.rs``), so under the shell this is
    a job inside a job -- supported since Windows 8, and the outer job's kill still
    reaches through. That is deliberately the same posture at both layers rather than
    two different mechanisms.

    **Why this is a second copy of the code in the terminal module.** The terminal has
    its own ``Jail`` in ``core_modules/terminal/pty_session.py``. The core may not
    import it -- "the core imports nothing from any module" is not a style rule, it is
    what makes a zero-module boot possible and it is asserted by a test. The other
    direction, a module importing the core, would make that module unable to run out
    of process, which is precisely the thing this class exists to support. So the
    duplication is the cost of the constraint, and it is a contained one: forty lines
    of ctypes against a frozen Win32 API.

    Every failure is non-fatal and recorded in :attr:`reason`. A module that runs but
    might orphan under a hard kill beats a module that will not load, and the host
    surfaces the reason on the record instead of swallowing it.
    """

    _k32: Any = None
    _extended_limit: Any = None

    def __init__(self) -> None:
        self.handle: Any = None
        self.reason: str = ""
        if not IS_WINDOWS:
            # POSIX orphaning is a different problem with a different answer (a
            # process group, or PR_SET_PDEATHSIG on Linux). Saying so beats a bare
            # False that reads as "unsupported, cause unknown".
            self.reason = "not Windows; job objects do not exist here"
            return
        try:
            self.handle = self._create()
        except Exception as exc:  # pragma: no cover - a broken kernel32 is not our bug
            self.reason = f"{type(exc).__name__}: {exc}"

    # -- the ctypes layer, bound once ----------------------------------------

    @classmethod
    def _bind(cls):
        if cls._k32 is not None:
            return cls._k32, cls._extended_limit
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),  # ULONG_PTR
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.OpenProcess.restype = wintypes.HANDLE
        cls._k32, cls._extended_limit = k32, EXTENDED_LIMIT
        return k32, EXTENDED_LIMIT

    def _create(self) -> Any:
        import ctypes

        k32, extended = self._bind()
        job = k32.CreateJobObjectW(None, None)
        if not job:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        info = extended()
        info.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        # 9 == JobObjectExtendedLimitInformation
        if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            err = ctypes.get_last_error()
            k32.CloseHandle(job)
            raise OSError(err, "SetInformationJobObject failed")
        return job

    # -- the two verbs -------------------------------------------------------

    def adopt(self, pid: int) -> str:
        """Put ``pid`` -- and everything it goes on to start -- in the job.

        Returns ``""`` on success and a sentence on failure, never raising: the
        caller has a live child either way and has to decide what to do about it.
        """
        if self.handle is None:
            return self.reason or "no job object"
        import ctypes

        k32, _ = self._bind()
        handle = k32.OpenProcess(0x0100 | 0x0001, False, int(pid))  # SET_QUOTA|TERMINATE
        if not handle:
            return f"OpenProcess({pid}) failed with error {ctypes.get_last_error()}"
        try:
            if not k32.AssignProcessToJobObject(self.handle, handle):
                return (
                    f"AssignProcessToJobObject({pid}) failed with error "
                    f"{ctypes.get_last_error()}; this module will not be killed if the "
                    "core is terminated abruptly"
                )
        finally:
            k32.CloseHandle(handle)
        return ""

    def release(self) -> bool:
        """Close the handle, which kills every process in the job.

        Idempotent; ``True`` if this call is what did it.
        """
        if self.handle is None:
            return False
        k32, _ = self._bind()
        handle, self.handle = self.handle, None
        k32.CloseHandle(handle)
        return True


def child_jail_supported() -> tuple[bool, str]:
    """Can this platform give the hard-kill guarantee? Answered by building a job and
    throwing it away, because the only honest answer is a real one."""
    probe = ChildJail()
    ok = probe.handle is not None
    reason = probe.reason
    probe.release()
    return ok, reason
