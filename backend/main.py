"""
MOM IT Helpdesk — Backend v4.0
================================
Run directly (development):
    cd backend
    uvicorn main:app --host 0.0.0.0 --port 8000

Run via setup script (simple):
    Windows : setup.bat        (from project root)
    macOS   : ./setup.sh       (from project root)

Run via PM2 (background service):
    pm2 start ecosystem.config.js
"""
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Union

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from database import engine, get_db, SessionLocal
import models
import schemas
from auth import hash_password, verify_password, create_access_token, get_current_admin
from routers import tickets, admin, notifications, update

# ── Logging ───────────────────────────────────────────
logging.basicConfig(level=logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

# ── Tables ────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)

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


# ── Lifespan (replaces deprecated @app.on_event) ──────
@asynccontextmanager
async def lifespan(application: FastAPI):
    # ── Startup ──────────────────────────────────────
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
            print("⚠  Default admin created: admin / admin123 — CHANGE THIS PASSWORD NOW!")
    finally:
        db.close()

    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(_cleanup_old_records, "cron", hour=2, minute=0)
    scheduler.start()

    print("✓  MOM Helpdesk v4.0 ready")
    print("   Admin:      http://0.0.0.0:8000/admin")
    print("   Technician: http://0.0.0.0:8000/tech")

    yield  # ← application runs here

    # ── Shutdown ─────────────────────────────────────
    scheduler.shutdown(wait=False)


# ── App ───────────────────────────────────────────────
app = FastAPI(
    title="MOM IT Helpdesk",
    version="4.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# CORS — restrict to your server IP in production via env var
_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────
app.include_router(tickets.router)
app.include_router(admin.router)
app.include_router(notifications.router)
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
    return {"status": "ok", "version": "4.0.0"}

# ── Auth ──────────────────────────────────────────────
@app.post("/auth/login", response_model=schemas.LoginResponse)
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)):
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
    """Delete tickets, notes, attachments, and notifications older than 30 days."""
    cutoff = datetime.utcnow() - timedelta(days=30)
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
            print(f"[cleanup] Removed {len(old)} tickets older than 30 days.")
    except Exception as e:
        db.rollback()
        print(f"[cleanup] Error: {e}")
    finally:
        db.close()
