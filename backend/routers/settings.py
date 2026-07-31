import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import models
import schemas
from auth import require_super_admin
from database import get_db
from security import detect_content_type

router = APIRouter()

_ALLOWED_LOGO_MIMES = {"image/png": ".png", "image/jpeg": ".jpg"}
_MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2MB

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "branding"
)
os.makedirs(_STATIC_DIR, exist_ok=True)


def _get_setting(db: Session, key: str) -> str:
    row = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
    return row.value if row else ""


def _set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(models.AppSetting(key=key, value=value))


# ── Branding / logo upload ─────────────────────────────

@router.get("/branding/logo")
def get_branding_logo(db: Session = Depends(get_db)):
    filename = _get_setting(db, "branding_logo_path")
    mimetype = _get_setting(db, "branding_logo_mimetype") or "image/png"
    if not filename:
        raise HTTPException(status_code=404, detail="No custom logo configured")
    full_path = os.path.join(_STATIC_DIR, filename)
    if not os.path.abspath(full_path).startswith(os.path.abspath(_STATIC_DIR) + os.sep):
        raise HTTPException(status_code=404, detail="No custom logo configured")
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="No custom logo configured")
    return FileResponse(full_path, media_type=mimetype)


@router.get("/branding", response_model=schemas.BrandingResponse)
def get_branding_status(db: Session = Depends(get_db)):
    return schemas.BrandingResponse(logo_configured=bool(_get_setting(db, "branding_logo_path")))


@router.post("/settings/logo", response_model=schemas.BrandingResponse)
async def upload_branding_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(require_super_admin),
):
    claimed_mime = file.content_type or ""
    if claimed_mime not in _ALLOWED_LOGO_MIMES:
        raise HTTPException(status_code=400, detail="Only PNG or JPEG images are allowed.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > _MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail="Logo must be smaller than 2MB.")

    # Verify the real content, not just the client-declared type.
    real_mime = detect_content_type(data)
    if real_mime not in _ALLOWED_LOGO_MIMES:
        raise HTTPException(status_code=400, detail="File content does not look like a PNG or JPEG image.")

    ext = _ALLOWED_LOGO_MIMES[real_mime]
    filename = f"logo{ext}"  # fixed name — never derived from the client-supplied filename
    with open(os.path.join(_STATIC_DIR, filename), "wb") as f:
        f.write(data)

    # Clean up a stale logo saved under the other allowed extension.
    for other_ext in _ALLOWED_LOGO_MIMES.values():
        if other_ext != ext:
            stale = os.path.join(_STATIC_DIR, f"logo{other_ext}")
            if os.path.exists(stale):
                os.remove(stale)

    _set_setting(db, "branding_logo_path", filename)
    _set_setting(db, "branding_logo_mimetype", real_mime)
    db.commit()
    return schemas.BrandingResponse(logo_configured=True)


@router.delete("/settings/logo", response_model=schemas.BrandingResponse)
def delete_branding_logo(
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(require_super_admin),
):
    filename = _get_setting(db, "branding_logo_path")
    if filename:
        full_path = os.path.join(_STATIC_DIR, filename)
        if os.path.exists(full_path):
            os.remove(full_path)
    _set_setting(db, "branding_logo_path", "")
    _set_setting(db, "branding_logo_mimetype", "")
    db.commit()
    return schemas.BrandingResponse(logo_configured=False)


# ── Desktop client versioning ──────────────────────────

@router.get("/client/version", response_model=schemas.ClientVersionResponse)
def get_client_version(db: Session = Depends(get_db)):
    return schemas.ClientVersionResponse(
        latest_version=_get_setting(db, "client_latest_version") or "1.0.0",
        download_url=_get_setting(db, "client_download_url") or None,
        release_notes=_get_setting(db, "client_release_notes") or None,
        mandatory=_get_setting(db, "client_mandatory") == "true",
    )


@router.patch("/settings/client-version", response_model=schemas.ClientVersionResponse)
def push_client_version(
    body: schemas.ClientVersionUpdate,
    db: Session = Depends(get_db),
    _admin: models.AdminUser = Depends(require_super_admin),
):
    _set_setting(db, "client_latest_version", body.latest_version.strip()[:32])
    _set_setting(db, "client_download_url", body.download_url.strip()[:2000])
    _set_setting(db, "client_release_notes", (body.release_notes or "").strip()[:2000])
    _set_setting(db, "client_mandatory", "true" if body.mandatory else "false")
    db.commit()
    return get_client_version(db)
