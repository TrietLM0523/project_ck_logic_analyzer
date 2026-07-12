# main.py

import sys

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QSplitter,
)
from PyQt6.QtCore import Qt

from driver.demo_driver import DemoDriver
from ui.waveform_view import WaveformView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Logic Analyzer App - Milestone 2 Waveform")
        self.resize(1200, 750)

        self.current_buffer = None

        root = QWidget()
        root_layout = QVBoxLayout(root)

        # Top controls
        top_bar = QHBoxLayout()
        self.title = QLabel("Logic Analyzer App")
        self.button_start_demo = QPushButton("Start Demo")
        self.button_fit = QPushButton("Fit View")

        top_bar.addWidget(self.title)
        top_bar.addStretch()
        top_bar.addWidget(self.button_start_demo)
        top_bar.addWidget(self.button_fit)

        root_layout.addLayout(top_bar)

        # Main splitter: waveform trên, text log dưới
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.waveform_view = WaveformView()
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(180)

        splitter.addWidget(self.waveform_view)
        splitter.addWidget(self.output)
        splitter.setSizes([550, 160])

        root_layout.addWidget(splitter)

        self.setCentralWidget(root)

        self.button_start_demo.clicked.connect(self.run_demo)
        self.button_fit.clicked.connect(self.fit_view)

    def run_demo(self):
        driver = DemoDriver(sample_rate_hz=1_000_000)
        buffer = driver.capture(duration_ms=50)

        self.current_buffer = buffer
        self.waveform_view.set_buffer(buffer)

        lines = []
        lines.append("Demo capture generated successfully.")
        lines.append(f"Sample rate: {buffer.sample_rate_hz} Hz")
        lines.append(f"Sample count: {buffer.sample_count()}")
        lines.append(f"Duration: {buffer.duration_seconds() * 1000:.3f} ms")
        lines.append("")
        lines.append("Channel mapping:")
        lines.append("CH1 = SPI CS")
        lines.append("CH2 = SPI MOSI")
        lines.append("CH3 = SPI MISO")
        lines.append("CH4 = SPI SCK")
        lines.append("CH5 = I2C SDA")
        lines.append("CH6 = I2C SCL")
        lines.append("CH7 = UART TX")
        lines.append("CH8 = unused")
        lines.append("")
        lines.append("Demo signal regions:")
        lines.append("SPI  starts around sample 2000")
        lines.append("I2C  starts around sample 15000")
        lines.append("UART starts around sample 32000")
        lines.append("")
        lines.append("Controls:")
        lines.append("- Mouse wheel: zoom in/out")
        lines.append("- Drag left mouse: pan horizontally")
        lines.append("- Fit View: show whole capture")

        self.output.setPlainText("\n".join(lines))

    def fit_view(self):
        if self.current_buffer is None:
            return

        visible_width = max(1, self.waveform_view.width() - self.waveform_view.left_margin - 20)
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