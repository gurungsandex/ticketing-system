# Security Analysis — IT Ticketing System

---

## Authentication

### JWT Tokens

- Algorithm: **HS256**
- Expiry: **8 hours**
- Signing secret: read from `SECRET_KEY` environment variable
- Fallback: an insecure hardcoded default (prints a startup warning — never use in production)

### Password Hashing

- Algorithm: **bcrypt** with random salt
- Minimum password length: **8 characters** (enforced server-side)

### Bearer Token Transport

- Standard requests: `Authorization: Bearer <token>` header
- WebSocket connections: `?token=<token>` query parameter (required because browsers cannot send custom headers on WebSocket upgrade)
- File downloads: `?token=<token>` query parameter (to allow direct browser navigation)

---

## Authorization (RBAC)

| Role | Access |
|---|---|
| `super_admin` | All endpoints including user management, ticket assignment, and the update API |
| `technician` | Own assigned tickets, notes, attachments. Cannot manage users or assign tickets. |
| Unauthenticated | `POST /tickets/` (ticket creation) and `GET /notifications/{client_id}` (client polling) only |

The public `POST /tickets/` endpoint is intentionally unauthenticated — it is how the desktop client app submits tickets without requiring end-users to have accounts.

---

## Input Validation

- All request bodies are validated with **Pydantic v2** schemas
- Ticket categories are validated against a whitelist (13 allowed values)
- File uploads are restricted to: `application/pdf`, `image/jpeg`, `image/png`, `image/gif`, `image/webp`
- Maximum attachment size: **10 MB** per file
- Minimum password length enforced on both user creation and password change endpoints

---

## File Storage

- Attachments are stored as **binary blobs in the SQLite database** — not on the filesystem
- No file path traversal risk
- No serving of user-uploaded content as static files
- Downloads are authenticated (token required)

---

## CORS

- Default: `allow_origins=["*"]` (suitable for internal LAN deployment)
- Configurable via `CORS_ORIGINS` environment variable for production hardening
- Credentials are allowed (required for cookie-based auth if ever implemented)

Recommendation: set `CORS_ORIGINS` to your specific server IP in production:
```
CORS_ORIGINS=http://192.168.1.50:8000
```

---

## Database

- **SQLite** — single file at `backend/helpdesk.db`
- No SQL injection risk: SQLAlchemy ORM with parameterized queries throughout
- The database file should not be web-accessible and should be excluded from version control (`.gitignore` enforces this)

---

## Transport Security

- No TLS/HTTPS is included by default — the system is designed for internal LAN use
- For deployments accessible outside the LAN, place a **reverse proxy** (Nginx, Caddy) in front to terminate TLS
- See the README for a sample Nginx HTTPS configuration

---

## Secrets Management

- `SECRET_KEY` is loaded from the `.env` file via `python-dotenv`
- `.env` is listed in `.gitignore` and is never committed to version control
- `.env.example` provides a safe template with no real values

---

## Automatic Data Cleanup

- Tickets and all related records (notes, attachments, notifications) older than **30 days** are automatically deleted daily at **2:00 AM**
- This is a privacy and storage management measure

---

## Known Limitations

| Item | Status | Notes |
|---|---|---|
| HTTPS | Not built-in | Use a reverse proxy for TLS |
| Rate limiting | Not implemented | Add via nginx `limit_req` or a FastAPI middleware if needed |
| Audit logging | Not implemented | Server logs requests at WARNING level; no structured audit trail |
| Multi-worker support | Not supported | SQLite does not support concurrent writes from multiple workers |
| Session invalidation | Not supported | JWT tokens cannot be revoked before expiry (8-hour window) |
| 2FA | Not implemented | Standard username/password auth only |

---

## Pre-Deployment Security Checklist

- [ ] `SECRET_KEY` is set to a strong random value in `.env`
- [ ] Default `admin` password has been changed
- [ ] `CORS_ORIGINS` is restricted to your server IP
- [ ] `backend/helpdesk.db` is backed up regularly
- [ ] Server firewall restricts port 8000 to the internal subnet only
- [ ] If externally accessible: HTTPS reverse proxy is configured
- [ ] `.env` is not committed to version control
