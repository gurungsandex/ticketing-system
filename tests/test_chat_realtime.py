"""Real-time chat delivery over WebSockets.

The chat previously relied on both sides polling every few seconds, so a reply
could sit unseen for most of that window. These tests pin the push path and,
more importantly, that opening a socket grants nothing the REST path did not.
"""
import pytest


def _start_session(client, client_id="cid-rt", name="Rita"):
    r = client.post("/chat/sessions", json={"client_id": client_id, "display_name": name})
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ── End-user channel ──────────────────────────────────

def test_user_socket_receives_agent_reply_immediately(client, admin_headers):
    """The point of the feature: the reply arrives as a pushed frame, with no
    poll in between."""
    sid = _start_session(client)
    client.post(f"/chat/sessions/{sid}/claim", headers=admin_headers)

    with client.websocket_connect(f"/ws/chat/client/{sid}?client_id=cid-rt") as ws:
        client.post(
            f"/chat/sessions/{sid}/agent-messages",
            json={"content": "Have you tried restarting it?"},
            headers=admin_headers,
        )
        frame = ws.receive_json()
        assert frame["type"] == "message"
        assert frame["content"] == "Have you tried restarting it?"
        assert frame["sender_role"] == "agent"


def test_user_socket_rejects_wrong_client_id(client):
    """Ownership scoping must hold on the socket exactly as it does on /poll —
    otherwise the socket is a way around it."""
    sid = _start_session(client, client_id="owner-rt")

    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/ws/chat/client/{sid}?client_id=attacker"
        ) as ws:
            ws.receive_json()


def test_user_socket_rejects_unknown_session(client):
    import uuid

    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/ws/chat/client/{uuid.uuid4()}?client_id=whatever"
        ) as ws:
            ws.receive_json()


def test_user_socket_requires_client_id(client):
    sid = _start_session(client)
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/chat/client/{sid}") as ws:
            ws.receive_json()


def test_user_socket_responds_to_ping(client):
    """Keeps the connection alive through idle-timeout proxies."""
    sid = _start_session(client)
    with client.websocket_connect(f"/ws/chat/client/{sid}?client_id=cid-rt") as ws:
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}


# ── Staff channel ─────────────────────────────────────

def test_staff_socket_receives_user_message_immediately(client, admin_headers):
    sid = _start_session(client)
    token = admin_headers["Authorization"].split(" ", 1)[1]

    with client.websocket_connect(f"/ws/chat/{sid}?token={token}") as ws:
        client.post(
            f"/chat/sessions/{sid}/messages?client_id=cid-rt",
            json={"content": "The printer is on fire"},
        )
        frame = ws.receive_json()
        assert frame["type"] == "message"
        assert frame["content"] == "The printer is on fire"
        assert frame["sender_role"] == "user"


def test_staff_socket_rejects_bad_token(client):
    sid = _start_session(client)
    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws/chat/{sid}?token=not-a-real-token") as ws:
            ws.receive_json()


def test_staff_socket_rejects_unknown_session(client, admin_headers):
    import uuid

    token = admin_headers["Authorization"].split(" ", 1)[1]
    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/ws/chat/{uuid.uuid4()}?token={token}"
        ) as ws:
            ws.receive_json()


# ── Typing indicator ──────────────────────────────────

def test_user_typing_reaches_the_agent(client, admin_headers):
    sid = _start_session(client)
    token = admin_headers["Authorization"].split(" ", 1)[1]

    with client.websocket_connect(f"/ws/chat/{sid}?token={token}") as staff_ws:
        with client.websocket_connect(
            f"/ws/chat/client/{sid}?client_id=cid-rt"
        ) as user_ws:
            user_ws.send_text("typing")
            frame = staff_ws.receive_json()
            assert frame["type"] == "typing"
            assert frame["sender_role"] == "user"


def test_agent_typing_reaches_the_user(client, admin_headers):
    sid = _start_session(client)
    token = admin_headers["Authorization"].split(" ", 1)[1]

    with client.websocket_connect(
        f"/ws/chat/client/{sid}?client_id=cid-rt"
    ) as user_ws:
        with client.websocket_connect(f"/ws/chat/{sid}?token={token}") as staff_ws:
            staff_ws.send_text("typing")
            frame = user_ws.receive_json()
            assert frame["type"] == "typing"
            assert frame["sender_role"] == "agent"
            assert frame["sender_name"] == "admin"


def test_typing_is_not_persisted(client, admin_headers):
    """A typing notice is ephemeral presence, not conversation history."""
    sid = _start_session(client)
    token = admin_headers["Authorization"].split(" ", 1)[1]

    with client.websocket_connect(f"/ws/chat/{sid}?token={token}") as ws:
        ws.send_text("typing")

    msgs = client.get(f"/chat/sessions/{sid}/messages", headers=admin_headers).json()
    assert all(m["content"] != "typing" for m in msgs)


# ── REST fallback stays intact ────────────────────────

def test_polling_still_works_alongside_sockets(client, admin_headers):
    """The socket is an optimisation, not a replacement — a client that cannot
    open one must still see the whole conversation."""
    sid = _start_session(client)
    client.post(f"/chat/sessions/{sid}/claim", headers=admin_headers)
    client.post(
        f"/chat/sessions/{sid}/agent-messages",
        json={"content": "polling reply"},
        headers=admin_headers,
    )

    poll = client.get(f"/chat/sessions/{sid}/poll?client_id=cid-rt&since=0").json()
    assert "polling reply" in [m["content"] for m in poll["messages"]]
