"""
Stable per-machine client identity.

The client_id is not just a label: the server accepts it as a bearer secret for
reading this machine's ticket statuses and for posting into its live chat
session. It is therefore kept in the OS credential store (Windows Credential
Manager / macOS Keychain) rather than a plaintext file — see secret_store.
"""
import os
import sys
import uuid
from pathlib import Path

import secret_store

_CLIENT_ID_KEY = "client_id"


def _get_storage_dir() -> Path:
    if sys.platform == "darwin":
        storage = Path.home() / "Library" / "Application Support" / "HelpdeskClient"
    else:
        storage = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "HelpdeskClient"
    storage.mkdir(parents=True, exist_ok=True)
    return storage


def get_client_id() -> str:
    """Return this machine's client id, creating one on first run.

    An id written by an older build into client_id.txt is migrated into the
    credential store by secret_store.get_secret, so upgrading does not orphan a
    machine's existing tickets.
    """
    existing = secret_store.get_secret(_CLIENT_ID_KEY)
    if existing:
        return existing

    new_id = str(uuid.uuid4())
    secret_store.set_secret(_CLIENT_ID_KEY, new_id)
    return new_id


def is_first_launch() -> bool:
    return secret_store.get_secret(_CLIENT_ID_KEY) is None
