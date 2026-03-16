import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.models import PortInfo
from app.protocols import scan_port, scan_ports, traceroute, COMMON_PORTS


@pytest.mark.asyncio
async def test_scan_port_open_returns_port_info():
    """Открытый порт возвращает PortInfo с state=open."""
    writer = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    with patch("app.protocols.asyncio.open_connection", AsyncMock(return_value=(None, writer))):
        result = await scan_port("127.0.0.1", 80, timeout=1.0)

    assert result is not None
    assert result.port == 80
    assert result.service == "HTTP"
    assert result.state == "open"


@pytest.mark.asyncio
async def test_scan_port_timeout_returns_none():
    """Таймаут соединения возвращает None."""
    with patch("app.protocols.asyncio.open_connection", AsyncMock(side_effect=asyncio.TimeoutError)):
        result = await scan_port("127.0.0.1", 80, timeout=0.5)
    assert result is None


@pytest.mark.asyncio
async def test_scan_port_connection_refused_returns_none():
    """ConnectionRefusedError возвращает None."""
    with patch("app.protocols.asyncio.open_connection", AsyncMock(side_effect=ConnectionRefusedError)):
        result = await scan_port("127.0.0.1", 80)
    assert result is None


@pytest.mark.asyncio
async def test_scan_port_os_error_returns_none():
    """OSError возвращает None."""
    with patch("app.protocols.asyncio.open_connection", AsyncMock(side_effect=OSError("Network unreachable"))):
        result = await scan_port("192.0.2.1", 80)
    assert result is None


@pytest.mark.asyncio
async def test_scan_port_unknown_port_returns_unknown_service():
    """Неизвестный порт получает service='unknown'."""
    writer = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    with patch("app.protocols.asyncio.open_connection", AsyncMock(return_value=(None, writer))):
        result = await scan_port("127.0.0.1", 9999, timeout=1.0)

    assert result.service == "unknown"


@pytest.mark.asyncio
async def test_scan_ports_returns_only_open_ports():
    """scan_ports возвращает только открытые порты."""
    writer = MagicMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()

    async def mock_conn(host, port):
        if port == 80:
            return None, writer
        raise ConnectionRefusedError()

    with patch("app.protocols.asyncio.open_connection", side_effect=mock_conn):
        results = await scan_ports("127.0.0.1", ports=[80, 443, 22])

    assert len(results) == 1
    assert results[0].port == 80


def test_common_ports_have_service_names():
    """Все порты в COMMON_PORTS имеют непустое имя сервиса."""
    for port, service in COMMON_PORTS.items():
        assert isinstance(service, str), f"Port {port}"
        assert len(service) > 0, f"Port {port}"


@pytest.mark.asyncio
async def test_traceroute_parses_windows_output():
    """traceroute парсит вывод Windows traceroute."""
    fake_output = """
Tracing route to 8.8.8.8 over a maximum of 30 hops

  1    <1 ms    <1 ms    <1 ms  192.168.1.1
  2    10 ms    12 ms    11 ms  router.isp.net [10.0.0.1]
  3    25 ms    24 ms    26 ms  93.184.216.34
"""
    with patch("app.protocols.subprocess.run") as mock_run, patch(
        "app.protocols._resolve_hop_hostnames", new=AsyncMock()
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout=fake_output, stderr="")
        result = await traceroute("8.8.8.8", max_hops=5, timeout=5)
    assert result.error == ""
    assert len(result.hops) >= 2
    assert result.hops[0].ip == "192.168.1.1"
    assert result.hops[0].hostname == ""
    assert result.hops[1].ip == "10.0.0.1"
    assert result.hops[1].hostname == "router.isp.net"
    assert result.hops[0].hop == 1
