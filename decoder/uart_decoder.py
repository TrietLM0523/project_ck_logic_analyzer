# decoder/uart_decoder.py

from dataclasses import dataclass

from data.logic_sample_buffer import LogicSampleBuffer
from decoder.decode_annotation import DecodeAnnotation


@dataclass
class UARTConfig:
    """
    Cấu hình UART cơ bản.

    Channel index nội bộ:
    0 = CH1
    ...
    6 = CH7
    7 = CH8
    """

    rx_channel: int = 6
    baudrate: int = 9600
    data_bits: int = 8
    parity: str = "NONE"
    stop_bits: int = 1
    idle_high: bool = True


class UARTDecoder:
    """
    UART decoder bất đồng bộ.

    Hỗ trợ:
    - 5 đến 8 data bits
    - Parity NONE, EVEN, ODD
    - 1 hoặc 2 stop bits
    - UART thông thường idle HIGH
    - Data gửi LSB first
    """

    def decode(
        self,
        buffer: LogicSampleBuffer,
        config: UARTConfig,
    ) -> list[DecodeAnnotation]:
        annotations: list[DecodeAnnotation] = []

        sample_count = buffer.sample_count()

        if sample_count < 2:
            return annotations

        if config.baudrate <= 0:
            return [
                DecodeAnnotation(
                    start_sample=0,
                    end_sample=0,
                    protocol="UART",
                    type="ERROR",
                    value="",
                    text="Baudrate must be greater than zero",
                    error=True,
                    error_reason="Invalid baudrate",
                )
            ]

        samples_per_bit = buffer.sample_rate_hz / config.baudrate

        # Nếu mỗi bit có quá ít sample thì việc lấy mẫu không đáng tin cậy.
        if samples_per_bit < 3:
            return [
                DecodeAnnotation(
                    start_sample=0,
                    end_sample=0,
                    protocol="UART",
                    type="ERROR",
                    value="",
                    text=(
                        "Sample rate is too low for this baudrate: "
                        f"{samples_per_bit:.2f} samples/bit"
                    ),
                    error=True,
                    error_reason="Insufficient samples per UART bit",
                )
            ]

        idle_level = 1 if config.idle_high else 0
        start_level = 0 if config.idle_high else 1

        parity_enabled = config.parity.upper() != "NONE"
        parity_bit_count = 1 if parity_enabled else 0

        sample_index = 1

        while sample_index < sample_count:
            previous_rx = buffer.get_bit(
                sample_index - 1,
                config.rx_channel,
            )
            current_rx = buffer.get_bit(
                sample_index,
                config.rx_channel,
            )

            # UART thông thường bắt đầu bằng cạnh HIGH -> LOW.
            start_edge_detected = previous_rx == idle_level and current_rx == start_level

            if not start_edge_detected:
                sample_index += 1
                continue

            frame_start_sample = sample_index

            # Kiểm tra giữa start bit để loại nhiễu/glitch.
            start_center_position = frame_start_sample + 0.5 * samples_per_bit

            start_center_sample = self._sample_at(
                buffer=buffer,
                sample_position=start_center_position,
                channel=config.rx_channel,
            )

            if start_center_sample is None:
                break

            if start_center_sample != start_level:
                # Tín hiệu đã quay lại idle quá sớm:
                # đây có thể chỉ là một glitch.
                sample_index += 1
                continue

            current_value = 0
            frame_errors: list[str] = []
            capture_incomplete = False

            # ======================================================
            # Đọc data bits tại giữa mỗi bit.
            #
            # Start bit center = 0.5 bit
            # Data bit 0       = 1.5 bit
            # Data bit 1       = 2.5 bit
            # ...
            # ======================================================
            for bit_index in range(config.data_bits):
                bit_center_position = frame_start_sample + (1.5 + bit_index) * samples_per_bit

                bit_value = self._sample_at(
                    buffer=buffer,
                    sample_position=bit_center_position,
                    channel=config.rx_channel,
                )

                if bit_value is None:
                    capture_incomplete = True
                    break

                # UART truyền LSB trước.
                current_value |= bit_value << bit_index

            if capture_incomplete:
                annotations.append(
                    DecodeAnnotation(
                        start_sample=frame_start_sample,
                        end_sample=sample_count - 1,
                        protocol="UART",
                        type="ERROR",
                        value="",
                        text="Capture ended during UART data bits",
                        error=True,
                        error_reason="Incomplete UART frame",
                    )
                )
                break

            # ======================================================
            # Kiểm tra parity nếu được bật.
            # ======================================================
            if parity_enabled:
                parity_center_position = (
                    frame_start_sample + (1.5 + config.data_bits) * samples_per_bit
                )

                received_parity = self._sample_at(
                    buffer=buffer,
                    sample_position=parity_center_position,
                    channel=config.rx_channel,
                )

                if received_parity is None:
                    annotations.append(
                        DecodeAnnotation(
                            start_sample=frame_start_sample,
                            end_sample=sample_count - 1,
                            protocol="UART",
                            type="ERROR",
                            value=f"0x{current_value:02X}",
                            text="Capture ended during UART parity bit",
                            error=True,
                            error_reason="Incomplete parity bit",
                        )
                    )
                    break

                expected_parity = self._expected_parity(
                    value=current_value,
                    data_bits=config.data_bits,
                    parity=config.parity,
                )

                if received_parity != expected_parity:
                    frame_errors.append(
                        "Parity error: "
                        f"expected {expected_parity}, "
                        f"received {received_parity}"
                    )

            # ======================================================
            # Kiểm tra stop bit.
            #
            # Với UART 8N1:
            # stop bit center = 9.5 bit kể từ cạnh start.
            # ======================================================
            first_stop_offset = 1.5 + config.data_bits + parity_bit_count

            for stop_index in range(config.stop_bits):
                stop_center_position = (
                    frame_start_sample + (first_stop_offset + stop_index) * samples_per_bit
                )

                stop_value = self._sample_at(
                    buffer=buffer,
                    sample_position=stop_center_position,
                    channel=config.rx_channel,
                )

                if stop_value is None:
                    capture_incomplete = True
                    break

                if stop_value != idle_level:
                    frame_errors.append(f"Framing error at stop bit {stop_index + 1}")

            if capture_incomplete:
                annotations.append(
                    DecodeAnnotation(
                        start_sample=frame_start_sample,
                        end_sample=sample_count - 1,
                        protocol="UART",
                        type="ERROR",
                        value=f"0x{current_value:02X}",
                        text="Capture ended during UART stop bit",
                        error=True,
                        error_reason="Incomplete stop bit",
                    )
                )
                break

            frame_length_bits = 1 + config.data_bits + parity_bit_count + config.stop_bits

            frame_end_sample = round(frame_start_sample + frame_length_bits * samples_per_bit)

            frame_end_sample = min(
                frame_end_sample,
                sample_count - 1,
            )

            display_character = self._format_character(current_value)

            if frame_errors:
                annotation_type = "ERROR"
                status_text = "; ".join(frame_errors)
                annotation_text = f"0x{current_value:02X} " f"{display_character} — {status_text}"
                is_error = True
            else:
                annotation_type = "DATA"
                annotation_text = f"0x{current_value:02X} " f"{display_character}"
                status_text = ""
                is_error = False

            annotations.append(
                DecodeAnnotation(
                    start_sample=frame_start_sample,
                    end_sample=frame_end_sample,
                    protocol="UART",
                    type=annotation_type,
                    value=f"0x{current_value:02X}",
                    text=annotation_text,
                    error=is_error,
                    error_reason=status_text,
                )
            )

            # Sau khi decode xong, KHÔNG nhảy thẳng tới frame_end_sample.
            #
            # Với các frame UART nối liền nhau, cạnh xuống START của byte kế
            # tiếp có thể nằm đúng tại biên:
            #
            #     frame_start + frame_length_bits * samples_per_bit
            #
            # frame_end_sample dùng round(), nên đôi khi nó rơi ngay sau cạnh
            # START đó. Nếu đặt sample_index = frame_end_sample, vòng lặp sẽ
            # bỏ qua cạnh HIGH -> LOW và mất nguyên byte, đặc biệt dễ thấy với
            # 0x00 hoặc 0xFF vì bên trong frame gần như không còn cạnh xuống.
            #
            # Ta chỉ bỏ qua tới GIỮA stop bit cuối. Từ đó vòng quét tiếp tục
            # từng sample và vẫn nhìn thấy cạnh START của frame kế tiếp.
            resume_position = frame_start_sample + (frame_length_bits - 0.5) * samples_per_bit

            sample_index = max(
                sample_index + 1,
                int(resume_position),
            )

        return annotations

    def _sample_at(
        self,
        buffer: LogicSampleBuffer,
        sample_position: float,
        channel: int,
    ) -> int | None:
        """
        Lấy giá trị logic tại sample gần vị trí thời gian yêu cầu nhất.
        """

        sample_index = round(sample_position)

        if sample_index < 0:
            return None

        if sample_index >= buffer.sample_count():
            return None

        return buffer.get_bit(sample_index, channel)

    def _expected_parity(
        self,
        value: int,
        data_bits: int,
        parity: str,
    ) -> int:
        """
        Tính parity bit mong đợi.

        EVEN:
        Tổng số bit 1 của data + parity phải là số chẵn.

        ODD:
        Tổng số bit 1 của data + parity phải là số lẻ.
        """

        mask = (1 << data_bits) - 1
        masked_value = value & mask

        number_of_ones = masked_value.bit_count()

        parity_name = parity.upper()

        if parity_name == "EVEN":
            return number_of_ones % 2

        if parity_name == "ODD":
            return 1 - (number_of_ones % 2)

        return 0

    def _format_character(self, value: int) -> str:
        """
        Chuyển byte sang ký tự dễ đọc.
        """

        if value == 9:
            return r"'\t'"

        if value == 10:
            return r"'\n'"

        if value == 13:
            return r"'\r'"

        if 32 <= value <= 126:
            return repr(chr(value))

        return "'non-printable'"
