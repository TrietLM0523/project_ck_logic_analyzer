# ui/waveform_view.py

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from config.app_config import CHANNEL_NAMES


class WaveformView(QWidget):
    """
    Widget vẽ waveform logic analyzer.

    Input:
    - LogicSampleBuffer
    - mỗi sample là 1 byte
    - bit 0 = CH1, bit 1 = CH2, ..., bit 7 = CH8

    Software trigger marker:
    - Trigger sample được đặt từ MainWindow sau khi tìm cạnh
    - Marker T hiển thị vị trí cạnh trigger

    Timing cursors:
    - Shift + Left Click: đặt Cursor A
    - Ctrl + Left Click: đặt Cursor B
    - Right Click: xóa cả hai cursor
    - Left Drag: pan ngang như cũ
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.buffer = None
        self.viewport_start_sample = 0
        self.samples_per_pixel = 10.0

        self.left_margin = 80
        self.top_margin = 30
        self.channel_height = 55
        self.channel_gap = 5

        self.dragging = False
        self.last_mouse_x = 0

        self.trigger_sample: int | None = None

        self.cursor_a_sample: int | None = None
        self.cursor_b_sample: int | None = None

        self.setMinimumHeight(500)
        self.setMouseTracking(True)

    def set_buffer(self, buffer):
        self.buffer = buffer
        self.viewport_start_sample = 0
        self.trigger_sample = None
        self.clear_cursors()

        if buffer is not None:
            visible_width = max(1, self.width() - self.left_margin - 20)
            self.samples_per_pixel = max(
                1.0,
                buffer.sample_count() / visible_width / 2,
            )

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        self._draw_background(painter)

        if self.buffer is None:
            self._draw_empty_message(painter)
            return

        self._draw_time_grid(painter)
        self._draw_channels(painter)
        self._draw_trigger(painter)
        self._draw_cursors(painter)
        self._draw_cursor_measurement(painter)
        self._draw_status_text(painter)

    def _draw_background(self, painter: QPainter):
        painter.fillRect(self.rect(), QColor(25, 25, 25))

    def _draw_empty_message(self, painter: QPainter):
        painter.setPen(QPen(QColor(220, 220, 220)))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "No capture loaded. Click Start Capture.",
        )

    def _draw_status_text(self, painter: QPainter):
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.setFont(QFont("Consolas", 9))

        start_time_us = self.buffer.sample_to_time_us(int(self.viewport_start_sample))
        text = (
            f"sample_rate={self.buffer.sample_rate_hz} Hz | "
            f"samples={self.buffer.sample_count()} | "
            f"start={start_time_us:.1f} us | "
            f"zoom={self.samples_per_pixel:.2f} samples/px"
        )
        painter.drawText(10, self.height() - 10, text)

    def _draw_cursor_measurement(self, painter: QPainter):
        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))

        measurement = self.cursor_measurement()

        if measurement is not None:
            painter.setPen(QPen(QColor(235, 235, 235)))
            frequency_text = self._format_frequency(measurement["frequency_hz"])
            text = (
                f"A={measurement['a_sample']} "
                f"({self._format_time_seconds(measurement['a_seconds'])}) | "
                f"B={measurement['b_sample']} "
                f"({self._format_time_seconds(measurement['b_seconds'])}) | "
                f"Δsamples={measurement['delta_samples']} | "
                f"Δt={self._format_time_seconds(measurement['delta_seconds'])} | "
                f"f={frequency_text}"
            )
        elif self.cursor_a_sample is not None:
            painter.setPen(QPen(QColor(80, 220, 255)))
            text = f"Cursor A: sample {self.cursor_a_sample} | " "Ctrl + Left Click to set Cursor B"
        elif self.cursor_b_sample is not None:
            painter.setPen(QPen(QColor(255, 120, 220)))
            text = (
                f"Cursor B: sample {self.cursor_b_sample} | " "Shift + Left Click to set Cursor A"
            )
        else:
            painter.setPen(QPen(QColor(150, 150, 150)))
            text = "Timing cursors: " "Shift+Click=A | Ctrl+Click=B | Right Click=clear"

        painter.drawText(10, self.height() - 27, text)

    def _draw_time_grid(self, painter: QPainter):
        width = self.width()
        height = self.height()

        wave_left = self.left_margin
        wave_right = width - 20
        wave_width = max(1, wave_right - wave_left)

        visible_samples = wave_width * self.samples_per_pixel
        start_sample = self.viewport_start_sample
        end_sample = start_sample + visible_samples

        grid_step_samples = self._choose_grid_step(visible_samples)
        first_grid = int(start_sample // grid_step_samples) * grid_step_samples

        painter.setFont(QFont("Consolas", 8))

        sample_position = first_grid
        while sample_position <= end_sample:
            x = self.sample_to_x(sample_position)

            if wave_left <= x <= wave_right:
                painter.setPen(QPen(QColor(55, 55, 55)))
                painter.drawLine(
                    int(x),
                    self.top_margin - 15,
                    int(x),
                    height - 40,
                )

                time_us = self.buffer.sample_to_time_us(int(sample_position))
                painter.setPen(QPen(QColor(150, 150, 150)))
                painter.drawText(int(x) + 3, 15, f"{time_us:.0f} us")

            sample_position += grid_step_samples

    def _choose_grid_step(self, visible_samples: float) -> int:
        target_grid_count = 8
        raw_step = max(1, visible_samples / target_grid_count)

        base = 1
        while base * 10 < raw_step:
            base *= 10

        for multiplier in [1, 2, 5, 10]:
            step = base * multiplier
            if step >= raw_step:
                return int(step)

        return int(base * 10)

    def _draw_channels(self, painter: QPainter):
        if self.buffer is None:
            return

        for channel_index in range(self.buffer.channel_count):
            self._draw_one_channel(painter, channel_index)

    def _draw_one_channel(self, painter: QPainter, channel_index: int):
        width = self.width()

        wave_left = self.left_margin
        wave_right = width - 20
        wave_width = max(1, wave_right - wave_left)

        y_top = self.top_margin + channel_index * self.channel_height
        y_mid = y_top + self.channel_height // 2

        high_y = y_mid - 14
        low_y = y_mid + 14

        if channel_index < len(CHANNEL_NAMES):
            label = CHANNEL_NAMES[channel_index]
        else:
            label = f"CH{channel_index + 1}"

        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(220, 220, 220)))
        painter.drawText(10, y_mid + 5, label)

        painter.setPen(QPen(QColor(45, 45, 45)))
        painter.drawLine(wave_left, y_mid, wave_right, y_mid)

        painter.setPen(QPen(self._channel_color(channel_index), 1))

        start_sample = int(self.viewport_start_sample)
        end_sample = int(self.viewport_start_sample + wave_width * self.samples_per_pixel) + 2

        start_sample = max(0, start_sample)
        end_sample = min(self.buffer.sample_count(), end_sample)

        if end_sample <= start_sample:
            return

        prev_x = wave_left
        prev_bit = self.buffer.get_bit(start_sample, channel_index)
        prev_y = high_y if prev_bit else low_y

        for x in range(wave_left + 1, wave_right):
            sample_index = int(self.x_to_sample(x))

            if sample_index < 0:
                sample_index = 0
            if sample_index >= self.buffer.sample_count():
                sample_index = self.buffer.sample_count() - 1

            bit = self.buffer.get_bit(sample_index, channel_index)
            y = high_y if bit else low_y

            if bit == prev_bit:
                painter.drawLine(prev_x, prev_y, x, y)
            else:
                painter.drawLine(prev_x, prev_y, x, prev_y)
                painter.drawLine(x, prev_y, x, y)

            prev_x = x
            prev_y = y
            prev_bit = bit

    def _draw_trigger(self, painter: QPainter):
        if self.buffer is None or self.trigger_sample is None:
            return

        x = self.sample_to_x(self.trigger_sample)
        wave_left = self.left_margin
        wave_right = self.width() - 20

        if x < wave_left or x > wave_right:
            return

        trigger_color = QColor(255, 190, 70)
        trigger_pen = QPen(trigger_color, 2)
        trigger_pen.setStyle(Qt.PenStyle.DashDotLine)

        painter.setPen(trigger_pen)
        painter.drawLine(
            int(x),
            self.top_margin - 15,
            int(x),
            self.height() - 40,
        )

        time_seconds = self.trigger_sample / self.buffer.sample_rate_hz

        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.setPen(QPen(trigger_color))
        painter.drawText(
            int(x) + 4,
            59,
            (f"T: sample {self.trigger_sample} | " f"{self._format_time_seconds(time_seconds)}"),
        )

    def _draw_cursors(self, painter: QPainter):
        if self.buffer is None:
            return

        if self.cursor_a_sample is not None:
            self._draw_one_cursor(
                painter=painter,
                sample_index=self.cursor_a_sample,
                label="A",
                color=QColor(80, 220, 255),
                label_y=27,
            )

        if self.cursor_b_sample is not None:
            self._draw_one_cursor(
                painter=painter,
                sample_index=self.cursor_b_sample,
                label="B",
                color=QColor(255, 120, 220),
                label_y=43,
            )

    def _draw_one_cursor(
        self,
        painter: QPainter,
        sample_index: int,
        label: str,
        color: QColor,
        label_y: int,
    ):
        x = self.sample_to_x(sample_index)

        wave_left = self.left_margin
        wave_right = self.width() - 20

        if x < wave_left or x > wave_right:
            return

        cursor_pen = QPen(color, 1)
        cursor_pen.setStyle(Qt.PenStyle.DashLine)

        painter.setPen(cursor_pen)
        painter.drawLine(
            int(x),
            self.top_margin - 15,
            int(x),
            self.height() - 40,
        )

        time_seconds = sample_index / self.buffer.sample_rate_hz

        painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
        painter.setPen(QPen(color))
        painter.drawText(
            int(x) + 4,
            label_y,
            f"{label}: {self._format_time_seconds(time_seconds)}",
        )

    def _channel_color(self, channel_index: int) -> QColor:
        colors = [
            QColor(80, 220, 120),
            QColor(255, 180, 80),
            QColor(255, 100, 100),
            QColor(100, 180, 255),
            QColor(220, 220, 80),
            QColor(120, 220, 220),
            QColor(180, 140, 255),
            QColor(220, 220, 220),
        ]
        return colors[channel_index % len(colors)]

    def sample_to_x(self, sample_index: float) -> float:
        return (
            self.left_margin + (sample_index - self.viewport_start_sample) / self.samples_per_pixel
        )

    def x_to_sample(self, x: float) -> float:
        return self.viewport_start_sample + (x - self.left_margin) * self.samples_per_pixel

    def wheelEvent(self, event):
        if self.buffer is None:
            return

        mouse_x = event.position().x()
        mouse_sample_before = self.x_to_sample(mouse_x)

        delta = event.angleDelta().y()
        if delta > 0:
            self.samples_per_pixel /= 1.25
        else:
            self.samples_per_pixel *= 1.25

        self.samples_per_pixel = max(
            0.1,
            min(self.samples_per_pixel, 10000.0),
        )

        mouse_sample_after = self.x_to_sample(mouse_x)
        self.viewport_start_sample += mouse_sample_before - mouse_sample_after

        self._clamp_viewport()
        self.update()

    def mousePressEvent(self, event):
        if self.buffer is None:
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.clear_cursors()
            event.accept()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        modifiers = event.modifiers()
        mouse_x = event.position().x()

        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.set_cursor_a_from_x(mouse_x)
            event.accept()
            return

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self.set_cursor_b_from_x(mouse_x)
            event.accept()
            return

        self.dragging = True
        self.last_mouse_x = mouse_x

    def mouseMoveEvent(self, event):
        if self.dragging and self.buffer is not None:
            x = event.position().x()
            dx = x - self.last_mouse_x
            self.last_mouse_x = x

            self.viewport_start_sample -= dx * self.samples_per_pixel

            self._clamp_viewport()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def set_cursor_a_from_x(self, x: float):
        sample_index = self._sample_index_from_x(x)

        if sample_index is None:
            return

        self.cursor_a_sample = sample_index
        self.update()

    def set_cursor_b_from_x(self, x: float):
        sample_index = self._sample_index_from_x(x)

        if sample_index is None:
            return

        self.cursor_b_sample = sample_index
        self.update()

    def _sample_index_from_x(self, x: float) -> int | None:
        if self.buffer is None:
            return None

        wave_left = self.left_margin
        wave_right = self.width() - 20

        if x < wave_left or x > wave_right:
            return None

        sample_index = round(self.x_to_sample(x))

        return max(
            0,
            min(sample_index, self.buffer.sample_count() - 1),
        )

    def set_trigger_sample(
        self,
        sample_index: int | None,
    ):
        if self.buffer is None or sample_index is None:
            self.trigger_sample = None
            self.update()
            return

        self.trigger_sample = max(
            0,
            min(
                int(sample_index),
                self.buffer.sample_count() - 1,
            ),
        )
        self.update()

    def clear_trigger(self):
        self.trigger_sample = None
        self.update()

    def center_on_sample(
        self,
        sample_index: int,
        position_ratio: float = 0.30,
    ):
        """
        Đặt sample tại một vị trí tương đối trong vùng waveform.

        position_ratio=0.30 nghĩa là marker nằm ở khoảng 30%
        chiều rộng waveform, để còn phần dữ liệu trước trigger.
        """

        if self.buffer is None:
            return

        ratio = max(0.0, min(float(position_ratio), 1.0))

        visible_width = max(
            1,
            self.width() - self.left_margin - 20,
        )
        visible_samples = visible_width * self.samples_per_pixel

        self.viewport_start_sample = int(sample_index) - visible_samples * ratio

        self._clamp_viewport()
        self.update()

    def clear_cursors(self):
        self.cursor_a_sample = None
        self.cursor_b_sample = None
        self.update()

    def cursor_measurement(self) -> dict | None:
        if self.buffer is None or self.cursor_a_sample is None or self.cursor_b_sample is None:
            return None

        delta_samples = abs(self.cursor_b_sample - self.cursor_a_sample)
        sample_rate_hz = self.buffer.sample_rate_hz

        a_seconds = self.cursor_a_sample / sample_rate_hz
        b_seconds = self.cursor_b_sample / sample_rate_hz
        delta_seconds = delta_samples / sample_rate_hz

        if delta_seconds > 0:
            frequency_hz = 1.0 / delta_seconds
        else:
            frequency_hz = None

        return {
            "a_sample": self.cursor_a_sample,
            "b_sample": self.cursor_b_sample,
            "delta_samples": delta_samples,
            "a_seconds": a_seconds,
            "b_seconds": b_seconds,
            "delta_seconds": delta_seconds,
            "frequency_hz": frequency_hz,
        }

    @staticmethod
    def _format_time_seconds(seconds: float) -> str:
        absolute_seconds = abs(seconds)

        if absolute_seconds >= 1:
            return f"{seconds:.6f} s"
        if absolute_seconds >= 1e-3:
            return f"{seconds * 1e3:.3f} ms"
        if absolute_seconds >= 1e-6:
            return f"{seconds * 1e6:.3f} us"

        return f"{seconds * 1e9:.3f} ns"

    @staticmethod
    def _format_frequency(frequency_hz: float | None) -> str:
        if frequency_hz is None:
            return "N/A"

        absolute_frequency = abs(frequency_hz)

        if absolute_frequency >= 1_000_000:
            return f"{frequency_hz / 1_000_000:.3f} MHz"
        if absolute_frequency >= 1_000:
            return f"{frequency_hz / 1_000:.3f} kHz"

        return f"{frequency_hz:.3f} Hz"

    def _clamp_viewport(self):
        if self.buffer is None:
            return

        self.viewport_start_sample = max(
            0,
            self.viewport_start_sample,
        )

        visible_width = max(
            1,
            self.width() - self.left_margin - 20,
        )
        visible_samples = visible_width * self.samples_per_pixel

        max_start = max(
            0,
            self.buffer.sample_count() - visible_samples,
        )
        self.viewport_start_sample = min(
            self.viewport_start_sample,
            max_start,
        )
