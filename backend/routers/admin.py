from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import get_current_admin, require_super_admin, hash_password

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
    db.commit()
    db.refresh(new_user)
    return new_user


@router.delete("/admin/users/{user_id}")
def delete_admin_user(
    user_id: int,
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
    db.delete(user)
    db.commit()
    return {"deleted": user_id, "username": user.username}
