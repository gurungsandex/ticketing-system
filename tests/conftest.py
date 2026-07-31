"""
Shared pytest fixtures.

Each test module gets an isolated, temporary SQLite database and a fresh app
import so state never leaks between runs. Environment variables must be set
BEFORE backend modules are imported, because config.py reads them at import
time.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

# Generous limits so functional tests never trip the rate limiter; the limiter
# itself is unit-tested separately in test_security.py.
os.environ.setdefault("SECRET_KEY", "pytest-secret-key")
os.environ.setdefault("RATE_LIMIT_TICKET_CREATE", "100000")
os.environ.setdefault("RATE_LIMIT_ATTACHMENT", "100000")
os.environ.setdefault("RATE_LIMIT_LOGIN", "100000")


@pytest.fixture()
def client():
    """A TestClient backed by a throwaway database file."""
    from fastapi.testclient import TestClient

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    # Import fresh so the engine binds to this test's DATABASE_URL.
    for mod in list(sys.modules):
        if mod in {"database", "models", "main", "auth", "config"} or mod.startswith("routers"):
            sys.modules.pop(mod, None)

    import main  # noqa: F401
    from main import app

    with TestClient(app) as c:
        yield c

    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(db_path + suffix)
        except OSError:
            pass


@pytest.fixture()
def admin_headers(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture()
def make_tech(client, admin_headers):
    """Factory that creates a technician and returns (username, headers)."""
    def _make(username: str | None = None, password: str = "techpass123"):
        username = username or f"tech_{uuid.uuid4().hex[:6]}"
        r = client.post(
            "/admin/users",
            json={"username": username, "password": password, "role": "technician"},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        lr = client.post("/auth/login", json={"username": username, "password": password})
        return username, {"Authorization": "Bearer " + lr.json()["access_token"]}

    return _make


def new_ticket(client, **overrides):
    payload = {
        "client_id": "client-1",
        "ip_address": "192.168.1.10",
        "hostname": "HOST-1",
        "category": "Printer",
    }
    payload.update(overrides)
    r = client.post("/tickets/", json=payload)
    assert r.status_code == 200, r.text
    return r.json()
