import asyncio
import base64
import logging
import os
import re
import socket
import time
from urllib.parse import urlparse, urljoin

import dns.resolver
import httpx
import whois
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# По умолчанию проверять SSL (verify=True). Для диагностики сайтов с кривым сертификатом
# можно задать VERIFY_SSL=false в окружении.
VERIFY_SSL = os.environ.get("VERIFY_SSL", "true").lower() in ("1", "true", "yes")

from app.models import (
    AnalysisResult,
    CookieInfo,
    CookiesInfo,
    DnsInfo,
    GeoInfo,
    HttpHeadersInfo,
    PageVolumeInfo,
    PageVolumeItem,
    PerformanceInfo,
    RedirectInfo,
    RedirectStep,
    SeoInfo,
    SecurityScore,
    SiteMetaInfo,
    TechInfo,
    TracerouteInfo,
    WhoisInfo,
)
from app.protocols import analyze_ssl, scan_ports, traceroute

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


async def _capture_screenshot(url: str, width: int = 1280, height: int = 800) -> str | None:
    """Делает скриншот страницы, возвращает base64 PNG или None."""
    # 1. Пробуем Playwright (если установлен)
    if PLAYWRIGHT_AVAILABLE:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": width, "height": height},
                    ignore_https_errors=True,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                )
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(1)
                screenshot_bytes = await page.screenshot(type="png", full_page=False)
                await browser.close()
                return base64.b64encode(screenshot_bytes).decode("ascii")
        except Exception as e:
            logger.debug("Скриншот Playwright %s: %s", url, e)

    # 2. Fallback: PageShot API (без ключа)
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.get(
                "https://pageshot.site/v1/screenshot",
                params={"url": url, "width": 1280, "height": 800, "format": "png"},
            )
            if resp.status_code == 200 and len(resp.content) > 1000:
                return base64.b64encode(resp.content).decode("ascii")
    except Exception as e:
        logger.debug("Скриншот PageShot %s: %s", url, e)

    return None


def _normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def _extract_hostname(url: str) -> str:
    return urlparse(url).hostname or ""


def _detect_html_encoding(content: bytes, content_type: str = "") -> str:
    """Определяет кодировку HTML: из Content-Type, meta charset или эвристика."""
    # 1. Из заголовка Content-Type
    if content_type and "charset=" in content_type.lower():
        for part in content_type.split(";"):
            part = part.strip().lower()
            if part.startswith("charset="):
                enc = part.split("=", 1)[1].strip().strip('"')
                enc = "cp1251" if enc in ("windows-1251", "cp1251", "win1251") else enc
                if enc:
                    return enc
                break
    # 2. Из meta charset в HTML (первые 4 КБ)
    head = content[:4096].decode("utf-8", errors="ignore")
    if "charset=" in head.lower():
        m = re.search(r'charset\s*=\s*["\']?([a-zA-Z0-9\-]+)', head, re.I)
        if m:
            enc = m.group(1).lower()
            if enc in ("utf-8", "utf8"):
                return "utf-8"
            if enc in ("windows-1251", "cp1251", "win1251"):
                return "cp1251"
    # 3. Эвристика: UTF-8 с errors=replace даёт �; если много — пробуем cp1251
    utf8_decoded = content.decode("utf-8", errors="replace")
    if "\ufffd" in utf8_decoded:
        try:
            cp1251_decoded = content.decode("cp1251", errors="replace")
            if cp1251_decoded.count("\ufffd") < utf8_decoded.count("\ufffd"):
                return "cp1251"
        except (LookupError, ValueError):
            pass
    return "utf-8"


def _resolve_dns_record(hostname: str, rtype: str) -> list[str]:
    """Синхронный DNS lookup для одного типа записи."""
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 2
        resolver.lifetime = 2
        answers = resolver.resolve(hostname, rtype)
        return [str(r) for r in answers]
    except Exception as e:
        logger.debug("DNS %s для %s: %s", rtype, hostname, e)
        return []


