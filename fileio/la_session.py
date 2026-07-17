# fileio/la_session.py

import csv
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

import numpy as np

from config.app_config import CHANNEL_NAMES
from data.logic_sample_buffer import LogicSampleBuffer
from decoder.decode_annotation import DecodeAnnotation

SESSION_FORMAT = "logic-analyzer-session"
SESSION_VERSION = 1


def save_la_session(
    file_path: str,
    buffer: LogicSampleBuffer,
    annotations: list[DecodeAnnotation],
) -> None:
    """
    Lưu buffer và annotation vào một file .la.
    """

    if buffer.sample_rate_hz <= 0:
        raise ValueError("Sample rate must be greater than zero")

    output_path = Path(file_path)

    if output_path.suffix.lower() != ".la":
        output_path = output_path.with_suffix(".la")

    samples = np.asarray(
        buffer.samples,
        dtype=np.uint8,
    )

    metadata = {
        "format": SESSION_FORMAT,
        "version": SESSION_VERSION,
        "sample_rate_hz": buffer.sample_rate_hz,
        "sample_count": int(samples.size),
        "channel_count": buffer.channel_count,
        "channel_names": CHANNEL_NAMES[: buffer.channel_count],
        "sample_dtype": "uint8",
    }

    annotation_text = _annotations_to_csv(annotations)

    with ZipFile(
        output_path,
        mode="w",
        compression=ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "meta.json",
            json.dumps(
                metadata,
                indent=2,
                ensure_ascii=False,
            ),
        )

        archive.writestr(
            "samples.bin",
            samples.tobytes(order="C"),
        )

        archive.writestr(
            "annotations.csv",
            annotation_text,
        )


def load_la_session(
    file_path: str,
) -> tuple[LogicSampleBuffer, list[DecodeAnnotation]]:
    """
    Đọc file .la.

    Trả về:
        buffer, annotations
    """

    input_path = Path(file_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Session file does not exist: {input_path}")

    try:
        with ZipFile(input_path, mode="r") as archive:
            required_files = {
                "meta.json",
                "samples.bin",
                "annotations.csv",
            }

            available_files = set(archive.namelist())
            missing_files = required_files - available_files

            if missing_files:
                missing_text = ", ".join(sorted(missing_files))
                raise ValueError(f"Invalid .la session. Missing: {missing_text}")

            metadata = json.loads(archive.read("meta.json").decode("utf-8"))

            _validate_metadata(metadata)

            sample_bytes = archive.read("samples.bin")

            # copy() giúp mảng không còn phụ thuộc vùng bytes của file ZIP.
            samples = np.frombuffer(
                sample_bytes,
                dtype=np.uint8,
            ).copy()

            expected_count = int(metadata["sample_count"])

            if samples.size != expected_count:
                raise ValueError(
                    "Sample count does not match meta.json: "
                    f"expected {expected_count}, "
                    f"found {samples.size}"
                )

            annotation_text = archive.read("annotations.csv").decode("utf-8-sig")

    except BadZipFile as error:
        raise ValueError("The selected file is not a valid .la session") from error

    buffer = LogicSampleBuffer(
        samples=samples,
        sample_rate_hz=int(metadata["sample_rate_hz"]),
        channel_count=int(metadata["channel_count"]),
    )

    annotations = _annotations_from_csv(annotation_text)

    return buffer, annotations


def _annotations_to_csv(
    annotations: list[DecodeAnnotation],
) -> str:
    csv_stream = io.StringIO(newline="")

    field_names = [
        "start_sample",
        "end_sample",
        "protocol",
        "type",
        "value",
        "text",
        "error",
        "error_reason",
    ]

    writer = csv.DictWriter(
        csv_stream,
        fieldnames=field_names,
    )

    writer.writeheader()

    for annotation in annotations:
        writer.writerow(
            {
                "start_sample": annotation.start_sample,
                "end_sample": annotation.end_sample,
                "protocol": annotation.protocol,
                "type": annotation.type,
                "value": annotation.value,
                "text": annotation.text,
                "error": annotation.error,
                "error_reason": annotation.error_reason,
            }
        )

    return csv_stream.getvalue()


def _annotations_from_csv(
    csv_text: str,
) -> list[DecodeAnnotation]:
    annotations: list[DecodeAnnotation] = []

    reader = csv.DictReader(io.StringIO(csv_text))

    for row in reader:
        if not row:
            continue

        error_value = str(row.get("error", "")).lower()

        annotation = DecodeAnnotation(
            start_sample=int(row["start_sample"]),
            end_sample=int(row["end_sample"]),
            protocol=row.get("protocol", ""),
            type=row.get("type", ""),
            value=row.get("value", ""),
            text=row.get("text", ""),
            error=error_value
            in {
                "true",
                "1",
                "yes",
            },
            error_reason=row.get("error_reason", ""),
        )

        annotations.append(annotation)

    return annotations


def _validate_metadata(metadata: dict) -> None:
    if metadata.get("format") != SESSION_FORMAT:
        raise ValueError("Unsupported session format")

    if metadata.get("version") != SESSION_VERSION:
        raise ValueError("Unsupported session version: " f"{metadata.get('version')}")

    if metadata.get("sample_dtype") != "uint8":
        raise ValueError("Only uint8 samples are supported")

    sample_rate = int(metadata.get("sample_rate_hz", 0))
    sample_count = int(metadata.get("sample_count", -1))
    channel_count = int(metadata.get("channel_count", 0))

    if sample_rate <= 0:
        raise ValueError("Invalid sample rate in meta.json")

    if sample_count < 0:
        raise ValueError("Invalid sample count in meta.json")

    if not 1 <= channel_count <= 8:
        raise ValueError("Invalid channel count in meta.json")
