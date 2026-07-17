# ui/decoder_panel.py

from typing import List

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtGui import QColor, QBrush
from data.logic_sample_buffer import LogicSampleBuffer
from decoder.decode_annotation import DecodeAnnotation
from decoder.spi_decoder import SPIDecoder, SPIConfig
from decoder.i2c_decoder import I2CDecoder, I2CConfig
from decoder.uart_decoder import UARTDecoder, UARTConfig
from fileio.csv_exporter import export_annotations_csv
from config.app_config import CHANNEL_NAMES


class DecoderPanel(QWidget):
    """
    Panel chọn decoder, chọn channel mapping và hiển thị bảng kết quả decode.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.buffer: LogicSampleBuffer | None = None
        self.annotations: List[DecodeAnnotation] = []

        layout = QVBoxLayout(self)

        # ===== Top bar =====
        top_bar = QHBoxLayout()

        self.label = QLabel("Protocol Decoder:")
        self.decoder_combo = QComboBox()
        self.decoder_combo.addItems(["SPI", "I2C", "UART"])

        self.button_decode = QPushButton("Decode")
        self.button_clear = QPushButton("Clear")
        self.button_export = QPushButton("Export CSV")
        self.button_export.setEnabled(False)

        top_bar.addWidget(self.label)
        top_bar.addWidget(self.decoder_combo)
        top_bar.addStretch()
        top_bar.addWidget(self.button_decode)
        top_bar.addWidget(self.button_export)
        top_bar.addWidget(self.button_clear)

        layout.addLayout(top_bar)

        # ===== Config group =====
        self.config_group = QGroupBox("Decoder Channel Mapping")
        config_layout = QGridLayout(self.config_group)

        # SPI channel combo boxes
        self.spi_cs_combo = self._make_channel_combo(default_index=0)  # CH1
        self.spi_mosi_combo = self._make_channel_combo(default_index=1)  # CH2
        self.spi_miso_combo = self._make_channel_combo(default_index=2)  # CH3
        self.spi_sck_combo = self._make_channel_combo(default_index=3)  # CH4

        config_layout.addWidget(QLabel("SPI CS:"), 0, 0)
        config_layout.addWidget(self.spi_cs_combo, 0, 1)

        config_layout.addWidget(QLabel("SPI MOSI:"), 0, 2)
        config_layout.addWidget(self.spi_mosi_combo, 0, 3)

        config_layout.addWidget(QLabel("SPI MISO:"), 0, 4)
        config_layout.addWidget(self.spi_miso_combo, 0, 5)

        config_layout.addWidget(QLabel("SPI SCK:"), 0, 6)
        config_layout.addWidget(self.spi_sck_combo, 0, 7)

        # I2C combo boxes, dùng cho milestone sau
        self.i2c_sda_combo = self._make_channel_combo(default_index=4)  # CH5
        self.i2c_scl_combo = self._make_channel_combo(default_index=5)  # CH6

        config_layout.addWidget(QLabel("I2C SDA:"), 1, 0)
        config_layout.addWidget(self.i2c_sda_combo, 1, 1)

        config_layout.addWidget(QLabel("I2C SCL:"), 1, 2)
        config_layout.addWidget(self.i2c_scl_combo, 1, 3)

        # UART combo box, dùng cho milestone sau
        self.uart_rx_combo = self._make_channel_combo(default_index=6)  # CH7
        self.uart_baud_combo = QComboBox()
        self.uart_baud_combo.addItems(
            [
                "1200",
                "2400",
                "4800",
                "9600",
                "19200",
                "38400",
                "57600",
                "115200",
            ]
        )
        self.uart_baud_combo.setCurrentText("9600")

        self.uart_data_bits_combo = QComboBox()
        self.uart_data_bits_combo.addItems(
            [
                "5",
                "6",
                "7",
                "8",
            ]
        )
        self.uart_data_bits_combo.setCurrentText("8")

        self.uart_parity_combo = QComboBox()
        self.uart_parity_combo.addItems(
            [
                "None",
                "Even",
                "Odd",
            ]
        )
        self.uart_parity_combo.setCurrentText("None")

        self.uart_stop_bits_combo = QComboBox()
        self.uart_stop_bits_combo.addItems(
            [
                "1",
                "2",
            ]
        )
        self.uart_stop_bits_combo.setCurrentText("1")
        config_layout.addWidget(QLabel("UART Baud:"), 2, 0)
        config_layout.addWidget(self.uart_baud_combo, 2, 1)

        config_layout.addWidget(QLabel("Data bits:"), 2, 2)
        config_layout.addWidget(self.uart_data_bits_combo, 2, 3)

        config_layout.addWidget(QLabel("Parity:"), 2, 4)
        config_layout.addWidget(self.uart_parity_combo, 2, 5)

        config_layout.addWidget(QLabel("Stop bits:"), 2, 6)
        config_layout.addWidget(self.uart_stop_bits_combo, 2, 7)

        config_layout.addWidget(QLabel("UART RX:"), 1, 4)
        config_layout.addWidget(self.uart_rx_combo, 1, 5)

        layout.addWidget(self.config_group)

        self.hint_label = QLabel(
            "Default mapping: SPI CS=CH1, MOSI=CH2, MISO=CH3, SCK=CH4 | "
            "I2C SDA=CH5, SCL=CH6 | UART RX=CH7"
        )
        layout.addWidget(self.hint_label)

        # ===== Result table =====
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Time (us)", "End (us)", "Protocol", "Type", "Value", "Text", "Status"]
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        self.button_decode.clicked.connect(self.decode_selected)
        self.button_clear.clicked.connect(self.clear_results)
        self.button_export.clicked.connect(self.export_results)

    def _make_channel_combo(self, default_index: int) -> QComboBox:
        combo = QComboBox()

        for name in CHANNEL_NAMES:
            combo.addItem(name)

        combo.setCurrentIndex(default_index)
        return combo

    def set_buffer(self, buffer: LogicSampleBuffer):
        self.buffer = buffer
        self.clear_results()

    def decode_selected(self):
        if self.buffer is None:
            self._set_annotations(
                [
                    DecodeAnnotation(
                        start_sample=0,
                        end_sample=0,
                        protocol="APP",
                        type="WARNING",
                        value="",
                        text="No capture buffer. Click Start Demo first.",
                        error=True,
                        error_reason="No buffer",
                    )
                ]
            )
            return

        decoder_name = self.decoder_combo.currentText()

        if decoder_name == "SPI":
            decoder = SPIDecoder()

            config = SPIConfig(
                cs_channel=self.spi_cs_combo.currentIndex(),
                mosi_channel=self.spi_mosi_combo.currentIndex(),
                miso_channel=self.spi_miso_combo.currentIndex(),
                sck_channel=self.spi_sck_combo.currentIndex(),
                mode=0,
                bit_order="MSB",
                word_size=8,
                cs_active_low=True,
            )

            annotations = decoder.decode(self.buffer, config)

        elif decoder_name == "I2C":
            decoder = I2CDecoder()

            config = I2CConfig(
                sda_channel=self.i2c_sda_combo.currentIndex(),
                scl_channel=self.i2c_scl_combo.currentIndex(),
            )

            annotations = decoder.decode(
                self.buffer,
                config,
            )

            # Không để bảng trống khiến người dùng tưởng nút Decode hỏng.
            if not annotations:
                annotations = [
                    DecodeAnnotation(
                        start_sample=0,
                        end_sample=0,
                        protocol="I2C",
                        type="WARNING",
                        value="",
                        text=("No I2C frame found. " "Check SDA/SCL mapping and capture data."),
                        error=True,
                        error_reason="No START condition detected",
                    )
                ]

        elif decoder_name == "UART":
            decoder = UARTDecoder()

            config = UARTConfig(
                rx_channel=self.uart_rx_combo.currentIndex(),
                baudrate=int(self.uart_baud_combo.currentText()),
                data_bits=int(self.uart_data_bits_combo.currentText()),
                parity=self.uart_parity_combo.currentText().upper(),
                stop_bits=int(self.uart_stop_bits_combo.currentText()),
                idle_high=True,
            )

            annotations = decoder.decode(
                self.buffer,
                config,
            )

            if not annotations:
                annotations = [
                    DecodeAnnotation(
                        start_sample=0,
                        end_sample=0,
                        protocol="UART",
                        type="WARNING",
                        value="",
                        text=(
                            "No UART frame found. Check RX channel, "
                            "baudrate, data bits, parity and stop bits."
                        ),
                        error=True,
                        error_reason="No UART start bit detected",
                    )
                ]
            # Đưa kết quả decoder lên bảng giao diện
        self._set_annotations(annotations)

    def export_results(self):
        if self.buffer is None:
            QMessageBox.warning(
                self,
                "Export CSV",
                "No capture buffer is available.",
            )
            return

        if not self.annotations:
            QMessageBox.information(
                self,
                "Export CSV",
                "There are no decoded results to export.",
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export decoded annotations",
            "decoded_annotations.csv",
            "CSV files (*.csv)",
        )

        # Người dùng bấm Cancel.
        if not file_path:
            return

        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        try:
            row_count = export_annotations_csv(
                file_path=file_path,
                annotations=self.annotations,
                sample_rate_hz=self.buffer.sample_rate_hz,
            )

        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Export failed",
                str(error),
            )
            return

        QMessageBox.information(
            self,
            "Export completed",
            f"Exported {row_count} decoded annotations.",
        )

    def clear_results(self):
        self.annotations = []
        self.table.setRowCount(0)
        self.button_export.setEnabled(False)

    def _set_annotations(
        self,
        annotations: List[DecodeAnnotation],
    ):
        self.annotations = annotations
        self.button_export.setEnabled(bool(annotations))
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(len(self.annotations))

        sample_rate = self.buffer.sample_rate_hz if self.buffer is not None else 1

        for row, ann in enumerate(self.annotations):
            start_time = ann.start_time_us(sample_rate)
            end_time = ann.end_time_us(sample_rate)

            status = "ERROR" if ann.error else "OK"

            values = [
                f"{start_time:.1f}",
                f"{end_time:.1f}",
                ann.protocol,
                ann.type,
                ann.value,
                ann.text,
                status,
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)

                # Fix theme tối: ép chữ sáng để không bị "có row nhưng không thấy chữ"
                item.setForeground(QBrush(QColor(230, 230, 230)))

                if ann.error:
                    item.setBackground(QBrush(QColor(70, 35, 35)))
                else:
                    item.setBackground(QBrush(QColor(35, 55, 35)))

                self.table.setItem(row, col, item)

        self.table.resizeRowsToContents()
