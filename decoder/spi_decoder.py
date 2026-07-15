# decoder/spi_decoder.py

from dataclasses import dataclass
from typing import List, Optional

from data.logic_sample_buffer import LogicSampleBuffer
from decoder.decode_annotation import DecodeAnnotation


@dataclass
class SPIConfig:
    """
    channel index:
    CH1 -> 0
    CH2 -> 1
    CH3 -> 2
    CH4 -> 3
    """

    cs_channel: int = 0      # CH1
    mosi_channel: int = 1    # CH2
    miso_channel: int = 2    # CH3
    sck_channel: int = 3     # CH4

    mode: int = 0
    bit_order: str = "MSB"   # "MSB" hoặc "LSB"
    word_size: int = 8
    cs_active_low: bool = True

    decode_mosi: bool = True
    decode_miso: bool = True


class SPIDecoder:
    """
    SPI decoder đơn giản.

    Bản đầu hỗ trợ tốt nhất:
    - SPI mode 0
    - CS active LOW
    - MSB first
    - word size 8

    Mapping demo:
    CH1 = CS
    CH2 = MOSI
    CH3 = MISO
    CH4 = SCK
    """

    def decode(
        self,
        buffer: LogicSampleBuffer,
        config: Optional[SPIConfig] = None,
    ) -> List[DecodeAnnotation]:
        if config is None:
            config = SPIConfig()

        result: List[DecodeAnnotation] = []

        n = buffer.sample_count()
        if n < 2:
            return result

        bit_count = 0
        mosi_value = 0
        miso_value = 0
        word_start_sample = 0
        in_transfer = False
        transfer_start = 0

        for i in range(1, n):
            cs = buffer.get_bit(i, config.cs_channel)
            selected = (cs == 0) if config.cs_active_low else (cs == 1)

            prev_sck = buffer.get_bit(i - 1, config.sck_channel)
            cur_sck = buffer.get_bit(i, config.sck_channel)

            if not selected:
                # Nếu vừa kết thúc transfer mà còn word dang dở thì báo warning
                if in_transfer and bit_count != 0:
                    result.append(
                        DecodeAnnotation(
                            start_sample=word_start_sample,
                            end_sample=i,
                            protocol="SPI",
                            type="ERROR",
                            value="",
                            text=f"Incomplete word: only {bit_count} bits before CS inactive",
                            error=True,
                            error_reason="CS inactive before completing word",
                        )
                    )

                in_transfer = False
                bit_count = 0
                mosi_value = 0
                miso_value = 0
                continue

            if not in_transfer:
                in_transfer = True
                transfer_start = i
                bit_count = 0
                mosi_value = 0
                miso_value = 0
                word_start_sample = i

            if self._is_sampling_edge(prev_sck, cur_sck, config.mode):
                mosi_bit = buffer.get_bit(i, config.mosi_channel)
                miso_bit = buffer.get_bit(i, config.miso_channel)

                if bit_count == 0:
                    word_start_sample = i
                    mosi_value = 0
                    miso_value = 0

                if config.bit_order.upper() == "MSB":
                    mosi_value = (mosi_value << 1) | mosi_bit
                    miso_value = (miso_value << 1) | miso_bit
                else:
                    mosi_value |= (mosi_bit << bit_count)
                    miso_value |= (miso_bit << bit_count)

                bit_count += 1

                if bit_count == config.word_size:
                    parts = []

                    value_text = ""

                    if config.decode_mosi:
                        parts.append(f"MOSI 0x{mosi_value:02X}")
                        value_text = f"0x{mosi_value:02X}"

                    if config.decode_miso:
                        parts.append(f"MISO 0x{miso_value:02X}")
                        if not value_text:
                            value_text = f"0x{miso_value:02X}"

                    result.append(
                        DecodeAnnotation(
                            start_sample=word_start_sample,
                            end_sample=i,
                            protocol="SPI",
                            type="DATA",
                            value=value_text,
                            text=", ".join(parts),
                        )
                    )

                    bit_count = 0
                    mosi_value = 0
                    miso_value = 0

        # Nếu kết thúc file khi đang transfer dang dở
        if in_transfer and bit_count != 0:
            result.append(
                DecodeAnnotation(
                    start_sample=word_start_sample,
                    end_sample=n - 1,
                    protocol="SPI",
                    type="ERROR",
                    value="",
                    text=f"Incomplete word at end of capture: {bit_count} bits",
                    error=True,
                    error_reason="End of capture before completing word",
                )
            )

        # Nếu không tìm thấy dữ liệu nào, thêm warning để dễ debug
        if len(result) == 0:
            result.append(
                DecodeAnnotation(
                    start_sample=0,
                    end_sample=0,
                    protocol="SPI",
                    type="WARNING",
                    value="",
                    text="No SPI data decoded. Check CS/MOSI/MISO/SCK mapping, sample rate, and SPI mode.",
                    error=True,
                    error_reason="No data decoded",
                )
            )

        return result

    def _is_sampling_edge(self, prev_sck: int, cur_sck: int, mode: int) -> bool:
        rising = prev_sck == 0 and cur_sck == 1
        falling = prev_sck == 1 and cur_sck == 0

        # Mode 0: CPOL=0, CPHA=0 -> sample rising
        if mode == 0:
            return rising

        # Mode 1: CPOL=0, CPHA=1 -> sample falling
        if mode == 1:
            return falling

        # Mode 2: CPOL=1, CPHA=0 -> sample falling
        if mode == 2:
            return falling

        # Mode 3: CPOL=1, CPHA=1 -> sample rising
        if mode == 3:
            return rising

        return rising