"""
OS-backed secret storage for the desktop client.

What is actually secret here
----------------------------
The client has no user account. Its identity is the client_id: a random uuid
generated on first run that the server treats as a bearer secret — whoever
presents it can read that machine's ticket statuses and post into its live chat
session. It was stored in a plaintext file in the user's roaming profile, where
any process running as that user, any backup, and anything that syncs %APPDATA%
could read it.

This moves it into the OS credential store — Windows Credential Manager, macOS
Keychain, or a Secret Service / kwallet backend on Linux — where it is
protected by the user's login credentials and not readable from a roaming
profile copy.

Migration and fallback
----------------------
An existing plaintext client_id is migrated into the credential store on first
run and the plaintext file is then removed. If no keyring backend is available
(a locked-down build, a headless session, keyring not installed), storage falls
back to the previous file so the client keeps working — degraded, not broken.
Which path was taken is reported by `backend_name()` for support.
"""
import sys
from pathlib import Path
from typing import Optional

SERVICE_NAME = "IT Ticketing System"

try:  # keyring is optional: the client must still run without it.
    import keyring
    from keyring.errors import KeyringError
    _KEYRING_IMPORTED = True
except ImportError:  # pragma: no cover - exercised via _force_no_keyring in tests
    keyring = None
    KeyringError = Exception
    _KEYRING_IMPORTED = False

_force_no_keyring = False


def _keyring_available() -> bool:
    """True when a real, usable backend is present.

    keyring always imports; what varies is whether it resolves to a working
    backend. The `fail` backend raises on use and `chainer`/`null` silently
    drop writes, so a value is round-tripped rather than trusted blindly.
    """
    if _force_no_keyring or not _KEYRING_IMPORTED:
        return False
    try:
        backend = keyring.get_keyring()
        name = f"{type(backend).__module__}.{type(backend).__name__}".lower()
        if "fail" in name or "null" in name:
            return False
        return True
    except (KeyringError, RuntimeError, OSError):
        return False


def backend_name() -> str:
    """Human-readable name of the active store, for the troubleshooting doc."""
    if not _keyring_available():
        return "file (no OS credential store available)"
    try:
        backend = keyring.get_keyring()
        return type(backend).__name__
    except (KeyringError, RuntimeError, OSError):
        return "file (no OS credential store available)"


# ── File fallback ─────────────────────────────────────

def _storage_dir() -> Path:
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "HelpdeskClient"
    else:
        import os
        d = Path(os.environ.get("APPDATA", str(Path.home()))) / "HelpdeskClient"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _file_path(key: str) -> Path:
    return _storage_dir() / f"{key}.txt"


def _read_file(key: str) -> Optional[str]:
    p = _file_path(key)
    try:
        if p.exists():
            value = p.read_text(encoding="utf-8").strip()
            return value or None
    except OSError:
        pass
    return None


def _write_file(key: str, value: str) -> bool:
    p = _file_path(key)
    try:
        p.write_text(value, encoding="utf-8")
        # Owner-only where the platform supports it.
        try:
            p.chmod(0o600)
        except (OSError, NotImplementedError):
            pass
        return True
    except OSError:
        return False


def _delete_file(key: str) -> None:
    try:
        p = _file_path(key)
        if p.exists():
            p.unlink()
    except OSError:
        pass


# ── Public API ────────────────────────────────────────

def get_secret(key: str) -> Optional[str]:
    """Read a secret, migrating a legacy plaintext value into the OS store."""
    if _keyring_available():
        try:
            value = keyring.get_password(SERVICE_NAME, key)
            if value:
                return value
        except (KeyringError, RuntimeError, OSError):
            pass

        # Not in the credential store yet — migrate a legacy plaintext value.
        legacy = _read_file(key)
        if legacy:
            if set_secret(key, legacy):
                _delete_file(key)
            return legacy
        return None

    return _read_file(key)


def set_secret(key: str, value: str) -> bool:
    """Store a secret. Returns True if it was written somewhere durable."""
    if _keyring_available():
        try:
            keyring.set_password(SERVICE_NAME, key, value)
            # Confirm the backend really kept it — some chainer configurations
            # accept a write and return nothing on read.
            if keyring.get_password(SERVICE_NAME, key) == value:
                return True
        except (KeyringError, RuntimeError, OSError):
            pass
    return _write_file(key, value)


def delete_secret(key: str) -> None:
    """Remove a secret from both the credential store and the legacy file."""
    if _keyring_available():
        try:
            keyring.delete_password(SERVICE_NAME, key)
        except (KeyringError, RuntimeError, OSError):
            pass
    _delete_file(key)
