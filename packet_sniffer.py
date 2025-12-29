import socket
import sys
from datetime import datetime
from utils import Protocol
from headers_parsers import IPHeader, TCPHeader, UDPHeader, DNSHeader


class PacketSniffer:
    """Класс анализатора траффика"""

    def __init__(self):
        self.host = "0.0.0.0"
        self.socket = None
        self.running = False
        self.parsed_packets = list()

    def start(self, host=None):
        """Запуск анализатора"""
        try:
            if host is not None:
                self.host = host
            # Получаем IP адрес интерфейса
            if self.host == "0.0.0.0":
                # Автоматически определяем локальный IP
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.connect(("8.8.8.8", 80))
                        self.host = s.getsockname()[0]
                except Exception:
                    self.host = "127.0.0.1"

            # Создаем raw socket
            if sys.platform == "win32":
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
                self.socket.bind((self.host, 0))

                # Включаем promiscuous mode
                try:
                    # SIO_RCVALL - получать все пакеты
                    SIO_RCVALL = getattr(socket, 'SIO_RCVALL', 0x98000001)
                    self.socket.ioctl(SIO_RCVALL, 1)
                except AttributeError:
                    pass

            else:
                # Для Linux
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
                self.socket.bind((self.host, 0))
                self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

            self.running = True

            # Запуск цикла анализатора
            self._start_sniffing()

        except PermissionError:
            raise PermissionError("Для запуска анализатора требуются права администратора")
        except Exception as e:
            raise Exception(f"Ошибка запуска анализатора: {e}")

    def stop(self):
        """Остановка анализатора"""
        self.running = False
        if self.socket:
            if sys.platform == "win32":
                try:
                    # Отключаем promiscuous mode
                    SIO_RCVALL = getattr(socket, 'SIO_RCVALL', 0x98000001)
                    self.socket.ioctl(SIO_RCVALL, 0)
                except Exception:
                    pass
            self.socket.close()

    def _start_sniffing(self):
        """Основной цикл захвата пакетов"""

        while self.running:
            try:
                # Читаем пакет
                raw_data = self.socket.recv(65535)

                # Парсим пакет
                packet = self._parse_packet(raw_data)
                self.parsed_packets.append(packet)

            except Exception:
                pass

    def _parse_packet(self, raw_data):
        """Парсинг захваченного пакета"""
        packet = dict()

        try:
            # Парсим IP заголовок
            ip_header = IPHeader(raw_data)

            packet['ip_header'] = ip_header.get_params()
            packet['timestamp'] = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            # Анализируем протокол транспортного уровня
            if ip_header.protocol == Protocol.TCP.value:
                packet['protocol'] = 'TCP'
                tcp_header = self._parse_tcp(ip_header.data)
                if tcp_header:
                    packet['protocol_header'] = tcp_header.get_params()

            elif ip_header.protocol == Protocol.UDP.value:
                packet['protocol'] = 'UPD'
                udp_header, dns_header = self._parse_udp(ip_header.data)
                if udp_header:
                    packet['protocol_header'] = udp_header.get_params()
                if dns_header:
                    packet['dns_header'] = dns_header.get_params()

            elif ip_header.protocol == Protocol.ICMP.value:
                packet['protocol'] = 'ICMP'
            else:
                packet['protocol'] = f"{ip_header.protocol}"

        except Exception as e:
            packet['error'] = f"Ошибка парсинга пакета: {e}"

        return packet

    def _parse_tcp(self, data):
        """Парсинг TCP пакета"""
        tcp_header = None

        try:
            tcp_header = TCPHeader(data)

        except Exception:
            pass

        return tcp_header

    def _parse_udp(self, data):
        """Парсинг UDP пакета"""
        udp_header = None
        dns_header = None

        try:
            udp_header = UDPHeader(data)

            # Проверяем DNS пакеты
            if (udp_header.source_port == Protocol.DNS.value
                    or udp_header.destination_port == Protocol.DNS.value):
                dns_header = self._parse_dns(udp_header.data)

        except Exception:
            pass

        return udp_header, dns_header

    def _parse_dns(self, data):
        """Парсинг DNS пакета"""
        dns_header = None

        try:
            dns_header = DNSHeader(data)

        except Exception:
            pass

        return dns_header

    def get_new_packets(self):
        """Получение новых проанализированных пакетов"""
        new_packets = self.parsed_packets.copy()
        self.parsed_packets.clear()
        return new_packets
