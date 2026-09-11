# Changelog

All notable changes to this project will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Security

- **Session JWTs no longer travel in attachment download URLs.** Both
  dashboards built download links as `?token=<8-hour session JWT>`. A URL is not
  a private channel — it lands in browser history, the server's access log,
  every proxy log on the path, and the `Referer` of whatever the page loads
  next. Downloads now use a token scoped to a single attachment that expires in
  60 seconds, and `get_current_admin` no longer accepts `?token=` at all.
  Authorisation is re-checked against the live database at download time, so a
  token minted while a technician was assigned stops working once the ticket is
  reassigned.
- **Download tokens cannot authenticate the API.** Session tokens now carry
  `typ="session"` and any other token type is refused as a credential. Without
  this, a download token — signed with the same key — would have granted a
  minute of full API access. Tokens issued before this change carry no type
  claim and remain valid, so nobody is logged out by the upgrade.
- **Self-update is disabled by default and pinned to a verified source.**
  `POST /update/apply` ran `git pull --rebase` and restarted the server into
  whatever it fetched, reachable by any super_admin on any deployment. It now
  requires `SELF_UPDATE_ENABLED=true`, requires the checkout's `origin` to point
  at the configured `GITHUB_REPO` **on github.com** (host and path both pinned,
  so a redirected remote is refused), pulls fast-forward only, and refuses to
  run over a dirty working tree.
- **Fixed DOM XSS in the dashboards.** The Updates tab injected GitHub release
  tags and git output into `innerHTML` unescaped; the client download link ran
  through HTML escaping but accepted a `javascript:` URL. Added a URL scheme
  allowlist, and `esc()` now escapes single quotes as well.
- **Client identity moved to the OS credential store.** The `client_id` is a
  bearer secret for reading a machine's ticket statuses and posting into its
  chat session, and it lived in a plaintext file in the roaming profile. It now
  lives in Windows Credential Manager / macOS Keychain, with automatic migration
  from the old file and a documented fallback where no backend is available.
- **Rate-limited `GET /notifications/{client_id}`**, the one public endpoint
  that had no limit.
- **Wildcard CORS now announces itself** at startup with the exact setting to
  change. The default is unchanged, because tightening it would break
  dashboards opened from another host.

### Added

- **Real-time live chat.** A `/ws/chat/{session_id}` endpoint existed but
  nothing used it — both dashboards and the desktop client discovered messages
  by polling every 2.5–3 seconds. All three now receive messages the moment they
  are stored, over a new end-user channel (`/ws/chat/client/{session_id}`,
  scoped by the same session-id + client-id pair as the REST endpoints) and the
  existing staff channel. Typing indicators in both directions. Sending stays on
  REST so writes keep a single authorisation path. Polling remains as a
  fallback at 15s, so a refused WebSocket upgrade degrades rather than breaks.
- **`docs/TROUBLESHOOTING.md`** — symptom → cause → fix, covering server
  startup, dashboards, client auto-start, connection and TLS errors, login
  lockouts, notifications, attachments, SmartScreen/Gatekeeper, antivirus
  quarantine of PyInstaller builds, updates, and log locations.
- **Supported-platform tables** in the README for the client (Windows 10 1809+,
  Windows 11, macOS 11+ on Intel and Apple Silicon), the dashboards (current
  Edge, Chrome, Firefox, Safari 16.4+), and the server.
- **Client uninstallers** (`uninstall.bat`, `uninstall.sh`, and
  `HelpdeskClient --uninstall`) that remove the logon entry, so deleting the app
  no longer leaves something trying to start a binary that is gone.
- **CI: dependency auditing and a git-history secret scan.** `pip-audit` over
  both requirement files (non-blocking — the one current finding has no released
  fix), and a scan of every commit on every ref rather than just the tip. ruff
  now lints the whole repo; bandit now covers `client_app/` and
  `server_daemon.py`.
- **81 new tests** (30 → 111) covering download-token scoping and expiry,
  self-update guards, auto-start registration, the single-instance lock, the
  credential store and its migration, and real-time chat delivery and scoping.

### Fixed

- **Auto-start could not be turned off.** Registration lived in two places that
  disagreed. "Disable auto-start" was silently undone by the self-healing
  re-registration on the next launch; Windows wrote the executable path unquoted
  from one path and quoted from the other, so a client installed under
  `C:\Program Files\...` either failed to start or churned the registry every
  launch; and macOS wrote `KeepAlive=false` from one path and `true` from the
  other, so crash recovery depended on which code ran last. Replaced with a
  single implementation: a per-user logon Scheduled Task on Windows (with
  `RestartOnFailure`, falling back to the `Run` key), a `LaunchAgent` with
  `RunAtLoad` and `KeepAlive` on macOS, a persisted opt-out, and exactly one
  mechanism active at a time so upgrades cannot leave duplicates.
- **A crashed client could refuse to start again.** The single-instance guard
  used shared memory, which on macOS and Linux outlives the process that created
  it — after a crash every later launch exited immediately and only a reboot
  cleared it. Replaced with an OS file lock, released automatically on process
  death.
- **The dashboards called `http://localhost:8000` regardless of where they were
  served from.** Anyone opening the dashboard from a machine other than the
  server loaded a page from the server that then called their own localhost. The
  panels now use the origin that served them; the hardcoded value is a fallback
  for `file://` opens only. Every request in a normal deployment is therefore
  same-origin.
- **Login could break outright in Safari private windows** and locked-down
  enterprise profiles, which reject `sessionStorage` writes. Losing persistence
  across a refresh is now the worst case.
- **`datetime.utcnow()`** in the update router — deprecated since Python 3.12.
- **`server_daemon.py` could not run on macOS or Linux**: it passed the
  Windows-only `CREATE_NO_WINDOW` creation flag unconditionally. It also ignored
  `HOST`/`PORT`.
- **Two spurious 404s per dashboard load** (`/favicon.ico` and `/branding/logo`
  when no custom logo is set), which read like faults in every admin's console.
- **`ruff check backend/ scripts/` failed on `master`**, so the CI lint job was
  red before any of this work.

### Changed

- Live chat and notification polling intervals relaxed now that WebSockets carry
  the traffic (chat thread 3s → 15s as a fallback only).
- `GITHUB_REPO` moved from a constant edited in `backend/routers/update.py` to
  an environment variable.
- `SECURITY.md` now documents deployment requirements and three known, accepted
  findings with reasoning: the pre-v1.1 placeholder key in git history (not a
  live credential — `config.py` rejects it), unauthenticated ticket creation,
  and the unfixable `ecdsa` advisory reached through `python-jose`.

### Upgrade notes

- **"Apply Update" now returns 403** until `SELF_UPDATE_ENABLED=true` and
  `GITHUB_REPO` are set in `.env`. This is deliberate: the feature should not be
  live on hosts that never intended to use it. Updating by hand on the server
  needs no configuration.
- **The desktop client gains a `keyring` dependency.** Rebuild the client from
  the updated spec files; `pip install -r client_app/requirements.txt` first.
- No database migration is required. No action is needed for existing sessions,
  client identities, or tickets — all migrate in place.

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
