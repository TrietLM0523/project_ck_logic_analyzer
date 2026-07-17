import csv
from collections.abc import Sequence
from pathlib import Path

from decoder.decode_annotation import DecodeAnnotation


def export_annotations_csv(
    file_path: str,
    annotations: Sequence[DecodeAnnotation],
    sample_rate_hz: int,
) -> int:
    """
    Xuất danh sách kết quả decode sang CSV.

    Trả về số annotation đã ghi.
    """

    if sample_rate_hz <= 0:
        raise ValueError("Sample rate must be greater than zero")

    output_path = Path(file_path)

    # utf-8-sig giúp Excel trên Windows đọc tiếng Việt ổn hơn.
    with output_path.open(
        mode="w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.writer(csv_file)

        writer.writerow(
            [
                "start_sample",
                "end_sample",
                "start_time_us",
                "end_time_us",
                "protocol",
                "type",
                "value",
                "text",
                "status",
                "error_reason",
            ]
        )

        for annotation in annotations:
            writer.writerow(
                [
                    annotation.start_sample,
                    annotation.end_sample,
                    f"{annotation.start_time_us(sample_rate_hz):.3f}",
                    f"{annotation.end_time_us(sample_rate_hz):.3f}",
                    annotation.protocol,
                    annotation.type,
                    annotation.value,
                    annotation.text,
                    "ERROR" if annotation.error else "OK",
                    annotation.error_reason,
                ]
            )

    return len(annotations)
