import pytest

from app import storage


def test_save_site_creates_entry(temp_storage_file):
    """save_site создаёт запись и возвращает её."""
    entry = storage.save_site("https://example.com", {"dns": {}}, "Тест")
    assert "id" in entry
    assert entry["url"] == "https://example.com"
    assert entry["note"] == "Тест"
    assert "analysis" in entry
    assert "saved_at" in entry


def test_get_all_saved_returns_list(temp_storage_file):
    """get_all_saved возвращает список сохранённых."""
    storage.save_site("https://a.com", {}, "")
    storage.save_site("https://b.com", {}, "")
    sites = storage.get_all_saved()
    assert len(sites) == 2


def test_get_saved_by_id_found(temp_storage_file):
    """get_saved_by_id находит запись по id."""
    entry = storage.save_site("https://example.com", {}, "")
    found = storage.get_saved_by_id(entry["id"])
    assert found is not None
    assert found["url"] == "https://example.com"


def test_get_saved_by_id_not_found(temp_storage_file):
    """get_saved_by_id возвращает None для несуществующего id."""
    assert storage.get_saved_by_id("nonexistent123") is None


def test_delete_saved_removes_entry(temp_storage_file):
    """delete_saved удаляет запись."""
    entry = storage.save_site("https://example.com", {}, "")
    ok = storage.delete_saved(entry["id"])
    assert ok is True
    assert storage.get_saved_by_id(entry["id"]) is None


def test_delete_saved_nonexistent_returns_false(temp_storage_file):
    """delete_saved возвращает False для несуществующего id."""
    assert storage.delete_saved("nonexistent123") is False


def test_update_note_updates(temp_storage_file):
    """update_note обновляет заметку."""
    entry = storage.save_site("https://example.com", {}, "Старая")
    ok = storage.update_note(entry["id"], "Новая заметка")
    assert ok is True
    found = storage.get_saved_by_id(entry["id"])
    assert found["note"] == "Новая заметка"


def test_update_note_nonexistent_returns_false(temp_storage_file):
    """update_note возвращает False для несуществующего id."""
    assert storage.update_note("nonexistent123", "Заметка") is False
