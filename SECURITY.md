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
