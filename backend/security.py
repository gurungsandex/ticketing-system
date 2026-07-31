"""
Security utilities: response headers, in-memory rate limiting, and real
file-type (magic byte) validation.

These are deliberately dependency-free so they add no new packages and work in
air-gapped LAN deployments.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

import config
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

# ── Security headers ──────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard hardening headers to every response (OWASP Secure Headers)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("X-XSS-Protection", "0")  # modern guidance: rely on CSP, disable legacy filter
        headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        # The self-contained panels use inline styles/scripts, so allow 'unsafe-inline'
        # for style/script but lock everything else down. connect-src stays broad so the
        # panel can reach the API/WebSocket on whatever host it is configured for.
        headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src *; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "object-src 'none'",
        )
        return response


# ── Rate limiting ─────────────────────────────────────

class RateLimiter:
    """Simple fixed-window-ish sliding limiter keyed by client identity.

    Not distributed (per-process), which is appropriate for the single-node
    deployments this app targets. Thread-safe.
    """

    def __init__(self):
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Return True if the request is allowed, False if over the limit."""
        if not config.RATE_LIMIT_ENABLED or limit <= 0:
            return True
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._hits[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """Best-effort client IP. Honours the first X-Forwarded-For hop for
    deployments behind a trusted reverse proxy, else the socket peer."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request, bucket: str, limit: int) -> None:
    """Raise HTTP 429 if the caller has exceeded `limit` in the configured window."""
    key = f"{bucket}:{client_ip(request)}"
    if not _limiter.check(key, limit, config.RATE_LIMIT_WINDOW_SECONDS):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down and try again shortly.",
            headers={"Retry-After": str(config.RATE_LIMIT_WINDOW_SECONDS)},
        )


# ── File magic-byte validation ────────────────────────

# Map allowed MIME types to signature checks. content_type is client-supplied
# and therefore untrusted; we verify the actual bytes.
def _looks_like_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _looks_like_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def _looks_like_jpeg(data: bytes) -> bool:
    return data[:3] == b"\xff\xd8\xff"


def _looks_like_gif(data: bytes) -> bool:
    return data[:6] in (b"GIF87a", b"GIF89a")


def _looks_like_webp(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def _looks_like_bmp(data: bytes) -> bool:
    return data[:2] == b"BM"


_SIGNATURE_CHECKS = {
    "application/pdf": _looks_like_pdf,
    "image/png": _looks_like_png,
    "image/jpeg": _looks_like_jpeg,
    "image/jpg": _looks_like_jpeg,
    "image/gif": _looks_like_gif,
    "image/webp": _looks_like_webp,
    "image/bmp": _looks_like_bmp,
}

ALLOWED_MIMES = set(_SIGNATURE_CHECKS.keys())


def detect_content_type(data: bytes) -> str | None:
    """Return the true MIME type inferred from the file's magic bytes, or None
    if it is not one of our allowed types."""
    for mime, check in _SIGNATURE_CHECKS.items():
        # Skip the duplicate image/jpg alias when reporting the canonical type.
        if mime == "image/jpg":
            continue
        if check(data):
            return mime
    return None
