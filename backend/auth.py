from datetime import timedelta
from typing import Optional

import bcrypt
import config
import models
from database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from utils import utcnow

SECRET_KEY = config.SECRET_KEY
ALGORITHM  = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_HOURS = config.ACCESS_TOKEN_EXPIRE_HOURS

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


SESSION_TOKEN_TYPE = "session"  # nosec B105 - a claim value, not a credential


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire, "typ": SESSION_TOKEN_TYPE})
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


# ── Download tokens ───────────────────────────────────
# Session JWTs must never travel in a URL. A URL ends up in browser history,
# in the server's access log, in any proxy log on the path, and in the Referer
# header of whatever the page loads next — so a full 8-hour session token in a
# download link is a credential leak with a long tail.
#
# Instead the dashboard asks for a token that is useful for exactly one thing:
# it names a single attachment, carries a distinct token type so it can never
# be replayed against the session-authenticated API, and expires in seconds.
DOWNLOAD_TOKEN_TYPE = "attachment_download"  # nosec B105 - a claim value, not a credential
DOWNLOAD_TOKEN_TTL_SECONDS = 60


def create_download_token(username: str, attachment_id: int) -> str:
    """Mint a short-lived token scoped to one attachment for one user."""
    return jwt.encode(
        {
            "sub": username,
            "typ": DOWNLOAD_TOKEN_TYPE,
            "aid": attachment_id,
            "exp": utcnow() + timedelta(seconds=DOWNLOAD_TOKEN_TTL_SECONDS),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def verify_download_token(token: str, attachment_id: int) -> str:
    """Return the username a download token authorises, or raise 401.

    Rejects a session JWT presented here: only a token minted by
    create_download_token for *this* attachment is accepted.
    """
    payload = decode_token(token)
    if payload.get("typ") != DOWNLOAD_TOKEN_TYPE:
        raise HTTPException(status_code=401, detail="Invalid download token")
    if payload.get("aid") != attachment_id:
        raise HTTPException(status_code=401, detail="Token is not valid for this file")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid download token")
    return username


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.AdminUser:
    """Accepts any authenticated IT staff member (admin or technician).

    The Authorization header is the only accepted carrier. WebSocket handshakes,
    which cannot set headers, validate their own ?token= via decode_token in the
    WebSocket routes; downloads use the scoped tokens above.
    """
    if not (credentials and credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)

    # A download token is signed with the same key, so without this check it
    # would authenticate the entire API for its lifetime. Only session tokens
    # get through here. Tokens minted before the "typ" claim existed carry no
    # type at all and stay valid, so adding this does not log anyone out.
    token_type = payload.get("typ")
    if token_type not in (None, SESSION_TOKEN_TYPE):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This token cannot be used to authenticate API requests",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
