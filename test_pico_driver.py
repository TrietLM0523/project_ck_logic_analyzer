# test_pico_driver.py

from __future__ import annotations

import sys

from driver.pico_driver import PicoDriver


def main() -> int:
    print("Available serial ports:")
    for device in PicoDriver.scan():
        print(
            f"  {device.port}: {device.description} "
            f"(VID={device.vid}, PID={device.pid})"
        )

    port = sys.argv[1] if len(sys.argv) > 1 else "COM14"

    print(f"\nReading INFO from {port}...")
    driver = PicoDriver(port=port)

    info = driver.read_info()
    for line in info:
        print(f"  {line}")

    print("\nCapturing 5,000 samples at 100 kHz...")
    buffer = driver.capture(
        sample_rate_hz=100_000,
        duration_ms=50,
    )

    unique_values = sorted(set(buffer.samples.tolist()))
    print(f"sample_rate_hz = {buffer.sample_rate_hz}")
    print(f"sample_count   = {buffer.sample_count()}")
    print(f"duration       = {buffer.duration_seconds():.6f} s")
    print(f"first 32 bytes = {buffer.samples[:32].tolist()}")
    print(f"unique values  = {unique_values[:32]}")

    for channel_index in range(buffer.channel_count):
        bits = (
            (buffer.samples >> channel_index) & 1
        )
        transitions = int((bits[1:] != bits[:-1]).sum())
        ones = int(bits.sum())

        print(
            f"CH{channel_index + 1}: "
            f"ones={ones}/{buffer.sample_count()}, "
            f"transitions={transitions}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