async def analyze_dns(hostname: str) -> DnsInfo:
    info = DnsInfo()
    record_map = {
        "A": "a_records",
        "AAAA": "aaaa_records",
        "MX": "mx_records",
        "NS": "ns_records",
        "TXT": "txt_records",
        "CNAME": "cname_records",
    }

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(None, _resolve_dns_record, hostname, rtype)
        for rtype in record_map
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for (rtype, field), res in zip(record_map.items(), results):
        if isinstance(res, list):
            setattr(info, field, res)

    return info


def analyze_cookies(response: httpx.Response) -> CookiesInfo:
    """Анализирует Set-Cookie заголовки на предмет безопасности."""
    info = CookiesInfo()
    summary: set[str] = set()

    # Получаем все Set-Cookie (get_list в httpx, иначе get)
    set_cookies: list[str] = []
    if hasattr(response.headers, "get_list"):
        set_cookies = list(response.headers.get_list("set-cookie"))
    else:
        sc = response.headers.get("set-cookie")
        if sc:
            set_cookies = [sc]

    for val in set_cookies:
        val = val.decode("utf-8", errors="replace") if isinstance(val, bytes) else val
        cookie = _parse_set_cookie(val)
        if cookie:
            info.cookies.append(cookie)

    # Рекомендации
    if not info.cookies:
        info.summary = ["Cookies не установлены или не переданы в ответе"]
    else:
        insecure = [c for c in info.cookies if not c.secure]
        no_httponly = [c for c in info.cookies if not c.httponly]
        no_samesite = [c for c in info.cookies if not c.samesite]

        if insecure:
            info.summary.append(f"⚠ {len(insecure)} cookie без флага Secure (уязвимы при HTTP)")
        if no_httponly:
            info.summary.append(f"⚠ {len(no_httponly)} cookie без HttpOnly (доступны из JavaScript)")
        if no_samesite:
            info.summary.append(f"⚠ {len(no_samesite)} cookie без SameSite (CSRF риск)")
        if not insecure and not no_httponly and not no_samesite:
            info.summary.append("✓ Все cookies настроены безопасно")

    return info


def _parse_set_cookie(header_value: str) -> CookieInfo | None:
    """Парсит значение Set-Cookie и извлекает атрибуты."""
    parts = [p.strip() for p in header_value.split(";")]
    if not parts:
        return None
    name_val = parts[0].split("=", 1)
    if len(name_val) < 2:
        return None
    name, value = name_val[0].strip(), name_val[1].strip()
    if not name:
        return None

    cookie = CookieInfo(name=name)
    issues: list[str] = []

    for part in parts[1:]:
        if "=" in part:
            attr, val = part.split("=", 1)
            attr, val = attr.strip().lower(), val.strip()
            if attr == "path":
                cookie.path = val
            elif attr == "domain":
                cookie.domain = val
            elif attr == "expires":
                cookie.expires = val
            elif attr == "samesite":
                cookie.samesite = val
        else:
            attr = part.strip().lower()
            if attr == "secure":
                cookie.secure = True
            elif attr == "httponly":
                cookie.httponly = True

    if not cookie.secure:
        issues.append(f"{name}: отсутствует Secure")
    if not cookie.httponly:
        issues.append(f"{name}: отсутствует HttpOnly")
    if not cookie.samesite:
        issues.append(f"{name}: отсутствует SameSite")

    cookie.issues = issues
    return cookie


async def analyze_headers(response: httpx.Response) -> HttpHeadersInfo:
    h = response.headers
    return HttpHeadersInfo(
        server=h.get("server", ""),
        content_type=h.get("content-type", ""),
        x_powered_by=h.get("x-powered-by", ""),
        x_frame_options=h.get("x-frame-options", ""),
        x_content_type_options=h.get("x-content-type-options", ""),
        x_xss_protection=h.get("x-xss-protection", ""),
        strict_transport_security=h.get("strict-transport-security", ""),
        content_security_policy=h.get("content-security-policy", ""),
        referrer_policy=h.get("referrer-policy", ""),
        permissions_policy=h.get("permissions-policy", ""),
        all_headers={k: v for k, v in h.items()},
    )


