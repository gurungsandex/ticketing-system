# Admin Guide — MOM IT Helpdesk v4.0

---

## System Requirements

**Server (Windows or macOS):**
- Python 3.10–3.12 recommended *(see Python version note below)*
- Node.js 18 or later — only required for PM2
- 1 GB RAM minimum
- Static LAN IP address (e.g. `192.168.1.50`)
- TCP port 8000 open on the server firewall

**End-user workstations:**
- Windows 10/11 or macOS 11+
- Network access to the server IP on port 8000

> **Python version note:** Python 3.14 is a pre-release. Its `pip` launcher is known to be broken on Windows with the error `Fatal error in launcher: Unable to create process`. Use **Python 3.12 LTS** for the server. Download from https://python.org/downloads/release/python-3128

---

## Part 1 — Installation

### Step 1 — Find Your Server IP

**Windows:** Open Command Prompt → run `ipconfig` → look for `IPv4 Address` under your active network adapter (e.g. `192.168.1.50`).

**macOS:** Open Terminal → run `ipconfig getifaddr en0`. If blank, try `en1`.

### Step 2 — Set the Server IP in Three Places

**`admin_panel/index.html`** — open in any text editor, find this line near the bottom inside the `<script>` block:
```javascript
const API = "http://YOUR_SERVER_IP:8000";
```
Replace `YOUR_SERVER_IP` with your actual IP (e.g. `192.168.1.50`).

**`tech_panel/index.html`** — same change, same location.

**`client_app/config.py`:**
```python
SERVER_URL = "http://192.168.1.50:8000"
```

### Step 3 — Install Python Dependencies

Open **Command Prompt** (Windows) or **Terminal** (macOS). Navigate to the `backend` folder:

```cmd
cd C:\path\to\helpdeskv05\backend
```

Install dependencies:

**Windows:**
```cmd
python -m pip install -r requirements.txt
```

**macOS:**
```bash
python3 -m pip install -r requirements.txt
```

> **Always use `python -m pip`** — never bare `pip`. On Windows, the `pip` shortcut frequently breaks after Python upgrades. `python -m pip` always works.

### Step 4 — Start the Server

Choose one method:

**Method A — setup script (simplest, runs in background):**

Windows — double-click `setup.bat` from the project root folder.  
The server launches in the background automatically. You can close the terminal window once it prints the access URLs.

macOS:
```bash
chmod +x setup.sh    # one time only
./setup.sh
```

The script auto-detects your IP, installs dependencies, starts the server in the background, and auto-writes `stop_server.sh`. Close the terminal after it finishes.

**To stop the server:**
- Windows: run `stop_server.bat`
- macOS: run `./stop_server.sh`

**Method B — PM2 (background service, survives reboots, recommended for production):**

See `docs/PM2_GUIDE.md`.

### Step 5 — Verify

Open a browser and go to:
```
http://192.168.1.50:8000/health
```
Expected response: `{"status":"ok","version":"4.0.0"}`

Then open the dashboards:
- Admin: `http://192.168.1.50:8000/admin`
- Tech:  `http://192.168.1.50:8000/tech`

### Step 6 — First Login and Password Change

Default credentials: **`admin` / `admin123`**

Change the password immediately:
1. Log in to the admin panel
2. Click **👤 Account** in the top navigation bar (top-right, between your role badge and Logout)
3. Enter current password (`admin123`), new password (min 8 characters), and confirm
4. Click **Change Password**

---

## Part 2 — User Management

Go to **Users** in the top navigation bar (visible to admins only).

### Create a Technician Account

1. Enter a username and password (minimum 8 characters)
2. Set Role to **Technician**
3. Click **Create**

Technician login URL: `http://SERVER_IP:8000/tech`

### Create an Additional Admin

Same steps — set Role to **Admin**.

### Delete a User

Click **Delete** next to any user in the table.
- You cannot delete your own account
- You cannot delete the last remaining admin
- Deleting a user does **not** delete their ticket history — only their login is removed

### Reset a Forgotten Password

There is no self-service reset. To reset a technician's password:
1. Delete their account
2. Re-create it with the same username and a new password

---

## Part 3 — Managing Tickets

### Ticket Statuses

| Status | Meaning |
|---|---|
| Active | Submitted but not yet picked up |
| In Progress | Technician is actively working on it |
| Resolved | Issue closed |

### Assigning a Ticket

1. Click any ticket row to open it
2. Right panel → **Assign Technician** → select from dropdown → **Assign**
3. The assigned technician receives an instant notification (real-time push or 30-second polling fallback)

Only admins can assign or reassign tickets.

### Updating Status

Admins can change status on any ticket. Technicians can only update status on tickets assigned to them. This is enforced server-side — not just in the UI.

