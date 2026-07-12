# ui/waveform_view.py

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtWidgets import QWidget

from config.app_config import CHANNEL_NAMES


class WaveformView(QWidget):
    """
    Widget vẽ waveform logic analyzer.

    Input:
    - LogicSampleBuffer
    - mỗi sample là 1 byte
    - bit 0 = CH1, bit 1 = CH2, ..., bit 7 = CH8
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.buffer = None

        # viewport_start_sample: sample đầu tiên đang hiển thị
        self.viewport_start_sample = 0

        # samples_per_pixel càng lớn thì càng zoom out
        self.samples_per_pixel = 10.0

        self.left_margin = 80
        self.top_margin = 30
        self.channel_height = 55
        self.channel_gap = 5

        self.dragging = False
        self.last_mouse_x = 0

        self.setMinimumHeight(500)
        self.setMouseTracking(True)

    def set_buffer(self, buffer):
        self.buffer = buffer
        self.viewport_start_sample = 0

        if buffer is not None:
            visible_width = max(1, self.width() - self.left_margin - 20)
            self.samples_per_pixel = max(1.0, buffer.sample_count() / visible_width / 2)

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
        self._draw_status_text(painter)

    def _draw_background(self, painter: QPainter):
        painter.fillRect(self.rect(), QColor(25, 25, 25))

    def _draw_empty_message(self, painter: QPainter):
        painter.setPen(QPen(QColor(220, 220, 220)))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "No capture loaded. Click Start Demo.",
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

    def _draw_time_grid(self, painter: QPainter):
        width = self.width()
        height = self.height()

        wave_left = self.left_margin
        wave_right = width - 20
        wave_width = max(1, wave_right - wave_left)

        visible_samples = wave_width * self.samples_per_pixel
        start_sample = self.viewport_start_sample
        end_sample = start_sample + visible_samples

        # chọn khoảng grid tương đối dễ nhìn
        grid_step_samples = self._choose_grid_step(visible_samples)

        first_grid = int(start_sample // grid_step_samples) * grid_step_samples

        painter.setFont(QFont("Consolas", 8))

        s = first_grid
        while s <= end_sample:
            x = self.sample_to_x(s)

            if wave_left <= x <= wave_right:
                painter.setPen(QPen(QColor(55, 55, 55)))
                painter.drawLine(int(x), self.top_margin - 15, int(x), height - 30)

                time_us = self.buffer.sample_to_time_us(int(s))
                painter.setPen(QPen(QColor(150, 150, 150)))
                painter.drawText(int(x) + 3, 15, f"{time_us:.0f} us")

            s += grid_step_samples

    def _choose_grid_step(self, visible_samples: float) -> int:
        """
        Chọn bước grid theo sample để nhìn vừa mắt.
        """
        target_grid_count = 8
        raw_step = max(1, visible_samples / target_grid_count)

        # Làm tròn về các mức 1, 2, 5 * 10^n
        base = 1
        while base * 10 < raw_step:
            base *= 10

        for mul in [1, 2, 5, 10]:
            step = base * mul
            if step >= raw_step:
                return int(step)

        return int(base * 10)

    def _draw_channels(self, painter: QPainter):
        if self.buffer is None:
            return

        for ch in range(self.buffer.channel_count):
            self._draw_one_channel(painter, ch)

    def _draw_one_channel(self, painter: QPainter, channel_index: int):
        width = self.width()

        wave_left = self.left_margin
        wave_right = width - 20
        wave_width = max(1, wave_right - wave_left)

        y_top = self.top_margin + channel_index * self.channel_height
        y_mid = y_top + self.channel_height // 2

        high_y = y_mid - 14
        low_y = y_mid + 14

        # label channel
        label = CHANNEL_NAMES[channel_index] if channel_index < len(CHANNEL_NAMES) else f"CH{channel_index + 1}"

        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(220, 220, 220)))
        painter.drawText(10, y_mid + 5, label)

        # đường nền channel
        painter.setPen(QPen(QColor(45, 45, 45)))
        painter.drawLine(wave_left, y_mid, wave_right, y_mid)

        # waveform
        painter.setPen(QPen(self._channel_color(channel_index), 1))

        start_sample = int(self.viewport_start_sample)
        end_sample = int(self.viewport_start_sample + wave_width * self.samples_per_pixel) + 2

        start_sample = max(0, start_sample)
        end_sample = min(self.buffer.sample_count(), end_sample)

        if end_sample <= start_sample:
            return

        # Lấy mẫu theo pixel để đỡ quá chậm.
        # Mỗi x pixel lấy trạng thái tại sample tương ứng.
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
                # tiếp tục đường ngang
                painter.drawLine(prev_x, prev_y, x, y)
            else:
                # vẽ đoạn ngang cũ + cạnh dọc
                painter.drawLine(prev_x, prev_y, x, prev_y)
                painter.drawLine(x, prev_y, x, y)

            prev_x = x
            prev_y = y
            prev_bit = bit

    def _channel_color(self, channel_index: int) -> QColor:
        colors = [
            QColor(80, 220, 120),   # CH1
            QColor(255, 180, 80),   # CH2
            QColor(255, 100, 100),  # CH3
            QColor(100, 180, 255),  # CH4
            QColor(220, 220, 80),   # CH5
            QColor(120, 220, 220),  # CH6
            QColor(180, 140, 255),  # CH7
            QColor(220, 220, 220),  # CH8
        ]
        return colors[channel_index % len(colors)]

    def sample_to_x(self, sample_index: float) -> float:
        return self.left_margin + (sample_index - self.viewport_start_sample) / self.samples_per_pixel

    def x_to_sample(self, x: float) -> float:
        return self.viewport_start_sample + (x - self.left_margin) * self.samples_per_pixel

    def wheelEvent(self, event):
        if self.buffer is None:
            return

        mouse_x = event.position().x()
        mouse_sample_before = self.x_to_sample(mouse_x)

        delta = event.angleDelta().y()

        if delta > 0:
            # zoom in
            self.samples_per_pixel /= 1.25
        else:
            # zoom out
            self.samples_per_pixel *= 1.25

        self.samples_per_pixel = max(0.1, min(self.samples_per_pixel, 10000.0))

        # giữ sample dưới con trỏ chuột gần như không đổi sau zoom
        mouse_sample_after = self.x_to_sample(mouse_x)
        self.viewport_start_sample += mouse_sample_before - mouse_sample_after

        self._clamp_viewport()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.last_mouse_x = event.position().x()

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

    def _clamp_viewport(self):
        if self.buffer is None:
            return

        self.viewport_start_sample = max(0, self.viewport_start_sample)

        visible_width = max(1, self.width() - self.left_margin - 20)
        visible_samples = visible_width * self.samples_per_pixel

        max_start = max(0, self.buffer.sample_count() - visible_samples)
        self.viewport_start_sample = min(self.viewport_start_sample, max_start)