def calculate_security_score(
    headers: HttpHeadersInfo,
    ssl_info=None,
    cookies_info=None,
    url: str = "",
) -> SecurityScore:
    score = 0
    details: list[str] = []
    max_score = 100

    if url.startswith("https://"):
        score += 10
        details.append("[+10] HTTPS включён")
    else:
        details.append("[  0] HTTPS не используется")

    if ssl_info and ssl_info.is_valid:
        score += 10
        details.append("[+10] SSL-сертификат действителен")
        if ssl_info.days_until_expiry < 30:
            details.append(f"[!] Сертификат истекает через {ssl_info.days_until_expiry} дней")
    elif ssl_info:
        details.append("[  0] SSL-сертификат недействителен или отсутствует")

    checks = [
        ("strict_transport_security", 15, "Strict-Transport-Security (HSTS)"),
        ("content_security_policy", 15, "Content-Security-Policy (CSP)"),
        ("x_frame_options", 10, "X-Frame-Options"),
        ("x_content_type_options", 10, "X-Content-Type-Options"),
        ("x_xss_protection", 5, "X-XSS-Protection"),
        ("referrer_policy", 10, "Referrer-Policy"),
        ("permissions_policy", 5, "Permissions-Policy"),
    ]

    for attr, pts, name in checks:
        if getattr(headers, attr, ""):
            score += pts
            details.append(f"[+{pts:>2}] {name} настроен")
        else:
            details.append(f"[  0] {name} отсутствует")

    if headers.server:
        details.append(f"[!] Сервер раскрывает версию: {headers.server}")

    # Проверка cookies
    if cookies_info and cookies_info.cookies:
        insecure_cookies = [c for c in cookies_info.cookies if not c.secure]
        no_httponly = [c for c in cookies_info.cookies if not c.httponly]
        if not insecure_cookies and not no_httponly:
            score += 5
            details.append("[+ 5] Cookies настроены безопасно (Secure, HttpOnly)")
        else:
            if insecure_cookies:
                details.append(f"[  0] {len(insecure_cookies)} cookie без Secure")
            if no_httponly:
                details.append(f"[  0] {len(no_httponly)} cookie без HttpOnly")

    if score >= 90:
        grade = "A+"
    elif score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return SecurityScore(score=score, max_score=max_score, grade=grade, details=details)


async def detect_technologies(html: str, headers: HttpHeadersInfo) -> TechInfo:
    techs: list[str] = []
    frameworks: list[str] = []
    meta: dict[str, str] = {}

    soup = BeautifulSoup(html, "lxml")

    for tag in soup.find_all("meta"):
        name = tag.get("name", "") or tag.get("property", "")
        content = tag.get("content", "")
        if name and content:
            meta[name] = content[:200]

    if "generator" in meta:
        techs.append(f"Generator: {meta['generator']}")

    tech_signatures = {
        "react": ("React", "framework"),
        "vue": ("Vue.js", "framework"),
        "angular": ("Angular", "framework"),
        "next": ("Next.js", "framework"),
        "nuxt": ("Nuxt.js", "framework"),
        "svelte": ("Svelte", "framework"),
        "jquery": ("jQuery", "library"),
        "bootstrap": ("Bootstrap", "css"),
        "tailwind": ("Tailwind CSS", "css"),
        "wordpress": ("WordPress", "cms"),
        "drupal": ("Drupal", "cms"),
        "joomla": ("Joomla", "cms"),
        "laravel": ("Laravel", "framework"),
        "django": ("Django", "framework"),
        "flask": ("Flask", "framework"),
        "express": ("Express.js", "framework"),
        "gatsby": ("Gatsby", "framework"),
    }

    html_lower = html.lower()
    for sig, (name, category) in tech_signatures.items():
        if sig in html_lower:
            if category == "framework":
                frameworks.append(name)
            else:
                techs.append(name)

    if headers.x_powered_by:
        techs.append(f"X-Powered-By: {headers.x_powered_by}")
    if headers.server:
        techs.append(f"Server: {headers.server}")

    return TechInfo(technologies=techs, meta_tags=meta, frameworks=frameworks)