### Internal Notes

Notes are visible only to IT staff (admins and technicians). End-users never see them. Use notes to log troubleshooting steps, escalation details, or resolution summaries.

### Downloading Attachments

Click **⬇ Download** next to any attachment. The file saves to your Downloads folder automatically.

If clicking does nothing or you see an authentication error:
1. Hard refresh the browser: `Ctrl+Shift+R` (Windows) / `Cmd+Shift+R` (macOS)
2. Try again — old cached JavaScript may have been the cause

---

## Part 4 — Restarting the Server

**You do not need to restart for HTML file changes.** Just hard-refresh the browser.

**You must restart when any Python file changes:**

| What changed | Restart needed? |
|---|---|
| `admin_panel/index.html` | ❌ — hard refresh browser only |
| `tech_panel/index.html` | ❌ — hard refresh browser only |
| Any file in `backend/` | ✅ |
| `requirements.txt` (after installing new packages) | ✅ |
| `ecosystem.config.js` | ✅ (via `pm2 restart helpdesk`) |

**How to restart:**

Via setup script — run `stop_server.bat` (Windows) or `./stop_server.sh` (macOS), then re-run the setup script.

Via PM2:
```bash
pm2 restart helpdesk
```

---

## Part 5 — Building and Distributing the Client Desktop App

The client desktop app is the tray/menu-bar application used by end-users to submit tickets. It must be compiled from source before distribution.

### When to Rebuild

| Changed file | Rebuild needed? |
|---|---|
| `client_app/config.py` (server IP changed) | **Yes** |
| `client_app/ui/main_window.py` | **Yes** |
| `client_app/api_client.py` | **Yes** |
| `client_app/main.py` | **Yes** |
| `admin_panel/index.html` | No |
| `tech_panel/index.html` | No |
| Any `backend/` file | No |

### Build — Windows (.exe)

Requires a Windows machine with Python 3.10–3.12.

Open Command Prompt:
```cmd
cd client_app
python -m pip install -r requirements.txt
python -m PyInstaller helpdesk.spec
```

Output: `client_app\dist\HelpdeskClient.exe`

Build time: approximately 2–3 minutes.

### Build — macOS (.app)

Requires a Mac with Python 3.10+.

Open Terminal:
```bash
cd client_app
python3 -m pip install -r requirements.txt
python3 -m PyInstaller helpdesk_mac.spec
```

Output: `client_app/dist/HelpdeskClient.app`

Build time: approximately 2–3 minutes.

### Distribution

**Windows:** Copy `HelpdeskClient.exe` to each workstation — no Python or other software required.

**macOS:** Copy `HelpdeskClient.app` to each Mac's `/Applications` folder.

On first launch the app:
- Appears in the system tray (Windows: bottom-right near the clock) or menu bar (macOS: top-right)
- Auto-registers to start on login (Windows: registry; macOS: LaunchAgent)
- Works offline — queues tickets locally if the server is unreachable and retries every 60 seconds

---

## Part 6 — Database Management

The database is a single file: `backend/helpdesk.db`

### Manual Backup

**Windows:**
```cmd
copy backend\helpdesk.db backup_helpdesk_%date:~-4,4%%date:~-7,2%%date:~0,2%.db
```

**macOS:**
```bash
cp backend/helpdesk.db backup_helpdesk_$(date +%Y%m%d).db
```

### Automatic Cleanup

Tickets, notes, attachments, and notifications older than 30 days are deleted automatically at 2 AM daily. To extend or disable this, edit `backend/main.py`:

```python
# Change 30 to any number of days, or comment out the scheduler job entirely
cutoff = datetime.utcnow() - timedelta(days=30)
```

Restart the server after editing.

---

## Part 7 — Firewall Configuration

Port 8000 must be reachable from workstations on the LAN.

**Windows (run Command Prompt as Administrator):**
```cmd
netsh advfirewall firewall add rule name="MOM Helpdesk" dir=in action=allow protocol=TCP localport=8000
```

**macOS:** macOS does not block local network inbound connections by default. If you have a strict firewall profile, allow TCP 8000 via System Settings → Network → Firewall → Options.

---

## Part 8 — Optional Configuration

### Change the Server Port

Default port is `8000`. To change it:

**`setup.bat` (Windows)** — edit the `mom_server_daemon.pyw` file that setup.bat writes, or change the port inside the `setup.bat` itself in the section that writes the daemon:
```bat
echo             "--host", "0.0.0.0", "--port", "8080"],
```

**`setup.sh` (macOS)** — edit the uvicorn launch line near the bottom:
```bash
nohup $PYTHON -m uvicorn main:app --host 0.0.0.0 --port 8080 ...
```

