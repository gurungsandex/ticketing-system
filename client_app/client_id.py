import os
import sys
import uuid
from pathlib import Path


def _get_storage_dir() -> Path:
    if sys.platform == "darwin":
        storage = Path.home() / "Library" / "Application Support" / "HelpdeskClient"
    else:
        storage = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "HelpdeskClient"
    storage.mkdir(parents=True, exist_ok=True)
    return storage


def get_client_id() -> str:
    storage_dir = _get_storage_dir()
    id_file = storage_dir / "client_id.txt"

    if id_file.exists():
        cid = id_file.read_text(encoding="utf-8").strip()
        if cid:
            return cid

    new_id = str(uuid.uuid4())
    id_file.write_text(new_id, encoding="utf-8")
    return new_id


def is_first_launch() -> bool:
    return not (_get_storage_dir() / "client_id.txt").exists()
