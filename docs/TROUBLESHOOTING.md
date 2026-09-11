# Troubleshooting

Symptom → cause → fix. Each entry starts with what you actually see.

If you are filing a bug, include: the server version (`GET /health`), the OS and
version of the affected machine, and the relevant log excerpt from
[Log locations](#log-locations). **Never paste a token, password, or ticket
description into a public issue** — ticket bodies can contain personal data.

**Contents**

- [Server will not start](#server-will-not-start)
- [Dashboards](#dashboards)
- [Client auto-start](#client-auto-start)
- [Connection and TLS errors](#connection-and-tls-errors)
- [Login lockouts](#login-lockouts)
- [Notifications](#notifications)
- [Live chat](#live-chat)
- [Attachments](#attachments)
- [SmartScreen and Gatekeeper warnings](#smartscreen-and-gatekeeper-warnings)
- [Antivirus quarantining PyInstaller builds](#antivirus-quarantining-pyinstaller-builds)
- [Updates](#updates)
- [Log locations](#log-locations)

---

## Server will not start

### `Address already in use` / `[Errno 98]` / port 8000 busy

**Cause.** A previous server is still running, or another application owns the
port.

**Fix.**

```bash
# macOS / Linux
lsof -ti :8000 | xargs kill -9
./setup.sh

# Windows
netstat -ano | findstr ":8000" | findstr LISTENING
taskkill /PID <pid> /F
setup.bat
```

To move the server instead, set `PORT` in `.env` and update the clients'
`HELPDESK_SERVER_URL`.

---

### `ModuleNotFoundError: No module named 'fastapi'` (or any dependency)

**Cause.** Dependencies were installed into a different interpreter than the one
running the server — most often a virtualenv that is not active, or Python from
the Microsoft Store.

**Fix.**

```bash
cd backend
python -m pip install -r requirements.txt   # same `python` you start the server with
python -c "import fastapi, sys; print(sys.executable)"
```

If the printed path is not the interpreter your start script uses, make them
match. On Windows, prefer the python.org installer over the Store build.

---

### Server starts, then exits immediately with no error

**Cause.** On Windows the daemon is launched with `pythonw.exe`, which has no
console — the traceback went to the log, not to your screen.

**Fix.** Read `logs/server.log`. To see it live, run the server in the
foreground instead:

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

### `[NOTICE] SECRET_KEY not set — using an auto-generated key`

**Cause.** Informational, not an error. With no `SECRET_KEY` in `.env` the
server generates one and persists it to `backend/secret.key`, so tokens survive
restarts.

**Fix.** Nothing is required for a single-server deployment. Set `SECRET_KEY`
explicitly if you run more than one server process or host — otherwise each one
generates its own key and a token issued by one is rejected by the others,
which looks like random logouts.

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

> Deleting `backend/secret.key` invalidates every issued token; everyone is
> logged out and must sign in again. Nothing else is lost.

---

### `[NOTICE] CORS_ORIGINS is '*'`

**Cause.** Informational. The default allows any origin, which suits a LAN
deployment where dashboards may be opened from several hosts.

**Fix.** For a production deployment set `CORS_ORIGINS` to your dashboard's
exact origin in `.env` and restart:

```
CORS_ORIGINS=https://helpdesk.example.com
```

Since v1.2 the dashboards call the origin they were served from, so if everyone
reaches them at `/admin` and `/tech` on the server itself, tightening this
breaks nothing.

---

### `database is locked`

**Cause.** SQLite under concurrent writes. The server already enables WAL and a
30-second busy timeout, so this usually means the database is on a network share
or a synced folder (OneDrive, Dropbox), where file locking is unreliable.

**Fix.** Move `helpdesk.db` to local disk. Set `DATABASE_URL` if you need it in
a specific place:

```
DATABASE_URL=sqlite:////var/lib/helpdesk/helpdesk.db
```

---

## Dashboards

### Dashboard loads but every action fails, or the login screen says it cannot connect

**Cause.** Before v1.2 the panels contained a hardcoded
`const API = "http://localhost:8000"`, so opening the dashboard from any machine
other than the server made the browser call *its own* localhost.

**Fix.** Upgrade to v1.2 or later, where the panel uses the origin it was served
from. Reach the dashboard through the server — `http://SERVER:8000/admin` — not
by opening `index.html` from disk.

If you must open the file directly, set `API_FALLBACK` near the top of the
`<script>` block in `admin_panel/index.html` and `tech_panel/index.html`.

---

### Blank page, or "Not configured" on login

**Cause.** The page was opened as `file:///.../index.html`, so there is no
origin to inherit and `API_FALLBACK` is still the placeholder.

**Fix.** Browse to `http://SERVER:8000/admin` instead. That is the supported
path and it keeps every request same-origin.

---

### Logged out on every page refresh

**Cause.** The session is held in `sessionStorage`. Safari private windows and
some locked-down enterprise profiles reject writes to it.

**Fix.** Use a normal (non-private) window. Since v1.2 a rejected write no
longer breaks login — you simply sign in again after a refresh.

---

### Dashboard works in Chrome but not Safari or Firefox

**Cause.** Usually a stale cached copy of the panel, not a compatibility
problem — the dashboards target current Edge, Chrome, Firefox and Safari.

**Fix.** Hard-reload (Cmd/Ctrl+Shift+R). If it persists, open the developer
console and file the first error message with your browser version.

---

## Client auto-start

The client registers itself at login **on every launch**, so an entry lost to a
profile reset, a path change, or antivirus cleanup repairs itself the next time
the client runs.

### The client does not start after a reboot

**Cause A — the user turned it off.** "Disable auto-start" in the tray menu now
persists, and the startup re-registration deliberately honours it.

*Fix.* Tray icon → **Enable auto-start**.

**Cause B — the entry is missing and the client has not run since.**

*Fix.* Start the client once by hand; it re-registers itself. Then verify:

```powershell
# Windows — one of these two should exist
schtasks /Query /TN "ITTicketingClient"
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ITTicketingClient
```

```bash
# macOS
ls -l ~/Library/LaunchAgents/com.ticketing.helpdesk.client.plist
launchctl print "gui/$(id -u)/com.ticketing.helpdesk.client" | head -20
```

**Cause C — Task Scheduler is disabled by policy.** The client falls back to the
`Run` key automatically. If neither exists, check whether Group Policy blocks
both.

---

### The client was installed under `C:\Program Files\...` and never starts

**Cause.** A pre-v1.2 client wrote the executable path to the registry
**unquoted**, so Windows treated the space in "Program Files" as an argument
separator and launched nothing.

**Fix.** Upgrade to v1.2 or later and start the client once; it rewrites the
entry in the correct quoted form. To confirm, the value should be wrapped in
double quotes:

```powershell
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ITTicketingClient
```

---

### Two copies of the client start at login

**Cause.** An upgrade from a version that used a different registration
mechanism left both a scheduled task and a `Run` key entry.

**Fix.** v1.2 keeps exactly one: registering the task removes the `Run` entry.
Start the client once to converge. To clear a stubborn leftover by hand:

```powershell
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ITTicketingClient /f
```

The single-instance lock means a duplicate launch exits immediately rather than
producing two tray icons, so this is cosmetic.

---

### The client will not start at all — "Client already running" but no tray icon

**Cause.** On pre-v1.2 clients the single-instance guard used shared memory,
which on macOS survives a crash. The orphaned segment made every later launch
exit immediately, and only a reboot cleared it.

**Fix.** Upgrade to v1.2 or later, which uses an OS file lock released
automatically when the process dies. To clear the state by hand:

```bash
# macOS
rm -f ~/Library/Application\ Support/HelpdeskClient/it-ticketing-client.lock
```

```powershell
# Windows
del "%LOCALAPPDATA%\HelpdeskClient\it-ticketing-client.lock"
```

---

### The client does not come back after crashing

**Cause.** On Windows a `Run` key entry only fires at logon; it cannot restart
anything. On macOS a LaunchAgent written with `KeepAlive=false` (some pre-v1.2
paths did this) will not relaunch either.

**Fix.** Upgrade to v1.2 or later. Windows then uses a logon task with
`RestartOnFailure`, and macOS writes `KeepAlive=true`. Verify:

```bash
# macOS — should print KeepAlive = true
plutil -p ~/Library/LaunchAgents/com.ticketing.helpdesk.client.plist
```

---

### Auto-start entries remain after uninstalling

**Cause.** The application was deleted without running the uninstaller, so the
logon entry survives and tries to start a binary that no longer exists.

**Fix.**

```powershell
client_app\scripts\uninstall.bat          REM add /purge to remove saved data too
```

```bash
client_app/scripts/uninstall.sh           # add --purge to remove saved data too
```

Or, if you still have the executable: `HelpdeskClient --uninstall`.

---

## Connection and TLS errors

### Client shows "Disconnected" / tickets queue up offline

**Cause.** The client cannot reach the server. The queue is working as designed
— tickets are held locally and flushed when the server returns.

**Fix.** Work outward:

```bash
curl http://SERVER:8000/health          # expect {"status":"ok",...}
```

1. No response from the server itself → the server is down; see
   [Server will not start](#server-will-not-start).
2. Works on the server but not from the client machine → firewall. Allow
   inbound TCP 8000 on the server.
3. Works by IP but not by name → DNS. Use the IP in `HELPDESK_SERVER_URL`.
4. Reachable but the client still shows disconnected → the client is pointed
   somewhere else. Check the tray **Settings** dialog, then
   `HELPDESK_SERVER_URL`, then the built-in default, in that order.

Queued tickets are retried every 60 seconds; the tray shows the pending count.

---

### `SSL: CERTIFICATE_VERIFY_FAILED` after putting the server behind HTTPS

**Cause.** The certificate is self-signed, or its chain is not trusted by the
client machine.

**Fix.** Install the issuing CA certificate into the OS trust store —
**Local Machine → Trusted Root Certification Authorities** on Windows, System
keychain on macOS. Do **not** disable certificate verification in the client;
that removes the protection TLS exists to provide.

A certificate must be issued for the exact hostname clients use. A certificate
for `helpdesk.example.com` does not validate when clients connect to
`https://192.168.1.50`.

---

### Live chat works but messages only arrive every 15 seconds

**Cause.** The WebSocket upgrade is being refused — usually a reverse proxy that
has not been configured to forward it. Chat then falls back to polling, which is
slower but still correct.

**Fix.** Forward the upgrade headers. nginx:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 3600s;
}
```

Caddy forwards WebSockets automatically.

Behind TLS the socket must be `wss://`, which the client derives from an
`https://` server URL. A client configured with `http://` against an HTTPS
server will fail the upgrade silently and poll forever.

---

### Everyone is rate-limited behind a reverse proxy

**Cause.** Rate limits are per client IP. If the proxy does not send
`X-Forwarded-For`, every request appears to come from the proxy, so one busy
user exhausts the limit for everybody.

**Fix.** Set `X-Forwarded-For` in the proxy (see the nginx block above). Only
do this for a proxy you control — the server trusts the first hop.

---

## Login lockouts

### `429 Too many requests` on the login screen

**Cause.** More than `RATE_LIMIT_LOGIN` attempts (default 10) from one IP inside
`RATE_LIMIT_WINDOW_SECONDS` (default 60). This is brute-force protection, not a
fault.

**Fix.** Wait for the window to pass — 60 seconds by default. There is no
account lockout, so nothing needs to be unlocked; the limit is per IP and
per time window only.

If a whole office shares one NAT address and legitimately trips this, raise the
limit in `.env` rather than disabling it:

```
RATE_LIMIT_LOGIN=30
RATE_LIMIT_WINDOW_SECONDS=60
```

Restarting the server clears all counters immediately — the limiter is
in-memory.

---

### `401 Invalid username or password` with credentials you know are right

**Cause.** Most often a forgotten password. It can also mean the signing key
changed (see below).

**Fix.** Reset it from another super_admin account: **Users → delete and
recreate**. If there is no other admin account, stop the server and recreate one
directly:

```bash
cd backend
python -c "
from database import SessionLocal
import models, auth
db = SessionLocal()
u = db.query(models.AdminUser).filter_by(username='admin').first()
u.hashed_password = auth.hash_password('a-new-strong-password')
db.commit()
print('Password reset.')
"
```

---

### Everyone is logged out at once / tokens rejected after a restart

**Cause.** The JWT signing key changed. Either `backend/secret.key` was deleted
or regenerated, or `SECRET_KEY` in `.env` changed, or you are running multiple
server processes that each generated their own key.

**Fix.** Set `SECRET_KEY` explicitly in `.env` so it is stable and shared, then
restart. Everyone signs in once more and it stops recurring.

---

### Sessions expire sooner than expected

**Cause.** Two independent timeouts: the JWT lifetime
(`ACCESS_TOKEN_EXPIRE_HOURS`, default 8) and the dashboard's own 60-minute idle
timer.

**Fix.** The idle timer is intentional for shared workstations. To extend the
token lifetime, set `ACCESS_TOKEN_EXPIRE_HOURS` in `.env`.

---

## Notifications

### The notification bell never updates

**Cause.** The WebSocket is not connected. The dot beside the bell shows its
state.

**Fix.** See the WebSocket proxy fix under
[Connection and TLS errors](#connection-and-tls-errors). Unread counts are also
polled every 30 seconds, so a broken socket delays notifications rather than
losing them.

---

### A technician gets no notification for a new chat

**Cause.** Working as designed. New chats page technicians whose status is
**Available**; admins are only paged if no technician is available. A **Busy**
agent is pinged every 5th unread message, and **Away**/**Offline** agents are
not pinged at all — the unread badge shows what they missed.

**Fix.** Set your status to **Available** in the dashboard header.

---

### The client tray shows no desktop notifications

**Cause.** Either the OS suppresses them, or no system tray is available.

**Fix.**

- Windows: Settings → System → Notifications → allow the client. Check that
  Focus Assist is off.
- macOS: System Settings → Notifications → allow the client.
- If the tray is unavailable entirely, the client keeps working — the main
  window shows the same status inline.

---

## Live chat

### The chat button is there but no agents respond

**Cause.** No agent has set their status to Available. Chat deliberately stays
reachable so the user can leave a message.

**Fix.** Have staff set **Available**. Waiting sessions appear in the dashboard
chat queue regardless and can be claimed at any time.

---

### "Chat session not found" in the client

**Cause.** The session was deleted by an admin, or the stored client identity
changed so the session is no longer owned by this machine.

**Fix.** Close and reopen the chat window to start a new session. If it recurs,
see the client-identity note under [Log locations](#log-locations).

---

## Attachments

### "File type not allowed"

**Cause.** Only PNG, JPG, GIF, WEBP, BMP and PDF are accepted, and the check
reads the file's actual magic bytes — renaming `report.docx` to `report.png`
does not work, by design.

**Fix.** Convert to an accepted format, or screenshot the document.

---

### "File too large"

**Cause.** The upload exceeds `MAX_UPLOAD_BYTES` (default 10 MB).

**Fix.** Compress the image, or raise the limit in `.env`. Attachments are
stored in the database, so a large limit grows `helpdesk.db` quickly.

---

### Download does nothing, or fails with 401

**Cause.** Since v1.2 a download link carries a token scoped to that one file
which expires after about a minute. A link copied out of the address bar and
reused later will not work — that is the point of the change.

**Fix.** Click **Download** in the dashboard again to mint a fresh token. If it
fails immediately, your session has expired; sign in again.

---

## SmartScreen and Gatekeeper warnings

The published builds are **not code-signed**, so both operating systems warn on
first run. The warning reflects the absence of a signature, not detected malware.

### Windows: "Windows protected your PC" (SmartScreen)

**Fix for a user.** Click **More info → Run anyway**.

**Fix for a deployment.** Do not ask hundreds of users to click through a
security warning. Either:

- Sign the executable with an organisational code-signing certificate
  (EV certificates get SmartScreen reputation immediately; standard OV
  certificates build reputation over time), or
- Distribute through Intune/SCCM/Group Policy, which installs without the
  interactive prompt, or
- Add a WDAC/AppLocker publisher or hash rule for the binary.

To sign a build:

```powershell
signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 HelpdeskClient.exe
```

### macOS: "cannot be opened because the developer cannot be verified" (Gatekeeper)

**Fix for a user.** Right-click the app → **Open** → **Open**. (Double-clicking
gives no such option; the right-click path is required.) On Ventura and later:
System Settings → Privacy & Security → **Open Anyway**.

**Fix for a deployment.** Sign and notarise with an Apple Developer ID, or
deploy via MDM, which bypasses the prompt.

```bash
codesign --deep --force --options runtime \
  --sign "Developer ID Application: Your Org (TEAMID)" HelpdeskClient.app
xcrun notarytool submit HelpdeskClient.zip \
  --apple-id you@example.com --team-id TEAMID --wait
xcrun stapler staple HelpdeskClient.app
```

If a downloaded app is quarantined and you have verified its origin:

```bash
xattr -d com.apple.quarantine /Applications/HelpdeskClient.app
```

---

## Antivirus quarantining PyInstaller builds

### The client executable is deleted or blocked shortly after install

**Cause.** PyInstaller bundles an interpreter and unpacks itself at runtime.
That behaviour resembles a packed dropper, so heuristic engines flag it. This is
a **false positive** and a well-known characteristic of PyInstaller, not a sign
the build is compromised.

The Windows spec also enables UPX compression, which raises the false-positive
rate further.

**Fix, in order of preference.**

1. **Code-sign the executable.** The single most effective measure — most
   engines trust a signed binary from a known publisher.
2. **Add an exclusion** for the install path and the process name in your
   endpoint protection console. Prefer a publisher or hash rule over a path
   rule; a path exclusion weakens protection for everything in that folder.
3. **Build without UPX** if your engine flags packed binaries. In
   `client_app/helpdesk.spec`, set `upx=False` and rebuild. The executable is
   larger and less likely to be flagged.
4. **Submit the file as a false positive** to your vendor. Most turn these
   around in a few days, and it fixes the problem fleet-wide.

Verify what was quarantined before excluding anything:

```powershell
Get-MpThreatDetection | Select-Object -First 5 |
  Format-List Resources, ThreatID, InitialDetectionTime
```

> Do not disable antivirus to work around this. Exclude the specific binary.

---

### The build works on the build machine but is quarantined everywhere else

**Cause.** The build machine has an exclusion, or has already seen the file.

**Fix.** Test on a clean machine with default protection before rolling out. Add
that step to your release checklist.

---

## Updates

### "Apply Update" returns 403 "Self-update is disabled"

**Cause.** Expected since v1.2. Self-update lets a dashboard session replace the
server's code, so it is off unless deliberately enabled.

**Fix.** If you want it, set both in `.env` and restart:

```
SELF_UPDATE_ENABLED=true
GITHUB_REPO=your-org/ticketing-system
```

Updating by hand on the server (`git pull`, restart) remains the safer default
and needs no configuration.

---

### "The checkout's 'origin' remote does not match GITHUB_REPO"

**Cause.** A deliberate guard. The server refuses to pull code from anywhere
other than the repository you configured, on github.com.

**Fix.** Check what the checkout actually points at:

```bash
git -C /path/to/ticketing-system config --get remote.origin.url
```

Make it match `GITHUB_REPO`. If you did not change it yourself, treat the
mismatch as a security incident before "fixing" it.

---

### "The checkout has uncommitted local changes"

**Cause.** Another guard: an update must not discard edits made on the server.

**Fix.** Review and resolve them on the server (`git status`, then commit,
stash, or revert), then retry.

---

## Log locations

| What | Where |
|---|---|
| Server log (both platforms) | `logs/server.log` in the project root |
| Server PID (macOS/Linux) | `logs/server.pid` |
| Database | `backend/helpdesk.db` (plus `-wal` / `-shm`) |
| JWT signing key | `backend/secret.key` — **treat as a secret** |
| Client settings + auto-start opt-out (Windows) | `%APPDATA%\HelpdeskClient\settings.json` |
| Client settings + auto-start opt-out (macOS) | `~/Library/Application Support/HelpdeskClient/settings.json` |
| Client offline queue (Windows) | `%APPDATA%\HelpdeskClient\offline_queue.json` |
| Client offline queue (macOS) | `~/Library/Application Support/HelpdeskClient/offline_queue.json` |
| Client single-instance lock (Windows) | `%LOCALAPPDATA%\HelpdeskClient\it-ticketing-client.lock` |
| Client single-instance lock (macOS) | `~/Library/Application Support/HelpdeskClient/it-ticketing-client.lock` |
| Client identity (`client_id`) | Windows Credential Manager / macOS Keychain, under **IT Ticketing System** |

The client identity moved into the OS credential store in v1.2. On machines
upgraded from an earlier version the old `client_id.txt` is migrated on first
run and then deleted; if you still see that file, the client has not been
started since the upgrade.

### Turning up server logging

Logging defaults to `WARNING` and access logs are suppressed. For diagnosis, run
the server in the foreground with more detail:

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug
```

> Ticket descriptions, chat messages and notes can contain personal data. The
> server deliberately does not log them, and tokens are never written to logs.
> Keep it that way: when sharing logs, review them first, and do not enable
> request-body logging on a production instance.
