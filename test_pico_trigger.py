# test_pico_trigger.py

from __future__ import annotations

import sys

from driver.pico_driver import PicoDriver


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "COM14"

    sample_rate_hz = 100_000

    # Tổng cộng 5.000 sample:
    # 1.000 sample trước trigger
    # 4.000 sample sau trigger
    pre_samples = 1000
    post_samples = 4000

    # Firmware CH0 = GPIO2 = app CH1.
    trigger_channel = 0

    print(f"Opening Pico on {port}")
    print("Arming hardware trigger...")
    print("Waiting for FALLING edge on " "GPIO2 / app CH1")

    driver = PicoDriver(
        port=port,
        channel_mask=0xFF,
    )

    buffer = driver.capture_trigger(
        sample_rate_hz=sample_rate_hz,
        pre_samples=pre_samples,
        post_samples=post_samples,
        trigger_channel=trigger_channel,
        edge="falling",
        timeout_ms=20000,
    )

    trigger_sample = pre_samples

    print()
    print("Hardware trigger capture completed")
    print(f"sample_rate_hz = " f"{buffer.sample_rate_hz}")
    print(f"sample_count   = " f"{buffer.sample_count()}")
    print(f"trigger_sample = " f"{trigger_sample}")
    print(f"trigger_time   = " f"{trigger_sample / buffer.sample_rate_hz * 1000:.3f} ms")

    left = max(
        0,
        trigger_sample - 16,
    )
    right = min(
        buffer.sample_count(),
        trigger_sample + 32,
    )

    print()
    print("Raw bytes around trigger:")
    print(buffer.samples[left:right].tolist())

    for channel_index in range(buffer.channel_count):
        bits = (buffer.samples >> channel_index) & 1

        transitions = int((bits[1:] != bits[:-1]).sum())

        ones = int(bits.sum())

        print(
            f"CH{channel_index + 1}: "
            f"ones={ones}/"
            f"{buffer.sample_count()}, "
            f"transitions={transitions}"
        )

    # Kiểm tra cạnh xuống gần vị trí trigger.
    ch1 = buffer.samples & 0x01

    search_left = max(
        1,
        trigger_sample - 3,
    )
    search_right = min(
        buffer.sample_count(),
        trigger_sample + 4,
    )

    falling_edges = []

    for index in range(
        search_left,
        search_right,
    ):
        if ch1[index - 1] == 1 and ch1[index] == 0:
            falling_edges.append(index)

    print()

    if falling_edges:
        print("PASS: Falling edge found near " f"trigger position: {falling_edges}")
    else:
        print(
            "WARNING: No falling edge was found "
            "within ±3 samples of the expected "
            "trigger position"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
