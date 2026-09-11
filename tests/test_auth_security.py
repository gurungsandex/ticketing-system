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


# ── Tokens must never be accepted from the URL ────────
#
# A query-string JWT is written to every access log on the request path, kept
# in browser history and can leak via Referer. These endpoints are header-only.

def test_download_rejects_token_in_query_string(client, admin_headers):
    t = new_ticket(client)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    up = client.post(
        f"/tickets/{t['id']}/attachments",
        files={"file": ("shot.png", png, "image/png")},
    )
    assert up.status_code == 200, up.text
    att_id = up.json()["id"]

    token = admin_headers["Authorization"].split(" ", 1)[1]

    # Valid token, but presented in the URL -> must be refused.
    r = client.get(f"/attachments/{att_id}/download?token={token}")
    assert r.status_code == 401, r.text

    # Same token in the Authorization header -> works.
    r = client.get(f"/attachments/{att_id}/download", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.content == png


def test_ticket_list_rejects_token_in_query_string(client, admin_headers):
    token = admin_headers["Authorization"].split(" ", 1)[1]
    assert client.get(f"/tickets/?token={token}").status_code == 401
    assert client.get("/tickets/", headers=admin_headers).status_code == 200
