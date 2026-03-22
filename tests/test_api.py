from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_returns_ok(client):
    """GET /api/health возвращает status ok и информацию о Redis."""
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "redis" in data


def test_get_saved_returns_list(client, temp_storage_file):
    """GET /api/saved возвращает список."""
    r = client.get("/api/saved")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_save_site_creates_entry(client, temp_storage_file):
    """POST /api/saved сохраняет сайт."""
    r = client.post("/api/saved", json={
        "url": "https://example.com",
        "analysis": {"dns": {}},
        "note": "Test",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["url"] == "https://example.com"
    assert "id" in data


def test_delete_saved_returns_404_for_unknown(client):
    """DELETE /api/saved/{id} возвращает 404 для несуществующего."""
    r = client.delete("/api/saved/nonexistent123")
    assert r.status_code == 404


@patch("main.full_analysis", new_callable=AsyncMock)
def test_analyze_endpoint(mock_analysis, client):
    """POST /api/analyze вызывает full_analysis и возвращает результат."""
    mock_analysis.return_value = {
        "url": "https://example.com",
        "ip_address": "93.184.216.34",
        "error": "",
    }
    r = client.post("/api/analyze", json={"url": "https://example.com"})
    assert r.status_code == 200
    mock_analysis.assert_called_once_with("https://example.com")
