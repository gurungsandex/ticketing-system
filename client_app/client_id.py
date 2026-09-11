"""
Client identity, stored in the OS credential store.

The client_id is not a cosmetic identifier: chat sessions and notification
lookups are scoped by it, and the public (unauthenticated) chat endpoints treat
it as a bearer secret -- anyone holding a client_id can read that user's chat
history. It therefore belongs in the platform credential store, not a
world-readable text file in the user's profile.

Storage order:
  1. Windows Credential Manager / macOS Keychain (via `keyring`).
  2. client_id.txt in the app-data directory -- legacy location, still read so
     existing installs keep their identity, and still used as a fallback where
     no credential store is available (e.g. a headless Linux test box).

Migration is deliberately conservative. An existing plaintext id is copied into
the credential store and the file is removed ONLY after the value has been read
back successfully. If the store silently fails to persist, deleting the file
first would orphan the user from their own ticket and chat history.
"""
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

_SERVICE = "IT Ticketing System"
_ENTRY = "client_id"


def _get_storage_dir() -> Path:
    if sys.platform == "darwin":
        storage = Path.home() / "Library" / "Application Support" / "HelpdeskClient"
    else:
        storage = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "HelpdeskClient"
    storage.mkdir(parents=True, exist_ok=True)
    return storage


def _id_file() -> Path:
    return _get_storage_dir() / "client_id.txt"


# ── Credential store access ───────────────────────────
# Wrapped so a missing/!broken backend degrades to the file instead of
# crashing the client on startup, and so tests can substitute a fake.

def _keyring():
    try:
        import keyring
        return keyring
    except Exception:
        return None


def _keyring_get() -> Optional[str]:
    kr = _keyring()
    if kr is None:
        return None
    try:
        value = kr.get_password(_SERVICE, _ENTRY)
    except Exception:
        return None
    return value.strip() if value and value.strip() else None


def _keyring_set(value: str) -> bool:
    """Write to the credential store and confirm it reads back.

    The read-back matters: some backends (a locked keychain, a stubbed
    SecretService) accept the write and return nothing afterwards. Reporting
    success there would let the caller delete the only surviving copy.
    """
    kr = _keyring()
    if kr is None:
        return False
    try:
        kr.set_password(_SERVICE, _ENTRY, value)
    except Exception:
        return False
    return _keyring_get() == value


def _read_legacy_file() -> Optional[str]:
    try:
        p = _id_file()
        if not p.exists():
            return None
        cid = p.read_text(encoding="utf-8").strip()
        return cid or None
    except Exception:
        return None


def _write_legacy_file(value: str) -> None:
    try:
        p = _id_file()
        p.write_text(value, encoding="utf-8")
        # Owner-only where the OS supports it.
        try:
            os.chmod(p, 0o600)
        except (OSError, NotImplementedError):
            pass
    except Exception:
        pass


def get_client_id() -> str:
    """Return this machine's client id, creating one on first run."""
    stored = _keyring_get()
    if stored:
        return stored

    # Existing install: promote the plaintext id into the credential store.
    legacy = _read_legacy_file()
    if legacy:
        if _keyring_set(legacy):
            try:
                _id_file().unlink()
            except OSError:
                pass
        return legacy

    new_id = str(uuid.uuid4())
    if not _keyring_set(new_id):
        # No usable credential store -- keep working, just less privately.
        _write_legacy_file(new_id)
    return new_id


def is_first_launch() -> bool:
    return _keyring_get() is None and _read_legacy_file() is None
