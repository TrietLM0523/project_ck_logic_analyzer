# driver/sigrok_cli_driver.py

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from data.logic_sample_buffer import LogicSampleBuffer


class SigrokCliError(RuntimeError):
    """
    Lỗi xảy ra khi gọi sigrok-cli hoặc thu dữ liệu.
    """


class SigrokCliDriver:
    """
    Thu dữ liệu từ Saleae clone thông qua sigrok-cli.

    Mapping:

        sigrok D0 -> project CH1 -> bit 0
        sigrok D1 -> project CH2 -> bit 1
        ...
        sigrok D7 -> project CH8 -> bit 7
    """

    CHANNELS = "D0,D1,D2,D3,D4,D5,D6,D7"

    def __init__(
        self,
        executable: str = "sigrok-cli",
        hardware_driver: str = "fx2lafw",
    ):
        self.executable = executable
        self.hardware_driver = hardware_driver
        self.channel_count = 8

    def find_executable(self) -> str:
        """
        Trả về đường dẫn thực tế của sigrok-cli.exe.
        """

        executable_path = Path(self.executable)

        # Trường hợp truyền đường dẫn đầy đủ.
        if executable_path.is_file():
            return str(executable_path.resolve())

        # Trường hợp sigrok-cli đã nằm trong PATH.
        discovered_path = shutil.which(self.executable)

        if discovered_path is None:
            raise SigrokCliError(
                "sigrok-cli was not found. " "Provide the full path to sigrok-cli.exe."
            )

        return discovered_path

    def scan(self) -> str:
        """
        Kiểm tra Saleae clone có được sigrok nhận diện không.
        """

        executable = self.find_executable()

        command = [
            executable,
            "--driver",
            self.hardware_driver,
            "--scan",
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        output = self._combine_output(completed)

        if completed.returncode != 0:
            raise SigrokCliError("sigrok-cli scan failed.\n\n" + output)

        return output

    def capture(
        self,
        sample_rate_hz: int,
        duration_ms: int,
    ) -> LogicSampleBuffer:
        """
        Thu dữ liệu từ Saleae clone.

        Ví dụ:

            sample_rate_hz = 1_000_000
            duration_ms = 200

        sẽ tạo:

            sample_count = 200_000
        """

        if sample_rate_hz <= 0:
            raise ValueError("Sample rate must be greater than zero.")

        if duration_ms <= 0:
            raise ValueError("Capture duration must be greater than zero.")

        executable = self.find_executable()

        sample_count = round(sample_rate_hz * duration_ms / 1000)

        if sample_count <= 0:
            raise ValueError("The requested capture contains no samples.")

        with tempfile.TemporaryDirectory(prefix="logic_analyzer_") as temporary_directory:
            output_path = Path(temporary_directory) / "capture.bin"

            command = [
                executable,
                "--driver",
                self.hardware_driver,
                "--config",
                f"samplerate={sample_rate_hz}",
                "--samples",
                str(sample_count),
                "--channels",
                self.CHANNELS,
                "--output-format",
                "binary",
                "--output-file",
                str(output_path),
            ]

            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._capture_timeout(duration_ms),
                check=False,
            )

            terminal_output = self._combine_output(completed)

            if completed.returncode != 0:
                raise SigrokCliError("sigrok-cli capture failed.\n\n" + terminal_output)

            if not output_path.exists():
                raise SigrokCliError("sigrok-cli completed but did not " "create the capture file.")

            samples = np.fromfile(
                output_path,
                dtype=np.uint8,
            )

        if samples.size == 0:
            raise SigrokCliError("The capture file contains no samples.")

        if samples.size != sample_count:
            raise SigrokCliError(
                "Unexpected sample count: "
                f"requested {sample_count}, "
                f"received {samples.size}."
            )

        return LogicSampleBuffer(
            samples=samples.copy(),
            sample_rate_hz=sample_rate_hz,
            channel_count=self.channel_count,
        )

    @staticmethod
    def _capture_timeout(
        duration_ms: int,
    ) -> float:
        """
        Thời gian chờ gồm thời gian capture và thời gian
        mở USB, nạp firmware, ghi file.
        """

        duration_seconds = duration_ms / 1000

        return max(
            10.0,
            duration_seconds + 8.0,
        )

    @staticmethod
    def _combine_output(
        completed: subprocess.CompletedProcess,
    ) -> str:
        outputs = []

        if completed.stdout:
            outputs.append(completed.stdout.strip())

        if completed.stderr:
            outputs.append(completed.stderr.strip())

        if not outputs:
            return "(sigrok-cli produced no terminal output)"

        return "\n".join(outputs)
