# MOM IT Helpdesk v4.0

IT ticketing system for Medical Offices of Manhattan.  
On-premise, HIPAA-conscious, no cloud dependency.

---

## Components

| Component | Path | Purpose |
|---|---|---|
| Backend API | `backend/` | FastAPI server, SQLite database |
| Admin panel | `admin_panel/` | Super-admin web dashboard (`/admin`) |
| Tech panel | `tech_panel/` | Technician web dashboard (`/tech`) |
| Client app | `client_app/` | Windows/macOS tray app for end-users |

---

## Quick Start

**Step 1 — Set your server IP** in these three files:

```
admin_panel/index.html    →  const API = "http://YOUR_IP:8000";
tech_panel/index.html     →  const API = "http://YOUR_IP:8000";
client_app/config.py      →  SERVER_URL = "http://YOUR_IP:8000"
```

**Step 2 — Start the server:**

| OS | Method | Command |
|---|---|---|
| Windows | Simple (background) | Double-click `setup.bat` |
| macOS | Simple (background) | `chmod +x setup.sh && ./setup.sh` |
| Both | PM2 (background) | See `docs/PM2_GUIDE.md` |

**Step 3 — Open in browser:**

```
http://YOUR_IP:8000/admin    ← admin login (admin / admin123)
http://YOUR_IP:8000/tech     ← technician login
```

**Change the default password immediately after first login.**

---

## Project Structure

```
helpdeskv05/
├── backend/
│   ├── main.py               ← FastAPI app entry point
│   ├── models.py             ← Database models
│   ├── schemas.py            ← Pydantic request/response schemas
│   ├── auth.py               ← JWT authentication & RBAC
│   ├── database.py           ← SQLite engine & session
│   ├── websocket_manager.py  ← WebSocket connection pool
│   ├── start_server.py       ← PM2 entry point (cross-platform)
│   ├── requirements.txt
│   └── routers/
│       ├── tickets.py        ← Ticket CRUD + RBAC
│       ├── admin.py          ← User management
│       ├── notifications.py  ← Bell API + WebSocket + client polling
│       └── update.py         ← GitHub pull + restart
├── admin_panel/
│   └── index.html            ← Admin dashboard (self-contained)
├── tech_panel/
│   └── index.html            ← Technician dashboard (self-contained)
├── client_app/               ← Windows/macOS tray app (PySide6)
├── logs/                     ← PM2 log output
├── docs/
│   ├── ADMIN_GUIDE.md
│   ├── TECHNICIAN_GUIDE.md
│   ├── USER_GUIDE.md
│   ├── PM2_GUIDE.md
│   └── SECURITY_ANALYSIS.md
├── ecosystem.config.js       ← PM2 config (Windows + macOS)
├── setup.bat                 ← Windows simple start
└── setup.sh                  ← macOS/Linux simple start
```

---

## Pre-Production Checklist

- [ ] Set server IP in all three config locations (Step 1 above)
- [ ] Change default admin password (`admin` / `admin123`)
- [ ] **Set a strong `SECRET_KEY`** — copy `.env.example` to `.env` and fill it in (see `docs/ADMIN_GUIDE.md` Part 8 for step-by-step instructions)
- [ ] Open TCP port 8000 in server firewall for your workstation subnet
- [ ] Build Windows client: `python -m PyInstaller helpdesk.spec` from `client_app/` → `dist/HelpdeskClient.exe`
- [ ] Build macOS client: `python3 -m PyInstaller helpdesk_mac.spec` from `client_app/` → `dist/HelpdeskClient.app`
- [ ] (Optional) Set `GITHUB_REPO` in `backend/routers/update.py` for auto-update
- [ ] To stop the server: run `stop_server.bat` (Windows) or `./stop_server.sh` (macOS)
