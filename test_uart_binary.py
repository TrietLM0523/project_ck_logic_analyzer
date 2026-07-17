# test_uart_binary.py

from pathlib import Path

import numpy as np

from data.logic_sample_buffer import LogicSampleBuffer
from decoder.uart_decoder import UARTConfig, UARTDecoder

UART_FILE = Path(r"E:\WORK\pach_kha\ET\Embedded_Systems_and_Interfaces\uart_test.bin")


def main():
    if not UART_FILE.exists():
        print("File not found:")
        print(UART_FILE)
        return

    samples = np.fromfile(
        UART_FILE,
        dtype=np.uint8,
    )

    buffer = LogicSampleBuffer(
        samples=samples,
        sample_rate_hz=1_000_000,
        channel_count=8,
    )

    decoder = UARTDecoder()

    config = UARTConfig(
        rx_channel=6,  # Internal index 6 = physical CH7
        baudrate=9600,
        data_bits=8,
        parity="NONE",
        stop_bits=1,
        idle_high=True,
    )

    annotations = decoder.decode(
        buffer,
        config,
    )

    print("UART binary test")
    print("Sample rate:", buffer.sample_rate_hz)
    print("Sample count:", buffer.sample_count())
    print("Annotations:", len(annotations))
    print()

    decoded_text = []

    for annotation in annotations:
        print(
            f"{annotation.start_sample:6d} -> "
            f"{annotation.end_sample:6d} | "
            f"{annotation.text}"
        )

        if (
            not annotation.error
            and isinstance(annotation.value, int)
            and 32 <= annotation.value <= 126
        ):
            decoded_text.append(chr(annotation.value))

    print()
    print(
        "Decoded text:",
        "".join(decoded_text),
    )


if __name__ == "__main__":
    main()
