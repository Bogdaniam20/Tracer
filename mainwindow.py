from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QMainWindow, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import threading
import time
from ui_mainwindow import Ui_MainWindow
from packet_sniffer import PacketSniffer
from utils import get_network_interfaces


class SnifferSignals(QObject):
    """Сигналы для коммуникации между потоками"""
    error_occurred = pyqtSignal(str)


class MainWindow(QMainWindow):
    """Класс главного окна"""

    def __init__(self):
        super(MainWindow, self).__init__()

        # Загрузка ui
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Модель отображения пакетов
        self.packets_model = QStandardItemModel()
        self.packets_model.setHorizontalHeaderLabels(['Пакеты'])
        self.packets_count = 0

        # Сигналы для обработки ошибок
        self.signals = SnifferSignals()
        self.signals.error_occurred.connect(self.show_error)

        # Загрузка сетевых интерфейсов
        interfaces = get_network_interfaces()
        self.ui.interfacesBox.addItems(interfaces)

        # Управление анализатором
        self.packet_sniffer = PacketSniffer()
        self.ui.controlButton.clicked.connect(self.control_sniffer)
        self.is_sniffer_running = False

    def control_sniffer(self):
        """Контроль анализатора сетевого траффика"""
        if not self.is_sniffer_running:
            # Запуск потока анализатора траффика
            self.sniffer_run()
        else:
            # Остановка анализатора траффика
            self.sniffer_stop()

    def sniffer_run(self):
        """Работа и получение данных анализатора траффика"""
        # Запуск потока анализатора траффика
        threading.Thread(target=self.sniffer_start_thread,
                         daemon=True).start()

        self.ui.controlButton.setText('Стоп')
        self.is_sniffer_running = True

        # Запуск потока получения данных анализатора траффика
        threading.Thread(target=self.sniffer_listen,
                         daemon=True).start()

    def sniffer_start_thread(self):
        """Запуск и контроль потока анализатора траффика"""
        try:
            self.packet_sniffer.start(self.ui.interfacesBox.currentText())
        except Exception as e:
            self.sniffer_stop()
            self.signals.error_occurred.emit(str(e))

    def sniffer_listen(self):
        """Получение данных из анализатора траффика"""
        try:
            while self.is_sniffer_running:
                packets = self.packet_sniffer.get_new_packets()

                if packets:
                    # Добавление информации о новых пакетах
                    for packet in packets:
                        self.add_packet(packet)

                # Небольшая задержка для снижения нагрузки
                time.sleep(1)

        except Exception as e:
            self.sniffer_stop()
            self.signals.error_occurred.emit(str(e))

    def sniffer_stop(self):
        """Остановка анализатора траффика"""
        self.packet_sniffer.stop()
        self.ui.controlButton.setText('Запуск')
        self.is_sniffer_running = False

    def add_packet(self, packet):
        """Добавление нового пакета"""
        self.packets_count += 1

        ip_header = packet['ip_header']
        ip = f"{ip_header['Source']} - {ip_header['Destination']}"
        root_item = QStandardItem(
            f"{self.packets_count:<10}{packet["timestamp"]:<20}"
            f"{ip:<40}"
            f"{packet['protocol']}")

        # Параметры IP
        ip_item = QStandardItem("IP")
        for param, value in ip_header.items():
            ip_item.appendRow(QStandardItem(f"{param}: {value}"))
        root_item.appendRow(ip_item)

        # Параметры протокола
        protocol_item = QStandardItem(f"{packet["protocol"]}")
        protocol_header = packet["protocol_header"]
        if protocol_header:
            for param, value in protocol_header.items():
                protocol_item.appendRow(QStandardItem(f"{param}: {value}"))
        root_item.appendRow(protocol_item)

        # Параметры DNS, если есть
        dns_header = packet.get("dns_header", None)
        if dns_header:
            dns_item = QStandardItem("DNS")
            for param, value in dns_header.items():
                dns_item.appendRow(QStandardItem(f"{param}: {value}"))
            root_item.appendRow(dns_item)

        self.packets_model.appendRow(root_item)
        self.ui.packetsTreeView.setModel(self.packets_model)

    def closeEvent(self, a0):
        """Остановка анализатора при закрытии, если он ещё работает"""
        if self.is_sniffer_running:
            self.sniffer_stop()
        return super().closeEvent(a0)

    @pyqtSlot(str)
    def show_error(self, error_message):
        """Показ ошибки"""
        QMessageBox.warning(self, 'Ошибка!', error_message)
