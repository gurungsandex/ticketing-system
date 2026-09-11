"""
Audit trail for privileged and security-relevant actions.

What belongs here: who did what, to which object, from where, and whether it
succeeded. What must never reach it: ticket descriptions, note bodies, chat
messages, passwords, or tokens. Those are user-submitted free text that may
contain personal or sensitive information, and an audit trail is exactly the
kind of long-lived, widely-read store it must not leak into. The helpers below
take identifiers and short fixed strings, never request bodies.

Writes participate in the caller's transaction and are flushed with it, so an
action and its audit record commit together -- there is no window where one
exists without the other.
"""
from typing import Optional

import models
from fastapi import Request
from security import client_ip
from sqlalchemy.orm import Session
from utils import utcnow

# ── Action vocabulary ─────────────────────────────────
# Dotted and stable, so log searches and alerts can match on a prefix.
LOGIN_SUCCESS = "auth.login.success"
LOGIN_FAILURE = "auth.login.failure"
PASSWORD_CHANGE = "auth.password.change"
USER_CREATE = "admin.user.create"
USER_DELETE = "admin.user.delete"
TICKET_ASSIGN = "ticket.assign"
KB_APPROVE = "kb.article.approve"
KB_REJECT = "kb.article.reject"
CHAT_DELETE = "chat.session.delete"
UPDATE_APPLY = "server.update.apply"


def record(
    db: Session,
    action: str,
    actor: Optional[str] = None,
    target: Optional[str] = None,
    detail: Optional[str] = None,
    request: Optional[Request] = None,
    success: bool = True,
) -> models.AuditLog:
    """Append an audit row. Caller commits."""
    entry = models.AuditLog(
        actor=actor or "anonymous",
        action=action,
        target=(target or None),
        # Capped: `detail` is for short fixed context like "role=technician",
        # never free text, and the cap is a backstop against a careless caller.
        detail=(detail or None) if detail is None else detail[:200],
        ip_address=client_ip(request) if request is not None else None,
        success=success,
        created_at=utcnow(),
    )
    db.add(entry)
    return entry
