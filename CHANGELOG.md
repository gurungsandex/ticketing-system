# Changelog

All notable changes to this project will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
