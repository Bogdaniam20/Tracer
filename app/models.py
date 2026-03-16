from pydantic import BaseModel
from typing import Optional


class AnalyzeRequest(BaseModel):
    url: str


class SaveSiteRequest(BaseModel):
    url: str
    analysis: dict
    note: str = ""


class SavedSiteResponse(BaseModel):
    id: str
    url: str
    note: str
    saved_at: str
    analysis: dict


class UpdateNoteRequest(BaseModel):
    note: str


class DnsInfo(BaseModel):
    a_records: list[str] = []
    aaaa_records: list[str] = []
    mx_records: list[str] = []
    ns_records: list[str] = []
    txt_records: list[str] = []
    cname_records: list[str] = []


class SslInfo(BaseModel):
    issuer: str = ""
    subject: str = ""
    version: int = 0
    serial_number: str = ""
    not_before: str = ""
    not_after: str = ""
    protocol_version: str = ""
    cipher_suite: str = ""
    key_size: int = 0
    san: list[str] = []
    is_valid: bool = False
    days_until_expiry: int = 0


class HttpHeadersInfo(BaseModel):
    server: str = ""
    content_type: str = ""
    x_powered_by: str = ""
    x_frame_options: str = ""
    x_content_type_options: str = ""
    x_xss_protection: str = ""
    strict_transport_security: str = ""
    content_security_policy: str = ""
    referrer_policy: str = ""
    permissions_policy: str = ""
    all_headers: dict[str, str] = {}


class SecurityScore(BaseModel):
    score: int = 0
    max_score: int = 100
    grade: str = "F"
    details: list[str] = []


class TechInfo(BaseModel):
    technologies: list[str] = []
    meta_tags: dict[str, str] = {}
    frameworks: list[str] = []


class PerformanceInfo(BaseModel):
    dns_lookup_ms: float = 0.0
    connect_ms: float = 0.0
    ttfb_ms: float = 0.0
    total_ms: float = 0.0
    content_size_bytes: int = 0
    redirect_count: int = 0
    http_version: str = ""
    content_encoding: str = ""
    cache_control: str = ""


class RedirectStep(BaseModel):
    url: str
    status_code: int


class RedirectInfo(BaseModel):
    final_url: str = ""
    redirect_count: int = 0
    chain: list[RedirectStep] = []


class SeoInfo(BaseModel):
    title: str = ""
    meta_description: str = ""
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    og_type: str = ""
    twitter_card: str = ""
    twitter_title: str = ""
    viewport: str = ""
    canonical_url: str = ""


class WhoisInfo(BaseModel):
    domain_name: str = ""
    registrar: str = ""
    creation_date: str = ""
    expiration_date: str = ""
    name_servers: list[str] = []
    status: list[str] = []
    country: str = ""


class PortInfo(BaseModel):
    port: int
    service: str
    state: str


class TracerouteHop(BaseModel):
    hop: int
    ip: str
    hostname: str = ""
    rtt_ms: list[float] = []


class TracerouteInfo(BaseModel):
    target: str = ""
    hops: list[TracerouteHop] = []
    error: str = ""


class CookieInfo(BaseModel):
    name: str
    secure: bool = False
    httponly: bool = False
    samesite: str = ""  # Strict, Lax, None
    path: str = ""
    domain: str = ""
    expires: str = ""
    issues: list[str] = []  # Проблемы безопасности


class CookiesInfo(BaseModel):
    cookies: list[CookieInfo] = []
    summary: list[str] = []  # Краткие рекомендации


class SiteMetaInfo(BaseModel):
    robots_txt_exists: bool = False
    robots_txt_preview: str = ""
    sitemap_exists: bool = False
    sitemap_url: str = ""


class GeoInfo(BaseModel):
    country: str = ""
    country_code: str = ""
    flag_emoji: str = ""


class PageVolumeItem(BaseModel):
    type: str  # html, images, css, js
    bytes: int = 0
    percent: float = 0.0


class PageVolumeInfo(BaseModel):
    total_bytes: int = 0
    items: list[PageVolumeItem] = []


class AnalysisResult(BaseModel):
    url: str
    ip_address: str = ""
    dns: Optional[DnsInfo] = None
    ssl: Optional[SslInfo] = None
    headers: Optional[HttpHeadersInfo] = None
    security: Optional[SecurityScore] = None
    technologies: Optional[TechInfo] = None
    performance: Optional[PerformanceInfo] = None
    whois: Optional[WhoisInfo] = None
    ports: list[PortInfo] = []
    traceroute: Optional[TracerouteInfo] = None
    cookies: Optional[CookiesInfo] = None
    redirect_info: Optional[RedirectInfo] = None
    seo: Optional[SeoInfo] = None
    site_meta: Optional[SiteMetaInfo] = None
    geo: Optional[GeoInfo] = None
    page_volume: Optional[PageVolumeInfo] = None
    screenshot: Optional[str] = None  # base64 PNG
    error: str = ""
