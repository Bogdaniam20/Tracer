import struct


class TCPHeader:
    """Класс для парсинга TCP заголовка"""

    def __init__(self, raw_data):
        try:
            # Распаковка TCP заголовка (минимум 20 байт)
            (src_port, dest_port, sequence,
             acknowledgment, offset_reserved_flags,
             window_size, checksum,
             urgent_pointer) = struct.unpack('!HHLLHHHH', raw_data[:20])

            # Параметры заголовка
            self.source_port = src_port
            self.destination_port = dest_port
            self.sequence_number = sequence
            self.acknowledgment_number = acknowledgment

            # Длина заголовка (первые 4 бита умножаем на 4)
            self.header_length = (offset_reserved_flags >> 12) * 4

            # Флаги (последние 6 бит)
            self.flags = offset_reserved_flags & 0x3F

            self.window_size = window_size
            self.checksum = checksum
            self.urgent_pointer = urgent_pointer

            # Данные после заголовка
            self.data = raw_data[self.header_length:]

        except Exception as e:
            raise Exception(f"Ошибка парсинга TCP заголовка: {e}")

    def get_flags_string(self):
        """Возвращение строкового представление TCP флагов"""
        flags = []
        if self.flags & 0x01:
            flags.append("FIN")
        if self.flags & 0x02:
            flags.append("SYN")
        if self.flags & 0x04:
            flags.append("RST")
        if self.flags & 0x08:
            flags.append("PSH")
        if self.flags & 0x10:
            flags.append("ACK")
        if self.flags & 0x20:
            flags.append("URG")
        return ' '.join(flags) if flags else None

    def get_params(self):
        """Получение всех параметров"""
        return {
            'Source port': self.source_port,
            'Destination port': self.destination_port,
            'Sequence number': self.sequence_number,
            'Acknowledgment number': self.acknowledgment_number,
            'Header length': self.header_length,
            'Flags': self.get_flags_string(),
            'Windows size': self.window_size,
            'Checksum': self.checksum,
        }
