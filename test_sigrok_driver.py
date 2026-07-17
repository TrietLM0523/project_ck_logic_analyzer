# test_sigrok_driver.py

from decoder.uart_decoder import (
    UARTConfig,
    UARTDecoder,
)
from driver.sigrok_cli_driver import (
    SigrokCliDriver,
    SigrokCliError,
)

SIGROK_CLI_PATH = (
    r"E:\WORK\pach_kha\ET\Embedded_Systems_and_Interfaces" r"\sigrok_cli\sigrok-cli\sigrok-cli.exe"
)


def main():
    driver = SigrokCliDriver(executable=SIGROK_CLI_PATH)

    try:
        print("Scanning Saleae clone...")
        print(driver.scan())
        print()

        print("Capturing 200 ms at 1 MHz...")

        buffer = driver.capture(
            sample_rate_hz=1_000_000,
            duration_ms=200,
        )

    except (SigrokCliError, ValueError) as error:
        print()
        print("CAPTURE FAILED")
        print(error)
        return

    print("Capture completed.")
    print(
        "Sample rate:",
        buffer.sample_rate_hz,
    )
    print(
        "Sample count:",
        buffer.sample_count(),
    )
    print(
        "Duration:",
        f"{buffer.duration_seconds() * 1000:.3f} ms",
    )
    print()

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

    decoded_characters = []

    print(
        "Annotations:",
        len(annotations),
    )

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
            decoded_characters.append(chr(annotation.value))

    print()
    print(
        "Decoded text:",
        "".join(decoded_characters),
    )


if __name__ == "__main__":
    main()
