# Security Analysis — MOM IT Helpdesk v4.0

---

## Authentication

**JWT (JSON Web Tokens)** signed with HS256. Tokens expire after 8 hours. A 1-hour idle timeout is enforced in both dashboards — the session clears automatically on inactivity.

Tokens are stored in `sessionStorage`, which is wiped when the browser tab is closed. This is preferable to `localStorage` which persists indefinitely across sessions.

### Required Before Production

Replace the default signing key in `backend/auth.py`:

```python
SECRET_KEY = "HELPDESK_SECRET_KEY_CHANGE_IN_PRODUCTION"
```

Generate a strong key:

**Windows:**
```cmd
python -c "import secrets; print(secrets.token_hex(32))"
```

**macOS:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Replace the value in `backend/auth.py` with the generated string, then restart the server. Anyone with the old key can forge valid tokens — this step is critical.

---

## Authorisation (RBAC)

Role enforcement is implemented at the **API level** — not just the frontend. A technician using a direct HTTP client (e.g. curl) still receives HTTP 403 on restricted endpoints.

| Action | Admin (super_admin) | Technician |
|---|---|---|
| View all tickets | ✅ | ❌ own tickets only |
| Assign ticket | ✅ | ❌ |
| Update ticket status | ✅ any ticket | ✅ assigned tickets only |
| Add internal note | ✅ any ticket | ✅ assigned tickets only |
| Download attachment | ✅ | ✅ assigned tickets only |
| Manage users | ✅ | ❌ |
| Apply updates | ✅ | ❌ |

---

## File Uploads

- **MIME type whitelist:** Only `image/png`, `image/jpeg`, `image/jpg`, `image/gif`, `image/webp`, `image/bmp`, and `application/pdf` are accepted. All other types return HTTP 400.
- **Size limit:** 10 MB per attachment. Larger files return HTTP 400.
- **Filename sanitisation:** Path separators (`/`, `\`) are stripped from filenames before storage to prevent path traversal.
- **Storage method:** Files are stored as binary blobs inside SQLite — not on the filesystem. This prevents directory traversal attacks and eliminates the risk of web server directory listing exposing uploaded files.

**Known limitation:** The MIME type check reads the `Content-Type` header from the upload request, which is set by the client and can be spoofed. For stronger validation, add file magic byte checking using the `python-magic` library.

---

## File Downloads

Downloads are authenticated via a `?token=` query parameter appended to the download URL:

```
http://SERVER_IP:8000/attachments/3/download?token=eyJhbGci...
```

The backend's `get_current_admin` dependency accepts this token from the query string and validates it identically to the `Authorization: Bearer` header. The file is served with `Content-Disposition: attachment` forcing a browser download rather than inline display.

**Security consideration:** The JWT appears in the download URL, which means it may appear in server access logs and browser network history. For the internal LAN use case this is acceptable. If the server is ever exposed externally, consider issuing short-lived single-use download tokens instead.

---

## Input Validation

- All API request bodies are validated by **Pydantic** schemas before reaching any business logic. Malformed or unexpected fields are rejected automatically.
- Ticket categories are validated against a hardcoded server-side allowlist — clients cannot create tickets with arbitrary category strings.
- All user-supplied content rendered in the dashboards passes through an `esc()` function that replaces `&`, `<`, `>`, and `"` with HTML entities, preventing Cross-Site Scripting (XSS).

---

## SQL Injection

The backend uses **SQLAlchemy ORM** with parameterised queries throughout. No raw SQL strings are constructed from user input. SQL injection risk is low.

---

## Transport Security

The server communicates over **HTTP** on the LAN. This is acceptable for a physically secured internal network where traffic is not leaving the building.

**If the server must be accessible outside the building:**

1. Place **Nginx** as a reverse proxy in front of uvicorn
2. Configure TLS on Nginx (self-signed certificate for internal use; Let's Encrypt for internet-facing)
3. Restrict `CORS_ORIGINS` to the specific domain or IP
4. Consider using a VPN rather than exposing port 8000 directly

---

## CORS

Current setting: `allow_origins=["*"]` — all origins are permitted. This is safe only on an isolated internal network.

To restrict for production, set the `CORS_ORIGINS` environment variable:

**PM2 — `ecosystem.config.js`:**
```javascript
env: {
  CORS_ORIGINS: "http://192.168.1.50:8000",
},
```

**setup.bat:**
```cmd
set CORS_ORIGINS=http://192.168.1.50:8000
```

**setup.sh:**
```bash
export CORS_ORIGINS="http://192.168.1.50:8000"
```

---

## Session Security

- Tokens are in `sessionStorage` — cleared on tab close, not persisted to disk
- 1-hour idle timeout enforced in both admin and technician dashboards
- Download tokens appear in URLs (see File Downloads section above)
- WebSocket handshake uses `?token=` — this is a one-time connection parameter and is not reusable

---

## HIPAA Considerations

The helpdesk system does not intentionally store Protected Health Information (PHI). What it does store:

- Workstation names, LAN IP addresses, and Windows usernames
- Issue descriptions and internal notes typed by IT staff
- Screenshot attachments — which may inadvertently contain PHI if a user captures a screen showing patient data

**Recommended controls:**

- Train staff not to include patient names or record numbers in ticket descriptions or screenshots
- The 30-day automatic deletion is enabled by default — verify the retention period meets your organisation's policy
- Back up `helpdesk.db` to an encrypted location (encrypted drive or encrypted backup service)
- Include `helpdesk.db` in your organisation's existing data classification and access control policies

---

## Production Hardening Checklist

| Item | Priority | Status |
|---|---|---|
| Replace `SECRET_KEY` in `backend/auth.py` with a random 64-character value | **Critical** | |
| Change default admin password (`admin` / `admin123`) | **Critical** | |
| Open port 8000 only to your workstation subnet (not `0.0.0.0/0`) | High | |
| Set `CORS_ORIGINS` to your specific server IP | High | |
| Schedule regular `helpdesk.db` backups | Medium | |
| Add Nginx + TLS if server is ever accessed outside the building | Medium | |
| Add magic byte validation to file uploads (`python-magic`) | Low | |
| Add login rate limiting (`slowapi`) to prevent brute force | Low | |
