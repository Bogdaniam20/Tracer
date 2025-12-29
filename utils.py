import socket
from enum import Enum


class Protocol(Enum):
    """Коды протоколов"""
    ICMP = 1
    TCP = 6
    UDP = 17
    DNS = 53


def get_network_interfaces():
    """Получает список сетевых интерфейсов"""

    # Добавление стандартных интерфейсов
    interfaces = ["0.0.0.0", "127.0.0.1"]

    # Пытаемся получить реальные IP адреса
    try:
        hostname = socket.gethostname()
        local_ips = socket.gethostbyname_ex(hostname)[2]
        for ip in local_ips:
            interfaces.append(ip)
    except Exception:
        pass

    return interfaces
