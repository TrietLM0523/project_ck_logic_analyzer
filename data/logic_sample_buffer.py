# data/logic_sample_buffer.py

from dataclasses import dataclass
import numpy as np


@dataclass
class LogicSampleBuffer:
    """
    Lưu dữ liệu logic 8 kênh.

    Mỗi sample là 1 byte:
    bit 0 = CH1
    bit 1 = CH2
    bit 2 = CH3
    bit 3 = CH4
    bit 4 = CH5
    bit 5 = CH6
    bit 6 = CH7
    bit 7 = CH8
    """

    samples: np.ndarray
    sample_rate_hz: int
    channel_count: int = 8

    def sample_count(self) -> int:
        return int(len(self.samples))

    def duration_seconds(self) -> float:
        if self.sample_rate_hz <= 0:
            return 0.0
        return self.sample_count() / self.sample_rate_hz

    def get_bit(self, sample_index: int, channel_index: int) -> int:
        """
        channel_index:
        CH1 -> 0
        CH2 -> 1
        ...
        CH8 -> 7
        """
        if sample_index < 0 or sample_index >= self.sample_count():
            return 0

        if channel_index < 0 or channel_index >= self.channel_count:
            return 0

        value = int(self.samples[sample_index])
        return (value >> channel_index) & 1

    def set_bit(self, sample_index: int, channel_index: int, bit_value: int) -> None:
        if sample_index < 0 or sample_index >= self.sample_count():
            return

        if channel_index < 0 or channel_index >= self.channel_count:
            return

        if bit_value:
            self.samples[sample_index] |= np.uint8(1 << channel_index)
        else:
            self.samples[sample_index] &= np.uint8(~(1 << channel_index) & 0xFF)

    def sample_to_time_us(self, sample_index: int) -> float:
        return sample_index * 1_000_000.0 / self.sample_rate_hz