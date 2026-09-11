# Changelog

All notable changes to this project will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added — audit trail
- New append-only `audit_log` table and `GET /audit` (super_admin only, with
  `action` / `actor` / `success` filters) recording privileged and
  security-relevant actions: login success and failure, password change, admin
  user create/delete, ticket assignment, KB approval/rejection, chat-session
  deletion, and self-update attempts.
- Records identifiers and outcomes only. Ticket descriptions, note bodies, chat
  messages, passwords and tokens are never written to it — tests assert that
  submitted passwords and message bodies do not appear in any entry.
- Writes commit in the same transaction as the action they describe, so there
  is no window where an action exists without its record.
- Excluded from the ticket retention sweep: "who deleted this ticket" must
  outlive the ticket.
- No new dependencies; existing SQLAlchemy models and the new table is created
  by `create_all` on startup, so upgrading needs no migration step.

### Performance
- `GET /tickets/` ran one COUNT query per ticket to populate `notes_count`,
  and both dashboards poll it every 20–30s per open tab. Replaced with a single
  GROUP BY aggregate: a 300-ticket listing went from 302 SQL statements to 3,
  and the count no longer grows with the table.

### Security — hardening pass
- **Rate-limit bypass closed.** `X-Forwarded-For` was trusted unconditionally,
  so any caller could rotate the header and walk past the login brute-force
  limiter. It is now honoured only when the real socket peer is listed in the
  new `TRUSTED_PROXY_IPS` setting, and the chain is walked right-to-left to the
  first untrusted hop.
- **Staff JWTs are no longer accepted from the URL.** `get_current_admin()` took
  a `?token=` query parameter, and both dashboards used it for attachment
  downloads — writing a full-privilege token into every access log on the path,
  browser history and `Referer`. Authentication is header-only for all HTTP
  routes; the dashboards fetch attachments with an `Authorization` header and a
  blob URL. WebSocket handshakes still use a query token, as the browser
  WebSocket API cannot send headers.
- **In-place self-update disabled by default.** `POST /update/apply` pulled code
  and `os.execv`'d the process, executing whatever the git remote served as the
  server user. Now gated behind `ALLOW_SELF_UPDATE` (default `false`), and
  `fetch` + `merge --ff-only` rather than `git pull --rebase` when enabled.

### Fixed — client auto-start
- Auto-start was implemented twice (startup self-heal and tray toggle) and had
  drifted apart. Consolidated into `client_app/autostart.py`, fixing three
  defects in the tray path: an **unquoted** executable path that silently broke
  auto-start for installs under `C:\Program Files\...`; `KeepAlive=false`
  contradicting the other implementation; and a macOS source-checkout entry that
  omitted the interpreter and could never launch.
- macOS `KeepAlive` is now `{SuccessfulExit: false}` — the client returns after a
  crash but honours a deliberate tray Quit.
- Both callers emit byte-identical entries, so an upgrade replaces the entry
  instead of leaving a stale second one.

### Fixed
- Deprecated `datetime.utcnow()` replaced with the timezone-correct
  `utils.utcnow()` helper (`backend/routers/update.py`).
- `ruff` is clean across `backend/`, `scripts/`, `tests/` and `client_app/`
  (import ordering, three unused Qt imports).

### Added — documentation
- `docs/TROUBLESHOOTING.md`: symptom → cause → fix covering server startup,
  connection/TLS errors, login lockouts, client auto-start, notifications,
  attachments, SmartScreen/Gatekeeper, antivirus quarantine of PyInstaller
  builds, and log locations.
- README: supported-OS matrix for server, desktop client (incl. the Windows 10
  1809 floor imposed by PySide6 6.11, and Apple Silicon build guidance) and
  browsers.
- `.env.example` documents `TRUSTED_PROXY_IPS` and `ALLOW_SELF_UPDATE`.

### Tests
- 30 → 63. New coverage: reverse-proxy header trust, rejection of URL-borne
  tokens, self-update gating, client credential-store migration (including a
  backend that accepts a write but does not persist it), and autostart
  registration/idempotency/upgrade behaviour.


### Added — Enterprise readiness (1.1)
- **Live chat**: secure end-user ↔ staff chat with agent presence
  (Available / Busy / Away / Offline), a staff queue with claim, and reusable
  response templates that are *inserted* into the reply editor for review rather
  than auto-sent. End users get a clear "Live Chat with IT" button in the
  desktop client (shown when an agent is available).
- **Knowledge management**: analysis of ticket history (frequent problems,
  common resolutions, repeated troubleshooting steps, common devices/
  departments/locations, and KB-article candidates), plus one-click AI-assisted
  **draft** generation. Generated content is always saved as a draft and must be
  approved by a super_admin — nothing is ever auto-published.
