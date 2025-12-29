import struct


class DNSHeader:
    """Класс для парсинга DNS заголовка"""

    def __init__(self, raw_data):
        try:
            (transaction_id, flags, questions, answer_rrs,
             authority_rrs, additional_rrs) = struct.unpack('!HHHHHH', raw_data[:12])

            # Параметры заголовка
            self.transaction_id = transaction_id
            self.flags = flags
            self.questions = questions
            self.answer_rrs = answer_rrs
            self.authority_rrs = authority_rrs
            self.additional_rrs = additional_rrs

            # Данные заголовка
            self.data = raw_data[12:]

        except Exception as e:
            raise Exception(f"Ошибка парсинга DNS заголовка: {e}")

    def is_response(self):
        """Проверка, является ли пакет ответом (QR бит)"""
        return bool(self.flags & 0x8000)

    def get_opcode(self):
        """Получение кода операции"""
        return (self.flags >> 11) & 0x0F

    def get_params(self):
        """Получение всех параметров"""
        return {
            'Transaction id': self.transaction_id,
            'Flags': self.flags,
            'Questions': self.questions,
            'Answer rrs': self.answer_rrs,
            'Authority rrs': self.authority_rrs,
            'Additional rrs': self.additional_rrs
        }
