import sys

from PyQt6.QtCore import QSettings, Qt
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

from config.runtime_config import resolve_sigrok_cli_path
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
from trigger.trigger_detector import find_trigger_sample
from ui.decoder_panel import DecoderPanel
from ui.waveform_view import WaveformView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Logic Analyzer App")
        self.resize(1450, 900)

        self.current_buffer: LogicSampleBuffer | None = None
        self.current_source_name = "None"
        self.settings = QSettings("EmbeddedSystemsLab", "LogicAnalyzerApp")

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
        self.source_combo.addItem("Saleae Clone", "saleae")
        self.source_combo.addItem("Pico 2 Product MCU", "pico")

        self.sample_rate_label = QLabel("Sample rate:")
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItem("250 kHz", 250_000)
        self.sample_rate_combo.addItem("500 kHz", 500_000)
        self.sample_rate_combo.addItem("1 MHz", 1_000_000)
        self.sample_rate_combo.addItem("2 MHz", 2_000_000)
        self.sample_rate_combo.addItem("4 MHz", 4_000_000)
        self.sample_rate_combo.addItem("8 MHz", 8_000_000)
        self.sample_rate_combo.setCurrentIndex(2)

        self.duration_label = QLabel("Duration:")
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 2000)
        self.duration_spin.setValue(200)
        self.duration_spin.setSingleStep(50)
        self.duration_spin.setSuffix(" ms")

        self.trigger_label = QLabel("Trigger:")
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItem("Disabled", None)
        self.trigger_combo.addItem("Rising edge", "rising")
        self.trigger_combo.addItem("Falling edge", "falling")
        self.trigger_combo.addItem("Either edge", "either")

        self.trigger_channel_label = QLabel("Channel:")
        self.trigger_channel_combo = QComboBox()
        for channel_index in range(8):
            self.trigger_channel_combo.addItem(
                f"CH{channel_index + 1}",
                channel_index,
            )

        self.pretrigger_label = QLabel("Pre-trigger:")
        self.pretrigger_spin = QSpinBox()
        self.pretrigger_spin.setRange(0, 90)
        self.pretrigger_spin.setValue(30)
        self.pretrigger_spin.setSingleStep(10)
        self.pretrigger_spin.setSuffix(" %")

        self.button_start_capture = QPushButton("Start Capture")
        self.button_save_session = QPushButton("Save Session")
        self.button_open_session = QPushButton("Open Session")
        self.button_fit = QPushButton("Fit View")
        self.button_clear_capture = QPushButton("Clear Capture")

        capture_bar.addWidget(self.title)
        capture_bar.addStretch()
        capture_bar.addWidget(self.source_label)
        capture_bar.addWidget(self.source_combo)
        capture_bar.addWidget(self.sample_rate_label)
        capture_bar.addWidget(self.sample_rate_combo)
        capture_bar.addWidget(self.duration_label)
        capture_bar.addWidget(self.duration_spin)
        capture_bar.addWidget(self.trigger_label)
        capture_bar.addWidget(self.trigger_combo)
        capture_bar.addWidget(self.trigger_channel_label)
        capture_bar.addWidget(self.trigger_channel_combo)
        capture_bar.addWidget(self.pretrigger_label)
        capture_bar.addWidget(self.pretrigger_spin)
        capture_bar.addWidget(self.button_start_capture)
        capture_bar.addWidget(self.button_save_session)
        capture_bar.addWidget(self.button_open_session)
        capture_bar.addWidget(self.button_fit)
        capture_bar.addWidget(self.button_clear_capture)

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
        self.button_clear_capture.clicked.connect(self.clear_capture)
        self.trigger_combo.currentIndexChanged.connect(self.update_trigger_controls)
        self.source_combo.currentIndexChanged.connect(self.update_source_controls)

        # M11: mỗi khi DecoderPanel đổi kết quả decode,
        # WaveformView nhận cùng danh sách annotation để vẽ overlay.
        self.decoder_panel.annotations_changed.connect(self.waveform_view.set_annotations)

        self.restore_settings()
        self.statusBar().showMessage("Ready")
        self.update_trigger_controls()
        self.update_source_controls()
        self.show_welcome_message()

    def update_source_controls(self):
        """Update UI hints for the selected capture backend."""

        source = self.source_combo.currentData()

        if source == "pico":
            self.statusBar().showMessage("Pico 2 backend is reserved for the product MCU firmware")
        else:
            self.statusBar().showMessage("Ready")

    def restore_settings(self):
        """Restore the user's last capture configuration."""

        geometry = self.settings.value("window_geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self._select_combo_data(
            self.source_combo,
            self.settings.value("source", "demo"),
        )
        self._select_combo_data(
            self.sample_rate_combo,
            int(self.settings.value("sample_rate_hz", 1_000_000)),
        )
        self.duration_spin.setValue(int(self.settings.value("duration_ms", 200)))

        saved_trigger = self.settings.value("trigger_edge", "disabled")
        trigger_value = None if saved_trigger == "disabled" else saved_trigger
        self._select_combo_data(self.trigger_combo, trigger_value)
        self._select_combo_data(
            self.trigger_channel_combo,
            int(self.settings.value("trigger_channel", 0)),
        )
        self.pretrigger_spin.setValue(int(self.settings.value("pretrigger_percent", 30)))

    def save_settings(self):
        """Persist UI configuration between application runs."""

        self.settings.setValue("window_geometry", self.saveGeometry())
        self.settings.setValue("source", self.source_combo.currentData())
        self.settings.setValue(
            "sample_rate_hz",
            int(self.sample_rate_combo.currentData()),
        )
        self.settings.setValue("duration_ms", self.duration_spin.value())

        trigger_value = self.trigger_combo.currentData()
        self.settings.setValue(
            "trigger_edge",
            "disabled" if trigger_value is None else trigger_value,
        )
        self.settings.setValue(
            "trigger_channel",
            int(self.trigger_channel_combo.currentData()),
        )
        self.settings.setValue(
            "pretrigger_percent",
            self.pretrigger_spin.value(),
        )

    @staticmethod
    def _select_combo_data(combo: QComboBox, target_value):
        for index in range(combo.count()):
            if combo.itemData(index) == target_value:
                combo.setCurrentIndex(index)
                return

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    def update_trigger_controls(self):
        enabled = self.trigger_combo.currentData() is not None
        self.trigger_channel_combo.setEnabled(enabled)
        self.pretrigger_spin.setEnabled(enabled)

    def show_welcome_message(self):
        lines = [
            "Logic Analyzer App",
            "",
            "Capture backends:",
            "- DemoDriver: generated SPI, I2C and UART samples",
            "- SigrokCliDriver: Saleae clone hardware capture",
            "- PicoDriver: final product MCU backend, connected with firmware",
            "",
            "Features:",
            "- SPI, I2C and UART decoding",
            "- Decode overlay on the waveform",
            "- Timing cursors and software trigger",
            "- CSV export and .la session save/load",
            "",
            "Cursor controls:",
            "- Shift + left click: Cursor A",
            "- Ctrl + left click: Cursor B",
            "- Right click: clear cursors",
        ]
        self.output.setPlainText("\n".join(lines))

    def run_capture(self):
        source = self.source_combo.currentData()
        sample_rate_hz = int(self.sample_rate_combo.currentData())
        duration_ms = self.duration_spin.value()

        estimated_sample_count = round(sample_rate_hz * duration_ms / 1000)

        if estimated_sample_count > 5_000_000:
            response = QMessageBox.question(
                self,
                "Large capture",
                (
                    f"This capture will contain approximately "
                    f"{estimated_sample_count:,} samples. "
                    "Waveform rendering and decoding may take longer. "
                    "Continue?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if response != QMessageBox.StandardButton.Yes:
                return

        if source == "pico":
            QMessageBox.information(
                self,
                "Pico 2",
                (
                    "Pico 2 is the MCU core of the final logic "
                    "analyzer. Its capture and hardware-trigger "
                    "protocol will be connected after testing "
                    "the board firmware."
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

        except (OSError, ValueError, SigrokCliError) as error:
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
            f"Capture completed: {buffer.sample_count()} samples",
            5000,
        )

    def capture_demo(
        self,
        sample_rate_hz: int,
        duration_ms: int,
    ) -> LogicSampleBuffer:
        driver = DemoDriver(sample_rate_hz=sample_rate_hz)
        return driver.capture(duration_ms=duration_ms)

    def capture_saleae(
        self,
        sample_rate_hz: int,
        duration_ms: int,
    ) -> LogicSampleBuffer:
        executable = resolve_sigrok_cli_path()

        driver = SigrokCliDriver(
            executable=executable,
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
        self.current_buffer = buffer
        self.current_source_name = source_name

        self.waveform_view.set_buffer(buffer)
        self.decoder_panel.set_buffer(buffer)

        trigger_info = self.apply_software_trigger(buffer)

        if not trigger_info["found"]:
            self.fit_view()

        lines = [
            "Capture completed successfully.",
            f"Source: {source_name}",
            f"Sample rate: {buffer.sample_rate_hz} Hz",
            f"Sample count: {buffer.sample_count()}",
            ("Duration: " f"{buffer.duration_seconds() * 1000:.3f} ms"),
            "",
        ]

        self.append_trigger_report(lines, trigger_info)

        if source_name == "Demo":
            lines.extend(
                [
                    "",
                    "Demo mapping:",
                    "CH1=SPI CS, CH2=MOSI, CH3=MISO, CH4=SCK",
                    "CH5=I2C SDA, CH6=SCL, CH7=UART TX",
                ]
            )
        elif source_name == "Saleae Clone":
            lines.extend(
                [
                    "",
                    "Saleae mapping:",
                    "sigrok D0..D7 = project CH1..CH8",
                ]
            )

        self.output.setPlainText("\n".join(lines))

    def apply_software_trigger(
        self,
        buffer: LogicSampleBuffer,
    ) -> dict:
        edge = self.trigger_combo.currentData()

        if edge is None:
            self.waveform_view.clear_trigger()
            return {
                "enabled": False,
                "found": False,
                "edge": None,
                "channel_index": None,
                "sample": None,
            }

        channel_index = int(self.trigger_channel_combo.currentData())

        trigger_sample = find_trigger_sample(
            buffer=buffer,
            channel_index=channel_index,
            edge=edge,
        )

        if trigger_sample is None:
            self.waveform_view.clear_trigger()
            return {
                "enabled": True,
                "found": False,
                "edge": edge,
                "channel_index": channel_index,
                "sample": None,
            }

        self.waveform_view.set_trigger_sample(trigger_sample)
        self.waveform_view.center_on_sample(
            sample_index=trigger_sample,
            position_ratio=self.pretrigger_spin.value() / 100.0,
        )

        return {
            "enabled": True,
            "found": True,
            "edge": edge,
            "channel_index": channel_index,
            "sample": trigger_sample,
        }

    def append_trigger_report(
        self,
        lines: list[str],
        trigger_info: dict,
    ):
        if not trigger_info["enabled"]:
            lines.append("Software trigger: Disabled")
            return

        channel_name = f"CH{trigger_info['channel_index'] + 1}"
        edge_name = str(trigger_info["edge"]).capitalize()

        if not trigger_info["found"]:
            lines.append(f"Software trigger: {edge_name} on {channel_name}")
            lines.append("Trigger result: No matching edge found")
            return

        trigger_sample = int(trigger_info["sample"])
        trigger_time_us = trigger_sample / self.current_buffer.sample_rate_hz * 1_000_000

        lines.append(f"Software trigger: {edge_name} on {channel_name}")
        lines.append(f"Trigger sample: {trigger_sample}")
        lines.append(f"Trigger time: {trigger_time_us:.3f} us")
        lines.append(f"View pre-trigger position: " f"{self.pretrigger_spin.value()}%")

    def clear_capture(self):
        """Remove the current capture and all derived display state."""

        self.current_buffer = None
        self.current_source_name = "None"

        self.waveform_view.set_buffer(None)
        self.decoder_panel.set_buffer(None)

        self.show_welcome_message()
        self.statusBar().showMessage("Capture cleared", 3000)

    def save_session(self):
        if self.current_buffer is None:
            QMessageBox.warning(
                self,
                "Save Session",
                "No capture data is available.",
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

    def open_session(self):
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
        self.decoder_panel.set_buffer(buffer)
        self.decoder_panel.set_annotations(annotations)
        self.select_sample_rate(buffer.sample_rate_hz)

        trigger_info = self.apply_software_trigger(buffer)
        if not trigger_info["found"]:
            self.fit_view()

        lines = [
            "Session loaded successfully.",
            f"File: {file_path}",
            f"Sample rate: {buffer.sample_rate_hz} Hz",
            f"Sample count: {buffer.sample_count()}",
            f"Annotations: {len(annotations)}",
            "",
        ]
        self.append_trigger_report(lines, trigger_info)
        self.output.setPlainText("\n".join(lines))

        self.statusBar().showMessage(
            "Session loaded successfully",
            5000,
        )

    def select_sample_rate(self, sample_rate_hz: int):
        for index in range(self.sample_rate_combo.count()):
            if self.sample_rate_combo.itemData(index) == sample_rate_hz:
                self.sample_rate_combo.setCurrentIndex(index)
                return

        self.sample_rate_combo.addItem(
            f"{sample_rate_hz} Hz",
            sample_rate_hz,
        )
        self.sample_rate_combo.setCurrentIndex(self.sample_rate_combo.count() - 1)

    def fit_view(self):
        if self.current_buffer is None:
            return

        visible_width = max(
            1,
            self.waveform_view.width() - self.waveform_view.left_margin - 20,
        )
        self.waveform_view.viewport_start_sample = 0
        self.waveform_view.samples_per_pixel = max(
            1.0,
            self.current_buffer.sample_count() / visible_width,
        )
        self.waveform_view.update()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
