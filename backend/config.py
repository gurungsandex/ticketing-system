"""
Centralized configuration for the IT Ticketing System.

All runtime settings are resolved here so the rest of the codebase reads a
single, well-documented source of truth instead of scattered os.environ calls.

Security note on SECRET_KEY
---------------------------
Older builds fell back to a *static* default key when SECRET_KEY was unset.
That is dangerous: anyone who reads the source can forge JWTs. Instead, when
no key is configured we generate a strong random key ONCE and persist it to a
gitignored file (secret.key) beside the database, then reuse it on every
restart. This keeps small LAN deployments working out-of-the-box while never
shipping a predictable, publicly-known signing key.
"""
import os
import secrets
from pathlib import Path

# Project root = parent of the backend/ directory that holds this file.
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_secret_key() -> tuple[str, bool]:
    """Return (secret_key, is_generated).

    Priority:
      1. SECRET_KEY environment variable (recommended for production).
      2. A persisted secret.key file next to the backend (auto-managed).
      3. A freshly generated key written to secret.key.
    """
    env_key = os.environ.get("SECRET_KEY", "").strip()
    # Reject the historical insecure placeholder so it can never be used.
    if env_key and env_key != "HELPDESK_SECRET_KEY_CHANGE_IN_PRODUCTION":
        return env_key, False

    key_file = BASE_DIR / "secret.key"
    if key_file.exists():
        stored = key_file.read_text(encoding="utf-8").strip()
        if stored:
            return stored, True

    generated = secrets.token_hex(32)
    try:
        key_file.write_text(generated, encoding="utf-8")
        # Restrict permissions where the OS supports it (POSIX).
        try:
            os.chmod(key_file, 0o600)
        except (OSError, NotImplementedError):
            pass
    except OSError:
        # Read-only filesystem — fall back to an in-memory key for this run.
        pass
    return generated, True


SECRET_KEY, SECRET_KEY_AUTO_GENERATED = _resolve_secret_key()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("ACCESS_TOKEN_EXPIRE_HOURS", "8"))

# ── Network / CORS ────────────────────────────────────
# Binding to all interfaces is intentional: this is a self-hosted LAN server
# that end-user clients and staff browsers reach over the local network. Lock
# it to a specific interface by setting HOST, and restrict exposure at the
# firewall / reverse proxy.
HOST = os.environ.get("HOST", "0.0.0.0")  # nosec B104 - LAN server binds all interfaces by design
PORT = int(os.environ.get("PORT", "8000"))

# CORS. Default "*" keeps LAN deployments frictionless, but "*" is incompatible
# with credentialed requests per the CORS spec, so we surface both values and
# let main.py choose a safe middleware configuration.
CORS_ORIGINS_RAW = os.environ.get("CORS_ORIGINS", "*")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_RAW.split(",") if o.strip()]
CORS_ALLOW_ALL = CORS_ORIGINS == ["*"] or not CORS_ORIGINS

# ── Rate limiting (in-memory, per-process) ────────────
# Sensible defaults that stop spam/DoS on the intentionally-unauthenticated
# public endpoints without hindering normal use. Tunable via env.
RATE_LIMIT_ENABLED = _bool_env("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_TICKET_CREATE = int(os.environ.get("RATE_LIMIT_TICKET_CREATE", "20"))   # per window / IP
RATE_LIMIT_ATTACHMENT = int(os.environ.get("RATE_LIMIT_ATTACHMENT", "30"))          # per window / IP
RATE_LIMIT_LOGIN = int(os.environ.get("RATE_LIMIT_LOGIN", "10"))                     # per window / IP
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

# ── Uploads ───────────────────────────────────────────
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))  # 10 MB

# ── Data retention ────────────────────────────────────
# Tickets older than this are auto-removed at 02:00. 0 disables cleanup so
# larger corporate deployments can retain full history for auditing.
TICKET_RETENTION_DAYS = int(os.environ.get("TICKET_RETENTION_DAYS", "0"))

# ── Field length caps (defence-in-depth against oversized input) ──
MAX_DESCRIPTION_LEN = int(os.environ.get("MAX_DESCRIPTION_LEN", "5000"))
MAX_NOTE_LEN = int(os.environ.get("MAX_NOTE_LEN", "5000"))
MAX_CHAT_MESSAGE_LEN = int(os.environ.get("MAX_CHAT_MESSAGE_LEN", "4000"))
MAX_GENERIC_TEXT_LEN = int(os.environ.get("MAX_GENERIC_TEXT_LEN", "300"))

VERSION = "1.1.0"
