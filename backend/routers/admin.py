from typing import List, Optional

import audit
import models
import schemas
from auth import hash_password, require_super_admin
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/admin/users", response_model=List[schemas.AdminUserResponse])
def list_admin_users(
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(require_super_admin),
):
    return db.query(models.AdminUser).all()


@router.post("/admin/users", response_model=schemas.AdminUserResponse)
def create_admin_user(
    body: schemas.AdminUserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(require_super_admin),
):
    if db.query(models.AdminUser).filter(models.AdminUser.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    valid_roles = {"super_admin", "technician"}
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    new_user = models.AdminUser(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(new_user)
    audit.record(db, audit.USER_CREATE, actor=current_admin.username,
                 target=body.username, detail=f"role={body.role}", request=request)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.delete("/admin/users/{user_id}")
def delete_admin_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(require_super_admin),
):
    user = db.query(models.AdminUser).filter(models.AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if user.role == "super_admin":
        # Prevent deleting the last super admin
        count = db.query(models.AdminUser).filter(models.AdminUser.role == "super_admin").count()
        if count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin account")
    deleted_username = user.username
    db.delete(user)
    audit.record(db, audit.USER_DELETE, actor=current_admin.username,
                 target=deleted_username, detail=f"role={user.role}", request=request)
    db.commit()
    return {"deleted": user_id, "username": deleted_username}


# ── Audit trail (super_admin only) ────────────────────

@router.get("/audit", response_model=List[schemas.AuditLogResponse])
def list_audit_log(
    action: Optional[str] = Query(None, description="Exact action, e.g. auth.login.failure"),
    actor: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_admin: models.AdminUser = Depends(require_super_admin),
):
    """Most recent privileged actions, newest first.

    Read-only by design: there is no endpoint to edit or delete entries, and
    the retention sweep does not touch them. An audit trail that its own
    subjects can rewrite is not an audit trail.
    """
    q = db.query(models.AuditLog)
    if action:
        q = q.filter(models.AuditLog.action == action)
    if actor:
        q = q.filter(models.AuditLog.actor == actor)
    if success is not None:
        q = q.filter(models.AuditLog.success == success)
    return q.order_by(models.AuditLog.created_at.desc(), models.AuditLog.id.desc()).limit(limit).all()
