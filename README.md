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
| **Live Chat** | Secure end-user ↔ staff chat with agent presence and response templates |
| **Knowledge Base** | Mines resolved tickets, generates review-only draft articles/playbooks |
| **Real-Time Notifications** | WebSocket bell for staff; polling for desktop client |
| **Admin Dashboard** | Tickets, filters, users, notes, chat, knowledge base — served at `/admin` |
| **Technician Portal** | Assigned tickets + live chat — served at `/tech` |
| **Desktop Client** | Windows/macOS system tray app (PySide6) — self-healing autostart |
| **File Attachments** | PDF and image uploads, validated by magic bytes, stored in the database |
| **Internal Notes** | Per-ticket staff notes visible only to admin/tech |
| **Retention** | Optional auto-cleanup (off by default; keep full history for auditing) |
| **Background Server** | Silent background process via `setup.sh` / `setup.bat` |

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
│   ├── main.py                ← FastAPI app, auth routes, scheduler
│   ├── models.py              ← SQLAlchemy ORM models
│   ├── schemas.py             ← Pydantic v2 request/response schemas
│   ├── auth.py                ← JWT creation, bcrypt, RBAC dependency
│   ├── database.py            ← SQLite engine & session factory
│   ├── websocket_manager.py   ← WebSocket connection pool
│   ├── requirements.txt
│   └── routers/
│       ├── tickets.py         ← Ticket CRUD
│       ├── admin.py           ← User management (super_admin only)
│       ├── notifications.py   ← Bell API + WebSocket + client polling
│       └── update.py          ← Optional GitHub Releases auto-update
├── admin_panel/
│   └── index.html             ← Admin dashboard (served at /admin)
├── tech_panel/
│   └── index.html             ← Technician portal (served at /tech)
├── client_app/                ← Optional desktop tray app (PySide6)
│   ├── main.py
│   ├── config.py              ← Set SERVER_URL here before building
│   ├── helpdesk.spec          ← PyInstaller spec — Windows .exe
│   ├── helpdesk_mac.spec      ← PyInstaller spec — macOS .app
│   └── ui/
│       └── main_window.py
├── docs/
│   ├── ADMIN_GUIDE.md
│   ├── TECHNICIAN_GUIDE.md
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
| `http://YOUR_IP:8000/admin` | Admin Dashboard |
| `http://YOUR_IP:8000/tech` | Technician Portal |
| `http://YOUR_IP:8000/health` | Health Check |
| `http://YOUR_IP:8000/api/docs` | Interactive API Docs |

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

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | — | JWT signing secret. Generate with `secrets.token_hex(32)` |
| `CORS_ORIGINS` | No | `*` | Comma-separated list of allowed origins |
| `HOST` | No | `0.0.0.0` | Server bind host |
| `PORT` | No | `8000` | Server port |

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

Distribute the built binary to end-user workstations. The app registers itself for autostart on first launch.

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
top bar. When an agent is Available, end users see a **Live Chat with IT** button in the
desktop client. Agents work a queue: claim a conversation, reply, and insert reusable
**response templates** (inserted into the editor for review — never auto-sent).

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
| `super_admin` | All tickets, user management, technician assignment, Updates tab |
| `technician` | Assigned tickets only, add notes, update status — no user management |

---

## Pre-Deployment Checklist

- [ ] Set `SECRET_KEY` in `.env`
- [ ] Update `const API = "..."` in both HTML panels
- [ ] Start server — confirm `/health` returns `{"status":"ok"}`
- [ ] Log in and change the default `admin` password
- [ ] Create technician accounts via Admin → Users
- [ ] Open TCP port 8000 on the server firewall
- [ ] (Optional) Build and distribute the desktop client to end-users
- [ ] (Optional) Set `GITHUB_REPO` in `backend/routers/update.py` for auto-updates
- [ ] (Optional) Configure Nginx/Caddy reverse proxy for HTTPS

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes and run the linter: `ruff check backend/ scripts/ --config pyproject.toml`
4. Open a pull request against `master`

Report bugs or request features via [GitHub Issues](https://github.com/gurungsandex/ticketing-system/issues).

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