- **Ticket prioritisation**: `priority` (low/normal/high/urgent) with column,
  filter, per-ticket control, and priority-aware notifications; resolution
  summary captured on resolve.
- New endpoints: `/agent/*`, `/canned-responses`, `/chat/*`, `/kb/*`,
  `/tickets/{id}/priority`.
- pytest test suite (`tests/`) covering ticket numbering + concurrency, RBAC,
  security headers, magic-byte upload validation, chat, and the KB approval flow.

### Added — Technician-first routing, branding, client updates (1.2)
- **Technician-first chat routing**: new/unclaimed chats page available
  technicians first instead of admins, falling back to admins only if no
  technician is online. Technicians can **escalate** a session to the admin
  queue; escalated sessions drop out of the technician's default view.
- **Presence-aware notification gating**: an `available` agent is notified on
  every message; a `busy` agent only every 5th unread message; `away`/`offline`
  agents get none until they return (unread badge shows what they missed).
- **Chat session deletion** (`super_admin` only) — permanently removes a
  session, its messages, and related notifications.
- **Always-reachable live chat**: the desktop client's chat button no longer
  blocks when nobody's online — it opens the chat and tells the user their
  message will be answered once an agent's back, instead of refusing to start
  a conversation.
- **Custom branding**: `super_admin` can upload a PNG/JPEG logo (magic-byte
  validated, 2MB cap) that replaces the default 🎫 icon across both dashboards
  and the desktop client (login screen, sidebar, tray icon, header).
- **Desktop client version push**: `super_admin` publishes a version/URL/notes
  from the Updates tab; the client checks on launch (and daily) and shows an
  update dialog with a direct download link, optionally marked mandatory.
- 8 seeded canned responses (was 0) and new tests covering technician-first
  routing, escalation visibility, the busy-agent threshold, and delete
  authorization.

### Fixed
- **Duplicate ticket numbers under concurrency**: replaced the racy `count()+1`
  scheme with an atomic per-day counter (`UPDATE last_seq + 1`) plus retry on
  contention. Verified by a 40-way concurrent-creation test.
- **Desktop client reliability** ("disappears / loses connection"): login
  autostart is now re-registered on every launch (self-healing) with a quoted
  executable path; macOS LaunchAgent uses `KeepAlive`; a single-instance guard
  prevents duplicates; when no system tray is available the window minimises
  instead of vanishing; and the server URL is configurable at runtime
  (`HELPDESK_SERVER_URL` / Settings dialog) so an IP change no longer bricks
  deployed clients. Added a live connection indicator.
- SQLite now runs in WAL mode with a busy timeout and foreign keys enforced,
  removing "database is locked" errors under concurrent use.
- Replaced deprecated `datetime.utcnow()` with a timezone-safe helper.

### Security
- `SECRET_KEY` no longer falls back to a predictable static default; when unset
  it is auto-generated and persisted to a gitignored `secret.key`.
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-
  Policy, Permissions-Policy) added to every response.
- CORS no longer combines a wildcard origin with credentials.
- In-memory rate limiting on the public ticket/attachment/chat endpoints and on
  login (brute-force protection).
- Attachment uploads validated by magic bytes, not just the client-declared
  content type.
- Idempotent startup migrations add new columns to existing databases without
  data loss.

---

## [1.0.0] — 2026-04-21

Initial public open-source release.

### Added
- FastAPI backend with SQLite database
- JWT authentication with `super_admin` and `technician` roles
- Ticket CRUD with category and sub-category validation
- File attachment support (PDF, images — stored as database blobs, max 10 MB)
- Internal notes system per ticket
- Real-time WebSocket bell notifications for staff
- Polling-based notifications for desktop client app
- Admin web dashboard (`/admin`) — ticket management, user management, assignment
- Technician web portal (`/tech`) — assigned ticket view, status updates, notes
- PySide6 desktop tray client for Windows and macOS (end-user ticket submission)
- Windows background daemon (`server_daemon.py`) — auto-restart on crash
- `setup.bat` (Windows) and `setup.sh` (macOS/Linux) for one-command deployment
- Automatic cleanup of records older than 30 days (runs daily at 2:00 AM)
- Optional GitHub Releases auto-update mechanism
- `scripts/init_db.py` seed script with demo users and tickets
- MIT License
- Full documentation: Admin Guide, Technician Guide, User Guide, Security Analysis

### Security
- Passwords hashed with bcrypt
- JWT tokens expire after 8 hours
- `SECRET_KEY` loaded from environment variable with startup warning if unset
- CORS configurable via `CORS_ORIGINS` environment variable
- File uploads restricted to allowed MIME types server-side
- All admin/tech endpoints protected by role-based access control

---

[Unreleased]: https://github.com/gurungsandex/ticketing-system/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/gurungsandex/ticketing-system/releases/tag/v1.0.0
