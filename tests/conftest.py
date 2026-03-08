"""Общие фикстуры и настройки для тестов."""
import sys
from pathlib import Path

import pytest

pytest_plugins = ("pytest_asyncio",)

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def temp_storage_file(tmp_path):
    """Временный файл для storage вместо saved_sites.json."""
    from app import storage
    original = storage.DATA_FILE
    storage.DATA_FILE = tmp_path / "saved_sites.json"
    yield storage.DATA_FILE
    storage.DATA_FILE = original
