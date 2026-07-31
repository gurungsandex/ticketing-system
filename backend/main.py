"""
IT Ticketing System — Backend
=============================
Run directly (development):
    cd backend
    uvicorn main:app --host 0.0.0.0 --port 8000

Run via setup script (background):
    Windows : setup.bat        (from project root)
    macOS   : ./setup.sh       (from project root)
"""
import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Union

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

import config  # noqa: E402
import models  # noqa: E402
import schemas  # noqa: E402
from auth import (  # noqa: E402
    create_access_token,
    get_current_admin,
    hash_password,
    verify_password,
)
from database import SessionLocal, engine, get_db  # noqa: E402
from fastapi import Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse  # noqa: E402
from migrations import run_migrations  # noqa: E402
from routers import admin, chat, knowledge, notifications, tickets, update  # noqa: E402
from security import SecurityHeadersMiddleware, rate_limit  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from utils import utcnow  # noqa: E402

# ── Logging ───────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# ── Tables + migrations ───────────────────────────────
models.Base.metadata.create_all(bind=engine)
run_migrations(engine)

# ── Static HTML paths ─────────────────────────────────
_BASE       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ADMIN_HTML = os.path.join(_BASE, "admin_panel", "index.html")
_TECH_HTML  = os.path.join(_BASE, "tech_panel",  "index.html")


def _serve_html(path: str, label: str) -> Union[FileResponse, HTMLResponse]:
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return HTMLResponse(
        f"<h2>{label} panel not found.</h2>"
        f"<p>Expected at: <code>{path}</code></p>",
        status_code=404,
    )


# ── Lifespan ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    db = SessionLocal()
    try:
        if not db.query(models.AdminUser).filter(
            models.AdminUser.role == "super_admin"
        ).first():
            db.add(models.AdminUser(
                username="admin",
                hashed_password=hash_password("admin123"),
                role="super_admin",
            ))
            db.commit()
            print("[!] Default admin created: admin / admin123 -- CHANGE THIS PASSWORD NOW!")
    finally:
        db.close()

    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(daemon=True)
    if config.TICKET_RETENTION_DAYS > 0:
        scheduler.add_job(_cleanup_old_records, "cron", hour=2, minute=0)
    scheduler.start()

    if config.SECRET_KEY_AUTO_GENERATED:
        print("=" * 60)
        print("[NOTICE] SECRET_KEY not set — using an auto-generated key")
        print("  persisted to backend/secret.key (gitignored). Tokens survive")
        print("  restarts. For multi-node or production, set SECRET_KEY in .env.")
        print("=" * 60)

    print(f"[OK] IT Ticketing System v{config.VERSION} ready")
    print(f"   Admin:      http://{config.HOST}:{config.PORT}/admin")
    print(f"   Technician: http://{config.HOST}:{config.PORT}/tech")

    yield

    scheduler.shutdown(wait=False)


# ── App ───────────────────────────────────────────────
app = FastAPI(
    title="IT Ticketing System",
    version=config.VERSION,
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Security headers on every response.
app.add_middleware(SecurityHeadersMiddleware)

# CORS. "*" is incompatible with credentialed requests per the CORS spec, so
# when all origins are allowed we must NOT also send allow_credentials=True.
if config.CORS_ALLOW_ALL:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ── Routers ───────────────────────────────────────────
app.include_router(tickets.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(update.router)


# ── Static routes ─────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return HTMLResponse("<meta http-equiv='refresh' content='0; url=/admin'>", status_code=302)


@app.get("/admin",  include_in_schema=False)
@app.get("/admin/", include_in_schema=False)
def serve_admin():
    return _serve_html(_ADMIN_HTML, "Admin")


@app.get("/tech",  include_in_schema=False)
@app.get("/tech/", include_in_schema=False)
def serve_tech():
    return _serve_html(_TECH_HTML, "Technician")


# ── Health ────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "version": config.VERSION}


# ── Auth ──────────────────────────────────────────────
@app.post("/auth/login", response_model=schemas.LoginResponse)
def login(body: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Throttle brute-force attempts per client IP.
    rate_limit(request, "login", config.RATE_LIMIT_LOGIN)
    user = db.query(models.AdminUser).filter(
        models.AdminUser.username == body.username
    ).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": user.username, "role": user.role})
    return schemas.LoginResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        username=user.username,
    )


@app.patch("/auth/change-password")
def change_password(
    body: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.AdminUser = Depends(get_current_admin),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    current_user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


# ── Scheduled cleanup ─────────────────────────────────
def _cleanup_old_records():
    """Delete tickets, notes, attachments, and notifications older than the
    configured retention window. Disabled entirely when retention is 0."""
    if config.TICKET_RETENTION_DAYS <= 0:
        return
    cutoff = utcnow() - timedelta(days=config.TICKET_RETENTION_DAYS)
    db = SessionLocal()
    try:
        old = db.query(models.Ticket).filter(models.Ticket.created_at < cutoff).all()
        for t in old:
            db.query(models.Note).filter(models.Note.ticket_id == t.id).delete()
            db.query(models.Attachment).filter(models.Attachment.ticket_id == t.id).delete()
            db.delete(t)
        db.query(models.Notification).filter(
            models.Notification.created_at < cutoff
        ).delete()
        db.commit()
        if old:
            print(f"[cleanup] Removed {len(old)} tickets older than "
                  f"{config.TICKET_RETENTION_DAYS} days.")
    except Exception as e:
        db.rollback()
        print(f"[cleanup] Error: {e}")
    finally:
        db.close()
