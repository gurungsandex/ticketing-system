import time
from datetime import date, datetime
from typing import List, Optional

import config
import models
import schemas
from auth import get_current_admin, require_admin_or_assigned, require_super_admin
from database import get_db
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from security import ALLOWED_MIMES, detect_content_type, rate_limit
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from utils import utcnow
from websocket_manager import ws_manager

router = APIRouter()

MAX_SIZE = config.MAX_UPLOAD_BYTES

VALID_CATEGORIES = {
    "Other", "Computer / Workstation", "Network / Internet / WiFi",
    "Printer", "Scanner", "Phone / VoIP", "Browser",
    "Software / Application", "Email", "VPN / Remote Access",
    "Hardware", "File Access / Permissions", "Performance Issues",
    "Password / Account", "Monitor / Display",
}
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_STATUSES = {"active", "in_progress", "resolved"}


# ── Helpers ───────────────────────────────────────────

def _next_ticket_seq(db: Session, date_key: str) -> int:
    """Atomically obtain the next per-day sequence number.

    The increment is done with a single ``UPDATE ... last_seq = last_seq + 1``
    statement evaluated by the database under its write lock, so the result is
    never derived from a stale in-memory read — two concurrent callers always
    receive distinct values. The counter row is created lazily on the first
    ticket of the day; a race there surfaces as an IntegrityError that the
    caller retries.
    """
    result = db.execute(
        update(models.TicketCounter)
        .where(models.TicketCounter.date_key == date_key)
        .values(last_seq=models.TicketCounter.last_seq + 1)
    )
    if result.rowcount == 0:
        # No counter row for today yet — create it. If a concurrent request
        # created it first, this raises IntegrityError and the caller retries.
        db.add(models.TicketCounter(date_key=date_key, last_seq=1))
        db.flush()
        return 1
    seq = db.execute(
        db.query(models.TicketCounter.last_seq)
        .filter(models.TicketCounter.date_key == date_key)
        .statement
    ).scalar_one()
    return seq


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


def _staff_recipients(db: Session, ticket: models.Ticket, exclude: Optional[str] = None) -> set:
    recipients = set()
    if ticket.assigned_to:
        recipients.add(ticket.assigned_to)
    for a in db.query(models.AdminUser).filter(models.AdminUser.role == "super_admin").all():
        recipients.add(a.username)
    recipients.discard(exclude)
    return recipients


# ── PUBLIC: Create ticket ─────────────────────────────

