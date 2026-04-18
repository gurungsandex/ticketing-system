import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
import models

SECRET_KEY = os.environ.get("SECRET_KEY", "HELPDESK_SECRET_KEY_CHANGE_IN_PRODUCTION")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _resolve_token(
    credentials: Optional[HTTPAuthorizationCredentials],
    token_param: Optional[str],
) -> str:
    """Return the raw JWT from either the Authorization header or ?token= query param
    (query param is used by WebSocket handshakes and download links)."""
    if credentials and credentials.credentials:
        return credentials.credentials
    if token_param:
        return token_param
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    token: Optional[str] = Query(None),   # for WS / download URLs
    db: Session = Depends(get_db),
) -> models.AdminUser:
    """Accepts any authenticated IT staff member (admin or technician)."""
    raw = _resolve_token(credentials, token)
    payload = decode_token(raw)
    username: str = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(models.AdminUser).filter(models.AdminUser.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_super_admin(
    current_user: models.AdminUser = Depends(get_current_admin),
) -> models.AdminUser:
    """Only super_admin role is allowed through."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required. Technicians cannot perform this action.",
        )
    return current_user


def require_admin_or_assigned(ticket_assigned_to: Optional[str], current_user: models.AdminUser):
    """Raise 403 unless the caller is super_admin OR is the assigned technician."""
    if current_user.role == "super_admin":
        return
    if current_user.username == ticket_assigned_to:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the assigned technician or an admin may update this ticket's status.",
    )
