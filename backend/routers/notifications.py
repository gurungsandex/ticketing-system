from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import get_current_admin, decode_token
from websocket_manager import ws_manager

router = APIRouter()


# ── WebSocket ─────────────────────────────────────────

@router.websocket("/ws/notifications")
async def ws_notifications(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Authenticated WebSocket channel for real-time notifications.
    Connect: ws://SERVER_IP:8000/ws/notifications?token=<JWT>
    """
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            await websocket.close(code=4001)
            return
        user = db.query(models.AdminUser).filter(
            models.AdminUser.username == username
        ).first()
        if not user:
            await websocket.close(code=4001)
            return
    except HTTPException:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(websocket, username)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, username)


# ── Staff notification bell ───────────────────────────

@router.get("/notifications/my/unread-count", response_model=schemas.UnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    count = (
        db.query(models.Notification)
        .filter(
            models.Notification.recipient_username == current_user.username,
            models.Notification.is_read == False,  # noqa: E712
        )
        .count()
    )
    return {"unread_count": count}


@router.get("/notifications/my", response_model=List[schemas.StaffNotificationResponse])
def get_my_notifications(
    limit: int = Query(30, le=100),
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    return (
        db.query(models.Notification)
        .filter(models.Notification.recipient_username == current_user.username)
        .order_by(models.Notification.created_at.desc())
        .limit(limit)
        .all()
    )


# NOTE: /notifications/read-all must be declared BEFORE /notifications/{notif_id}/read
# so that the literal path "read-all" is not mistakenly captured as a {notif_id} value.
@router.patch("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    updated = (
        db.query(models.Notification)
        .filter(
            models.Notification.recipient_username == current_user.username,
            models.Notification.is_read == False,  # noqa: E712
        )
        .update({"is_read": True})
    )
    db.commit()
    return {"marked_read": updated}


@router.patch("/notifications/{notif_id}/read")
def mark_one_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    n = db.query(models.Notification).filter(
        models.Notification.id == notif_id,
        models.Notification.recipient_username == current_user.username,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()
    return {"id": notif_id, "is_read": True}


# ── Legacy: client-app polling ────────────────────────
# Must be last — {client_id} would otherwise swallow /my and /my/unread-count

@router.get("/notifications/{client_id}", response_model=List[schemas.NotificationItem])
def get_client_notifications(client_id: str, db: Session = Depends(get_db)):
    """Polled by the end-user Windows tray app to check ticket status changes."""
    tickets = (
        db.query(models.Ticket)
        .filter(models.Ticket.client_id == client_id)
        .order_by(models.Ticket.created_at.desc())
        .all()
    )
    return [
        schemas.NotificationItem(id=t.id, status=t.status, updated_at=t.updated_at)
        for t in tickets
    ]