def _get_http_version(response: httpx.Response) -> str:
    """Извлекает версию HTTP из ответа."""
    ver = getattr(response, "http_version", None)
    if ver == "HTTP/2":
        return "HTTP/2"
    if ver == "HTTP/1.1":
        return "HTTP/1.1"
    if ver == "HTTP/1.0":
        return "HTTP/1.0"
    return str(ver) if ver else ""


def analyze_redirects(response: httpx.Response, final_url: str) -> RedirectInfo:
    """Анализирует цепочку редиректов."""
    chain = [
        RedirectStep(url=str(r.url), status_code=r.status_code)
        for r in response.history
    ]
    return RedirectInfo(
        final_url=final_url,
        redirect_count=len(chain),
        chain=chain,
    )


def analyze_seo(html: str) -> SeoInfo:
    """Анализирует SEO-метаданные страницы."""
    info = SeoInfo()
    soup = BeautifulSoup(html, "lxml")

    title = soup.find("title")
    if title and title.string:
        info.title = title.string.strip()[:500]

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        info.meta_description = meta_desc["content"].strip()[:500]

    for prop, attr in [
        ("og:title", "og_title"),
        ("og:description", "og_description"),
        ("og:image", "og_image"),
        ("og:type", "og_type"),
    ]:
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            setattr(info, attr, tag["content"].strip()[:500])

    tw_card = soup.find("meta", attrs={"name": "twitter:card"})
    if tw_card and tw_card.get("content"):
        info.twitter_card = tw_card["content"].strip()
    tw_title = soup.find("meta", attrs={"name": "twitter:title"})
    if tw_title and tw_title.get("content"):
        info.twitter_title = tw_title["content"].strip()[:500]

    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport and viewport.get("content"):
        info.viewport = viewport["content"].strip()

    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        info.canonical_url = canonical["href"].strip()[:500]

    return info


async def analyze_site_meta(base_url: str) -> SiteMetaInfo:
    """Проверяет robots.txt и sitemap.xml (параллельно)."""
    info = SiteMetaInfo()
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = f"{base}/robots.txt"
    sitemap_url = f"{base}/sitemap.xml"

    async def fetch_robots():
        try:
            async with httpx.AsyncClient(timeout=2.0, verify=VERIFY_SSL) as client:
                r = await client.get(robots_url)
                if r.status_code == 200:
                    content = r.text.strip()
                    return True, content[:800] + ("..." if len(content) > 800 else "")
        except Exception as e:
            logger.debug("robots.txt %s: %s", robots_url, e)
        return False, ""

    async def fetch_sitemap():
        try:
            async with httpx.AsyncClient(timeout=2.0, verify=VERIFY_SSL) as client:
                s = await client.get(sitemap_url)
                if s.status_code == 200 and "xml" in (s.headers.get("content-type", "") or ""):
                    return True, sitemap_url
        except Exception as e:
            logger.debug("sitemap %s: %s", sitemap_url, e)
        return False, ""

    (robots_ok, robots_content), (sitemap_ok, sitemap_url_res) = await asyncio.gather(
        fetch_robots(), fetch_sitemap()
    )

    info.robots_txt_exists = robots_ok
    info.robots_txt_preview = robots_content
    info.sitemap_exists = sitemap_ok
    info.sitemap_url = sitemap_url_res if sitemap_ok else ""

    return info


