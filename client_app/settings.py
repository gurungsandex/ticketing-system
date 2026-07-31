"""
Runtime settings for the desktop client.

The server URL used to be a build-time constant in config.py, which meant that
if the server's LAN IP ever changed, every deployed client stopped working and
had to be rebuilt and reinstalled. That is a major cause of "the client lost its
connection" reports.

Resolution order (first match wins):
  1. HELPDESK_SERVER_URL environment variable (great for managed deployments).
  2. A user-editable settings.json in the app-data directory.
  3. The build-time default from config.py.

The resolved URL can also be updated at runtime (Settings dialog) and is then
persisted to settings.json, so IT can point clients at a new server without
redeploying binaries.
"""
import json
import os
import sys
from pathlib import Path

import config


def storage_dir() -> Path:
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "HelpdeskClient"
    else:
        d = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "HelpdeskClient"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _settings_path() -> Path:
    return storage_dir() / "settings.json"


def _load() -> dict:
    p = _settings_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        _settings_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _normalize(url: str) -> str:
    return (url or "").strip().rstrip("/")


def get_server_url() -> str:
    env = _normalize(os.environ.get("HELPDESK_SERVER_URL", ""))
    if env:
        return env
    stored = _normalize(_load().get("server_url", ""))
    if stored:
        return stored
    return _normalize(config.SERVER_URL)


def set_server_url(url: str) -> None:
    data = _load()
    data["server_url"] = _normalize(url)
    _save(data)


def is_configured() -> bool:
    url = get_server_url()
    return bool(url) and "YOUR_SERVER_IP" not in url
