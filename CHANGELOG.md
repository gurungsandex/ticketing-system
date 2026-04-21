# Changelog

All notable changes to this project will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_Changes on `master` not yet tagged as a release._

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
