"""Attachment downloads must not carry a session JWT in the URL."""
import time

from conftest import new_ticket

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _attach(client, ticket_id):
    r = client.post(
        f"/tickets/{ticket_id}/attachments",
        files={"file": ("shot.png", PNG, "image/png")},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_session_jwt_is_rejected_in_download_url(client, admin_headers):
    """The whole point of the change: a session token in the query string must
    no longer authorise anything, so a leaked URL is worthless."""
    t = new_ticket(client)
    aid = _attach(client, t["id"])
    session_jwt = admin_headers["Authorization"].split(" ", 1)[1]

    r = client.get(f"/attachments/{aid}/download?token={session_jwt}")
    assert r.status_code == 401


def test_download_with_scoped_token_succeeds(client, admin_headers):
    t = new_ticket(client)
    aid = _attach(client, t["id"])

    issued = client.post(f"/attachments/{aid}/download-token", headers=admin_headers)
    assert issued.status_code == 200, issued.text
    token = issued.json()["token"]

    r = client.get(f"/attachments/{aid}/download?token={token}")
    assert r.status_code == 200
    assert r.content == PNG
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"


def test_download_token_is_scoped_to_one_attachment(client, admin_headers):
    """A token for file A must not fetch file B."""
    t = new_ticket(client)
    aid_a = _attach(client, t["id"])
    aid_b = _attach(client, t["id"])

    token_a = client.post(
        f"/attachments/{aid_a}/download-token", headers=admin_headers
    ).json()["token"]

    assert client.get(f"/attachments/{aid_b}/download?token={token_a}").status_code == 401


def test_download_requires_a_token(client, admin_headers):
    t = new_ticket(client)
    aid = _attach(client, t["id"])
    assert client.get(f"/attachments/{aid}/download").status_code == 422


def test_issuing_a_token_requires_authentication(client):
    t = new_ticket(client)
    aid = _attach(client, t["id"])
    assert client.post(f"/attachments/{aid}/download-token").status_code in (401, 403)


def test_technician_cannot_get_token_for_unassigned_ticket(client, admin_headers, make_tech):
    """Authorisation is enforced when the token is issued, not only at download."""
    _, tech_headers = make_tech()
    t = new_ticket(client)
    aid = _attach(client, t["id"])

    r = client.post(f"/attachments/{aid}/download-token", headers=tech_headers)
    assert r.status_code == 403


def test_download_rechecks_authorisation_against_current_state(
    client, admin_headers, make_tech
):
    """A token minted while a technician was assigned must stop working once
    the ticket is reassigned — the token is a carrier, not a grant."""
    tech_name, tech_headers = make_tech()
    other_name, _ = make_tech()
    t = new_ticket(client)
    aid = _attach(client, t["id"])

    client.patch(
        f"/tickets/{t['id']}/assign",
        json={"assigned_to": tech_name},
        headers=admin_headers,
    )
    token = client.post(
        f"/attachments/{aid}/download-token", headers=tech_headers
    ).json()["token"]

    # Still valid while assigned.
    assert client.get(f"/attachments/{aid}/download?token={token}").status_code == 200

    # Reassign away; the already-issued token must now be refused.
    client.patch(
        f"/tickets/{t['id']}/assign",
        json={"assigned_to": other_name},
        headers=admin_headers,
    )
    assert client.get(f"/attachments/{aid}/download?token={token}").status_code == 403


def test_download_token_expires(client, admin_headers, monkeypatch):
    """Short lifetime is the mitigation for a URL that gets logged."""
    import auth

    t = new_ticket(client)
    aid = _attach(client, t["id"])

    monkeypatch.setattr(auth, "DOWNLOAD_TOKEN_TTL_SECONDS", -1)
    token = auth.create_download_token("admin", aid)
    time.sleep(0.01)

    assert client.get(f"/attachments/{aid}/download?token={token}").status_code == 401


def test_download_token_cannot_authenticate_the_api(client, admin_headers):
    """A download token is signed with the same key as a session token, so it
    must be explicitly refused as an API credential — otherwise handing out a
    download link would hand out a minute of full API access."""
    t = new_ticket(client)
    aid = _attach(client, t["id"])
    token = client.post(
        f"/attachments/{aid}/download-token", headers=admin_headers
    ).json()["token"]

    r = client.get("/tickets/", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_session_token_still_authenticates_the_api(client, admin_headers):
    """The type check must not lock out ordinary sessions."""
    assert client.get("/tickets/", headers=admin_headers).status_code == 200
