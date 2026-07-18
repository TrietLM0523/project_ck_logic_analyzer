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
DEFAULT_BAUDRATE = 115_200

_RATE_RE = re.compile(r"\brate=(\d+)\b")


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
            raise PicoDriverError(
                f"Cannot open Pico serial port {port}: {exc}"
            ) from exc

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
            raise PicoDriverError(
                f"Failed to send command {command!r}: {exc}"
            ) from exc

    def read_line(self) -> str:
        try:
            return (
                self.ser.readline()
                .decode("ascii", errors="replace")
                .strip()
            )
        except serial.SerialException as exc:
            raise PicoDriverError(
                f"Failed while reading Pico metadata: {exc}"
            ) from exc

    def read_capture_block(self) -> tuple[list[str], bytes]:
        metadata: list[str] = []

        while True:
            line = self.read_line()

            # readline() returns an empty string on timeout.
            if not line:
                raise PicoDriverError(
                    "Timed out waiting for Pico capture metadata."
                )

            metadata.append(line)

            if line.startswith("ERR"):
                raise PicoDriverError(line)

            if not line.startswith("BIN "):
                continue

            parts = line.split()
            if len(parts) != 2:
                raise PicoDriverError(
                    f"Invalid BIN header from Pico: {line!r}"
                )

            try:
                payload_length = int(parts[1])
            except ValueError as exc:
                raise PicoDriverError(
                    f"Invalid payload length in {line!r}"
                ) from exc

            if payload_length < 0:
                raise PicoDriverError(
                    f"Negative payload length: {payload_length}"
                )

            try:
                raw = self.ser.read(payload_length)
            except serial.SerialException as exc:
                raise PicoDriverError(
                    f"Failed while reading capture payload: {exc}"
                ) from exc

            if len(raw) != payload_length:
                raise PicoDriverError(
                    f"Expected {payload_length} capture bytes, "
                    f"received {len(raw)}."
                )

            tail = self.read_line()
            if not tail:
                # Some firmware revisions leave one blank line before END.
                tail = self.read_line()

            if tail != "END":
                raise PicoDriverError(
                    f"Expected END after capture payload, got {tail!r}."
                )

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
                raise PicoDriverError(
                    "Pico returned no INFO response."
                )

            return lines

    def capture(
        self,
        sample_rate_hz: int,
        duration_ms: int,
    ) -> LogicSampleBuffer:
        sample_rate_hz = int(sample_rate_hz)
        duration_ms = int(duration_ms)

        if not 1 <= sample_rate_hz <= MAX_RATE_HZ:
            raise ValueError(
                f"sample_rate_hz must be between 1 and {MAX_RATE_HZ}."
            )
        if duration_ms <= 0:
            raise ValueError("duration_ms must be greater than zero.")

        sample_count = round(
            sample_rate_hz * duration_ms / 1000
        )

        if not 1 <= sample_count <= MAX_CAPTURE_SAMPLES:
            maximum_duration_ms = (
                MAX_CAPTURE_SAMPLES * 1000 / sample_rate_hz
            )
            raise ValueError(
                f"Requested {sample_count} samples, but Pico CAP_TIMER "
                f"supports at most {MAX_CAPTURE_SAMPLES}. "
                f"At {sample_rate_hz} Hz, use duration <= "
                f"{maximum_duration_ms:.3f} ms."
            )

        command = (
            f"CAP_TIMER {sample_rate_hz} {sample_count} "
            f"0x{self.channel_mask:02x}"
        )

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

        actual_rate_hz = self._actual_rate_from_metadata(
            default_rate_hz=sample_rate_hz,
            metadata=metadata,
        )

        samples = np.frombuffer(raw, dtype=np.uint8).copy()

        if samples.size != sample_count:
            raise PicoDriverError(
                f"Pico returned {samples.size} samples, "
                f"but {sample_count} were requested."
            )

        return LogicSampleBuffer(
            samples=samples,
            sample_rate_hz=actual_rate_hz,
            channel_count=8,
        )

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
