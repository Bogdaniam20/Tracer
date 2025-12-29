import struct


class IPHeader:
    """Класс для парсинга IP заголовка"""

    def __init__(self, raw_data):
        try:
            # Распаковка первых 20 байт (минимальный IP заголовок)
            (version_header_len, dscp, total_length,
             identification, flags_offset,
             time_to_live, protocol, checksum,
             src_ip, dest_ip) = struct.unpack('!BBHHHBBH4s4s', raw_data[:20])

            # Версия IP (первые 4 бита)
            self.version = version_header_len >> 4

            # Длина заголовка (последние 4 бита умножаем на 4)
            self.header_length = (version_header_len & 0x0F) * 4

            # Остальные параметры заголовка
            self.differentiated_services = dscp
            self.total_length = total_length
            self.identification = identification
            self.flags = flags_offset >> 13
            self.fragment_offset = flags_offset & 0x1FFF
            self.time_to_live = time_to_live
            self.protocol = protocol
            self.checksum = checksum
            self.source_ip = self.ip_to_string(src_ip)
            self.destination_ip = self.ip_to_string(dest_ip)

            # Данные после заголовка
            self.data = raw_data[self.header_length:self.total_length]

        except Exception as e:
            raise Exception(f"Ошибка парсинга IP заголовка: {e}")

    @staticmethod
    def ip_to_string(ip_bytes):
        """Конвертирование IP адреса из байтов в строку"""
        return '.'.join(map(str, ip_bytes))

    def get_params(self):
        """Получение всех параметров"""
        return {
            'Version': self.version,
            'Source': self.source_ip,
            'Destination': self.destination_ip,
            'Header length': self.header_length,
            'Differentiated Services': self.differentiated_services,
            'Total length': self.total_length,
            'Identification': self.identification,
            'Flags': self.flags,
            'Fragment offset': self.fragment_offset,
            'Time to live': self.time_to_live,
            'Protocol': self.protocol,
            'Checksum': self.checksum
        }
