import struct


class UDPHeader:
    """Класс для парсинга UDP заголовка"""

    def __init__(self, raw_data):
        try:
            (src_port, dest_port,
             length, checksum) = struct.unpack('!HHHH', raw_data[:8])

            # Параметры заголовка
            self.source_port = src_port
            self.destination_port = dest_port
            self.length = length
            self.checksum = checksum

            # Данные заголовка
            self.data = raw_data[8:self.length]

        except Exception as e:
            raise Exception(f"Ошибка парсинга UPD заголовка: {e}")

    def get_params(self):
        """Получение всех параметров"""
        return {
            'Source port': self.source_port,
            'Destination port': self.destination_port,
            'Header length': self.length,
            'Checksum': self.checksum,
        }
