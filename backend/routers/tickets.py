from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import get_current_admin, require_super_admin, require_admin_or_assigned
from websocket_manager import ws_manager

router = APIRouter()

ALLOWED_MIMES = {
    "image/png", "image/jpeg", "image/jpg", "image/gif",
    "image/webp", "image/bmp", "application/pdf",
}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


# ── Helpers ───────────────────────────────────────────

def generate_ticket_id(db: Session) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"TKT-{today}-"
    count = db.query(models.Ticket).filter(models.Ticket.id.like(f"{prefix}%")).count()
    return f"{prefix}{count + 1:04d}"


def _create_notification(
    db: Session,
    recipient_username: str,
    ticket_id: str,
    event_type: str,
    message: str,
) -> models.Notification:
    notif = models.Notification(
        recipient_username=recipient_username,
        ticket_id=ticket_id,
        event_type=event_type,
        message=message,
    )
    db.add(notif)
    return notif


# ── PUBLIC: Create ticket ─────────────────────────────

@router.post("/tickets/", response_model=schemas.TicketCreateResponse)
def create_ticket(payload: schemas.TicketCreate, db: Session = Depends(get_db)):
    valid_categories = {
        "Other", "Computer / Workstation", "Network / Internet / WiFi",
        "Printer", "Scanner", "Phone / VoIP", "Browser",
        "Software / Application", "Email", "VPN / Remote Access",
        "Hardware", "File Access / Permissions", "Performance Issues",
    }
    if payload.category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"Invalid category: {payload.category}")

    ticket = models.Ticket(
        id=generate_ticket_id(db),
        client_id=payload.client_id,
        username=payload.username or "",
        ip_address=payload.ip_address,
        hostname=payload.hostname,
        category=payload.category,
        sub_category=payload.sub_category or "",
        description=payload.description or "",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=None,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


# ── PUBLIC: Upload attachment (client app — no auth) ──

@router.post("/tickets/{ticket_id}/attachments")
async def upload_attachment(
    ticket_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first():
        raise HTTPException(status_code=404, detail="Ticket not found")

    mime = file.content_type or ""
    if mime not in ALLOWED_MIMES:
        raise HTTPException(status_code=400,
            detail="File type not allowed. Use PNG, JPG, GIF, WEBP, BMP, or PDF.")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10 MB.")

    # Sanitise filename — strip path separators
    safe_name = (file.filename or "attachment").replace("/", "_").replace("\\", "_")

    att = models.Attachment(
        ticket_id=ticket_id,
        filename=safe_name,
        mimetype=mime,
        size_bytes=len(data),
        data=data,
        created_at=datetime.utcnow(),
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"id": att.id, "filename": att.filename, "size_bytes": att.size_bytes}


# ── STAFF: List all tickets ───────────────────────────

@router.get("/tickets/", response_model=List[schemas.TicketDetail])
def list_tickets(
    status:    Optional[str] = Query(None),
    category:  Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    q = db.query(models.Ticket)

    # Technicians only see tickets assigned to them
    if current_user.role == "technician":
        q = q.filter(models.Ticket.assigned_to == current_user.username)

    if status:
        q = q.filter(models.Ticket.status == status)
    if category:
        q = q.filter(models.Ticket.category == category)
    if date_from:
        try:
            q = q.filter(models.Ticket.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from. Use YYYY-MM-DD")
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q = q.filter(models.Ticket.created_at <= dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to. Use YYYY-MM-DD")

    tickets = q.order_by(models.Ticket.created_at.desc()).all()
    result = []
    for t in tickets:
        nc = db.query(models.Note).filter(models.Note.ticket_id == t.id).count()
        result.append(schemas.TicketDetail(
            id=t.id, client_id=t.client_id, username=t.username,
            ip_address=t.ip_address, hostname=t.hostname,
            category=t.category, sub_category=t.sub_category,
            description=t.description, status=t.status,
            assigned_to=t.assigned_to, created_at=t.created_at,
            updated_at=t.updated_at, notes_count=nc,
        ))
    return result


# ── STAFF: Get single ticket ──────────────────────────

@router.get("/tickets/{ticket_id}", response_model=schemas.TicketDetail)
def get_ticket(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Technicians can only view their assigned tickets
    if current_user.role == "technician" and t.assigned_to != current_user.username:
        raise HTTPException(status_code=403, detail="You are not assigned to this ticket.")

    nc = db.query(models.Note).filter(models.Note.ticket_id == ticket_id).count()
    return schemas.TicketDetail(
        id=t.id, client_id=t.client_id, username=t.username,
        ip_address=t.ip_address, hostname=t.hostname,
        category=t.category, sub_category=t.sub_category,
        description=t.description, status=t.status,
        assigned_to=t.assigned_to, created_at=t.created_at,
        updated_at=t.updated_at, notes_count=nc,
    )


# ── RBAC: Update status (admin OR assigned technician) ─

@router.patch("/tickets/{ticket_id}/status")
async def update_status(
    ticket_id: str,
    body: schemas.TicketStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    if body.status not in {"active", "in_progress", "resolved"}:
        raise HTTPException(status_code=400, detail="Invalid status value")

    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # BACKEND RBAC — not frontend only
    require_admin_or_assigned(t.assigned_to, current_user)

    t.status = body.status
    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)

    # Notify all relevant staff about status change
    recipients = set()
    if t.assigned_to:
        recipients.add(t.assigned_to)
    # Notify all admins
    admins = db.query(models.AdminUser).filter(models.AdminUser.role == "super_admin").all()
    for a in admins:
        recipients.add(a.username)
    recipients.discard(current_user.username)  # don't self-notify

    msg = f"Ticket {ticket_id} status changed to '{body.status.replace('_', ' ')}' by {current_user.username}"
    for recipient in recipients:
        n = _create_notification(db, recipient, ticket_id, "status_changed", msg)
    db.commit()

    # WebSocket push
    payload = {"type": "status_changed", "ticket_id": ticket_id,
               "status": body.status, "message": msg}
    await ws_manager.broadcast_to_users(list(recipients), payload)

    return {"id": t.id, "status": t.status, "updated_at": t.updated_at}


# ── ADMIN ONLY: Assign ticket ─────────────────────────

@router.patch("/tickets/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    body: schemas.TicketAssignUpdate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(require_super_admin),  # ADMIN ONLY
):
    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Verify the assignee exists
    assignee = db.query(models.AdminUser).filter(
        models.AdminUser.username == body.assigned_to
    ).first()
    if not assignee:
        raise HTTPException(status_code=404, detail=f"User '{body.assigned_to}' not found")

    t.assigned_to = body.assigned_to
    t.updated_at = datetime.utcnow()

    # Create notification for the assigned technician
    msg = f"You have been assigned ticket {ticket_id} — {t.category}"
    _create_notification(db, body.assigned_to, ticket_id, "assigned", msg)
    db.commit()
    db.refresh(t)

    # WebSocket push
    payload = {"type": "assigned", "ticket_id": ticket_id, "message": msg}
    await ws_manager.push(body.assigned_to, payload)

    return {"id": t.id, "assigned_to": t.assigned_to, "updated_at": t.updated_at}


# ── STAFF: Notes (admin or assigned technician) ───────

@router.post("/tickets/{ticket_id}/notes", response_model=schemas.NoteResponse)
async def add_note(
    ticket_id: str,
    body: schemas.NoteCreate,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Technicians can only add notes to their assigned tickets
    if current_user.role == "technician" and t.assigned_to != current_user.username:
        raise HTTPException(status_code=403, detail="You are not assigned to this ticket.")

    note = models.Note(
        ticket_id=ticket_id,
        admin_username=current_user.username,
        content=body.content,
        created_at=datetime.utcnow(),
    )
    db.add(note)

    # Notify: assigned technician + all admins (except the note author)
    recipients = set()
    if t.assigned_to:
        recipients.add(t.assigned_to)
    admins = db.query(models.AdminUser).filter(models.AdminUser.role == "super_admin").all()
    for a in admins:
        recipients.add(a.username)
    recipients.discard(current_user.username)

    preview = body.content[:60] + ("…" if len(body.content) > 60 else "")
    msg = f"{current_user.username} added a note on {ticket_id}: \"{preview}\""
    for recipient in recipients:
        _create_notification(db, recipient, ticket_id, "comment_added", msg)

    db.commit()
    db.refresh(note)

    payload = {"type": "comment_added", "ticket_id": ticket_id, "message": msg}
    await ws_manager.broadcast_to_users(list(recipients), payload)

    return note


@router.get("/tickets/{ticket_id}/notes", response_model=List[schemas.NoteResponse])
def get_notes(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_user.role == "technician" and t.assigned_to != current_user.username:
        raise HTTPException(status_code=403, detail="You are not assigned to this ticket.")
    return (
        db.query(models.Note)
        .filter(models.Note.ticket_id == ticket_id)
        .order_by(models.Note.created_at.asc())
        .all()
    )


# ── STAFF: Attachments ────────────────────────────────

@router.get("/tickets/{ticket_id}/attachments", response_model=List[schemas.AttachmentResponse])
def get_attachments(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if current_user.role == "technician" and t.assigned_to != current_user.username:
        raise HTTPException(status_code=403, detail="You are not assigned to this ticket.")
    return (
        db.query(models.Attachment)
        .filter(models.Attachment.ticket_id == ticket_id)
        .order_by(models.Attachment.created_at.asc())
        .all()
    )


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),  # accepts ?token= too
):
    """
    Secure file download with authentication.
    Supports both Authorization header and ?token= query param so the
    frontend fetch+blob approach and direct URL opens both work.
    """
    a = db.query(models.Attachment).filter(models.Attachment.id == attachment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Verify caller has access to the parent ticket
    t = db.query(models.Ticket).filter(models.Ticket.id == a.ticket_id).first()
    if t and current_user.role == "technician" and t.assigned_to != current_user.username:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Sanitise filename for Content-Disposition header
    safe = a.filename.replace('"', '\\"').replace("\n", "").replace("\r", "")
    return Response(
        content=a.data,
        media_type=a.mimetype or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
