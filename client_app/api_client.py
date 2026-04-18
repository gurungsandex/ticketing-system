import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

import requests

from config import SERVER_URL

_queue_lock = threading.Lock()


def _storage_dir() -> Path:
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "HelpdeskClient"
    else:
        d = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "HelpdeskClient"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _queue_path() -> Path:
    return _storage_dir() / "offline_queue.json"


def _read_queue() -> list:
    p = _queue_path()
    if not p.exists(): return []
    try:
        data = p.read_text(encoding="utf-8").strip()
        return json.loads(data) if data else []
    except Exception: return []


def _write_queue(items: list):
    try:
        _queue_path().write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    except Exception: pass


def _enqueue(payload: dict):
    with _queue_lock:
        q = _read_queue(); q.append(payload); _write_queue(q)


def get_queue_size() -> int:
    with _queue_lock: return len(_read_queue())


def submit_ticket(payload: dict) -> Optional[dict]:
    try:
        r = requests.post(f"{SERVER_URL}/tickets/", json=payload, timeout=6)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException:
        _enqueue(payload)
        return None


def upload_attachment(ticket_id: str, filepath: str) -> bool:
    """Upload a file attachment for a ticket. Returns True on success."""
    try:
        import mimetypes
        mime, _ = mimetypes.guess_type(filepath)
        mime = mime or "application/octet-stream"
        with open(filepath, "rb") as f:
            filename = os.path.basename(filepath)
            r = requests.post(
                f"{SERVER_URL}/tickets/{ticket_id}/attachments",
                files={"file": (filename, f, mime)},
                timeout=30,
            )
            r.raise_for_status()
            return True
    except Exception:
        return False


def get_notifications(client_id: str) -> list:
    try:
        r = requests.get(f"{SERVER_URL}/notifications/{client_id}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception: return []


def flush_offline_queue() -> int:
    with _queue_lock:
        queue = _read_queue()
        if not queue: return 0
        remaining = []; flushed = 0
        for payload in queue:
            try:
                r = requests.post(f"{SERVER_URL}/tickets/", json=payload, timeout=6)
                r.raise_for_status(); flushed += 1
            except Exception: remaining.append(payload)
        _write_queue(remaining)
        return flushed
