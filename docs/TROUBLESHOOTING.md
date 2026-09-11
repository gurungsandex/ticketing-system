# Troubleshooting

Symptom → cause → fix, for the problems that actually come up in this
deployment. Each entry names the file or setting involved so you can confirm
the diagnosis rather than guessing.

Jump to: [Log locations](#log-locations) · [Server startup](#server-startup) ·
[Connection & TLS](#connection--tls-errors) · [Login lockouts](#login-lockouts)
· [Client auto-start](#client-auto-start) · [Notifications](#notifications) ·
[Attachments](#attachments) · [SmartScreen & Gatekeeper](#smartscreen--gatekeeper-warnings)
· [Antivirus](#antivirus-quarantining-pyinstaller-builds)

---

## Log locations

Check these before anything else — most entries below are confirmed or ruled
out by one line in a log.

| What | Where |
|------|-------|
| Server (all platforms) | `logs/server.log` in the project root |
| Server PID | `logs/server.pid` (written by `setup.sh`) |
| Windows background daemon | `logs/server.log`, written by `server_daemon.py` |
| Client settings | Windows `%APPDATA%\HelpdeskClient\settings.json` · macOS `~/Library/Application Support/HelpdeskClient/settings.json` |
| Client offline queue | same directory, `offline_queue.json` |
| Client identity (legacy installs) | same directory, `client_id.txt` — after upgrade this moves into Credential Manager / Keychain and the file is removed |
| Windows auto-start entry | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value `ITTicketingClient` |
| macOS auto-start entry | `~/Library/LaunchAgents/com.ticketing.helpdesk.client.plist` |

The desktop client does not write a log file. To see its output, run the
executable from a terminal — a frozen build is built with `console=False`, so
for diagnosis run from source: `python client_app/main.py`.

> **Privacy note.** Ticket descriptions and chat messages are user-submitted
> free text and may contain sensitive or personal data. They are stored in the
> database but are deliberately **not** written to `server.log`. Do not paste
> raw ticket bodies into a bug report, and do not add logging that echoes
> them. Access tokens are likewise never logged — see the JWT entry under
> [Connection & TLS](#connection--tls-errors).

---

## Server startup

### The server exits immediately and `logs/server.log` ends with `Address already in use`

**Cause.** Something is already bound to port 8000 — usually a previous
instance that was never stopped.

**Fix.** `./setup.sh` already tries to clear the port. If it did not:

```bash
lsof -ti :8000 | xargs kill -9      # macOS / Linux
netstat -ano | findstr :8000        # Windows — note the PID, then:
taskkill /PID <pid> /F
```

Then start again. To run on a different port instead, set `PORT` in `.env`.

---

### `ModuleNotFoundError` on startup

**Cause.** Dependencies were installed into a different interpreter than the
one running the server — common when several Pythons are installed.

**Fix.** Install with the *same* interpreter you start with:

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

---

### Everyone is logged out after a server restart

**Cause.** No `SECRET_KEY` is set, so the server generated one and persisted it
to `backend/secret.key`. If that file is not writable (read-only filesystem, a
container without a volume), a **new** key is generated on every start and all
previously issued tokens become invalid.

**Fix.** Set an explicit key in `.env` and restart:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# paste into .env as SECRET_KEY=...
```

This is also required for multi-node deployments — every node must share one
key or tokens issued by one will be rejected by another.

---

### `/admin` returns "Admin panel not found"

**Cause.** The server is running from a directory where `admin_panel/index.html`
is not at the expected path relative to `backend/`.

**Fix.** Start the server from inside `backend/` within a complete checkout.
The 404 page prints the exact path it looked for — compare it to where the file
actually is.

---

### Tickets disappear after some days

**Cause.** `TICKET_RETENTION_DAYS` is set above 0. A scheduled job at 02:00
deletes tickets, notes, attachments, and notifications older than that window.

**Fix.** Set `TICKET_RETENTION_DAYS=0` in `.env` (the default) to keep
everything. Deleted rows are not recoverable except from a backup.

---

## Connection & TLS errors

### Client shows "● Disconnected" / dashboard shows "Cannot reach server"

**Cause**, in the order worth checking:

1. Server not running → check `logs/server.log`.
2. Wrong address configured on the client (⚙ Settings) or in the dashboard
   (`const API` near the top of the `<script>` block in `admin_panel/index.html`).
3. Host firewall blocking inbound 8000.
4. Client and server on different subnets/VLANs with no route.

**Fix.** Confirm reachability from the client machine first:

```bash
curl http://<server-ip>:8000/health      # expect {"status":"ok",...}
```

If that works and the app still fails, the address configured in the app is
wrong. The client resolves its server URL in this order — the first match wins:
`HELPDESK_SERVER_URL` environment variable → `settings.json` → the build-time
default in `client_app/config.py`. An environment variable set by your
deployment tooling will silently override whatever the user typed into ⚙
Settings.

---

### `SSLError` / `CERTIFICATE_VERIFY_FAILED` from the client after moving to HTTPS

**Cause.** The client uses `requests`, which verifies certificates against the
system trust store. A self-signed or internal-CA certificate is not in it.

**Fix.** Install the issuing CA certificate into the machine trust store
(Windows: Local Machine → Trusted Root Certification Authorities; macOS:
System keychain, marked Always Trust). Do **not** disable verification — it
turns a TLS deployment back into an unauthenticated one.

---

### Dashboard loads but every API call fails with a CORS error

**Cause.** `CORS_ORIGINS` is set to something that does not include the origin
the dashboard is actually served from.

**Fix.** Either serve the dashboard from the same origin as the API (visit
`http://<server>:8000/admin` rather than opening `index.html` from disk), or
add the dashboard's origin to `CORS_ORIGINS` in `.env`. Note that a page opened
via `file://` has a null origin and cannot be allow-listed — serve it over HTTP.

---

### WebSocket never connects; notifications only arrive on page refresh

**Cause.** The dashboard opens `ws://…/ws/notifications?token=…`. A reverse
proxy that does not forward the `Upgrade` and `Connection` headers will drop
the handshake. The dashboard falls back to polling, so the app still works —
it just stops being live.

**Fix.** Enable WebSocket proxying. For nginx:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade    $http_upgrade;
proxy_set_header Connection "upgrade";
```

> The token is in the query string **only** for WebSocket handshakes, because
> the browser WebSocket API cannot set headers. Every other route rejects a
> token in the URL. If you add proxy access logging, exclude `/ws/` query
> strings so tokens are not written to disk.

---

## Login lockouts

### "Too many requests. Please slow down and try again shortly." (HTTP 429)

**Cause.** The login rate limiter. Default is `RATE_LIMIT_LOGIN=10` attempts
per `RATE_LIMIT_WINDOW_SECONDS=60`, counted per client IP.

**Fix.** Wait for the window to pass (the `Retry-After` header gives the
seconds). The limiter is in-memory, so restarting the server also clears it.

**If a whole office is locked out at once**, the cause is almost certainly
this: the server is behind a reverse proxy and `TRUSTED_PROXY_IPS` is not set,
so every request appears to come from the proxy's IP and all staff share a
single bucket. Set `TRUSTED_PROXY_IPS` to the proxy's address in `.env` and
restart.

Conversely, do **not** set it when there is no proxy — `X-Forwarded-For` is
caller-supplied, and trusting it lets an attacker forge a new source IP per
request and bypass brute-force protection entirely.

---

### Forgotten admin password

**Cause.** No self-service reset exists by design.

**Fix.** Another `super_admin` cannot reset a password either — they can only
delete and recreate the account (Users page). If *no* admin can log in, reset
directly against the database:

```bash
cd backend
python3 -c "
from database import SessionLocal
import models
from auth import hash_password
db = SessionLocal()
u = db.query(models.AdminUser).filter(models.AdminUser.username=='admin').first()
u.hashed_password = hash_password('a-new-strong-password')
db.commit()
print('reset')
"
```

Do this on the server console only, and change the password again from the UI
afterwards so it is not left in your shell history.

---

### Session expires while still working

**Cause.** Two independent timers: the JWT lifetime
(`ACCESS_TOKEN_EXPIRE_HOURS`, default 8) and a dashboard idle timeout of 60
minutes that clears `sessionStorage`.

**Fix.** Expected behaviour. Raise `ACCESS_TOKEN_EXPIRE_HOURS` if the token
lifetime is the constraint — but the idle timeout is client-side and
deliberate. Closing the browser tab always ends the session, because the token
is held in `sessionStorage`, not `localStorage`.

---

## Client auto-start

### The client does not start at login after install

**Cause**, most common first:

1. The app was never launched once after install. Registration happens on
   first run, not at install time.
2. The install path contains spaces and an **older build** wrote an unquoted
   registry value (`C:\Program Files\...` parsed as `C:\Program`). Fixed in
   current builds, which quote the command and self-heal on next launch.
3. A group policy or security product strips `HKCU` Run entries.
4. macOS: the user disabled the item under System Settings → General → Login
   Items.

**Fix.** Launch the client once manually — it re-registers itself on every
launch, so a missing or stale entry heals automatically. Then verify:

```powershell
# Windows — expect a QUOTED path
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ITTicketingClient
```

```bash
# macOS
cat ~/Library/LaunchAgents/com.ticketing.helpdesk.client.plist
```

If the entry is present and correct but the client still does not appear at
login, check whether it *is* running without a visible window — see the tray
entry below.

---

### Two copies of the client start, or two tray icons appear

**Cause.** Historically, a second auto-start entry from an older install. The
current build cannot produce this: Windows uses a single fixed registry value
name and macOS a single fixed plist path, so re-registering overwrites rather
than accumulates.

**Fix.** Remove any stale entry under a *different* name from previous builds,
then relaunch. A single-instance guard (`QSharedMemory`) also prevents two
copies running concurrently in the same session — the second exits immediately
with "Client already running."

---

### The client does not come back after a crash

**Cause.** Platform difference, and it is a real limitation:

- **macOS** — the LaunchAgent sets `KeepAlive: {SuccessfulExit: false}`, so
  launchd restarts it after an abnormal exit but *not* after the user chooses
  Quit in the tray. That is intentional; plain `KeepAlive: true` would make
  Quit appear broken.
- **Windows** — an `HKCU` Run entry runs once at login and provides **no**
  crash restart. The client will return at next login, not immediately.

**Fix.** If immediate crash-restart is required on Windows, deploy a scheduled
task with restart-on-failure instead of the Run key. That requires
administrator rights and is a deployment decision — it is not what the app
registers for itself.

---

### Uninstall left the client starting at login

**Cause.** The auto-start entry is per-user and lives outside the application
directory, so deleting the executable does not remove it.

**Fix.** Use "Disable auto-start" in the tray menu before uninstalling, or
remove the entry directly:

```powershell
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ITTicketingClient /f
```

```bash
rm ~/Library/LaunchAgents/com.ticketing.helpdesk.client.plist
```

Note this must be done **per user profile** that ran the client.

---

## Notifications

### Staff see no notifications until they refresh

**Cause.** The WebSocket is not connected — see
[WebSocket never connects](#websocket-never-connects-notifications-only-arrive-on-page-refresh).
The dashboard degrades to polling, so nothing is lost, but delivery is no
longer immediate.

---

### An end user gets no "resolved" popup

**Cause.** The client polls `/notifications/{client_id}` every 30 seconds and
only raises a popup on a *change* it observed. It cannot report a change that
happened while it was not running — the first poll after launch establishes a
baseline.

**Fix.** Expected for status changes that happen while the client is closed.
If popups never appear at all, check that the OS allows notifications for the
app (Windows: Settings → System → Notifications; macOS: System Settings →
Notifications).

**Known limitation:** where no system tray is available (some Linux desktops,
locked-down kiosks, certain remote sessions) the client detects this and skips
creating a tray icon — but status popups are then dropped silently rather than
shown some other way. The ticket list in the window is still accurate; only the
proactive popup is lost.

---

### A busy agent stops getting chat pings

**Cause.** Deliberate. Presence-aware routing: an `available` agent is pinged
on every message, a `busy` agent only every 5th unread message, and an
`away`/`offline` agent not at all. Unclaimed sessions page available
technicians first and fall back to admins only when no technician is available.

**Fix.** Change your status in the dashboard. If nobody is receiving pings,
check that at least one account has `chat_status = available`.

---

## Attachments

### "File type not allowed. Use PNG, JPG, GIF, WEBP, BMP, or PDF."

**Cause.** The declared MIME type is outside the allow-list.

**Fix.** Convert the file. Office documents and archives are not accepted by
design — paste relevant content into the ticket description instead.

---

### "File content does not match an allowed image/PDF type."

**Cause.** The file's declared type and its actual bytes disagree. The server
validates magic bytes because the client-supplied content type is untrusted.
Usually a renamed file (`report.docx` → `report.pdf`) or a truncated/corrupt
upload.

**Fix.** Upload the file in its real format.

---

### "File too large. Max 10 MB."

**Cause.** `MAX_UPLOAD_BYTES`, default 10485760.

**Fix.** Compress or crop the screenshot, or raise `MAX_UPLOAD_BYTES` in
`.env`. Attachments are stored as blobs in SQLite, so raising this materially
grows the database file — check disk before increasing it much.

---

### Download does nothing / downloads a file named "attachment"

**Cause.** The dashboard fetches the attachment with an `Authorization` header
and hands the browser a blob URL. A browser extension that blocks
programmatic downloads, or a session that expired between page load and click,
will break it.

**Fix.** Reload the page and sign in again. If it persists, check the browser
console — an expired session surfaces as "Download failed (401)".

---

## SmartScreen & Gatekeeper warnings

### Windows: "Windows protected your PC — unrecognised app"

**Cause.** The executable is unsigned, or signed with a certificate that has
not yet built SmartScreen reputation. This is expected for an unsigned
PyInstaller build.

**Fix, in order of preference:**

1. Sign the executable with an OV or EV code-signing certificate. EV gets
   immediate SmartScreen reputation; OV accrues it over time and downloads.
2. Distribute through your management tooling (Intune/SCCM), which installs
   without the interactive SmartScreen prompt.
3. Interactively, a user can click **More info → Run anyway** — acceptable for
   a pilot, not for a fleet rollout.

---

### macOS: "cannot be opened because the developer cannot be verified"

**Cause.** The `.app` is not signed with a Developer ID certificate and not
notarised.

**Fix.**

1. Sign with Developer ID Application, then notarise and staple the ticket.
   This is the only fix that scales.
2. Interactively: System Settings → Privacy & Security → **Open Anyway**, or
   `xattr -dr com.apple.quarantine /Applications/HelpdeskClient.app`.

Note that an unsigned app on Apple Silicon must still carry at least an ad-hoc
signature to execute at all; PyInstaller applies one automatically, which is
why it runs after the Gatekeeper prompt is dismissed but is still flagged.

---

## Antivirus quarantining PyInstaller builds

### The built `.exe` is deleted or quarantined immediately after building

**Cause.** PyInstaller's one-file bootloader unpacks to a temp directory at
runtime, which heuristically resembles packed malware. This is a
false positive and affects most PyInstaller output, not this app specifically.

**Fix, in order of preference:**

1. **Code-sign the executable.** The single most effective change — most
   engines weight a valid signature heavily.
2. Submit the binary to your AV vendor as a false positive.
3. Add an exclusion for the build output directory and the install path.
4. Build with `--onedir` instead of one-file. A directory build does not
   self-extract at runtime and trips far fewer heuristics. Note that
   `helpdesk.spec` currently uses `onefile=True`; the macOS spec already
   produces a directory bundle.
5. Consider disabling UPX compression (`upx=True` in `helpdesk.spec`) — packed
   binaries attract additional heuristics.

Rebuild from a clean tree after any change — a quarantined intermediate in
`build/` will otherwise be reused.

---

## Still stuck?

Collect, in this order:

1. The last 50 lines of `logs/server.log`.
2. `curl -i http://<server>:8000/health` from the affected machine.
3. The exact error text from the client or the browser console.
4. Server OS and version, client OS and version, and whether a reverse proxy
   is in front of the server.

Redact ticket content and tokens before sharing.
