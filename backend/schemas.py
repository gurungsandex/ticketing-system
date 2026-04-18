from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── Ticket ────────────────────────────────────────────

class TicketCreate(BaseModel):
    client_id:    str
    username:     Optional[str] = None
    ip_address:   str
    hostname:     str
    category:     str
    sub_category: Optional[str] = ""
    description:  Optional[str] = ""


class TicketCreateResponse(BaseModel):
    id:         str
    status:     str
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TicketDetail(BaseModel):
    id:           str
    client_id:    str
    username:     Optional[str] = None
    ip_address:   Optional[str] = None
    hostname:     Optional[str] = None
    category:     str
    sub_category: Optional[str] = None
    description:  Optional[str] = None
    status:       str
    assigned_to:  Optional[str] = None
    created_at:   Optional[datetime] = None
    updated_at:   Optional[datetime] = None
    notes_count:  Optional[int] = 0
    model_config = {"from_attributes": True}


class TicketStatusUpdate(BaseModel):
    status: str


class TicketAssignUpdate(BaseModel):
    assigned_to: str


# ── Client-side notification (polling by client_id) ───

class NotificationItem(BaseModel):
    id:         str
    status:     str
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Staff notifications (bell icon) ──────────────────

class StaffNotificationResponse(BaseModel):
    id:                 int
    recipient_username: str
    ticket_id:          str
    event_type:         str
    message:            str
    is_read:            bool
    created_at:         Optional[datetime] = None
    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    unread_count: int


# ── Notes ─────────────────────────────────────────────

class NoteCreate(BaseModel):
    content: str


class NoteResponse(BaseModel):
    id:             int
    ticket_id:      str
    admin_username: Optional[str] = None
    content:        str
    created_at:     Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Attachments ───────────────────────────────────────

class AttachmentResponse(BaseModel):
    id:         int
    ticket_id:  str
    filename:   str
    mimetype:   Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Auth ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type:   str
    role:         str
    username:     str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str


# ── Admin users ───────────────────────────────────────

class AdminUserCreate(BaseModel):
    username: str
    password: str
    role:     Optional[str] = "technician"


class AdminUserResponse(BaseModel):
    id:       int
    username: str
    role:     str
    model_config = {"from_attributes": True}
