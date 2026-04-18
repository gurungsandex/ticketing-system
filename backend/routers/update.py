"""
Auto-update router.

One-time setup:
1. Push your project to a private GitHub repository.
2. Set GITHUB_REPO below to "yourorg/yourrepo".
3. Clone that repo onto the server and run the backend from inside it.
4. "Apply Update" in the admin dashboard runs git pull and restarts.
"""
import os
import sys
import subprocess
import threading
from datetime import datetime

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException

import models
from auth import require_super_admin

router = APIRouter()

# ── Set your GitHub repo here ─────────────────────────
GITHUB_REPO = "YOUR_ORG/YOUR_REPO"
# Example: GITHUB_REPO = "sandeshgrg/mom-helpdesk"

CURRENT_VERSION = "4.0.0"
# ─────────────────────────────────────────────────────

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _is_git_repo() -> bool:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=_PROJECT_ROOT, capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def _get_current_commit() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_PROJECT_ROOT, capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _get_latest_github_release() -> dict:
    if GITHUB_REPO == "YOUR_ORG/YOUR_REPO":
        return {"tag": "not configured", "notes": "Set GITHUB_REPO in backend/routers/update.py"}
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        r = http_requests.get(url, timeout=8,
                               headers={"Accept": "application/vnd.github.v3+json"})
        if r.status_code == 200:
            data = r.json()
            return {
                "tag": data.get("tag_name", "unknown"),
                "notes": data.get("body", "")[:500],
                "published_at": data.get("published_at", ""),
                "url": data.get("html_url", ""),
            }
        return {"tag": "unknown", "notes": f"GitHub API returned {r.status_code}"}
    except Exception as e:
        return {"tag": "unknown", "notes": f"Could not reach GitHub: {e}"}


def _do_git_pull() -> tuple:
    try:
        r = subprocess.run(
            ["git", "pull", "--rebase"],
            cwd=_PROJECT_ROOT, capture_output=True, text=True, timeout=60,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return False, "git not found. Install Git and add it to PATH."
    except subprocess.TimeoutExpired:
        return False, "git pull timed out after 60 seconds."
    except Exception as e:
        return False, str(e)


def _restart_server():
    import time
    time.sleep(1.5)
    os.execv(sys.executable, [sys.executable] + sys.argv)


@router.get("/update/check")
def check_for_updates(_admin: models.AdminUser = Depends(require_super_admin)):
    is_git = _is_git_repo()
    latest = _get_latest_github_release()
    return {
        "current_version": CURRENT_VERSION,
        "current_commit": _get_current_commit() if is_git else "N/A",
        "latest_release": latest,
        "git_available": is_git,
        "repo": GITHUB_REPO,
        "update_available": (
            GITHUB_REPO != "YOUR_ORG/YOUR_REPO"
            and latest.get("tag", "unknown") not in ("unknown", "not configured", CURRENT_VERSION)
        ),
        "checked_at": datetime.utcnow().isoformat(),
    }


@router.post("/update/apply")
def apply_update(_admin: models.AdminUser = Depends(require_super_admin)):
    if not _is_git_repo():
        raise HTTPException(
            status_code=400,
            detail=(
                "Server is not inside a git repository. "
                "Clone the GitHub repo to the server and run from that folder."
            ),
        )
    success, output = _do_git_pull()
    if not success:
        raise HTTPException(status_code=500, detail=f"git pull failed: {output}")

    threading.Thread(target=_restart_server, daemon=True).start()
    return {
        "message": "Update applied. Server restarting in ~2 seconds.",
        "git_output": output,
        "new_commit": _get_current_commit(),
    }
