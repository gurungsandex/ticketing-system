# IT Ticketing System

A self-hosted, on-premise IT helpdesk ticketing system for corporate environments. Built with FastAPI and SQLite, featuring a web-based admin dashboard, technician portal, and a desktop tray client for end-users.

No cloud dependency. No external services. Runs entirely on your internal network.

---

## Features

- **Ticket Management** — Create, assign, update, and close support tickets
- **Role-Based Access Control** — `super_admin` and `technician` roles with distinct permissions
- **Real-Time Notifications** — WebSocket bell notifications for staff; polling notifications for end-users
- **Admin Dashboard** — Full ticket and user management via browser (`/admin`)
- **Technician Portal** — Focused view of assigned tickets (`/tech`)
- **Desktop Client App** — Windows/macOS system tray app for end-users to submit tickets
- **File Attachments** — Upload PDFs and images directly to tickets (stored in database)
- **Notes System** — Internal staff notes per ticket
- **Auto Cleanup** — Tickets older than 30 days are automatically removed at 2:00 AM
- **Background Server** — Runs silently via `setup.bat` (Windows) or `setup.sh` (macOS/Linux)
- **Auto-Update Support** — Optional GitHub release integration for one-click updates

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend API** | FastAPI 0.110+ |
| **Server** | Uvicorn (ASGI) |
| **Database** | SQLite (via SQLAlchemy) |
| **Authentication** | JWT (python-jose) + bcrypt |
| **Real-time** | WebSocket (FastAPI built-in) |
| **Scheduled Jobs** | APScheduler |
| **Admin/Tech Panels** | HTML5 + Vanilla JS (self-contained) |
| **Desktop Client** | PySide6 (Qt6 Python bindings) |

---

## Project Structure

```
ticketing-system/
├── backend/
│   ├── main.py               ← FastAPI app entry point
│   ├── models.py             ← SQLAlchemy database models
│   ├── schemas.py            ← Pydantic request/response schemas
│   ├── auth.py               ← JWT authentication & RBAC
│   ├── database.py           ← SQLite engine & session
│   ├── websocket_manager.py  ← WebSocket connection pool
│   ├── requirements.txt
│   └── routers/
│       ├── tickets.py        ← Ticket CRUD + RBAC
│       ├── admin.py          ← User management
│       ├── notifications.py  ← Bell API + WebSocket + client polling
│       └── update.py         ← Optional GitHub auto-update
├── admin_panel/
│   └── index.html            ← Admin dashboard (self-contained, served at /admin)
├── tech_panel/
│   └── index.html            ← Technician dashboard (self-contained, served at /tech)
├── client_app/               ← Windows/macOS desktop tray app (PySide6)
│   ├── main.py
│   ├── config.py             ← SERVER_URL and app name — set before building
│   ├── helpdesk.spec         ← PyInstaller spec for Windows .exe
│   ├── helpdesk_mac.spec     ← PyInstaller spec for macOS .app
│   └── ui/
│       └── main_window.py
├── docs/
│   ├── ADMIN_GUIDE.md
│   ├── TECHNICIAN_GUIDE.md
│   ├── USER_GUIDE.md
│   └── SECURITY_ANALYSIS.md
├── scripts/
│   └── init_db.py            ← Optional: seed demo data
├── .env.example              ← Environment variable template
├── setup.bat                 ← Windows: install deps + start server in background
├── setup.sh                  ← macOS/Linux: install deps + start server in background
├── server_daemon.py          ← Windows background daemon (launched by setup.bat)
└── LICENSE
```

---

## Quick Start

### Prerequisites

- **Python 3.10–3.12** (Python 3.12 LTS recommended)
- A static LAN IP address on the server machine
- TCP port 8000 open on the server firewall

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/YOUR_ORG/ticketing-system.git
cd ticketing-system
```

---

### Step 2 — Configure Environment Variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

At minimum, generate and set a strong `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output into `.env`:

```
SECRET_KEY=your_generated_key_here
```