@router.post("/tickets/", response_model=schemas.TicketCreateResponse)
def create_ticket(payload: schemas.TicketCreate, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "ticket_create", config.RATE_LIMIT_TICKET_CREATE)

    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {payload.category}")

    priority = (payload.priority or "normal").lower()
    if priority not in VALID_PRIORITIES:
        priority = "normal"

    description = (payload.description or "")[: config.MAX_DESCRIPTION_LEN]

    # Reserve a unique ticket number and insert atomically. Retry on the rare
    # counter-row race (IntegrityError) or a transient SQLite lock timeout
    # (OperationalError), with a small backoff so contending writers stagger.
    last_error: Optional[Exception] = None
    ticket = None
    for attempt in range(10):
        try:
            date_key = date.today().strftime("%Y%m%d")
            seq = _next_ticket_seq(db, date_key)
            ticket = models.Ticket(
                id=f"TKT-{date_key}-{seq:04d}",
                client_id=payload.client_id,
                username=payload.username or "",
                ip_address=payload.ip_address,
                hostname=payload.hostname,
                category=payload.category,
                sub_category=payload.sub_category or "",
                description=description,
                priority=priority,
                department=(payload.department or None),
                location=(payload.location or None),
                device=(payload.device or None),
                status="active",
                created_at=utcnow(),
                updated_at=None,
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            break
        except (IntegrityError, OperationalError) as exc:
            last_error = exc
            db.rollback()
            time.sleep(0.02 * (attempt + 1))
    if ticket is None:
        raise HTTPException(
            status_code=503,
            detail="Could not allocate a ticket number. Please try again.",
        ) from last_error

    # Notify staff about the new ticket (urgent/high get flagged).
    flag = "🔴 " if priority in ("high", "urgent") else ""
    msg = f"{flag}New {priority} ticket {ticket.id} — {ticket.category}"
    for admin in db.query(models.AdminUser).filter(
        models.AdminUser.role == "super_admin"
    ).all():
        _create_notification(db, admin.username, ticket.id, "new_ticket", msg)
    db.commit()
    return ticket


# ── PUBLIC: Upload attachment (client app — no auth) ──

@router.post("/tickets/{ticket_id}/attachments")
async def upload_attachment(
    ticket_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    rate_limit(request, "attachment", config.RATE_LIMIT_ATTACHMENT)

    if not db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first():
        raise HTTPException(status_code=404, detail="Ticket not found")

    claimed_mime = file.content_type or ""
    if claimed_mime not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=400,
            detail="File type not allowed. Use PNG, JPG, GIF, WEBP, BMP, or PDF.",
        )

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10 MB.")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")

    # Verify the real content, not just the client-declared type.
    real_mime = detect_content_type(data)
    if real_mime is None:
        raise HTTPException(
            status_code=400,
            detail="File content does not match an allowed image/PDF type.",
        )

    safe_name = (file.filename or "attachment").replace("/", "_").replace("\\", "_")[:255]

    att = models.Attachment(
        ticket_id=ticket_id,
        filename=safe_name,
        mimetype=real_mime,
        size_bytes=len(data),
        data=data,
        created_at=utcnow(),
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return {"id": att.id, "filename": att.filename, "size_bytes": att.size_bytes}


# ── STAFF: List all tickets ───────────────────────────

def _to_detail(db: Session, t: models.Ticket) -> schemas.TicketDetail:
    nc = db.query(models.Note).filter(models.Note.ticket_id == t.id).count()
    return schemas.TicketDetail(
        id=t.id, client_id=t.client_id, username=t.username,
        ip_address=t.ip_address, hostname=t.hostname,
        category=t.category, sub_category=t.sub_category,
        description=t.description, status=t.status,
        priority=t.priority or "normal", department=t.department,
        location=t.location, device=t.device,
        resolution_summary=t.resolution_summary, resolved_at=t.resolved_at,
        assigned_to=t.assigned_to, created_at=t.created_at,
        updated_at=t.updated_at, notes_count=nc,
    )


@router.get("/tickets/", response_model=List[schemas.TicketDetail])
def list_tickets(
    status:    Optional[str] = Query(None),
    category:  Optional[str] = Query(None),
    priority:  Optional[str] = Query(None),
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
    if priority:
        q = q.filter(models.Ticket.priority == priority)
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
    return [_to_detail(db, t) for t in tickets]


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
    if current_user.role == "technician" and t.assigned_to != current_user.username:
        raise HTTPException(status_code=403, detail="You are not assigned to this ticket.")
    return _to_detail(db, t)


# ── RBAC: Update status (admin OR assigned technician) ─

@router.patch("/tickets/{ticket_id}/status")
async def update_status(
    ticket_id: str,
    body: schemas.TicketStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status value")

    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")

    require_admin_or_assigned(t.assigned_to, current_user)

    t.status = body.status
    t.updated_at = utcnow()
    if body.status == "resolved":
        t.resolved_at = utcnow()
        if body.resolution_summary:
            t.resolution_summary = body.resolution_summary[: config.MAX_DESCRIPTION_LEN]
    db.commit()
    db.refresh(t)

    recipients = _staff_recipients(db, t, exclude=current_user.username)
    msg = f"Ticket {ticket_id} status changed to '{body.status.replace('_', ' ')}' by {current_user.username}"
    for recipient in recipients:
        _create_notification(db, recipient, ticket_id, "status_changed", msg)
    db.commit()

    payload = {"type": "status_changed", "ticket_id": ticket_id,
               "status": body.status, "message": msg}
    await ws_manager.broadcast_to_users(list(recipients), payload)

    return {"id": t.id, "status": t.status, "updated_at": t.updated_at}


# ── RBAC: Update priority (admin OR assigned technician) ─

@router.patch("/tickets/{ticket_id}/priority")
async def update_priority(
    ticket_id: str,
    body: schemas.TicketPriorityUpdate,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    priority = (body.priority or "").lower()
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority value")

    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    require_admin_or_assigned(t.assigned_to, current_user)

    t.priority = priority
    t.updated_at = utcnow()
    db.commit()
    return {"id": t.id, "priority": t.priority}


# ── ADMIN ONLY: Assign ticket ─────────────────────────

@router.patch("/tickets/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    body: schemas.TicketAssignUpdate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(require_super_admin),
):
    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")

    assignee = db.query(models.AdminUser).filter(
        models.AdminUser.username == body.assigned_to
    ).first()
    if not assignee:
        raise HTTPException(status_code=404, detail=f"User '{body.assigned_to}' not found")

    t.assigned_to = body.assigned_to
    t.updated_at = utcnow()

    msg = f"You have been assigned ticket {ticket_id} — {t.category} ({t.priority or 'normal'} priority)"
    _create_notification(db, body.assigned_to, ticket_id, "assigned", msg)
    db.commit()
    db.refresh(t)

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
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Note cannot be empty.")
    content = content[: config.MAX_NOTE_LEN]

    t = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if current_user.role == "technician" and t.assigned_to != current_user.username:
        raise HTTPException(status_code=403, detail="You are not assigned to this ticket.")

    note = models.Note(
        ticket_id=ticket_id,
        admin_username=current_user.username,
        content=content,
        created_at=utcnow(),
    )
    db.add(note)

    recipients = _staff_recipients(db, t, exclude=current_user.username)
    preview = content[:60] + ("…" if len(content) > 60 else "")
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
    current_user: models.AdminUser = Depends(get_current_admin),
):
    a = db.query(models.Attachment).filter(models.Attachment.id == attachment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Attachment not found")

    t = db.query(models.Ticket).filter(models.Ticket.id == a.ticket_id).first()
    if t and current_user.role == "technician" and t.assigned_to != current_user.username:
        raise HTTPException(status_code=403, detail="Access denied.")

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
