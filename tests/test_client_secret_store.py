"""The client_id is a bearer secret, so it belongs in the OS credential store.

These tests use a stub keyring backend rather than the real Credential Manager
or Keychain, so they run headlessly on any platform. What they pin is the
contract the client depends on: a secret survives a restart, a legacy plaintext
value is migrated and then deleted, and the client still works when no
credential store exists at all.
"""
import sys
from pathlib import Path

import pytest

CLIENT_APP = Path(__file__).resolve().parent.parent / "client_app"

_SHADOWED = ("config", "settings", "secret_store", "client_id")


class StubKeyring:
    """Stands in for a working OS credential store."""

    def __init__(self):
        self.store = {}

    def get_password(self, service, key):
        return self.store.get((service, key))

    def set_password(self, service, key, value):
        self.store[(service, key)] = value

    def delete_password(self, service, key):
        self.store.pop((service, key), None)

    def get_keyring(self):
        return self


@pytest.fixture()
def client_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    saved_modules = {name: sys.modules.get(name) for name in _SHADOWED}
    saved_path = list(sys.path)
    for name in _SHADOWED:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(CLIENT_APP))
    try:
        yield tmp_path
    finally:
        sys.path[:] = saved_path
        for name in _SHADOWED:
            sys.modules.pop(name, None)
            if saved_modules[name] is not None:
                sys.modules[name] = saved_modules[name]


@pytest.fixture()
def with_keyring(client_env, monkeypatch):
    import secret_store

    stub = StubKeyring()
    monkeypatch.setattr(secret_store, "keyring", stub)
    monkeypatch.setattr(secret_store, "_KEYRING_IMPORTED", True)
    monkeypatch.setattr(secret_store, "_force_no_keyring", False)
    return secret_store, stub


@pytest.fixture()
def without_keyring(client_env, monkeypatch):
    import secret_store

    monkeypatch.setattr(secret_store, "_force_no_keyring", True)
    return secret_store


# ── Storage in the credential store ───────────────────

def test_secret_round_trips_through_credential_store(with_keyring):
    secret_store, stub = with_keyring

    assert secret_store.set_secret("client_id", "abc-123") is True
    assert secret_store.get_secret("client_id") == "abc-123"
    # It really went to the credential store, not to disk.
    assert stub.store[(secret_store.SERVICE_NAME, "client_id")] == "abc-123"


def test_secret_is_not_written_to_disk_when_keyring_works(with_keyring, client_env):
    secret_store, _ = with_keyring
    secret_store.set_secret("client_id", "abc-123")

    plaintext = client_env / "HelpdeskClient" / "client_id.txt"
    assert not plaintext.exists(), "secret must not also be left in plaintext"


def test_missing_secret_returns_none(with_keyring):
    secret_store, _ = with_keyring
    assert secret_store.get_secret("nothing-here") is None


def test_delete_removes_the_secret(with_keyring):
    secret_store, _ = with_keyring
    secret_store.set_secret("client_id", "abc-123")
    secret_store.delete_secret("client_id")
    assert secret_store.get_secret("client_id") is None


# ── Migration from the old plaintext file ─────────────

def test_legacy_plaintext_id_is_migrated_and_removed(with_keyring, client_env):
    """Upgrading must not orphan a machine's existing tickets, and must not
    leave the old readable copy behind."""
    secret_store, stub = with_keyring
    legacy = client_env / "HelpdeskClient"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "client_id.txt").write_text("legacy-uuid-value", encoding="utf-8")

    assert secret_store.get_secret("client_id") == "legacy-uuid-value"
    assert stub.store[(secret_store.SERVICE_NAME, "client_id")] == "legacy-uuid-value"
    assert not (legacy / "client_id.txt").exists(), "plaintext copy must be removed"


def test_migrated_id_is_stable_on_next_read(with_keyring, client_env):
    secret_store, _ = with_keyring
    legacy = client_env / "HelpdeskClient"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "client_id.txt").write_text("legacy-uuid-value", encoding="utf-8")

    first = secret_store.get_secret("client_id")
    second = secret_store.get_secret("client_id")
    assert first == second == "legacy-uuid-value"


# ── Degraded mode: no credential store available ──────

def test_falls_back_to_file_without_keyring(without_keyring, client_env):
    """A client with no usable backend must keep working, not fail to start."""
    secret_store = without_keyring

    assert secret_store.set_secret("client_id", "fallback-id") is True
    assert secret_store.get_secret("client_id") == "fallback-id"
    assert (client_env / "HelpdeskClient" / "client_id.txt").exists()


def test_backend_name_reports_fallback(without_keyring):
    assert "file" in without_keyring.backend_name()


# ── client_id module behaviour ────────────────────────

def test_client_id_is_generated_once_and_reused(with_keyring):
    import client_id

    first = client_id.get_client_id()
    second = client_id.get_client_id()
    assert first == second
    assert len(first) == 36, "expected a uuid4 string"


def test_client_id_survives_a_restart(with_keyring):
    """A new process must see the same id — otherwise every launch would look
    like a brand-new machine and lose its ticket history."""
    import client_id

    first = client_id.get_client_id()

    sys.modules.pop("client_id", None)
    import client_id as client_id_reloaded

    assert client_id_reloaded.get_client_id() == first


def test_first_launch_detection(with_keyring):
    import client_id

    assert client_id.is_first_launch() is True
    client_id.get_client_id()
    assert client_id.is_first_launch() is False


def test_client_id_migrates_from_legacy_file(with_keyring, client_env):
    import client_id

    legacy = client_env / "HelpdeskClient"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "client_id.txt").write_text("11111111-2222-3333-4444-555555555555",
                                          encoding="utf-8")

    assert client_id.get_client_id() == "11111111-2222-3333-4444-555555555555"