**PM2** — edit `ecosystem.config.js`:
```javascript
env: {
  HOST: "0.0.0.0",
  PORT: "8080",
},
```

After changing the port, also update:
- `const API` in `admin_panel/index.html`
- `const API` in `tech_panel/index.html`
- `SERVER_URL` in `client_app/config.py` (then rebuild)

### Set a Strong JWT Secret Key

The default secret key in `backend/auth.py` must be replaced before going live. The key is read from the `SECRET_KEY` environment variable if set.

Generate a secure random key:

**Windows:**
```cmd
python -c "import secrets; print(secrets.token_hex(32))"
```

**macOS:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Set it as an environment variable before starting the server:

**Windows (setup.bat):** Add before launching, or set it in your system environment variables.

**macOS (setup.sh):**
```bash
export SECRET_KEY="your-generated-key-here"
./setup.sh
```

**PM2 (recommended):** Add to `ecosystem.config.js` under `env`:
```javascript
env: {
  HOST: "0.0.0.0",
  PORT: "8000",
  SECRET_KEY: "your-generated-key-here",
},
```

### Restrict CORS to Your Server IP

By default CORS allows all origins (`*`). To lock it to your server only:

**Via PM2** — add to `ecosystem.config.js` under `env`:
```javascript
env: {
  HOST: "0.0.0.0",
  PORT: "8000",
  CORS_ORIGINS: "http://192.168.1.50:8000",
},
```
Then: `pm2 restart helpdesk`

**Via setup script** — set the variable before running:

Windows:
```cmd
set CORS_ORIGINS=http://192.168.1.50:8000
setup.bat
```
macOS:
```bash
export CORS_ORIGINS="http://192.168.1.50:8000"
./setup.sh
```

### Configure GitHub Auto-Update

This allows the admin panel to pull updates directly from a private GitHub repository.

1. Push the project to a private GitHub repository
2. Open `backend/routers/update.py` and set:
   ```python
   GITHUB_REPO = "yourorg/mom-helpdesk"
   ```
3. On the server, clone the repo and run the backend from inside that cloned folder
4. Admin panel → **Updates** → **Check for Updates** → **Apply Update**

The server pulls the latest code and restarts automatically. End-users never interact with GitHub.

### Change Data Retention Period

Edit `backend/main.py`, find `_cleanup_old_records()`:
```python
cutoff = datetime.utcnow() - timedelta(days=30)  # change 30 to desired days
```
Restart the server after saving.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Fatal error in launcher` when running pip | Python 3.14 broken pip shortcut on Windows | Use `python -m pip install -r requirements.txt` instead |
| `pip` not recognised | Python not added to PATH | Reinstall Python 3.12 — check **"Add Python to PATH"** during setup, then reopen Command Prompt |
| `{"detail":"Authentication required"}` on download | Old HTML cached in browser | Hard refresh: `Ctrl+Shift+R` (Windows) / `Cmd+Shift+R` (macOS), then try downloading again |
| Download button does nothing | Old HTML file still in place | Confirm latest `index.html` is in `admin_panel/` and `tech_panel/`, then hard refresh |
| Can't reach server from other machines | Firewall blocking port 8000 | Run the firewall command in Part 7 |
| "Admin panel not found" in browser | setup.bat/setup.sh run from wrong folder | Run from the project root (`helpdeskv05/`), not from inside `backend/` |
| Login fails with correct password | Database not initialised or file corrupted | Delete `backend/helpdesk.db` and restart — a fresh DB is auto-created |
| Tickets don't appear after login | Wrong IP in `const API` | Confirm `const API = "http://192.168.1.50:8000"` — do not use `localhost` from another machine |
| Notification bell shows grey dot | Browser blocked WebSocket | No action needed — notifications fall back to 30-second polling automatically |
| PM2 shows `errored` | Python not found | Run `where python` (Windows) / `which python3` (macOS) — see `PM2_GUIDE.md` for full fix |
| Python changes not taking effect | Server not restarted | Restart after any `.py` file change — see Part 4 |
| HTML changes not visible | Browser cache | Hard refresh only — no server restart needed for HTML files |
| Client app won't connect to server | Wrong `SERVER_URL` in `config.py` | Update `SERVER_URL`, rebuild, redistribute |
| End-user sees no tray icon (Windows) | App not running | Ask the user to open `HelpdeskClient.exe` — it registers auto-start on first launch |
| End-user sees no menu-bar icon (macOS) | App not running | Ask the user to open `HelpdeskClient.app` from Applications |
| Server stops when terminal is closed (macOS) | Using old setup.sh | Re-run `./setup.sh` — updated version runs in background automatically |
| `stop_server.bat` / `stop_server.sh` not found | setup script not run yet | Run `setup.bat` or `./setup.sh` first — the stop script is generated automatically |
