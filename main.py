# main.py

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from data.logic_sample_buffer import LogicSampleBuffer
from driver.demo_driver import DemoDriver
from driver.sigrok_cli_driver import (
    SigrokCliDriver,
    SigrokCliError,
)
from fileio.la_session import (
    load_la_session,
    save_la_session,
)
from ui.decoder_panel import DecoderPanel
from ui.waveform_view import WaveformView

SIGROK_CLI_PATH = (
    r"E:\WORK\pach_kha\ET\Embedded_Systems_and_Interfaces" r"\sigrok_cli\sigrok-cli\sigrok-cli.exe"
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Logic Analyzer App - Milestone 8 Hardware Capture")
        self.resize(1350, 820)

        self.current_buffer: LogicSampleBuffer | None = None
        self.current_source_name = "None"

        root = QWidget()
        root_layout = QVBoxLayout(root)

        # ==========================================================
        # Capture controls
        # ==========================================================
        capture_bar = QHBoxLayout()

        self.title = QLabel("Logic Analyzer App")

        self.source_label = QLabel("Source:")
        self.source_combo = QComboBox()
        self.source_combo.addItem("Demo", "demo")
        self.source_combo.addItem(
            "Saleae Clone",
            "saleae",
        )
        self.source_combo.addItem(
            "Pico 2 - Pending",
            "pico",
        )

        self.sample_rate_label = QLabel("Sample rate:")
        self.sample_rate_combo = QComboBox()

        self.sample_rate_combo.addItem(
            "250 kHz",
            250_000,
        )
        self.sample_rate_combo.addItem(
            "500 kHz",
            500_000,
        )
        self.sample_rate_combo.addItem(
            "1 MHz",
            1_000_000,
        )
        self.sample_rate_combo.addItem(
            "2 MHz",
            2_000_000,
        )
        self.sample_rate_combo.addItem(
            "4 MHz",
            4_000_000,
        )
        self.sample_rate_combo.addItem(
            "8 MHz",
            8_000_000,
        )

        # Mặc định chọn 1 MHz.
        self.sample_rate_combo.setCurrentIndex(2)

        self.duration_label = QLabel("Duration:")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 2000)
        self.duration_spin.setValue(200)
        self.duration_spin.setSingleStep(50)
        self.duration_spin.setSuffix(" ms")

        self.button_start_capture = QPushButton("Start Capture")
        self.button_save_session = QPushButton("Save Session")
        self.button_open_session = QPushButton("Open Session")
        self.button_fit = QPushButton("Fit View")

        capture_bar.addWidget(self.title)
        capture_bar.addStretch()

        capture_bar.addWidget(self.source_label)
        capture_bar.addWidget(self.source_combo)

        capture_bar.addWidget(self.sample_rate_label)
        capture_bar.addWidget(self.sample_rate_combo)

        capture_bar.addWidget(self.duration_label)
        capture_bar.addWidget(self.duration_spin)

        capture_bar.addWidget(self.button_start_capture)
        capture_bar.addWidget(self.button_save_session)
        capture_bar.addWidget(self.button_open_session)
        capture_bar.addWidget(self.button_fit)

        root_layout.addLayout(capture_bar)

        # ==========================================================
        # Main content
        # ==========================================================
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        self.waveform_view = WaveformView()

        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.output = QTextEdit()
        self.output.setReadOnly(True)

        self.decoder_panel = DecoderPanel()

        bottom_splitter.addWidget(self.output)
        bottom_splitter.addWidget(self.decoder_panel)
        bottom_splitter.setSizes([430, 820])

        main_splitter.addWidget(self.waveform_view)
        main_splitter.addWidget(bottom_splitter)
        main_splitter.setSizes([570, 230])

        root_layout.addWidget(main_splitter)

        self.setCentralWidget(root)

        # ==========================================================
        # Signals
        # ==========================================================
        self.button_start_capture.clicked.connect(self.run_capture)
        self.button_save_session.clicked.connect(self.save_session)
        self.button_open_session.clicked.connect(self.open_session)
        self.button_fit.clicked.connect(self.fit_view)

        self.statusBar().showMessage("Ready")

        self.show_welcome_message()

    def show_welcome_message(self):
        lines = [
            "Logic Analyzer App",
            "",
            "Available capture sources:",
            "- Demo: generated SPI, I2C and UART signals",
            "- Saleae Clone: real capture through sigrok-cli",
            "- Pico 2: MCU core of the final product, pending hardware",
            "",
            "Recommended Saleae UART test:",
            "- Sample rate: 1 MHz",
            "- Duration: 200 ms",
            "- Arduino D7 -> Saleae CH7",
            "- Arduino GND -> Saleae GND",
            "- UART decoder: CH7, 9600 baud, 8N1",
        ]

        self.output.setPlainText("\n".join(lines))

    def run_capture(self):
        """
        Chọn nguồn capture và tạo LogicSampleBuffer.
        """

        source = self.source_combo.currentData()

        sample_rate_hz = int(self.sample_rate_combo.currentData())

        duration_ms = self.duration_spin.value()

        if source == "pico":
            QMessageBox.information(
                self,
                "Pico 2",
                (
                    "Pico 2 integration is prepared as the "
                    "final hardware source, but its firmware "
                    "protocol must be tested with the board."
                ),
            )
            return

        self.button_start_capture.setEnabled(False)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        self.statusBar().showMessage("Capturing...")

        QApplication.processEvents()

        try:
            if source == "demo":
                buffer = self.capture_demo(
                    sample_rate_hz=sample_rate_hz,
                    duration_ms=duration_ms,
                )

                source_name = "Demo"

            elif source == "saleae":
                buffer = self.capture_saleae(
                    sample_rate_hz=sample_rate_hz,
                    duration_ms=duration_ms,
                )

                source_name = "Saleae Clone"

            else:
                raise ValueError(f"Unsupported capture source: {source}")

        except (
            OSError,
            ValueError,
            SigrokCliError,
        ) as error:
            QMessageBox.critical(
                self,
                "Capture failed",
                str(error),
            )

            self.statusBar().showMessage("Capture failed")
            return

        finally:
            QApplication.restoreOverrideCursor()
            self.button_start_capture.setEnabled(True)

        self.load_capture_buffer(
            buffer=buffer,
            source_name=source_name,
        )

        self.statusBar().showMessage(
            (f"Capture completed: " f"{buffer.sample_count()} samples"),
            5000,
        )

    def capture_demo(
        self,
        sample_rate_hz: int,
        duration_ms: int,
    ) -> LogicSampleBuffer:
        """
        Sinh tín hiệu demo bằng phần mềm.
        """

        driver = DemoDriver(sample_rate_hz=sample_rate_hz)

        return driver.capture(duration_ms=duration_ms)

    def capture_saleae(
        self,
        sample_rate_hz: int,
        duration_ms: int,
    ) -> LogicSampleBuffer:
        """
        Thu tín hiệu thật từ Saleae clone.
        """

        driver = SigrokCliDriver(
            executable=SIGROK_CLI_PATH,
            hardware_driver="fx2lafw",
        )

        return driver.capture(
            sample_rate_hz=sample_rate_hz,
            duration_ms=duration_ms,
        )

    def load_capture_buffer(
        self,
        buffer: LogicSampleBuffer,
        source_name: str,
    ):
        """
        Đưa buffer vào waveform và decoder panel.
        """

        self.current_buffer = buffer
        self.current_source_name = source_name

        self.waveform_view.set_buffer(buffer)

        # Buffer mới nên xóa annotation của capture cũ.
        self.decoder_panel.set_buffer(buffer)

        self.fit_view()

        lines = [
            "Capture completed successfully.",
            f"Source: {source_name}",
            f"Sample rate: {buffer.sample_rate_hz} Hz",
            f"Sample count: {buffer.sample_count()}",
            ("Duration: " f"{buffer.duration_seconds() * 1000:.3f} ms"),
            "",
        ]

        if source_name == "Demo":
            lines.extend(
                [
                    "Demo channel mapping:",
                    "CH1 = SPI CS",
                    "CH2 = SPI MOSI",
                    "CH3 = SPI MISO",
                    "CH4 = SPI SCK",
                    "CH5 = I2C SDA",
                    "CH6 = I2C SCL",
                    "CH7 = UART TX",
                    "CH8 = unused",
                    "",
                    "Expected UART: HELLO",
                    "UART configuration: CH7, 9600 baud, 8N1",
                ]
            )

        elif source_name == "Saleae Clone":
            lines.extend(
                [
                    "Saleae channel mapping:",
                    "sigrok D0 = project CH1",
                    "sigrok D1 = project CH2",
                    "...",
                    "sigrok D6 = project CH7",
                    "sigrok D7 = project CH8",
                    "",
                    "For the current Arduino UART test:",
                    "Arduino D7 -> Saleae CH7",
                    "Arduino GND -> Saleae GND",
                    "UART configuration: CH7, 9600 baud, 8N1",
                ]
            )

        self.output.setPlainText("\n".join(lines))

    def save_session(self):
        """
        Lưu raw samples, metadata và annotation vào .la.
        """

        if self.current_buffer is None:
            QMessageBox.warning(
                self,
                "Save Session",
                ("No capture data is available. " "Start a capture first."),
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save logic analyzer session",
            "capture.la",
            "Logic Analyzer Session (*.la)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".la"):
            file_path += ".la"

        try:
            save_la_session(
                file_path=file_path,
                buffer=self.current_buffer,
                annotations=self.decoder_panel.annotations,
            )

        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Save failed",
                str(error),
            )
            return

        self.statusBar().showMessage(
            "Session saved successfully",
            5000,
        )

        QMessageBox.information(
            self,
            "Save completed",
            ("The logic analyzer session " "was saved successfully."),
        )

    def open_session(self):
        """
        Mở file .la và khôi phục capture.
        """

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open logic analyzer session",
            "",
            "Logic Analyzer Session (*.la)",
        )

        if not file_path:
            return

        try:
            buffer, annotations = load_la_session(file_path)

        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Open failed",
                str(error),
            )
            return

        self.current_buffer = buffer
        self.current_source_name = "Session File"

        self.waveform_view.set_buffer(buffer)

        # set_buffer() xóa annotation cũ.
        self.decoder_panel.set_buffer(buffer)

        # Vì vậy annotation phải được nạp sau.
        self.decoder_panel.set_annotations(annotations)

        self.select_sample_rate(buffer.sample_rate_hz)

        self.fit_view()

        lines = [
            "Session loaded successfully.",
            f"File: {file_path}",
            f"Sample rate: {buffer.sample_rate_hz} Hz",
            f"Sample count: {buffer.sample_count()}",
            ("Duration: " f"{buffer.duration_seconds() * 1000:.3f} ms"),
            f"Annotations: {len(annotations)}",
            "",
            ("The raw samples can still be decoded again " "with another protocol configuration."),
        ]

        self.output.setPlainText("\n".join(lines))

        self.statusBar().showMessage(
            "Session loaded successfully",
            5000,
        )

    def select_sample_rate(
        self,
        sample_rate_hz: int,
    ):
        """
        Chọn sample rate tương ứng khi mở session.
        """

        for index in range(self.sample_rate_combo.count()):
            value = self.sample_rate_combo.itemData(index)

            if value == sample_rate_hz:
                self.sample_rate_combo.setCurrentIndex(index)
                return

        # Nếu session dùng rate chưa có trong danh sách.
        self.sample_rate_combo.addItem(
            f"{sample_rate_hz} Hz",
            sample_rate_hz,
        )

        self.sample_rate_combo.setCurrentIndex(self.sample_rate_combo.count() - 1)

    def fit_view(self):
        """
        Zoom để hiển thị toàn bộ capture.
        """

        if self.current_buffer is None:
            return

        visible_width = max(
            1,
            (self.waveform_view.width() - self.waveform_view.left_margin - 20),
        )

        self.waveform_view.viewport_start_sample = 0

        self.waveform_view.samples_per_pixel = max(
            1.0,
            (self.current_buffer.sample_count() / visible_width),
        )

        self.waveform_view.update()


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
