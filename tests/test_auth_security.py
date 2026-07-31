"""Auth, RBAC, and HTTP security hardening."""
from conftest import new_ticket


def test_login_and_bad_password(client):
    assert client.post("/auth/login",
                       json={"username": "admin", "password": "admin123"}).status_code == 200
    assert client.post("/auth/login",
                       json={"username": "admin", "password": "wrong"}).status_code == 401


def test_change_password_requires_current(client, admin_headers):
    r = client.patch("/auth/change-password",
                     json={"current_password": "nope", "new_password": "longenough1"},
                     headers=admin_headers)
    assert r.status_code == 400


def test_security_headers_present(client):
    h = client.get("/health").headers
    assert h.get("X-Content-Type-Options") == "nosniff"
    assert h.get("X-Frame-Options") == "DENY"
    assert "content-security-policy" in {k.lower() for k in h.keys()}


def test_default_admin_seeded(client):
    # The lifespan handler seeds the default admin.
    assert client.post("/auth/login",
                       json={"username": "admin", "password": "admin123"}).status_code == 200


def test_attachment_rejects_spoofed_content(client):
    t = new_ticket(client)
    # Claims to be a PNG but the bytes are not.
    files = {"file": ("evil.png", b"this is not really a png", "image/png")}
    r = client.post(f"/tickets/{t['id']}/attachments", files=files)
    assert r.status_code == 400


def test_attachment_accepts_real_png(client):
    t = new_ticket(client)
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    files = {"file": ("ok.png", png, "image/png")}
    r = client.post(f"/tickets/{t['id']}/attachments", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["filename"] == "ok.png"
