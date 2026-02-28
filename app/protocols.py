import ssl
import socket
import asyncio
from datetime import datetime

from app.models import SslInfo, PortInfo


COMMON_PORTS = {
    21: "FTP",
    22: "SSH",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    465: "SMTPS",
    587: "SMTP/TLS",
    993: "IMAPS",
    995: "POP3S",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    8080: "HTTP-Alt",
    8443: "HTTPS-Alt",
    27017: "MongoDB",
}


async def analyze_ssl(hostname: str, port: int = 443) -> SslInfo:
    info = SslInfo()
    try:
        ctx = ssl.create_default_context()
        conn = ctx.wrap_socket(socket.socket(socket.AF_INET), server_hostname=hostname)
        conn.settimeout(5)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: conn.connect((hostname, port)))

        cert = conn.getpeercert()
        cipher = conn.cipher()

        if cert:
            issuer_parts = []
            for rdn in cert.get("issuer", []):
                for attr in rdn:
                    issuer_parts.append(f"{attr[0]}={attr[1]}")
            info.issuer = ", ".join(issuer_parts)

            subject_parts = []
            for rdn in cert.get("subject", []):
                for attr in rdn:
                    subject_parts.append(f"{attr[0]}={attr[1]}")
            info.subject = ", ".join(subject_parts)

            info.serial_number = cert.get("serialNumber", "")
            info.not_before = cert.get("notBefore", "")
            info.not_after = cert.get("notAfter", "")
            info.version = cert.get("version", 0)

            san_list = []
            for san_type, san_value in cert.get("subjectAltName", []):
                san_list.append(f"{san_type}:{san_value}")
            info.san = san_list

            try:
                expiry = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                info.days_until_expiry = (expiry - datetime.now()).days
                info.is_valid = info.days_until_expiry > 0
            except (ValueError, KeyError):
                pass

        if cipher:
            info.protocol_version = cipher[1]
            info.cipher_suite = cipher[0]
            info.key_size = cipher[2] if len(cipher) > 2 else 0

        conn.close()

    except Exception:
        pass

    return info


async def scan_port(host: str, port: int, timeout: float = 2.0) -> PortInfo | None:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        service = COMMON_PORTS.get(port, "unknown")
        return PortInfo(port=port, service=service, state="open")
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return None


async def scan_ports(host: str, ports: list[int] | None = None) -> list[PortInfo]:
    if ports is None:
        ports = list(COMMON_PORTS.keys())

    tasks = [scan_port(host, port) for port in ports]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]
