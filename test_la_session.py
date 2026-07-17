from pathlib import Path

import numpy as np

from driver.demo_driver import DemoDriver
from decoder.uart_decoder import UARTConfig, UARTDecoder
from fileio.la_session import load_la_session, save_la_session


def main():
    output_path = Path("test_capture.la")

    driver = DemoDriver(sample_rate_hz=1_000_000)

    original_buffer = driver.capture(duration_ms=50)

    decoder = UARTDecoder()

    annotations = decoder.decode(
        original_buffer,
        UARTConfig(
            rx_channel=6,
            baudrate=9600,
            data_bits=8,
            parity="NONE",
            stop_bits=1,
            idle_high=True,
        ),
    )

    save_la_session(
        file_path=str(output_path),
        buffer=original_buffer,
        annotations=annotations,
    )

    loaded_buffer, loaded_annotations = load_la_session(str(output_path))

    assert loaded_buffer.sample_rate_hz == original_buffer.sample_rate_hz

    assert loaded_buffer.channel_count == original_buffer.channel_count

    assert np.array_equal(
        loaded_buffer.samples,
        original_buffer.samples,
    )

    assert len(loaded_annotations) == len(annotations)

    print("M7 session test passed")
    print(
        "Samples:",
        loaded_buffer.sample_count(),
    )
    print(
        "Annotations:",
        len(loaded_annotations),
    )
    print(
        "File:",
        output_path.resolve(),
    )


if __name__ == "__main__":
    main()
