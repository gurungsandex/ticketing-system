"""
Single-instance guard.

The client previously used QSharedMemory. On macOS and Linux a POSIX shared
memory segment outlives the process that created it, so after a hard kill or a
crash the orphaned segment made every subsequent launch believe another copy
was running — the client would exit immediately and never come back. That
directly defeats "restarts after a crash", and the only recovery was a reboot
or manual cleanup.

This uses an advisory lock on a file instead. The operating system releases the
lock when the owning process dies, however it dies, so a crashed client leaves
nothing to clean up and the next launch acquires the lock normally.

Scope: the lock file lives in the per-user application data directory, so one
instance runs per logged-on user. On Windows that is also per Terminal Services
session for different users; two simultaneous sessions of the *same* user share
the directory and therefore the lock.
"""
import os
import sys
from pathlib import Path
from typing import Optional


class SingleInstance:
    """Acquire with `acquire()`; keep the object alive for the process
    lifetime. Releasing is automatic on exit, but `release()` is available for
    orderly shutdown."""

    def __init__(self, name: str = "it-ticketing-client"):
        self._name = name
        self._handle = None
        self._path = self._lock_path()

    def _lock_path(self) -> Path:
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support" / "HelpdeskClient"
        elif sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA")
                        or os.environ.get("APPDATA")
                        or Path.home()) / "HelpdeskClient"
        else:
            base = Path(os.environ.get("XDG_RUNTIME_DIR")
                        or Path.home()) / ".helpdesk-client"
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return base / f"{self._name}.lock"

    def acquire(self) -> bool:
        """True if this process now owns the lock, False if another live
        instance holds it. On any unexpected error we return True: failing open
        keeps the client usable, which matters more than strict exclusivity."""
        try:
            # Opened without truncating so a live owner's PID stays readable.
            self._handle = open(self._path, "a+")
        except OSError:
            return True

        try:
            if sys.platform == "win32":
                import msvcrt
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # Held by a running instance.
            self._close()
            return False
        except ImportError:
            return True

        # Record the owner's PID — purely diagnostic, for support to confirm
        # which process holds the lock.
        try:
            self._handle.seek(0)
            self._handle.truncate()
            self._handle.write(str(os.getpid()))
            self._handle.flush()
        except OSError:
            pass
        return True

    def owner_pid(self) -> Optional[int]:
        """PID recorded in the lock file, if readable. Diagnostic only."""
        try:
            raw = self._path.read_text(encoding="utf-8").strip()
            return int(raw) if raw else None
        except (OSError, ValueError):
            return None

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except (OSError, ImportError):
            pass
        self._close()

    def _close(self) -> None:
        try:
            if self._handle is not None:
                self._handle.close()
        except OSError:
            pass
        self._handle = None
