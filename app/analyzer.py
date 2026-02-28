import asyncio
import socket
import time
from urllib.parse import urlparse

import dns.resolver
import httpx
import whois
from bs4 import BeautifulSoup

from app.models import (
    AnalysisResult,
    DnsInfo,
    HttpHeadersInfo,
    PerformanceInfo,
    SecurityScore,
    TechInfo,
    WhoisInfo,
)
from app.protocols import analyze_ssl, scan_ports


def _normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def _extract_hostname(url: str) -> str:
    return urlparse(url).hostname or ""


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

    for rtype, field in record_map.items():
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 5
            answers = resolver.resolve(hostname, rtype)
            setattr(info, field, [str(r) for r in answers])
        except Exception:
            pass

    return info


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
    headers: HttpHeadersInfo, ssl_info=None, url: str = ""
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


async def measure_performance(url: str) -> PerformanceInfo:
    info = PerformanceInfo()
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=15, verify=False
        ) as client:
            t0 = time.monotonic()
            response = await client.get(url)
            total = time.monotonic() - start

            info.total_ms = round(total * 1000, 2)
            info.ttfb_ms = round((time.monotonic() - t0) * 1000, 2)
            info.content_size_bytes = len(response.content)
            info.redirect_count = len(response.history)
    except Exception:
        pass
    return info


async def analyze_whois(hostname: str) -> WhoisInfo:
    info = WhoisInfo()
    try:
        loop = asyncio.get_event_loop()
        w = await loop.run_in_executor(None, whois.whois, hostname)

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

    except Exception:
        pass
    return info


def _whois_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return str(val[0])
    return str(val)


async def full_analysis(url: str) -> AnalysisResult:
    url = _normalize_url(url)
    hostname = _extract_hostname(url)
    result = AnalysisResult(url=url)

    if not hostname:
        result.error = "Невозможно извлечь имя хоста из URL"
        return result

    try:
        ip = socket.gethostbyname(hostname)
        result.ip_address = ip
    except socket.gaierror:
        result.error = f"Не удалось разрешить DNS для {hostname}"
        return result

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=15, verify=False
        ) as client:
            response = await client.get(url)
            html = response.text

        dns_task = analyze_dns(hostname)
        ssl_task = analyze_ssl(hostname) if url.startswith("https") else asyncio.sleep(0)
        headers_task = analyze_headers(response)
        perf_task = measure_performance(url)
        whois_task = analyze_whois(hostname)
        ports_task = scan_ports(ip)

        results = await asyncio.gather(
            dns_task, ssl_task, headers_task, perf_task, whois_task, ports_task,
            return_exceptions=True,
        )

        dns_res = results[0] if not isinstance(results[0], Exception) else DnsInfo()
        ssl_res = results[1] if not isinstance(results[1], Exception) and url.startswith("https") else None
        headers_res = results[2] if not isinstance(results[2], Exception) else HttpHeadersInfo()
        perf_res = results[3] if not isinstance(results[3], Exception) else PerformanceInfo()
        whois_res = results[4] if not isinstance(results[4], Exception) else WhoisInfo()
        ports_res = results[5] if not isinstance(results[5], Exception) else []

        result.dns = dns_res
        result.ssl = ssl_res
        result.headers = headers_res
        result.performance = perf_res
        result.whois = whois_res
        result.ports = ports_res

        tech_res = await detect_technologies(html, headers_res)
        result.technologies = tech_res

        result.security = calculate_security_score(headers_res, ssl_res, url)

    except httpx.RequestError as e:
        result.error = f"Ошибка запроса: {e}"
    except Exception as e:
        result.error = f"Неизвестная ошибка: {e}"

    return result
