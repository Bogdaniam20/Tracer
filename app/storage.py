import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from filelock import FileLock

DATA_FILE = Path(__file__).parent.parent / "data" / "saved_sites.json"
HISTORY_FILE = Path(__file__).parent.parent / "data" / "scan_history.json"
DATA_LOCK = DATA_FILE.with_suffix(".lock")
HISTORY_LOCK = HISTORY_FILE.with_suffix(".lock")

# Лимит истории настраивается через HISTORY_MAX_ENTRIES (по умолчанию 100)
HISTORY_MAX_ENTRIES = int(os.environ.get("HISTORY_MAX_ENTRIES", "100"))


def _ensure_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")


def _read_all() -> list[dict]:
    _ensure_file(DATA_FILE)
    with FileLock(DATA_LOCK, timeout=10):
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _write_all(data: list[dict]):
    _ensure_file(DATA_FILE)
    with FileLock(DATA_LOCK, timeout=10):
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_site(url: str, analysis: dict, note: str = "") -> dict:
    with FileLock(DATA_LOCK, timeout=10):
        _ensure_file(DATA_FILE)
        sites = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        entry = {
            "id": uuid.uuid4().hex[:12],
            "url": url,
            "note": note,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "analysis": analysis,
        }
        sites.insert(0, entry)
        DATA_FILE.write_text(json.dumps(sites, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def get_all_saved() -> list[dict]:
    return _read_all()


def get_saved_by_id(site_id: str) -> Optional[dict]:
    for s in _read_all():
        if s["id"] == site_id:
            return s
    return None


def delete_saved(site_id: str) -> bool:
    with FileLock(DATA_LOCK, timeout=10):
        _ensure_file(DATA_FILE)
        sites = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        filtered = [s for s in sites if s["id"] != site_id]
        if len(filtered) == len(sites):
            return False
        DATA_FILE.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def update_note(site_id: str, note: str) -> bool:
    with FileLock(DATA_LOCK, timeout=10):
        _ensure_file(DATA_FILE)
        sites = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for s in sites:
            if s["id"] == site_id:
                s["note"] = note
                DATA_FILE.write_text(json.dumps(sites, ensure_ascii=False, indent=2), encoding="utf-8")
                return True
    return False


# --- История сканирований ---

def _ensure_history_file():
    _ensure_file(HISTORY_FILE)


def _read_history() -> list[dict]:
    _ensure_history_file()
    with FileLock(HISTORY_LOCK, timeout=10):
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def add_scan_to_history(url: str, ip_address: str = "") -> None:
    _ensure_history_file()
    with FileLock(HISTORY_LOCK, timeout=10):
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        entry = {
            "url": url,
            "ip_address": ip_address,
            "scanned_at": datetime.now().isoformat(timespec="seconds"),
        }
        history.insert(0, entry)
        history = history[:HISTORY_MAX_ENTRIES]
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def get_scan_history(limit: int = 50) -> list[dict]:
    return _read_history()[:limit]


def delete_history_entry(index: int) -> bool:
    _ensure_history_file()
    with FileLock(HISTORY_LOCK, timeout=10):
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if index < 0 or index >= len(history):
            return False
        history.pop(index)
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def clear_history() -> None:
    _ensure_history_file()
    with FileLock(HISTORY_LOCK, timeout=10):
        HISTORY_FILE.write_text("[]", encoding="utf-8")
