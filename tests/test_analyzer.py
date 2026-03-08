from unittest.mock import MagicMock

import pytest

from app.analyzer import (
    _normalize_url,
    _extract_hostname,
    analyze_cookies,
    calculate_security_score,
    detect_technologies,
)
from app.models import HttpHeadersInfo, SslInfo


def test_normalize_url_adds_https():
    """URL без схемы получает https://."""
    assert _normalize_url("example.com") == "https://example.com"


def test_normalize_url_preserves_https():
    """URL с https остаётся без изменений (кроме trailing slash)."""
    assert _normalize_url("https://example.com") == "https://example.com"


def test_normalize_url_strips_trailing_slash():
    """Trailing slash удаляется."""
    assert _normalize_url("https://example.com/") == "https://example.com"


def test_extract_hostname():
    """Извлечение hostname из URL."""
    assert _extract_hostname("https://example.com/path") == "example.com"
    assert _extract_hostname("http://sub.example.com:8080/") == "sub.example.com"
    assert _extract_hostname("invalid") == ""


def test_calculate_security_score_https_bonus():
    """HTTPS даёт +10 баллов."""
    headers = HttpHeadersInfo()
    score = calculate_security_score(headers, None, url="https://example.com")
    assert score.score >= 10
    assert any("[+10] HTTPS" in d for d in score.details)


def test_calculate_security_score_http_no_bonus():
    """HTTP не даёт бонус за HTTPS."""
    headers = HttpHeadersInfo()
    score = calculate_security_score(headers, None, url="http://example.com")
    assert any("HTTPS не используется" in d for d in score.details)


def test_calculate_security_score_hsts_adds_points():
    """HSTS добавляет баллы."""
    headers = HttpHeadersInfo(strict_transport_security="max-age=31536000")
    score = calculate_security_score(headers, None, url="https://example.com")
    assert any("HSTS" in d for d in score.details)
    assert score.score >= 25


def test_calculate_security_score_grade_a():
    """Оценка A при высоком score."""
    headers = HttpHeadersInfo(
        strict_transport_security="x",
        content_security_policy="x",
        x_frame_options="DENY",
        x_content_type_options="nosniff",
        referrer_policy="no-referrer",
    )
    ssl = SslInfo(is_valid=True)
    score = calculate_security_score(headers, ssl, url="https://example.com")
    assert score.grade in ("A", "A+")


@pytest.mark.asyncio
async def test_detect_technologies_finds_meta_generator():
    """detect_technologies находит meta generator."""
    html = '<html><head><meta name="generator" content="WordPress 6.0"></head></html>'
    headers = HttpHeadersInfo()
    tech = await detect_technologies(html, headers)
    assert any("Generator" in t for t in tech.technologies)


@pytest.mark.asyncio
async def test_detect_technologies_finds_x_powered_by():
    """detect_technologies добавляет X-Powered-By из заголовков."""
    html = "<html></html>"
    headers = HttpHeadersInfo(x_powered_by="Express")
    tech = await detect_technologies(html, headers)
    assert any("Express" in t for t in tech.technologies)


def test_analyze_cookies_parses_secure_httponly():
    """analyze_cookies парсит Secure и HttpOnly."""
    resp = MagicMock()
    resp.headers.get_list.return_value = [
        "session=abc123; Path=/; Secure; HttpOnly; SameSite=Strict",
    ]
    info = analyze_cookies(resp)
    assert len(info.cookies) == 1
    assert info.cookies[0].name == "session"
    assert info.cookies[0].secure is True
    assert info.cookies[0].httponly is True
    assert info.cookies[0].samesite == "Strict"
    assert len(info.cookies[0].issues) == 0


def test_analyze_cookies_detects_insecure():
    """analyze_cookies обнаруживает небезопасные cookies."""
    resp = MagicMock()
    resp.headers.get_list.return_value = ["foo=bar; Path=/"]
    info = analyze_cookies(resp)
    assert len(info.cookies) == 1
    assert info.cookies[0].secure is False
    assert info.cookies[0].httponly is False
    assert any("Secure" in i for i in info.cookies[0].issues)
