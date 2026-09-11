# IT Ticketing System

[![CI](https://github.com/gurungsandex/ticketing-system/actions/workflows/ci.yml/badge.svg)](https://github.com/gurungsandex/ticketing-system/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

A lightweight, self-hosted IT helpdesk ticketing system for small to mid-sized teams. Runs entirely on your internal network — no cloud dependency, no external services, no subscription fees.

Built with **FastAPI** + **SQLite**. Ships with a browser-based admin dashboard, a technician portal, and an optional desktop tray client for end-users.

---

## Screenshots

> _Admin Dashboard — indigo sidebar, full ticket management_

> _Technician Portal — teal sidebar, assigned tickets view_

> _End-User Desktop Client — system tray app for ticket submission_

---

## Features

| Feature | Details |
|---|---|
| **Ticket Management** | Create, assign, prioritise, update, and resolve support tickets |
| **Prioritisation** | Low / Normal / High / Urgent with filtering and priority-aware alerts |
| **Duplicate-proof Numbering** | Atomic per-day counter — safe under simultaneous submissions |
| **Role-Based Access** | `super_admin` and `technician` roles with separate portals |
| **Live Chat** | Real-time WebSocket delivery with typing indicators; technician-first routing with admin escalation, presence-aware notifications, canned responses, always-reachable offline messaging |
| **Knowledge Base** | Mines resolved tickets, generates review-only draft articles/playbooks |
| **Custom Branding** | Upload a PNG/JPEG logo to replace the default icon across both dashboards and the desktop client |
| **Desktop Client Updates** | Push a new client version + download link from the admin panel; the desktop app checks on startup and prompts end-users |
| **Real-Time Notifications** | WebSocket bell for staff; polling for the desktop client |
| **Admin Dashboard** | Tickets, filters, users, notes, chat, knowledge base — served at `/admin` |
| **Technician Portal** | Assigned tickets + live chat — served at `/tech` |
| **Desktop Client** | Windows/macOS system tray app (PySide6) — self-healing auto-start, identity stored in Credential Manager / Keychain |
| **File Attachments** | PDF and image uploads, validated by magic bytes, stored in the database |
| **Internal Notes** | Per-ticket staff notes visible only to admin/tech |
| **Retention** | Optional auto-cleanup (off by default; keep full history for auditing) |
| **Background Server** | Silent background process via `setup.sh` / `setup.bat` |

---

## Supported Platforms

### Desktop client

| Platform | Versions | Architectures | Notes |
|---|---|---|---|
| Windows 11 | All supported releases (23H2, 24H2, 25H2) | x64, ARM64 | ARM64 runs the x64 build under emulation |
| Windows 10 | 1809 and later, including 21H2 and 22H2 (all still-serviced builds) | x64 | Below 1809, PySide6 is unsupported |
| macOS | 11 Big Sur and later (12, 13, 14, 15, 26) | Intel (x86_64), Apple Silicon (arm64) | Build on the architecture you target, or produce a universal2 build |

Auto-start is per-user and needs no administrator rights: a logon Scheduled Task
on Windows (falling back to the `HKCU` `Run` key where Task Scheduler is
restricted by policy), and a `LaunchAgent` with `RunAtLoad` and `KeepAlive` on
macOS. Published builds are **not code-signed** — see
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for SmartScreen, Gatekeeper
and antivirus handling.

### Dashboards

| Browser | Supported |
|---|---|
| Microsoft Edge | Current and previous stable |
| Google Chrome | Current and previous stable |
| Mozilla Firefox | Current stable and current ESR |
| Safari | 16.4 and later (macOS and iPadOS) |

The panels are plain HTML/CSS/JS with no build step and no external CDN
dependency, so they work offline on an isolated network. They are served by the
backend at `/admin` and `/tech` and call whichever origin served them — there is
nothing to configure per deployment.

### Server

| Component | Requirement |
|---|---|
| Python | 3.10, 3.11, or 3.12 (CI covers all three) |
| OS | Windows, macOS, or Linux |
| Database | SQLite (bundled) — keep it on local disk, not a network or synced folder |

---

## Documentation

| Guide | For |
|---|---|
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | End users submitting tickets |
| [docs/TECHNICIAN_GUIDE.md](docs/TECHNICIAN_GUIDE.md) | Technicians working the queue |
| [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | Administrators running the system |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | **Something is broken** — symptom → cause → fix |
| [docs/SECURITY_ANALYSIS.md](docs/SECURITY_ANALYSIS.md) | Security design and limitations |
| [SECURITY.md](SECURITY.md) | Reporting a vulnerability; deployment requirements |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.110+ |
| Server | Uvicorn (ASGI) |
| Database | SQLite via SQLAlchemy 2.0 |
| Auth | JWT (python-jose) + bcrypt |
| Real-time | WebSocket (FastAPI native) |
| Scheduler | APScheduler |
| Admin / Tech UI | HTML5 + Vanilla JS (zero dependencies, self-contained) |
| Desktop Client | PySide6 (Qt6 Python bindings) |

---

## Project Structure

```
ticketing-system/
├── backend/
│   ├── main.py                ← FastAPI app, auth routes, scheduler, middleware
│   ├── config.py              ← Central settings (SECRET_KEY, rate limits, retention)
│   ├── models.py              ← SQLAlchemy ORM models
│   ├── schemas.py             ← Pydantic v2 request/response schemas
│   ├── auth.py                ← JWT creation, bcrypt, RBAC dependency
│   ├── security.py            ← Security headers, rate limiter, magic-byte checks
│   ├── database.py            ← SQLite engine (WAL/busy_timeout) & session factory
│   ├── migrations.py          ← Idempotent startup schema migrations
│   ├── utils.py               ← Shared helpers (timezone-safe UTC)
│   ├── websocket_manager.py   ← WebSocket pools (staff notifications + chat)
│   ├── requirements.txt
│   ├── routers/
│   │   ├── tickets.py         ← Ticket CRUD, atomic numbering, priority, attachments
│   │   ├── admin.py           ← User management (super_admin only)
│   │   ├── notifications.py   ← Bell API + WebSocket + client polling
│   │   ├── chat.py            ← Live chat, agent presence, canned responses, escalation
│   │   ├── knowledge.py       ← KB analytics, draft generation, approval workflow
│   │   ├── settings.py        ← Branding logo upload + desktop client version push
│   │   └── update.py          ← Optional GitHub Releases auto-update (server)
│   ├── services/
│   │   └── kb_analysis.py     ← Ticket-history mining + draft assembly
│   └── static/branding/       ← Uploaded logo lives here (gitignored)
├── admin_panel/
│   └── index.html             ← Admin dashboard (served at /admin)
├── tech_panel/
│   └── index.html             ← Technician portal (served at /tech)
├── client_app/                ← Optional desktop tray app (PySide6)
│   ├── main.py                ← Autostart, single-instance guard, tray fallback
│   ├── config.py              ← Build-time defaults (APP_NAME, poll intervals)
│   ├── settings.py            ← Runtime server-URL resolution (env / settings.json)
│   ├── api_client.py          ← HTTP client + offline queue + chat
│   ├── notifier.py            ← Background polling + connection health
│   ├── helpdesk.spec          ← PyInstaller spec — Windows .exe
│   ├── helpdesk_mac.spec      ← PyInstaller spec — macOS .app
│   └── ui/
│       ├── main_window.py     ← Ticket form + tray + settings
│       └── chat_dialog.py     ← End-user live-chat window (real-time)
├── tests/                     ← pytest suite (numbering, RBAC, security, chat, KB)
├── docs/
│   ├── ADMIN_GUIDE.md
│   ├── TECHNICIAN_GUIDE.md
│   ├── TROUBLESHOOTING.md     ← Symptom → cause → fix
│   ├── USER_GUIDE.md
│   └── SECURITY_ANALYSIS.md
├── scripts/
│   └── init_db.py             ← Seed demo users and tickets
├── .env.example               ← Environment variable template
├── setup.bat                  ← Windows: install deps + start server
├── setup.sh                   ← macOS/Linux: install deps + start server
├── server_daemon.py           ← Windows background daemon
└── pyproject.toml             ← Ruff linter config
```

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- A static LAN IP on the server machine
- TCP port 8000 open on the server firewall

---

### 1 — Clone

```bash
git clone https://github.com/gurungsandex/ticketing-system.git
cd ticketing-system
```

---

### 2 — Configure Environment

```bash
cp .env.example .env
```

Generate a secret key and add it to `.env`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

```env
SECRET_KEY=paste_your_generated_key_here
```

---

### 3 — Set Your Server IP

In **`admin_panel/index.html`** and **`tech_panel/index.html`**, find this line near the bottom of the `<script>` block and update it:

```javascript
const API = "http://YOUR_SERVER_IP:8000";
```

Replace `YOUR_SERVER_IP` with your actual LAN IP (e.g. `192.168.1.50`).

---

### 4 — Start the Server

**macOS / Linux:**
```bash
chmod +x setup.sh && ./setup.sh
```

**Windows:**
```
Double-click setup.bat
```

The setup script installs dependencies, detects your LAN IP, and starts the server in the background.

**Or run manually for development:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 5 — Open the App

| URL | Panel |
|---|---|
| `http://YOUR_IP:8000/admin` | Admin Dashboard — tickets, users, live chat, knowledge base |
| `http://YOUR_IP:8000/tech` | Technician Portal — assigned tickets + live chat |
| `http://YOUR_IP:8000/health` | Health Check |
| `http://YOUR_IP:8000/api/docs` | Interactive API Docs (full endpoint reference) |

Key API groups (see `/api/docs` for the full contract):

| Group | Endpoints |
|---|---|
| Tickets | `POST /tickets/` (public), `GET /tickets/`, `PATCH /tickets/{id}/status`, `/priority`, `/assign` |
| Chat | `GET /chat/availability`, `POST /chat/sessions`, `/messages`, `/claim`, `/agent-messages` |
| Presence | `PATCH /agent/status`, `GET /agent/presence` |
| Templates | `GET/POST/DELETE /canned-responses` |
| Knowledge base | `GET /kb/analysis`, `POST /kb/generate-draft`, `GET/POST/PATCH /kb/articles`, `POST /kb/articles/{id}/review` |

---

## Default Credentials

> **Change both passwords immediately after first login.**

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Technician | `tech` | `tech12345` |

Change password: Admin Dashboard → click your username (top of sidebar) → **Change Password**.

---

## Seed Demo Data (Optional)

Populate the database with sample users and tickets for testing:

```bash
cd backend
python3 ../scripts/init_db.py
```

Creates:
- `admin` / `admin123` (super_admin)
- `tech` / `tech12345` (technician)
- 10 sample tickets across multiple categories and statuses

---

## Running the Tests

```bash
cd backend
pip install -r requirements.txt
pip install pytest httpx
SECRET_KEY=test pytest ../tests/ -v
```

The suite covers race-safe ticket numbering (including a concurrent-creation
stress test), RBAC, security headers, magic-byte upload validation, the live-chat
flow, and the knowledge-base approval workflow. CI runs it on Python 3.10–3.12
alongside `ruff` and a `bandit` security scan.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Recommended | auto-generated | JWT signing secret. If unset, a strong key is generated and persisted to `backend/secret.key` (gitignored). Set explicitly for multi-node. |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins. `*` never sends credentials. |
| `HOST` | No | `0.0.0.0` | Server bind host |
| `PORT` | No | `8000` | Server port |
| `ACCESS_TOKEN_EXPIRE_HOURS` | No | `8` | JWT lifetime |
| `RATE_LIMIT_ENABLED` | No | `true` | Toggle rate limiting on public endpoints + login |
| `RATE_LIMIT_TICKET_CREATE` / `_ATTACHMENT` / `_LOGIN` | No | `20` / `30` / `10` | Requests per window per client IP |
| `RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate-limit window |
| `MAX_UPLOAD_BYTES` | No | `10485760` | Max attachment size (10 MB) |
| `TICKET_RETENTION_DAYS` | No | `0` | Auto-delete tickets older than N days at 02:00. `0` = keep everything (recommended for auditing). |

---

## Building the Desktop Client (Optional)

The client app is a system tray application for end-users to submit tickets without a browser.

**1. Set your server URL in `client_app/config.py`:**
```python
SERVER_URL = "http://192.168.1.50:8000"
APP_NAME   = "Your Company — Tech Support"
```

**2. Install client dependencies:**
```bash
cd client_app
pip install -r requirements.txt
```

**3. Build:**

Windows `.exe`:
```bash
python -m PyInstaller helpdesk.spec
# → dist/HelpdeskClient.exe
```

macOS `.app`:
```bash
python3 -m PyInstaller helpdesk_mac.spec
# → dist/HelpdeskClient.app
```

Distribute the built binary to end-user workstations. The app registers itself
for login auto-start on first launch, and repairs that registration on every
subsequent launch if it goes missing.

**Code signing.** Builds are unsigned by default, so Windows SmartScreen and
macOS Gatekeeper warn on first run and some antivirus engines quarantine
PyInstaller output. For any deployment beyond a handful of machines, sign the
binary — it is the single most effective fix for all three problems. See
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#smartscreen-and-gatekeeper-warnings).

**Uninstalling.** Run the uninstaller rather than just deleting the app,
otherwise the logon entry survives and keeps trying to start a binary that is no
longer there:

```bash
client_app/scripts/uninstall.sh        # macOS;  --purge also removes saved data
client_app\scripts\uninstall.bat       # Windows; /purge also removes saved data
```

Or, with the executable still present: `HelpdeskClient --uninstall`.

---

## Security

- Change default credentials immediately after deployment
- `SECRET_KEY` auto-generates and persists if unset — set it explicitly for multi-node
- Restrict `CORS_ORIGINS` to your server origin in production (wildcard never sends credentials)
- Security headers (CSP, X-Frame-Options, nosniff, Referrer-Policy) on every response
- Rate limiting on public endpoints and login (brute-force / spam protection)
- JWT tokens expire after 8 hours (configurable)
- Passwords hashed with bcrypt (min 8 characters enforced)
- File attachments validated by magic bytes and stored as database blobs — no filesystem exposure
- `POST /tickets/` is intentionally unauthenticated (required for client app submissions) but rate limited
- AI-generated knowledge-base content is never auto-published — it requires admin approval

See [docs/SECURITY_ANALYSIS.md](docs/SECURITY_ANALYSIS.md) for a full security review.

---

## Live Chat & Knowledge Base

**Live chat** — Staff set their availability (Available / Busy / Away / Offline) from the
top bar. The **"Live Chat with IT"** button in the desktop client is always available:
if an agent is online you're connected right away, and if not, the client tells you so and
lets you leave a message anyway — it's saved and answered as soon as someone's back online.
**Technicians are the front line**: new chats page available technicians first, and a
technician can **escalate** a conversation to the admin queue when it needs admin-level
access or a decision. Notifications are presence-aware — a `busy` agent isn't pinged for
every message, just every 5th, and `away`/`offline` agents aren't paged at all until they're
back. Agents work a queue: claim a conversation, reply, and insert reusable **canned
responses** (inserted into the editor for review — never auto-sent). Admins can permanently
delete a session from history when needed.

**Branding** — a super_admin can upload a PNG/JPEG logo (Updates tab → Branding) that
replaces the default icon across both dashboards and the desktop client.

**Desktop client updates** — a super_admin can push a new client version + download link +
release notes from the Updates tab; every desktop client checks on startup and shows an
update prompt with a direct download link (optionally marked mandatory).

**Knowledge base** — The system analyses resolved-ticket history to surface frequent
problems, common resolutions, repeated troubleshooting steps, and the devices/departments/
locations most often involved, then flags clusters that would benefit from an article.
One click generates an **AI-assisted draft**; drafts and playbooks must be reviewed and
**approved by an admin** before they are published. Editing an approved article returns it
to draft for re-review.

---

## User Roles

| Role | Capabilities |
|---|---|
| `super_admin` | All tickets, user management, technician assignment, live chat, canned responses, knowledge-base authoring **and approval**, Updates tab |
| `technician` | Assigned tickets only (notes, status, priority), live chat, canned responses, knowledge-base drafts (approval requires an admin) — no user management |

> Knowledge-base drafts — including AI-assisted ones — are never published automatically. Only a `super_admin` can approve or publish an article.

---

## Pre-Deployment Checklist

- [ ] Set a strong `SECRET_KEY` in `.env` (multi-node deployments must share one)
- [ ] Start server — confirm `/health` returns `{"status":"ok","version":"1.1.0"}`
- [ ] Reach the dashboards at `http://SERVER:8000/admin` and `/tech` (no per-deployment edit needed — they call the origin that served them)
- [ ] Log in and change the default `admin` password immediately
- [ ] Create technician accounts via Admin → Users
- [ ] Restrict `CORS_ORIGINS` to your server origin
- [ ] Open TCP port 8000 on the server firewall (internal subnet only)
- [ ] Decide on `TICKET_RETENTION_DAYS` (0 keeps full history for auditing)
- [ ] Confirm `backend/secret.key` and `backend/helpdesk.db` are backed up and not committed
- [ ] (Optional) Build and distribute the desktop client; set `HELPDESK_SERVER_URL` centrally
- [ ] (Optional) Set `GITHUB_REPO` and `SELF_UPDATE_ENABLED=true` in `.env` to allow dashboard-triggered updates — leave off unless you need it, since it lets a dashboard session replace the server's code
- [ ] (Recommended) Nginx/Caddy reverse proxy for HTTPS — forward WebSocket upgrade headers and `X-Forwarded-For`, and set `HOST=127.0.0.1` behind it
- [ ] (Recommended) Sign the desktop client binary before wide distribution

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes, then run the linter and tests:
   ```bash
   ruff check . --config pyproject.toml
   cd backend && pytest ../tests/ -q
   ```
4. Open a pull request against `master`

Report bugs or request features via [GitHub Issues](https://github.com/gurungsandex/ticketing-system/issues).

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
