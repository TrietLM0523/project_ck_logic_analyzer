# decoder/i2c_decoder.py

from dataclasses import dataclass

from data.logic_sample_buffer import LogicSampleBuffer
from decoder.decode_annotation import DecodeAnnotation


@dataclass
class I2CConfig:
    """
    Cấu hình kênh cho I2C decoder.

    Giá trị channel dùng chỉ số nội bộ:
    0 = CH1
    1 = CH2
    ...
    7 = CH8
    """

    sda_channel: int = 4  # CH5
    scl_channel: int = 5  # CH6


class I2CDecoder:
    """
    I2C decoder cơ bản, hỗ trợ:

    - START
    - Repeated START
    - STOP
    - Địa chỉ 7 bit
    - Bit Read/Write
    - Data byte
    - ACK/NACK

    Quy tắc quan trọng:
    SDA chỉ được lấy mẫu tại cạnh lên của SCL.
    """

    def decode(
        self,
        buffer: LogicSampleBuffer,
        config: I2CConfig,
    ) -> list[DecodeAnnotation]:
        annotations: list[DecodeAnnotation] = []

        sample_count = buffer.sample_count()

        if sample_count < 2:
            return annotations

        # Trạng thái transaction
        in_transaction = False

        # Byte đầu tiên sau START là byte address
        byte_index = 0

        # Trạng thái ghép byte
        bit_count = 0
        current_value = 0
        waiting_for_ack = False

        byte_start_sample = 0
        byte_data_end_sample = 0

        for sample_index in range(1, sample_count):
            previous_sda = buffer.get_bit(
                sample_index - 1,
                config.sda_channel,
            )
            current_sda = buffer.get_bit(
                sample_index,
                config.sda_channel,
            )

            previous_scl = buffer.get_bit(
                sample_index - 1,
                config.scl_channel,
            )
            current_scl = buffer.get_bit(
                sample_index,
                config.scl_channel,
            )

            # ==========================================================
            # START:
            # SDA chuyển HIGH -> LOW trong khi SCL đang HIGH.
            # ==========================================================
            start_detected = previous_sda == 1 and current_sda == 0 and current_scl == 1

            if start_detected:
                # Nếu đang trong transaction thì đây là Repeated START.
                annotation_type = "RESTART" if in_transaction else "START"

                annotation_text = "Repeated START" if in_transaction else "START"

                # Nếu START xuất hiện giữa một byte chưa hoàn chỉnh,
                # báo byte dang dở.
                if in_transaction and (bit_count != 0 or waiting_for_ack):
                    annotations.append(
                        DecodeAnnotation(
                            start_sample=byte_start_sample,
                            end_sample=sample_index,
                            protocol="I2C",
                            type="ERROR",
                            value="",
                            text="Incomplete byte before repeated START",
                            error=True,
                            error_reason=("Repeated START occurred " "before byte completion"),
                        )
                    )

                annotations.append(
                    DecodeAnnotation(
                        start_sample=sample_index,
                        end_sample=sample_index,
                        protocol="I2C",
                        type=annotation_type,
                        value="",
                        text=annotation_text,
                    )
                )

                in_transaction = True
                byte_index = 0

                bit_count = 0
                current_value = 0
                waiting_for_ack = False
                byte_start_sample = sample_index

                # START không phải data bit.
                continue

            # ==========================================================
            # STOP:
            # SDA chuyển LOW -> HIGH trong khi SCL đang HIGH.
            # ==========================================================
            stop_detected = previous_sda == 0 and current_sda == 1 and current_scl == 1

            if stop_detected:
                # Khi tạo STOP, SCL thường lên HIGH trước rồi SDA mới lên HIGH.
                # Cạnh lên SCL này có thể bị hiểu nhầm là bit đầu của byte mới.
                if bit_count == 1 and not waiting_for_ack:
                    bit_count = 0
                    current_value = 0

                elif bit_count != 0 or waiting_for_ack:
                    annotations.append(
                        DecodeAnnotation(
                            start_sample=byte_start_sample,
                            end_sample=sample_index,
                            protocol="I2C",
                            type="ERROR",
                            value="",
                            text="Incomplete byte before STOP",
                            error=True,
                            error_reason=("STOP occurred before byte completion"),
                        )
                    )

                annotations.append(
                    DecodeAnnotation(
                        start_sample=sample_index,
                        end_sample=sample_index,
                        protocol="I2C",
                        type="STOP",
                        value="",
                        text="STOP",
                    )
                )

                in_transaction = False
                byte_index = 0
                bit_count = 0
                current_value = 0
                waiting_for_ack = False
                continue

            # Chưa gặp START thì không decode data.
            if not in_transaction:
                continue

            # ==========================================================
            # Phát hiện cạnh lên của SCL.
            # I2C receiver đọc SDA tại cạnh này.
            # ==========================================================
            scl_rising_edge = previous_scl == 0 and current_scl == 1

            if not scl_rising_edge:
                continue

            # ==========================================================
            # Đọc 8 data bit.
            # ==========================================================
            if not waiting_for_ack:
                if bit_count == 0:
                    byte_start_sample = sample_index
                    current_value = 0

                # I2C truyền MSB trước.
                current_value = (current_value << 1) | current_sda

                bit_count += 1

                if bit_count == 8:
                    byte_data_end_sample = sample_index
                    waiting_for_ack = True

                continue

            # ==========================================================
            # Cạnh lên thứ 9: đọc ACK/NACK.
            #
            # SDA = 0 → ACK
            # SDA = 1 → NACK
            # ==========================================================
            ack_bit = current_sda
            ack_text = "ACK" if ack_bit == 0 else "NACK"

            if byte_index == 0:
                # Byte đầu:
                # bit 7..1 = địa chỉ 7 bit
                # bit 0    = R/W
                address = current_value >> 1
                read_write_bit = current_value & 0x01

                direction = "Read" if read_write_bit == 1 else "Write"

                annotations.append(
                    DecodeAnnotation(
                        start_sample=byte_start_sample,
                        end_sample=sample_index,
                        protocol="I2C",
                        type="ADDRESS",
                        value=f"0x{address:02X}",
                        text=(f"Address 0x{address:02X} " f"{direction} {ack_text}"),
                    )
                )

            else:
                annotations.append(
                    DecodeAnnotation(
                        start_sample=byte_start_sample,
                        end_sample=sample_index,
                        protocol="I2C",
                        type="DATA",
                        value=f"0x{current_value:02X}",
                        text=(f"Data 0x{current_value:02X} " f"{ack_text}"),
                    )
                )

            # Chuẩn bị đọc byte tiếp theo.
            byte_index += 1

            bit_count = 0
            current_value = 0
            waiting_for_ack = False
            byte_start_sample = byte_data_end_sample

        # Capture kết thúc khi transaction còn dang dở.
        if in_transaction and (bit_count != 0 or waiting_for_ack):
            annotations.append(
                DecodeAnnotation(
                    start_sample=byte_start_sample,
                    end_sample=sample_count - 1,
                    protocol="I2C",
                    type="ERROR",
                    value="",
                    text="Capture ended during an I2C byte",
                    error=True,
                    error_reason=("Capture ended before byte completion"),
                )
            )

        return annotations
