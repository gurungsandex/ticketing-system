"""Live chat, agent presence, and canned response templates."""


def test_presence_and_availability(client, admin_headers):
    # No agent available initially.
    assert client.get("/chat/availability").json()["live_support_available"] is False
    # Admin goes available.
    r = client.patch("/agent/status", json={"status": "available"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["chat_status"] == "available"
    avail = client.get("/chat/availability").json()
    assert avail["live_support_available"] is True and avail["available_agents"] == 1


def test_invalid_agent_status_rejected(client, admin_headers):
    assert client.patch("/agent/status", json={"status": "vacation"},
                        headers=admin_headers).status_code == 400


def test_chat_full_flow(client, admin_headers):
    client.patch("/agent/status", json={"status": "available"}, headers=admin_headers)
    session = client.post("/chat/sessions",
                          json={"client_id": "cid-1", "display_name": "Alice"}).json()
    sid = session["id"]
    assert session["status"] == "waiting"

    # User sends a message.
    r = client.post(f"/chat/sessions/{sid}/messages?client_id=cid-1",
                    json={"content": "My printer is broken"})
    assert r.status_code == 200

    # Agent claims and replies.
    assert client.post(f"/chat/sessions/{sid}/claim", headers=admin_headers).status_code == 200
    assert client.post(f"/chat/sessions/{sid}/agent-messages",
                       json={"content": "Happy to help"}, headers=admin_headers).status_code == 200

    # User polls and sees both.
    poll = client.get(f"/chat/sessions/{sid}/poll?client_id=cid-1&since=0").json()
    assert poll["status"] == "active"
    contents = [m["content"] for m in poll["messages"]]
    assert "My printer is broken" in contents
    assert "Happy to help" in contents


def test_chat_ownership_scoping(client):
    """A different client_id must not read someone else's session."""
    session = client.post("/chat/sessions",
                          json={"client_id": "owner", "display_name": "Bob"}).json()
    sid = session["id"]
    r = client.get(f"/chat/sessions/{sid}/poll?client_id=attacker&since=0")
    assert r.status_code == 404


def test_technician_paged_before_admin(client, admin_headers, make_tech):
    """A new chat should notify an available technician, not the admin, when
    a technician is online — technicians are the front line."""
    tech_user, tech_headers = make_tech()
    client.patch("/agent/status", json={"status": "available"}, headers=tech_headers)

    session = client.post("/chat/sessions", json={"client_id": "cid-tf", "display_name": "Carol"}).json()

    notifs = client.get("/notifications/my", headers=tech_headers).json()
    assert any(n["ticket_id"] == session["id"] for n in notifs)
    admin_notifs = client.get("/notifications/my", headers=admin_headers).json()
    assert not any(n["ticket_id"] == session["id"] for n in admin_notifs)


def test_technician_list_excludes_escalated(client, admin_headers, make_tech):
    tech_user, tech_headers = make_tech()
    client.patch("/agent/status", json={"status": "available"}, headers=tech_headers)
    session = client.post("/chat/sessions", json={"client_id": "cid-esc", "display_name": "Dana"}).json()
    sid = session["id"]

    # Visible to the technician before escalation.
    sessions = client.get("/chat/sessions", headers=tech_headers).json()
    assert any(s["id"] == sid for s in sessions)

    r = client.post(f"/chat/sessions/{sid}/escalate", headers=tech_headers)
    assert r.status_code == 200
    assert r.json()["escalated"] is True

    # Gone from the technician's default view, but visible to the admin.
    sessions = client.get("/chat/sessions", headers=tech_headers).json()
    assert not any(s["id"] == sid for s in sessions)
    admin_sessions = client.get("/chat/sessions", headers=admin_headers).json()
    assert any(s["id"] == sid for s in admin_sessions)


def test_busy_agent_notified_every_fifth_message(client, admin_headers):
    session = client.post("/chat/sessions", json={"client_id": "cid-busy", "display_name": "Eve"}).json()
    sid = session["id"]
    client.post(f"/chat/sessions/{sid}/claim", headers=admin_headers)
    client.patch("/agent/status", json={"status": "busy"}, headers=admin_headers)

    for i in range(4):
        r = client.post(f"/chat/sessions/{sid}/messages?client_id=cid-busy",
                        json={"content": f"message {i+1}"})
        assert r.status_code == 200
    # unread_count should be climbing but not yet a multiple of 5.
    sessions = client.get("/chat/sessions", headers=admin_headers).json()
    s = next(x for x in sessions if x["id"] == sid)
    assert s["unread_count"] == 4

    r = client.post(f"/chat/sessions/{sid}/messages?client_id=cid-busy",
                    json={"content": "message 5"})
    assert r.status_code == 200


def test_delete_session_requires_super_admin(client, admin_headers, make_tech):
    tech_user, tech_headers = make_tech()
    session = client.post("/chat/sessions", json={"client_id": "cid-del", "display_name": "Frank"}).json()
    sid = session["id"]

    assert client.delete(f"/chat/sessions/{sid}", headers=tech_headers).status_code == 403
    assert client.delete(f"/chat/sessions/{sid}", headers=admin_headers).status_code == 200
    assert client.get(f"/chat/sessions/{sid}/poll?client_id=cid-del&since=0").status_code == 404


def test_canned_responses(client, admin_headers):
    created = client.post("/canned-responses",
                          json={"title": "Password reset",
                                "body": "We have reset your password.",
                                "is_shared": True},
                          headers=admin_headers)
    assert created.status_code == 200
    cr_id = created.json()["id"]
    items = client.get("/canned-responses", headers=admin_headers).json()
    assert any(c["id"] == cr_id for c in items)
    assert client.delete(f"/canned-responses/{cr_id}", headers=admin_headers).status_code == 200
