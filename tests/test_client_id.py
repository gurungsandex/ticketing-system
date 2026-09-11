"""
Client identity storage and credential-store migration.

These run without PySide6 or a real keyring backend: the client_app directory
is put on sys.path and the credential store is faked, so the migration logic is
exercised on any CI box.
"""
import importlib.util
import uuid
from pathlib import Path

import pytest

# Load client_app/client_id.py directly by path. client_app/ must NOT go on
# sys.path: it contains main.py, config.py and settings.py, which would shadow
# the backend modules of the same name for every other test in this suite.
_SRC = Path(__file__).resolve().parent.parent / "client_app" / "client_id.py"
_spec = importlib.util.spec_from_file_location("_client_id_under_test", _SRC)
cid_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cid_mod)


class FakeKeyring:
    """Stands in for the Windows Credential Manager / macOS Keychain."""

    def __init__(self, writable=True, readable=True):
        self.store = {}
        self.writable = writable
        self.readable = readable

    def get_password(self, service, entry):
        if not self.readable:
            return None
        return self.store.get((service, entry))

    def set_password(self, service, entry, value):
        if not self.writable:
            raise RuntimeError("credential store locked")
        self.store[(service, entry)] = value


@pytest.fixture()
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(cid_mod, "_get_storage_dir", lambda: tmp_path)
    return tmp_path


def _use(monkeypatch, kr):
    monkeypatch.setattr(cid_mod, "_keyring", lambda: kr)


def test_new_install_stores_id_in_credential_store_not_on_disk(storage, monkeypatch):
    kr = FakeKeyring()
    _use(monkeypatch, kr)

    got = cid_mod.get_client_id()

    assert uuid.UUID(got)
    assert kr.store[("IT Ticketing System", "client_id")] == got
    assert not (storage / "client_id.txt").exists(), "secret must not be left on disk"


def test_existing_id_is_returned_stably(storage, monkeypatch):
    kr = FakeKeyring()
    _use(monkeypatch, kr)
    first = cid_mod.get_client_id()
    assert cid_mod.get_client_id() == first


def test_legacy_file_is_migrated_and_removed(storage, monkeypatch):
    legacy = "11111111-2222-3333-4444-555555555555"
    (storage / "client_id.txt").write_text(legacy, encoding="utf-8")
    kr = FakeKeyring()
    _use(monkeypatch, kr)

    got = cid_mod.get_client_id()

    # Identity must be preserved -- it ties the user to their ticket history.
    assert got == legacy
    assert kr.store[("IT Ticketing System", "client_id")] == legacy
    assert not (storage / "client_id.txt").exists()


def test_legacy_file_survives_when_credential_store_write_fails(storage, monkeypatch):
    """If the store can't persist, deleting the only copy would orphan the user."""
    legacy = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    (storage / "client_id.txt").write_text(legacy, encoding="utf-8")
    _use(monkeypatch, FakeKeyring(writable=False))

    got = cid_mod.get_client_id()

    assert got == legacy
    assert (storage / "client_id.txt").exists()


def test_legacy_file_survives_when_store_accepts_but_does_not_persist(storage, monkeypatch):
    """A write that silently doesn't stick must not count as success."""
    legacy = "aaaaaaaa-bbbb-cccc-dddd-ffffffffffff"
    (storage / "client_id.txt").write_text(legacy, encoding="utf-8")
    _use(monkeypatch, FakeKeyring(readable=False))

    got = cid_mod.get_client_id()

    assert got == legacy
    assert (storage / "client_id.txt").exists()


def test_falls_back_to_file_when_no_keyring_available(storage, monkeypatch):
    monkeypatch.setattr(cid_mod, "_keyring", lambda: None)

    got = cid_mod.get_client_id()

    assert uuid.UUID(got)
    assert (storage / "client_id.txt").read_text(encoding="utf-8").strip() == got
    assert cid_mod.get_client_id() == got


def test_is_first_launch(storage, monkeypatch):
    kr = FakeKeyring()
    _use(monkeypatch, kr)
    assert cid_mod.is_first_launch() is True
    cid_mod.get_client_id()
    assert cid_mod.is_first_launch() is False
