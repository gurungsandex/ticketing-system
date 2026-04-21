# Contributing to IT Ticketing System

Thank you for your interest in contributing! This document covers how to report bugs, suggest features, submit code, and keep the project healthy.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Submitting a Pull Request](#submitting-a-pull-request)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Commit Message Format](#commit-message-format)
- [Testing](#testing)
- [Documentation](#documentation)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior by opening a private security advisory or contacting the maintainers.

---

## How Can I Contribute?

### Reporting Bugs

Before submitting a bug report:
1. Search [existing issues](../../issues) to avoid duplicates
2. Check if the issue is already fixed in the latest commit

When filing a bug, use the **Bug Report** issue template and include:
- Steps to reproduce
- Expected vs. actual behavior
- OS, Python version, browser (if relevant)
- Relevant log output from `logs/server.log`

### Suggesting Features

Use the **Feature Request** issue template. Describe:
- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

Features that serve the broadest range of organizations are prioritized.

### Submitting a Pull Request

1. **Fork** the repository
2. **Create a branch** from `master`:
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/your-bug-description
   ```
3. **Make your changes** following the [coding standards](#coding-standards) below
4. **Test your changes** — see [Testing](#testing)
5. **Commit** using the [commit format](#commit-message-format) below
6. **Push** to your fork and open a Pull Request against `master`
7. Fill in the PR template completely

PRs should be focused and minimal — one feature or fix per PR. Large refactors should be discussed in an issue first.

---

## Development Setup

**Requirements:** Python 3.10–3.12, Git

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/ticketing-system.git
cd ticketing-system

# 2. Set up the backend
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cd ..
cp .env.example .env
# Edit .env — generate a SECRET_KEY:
python3 -c "import secrets; print(secrets.token_hex(32))"

# 4. Run the server in development mode (auto-reload)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 5. (Optional) Seed demo data
cd ..
python scripts/init_db.py
```

Open `http://localhost:8000/admin` to access the admin panel.

**For the client app:**
```bash
cd client_app
pip install -r requirements.txt
python main.py
```

---

## Project Structure

```
ticketing-system/
├── backend/           FastAPI application (Python)
│   └── routers/       Route handlers (tickets, admin, notifications, update)
├── admin_panel/       Admin web dashboard (HTML + vanilla JS)
├── tech_panel/        Technician web dashboard (HTML + vanilla JS)
├── client_app/        Desktop tray app (PySide6)
│   └── ui/
├── docs/              User and administrator guides
├── scripts/           Utility scripts (seed, migrations)
└── .github/           GitHub Actions, issue templates, PR template
```

---

## Coding Standards

### Python (backend + client)

- Follow [PEP 8](https://pep8.org/) style
- Use type hints on all function signatures
- Keep functions short and single-purpose
- Validate all external input with Pydantic schemas
- No secrets, IPs, or credentials in code — use `.env` / `config.py`
- Max line length: **100 characters**

### HTML / JavaScript (admin_panel, tech_panel)

- Vanilla JS only — no external framework dependencies
- Keep all styles inline within the single HTML file (self-contained design)
- Use `const` / `let`, never `var`
- Prefer `async/await` over `.then()` chains

### General

- No commented-out code in PRs
- No `print()` debug statements left in submitted code (use `logging`)
- Keep dependencies minimal — avoid adding new packages without discussion

---

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer]
```

**Types:**

| Type | When to use |
|---|---|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that isn't a feature or fix |
| `test` | Adding or updating tests |
| `chore` | Build process, dependency updates, tooling |
| `security` | Security fix or hardening |

**Examples:**
```
feat(tickets): add ticket search by hostname
fix(auth): prevent token reuse after password change
docs(readme): add reverse proxy HTTPS example
security(upload): validate MIME type server-side
```

---

## Testing

The project does not yet have a formal test suite — adding one is a welcome contribution.

Before submitting a PR, manually verify:

**Backend changes:**
- [ ] Server starts without errors: `uvicorn main:app --reload`
- [ ] Health check responds: `GET /health` → `{"status":"ok"}`
- [ ] Login works for both roles (`admin`, technician)
- [ ] Changed functionality works end-to-end in the browser

**Client app changes:**
- [ ] App launches without errors: `python client_app/main.py`
- [ ] Ticket submission sends correctly and appears in admin panel

**HTML panel changes:**
- [ ] Test in Chrome and Firefox
- [ ] Verify both super_admin and technician login flows

If you are adding a new feature, consider including a simple test or a description of how you tested it in your PR.

---

## Documentation

- If your change affects how the app is installed, configured, or used — update the relevant file in `docs/`
- If it adds a new environment variable — update `.env.example` with a comment
- If it changes the API — the FastAPI `/api/docs` page auto-updates, but add a note in the PR

---

## Questions?

Open a [Discussion](../../discussions) for questions that aren't bugs or feature requests. We're happy to help new contributors get started.
