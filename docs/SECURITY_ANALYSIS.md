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
- [ ] Default demo canned responses/branding reviewed before go-live
- [ ] `client_latest_version` pushed to match the actual client build before wide distribution

---

## Version 1.1 — Enterprise Hardening Update

The following controls were added in 1.1 and change several of the statuses above.

| Item | 1.0 | 1.1 |
|---|---|---|
| `SECRET_KEY` default | Predictable static fallback | Auto-generated & persisted to gitignored `secret.key`; no known key ever ships |
| Rate limiting | Not implemented | In-memory limiter on `POST /tickets/`, attachment upload, chat, and login |
| Security headers | None | CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` on every response |
| CORS | `*` + credentials (invalid) | Wildcard never combined with credentials; explicit origins get credentials |
| Attachment validation | Client-declared MIME only | Magic-byte (content) validation rejects spoofed types |
| Concurrent writes | "database is locked" possible | SQLite WAL + busy timeout + FK enforcement |
| Duplicate ticket numbers | Possible under load | Atomic per-day counter with retry (race-tested) |
| Input size | Unbounded text fields | Length caps on descriptions, notes, and chat messages |

### OWASP Top 10 coverage notes

- **A01 Broken Access Control** — RBAC enforced server-side on every ticket, note,
  chat, and KB endpoint; chat sessions are scoped to the owning `client_id`; KB
  approval restricted to `super_admin`.
- **A02 Cryptographic Failures** — bcrypt password hashing; JWT signed with a
  non-guessable key.
- **A03 Injection** — SQLAlchemy parameterised queries throughout; output escaped
  in the panels.
- **A04 Insecure Design** — AI-generated KB content cannot be auto-published; it is
  gated behind human approval.
- **A05 Security Misconfiguration** — security headers, safe CORS, and a fail-safe
  secret key.
- **A07 Identification & Auth Failures** — login rate limiting mitigates brute force.

### Still recommended for internet-facing deployments

- Terminate TLS at a reverse proxy (nginx/Caddy) and set `CORS_ORIGINS`.
- Consider a structured audit log and short-lived tokens with refresh if you need
  session revocation.

---

## Version 1.2 — Technician-First Routing, Branding, Client Versioning

- **Chat escalation is any-staff, deletion is `super_admin`-only** — `POST
  /chat/sessions/{id}/escalate` requires only a valid staff JWT (either role can
  hand a chat to the admin queue), while `DELETE /chat/sessions/{id}` explicitly
  checks `current_user.role == "super_admin"` and hard-deletes the session, its
  messages, and its `Notification` rows.
- **Notification routing is presence- and role-aware** — new/unclaimed chats page
  available technicians first (falling back to all admins only if literally no
  technician is online, so nothing is silently dropped); once claimed, the
  assigned agent is notified immediately if `available`, throttled to every 5th
  unread message if `busy` (`BUSY_NOTIFY_EVERY` in `chat.py`), and never notified
  while `away`/`offline`. The `unread_count` counter that drives this can only be
  cleared by the session's own assigned agent (`get_chat_messages`,
  `post_agent_message`, `claim_chat_session`) — an unrelated staff member merely
  viewing a thread cannot silently suppress another agent's notifications.
- **Branding logo upload validates real file content, not just the declared
  MIME type** — `POST /settings/logo` (`super_admin` only) re-derives the type
  from magic bytes via `security.detect_content_type()` (the same helper used
  for ticket attachments), caps the upload at 2MB, and always writes to a fixed
  filename (`logo.png`/`logo.jpg`) derived from the verified type — the
  client-supplied filename is never used for the on-disk path, ruling out path
  traversal via a crafted filename.
- **`GET /branding/logo` and `GET /client/version` are intentionally public** —
  they expose only a logo image and non-sensitive version/URL metadata, mirroring
  the existing public `GET /chat/availability` pattern; both are backed by a new
  generic `AppSetting` key/value table, not per-user data.
- **Known limitation carried forward**: canned-response create/delete
  (`POST`/`DELETE /canned-responses`) remains available to any authenticated
  staff member, not just `super_admin` — acceptable for an internal tool where
  all staff are trusted, but worth tightening if templates should be
  admin-curated only.