See [Environment Setup](#environment-setup) below for all available variables.

---

### Step 3 — Set Your Server IP

Set the server's LAN IP address in **three places** before starting:

**`admin_panel/index.html`** — find near the bottom of the `<script>` block:
```javascript
const API = "http://YOUR_SERVER_IP:8000";
```

**`tech_panel/index.html`** — same location:
```javascript
const API = "http://YOUR_SERVER_IP:8000";
```

**`client_app/config.py`** — before building the client app:
```python
SERVER_URL = "http://YOUR_SERVER_IP:8000"
```

Replace `YOUR_SERVER_IP` with your actual LAN IP (e.g. `192.168.1.50`).

---

### Step 4 — Start the Server

**Windows** (runs in background, safe to close the window):
```
Double-click setup.bat
```
Or from Command Prompt:
```cmd
setup.bat
```

**macOS / Linux** (runs in background):
```bash
chmod +x setup.sh
./setup.sh
```

The setup script will:
1. Verify Python is installed
2. Install all Python dependencies
3. Detect your server's LAN IP
4. Start the server as a background process
5. Print access URLs and default credentials

---

### Step 5 — Access the Application

| Panel | URL |
|---|---|
| Admin Dashboard | `http://YOUR_SERVER_IP:8000/admin` |
| Technician Portal | `http://YOUR_SERVER_IP:8000/tech` |
| Health Check | `http://YOUR_SERVER_IP:8000/health` |
| API Docs (dev) | `http://YOUR_SERVER_IP:8000/api/docs` |

---

## Default Credentials

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `admin123` |
| Role | `super_admin` |

> **Change the default password immediately after first login.**  
> Go to the Admin Dashboard → click your username → Change Password.

---

## Environment Setup

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | **Yes** | JWT signing secret. Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `CORS_ORIGINS` | No | Restrict CORS to specific origins (default: `*`). Example: `http://192.168.1.50:8000` |
| `HOST` | No | Server bind host (default: `0.0.0.0`) |
| `PORT` | No | Server port (default: `8000`) |

---

## Running the App

### Development Mode

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Production (Background)

**Windows:**
```cmd
setup.bat          # Start server
stop_server.bat    # Stop server (generated by setup.bat)
```

**macOS/Linux:**
```bash
./setup.sh         # Start server
./stop_server.sh   # Stop server (generated by setup.sh)
```

Logs are written to `logs/server.log`.

---

## Building the Desktop Client App

The client app is a PySide6 desktop tray application for end-users to submit tickets.

**Before building**, set your server URL in `client_app/config.py`:
```python
SERVER_URL = "http://192.168.1.50:8000"
APP_NAME   = "Your Company — Tech Support"
```

**Install client dependencies:**
```bash
cd client_app
pip install -r requirements.txt
```

**Build for Windows (.exe):**
```bash
python -m PyInstaller helpdesk.spec
# Output: client_app/dist/HelpdeskClient.exe
```

**Build for macOS (.app):**
```bash
python3 -m PyInstaller helpdesk_mac.spec
# Output: client_app/dist/HelpdeskClient.app
```

Distribute the built binary to end-user workstations. On first launch, the app registers itself for autostart.

---

## Deployment Guide

### Firewall

Open TCP port 8000 for your workstation subnet:

**Windows Server:**
```cmd
netsh advfirewall firewall add rule name="IT Ticketing" dir=in action=allow protocol=TCP localport=8000
```

**Linux (ufw):**
```bash
sudo ufw allow 8000/tcp
```

### Reverse Proxy (Optional — HTTPS)

To enable HTTPS, place Nginx or Caddy in front of uvicorn:

**Nginx example:**
```nginx
server {
    listen 443 ssl;
    server_name helpdesk.yourdomain.com;

    ssl_certificate     /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Database Backup

The database is a single file at `backend/helpdesk.db`. Back it up by copying this file:

```bash
cp backend/helpdesk.db backups/helpdesk_$(date +%Y%m%d).db
```

### Optional: Seed Demo Data

Run the seed script to create sample users and tickets for testing:

```bash
python scripts/init_db.py
```

This creates:
- Admin user: `admin` / `admin123`
- Technician user: `tech1` / `tech1pass`
- 5 sample tickets

---

## Auto-Update (Optional)

The system includes a built-in update mechanism via GitHub Releases.

1. Set your repository in `backend/routers/update.py`:
   ```python
   GITHUB_REPO = "YOUR_ORG/ticketing-system"
   ```
2. In the Admin Dashboard, navigate to the **Updates** tab (super_admin only)
3. Click **Check for Updates** — the system compares against the latest GitHub release
4. Click **Apply Update** to run `git pull --rebase` and restart the server

---

## Security Notes

- **Change default credentials** immediately after deployment
- **Set a strong `SECRET_KEY`** — never use the default
- **Restrict CORS** in production via `CORS_ORIGINS` env var
- Attachments are stored as binary blobs in the database (no filesystem exposure)
- JWT tokens expire after 8 hours
- Passwords are hashed with bcrypt
- Minimum password length is 8 characters
- The `/admin` and `/tech` routes require authentication
- Ticket creation (`POST /tickets/`) is intentionally public to allow client app submissions without auth

For a full security analysis, see [docs/SECURITY_ANALYSIS.md](docs/SECURITY_ANALYSIS.md).

---

## User Roles

| Role | Permissions |
|---|---|
| `super_admin` | Full access: manage users, assign tickets, view all tickets, access Updates tab |
| `technician` | View and work assigned tickets, add notes, change status — cannot manage users |

---

## Pre-Deployment Checklist

- [ ] Set `SECRET_KEY` in `.env`
- [ ] Set server IP in `admin_panel/index.html`, `tech_panel/index.html`, and `client_app/config.py`
- [ ] Start server and confirm health check responds: `http://YOUR_IP:8000/health`
- [ ] Log in and **change the default `admin` password**
- [ ] Create technician accounts via Admin Dashboard → Users
- [ ] Open TCP port 8000 on the server firewall
- [ ] Build and distribute the desktop client app to end-user workstations
- [ ] (Optional) Set `GITHUB_REPO` in `backend/routers/update.py` for auto-updates
- [ ] (Optional) Configure a reverse proxy for HTTPS

---

## License

MIT License — see [LICENSE](LICENSE) for full text.