def _country_code_to_flag(code: str) -> str:
    """Преобразует код страны (US, RU) в emoji флаг."""
    if not code or len(code) != 2:
        return ""
    try:
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())
    except (ValueError, TypeError):
        return ""


async def analyze_geo(ip: str) -> GeoInfo:
    """Определяет страну по IP через ip-api.com."""
    info = GeoInfo()
    if not ip or ip.startswith("127.") or ip == "::1":
        return info
    if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
        return info  # приватные IP — API не определит
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "country,countryCode"},
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("status") != "fail":
                    info.country = data.get("country", "")
                    info.country_code = data.get("countryCode", "")
                    info.flag_emoji = _country_code_to_flag(info.country_code)
    except Exception as e:
        logger.debug("GeoIP для %s: %s", ip, e)
    return info


async def analyze_page_volume(
    base_url: str, html: str, html_size: int
) -> PageVolumeInfo:
    """Анализирует объём страницы по типам контента (HTML, images, CSS, JS)."""
    info = PageVolumeInfo()
    soup = BeautifulSoup(html, "lxml")

    images_bytes = 0
    css_bytes = 0
    js_bytes = 0

    img_urls = []
    for img in soup.find_all("img", src=True)[:25]:
        src = img["src"].strip()
        if src and not src.startswith("data:"):
            img_urls.append(urljoin(base_url, src))

    css_urls = []
    for link in soup.find_all("link", rel=lambda x: x and "stylesheet" in str(x).lower())[:15]:
        href = link.get("href", "").strip()
        if href:
            css_urls.append(urljoin(base_url, href))

    js_urls = []
    for script in soup.find_all("script", src=True)[:15]:
        src = script["src"].strip()
        if src:
            js_urls.append(urljoin(base_url, src))

    async def fetch_size(client: httpx.AsyncClient, url: str) -> int:
        try:
            r = await client.head(url, follow_redirects=True)
            if r.status_code == 200:
                cl = r.headers.get("content-length")
                if cl:
                    return int(cl)
            r2 = await client.get(url, follow_redirects=True)
            return len(r2.content)
        except Exception as e:
            logger.debug("fetch_size %s: %s", url, e)
            return 0

    try:
        async with httpx.AsyncClient(timeout=5.0, verify=VERIFY_SSL) as client:
            for url in img_urls:
                images_bytes += await fetch_size(client, url)
            for url in css_urls:
                css_bytes += await fetch_size(client, url)
            for url in js_urls:
                js_bytes += await fetch_size(client, url)
    except Exception as e:
        logger.debug("analyze_page_volume: %s", e)

    total = html_size + images_bytes + css_bytes + js_bytes
    info.total_bytes = total

    if total > 0:
        for label, size in [
            ("html", html_size),
            ("images", images_bytes),
            ("css", css_bytes),
            ("js", js_bytes),
        ]:
            pct = round(100 * size / total, 2)
            info.items.append(
                PageVolumeItem(type=label, bytes=size, percent=pct)
            )

    return info


def _extract_performance_from_response(
    response: httpx.Response,
    ttfb_ms: float | None = None,
    dns_lookup_ms: float = 0.0,
    connect_ms: float = 0.0,
    total_ms: float | None = None,
) -> PerformanceInfo:
    """Извлекает метрики производительности из ответа."""
    info = PerformanceInfo()
    try:
        info.dns_lookup_ms = round(dns_lookup_ms, 2)
        info.connect_ms = round(connect_ms, 2)
        info.ttfb_ms = round(ttfb_ms, 2) if ttfb_ms is not None else 0.0
        if total_ms is not None:
            info.total_ms = round(total_ms, 2)
        else:
            elapsed = getattr(response, "elapsed", None)
            if elapsed is not None:
                info.total_ms = round(elapsed.total_seconds() * 1000, 2)
        info.content_size_bytes = len(response.content)
        info.redirect_count = len(response.history)
        info.http_version = _get_http_version(response)
        info.content_encoding = response.headers.get("content-encoding", "")
        info.cache_control = response.headers.get("cache-control", "")
    except Exception as e:
        logger.debug("_extract_performance: %s", e)
    return info


