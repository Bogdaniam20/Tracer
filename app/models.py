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
    error: str = ""
