# driver/demo_driver.py

import numpy as np

from data.logic_sample_buffer import LogicSampleBuffer
from config.app_config import DEFAULT_SAMPLE_RATE_HZ, CHANNEL_COUNT


class DemoDriver:
    """
    Driver giả lập để test app không cần phần cứng.

    Mapping:
    CH1 = SPI CS
    CH2 = SPI MOSI
    CH3 = SPI MISO
    CH4 = SPI SCK

    CH5 = I2C SDA
    CH6 = I2C SCL

    CH7 = UART TX
    CH8 = unused
    """

    def __init__(self, sample_rate_hz: int = DEFAULT_SAMPLE_RATE_HZ):
        self.sample_rate_hz = sample_rate_hz

    def capture(self, duration_ms: int = 50) -> LogicSampleBuffer:
        sample_count = int(self.sample_rate_hz * duration_ms / 1000)
        samples = np.zeros(sample_count, dtype=np.uint8)

        buffer = LogicSampleBuffer(
            samples=samples,
            sample_rate_hz=self.sample_rate_hz,
            channel_count=CHANNEL_COUNT,
        )

        # Set idle mặc định
        self._set_channel_range(buffer, 0, sample_count, 0, 1)  # CH1 SPI CS idle HIGH
        self._set_channel_range(buffer, 0, sample_count, 3, 0)  # CH4 SPI SCK idle LOW

        self._set_channel_range(buffer, 0, sample_count, 4, 1)  # CH5 I2C SDA idle HIGH
        self._set_channel_range(buffer, 0, sample_count, 5, 1)  # CH6 I2C SCL idle HIGH

        self._set_channel_range(buffer, 0, sample_count, 6, 1)  # CH7 UART idle HIGH

        # Sinh các protocol demo ở các vùng khác nhau
        self._generate_spi(buffer, start_sample=2_000)
        self._generate_i2c(buffer, start_sample=15_000)
        self._generate_uart(buffer, start_sample=32_000, text="HELLO")

        return buffer

    def _set_channel_range(
        self,
        buffer: LogicSampleBuffer,
        start: int,
        end: int,
        channel_index: int,
        bit_value: int,
    ) -> None:
        start = max(0, start)
        end = min(buffer.sample_count(), end)
        mask = np.uint8(1 << channel_index)

        if bit_value:
            buffer.samples[start:end] |= mask
        else:
            buffer.samples[start:end] &= np.uint8(~mask & 0xFF)

    # =========================
    # SPI demo
    # =========================

    def _generate_spi(self, buffer: LogicSampleBuffer, start_sample: int) -> None:
        cs = 0      # CH1
        mosi = 1    # CH2
        miso = 2    # CH3
        sck = 3     # CH4

        half_period = 4  # 1 MHz sample rate -> clock khoảng 125 kHz
        gap = 20

        bytes_out = [0x55, 0xAA, 0x3C, 0xC3]
        bytes_in = [0x11, 0x22, 0x33, 0x44]

        i = start_sample

        # CS active LOW
        buffer.set_bit(i, cs, 0)
        self._set_channel_range(buffer, i, i + 400, cs, 0)

        for out_byte, in_byte in zip(bytes_out, bytes_in):
            for bit in range(7, -1, -1):
                mosi_bit = (out_byte >> bit) & 1
                miso_bit = (in_byte >> bit) & 1

                # Mode 0: data stable before rising edge
                self._set_channel_range(buffer, i, i + half_period, sck, 0)
                self._set_channel_range(buffer, i, i + half_period, mosi, mosi_bit)
                self._set_channel_range(buffer, i, i + half_period, miso, miso_bit)
                i += half_period

                # rising/high phase
                self._set_channel_range(buffer, i, i + half_period, sck, 1)
                self._set_channel_range(buffer, i, i + half_period, mosi, mosi_bit)
                self._set_channel_range(buffer, i, i + half_period, miso, miso_bit)
                i += half_period

            i += gap

        self._set_channel_range(buffer, i, i + 100, cs, 1)
        self._set_channel_range(buffer, i, i + 100, sck, 0)

    # =========================
    # I2C demo
    # =========================

    def _generate_i2c(self, buffer: LogicSampleBuffer, start_sample: int) -> None:
        sda = 4  # CH5
        scl = 5  # CH6

        i = start_sample
        delay = 8

        def set_sda(start, end, value):
            self._set_channel_range(buffer, start, end, sda, value)

        def set_scl(start, end, value):
            self._set_channel_range(buffer, start, end, scl, value)

        def write_bit(bit_value: int):
            nonlocal i

            # đổi data khi SCL LOW
            set_scl(i, i + delay, 0)
            set_sda(i, i + delay, bit_value)
            i += delay

            # SCL HIGH: receiver đọc SDA
            set_scl(i, i + delay, 1)
            set_sda(i, i + delay, bit_value)
            i += delay

            set_scl(i, i + delay, 0)
            set_sda(i, i + delay, bit_value)
            i += delay

        def write_byte(value: int):
            nonlocal i

            for bit in range(7, -1, -1):
                write_bit((value >> bit) & 1)

            # ACK = 0
            write_bit(0)

        # idle
        set_sda(i, i + delay, 1)
        set_scl(i, i + delay, 1)
        i += delay

        # START: SDA falling while SCL HIGH
        set_scl(i, i + delay, 1)
        set_sda(i, i + delay, 0)
        i += delay

        # Address 0x3C Write => raw byte 0x78
        write_byte(0x3C << 1)
        write_byte(0x00)
        write_byte(0x55)
        write_byte(0xAA)
        write_byte(0x12)
        write_byte(0x34)

        # STOP: SDA rising while SCL HIGH
        set_sda(i, i + delay, 0)
        set_scl(i, i + delay, 0)
        i += delay

        set_scl(i, i + delay, 1)
        set_sda(i, i + delay, 0)
        i += delay

        set_scl(i, i + delay, 1)
        set_sda(i, i + delay, 1)

    # =========================
    # UART demo
    # =========================

    def _generate_uart(self, buffer: LogicSampleBuffer, start_sample: int, text: str) -> None:
        tx = 6  # CH7
        baudrate = 9600
        samples_per_bit = int(round(self.sample_rate_hz / baudrate))

        i = start_sample

        for ch in text:
            value = ord(ch)

            # start bit LOW
            self._set_channel_range(buffer, i, i + samples_per_bit, tx, 0)
            i += samples_per_bit

            # 8 data bits, LSB first
            for bit in range(8):
                bit_value = (value >> bit) & 1
                self._set_channel_range(buffer, i, i + samples_per_bit, tx, bit_value)
                i += samples_per_bit

            # stop bit HIGH
            self._set_channel_range(buffer, i, i + samples_per_bit, tx, 1)
            i += samples_per_bit

            # small gap
            self._set_channel_range(buffer, i, i + samples_per_bit, tx, 1)
            i += samples_per_bit