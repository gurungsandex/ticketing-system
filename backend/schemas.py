from datetime import datetime
from typing import Optional

from pydantic import BaseModel

# ── Ticket ────────────────────────────────────────────

class TicketCreate(BaseModel):
    client_id:    str
    username:     Optional[str] = None
    ip_address:   str
    hostname:     str
    category:     str
    sub_category: Optional[str] = ""
    description:  Optional[str] = ""
    priority:     Optional[str] = "normal"
    department:   Optional[str] = None
    location:     Optional[str] = None
    device:       Optional[str] = None


class TicketCreateResponse(BaseModel):
    id:         str
    status:     str
    priority:   Optional[str] = "normal"
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TicketDetail(BaseModel):
    id:                 str
    client_id:          str
    username:           Optional[str] = None
    ip_address:         Optional[str] = None
    hostname:           Optional[str] = None
    category:           str
    sub_category:       Optional[str] = None
    description:        Optional[str] = None
    status:             str
    priority:           Optional[str] = "normal"
    department:         Optional[str] = None
    location:           Optional[str] = None
    device:             Optional[str] = None
    resolution_summary: Optional[str] = None
    resolved_at:        Optional[datetime] = None
    assigned_to:        Optional[str] = None
    created_at:         Optional[datetime] = None
    updated_at:         Optional[datetime] = None
    notes_count:        Optional[int] = 0
    model_config = {"from_attributes": True}


class TicketStatusUpdate(BaseModel):
    status: str
    resolution_summary: Optional[str] = None


class TicketPriorityUpdate(BaseModel):
    priority: str


class TicketAssignUpdate(BaseModel):
    assigned_to: str


# ── Client-side notification (polling by client_id) ───

class NotificationItem(BaseModel):
    id:         str
    status:     str
    category:   Optional[str] = None
    priority:   Optional[str] = "normal"
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
    chat_status: Optional[str] = "offline"
    model_config = {"from_attributes": True}


# ── Agent presence ────────────────────────────────────

class AgentStatusUpdate(BaseModel):
    status: str   # available | busy | away | offline


class AgentPresence(BaseModel):
    username: str
    role: str
    chat_status: Optional[str] = "offline"
    model_config = {"from_attributes": True}


# ── Canned responses ──────────────────────────────────

class CannedResponseCreate(BaseModel):
    title:    str
    body:     str
    category: Optional[str] = None
    is_shared: bool = True


class CannedResponseResponse(BaseModel):
    id:         int
    title:      str
    body:       str
    category:   Optional[str] = None
    created_by: Optional[str] = None
    is_shared:  bool = True
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Live chat ─────────────────────────────────────────

class ChatStartRequest(BaseModel):
    client_id:    str
    display_name: Optional[str] = None
    hostname:     Optional[str] = None
    subject:      Optional[str] = None


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageResponse(BaseModel):
    id:          int
    session_id:  str
    sender_role: str
    sender_name: Optional[str] = None
    content:     str
    created_at:  Optional[datetime] = None
    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    id:             str
    client_id:      str
    display_name:   Optional[str] = None
    hostname:       Optional[str] = None
    status:         str
    agent_username: Optional[str] = None
    subject:        Optional[str] = None
    created_at:     Optional[datetime] = None
    closed_at:      Optional[datetime] = None
    last_activity:  Optional[datetime] = None
    model_config = {"from_attributes": True}


class ChatAvailability(BaseModel):
    live_support_available: bool
    available_agents: int


# ── Knowledge base ────────────────────────────────────

class KBArticleCreate(BaseModel):
    title:           str
    category:        Optional[str] = None
    problem_summary: Optional[str] = None
    content:         str
    article_type:    Optional[str] = "article"
    tags:            Optional[str] = None


class KBArticleUpdate(BaseModel):
    title:           Optional[str] = None
    category:        Optional[str] = None
    problem_summary: Optional[str] = None
    content:         Optional[str] = None
    article_type:    Optional[str] = None
    tags:            Optional[str] = None


class KBArticleResponse(BaseModel):
    id:              int
    title:           str
    category:        Optional[str] = None
    problem_summary: Optional[str] = None
    content:         str
    article_type:    Optional[str] = "article"
    source:          Optional[str] = "manual"
    workflow_status: str
    tags:            Optional[str] = None
    created_by:      Optional[str] = None
    approved_by:     Optional[str] = None
    approved_at:     Optional[datetime] = None
    created_at:      Optional[datetime] = None
    updated_at:      Optional[datetime] = None
    model_config = {"from_attributes": True}


class KBArticleSummary(BaseModel):
    id:              int
    title:           str
    category:        Optional[str] = None
    article_type:    Optional[str] = "article"
    source:          Optional[str] = "manual"
    workflow_status: str
    created_by:      Optional[str] = None
    created_at:      Optional[datetime] = None
    model_config = {"from_attributes": True}
