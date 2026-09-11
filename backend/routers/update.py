"""
Self-update router.

Security posture
----------------
"Apply Update" makes the server fetch code from a git remote and restart into
it. That is remote code execution by design, and it inherits the trust of
whatever that remote serves. Three things follow, and all are enforced here
rather than left to documentation:

  * It is disabled unless an operator sets SELF_UPDATE_ENABLED=true. Previously
    any super_admin session on any deployment could trigger it, which turned a
    stolen dashboard password into control of the host.
  * The checkout's `origin` remote must match the configured GITHUB_REPO.
    Without that check, anyone able to edit .git/config — or a repo cloned from
    somewhere unexpected — silently redirects the update to their own code.
  * The pull is fast-forward only and refuses to run over local modifications,
    so an update can never silently discard or merge on top of local state.

One-time setup:
1. Push your project to a GitHub repository.
2. Set GITHUB_REPO="yourorg/yourrepo" and SELF_UPDATE_ENABLED=true in .env.
3. Clone that repo onto the server and run the backend from inside it.
4. "Apply Update" in the admin dashboard then runs git pull and restarts.
"""
import os
import re
import subprocess  # nosec B404 - fixed argv only, never a shell
import sys
import threading

import config
import models
import requests as http_requests
from auth import require_super_admin
from fastapi import APIRouter, Depends, HTTPException
from utils import utcnow

router = APIRouter()

GITHUB_REPO = config.GITHUB_REPO
CURRENT_VERSION = config.VERSION

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# "owner/repo" — anything else is a misconfiguration, not a repo we will pull.
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _git(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603 B607 - fixed argv, shell=False, no user input
        ["git", *args],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _repo_configured() -> bool:
    return bool(GITHUB_REPO) and bool(_REPO_RE.match(GITHUB_REPO))


def _is_git_repo() -> bool:
    try:
        return _git("rev-parse", "--git-dir", timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _get_current_commit() -> str:
    try:
        r = _git("rev-parse", "--short", "HEAD", timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _remote_url() -> str:
    try:
        r = _git("config", "--get", "remote.origin.url", timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# The host is pinned, not just the path. Matching on "owner/repo" alone would
# accept https://evil.example/owner/repo — an attacker who can edit .git/config
# would then serve the update while passing every other check.
_ALLOWED_REMOTE_HOSTS = {"github.com", "www.github.com"}

# https://github.com/owner/repo[.git]  |  [ssh://]git@github.com:owner/repo[.git]
_REMOTE_PATTERNS = (
    re.compile(r"^https://(?P<host>[^/]+)/(?P<path>[^/]+/[^/]+?)(?:\.git)?/?$", re.I),
    re.compile(r"^ssh://git@(?P<host>[^/]+)/(?P<path>[^/]+/[^/]+?)(?:\.git)?/?$", re.I),
    re.compile(r"^git@(?P<host>[^:]+):(?P<path>[^/]+/[^/]+?)(?:\.git)?/?$", re.I),
)


def _remote_matches_configured_repo() -> bool:
    """True when origin actually points at GITHUB_REPO on GitHub itself.

    Accepts the HTTPS and SSH spellings, with or without a .git suffix, and
    compares case-insensitively because GitHub treats owner/repo that way.
    Anything else — a different host, a plain-http remote, a local path, an
    unparseable value — is rejected.
    """
    if not _repo_configured():
        return False
    url = _remote_url().strip()
    if not url:
        return False
    for pattern in _REMOTE_PATTERNS:
        m = pattern.match(url)
        if not m:
            continue
        if m.group("host").lower() not in _ALLOWED_REMOTE_HOSTS:
            return False
        return m.group("path").lower() == GITHUB_REPO.lower()
    return False


def _working_tree_is_clean() -> bool:
    """Refuse to update over local edits — an update must not silently discard
    or merge on top of changes an operator made on the box."""
    try:
        r = _git("status", "--porcelain", timeout=10)
        return r.returncode == 0 and not r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False


def _get_latest_github_release() -> dict:
    if not _repo_configured():
        return {"tag": "not configured",
                "notes": "Set GITHUB_REPO in .env to enable update checks."}
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        r = http_requests.get(url, timeout=8,
                              headers={"Accept": "application/vnd.github.v3+json"})
        if r.status_code == 200:
            data = r.json()
            return {
                "tag": str(data.get("tag_name", "unknown"))[:100],
                "notes": str(data.get("body", ""))[:500],
                "published_at": str(data.get("published_at", ""))[:40],
                "url": str(data.get("html_url", ""))[:300],
            }
        return {"tag": "unknown", "notes": f"GitHub API returned {r.status_code}"}
    except http_requests.RequestException as e:
        return {"tag": "unknown", "notes": f"Could not reach GitHub: {e}"}


def _do_git_pull() -> tuple:
    """Fast-forward only. A merge or rebase here could run merge drivers and
    resolve conflicts unattended on a production host; refusing is safer and
    tells the operator to look at the box."""
    try:
        r = _git("pull", "--ff-only", "--no-rebase")
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return False, "git not found. Install Git and add it to PATH."
    except subprocess.TimeoutExpired:
        return False, "git pull timed out after 60 seconds."
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def _restart_server():
    import time
    time.sleep(1.5)
    os.execv(sys.executable, [sys.executable] + sys.argv)  # nosec B606 - deliberate in-place restart


@router.get("/update/check")
def check_for_updates(_admin: models.AdminUser = Depends(require_super_admin)):
    is_git = _is_git_repo()
    latest = _get_latest_github_release()
    return {
        "current_version": CURRENT_VERSION,
        "current_commit": _get_current_commit() if is_git else "N/A",
        "latest_release": latest,
        "git_available": is_git,
        "repo": GITHUB_REPO or "not configured",
        "self_update_enabled": config.SELF_UPDATE_ENABLED,
        "update_available": (
            config.SELF_UPDATE_ENABLED
            and _repo_configured()
            and latest.get("tag", "unknown") not in
            ("unknown", "not configured", CURRENT_VERSION)
        ),
        "checked_at": utcnow().isoformat(),
    }


@router.post("/update/apply")
def apply_update(_admin: models.AdminUser = Depends(require_super_admin)):
    if not config.SELF_UPDATE_ENABLED:
        raise HTTPException(
            status_code=403,
            detail=(
                "Self-update is disabled. It lets a dashboard session replace the "
                "server's code, so it must be turned on deliberately: set "
                "SELF_UPDATE_ENABLED=true and GITHUB_REPO in .env, then restart. "
                "Updating by hand on the server is the safer default."
            ),
        )
    if not _repo_configured():
        raise HTTPException(
            status_code=400,
            detail="GITHUB_REPO is not set to a valid 'owner/repo' value in .env.",
        )
    if not _is_git_repo():
        raise HTTPException(
            status_code=400,
            detail=(
                "Server is not inside a git repository. "
                "Clone the GitHub repo to the server and run from that folder."
            ),
        )
    if not _remote_matches_configured_repo():
        raise HTTPException(
            status_code=400,
            detail=(
                "The checkout's 'origin' remote does not match GITHUB_REPO. "
                "Refusing to pull code from an unexpected source."
            ),
        )
    if not _working_tree_is_clean():
        raise HTTPException(
            status_code=409,
            detail=(
                "The checkout has uncommitted local changes. Resolve them on the "
                "server first — an update must not discard local state."
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
