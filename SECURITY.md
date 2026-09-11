# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x (latest) | ✅ Active |

Only the latest release on the `master` branch receives security fixes.

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub Issues.**

Instead, use one of these private channels:

1. **GitHub Security Advisory (preferred):**  
   [Open a private advisory](../../security/advisories/new) — only you and the maintainers can see it until it is resolved and disclosed.

2. **Email:**  
   If you cannot use GitHub, describe the issue in an email to the repository maintainer. Find contact details on the maintainer's GitHub profile.

---

## What to Include

A good vulnerability report includes:

- Description of the vulnerability and its potential impact
- Steps to reproduce (proof of concept if possible)
- Affected version / component (backend, admin panel, client app)
- Any suggested fix or mitigation

---

## Response Timeline

| Stage | Target |
|-------|--------|
| Acknowledgement | Within 72 hours |
| Initial assessment | Within 7 days |
| Fix or mitigation | Depends on severity |
| Public disclosure | After fix is released |

---

## Scope

Items considered in scope:

- Authentication bypass or privilege escalation
- SQL injection or data corruption
- JWT secret exposure or token forgery
- Arbitrary file read/write via the attachment API
- Remote code execution on the server

Items considered out of scope:

- Vulnerabilities that require physical access to the server
- Self-XSS (exploiting yourself)
- Issues in dependencies — report those upstream and open a Dependabot PR here
- Missing security headers that do not result in a practical exploit

---

## OWASP Top 10:2025 — Current Posture

Reviewed across the backend, both dashboards, and the desktop client.

| # | Category | Status | Notes |
|---|---|---|---|
| A01 | Broken Access Control | ✅ Addressed | RBAC enforced server-side, not just in the UI: technicians see only tickets assigned to them, `require_super_admin` gates user management/assignment/KB approval, and chat replies are restricted to the assigned agent or an admin. |
| A02 | Security Misconfiguration | ⚠️ Partly | Security headers (CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`) on every response; CORS never pairs `*` with credentials; self-update off by default. **Open:** ships HTTP-only, and the default `admin`/`admin123` account must be changed at deployment. |
| A03 | Software Supply Chain Failures | ⚠️ Partly | Dependabot enabled; `pip-audit` in CI. **Open:** `ecdsa` PYSEC-2026-1325 (transitive via `python-jose`) has no published fix — not reachable here as tokens are HS256, clears only by moving to `PyJWT`. Client binaries are unsigned. |
| A04 | Cryptographic Failures | ⚠️ Partly | bcrypt password hashing; `SECRET_KEY` never ships as a static default (auto-generated and persisted, historical placeholder explicitly rejected); staff tokens no longer travel in URLs; client secret in the OS credential store. **Open:** no TLS by default, so credentials and tokens cross the network in the clear. |
| A05 | Injection | ✅ Addressed | All database access via SQLAlchemy ORM with bound parameters — no string-built SQL. Dashboard output is escaped through `esc()` before interpolation. Uploaded logo filenames are fixed server-side, never derived from client input. |
| A06 | Insecure Design | ⚠️ By design | `POST /tickets/` and the end-user chat endpoints are deliberately unauthenticated — the desktop client holds no credentials. Mitigated by per-IP rate limiting and by scoping chat reads to a `client_id` that acts as a bearer secret. Anyone who can reach the port can file a ticket; that is the accepted trade-off for frictionless submission. |
| A07 | Authentication Failures | ✅ Addressed | Per-IP login rate limiting that can no longer be bypassed via a forged `X-Forwarded-For`; bcrypt; 8-hour token expiry plus a 60-minute dashboard idle timeout; tokens in `sessionStorage`, so closing the tab ends the session. |
| A08 | Software or Data Integrity Failures | ✅ Addressed | Self-update disabled by default; when enabled it is `fetch` + `merge --ff-only`, so it cannot land a half-applied rebase on production. Attachments are validated by magic bytes, not the client-declared MIME type. AI-generated KB content is always a draft and requires admin approval. |
| A09 | Logging & Alerting Failures | ⚠️ Partly | Ticket bodies, chat messages, and tokens are deliberately kept out of `server.log`. **Open:** there is no audit trail of privileged actions (user creation/deletion, assignment, KB approval) and no alerting on repeated auth failures. |
| A10 | Mishandling of Exceptional Conditions | ✅ Addressed | Handlers raise `HTTPException` with safe messages rather than leaking tracebacks; ticket-number allocation retries on contention and fails closed with 503 rather than issuing a duplicate; credential-store migration fails closed, keeping the existing file if the store does not persist. |

### Automated scanning

Run before every release:

```bash
bandit -r backend/ client_app/ scripts/ server_daemon.py -ll
pip-audit -r backend/requirements.txt
```

Current results: **bandit** 0 High, 1 Medium (`server_daemon.py` binding
`0.0.0.0`, intentional for a LAN server). **pip-audit** 1 finding (`ecdsa`, as
above). A secret scan across full git history shows no committed credentials —
no `.env`, `.db`, `.key` or `.pem` has ever been tracked. A placeholder string
(`HELPDESK_SECRET_KEY_CHANGE_IN_PRODUCTION`) appears in pre-`a759fa5` history;
it is a public placeholder, never a live secret, and current code explicitly
refuses it.

### Known gaps

These are accepted or pending a deployment decision, not oversights:

- **No TLS by default.** Deploy behind a TLS-terminating reverse proxy for
  anything beyond a trusted LAN, and set `TRUSTED_PROXY_IPS` when you do.
- **Unsigned client binaries.** Triggers SmartScreen and Gatekeeper warnings;
  fixing this requires code-signing certificates.
- **Unauthenticated ticket submission.** Load-bearing for the desktop client;
  changing it requires a client enrolment mechanism.
- **No privileged-action audit log.**

---

## Known Security Posture

See [docs/SECURITY_ANALYSIS.md](docs/SECURITY_ANALYSIS.md) for a full analysis of the current security design, known limitations, and recommended hardening steps.