async def analyze_whois(hostname: str) -> WhoisInfo:
    info = WhoisInfo()
    try:
        loop = asyncio.get_event_loop()
        w = await asyncio.wait_for(
            loop.run_in_executor(None, whois.whois, hostname),
            timeout=5.0,
        )

        info.domain_name = _whois_str(w.domain_name)
        info.registrar = _whois_str(w.registrar)
        info.creation_date = _whois_str(w.creation_date)
        info.expiration_date = _whois_str(w.expiration_date)
        info.country = _whois_str(w.get("country", ""))

        ns = w.name_servers
        if ns:
            info.name_servers = [str(s) for s in ns] if isinstance(ns, list) else [str(ns)]

        status = w.status
        if status:
            info.status = [str(s) for s in status] if isinstance(status, list) else [str(status)]

    except Exception as e:
        logger.debug("WHOIS %s: %s", hostname, e)
    return info


def _whois_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return str(val[0])
    return str(val)


def _resolve_host_sync(hostname: str) -> str | None:
    """Разрешает хост в IP (IPv4 или IPv6) через getaddrinfo."""
    try:
        # family=0 — любой протокол (IPv4 и IPv6)
        addrs = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if addrs:
            return addrs[0][4][0]
    except (socket.gaierror, OSError):
        pass
    return None


def _measure_connect_sync(hostname: str, port: int) -> float:
    """Измеряет время TCP-подключения в миллисекундах."""
    try:
        t0 = time.perf_counter()
        sock = socket.create_connection((hostname, port), timeout=5)
        sock.close()
        return (time.perf_counter() - t0) * 1000
    except (socket.error, OSError):
        return 0.0


