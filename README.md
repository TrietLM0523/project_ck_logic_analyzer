# Logic Analyzer App

A desktop logic-analyzer application built with Python and PyQt6. The app captures eight digital channels, renders waveforms, decodes SPI/I2C/UART traffic, measures timing, and stores reusable capture sessions.

## Main features

- Eight-channel digital waveform display (`CH1` to `CH8`)
- Zoom and horizontal pan
- Timing cursors with sample difference, time difference, and frequency
- Software edge trigger with configurable channel and pre-trigger view position
- SPI decoder with channel mapping and mode options
- I2C decoder with START, STOP, address, data, ACK, and NACK annotations
- UART decoder with configurable baud rate, data bits, parity, and stop bits
- Decode annotations displayed in both a table and directly over the waveform
- CSV export of decode results
- `.la` session save/load containing metadata, raw samples, and annotations
- Demo and Saleae-clone capture backends
- Driver boundary prepared for the Pico 2 product MCU backend

## Architecture

```text
Capture source
├── DemoDriver
├── SigrokCliDriver -> Saleae clone / fx2lafw
└── PicoDriver      -> Pico firmware (product MCU)
        |
        v
LogicSampleBuffer
├── WaveformView
├── Trigger detector
├── Timing cursors
├── SPI / I2C / UART decoders
└── Session / CSV export
```

All capture drivers return the same `LogicSampleBuffer`, so the waveform, decoders, trigger, cursors, and file formats are independent of the hardware backend.

## Channel representation

Each sample is stored as one unsigned byte:

```text
bit 0 -> CH1
bit 1 -> CH2
...
bit 7 -> CH8
```

For the Saleae clone through sigrok:

```text
D0 -> CH1
D1 -> CH2
...
D7 -> CH8
```

## Project structure

```text
.
├── main.py
├── config/
│   ├── app_config.py
│   └── runtime_config.py
├── data/
│   └── logic_sample_buffer.py
├── driver/
│   ├── demo_driver.py
│   ├── sigrok_cli_driver.py
│   └── pico_driver.py
├── decoder/
│   ├── decode_annotation.py
│   ├── spi_decoder.py
│   ├── i2c_decoder.py
│   └── uart_decoder.py
├── trigger/
│   └── trigger_detector.py
├── fileio/
│   ├── csv_exporter.py
│   └── la_session.py
└── ui/
    ├── waveform_view.py
    └── decoder_panel.py
```

## Requirements

- Python 3.11
- NumPy
- PyQt6
- `sigrok-cli` for Saleae-clone capture

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Configure sigrok-cli

The application resolves `sigrok-cli` in this order:

1. `LOGIC_ANALYZER_SIGROK_CLI` environment variable
2. `sigrok-cli` available in `PATH`
3. A project-local or sibling `sigrok_cli/sigrok-cli/sigrok-cli.exe` folder

PowerShell example:

```powershell
$env:LOGIC_ANALYZER_SIGROK_CLI = "C:\path\to\sigrok-cli.exe"
python main.py
```

## Run

```bash
python main.py
```

## Waveform controls

```text
Mouse wheel          Zoom around the pointer
Left drag            Pan horizontally
Shift + left click   Place Cursor A
Ctrl + left click    Place Cursor B
Right click          Clear timing cursors
Fit View             Display the full capture
```

## Saleae UART smoke test

Example wiring:

```text
Arduino GND -> Saleae GND
Arduino TX  -> selected Saleae channel
```

Recommended settings:

```text
Sample rate: 1 MHz
Duration:    200 ms
UART:        9600 baud, 8 data bits, no parity, 1 stop bit
```

## `.la` session format

A `.la` file is a ZIP container:

```text
capture.la
├── meta.json
├── samples.bin
└── annotations.csv
```

- `meta.json`: sample rate, sample count, channel count, and format metadata
- `samples.bin`: packed raw channel states
- `annotations.csv`: decoded protocol annotations

## Pico 2 product backend

The Pico 2 is the MCU core of the final logic-analyzer hardware. Its firmware captures GPIO samples, preferably using PIO/DMA or an equivalent deterministic mechanism, and sends packed samples to the desktop application. `PicoDriver` converts that stream into `LogicSampleBuffer`, allowing all existing desktop features to remain unchanged.
