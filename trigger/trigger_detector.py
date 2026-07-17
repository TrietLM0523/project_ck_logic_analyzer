# trigger/trigger_detector.py

from __future__ import annotations

import numpy as np

from data.logic_sample_buffer import LogicSampleBuffer

VALID_TRIGGER_EDGES = {"rising", "falling", "either"}


def find_trigger_sample(
    buffer: LogicSampleBuffer,
    channel_index: int,
    edge: str,
    start_sample: int = 1,
) -> int | None:
    """
    Tìm cạnh trigger đầu tiên trong buffer đã capture.

    Đây là software trigger:
    - dữ liệu đã được thu xong trước
    - app tìm cạnh trong raw samples
    - waveform được căn theo vị trí cạnh tìm thấy

    Parameters
    ----------
    buffer:
        Dữ liệu capture.
    channel_index:
        Chỉ số nội bộ 0..7, tương ứng CH1..CH8.
    edge:
        "rising", "falling" hoặc "either".
    start_sample:
        Bỏ qua các cạnh trước sample này.
    """

    if buffer.sample_count() < 2:
        return None

    if not 0 <= channel_index < buffer.channel_count:
        raise ValueError(f"Trigger channel must be between 0 and " f"{buffer.channel_count - 1}.")

    normalized_edge = edge.strip().lower()

    if normalized_edge not in VALID_TRIGGER_EDGES:
        raise ValueError("Trigger edge must be rising, falling or either.")

    first_allowed_sample = max(1, int(start_sample))

    channel_values = (np.right_shift(buffer.samples, channel_index) & 1).astype(
        np.uint8, copy=False
    )

    previous_values = channel_values[:-1]
    current_values = channel_values[1:]

    if normalized_edge == "rising":
        transition_mask = (previous_values == 0) & (current_values == 1)
    elif normalized_edge == "falling":
        transition_mask = (previous_values == 1) & (current_values == 0)
    else:
        transition_mask = previous_values != current_values

    # Phần tử i của transition_mask mô tả cạnh giữa sample i và i+1.
    transition_samples = np.flatnonzero(transition_mask) + 1

    valid_samples = transition_samples[transition_samples >= first_allowed_sample]

    if valid_samples.size == 0:
        return None

    return int(valid_samples[0])
