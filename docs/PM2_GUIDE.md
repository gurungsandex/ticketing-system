# PM2 Guide — MOM IT Helpdesk v4.0

PM2 runs the helpdesk server as a **background service** — no terminal window needed, survives reboots, and auto-restarts on crash.

---

## Prerequisites

### 1. Python (3.10–3.12)

Verify Python is installed and working:

**Windows:**
```cmd
python --version
python -m pip --version
```

**macOS:**
```bash
python3 --version
python3 -m pip --version
```

Both commands must return version numbers. If `python` is not found, install Python 3.12 from https://python.org — on Windows, check **"Add Python to PATH"** during installation.

### 2. Node.js (18 or later)

**Windows:** Download from https://nodejs.org (LTS version) — during setup, check **"Automatically install the necessary tools"**.

**macOS:**
```bash
brew install node
```
Or download from https://nodejs.org.

Verify:
```bash
node --version
npm --version
```

---

## Installation

### Step 1 — Install Python Dependencies

Run from the project root (`helpdeskv05/`):

**Windows:**
```cmd
cd backend
python -m pip install -r requirements.txt
cd ..
```

**macOS:**
```bash
cd backend
python3 -m pip install -r requirements.txt
cd ..
```

> Always use `python -m pip` — not bare `pip`. The `pip` shortcut is unreliable on Windows.

### Step 2 — Install PM2

**Windows:**
```cmd
npm install -g pm2
npm install -g pm2-windows-startup
```

**macOS:**
```bash
npm install -g pm2
```

### Step 3 — Start with PM2

Run from the project root (`helpdeskv05/`):

```bash
pm2 start ecosystem.config.js
```

You should see a table with `helpdesk` listed as **online**.

### Step 4 — Verify

```
http://localhost:8000/health
```
Expected: `{"status":"ok","version":"4.0.0"}`

### Step 5 — Configure Auto-Start on Boot

**Windows:**
```cmd
pm2-windows-startup install
pm2 save
```

**macOS:**
```bash
pm2 startup
```
Copy and run the `sudo` command it prints, then:
```bash
pm2 save
```

`pm2 save` stores the current process list. PM2 restores it automatically on reboot.

---

## Daily Commands

| Action | Command |
|---|---|
| Start server | `pm2 start ecosystem.config.js` |
| Stop server | `pm2 stop helpdesk` |
| Restart server | `pm2 restart helpdesk` |
| Remove from PM2 | `pm2 delete helpdesk` |
| Check status | `pm2 status` |
| Live log tail | `pm2 logs helpdesk` |
| Last 100 log lines | `pm2 logs helpdesk --lines 100` |
| Clear log files | `pm2 flush helpdesk` |

> **When to restart:** Only needed when Python files in `backend/` change. HTML file changes in `admin_panel/` or `tech_panel/` take effect immediately with a browser hard refresh — no restart needed.

---

## Optional Configuration

### Change Port or Host

Edit `ecosystem.config.js` under `env`:

```javascript
env: {
  HOST: "0.0.0.0",
  PORT: "8080",   // ← change port here
},
```

Then:
```bash
pm2 restart helpdesk
```

Also update `const API` in both HTML panels and `SERVER_URL` in `client_app/config.py`.

### Set Environment Variables

Any environment variable can be added to `ecosystem.config.js`:

```javascript
env: {
  HOST: "0.0.0.0",
  PORT: "8000",
  CORS_ORIGINS: "http://192.168.1.50:8000",
},
```

Restart after any `ecosystem.config.js` change:
```bash
pm2 restart helpdesk
```

### View Log Files Directly

Logs are written to `logs/` in the project root:

| File | Contents |
|---|---|
| `logs/out.log` | Standard output — startup messages, cleanup notices |
| `logs/err.log` | Errors and exceptions |

Logs rotate automatically when they exceed 10 MB.

---

## Uninstalling

### Remove the helpdesk process from PM2

```bash
pm2 delete helpdesk
pm2 save
```

### Remove auto-start on boot

**Windows:**
```cmd
pm2-windows-startup uninstall
```

**macOS:**
```bash
pm2 unstartup launchd
```

### Uninstall PM2 entirely

```bash
npm uninstall -g pm2
```

---

## Troubleshooting

### PM2 shows `errored` status

```bash
pm2 logs helpdesk --lines 50
```

**Most common cause — Python not found:**

Windows: run `where python` to get the full path.
macOS: run `which python3` to get the full path.

If Python is found but PM2 still errors, confirm the `interpreter` setting in `ecosystem.config.js` matches your OS. The file uses `process.platform === "win32"` to automatically choose `python` (Windows) or `python3` (macOS) — verify your Python executable name matches.

**Missing dependencies:**
```
ModuleNotFoundError: No module named 'fastapi'
```
Run:
```cmd
cd backend
python -m pip install -r requirements.txt
cd ..
pm2 restart helpdesk
```

### Port 8000 already in use

**macOS / Linux:**
```bash
lsof -i :8000
kill -9 <PID from above>
```

**Windows:**
```cmd
netstat -ano | findstr :8000
taskkill /PID <PID from above> /F
```

Then:
```bash
pm2 restart helpdesk
```

### PM2 shows `online` but browser cannot reach the server

1. Confirm the server IP is correct — run `ipconfig` (Windows) or `ipconfig getifaddr en0` (macOS)
2. Confirm `const API` in `admin_panel/index.html` and `tech_panel/index.html` matches that IP
3. Open port 8000 on the server firewall — see Part 7 of `ADMIN_GUIDE.md`

### Python or pip changes not reflected

PM2 does not hot-reload. Always restart after any code change:
```bash
pm2 restart helpdesk
```

### pm2-windows-startup install fails on Windows

Run Command Prompt as Administrator, then retry:
```cmd
pm2-windows-startup install
pm2 save
```

### PM2 process list lost after reboot (Windows)

This means `pm2 save` was not run or the startup hook was not installed correctly:
```cmd
pm2-windows-startup install
pm2 start ecosystem.config.js
pm2 save
```
