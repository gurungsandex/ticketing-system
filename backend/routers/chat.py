"""
Secure live chat, agent presence, and reusable response templates.

Design notes
------------
* End-user endpoints (used by the desktop client) are unauthenticated but
  scoped by the pair (session uuid + client_id). The client_id is a locally
  stored random uuid that acts as a bearer secret, so a caller can only read or
  post to a session they own. All public endpoints are rate limited.
* Staff endpoints require a valid JWT (any IT staff member).
* Response templates are inserted into the agent's editor by the frontend and
  are never auto-sent — this module only stores/returns them.
"""
import uuid
from typing import List, Optional

import config
import models
import schemas
from auth import decode_token, get_current_admin
from database import get_db
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from security import rate_limit
from sqlalchemy.orm import Session
from utils import utcnow
from websocket_manager import chat_hub, ws_manager

router = APIRouter()

VALID_AGENT_STATUSES = {"available", "busy", "away", "offline"}


def _touch(session: models.ChatSession) -> None:
    session.last_activity = utcnow()


def _msg_out(m: models.ChatMessage) -> dict:
    return {
        "id": m.id, "session_id": m.session_id, "sender_role": m.sender_role,
        "sender_name": m.sender_name,
        "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


# ══════════════════════════════════════════════════════
#  Agent presence
# ══════════════════════════════════════════════════════

@router.patch("/agent/status", response_model=schemas.AgentPresence)
def set_agent_status(
    body: schemas.AgentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    status = (body.status or "").lower()
    if status not in VALID_AGENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    current_user.chat_status = status
    current_user.chat_status_updated = utcnow()
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/agent/presence", response_model=List[schemas.AgentPresence])
def list_agent_presence(
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    return db.query(models.AdminUser).all()


# ══════════════════════════════════════════════════════
#  Canned response templates
# ══════════════════════════════════════════════════════

@router.get("/canned-responses", response_model=List[schemas.CannedResponseResponse])
def list_canned_responses(
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    # Shared templates + the caller's own private ones.
    return (
        db.query(models.CannedResponse)
        .filter(
            (models.CannedResponse.is_shared == True)  # noqa: E712
            | (models.CannedResponse.created_by == current_user.username)
        )
        .order_by(models.CannedResponse.title.asc())
        .all()
    )


@router.post("/canned-responses", response_model=schemas.CannedResponseResponse)
def create_canned_response(
    body: schemas.CannedResponseCreate,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    title = (body.title or "").strip()
    text = (body.body or "").strip()
    if not title or not text:
        raise HTTPException(status_code=400, detail="Title and body are required.")
    cr = models.CannedResponse(
        title=title[: config.MAX_GENERIC_TEXT_LEN],
        body=text[: config.MAX_DESCRIPTION_LEN],
        category=(body.category or None),
        created_by=current_user.username,
        is_shared=bool(body.is_shared),
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return cr


@router.delete("/canned-responses/{cr_id}")
def delete_canned_response(
    cr_id: int,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    cr = db.query(models.CannedResponse).filter(models.CannedResponse.id == cr_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Template not found")
    if cr.created_by != current_user.username and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="You can only delete your own templates.")
    db.delete(cr)
    db.commit()
    return {"deleted": cr_id}


# ══════════════════════════════════════════════════════
#  Live chat — public (end-user) endpoints
# ══════════════════════════════════════════════════════

def _count_available_agents(db: Session) -> int:
    return (
        db.query(models.AdminUser)
        .filter(models.AdminUser.chat_status == "available")
        .count()
    )


@router.get("/chat/availability", response_model=schemas.ChatAvailability)
def chat_availability(request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "chat_public", config.RATE_LIMIT_TICKET_CREATE)
    n = _count_available_agents(db)
    return {"live_support_available": n > 0, "available_agents": n}


@router.post("/chat/sessions", response_model=schemas.ChatSessionResponse)
def start_chat_session(
    body: schemas.ChatStartRequest, request: Request, db: Session = Depends(get_db)
):
    rate_limit(request, "chat_public", config.RATE_LIMIT_TICKET_CREATE)
    if not body.client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    # Reuse an existing open session for this client rather than piling up rows.
    existing = (
        db.query(models.ChatSession)
        .filter(
            models.ChatSession.client_id == body.client_id,
            models.ChatSession.status.in_(["waiting", "active"]),
        )
        .order_by(models.ChatSession.created_at.desc())
        .first()
    )
    if existing:
        return existing

    session = models.ChatSession(
        id=str(uuid.uuid4()),
        client_id=body.client_id,
        display_name=(body.display_name or "")[: config.MAX_GENERIC_TEXT_LEN] or None,
        hostname=(body.hostname or "")[: config.MAX_GENERIC_TEXT_LEN] or None,
        subject=(body.subject or "")[: config.MAX_GENERIC_TEXT_LEN] or None,
        status="waiting",
        created_at=utcnow(),
        last_activity=utcnow(),
    )
    db.add(session)

    # Notify all admins that a visitor is waiting for live support.
    who = session.display_name or "A user"
    msg = f"💬 {who} started a live chat" + (f": {session.subject}" if session.subject else "")
    for admin in db.query(models.AdminUser).filter(
        models.AdminUser.role == "super_admin"
    ).all():
        db.add(models.Notification(
            recipient_username=admin.username, ticket_id=session.id,
            event_type="chat", message=msg,
        ))
    db.commit()
    db.refresh(session)
    return session


def _verify_owner(db: Session, session_id: str, client_id: str) -> models.ChatSession:
    session = db.query(models.ChatSession).filter(
        models.ChatSession.id == session_id
    ).first()
    if not session or session.client_id != client_id:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.get("/chat/sessions/{session_id}/poll")
def poll_chat(
    session_id: str,
    request: Request,
    client_id: str = Query(...),
    since: int = Query(0),
    db: Session = Depends(get_db),
):
    """End-user polling: returns session status + messages newer than `since`."""
    rate_limit(request, "chat_poll", 240)  # generous; polled every few seconds
    session = _verify_owner(db, session_id, client_id)
    msgs = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session_id, models.ChatMessage.id > since)
        .order_by(models.ChatMessage.id.asc())
        .all()
    )
    return {
        "status": session.status,
        "agent_username": session.agent_username,
        "messages": [_msg_out(m) for m in msgs],
    }


@router.post("/chat/sessions/{session_id}/messages", response_model=schemas.ChatMessageResponse)
async def post_user_message(
    session_id: str,
    body: schemas.ChatMessageCreate,
    request: Request,
    client_id: str = Query(...),
    db: Session = Depends(get_db),
):
    rate_limit(request, "chat_post", 120)
    session = _verify_owner(db, session_id, client_id)
    if session.status == "closed":
        raise HTTPException(status_code=400, detail="This chat has been closed.")
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    content = content[: config.MAX_CHAT_MESSAGE_LEN]

    m = models.ChatMessage(
        session_id=session_id, sender_role="user",
        sender_name=session.display_name or "User", content=content, created_at=utcnow(),
    )
    db.add(m)
    _touch(session)
    db.commit()
    db.refresh(m)

    await chat_hub.publish(session_id, {"type": "message", **_msg_out(m)})
    # Ping the assigned agent (or all admins if unclaimed).
    targets = [session.agent_username] if session.agent_username else [
        a.username for a in db.query(models.AdminUser).filter(
            models.AdminUser.role == "super_admin").all()
    ]
    await ws_manager.broadcast_to_users(
        [t for t in targets if t],
        {"type": "chat_message", "session_id": session_id, "message": content},
    )
    return m


@router.post("/chat/sessions/{session_id}/close")
def close_chat_user(
    session_id: str,
    request: Request,
    client_id: str = Query(...),
    db: Session = Depends(get_db),
):
    rate_limit(request, "chat_post", 120)
    session = _verify_owner(db, session_id, client_id)
    session.status = "closed"
    session.closed_at = utcnow()
    db.commit()
    return {"status": "closed"}


# ══════════════════════════════════════════════════════
#  Live chat — staff endpoints
# ══════════════════════════════════════════════════════

@router.get("/chat/sessions", response_model=List[schemas.ChatSessionResponse])
def list_chat_sessions(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    q = db.query(models.ChatSession)
    if status:
        q = q.filter(models.ChatSession.status == status)
    else:
        q = q.filter(models.ChatSession.status.in_(["waiting", "active"]))
    # Technicians see waiting sessions + those they've claimed.
    if current_user.role == "technician":
        q = q.filter(
            (models.ChatSession.status == "waiting")
            | (models.ChatSession.agent_username == current_user.username)
        )
    return q.order_by(models.ChatSession.last_activity.desc()).all()


@router.get("/chat/sessions/{session_id}/messages", response_model=List[schemas.ChatMessageResponse])
def get_chat_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.id.asc())
        .all()
    )


@router.post("/chat/sessions/{session_id}/claim", response_model=schemas.ChatSessionResponse)
async def claim_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if session.status == "closed":
        raise HTTPException(status_code=400, detail="Chat is already closed.")
    if session.agent_username and session.agent_username != current_user.username:
        raise HTTPException(status_code=409, detail=f"Already handled by {session.agent_username}")

    session.agent_username = current_user.username
    session.status = "active"
    _touch(session)
    sys_msg = models.ChatMessage(
        session_id=session_id, sender_role="system", sender_name="System",
        content=f"{current_user.username} joined the chat.", created_at=utcnow(),
    )
    db.add(sys_msg)
    db.commit()
    db.refresh(session)
    await chat_hub.publish(session_id, {"type": "message", **_msg_out(sys_msg)})
    return session


@router.post("/chat/sessions/{session_id}/agent-messages", response_model=schemas.ChatMessageResponse)
async def post_agent_message(
    session_id: str,
    body: schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if session.status == "closed":
        raise HTTPException(status_code=400, detail="Chat is closed.")
    # Only the assigned agent (or an admin) may reply.
    if session.agent_username and session.agent_username != current_user.username \
            and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="This chat is handled by another agent.")
    if not session.agent_username:
        session.agent_username = current_user.username
        session.status = "active"

    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    content = content[: config.MAX_CHAT_MESSAGE_LEN]

    m = models.ChatMessage(
        session_id=session_id, sender_role="agent",
        sender_name=current_user.username, content=content, created_at=utcnow(),
    )
    db.add(m)
    _touch(session)
    db.commit()
    db.refresh(m)
    await chat_hub.publish(session_id, {"type": "message", **_msg_out(m)})
    return m


@router.post("/chat/sessions/{session_id}/close-staff")
async def close_chat_staff(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    session.status = "closed"
    session.closed_at = utcnow()
    sys_msg = models.ChatMessage(
        session_id=session_id, sender_role="system", sender_name="System",
        content="The agent closed this chat.", created_at=utcnow(),
    )
    db.add(sys_msg)
    db.commit()
    await chat_hub.publish(session_id, {"type": "message", **_msg_out(sys_msg)})
    await chat_hub.publish(session_id, {"type": "closed"})
    return {"status": "closed"}


# ── WebSocket: staff real-time chat channel ───────────

@router.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str, token: str = Query(...),
                  db: Session = Depends(get_db)):
    """Authenticated staff channel for a chat session. End users use REST polling."""
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username or not db.query(models.AdminUser).filter(
                models.AdminUser.username == username).first():
            await websocket.close(code=4001)
            return
    except HTTPException:
        await websocket.close(code=4001)
        return

    await chat_hub.subscribe(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        chat_hub.unsubscribe(websocket, session_id)
