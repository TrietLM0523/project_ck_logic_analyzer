# driver/pico_driver.py

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import numpy as np
import serial
from serial.tools import list_ports

from data.logic_sample_buffer import LogicSampleBuffer

MAX_RATE_HZ = 10_000_000
MAX_CAPTURE_SAMPLES = 65_536
MAX_PRETRIGGER_SAMPLES = 16_384
DEFAULT_BAUDRATE = 115_200

_RATE_RE = re.compile(r"\brate=(\d+)\b")
_TRIGGER_INDEX_RE = re.compile(r"\btrig_index=(\d+)\b")


class PicoDriverError(RuntimeError):
    """Raised when the Pico protocol or serial connection fails."""


@dataclass(frozen=True)
class PicoDeviceInfo:
    port: str
    description: str
    manufacturer: str | None
    serial_number: str | None
    vid: int | None
    pid: int | None


class _ProductProtocol:
    """
    Low-level protocol used by the current Pico product firmware.

    PC -> Pico:
        ASCII command followed by '\n'

    Pico -> PC:
        zero or more ASCII metadata lines
        BIN <payload_length>
        <payload_length raw bytes>
        END
    """

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = 5.0,
    ):
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=timeout,
                write_timeout=timeout,
            )
        except serial.SerialException as exc:
            raise PicoDriverError(f"Cannot open Pico serial port {port}: {exc}") from exc

        # Give USB CDC/firmware a short time to settle.
        time.sleep(0.2)
        self.ser.reset_input_buffer()

    def close(self) -> None:
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self) -> "_ProductProtocol":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def send_line(self, command: str) -> None:
        try:
            self.ser.write((command + "\n").encode("ascii"))
            self.ser.flush()
        except (UnicodeEncodeError, serial.SerialException) as exc:
            raise PicoDriverError(f"Failed to send command {command!r}: {exc}") from exc

    def read_line(self) -> str:
        try:
            return self.ser.readline().decode("ascii", errors="replace").strip()
        except serial.SerialException as exc:
            raise PicoDriverError(f"Failed while reading Pico metadata: {exc}") from exc

    def read_capture_block(self) -> tuple[list[str], bytes]:
        metadata: list[str] = []

        while True:
            line = self.read_line()

            # readline() returns an empty string on timeout.
            if not line:
                raise PicoDriverError("Timed out waiting for Pico capture metadata.")

            metadata.append(line)

            if line.startswith("ERR"):
                raise PicoDriverError(line)

            if not line.startswith("BIN "):
                continue

            parts = line.split()
            if len(parts) != 2:
                raise PicoDriverError(f"Invalid BIN header from Pico: {line!r}")

            try:
                payload_length = int(parts[1])
            except ValueError as exc:
                raise PicoDriverError(f"Invalid payload length in {line!r}") from exc

            if payload_length < 0:
                raise PicoDriverError(f"Negative payload length: {payload_length}")

            try:
                raw = self.ser.read(payload_length)
            except serial.SerialException as exc:
                raise PicoDriverError(f"Failed while reading capture payload: {exc}") from exc

            if len(raw) != payload_length:
                raise PicoDriverError(
                    f"Expected {payload_length} capture bytes, " f"received {len(raw)}."
                )

            tail = self.read_line()
            if not tail:
                # Some firmware revisions leave one blank line before END.
                tail = self.read_line()

            if tail != "END":
                raise PicoDriverError(f"Expected END after capture payload, got {tail!r}.")

            return metadata, raw