async def full_analysis(url: str) -> AnalysisResult:
    url = _normalize_url(url)
    hostname = _extract_hostname(url)
    result = AnalysisResult(url=url)

    if not hostname:
        result.error = "Невозможно извлечь имя хоста из URL"
        return result

    loop = asyncio.get_event_loop()

    # Асинхронное разрешение хоста (IPv4 и IPv6) вместо блокирующего gethostbyname
    t_dns_start = time.perf_counter()
    ip = await loop.run_in_executor(None, _resolve_host_sync, hostname)
    dns_lookup_ms = (time.perf_counter() - t_dns_start) * 1000

    if not ip:
        result.error = f"Не удалось разрешить DNS для {hostname}"
        return result
    result.ip_address = ip

    parsed = urlparse(url)
    port = 443 if parsed.scheme == "https" else 80

    # Измерение времени TCP-подключения (в executor, т.к. блокирующий вызов)
    connect_ms = await loop.run_in_executor(None, _measure_connect_sync, hostname, port)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=10.0, verify=VERIFY_SSL
        ) as client:
            # Streaming-запрос для точного измерения TTFB (время до первого байта).
            # Accept-Encoding: identity — запрашиваем несжатый ответ, чтобы избежать
            # ошибок декомпрессии (incorrect header check) при streaming.
            headers = {"Accept-Encoding": "identity"}
            ttfb_ms: float | None = None
            total_request_ms: float = 0.0
            response: httpx.Response
            html: str

            try:
                t_request_start = time.perf_counter()
                async with client.stream("GET", url, headers=headers) as stream_resp:
                    chunks: list[bytes] = []
                    async for chunk in stream_resp.aiter_bytes():
                        if ttfb_ms is None:
                            ttfb_ms = (time.perf_counter() - t_request_start) * 1000
                        chunks.append(chunk)
                    total_request_ms = (time.perf_counter() - t_request_start) * 1000
                    content = b"".join(chunks)
                    response = httpx.Response(
                        status_code=stream_resp.status_code,
                        headers=stream_resp.headers,
                        content=content,
                        request=stream_resp.request,
                    )
                    enc = _detect_html_encoding(
                        content,
                        stream_resp.headers.get("content-type", ""),
                    )
                    html = content.decode(enc, errors="replace")
            except Exception as e:
                # Ошибка декомпрессии (incorrect header check) или streaming — fallback на GET
                if isinstance(e, httpx.RequestError):
                    raise  # Сетевые ошибки пробрасываем
                logger.debug("Streaming fallback на GET: %s", e)
                t_request_start = time.perf_counter()
                response = await client.get(url)
                total_request_ms = (time.perf_counter() - t_request_start) * 1000
                html = response.text
                ttfb_ms = response.elapsed.total_seconds() * 1000 if response.elapsed else total_request_ms

        perf_res = _extract_performance_from_response(
            response,
            ttfb_ms=ttfb_ms,
            dns_lookup_ms=dns_lookup_ms,
            connect_ms=connect_ms,
            total_ms=total_request_ms,
        )

        final_url = str(response.url)
        dns_task = analyze_dns(hostname)
        ssl_task = analyze_ssl(hostname) if url.startswith("https") else asyncio.sleep(0)
        headers_task = analyze_headers(response)
        whois_task = analyze_whois(hostname)
        ports_task = scan_ports(ip)
        traceroute_task = traceroute(ip, max_hops=8, timeout=90)
        site_meta_task = analyze_site_meta(url)
        geo_task = analyze_geo(ip)
        page_volume_task = analyze_page_volume(final_url, html, len(response.content))
        screenshot_task = _capture_screenshot(final_url)

        results = await asyncio.gather(
            dns_task, ssl_task, headers_task, whois_task, ports_task, traceroute_task,
            site_meta_task, geo_task, page_volume_task, screenshot_task,
            return_exceptions=True,
        )

        dns_res = results[0] if not isinstance(results[0], Exception) else DnsInfo()
        ssl_res = results[1] if not isinstance(results[1], Exception) and url.startswith("https") else None
        headers_res = results[2] if not isinstance(results[2], Exception) else HttpHeadersInfo()
        whois_res = results[3] if not isinstance(results[3], Exception) else WhoisInfo()
        ports_res = results[4] if not isinstance(results[4], Exception) else []
        if isinstance(results[5], Exception):
            traceroute_res = TracerouteInfo(
                target=ip,
                error=f"Ошибка: {results[5]}",
            )
        else:
            traceroute_res = results[5]
        site_meta_res = results[6] if not isinstance(results[6], Exception) else SiteMetaInfo()
        geo_res = results[7] if not isinstance(results[7], Exception) else GeoInfo()
        page_volume_res = results[8] if not isinstance(results[8], Exception) else PageVolumeInfo()
        screenshot_res = results[9] if not isinstance(results[9], Exception) and results[9] else None

        result.dns = dns_res
        result.ssl = ssl_res
        result.headers = headers_res
        result.performance = perf_res
        result.whois = whois_res
        result.ports = ports_res
        result.traceroute = traceroute_res

        cookies_res = analyze_cookies(response)
        result.cookies = cookies_res

        result.redirect_info = analyze_redirects(response, str(response.url))
        result.seo = analyze_seo(html)
        result.site_meta = site_meta_res
        result.geo = geo_res
        result.page_volume = page_volume_res

        tech_res = await detect_technologies(html, headers_res)
        result.technologies = tech_res

        result.security = calculate_security_score(headers_res, ssl_res, cookies_res, url)
        result.screenshot = screenshot_res

    except httpx.RequestError as e:
        result.error = f"Ошибка запроса: {e}"
    except Exception as e:
        result.error = f"Неизвестная ошибка: {e}"

    return result
