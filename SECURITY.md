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

## Known Security Posture

See [docs/SECURITY_ANALYSIS.md](docs/SECURITY_ANALYSIS.md) for a full analysis of the current security design, known limitations, and recommended hardening steps.

---

## Deployment Requirements

These are not optional for anything beyond a trusted, isolated LAN.

| Requirement | Why |
|---|---|
| Terminate TLS at a reverse proxy | The server speaks plain HTTP. Without TLS, credentials and ticket contents — which can include personal data — cross the network in the clear. |
| Set `SECRET_KEY` explicitly | Otherwise each server process generates its own, so tokens issued by one are rejected by another. |
| Change the default `admin` / `admin123` password | It is seeded on first start and printed to the log. |
| Set `CORS_ORIGINS` to your dashboard's origin | The `*` default allows any site a signed-in staff member visits to reach the API from their browser. |
| Restrict network exposure at the firewall | The server binds all interfaces by design so LAN clients can reach it. |
| Keep `backend/secret.key` and `helpdesk.db` off backups that leave your control | They are the signing key and the full ticket history respectively. |

Leave `SELF_UPDATE_ENABLED` off unless you specifically need it. When enabled,
a super_admin session can replace the server's code and restart into it.

---

## Known and Accepted Findings

Documented rather than fixed, with the reasoning. Re-report any of these only
if you can demonstrate impact beyond what is described.

### Historical placeholder key in git history

Releases before v1.1 shipped a hardcoded default signing key,
`HELPDESK_SECRET_KEY_CHANGE_IN_PRODUCTION`, which remains visible in this
repository's commit history and cannot be removed without rewriting published
history and breaking every existing clone.

It is **not a live credential**. `backend/config.py` explicitly rejects that
value, so no deployment can sign tokens with it even if it is set in the
environment. CI allowlists this one string in its history scan and reports its
occurrence count separately so the allowlist cannot silently become dead code.

**If you ever ran a pre-v1.1 release in production**, tokens issued then were
forgeable by anyone who read the source. Those tokens expired within 8 hours,
but rotate `SECRET_KEY` and require a fresh sign-in to be certain.

### Unauthenticated ticket creation and client polling

The desktop client has no user account, so `POST /tickets/`,
`POST /tickets/{id}/attachments`, `GET /notifications/{client_id}` and the
`/chat/*` end-user endpoints are unauthenticated. Each is rate limited per IP,
uploads are validated by magic bytes rather than the declared type, and the
chat and notification endpoints are scoped by a locally generated `client_id`
that acts as a bearer secret.

The residual risk is that anyone who can reach the server can create tickets.
Closing it requires per-device enrollment tokens, which every deployed client
would need to re-enroll for. That remains an open design decision rather than a
defect.

### `ecdsa` advisory (PYSEC-2026-1325)

`python-jose[cryptography]` pulls in `ecdsa`, which carries a timing-attack
advisory with **no released fix** — upstream considers side-channel resistance
out of scope.

This project signs tokens with HMAC-SHA256 (`HS256`) and never uses ECDSA, so
the vulnerable code path is not reached. CI reports `pip-audit` findings without
failing the build, because a finding with no available fix would otherwise wedge
every build permanently. Migrating from the largely unmaintained `python-jose`
to `PyJWT` would drop the dependency entirely and is the recommended long-term
fix.

---

## Reporting a Security Bug in a Deployment You Run

If you believe a deployment has been compromised:

1. Rotate `SECRET_KEY` — this invalidates every issued token immediately.
2. Reset all staff passwords.
3. Check `logs/server.log` and your reverse proxy's access log for unexpected
   `POST /update/apply`, `POST /admin/users`, and `DELETE` requests.
4. Confirm `git -C <checkout> config --get remote.origin.url` still points where
   you expect, and `git status` is clean.
