import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_FILE = Path(__file__).parent.parent / "data" / "saved_sites.json"
HISTORY_FILE = Path(__file__).parent.parent / "data" / "scan_history.json"
HISTORY_MAX_ENTRIES = 100


def _ensure_file():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")


def _read_all() -> list[dict]:
    _ensure_file()
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _write_all(data: list[dict]):
    _ensure_file()
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_site(url: str, analysis: dict, note: str = "") -> dict:
    sites = _read_all()
    entry = {
        "id": uuid.uuid4().hex[:12],
        "url": url,
        "note": note,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "analysis": analysis,
    }
    sites.insert(0, entry)
    _write_all(sites)
    return entry


def get_all_saved() -> list[dict]:
    return _read_all()


def get_saved_by_id(site_id: str) -> Optional[dict]:
    for s in _read_all():
        if s["id"] == site_id:
            return s
    return None


def delete_saved(site_id: str) -> bool:
    sites = _read_all()
    filtered = [s for s in sites if s["id"] != site_id]
    if len(filtered) == len(sites):
        return False
    _write_all(filtered)
    return True


def update_note(site_id: str, note: str) -> bool:
    sites = _read_all()
    for s in sites:
        if s["id"] == site_id:
            s["note"] = note
            _write_all(sites)
            return True
    return False


# --- История сканирований ---

def _ensure_history_file():
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text("[]", encoding="utf-8")


def _read_history() -> list[dict]:
    _ensure_history_file()
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def add_scan_to_history(url: str, ip_address: str = "") -> None:
    history = _read_history()
    entry = {
        "url": url,
        "ip_address": ip_address,
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
    }
    history.insert(0, entry)
    history = history[:HISTORY_MAX_ENTRIES]
    _ensure_history_file()
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def get_scan_history(limit: int = 50) -> list[dict]:
    return _read_history()[:limit]
