import logging
import platform
import re
import ssl
import socket
import subprocess
import asyncio
from datetime import datetime

from app.models import SslInfo, PortInfo, TracerouteInfo, TracerouteHop

logger = logging.getLogger(__name__)


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
        conn.settimeout(3)

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

    except Exception as e:
        logger.debug("SSL для %s:%s: %s", hostname, port, e)

    return info


async def scan_port(host: str, port: int, timeout: float = 1.0) -> PortInfo | None:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        #writer.wait_closed() эта ошибка тормозила бы приложение
        await writer.wait_closed()
        service = COMMON_PORTS.get(port, "unknown")
        return PortInfo(port=port, service=service, state="open")
    #except (asyncio.TimeoutError): эта ошибка не перехватывает все ошибки
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return None


async def scan_ports(host: str, ports: list[int] | None = None) -> list[PortInfo]:
    if ports is None:
        ports = list(COMMON_PORTS.keys())

    tasks = [scan_port(host, port) for port in ports]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


def _is_ipv6(addr: str) -> bool:
    """Проверяет, является ли адрес IPv6."""
    return ":" in addr


async def traceroute(host: str, max_hops: int = 8, timeout: int = 90) -> TracerouteInfo:
    """Выполняет traceroute до хоста (tracert на Windows, traceroute на Unix)."""
    info = TracerouteInfo(target=host)
    is_windows = platform.system() == "Windows"
    # 8 хопов * 3 пробы * 2 сек ≈ 48 сек; timeout 90 даёт запас

    def _run_traceroute():
        if is_windows:
            # -w 2000: 2 сек на ответ; без -d — показывать hostname (обратный DNS)
            base = ["tracert", "-h", str(max_hops), "-w", "2000"]
            if _is_ipv6(host):
                base.insert(1, "-6")
            cmd = base + [host]
        else:
            base = ["traceroute", "-m", str(max_hops), "-w", "2"]
            if _is_ipv6(host):
                base.insert(1, "-6")
            cmd = base + [host]
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="cp866" if is_windows else "utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            logger.debug("Traceroute timeout для %s", host)
            return None
        except FileNotFoundError as e:
            logger.debug("Traceroute не найден: %s", e)
            return None

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_traceroute)
        if result is None:
            info.error = "Traceroute недоступен или превышено время ожидания"
            return info

        if result.returncode != 0 and not result.stdout:
            err = (result.stderr or "Ошибка выполнения traceroute").strip()[:200]
            info.error = err if err else "Не удалось получить маршрут"
            return info

        info.hops = _parse_traceroute_output(result.stdout, is_windows)
        # Обратный DNS для хопов без hostname (PTR-записи маршрутизаторов)
        await _resolve_hop_hostnames(info.hops)
    except Exception as e:
        info.error = str(e)[:150]

    return info


async def _resolve_hop_hostnames(hops: list[TracerouteHop]) -> None:
    """Заполняет hostname через обратный DNS (gethostbyaddr) для хопов без имени."""

    def _resolve_all() -> None:
        for hop in hops:
            if hop.hostname:
                continue
            try:
                name, _, _ = socket.gethostbyaddr(hop.ip)
                if name and name != hop.ip:
                    hop.hostname = name
            except (socket.gaierror, socket.herror, socket.timeout, OSError):
                pass

    try:
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(loop.run_in_executor(None, _resolve_all), timeout=8)
    except (asyncio.TimeoutError, Exception):
        pass


def _parse_traceroute_output(output: str, is_windows: bool) -> list[TracerouteHop]:
    hops: list[TracerouteHop] = []
    ip_pattern = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
    # Windows: "  1    <1 ms    <1 ms    <1 ms  192.168.1.1" или "  hostname [192.168.1.1]"
    # Linux:   " 1  hostname (192.168.1.1)  1.234 ms" или " 1  192.168.1.1  1.234 ms"

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        # Пропускаем заголовки
        if "tracing route" in line.lower() or "over a maximum" in line.lower():
            continue
        # Пропускаем строки с "*" без IP (Request timed out)
        if "*" in line and not ip_pattern.search(line):
            continue
        # Ищем номер хопа в начале строки
        m = re.match(r"^\s*(\d+)\s+", line)
        if not m:
            continue
        hop_num = int(m.group(1))
        # Извлекаем IP и hostname
        ip = ""
        hostname = ""
        # Windows: hostname [IP]
        win_match = re.search(r"\s+(\S+)\s*\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]", line)
        if win_match:
            potential_host, ip = win_match.group(1), win_match.group(2)
            # hostname не должен быть числом или "ms"
            if not re.match(r"^[\d.]+$", potential_host) and potential_host.lower() != "ms":
                hostname = potential_host
        # Linux: hostname (IP) или IP (IP)
        if not ip:
            lin_match = re.search(r"\s+(\S+)\s*\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)", line)
            if lin_match:
                potential_host, ip = lin_match.group(1), lin_match.group(2)
                if not re.match(r"^[\d.]+$", potential_host):
                    hostname = potential_host
        # Fallback: только IP
        if not ip:
            ip_match = ip_pattern.search(line)
            if ip_match:
                ip = ip_match.group(1)
        if not ip:
            continue
        # Извлекаем RTT в мс (<1 ms, 5 ms, 1.234 ms)
        rtts = []
        for x in re.findall(r"(?:<)?([\d.]+)\s*(?:ms|мс)", line, re.IGNORECASE):
            try:
                rtts.append(float(x))
            except ValueError:
                pass
        hops.append(TracerouteHop(hop=hop_num, ip=ip, hostname=hostname, rtt_ms=rtts))

    return hops
