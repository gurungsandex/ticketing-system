from sqlalchemy import Column, Integer, Text, DateTime, LargeBinary, Boolean
from sqlalchemy.sql import func
from database import Base


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
    assigned_to   = Column(Text)
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, onupdate=func.now())


class AdminUser(Base):
    __tablename__ = "admin_users"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(Text, unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    role            = Column(Text, default="technician")


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
    event_type         = Column(Text, nullable=False)   # "assigned" | "comment_added" | "status_changed"
    message            = Column(Text, nullable=False)
    is_read            = Column(Boolean, default=False)
    created_at         = Column(DateTime, default=func.now())
