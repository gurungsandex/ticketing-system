"""
Privileged-action audit trail.

Two properties matter and are pinned here: that privileged actions are
recorded, and that user-submitted free text (ticket bodies, chat messages,
passwords) never reaches the trail.
"""
from conftest import new_ticket


def _log(client, headers, **params):
    r = client.get("/audit", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ── Access control ────────────────────────────────────

def test_audit_requires_authentication(client):
    assert client.get("/audit").status_code == 401


def test_audit_requires_super_admin(client, make_tech):
    _, tech_headers = make_tech()
    assert client.get("/audit", headers=tech_headers).status_code == 403


# ── Auth events ───────────────────────────────────────

def test_successful_login_is_recorded(client, admin_headers):
    rows = _log(client, admin_headers, action="auth.login.success")
    assert any(r["actor"] == "admin" and r["success"] for r in rows)


def test_failed_login_is_recorded_without_the_password(client, admin_headers):
    client.post("/auth/login", json={"username": "admin", "password": "hunter2-wrong"})
    rows = _log(client, admin_headers, action="auth.login.failure")
    assert rows, "failed login was not recorded"
    entry = rows[0]
    assert entry["actor"] == "admin"
    assert entry["success"] is False
    # The submitted password must never appear anywhere in the record.
    assert "hunter2-wrong" not in str(entry)


def test_failed_login_for_unknown_user_is_recorded(client, admin_headers):
    client.post("/auth/login", json={"username": "ghost", "password": "x"})
    rows = _log(client, admin_headers, action="auth.login.failure", actor="ghost")
    assert len(rows) == 1


def test_password_change_is_recorded(client, admin_headers):
    r = client.patch("/auth/change-password",
                     json={"current_password": "admin123", "new_password": "a-longer-pass"},
                     headers=admin_headers)
    assert r.status_code == 200, r.text
    rows = _log(client, admin_headers, action="auth.password.change")
    assert rows and rows[0]["success"] is True
    assert "a-longer-pass" not in str(rows[0])


def test_rejected_password_change_is_recorded_as_failure(client, admin_headers):
    client.patch("/auth/change-password",
                 json={"current_password": "wrong", "new_password": "another-pass"},
                 headers=admin_headers)
    rows = _log(client, admin_headers, action="auth.password.change", success=False)
    assert rows, "rejected password change was not recorded"
    assert "another-pass" not in str(rows[0])


# ── Privileged actions ────────────────────────────────

def test_user_creation_and_deletion_are_recorded(client, admin_headers):
    r = client.post("/admin/users",
                    json={"username": "auditee", "password": "password123", "role": "technician"},
                    headers=admin_headers)
    assert r.status_code == 200, r.text
    created = _log(client, admin_headers, action="admin.user.create")
    assert created[0]["target"] == "auditee"
    assert created[0]["detail"] == "role=technician"
    assert "password123" not in str(created[0])

    client.delete(f"/admin/users/{r.json()['id']}", headers=admin_headers)
    deleted = _log(client, admin_headers, action="admin.user.delete")
    assert deleted[0]["target"] == "auditee"


def test_ticket_assignment_is_recorded(client, admin_headers, make_tech):
    username, _ = make_tech()
    t = new_ticket(client, description="PHI-LIKE-SECRET-TEXT")
    r = client.patch(f"/tickets/{t['id']}/assign",
                     json={"assigned_to": username}, headers=admin_headers)
    assert r.status_code == 200, r.text
    rows = _log(client, admin_headers, action="ticket.assign")
    assert rows[0]["target"] == t["id"]
    assert rows[0]["detail"] == f"assigned_to={username}"
    # The ticket body is user free text and must not be copied into the trail.
    assert "PHI-LIKE-SECRET-TEXT" not in str(rows[0])


def test_chat_session_deletion_is_recorded_without_message_text(client, admin_headers):
    s = client.post("/chat/sessions",
                    json={"client_id": "c-audit", "display_name": "User"}).json()
    client.post(f"/chat/sessions/{s['id']}/messages",
                params={"client_id": "c-audit"},
                json={"content": "CONFIDENTIAL-CHAT-BODY"})
    assert client.delete(f"/chat/sessions/{s['id']}", headers=admin_headers).status_code == 200

    rows = _log(client, admin_headers, action="chat.session.delete")
    assert rows[0]["target"] == s["id"]
    assert "CONFIDENTIAL-CHAT-BODY" not in str(rows[0])


def test_refused_self_update_is_recorded_as_failure(client, admin_headers):
    assert client.post("/update/apply", headers=admin_headers).status_code == 403
    rows = _log(client, admin_headers, action="server.update.apply")
    assert rows and rows[0]["success"] is False


# ── Query behaviour ───────────────────────────────────

def test_entries_are_newest_first_and_limited(client, admin_headers):
    for i in range(4):
        client.post("/admin/users",
                    json={"username": f"u{i}", "password": "password123", "role": "technician"},
                    headers=admin_headers)
    rows = _log(client, admin_headers, action="admin.user.create", limit=2)
    assert len(rows) == 2
    assert rows[0]["target"] == "u3"      # newest first
    assert rows[1]["target"] == "u2"


def test_audit_log_has_no_mutation_endpoints(client, admin_headers):
    """An audit trail its subjects can rewrite is not an audit trail."""
    assert client.delete("/audit", headers=admin_headers).status_code in (404, 405)
    assert client.post("/audit", headers=admin_headers).status_code in (404, 405)
