from database import Base
from sqlalchemy import Boolean, Column, DateTime, Integer, LargeBinary, Text
from sqlalchemy.sql import func


class Ticket(Base):
    __tablename__ = "tickets"

    id            = Column(Text, primary_key=True, index=True)
    client_id     = Column(Text, nullable=False, index=True)
    username      = Column(Text)
    ip_address    = Column(Text)
    hostname      = Column(Text)
    category      = Column(Text, nullable=False)
    sub_category  = Column(Text)
    description   = Column(Text)
    status        = Column(Text, default="active")
    # ITSM: prioritisation + resolution capture (added in 1.1, nullable for back-compat)
    priority          = Column(Text, default="normal", index=True)  # low | normal | high | urgent
    department        = Column(Text)
    location          = Column(Text)
    device            = Column(Text)
    resolution_summary = Column(Text)
    resolved_at       = Column(DateTime)
    assigned_to   = Column(Text, index=True)
    created_at    = Column(DateTime, default=func.now(), index=True)
    updated_at    = Column(DateTime, onupdate=func.now())


class TicketCounter(Base):
    """Atomic per-day sequence source for ticket numbers.

    One row per YYYYMMDD date key. The counter is incremented inside a
    transaction with a row-level UPDATE so two concurrent ticket creations can
    never read the same value — eliminating duplicate ticket numbers.
    """
    __tablename__ = "ticket_counters"

    date_key = Column(Text, primary_key=True)   # e.g. "20260731"
    last_seq = Column(Integer, nullable=False, default=0)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(Text, unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    role            = Column(Text, default="technician")
    # Live-chat presence (added 1.1)
    chat_status         = Column(Text, default="offline")  # available | busy | away | offline
    chat_status_updated = Column(DateTime)


class Note(Base):
    __tablename__ = "notes"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id      = Column(Text, nullable=False, index=True)
    admin_username = Column(Text)
    content        = Column(Text, nullable=False)
    created_at     = Column(DateTime, default=func.now())


class Attachment(Base):
    __tablename__ = "attachments"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id   = Column(Text, nullable=False, index=True)
    filename    = Column(Text, nullable=False)
    mimetype    = Column(Text)
    size_bytes  = Column(Integer)
    data        = Column(LargeBinary, nullable=False)
    created_at  = Column(DateTime, default=func.now())


class Notification(Base):
    """Real-time notifications for IT staff (admin + technicians)."""
    __tablename__ = "notifications"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    recipient_username = Column(Text, nullable=False, index=True)
    ticket_id          = Column(Text, nullable=False)
    event_type         = Column(Text, nullable=False)   # assigned | comment_added | status_changed | chat
    message            = Column(Text, nullable=False)
    is_read            = Column(Boolean, default=False)
    created_at         = Column(DateTime, default=func.now())


# ── Live chat ─────────────────────────────────────────

class CannedResponse(Base):
    """Reusable agent reply template. Inserted into the editor for review —
    never auto-sent."""
    __tablename__ = "canned_responses"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    title      = Column(Text, nullable=False)
    body       = Column(Text, nullable=False)
    category   = Column(Text)             # optional grouping
    created_by = Column(Text)
    is_shared  = Column(Boolean, default=True)   # visible to all staff vs. author-only
    created_at = Column(DateTime, default=func.now())


class ChatSession(Base):
    """A live-support conversation between one end user and IT staff."""
    __tablename__ = "chat_sessions"

    id             = Column(Text, primary_key=True)      # uuid
    client_id      = Column(Text, nullable=False, index=True)
    display_name   = Column(Text)                        # end-user's name
    hostname       = Column(Text)
    status         = Column(Text, default="waiting", index=True)  # waiting | active | closed
    agent_username = Column(Text, index=True)
    subject        = Column(Text)
    escalated      = Column(Boolean, default=False)   # handed from front-line techs to admins
    unread_count   = Column(Integer, default=0)       # unread user messages since agent last read/replied
    created_at     = Column(DateTime, default=func.now(), index=True)
    closed_at      = Column(DateTime)
    last_activity  = Column(DateTime, default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(Text, nullable=False, index=True)
    sender_role   = Column(Text, nullable=False)   # user | agent | system
    sender_name   = Column(Text)
    content       = Column(Text, nullable=False)
    created_at    = Column(DateTime, default=func.now())


# ── App settings (branding logo, desktop client version) ──

class AppSetting(Base):
    """Simple key/value store for admin-configurable, non-per-user settings."""
    __tablename__ = "app_settings"

    key   = Column(Text, primary_key=True)
    value = Column(Text)


# ── Knowledge base ────────────────────────────────────

class KBArticle(Base):
    """Knowledge-base article or troubleshooting playbook.

    AI/analysis-generated content is stored with workflow_status='draft' and
    MUST be reviewed and approved by an authorized IT professional before it
    can move to 'approved'/'published'. Nothing is auto-published.
    """
    __tablename__ = "kb_articles"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    title           = Column(Text, nullable=False)
    category        = Column(Text, index=True)
    problem_summary = Column(Text)
    content         = Column(Text, nullable=False)   # markdown body
    article_type    = Column(Text, default="article")  # article | playbook
    source          = Column(Text, default="manual")   # manual | ai_generated
    workflow_status = Column(Text, default="draft", index=True)  # draft | approved | published | rejected
    tags            = Column(Text)                    # comma-separated
    source_meta     = Column(Text)                    # JSON: which tickets/analysis produced it
    created_by      = Column(Text)
    approved_by     = Column(Text)
    approved_at     = Column(DateTime)
    created_at      = Column(DateTime, default=func.now())
    updated_at      = Column(DateTime, onupdate=func.now())
