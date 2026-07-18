"""
Safe serial-port probe for Raspberry Pi Pico / Arduino setups.

Default behavior:
- Lists all serial ports.
- Does NOT send any command.

Optional passive read:
    python tools/probe_pico_serial.py --port COM7 --read-seconds 3

This only reads bytes already emitted by the device and saves them to
pico_probe.bin. It does not attempt to guess the firmware protocol.
"""

from __future__ import annotations

import argparse
import string
import sys
import time
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:
    raise SystemExit(
        "pyserial is not installed.\n"
        "Install it with: python -m pip install pyserial"
    ) from exc


def format_optional_hex(value: int | None) -> str:
    return "N/A" if value is None else f"0x{value:04X}"


def list_serial_ports() -> list[str]:
    ports = sorted(list_ports.comports(), key=lambda item: item.device)
    print(f"Found {len(ports)} serial port(s).\n")

    devices: list[str] = []
    for index, port in enumerate(ports, start=1):
        devices.append(port.device)
        print(f"[{index}] {port.device}")
        print(f"    Description : {port.description or 'N/A'}")
        print(f"    Manufacturer: {port.manufacturer or 'N/A'}")
        print(f"    Product     : {port.product or 'N/A'}")
        print(f"    Serial no.  : {port.serial_number or 'N/A'}")
        print(
            "    VID:PID     : "
            f"{format_optional_hex(port.vid)}:{format_optional_hex(port.pid)}"
        )
        print(f"    HWID        : {port.hwid or 'N/A'}")
        print()

    return devices


def printable_preview(data: bytes, limit: int = 256) -> str:
    allowed = set(string.printable)
    chars: list[str] = []
    for byte in data[:limit]:
        char = chr(byte)
        chars.append(char if char in allowed and char not in "\x0b\x0c" else ".")
    return "".join(chars)


def passive_read(
    port_name: str,
    baudrate: int,
    read_seconds: float,
    output_path: Path,
) -> None:
    if read_seconds <= 0:
        raise ValueError("--read-seconds must be greater than 0.")

    ser = serial.Serial(
        port=None,
        baudrate=baudrate,
        timeout=0.05,
        write_timeout=1,
    )
    ser.dtr = False
    ser.rts = False
    ser.port = port_name

    print(f"Opening {port_name} at {baudrate} baud for passive read...")
    print("No command will be transmitted.")

    try:
        ser.open()
        deadline = time.monotonic() + read_seconds
        captured = bytearray()

        while time.monotonic() < deadline:
            waiting = ser.in_waiting
            chunk = ser.read(waiting if waiting > 0 else 1)
            if chunk:
                captured.extend(chunk)

        data = bytes(captured)
        output_path.write_bytes(data)

        print(f"\nCaptured {len(data)} byte(s).")
        print(f"Saved raw bytes to: {output_path.resolve()}")

        if not data:
            print(
                "\nNo bytes arrived. This does not prove the port is wrong. "
                "The firmware may wait for a command, may use another baud rate, "
                "or may communicate through physical UART pins instead of USB CDC."
            )
            return

        preview = data[:256]
        print("\nFirst bytes in hexadecimal:")
        print(" ".join(f"{byte:02X}" for byte in preview))

        print("\nPrintable preview:")
        print(printable_preview(data))

    except serial.SerialException as exc:
        raise SystemExit(f"Serial error on {port_name}: {exc}") from exc
    finally:
        if ser.is_open:
            ser.close()


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List serial ports and optionally passively read one port."
    )
    parser.add_argument(
        "--port",
        help="Serial port to read, for example COM7. Omit to only list ports.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Baud rate for passive read. Default: 115200.",
    )
    parser.add_argument(
        "--read-seconds",
        type=float,
        default=3.0,
        help="Passive read duration in seconds. Default: 3.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pico_probe.bin"),
        help="Raw output file. Default: pico_probe.bin.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    list_serial_ports()

    if args.port:
        passive_read(
            port_name=args.port,
            baudrate=args.baud,
            read_seconds=args.read_seconds,
            output_path=args.output,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