class PicoDriver:
    """
    Capture adapter for the custom Pico logic-analyzer firmware.

    Mapping returned to the desktop app:
        raw bit 0 -> CH1
        raw bit 1 -> CH2
        ...
        raw bit 7 -> CH8

    The first integration uses CAP_TIMER. The desktop application's existing
    software trigger can still operate on the returned LogicSampleBuffer.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        channel_mask: int = 0xFF,
    ):
        if not port:
            raise ValueError("Pico serial port must not be empty.")
        if not 0 < channel_mask <= 0xFF:
            raise ValueError("channel_mask must be between 0x01 and 0xFF.")

        self.port = port
        self.baudrate = int(baudrate)
        self.channel_mask = int(channel_mask)
        self.last_capture_metadata: list[str] = []
        self.last_trigger_index: int | None = None

    @staticmethod
    def scan() -> list[PicoDeviceInfo]:
        devices: list[PicoDeviceInfo] = []

        for port in list_ports.comports():
            devices.append(
                PicoDeviceInfo(
                    port=port.device,
                    description=port.description or "",
                    manufacturer=port.manufacturer,
                    serial_number=port.serial_number,
                    vid=port.vid,
                    pid=port.pid,
                )
            )

        return devices

    def read_info(self, timeout: float = 0.5) -> list[str]:
        with _ProductProtocol(
            port=self.port,
            baudrate=self.baudrate,
            timeout=timeout,
        ) as protocol:
            protocol.send_line("INFO")

            lines: list[str] = []
            deadline = time.monotonic() + 2.0

            while time.monotonic() < deadline:
                line = protocol.read_line()
                if not line:
                    continue

                lines.append(line)
                if line == "READY":
                    break

            if not lines:
                raise PicoDriverError("Pico returned no INFO response.")

            return lines

    def capture(
        self,
        sample_rate_hz: int,
        duration_ms: int,
    ) -> LogicSampleBuffer:
        sample_rate_hz = int(sample_rate_hz)
        duration_ms = int(duration_ms)

        if not 1 <= sample_rate_hz <= MAX_RATE_HZ:
            raise ValueError(f"sample_rate_hz must be between 1 and {MAX_RATE_HZ}.")
        if duration_ms <= 0:
            raise ValueError("duration_ms must be greater than zero.")

        sample_count = round(sample_rate_hz * duration_ms / 1000)

        if not 1 <= sample_count <= MAX_CAPTURE_SAMPLES:
            maximum_duration_ms = MAX_CAPTURE_SAMPLES * 1000 / sample_rate_hz
            raise ValueError(
                f"Requested {sample_count} samples, but Pico CAP_TIMER "
                f"supports at most {MAX_CAPTURE_SAMPLES}. "
                f"At {sample_rate_hz} Hz, use duration <= "
                f"{maximum_duration_ms:.3f} ms."
            )

        command = f"CAP_TIMER {sample_rate_hz} {sample_count} " f"0x{self.channel_mask:02x}"

        # Add margin for acquisition plus USB transfer.
        acquisition_seconds = sample_count / sample_rate_hz
        timeout = max(5.0, acquisition_seconds + 3.0)

        with _ProductProtocol(
            port=self.port,
            baudrate=self.baudrate,
            timeout=timeout,
        ) as protocol:
            protocol.send_line(command)
            metadata, raw = protocol.read_capture_block()
            self.last_capture_metadata = list(metadata)
            self.last_trigger_index = None

        actual_rate_hz = self._actual_rate_from_metadata(
            default_rate_hz=sample_rate_hz,
            metadata=metadata,
        )

        samples = np.frombuffer(raw, dtype=np.uint8).copy()

        if samples.size != sample_count:
            raise PicoDriverError(
                f"Pico returned {samples.size} samples, " f"but {sample_count} were requested."
            )

        return LogicSampleBuffer(
            samples=samples,
            sample_rate_hz=actual_rate_hz,
            channel_count=8,
        )

    def capture_trigger(
        self,
        sample_rate_hz: int,
        pre_samples: int,
        post_samples: int,
        trigger_channel: int,
        edge: str,
        timeout_ms: int = 3000,
    ) -> LogicSampleBuffer:
        """
        Capture bằng hardware trigger của Pico.

        trigger_channel:
            0 = firmware CH0 = GPIO2 = app CH1
            1 = firmware CH1 = GPIO3 = app CH2
            ...
            7 = firmware CH7 = GPIO9 = app CH8

        edge:
            rising
            falling
            either  -> được đổi thành "change" cho firmware
        """

        sample_rate_hz = int(sample_rate_hz)
        pre_samples = int(pre_samples)
        post_samples = int(post_samples)
        trigger_channel = int(trigger_channel)
        timeout_ms = int(timeout_ms)

        edge = str(edge).strip().lower()

        # UI hiện tại gọi là "either",
        # firmware của bạn fen gọi là "change".
        if edge == "either":
            firmware_edge = "change"
        else:
            firmware_edge = edge

        if not 1 <= sample_rate_hz <= MAX_RATE_HZ:
            raise ValueError(f"sample_rate_hz must be between " f"1 and {MAX_RATE_HZ}")

        if not 0 <= pre_samples <= MAX_PRETRIGGER_SAMPLES:
            raise ValueError(f"pre_samples must be between " f"0 and {MAX_PRETRIGGER_SAMPLES}")

        if post_samples < 1:
            raise ValueError("post_samples must be at least 1")

        total_samples = pre_samples + post_samples

        if total_samples > MAX_CAPTURE_SAMPLES:
            raise ValueError(
                f"Total trigger capture is {total_samples} samples, "
                f"but the Pico supports at most "
                f"{MAX_CAPTURE_SAMPLES}"
            )

        if not 0 <= trigger_channel <= 7:
            raise ValueError("trigger_channel must be between 0 and 7")

        allowed_edges = {
            "rising",
            "falling",
            "change",
            "high",
            "low",
        }

        if firmware_edge not in allowed_edges:
            raise ValueError(f"Unsupported trigger edge: {edge}")

        if timeout_ms < 1:
            raise ValueError("timeout_ms must be greater than zero")

        command = (
            f"CAP_TRIGGER "
            f"{sample_rate_hz} "
            f"{pre_samples} "
            f"{post_samples} "
            f"0x{self.channel_mask:02x} "
            f"{trigger_channel} "
            f"{firmware_edge} "
            f"{timeout_ms}"
        )

        acquisition_seconds = total_samples / sample_rate_hz

        # Chờ trigger + thời gian thu + thời gian truyền USB.
        serial_timeout = max(
            5.0,
            timeout_ms / 1000.0 + acquisition_seconds + 3.0,
        )

        with _ProductProtocol(
            port=self.port,
            baudrate=self.baudrate,
            timeout=serial_timeout,
        ) as protocol:
            protocol.send_line(command)
            metadata, raw = protocol.read_capture_block()

        # Lưu lại toàn bộ metadata của lần capture gần nhất.
        self.last_capture_metadata = list(metadata)

        # Đọc vị trí trigger thực tế do firmware báo.
        self.last_trigger_index = self._trigger_index_from_metadata(
            metadata=metadata,
            default_index=pre_samples,
        )

        actual_rate_hz = self._actual_rate_from_metadata(
            default_rate_hz=sample_rate_hz,
            metadata=metadata,
        )

        samples = np.frombuffer(
            raw,
            dtype=np.uint8,
        ).copy()

        if samples.size != total_samples:
            metadata_text = "\n".join(f"  {line}" for line in metadata)

            raise PicoDriverError(
                f"Pico returned {samples.size} samples, "
                f"but {total_samples} were requested.\n\n"
                f"Command:\n"
                f"  {command}\n\n"
                f"Firmware metadata:\n"
                f"{metadata_text}"
            )
        if self.last_trigger_index is None or not 0 <= self.last_trigger_index < samples.size:
            metadata_text = "\n".join(f"  {line}" for line in metadata)

            raise PicoDriverError(
                "Firmware returned an invalid "
                "trigger index: "
                f"{self.last_trigger_index}\n\n"
                f"Firmware metadata:\n"
                f"{metadata_text}"
            )

        return LogicSampleBuffer(
            samples=samples,
            sample_rate_hz=actual_rate_hz,
            channel_count=8,
        )

    @staticmethod
    def _trigger_index_from_metadata(
        metadata: list[str],
        default_index: int,
    ) -> int:
        """
        Đọc vị trí trigger thực tế từ metadata firmware.

        Ví dụ metadata:
            OK ... trig_index=7127 ...

        Nếu firmware cũ không có trig_index thì dùng
        pre_samples làm giá trị dự phòng.
        """

        for line in metadata:
            match = _TRIGGER_INDEX_RE.search(line)

            if match:
                return int(match.group(1))

        return int(default_index)

    @staticmethod
    def _actual_rate_from_metadata(
        default_rate_hz: int,
        metadata: list[str],
    ) -> int:
        for line in metadata:
            match = _RATE_RE.search(line)
            if match:
                return int(match.group(1))

        return default_rate_hz
