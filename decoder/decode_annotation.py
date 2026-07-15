# decoder/decode_annotation.py

from dataclasses import dataclass


@dataclass
class DecodeAnnotation:
    start_sample: int
    end_sample: int

    protocol: str
    type: str
    value: str
    text: str

    error: bool = False
    error_reason: str = ""

    def start_time_us(self, sample_rate_hz: int) -> float:
        return self.start_sample * 1_000_000.0 / sample_rate_hz

    def end_time_us(self, sample_rate_hz: int) -> float:
        return self.end_sample * 1_000_000.0 / sample_rate_hz