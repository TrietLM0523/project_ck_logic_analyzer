# driver/capture_driver.py

from typing import Protocol

from data.logic_sample_buffer import LogicSampleBuffer


class CaptureDriver(Protocol):
    """
    Interface chung cho mọi nguồn capture.

    DemoDriver, SigrokCliDriver và PicoDriver đều phải
    cung cấp method capture() theo cùng định dạng.
    """

    def capture(
        self,
        sample_rate_hz: int,
        duration_ms: int,
    ) -> LogicSampleBuffer: ...
