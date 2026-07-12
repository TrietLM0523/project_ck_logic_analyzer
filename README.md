# Logic Analyzer App

Ứng dụng phân tích tín hiệu logic đơn giản, xây dựng bằng Python + PyQt6, phục vụ đồ án Hệ thống nhúng.

Mục tiêu của project là xây dựng một logic analyzer app có khả năng hiển thị waveform logic 8 kênh CH1 → CH8, hỗ trợ zoom/pan theo thời gian, giải mã các giao thức cơ bản gồm SPI, I2C, UART, hiển thị kết quả decode, lưu/mở session capture, và hỗ trợ nhiều nguồn dữ liệu khác nhau.

Nguồn dữ liệu dự kiến gồm:

- `DemoDriver`: dữ liệu giả để test không cần phần cứng.
- `Saleae clone` qua sigrok-cli/PulseView: dùng logic analyzer hiện tại, loại cần cài driver bằng Zadig.
- `Raspberry Pi Pico 2`: mục tiêu phần cứng chính của project, dùng làm lõi capture logic analyzer.

---

## Channel Mapping

Ứng dụng dùng cách đánh số kênh theo logic analyzer thật: CH1 đến CH8.

Trong dữ liệu nội bộ, mỗi sample là 1 byte:

```text
bit 0 = CH1
bit 1 = CH2
bit 2 = CH3
bit 3 = CH4
bit 4 = CH5
bit 5 = CH6
bit 6 = CH7
bit 7 = CH8
```

Mapping demo mặc định:

```text
CH1 = SPI CS
CH2 = SPI MOSI
CH3 = SPI MISO
CH4 = SPI SCK

CH5 = I2C SDA
CH6 = I2C SCL

CH7 = UART TX/RX
CH8 = unused
```

Lưu ý: trong PulseView, nhiều thiết bị hiển thị zero-based như D0–D7. Khi đó thường tương ứng:

```text
CH1 physical = D0 in PulseView
CH2 physical = D1 in PulseView
CH3 physical = D2 in PulseView
CH4 physical = D3 in PulseView
CH5 physical = D4 in PulseView
CH6 physical = D5 in PulseView
CH7 physical = D6 in PulseView
CH8 physical = D7 in PulseView
```

---

## Project Structure

```text
Logic_Analyzer_App/
├─ main.py
├─ README.md
├─ .gitignore
├─ config/
│  ├─ __init__.py
│  └─ app_config.py
├─ data/
│  ├─ __init__.py
│  └─ logic_sample_buffer.py
├─ driver/
│  ├─ __init__.py
│  └─ demo_driver.py
├─ decoder/
│  └─ __init__.py
├─ ui/
│  ├─ __init__.py
│  └─ waveform_view.py
├─ fileio/
│  └─ __init__.py
└─ GUIDE_logic_analyzer_app.md
```

---

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `config/` | Cấu hình chung: số kênh, tên kênh, sample rate mặc định |
| `data/` | Cấu trúc dữ liệu sample logic |
| `driver/` | Nguồn dữ liệu: demo, sigrok/Saleae clone, Pico 2 |
| `decoder/` | Thuật toán giải mã SPI/I2C/UART |
| `ui/` | Giao diện và waveform view |
| `fileio/` | Save/load session, export CSV |
| `main.py` | Entry point của ứng dụng |

Khi cần sửa:

| Câu hỏi | File/module cần sửa |
|---|---|
| Đổi màu waveform | `ui/waveform_view.py`, hàm `_channel_color()` |
| Đổi số kênh | `config/app_config.py` và `data/logic_sample_buffer.py` |
| Đổi tên CH1, CH2... | `config/app_config.py` |
| Sửa cách vẽ waveform | `ui/waveform_view.py` |
| Sửa zoom/pan | `ui/waveform_view.py`, các hàm `wheelEvent`, `mouseMoveEvent` |
| Sửa thuật toán SPI | `decoder/spi_decoder.py` |
| Sửa thuật toán I2C | `decoder/i2c_decoder.py` |
| Sửa thuật toán UART | `decoder/uart_decoder.py` |
| Thêm Pico 2 | `driver/pico_driver.py` |
| Thêm Saleae clone/sigrok | `driver/sigrok_cli_driver.py` |
| Sửa lưu/mở file | `fileio/session_writer.py`, `fileio/session_reader.py` |
| Sửa export CSV | `fileio/csv_exporter.py` |

---

## How to Run

Tạo môi trường conda:

```bash
conda create -n logic_analyzer python=3.11 -y
conda activate logic_analyzer
python -m pip install --upgrade pip
pip install PyQt6 numpy
```

Chạy app:

```bash
python main.py
```

Nếu VS Code báo không tìm thấy PyQt6 nhưng terminal chạy được, chọn lại interpreter:

```text
Ctrl + Shift + P
Python: Select Interpreter
Chọn env logic_analyzer
```

Có thể kiểm tra Python đang dùng bằng:

```bash
where python
python -c "import sys; print(sys.executable)"
python -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')"
```

---

## Hardware Test Plan

### Option 1: DemoDriver

Không cần phần cứng. App tự sinh dữ liệu giả:

```text
SPI  : 0x55, 0xAA, 0x3C, 0xC3
I2C  : Address 0x3C Write, data 00 55 AA 12 34
UART : HELLO
```

Mục đích:

- Test waveform.
- Test decoder.
- Test save/load.
- Test export CSV.
- Không phụ thuộc phần cứng thật.

### Option 2: Saleae Clone + sigrok/PulseView

Dùng logic analyzer clone 8 kênh hiện tại.

Yêu cầu:

- Cài driver bằng Zadig nếu cần.
- Test capture bằng PulseView trước.
- Mapping vật lý vẫn dùng CH1–CH8.
- Sau này có thể tạo `SigrokCliDriver` hoặc `SaleaeCloneDriver` để đưa dữ liệu về `LogicSampleBuffer`.

SPI test wiring:

```text
Arduino D10 -> CH1  // CS
Arduino D11 -> CH2  // MOSI
Arduino D12 -> CH3  // MISO
Arduino D13 -> CH4  // SCK
Arduino GND -> GND
```

I2C test wiring:

```text
Arduino A4 -> CH5  // SDA
Arduino A5 -> CH6  // SCL
Arduino GND -> GND
```

UART test wiring:

```text
Arduino TX / software TX -> CH7
Arduino GND              -> GND
```

### Option 3: Raspberry Pi Pico 2

Mục tiêu cuối của project là dùng Raspberry Pi Pico 2 làm lõi capture.

Hướng thiết kế:

```text
Pico 2 firmware captures digital samples
        ↓
PC app receives sample stream
        ↓
Convert to LogicSampleBuffer
        ↓
Waveform renderer + SPI/I2C/UART decoder
```

Điểm quan trọng: app không phụ thuộc nguồn dữ liệu cụ thể. DemoDriver, Saleae/sigrok và PicoDriver đều phải trả về cùng kiểu `LogicSampleBuffer`.

---

## Decoder Design

Decode là tính năng bắt buộc của app.

Decoder đầu vào:

```text
LogicSampleBuffer
```

Decoder đầu ra:

```text
DecodeAnnotation[]
```

Dự kiến hỗ trợ 3 decoder mặc định:

- SPI
- I2C
- UART

### SPI Default Config

```text
CS   = CH1
MOSI = CH2
MISO = CH3
SCK  = CH4
Mode = 0
Bit order = MSB first
Word size = 8
CS active = LOW
Display = HEX
```

SPI decoder hoạt động bằng cách:

- Chỉ decode khi CS active.
- Với Mode 0, đọc MOSI/MISO tại cạnh lên của SCK.
- Gom đủ 8 bit thành 1 byte.
- Hiển thị dạng hex, ví dụ `0x55`, `0xAA`.

### I2C Default Config

```text
SDA = CH5
SCL = CH6
Address mode = 7-bit
Display = HEX
```

I2C decoder hoạt động bằng cách:

- Tìm START: SDA xuống LOW khi SCL đang HIGH.
- Tìm STOP: SDA lên HIGH khi SCL đang HIGH.
- Đọc SDA tại cạnh lên của SCL.
- Mỗi byte gồm 8 bit data + 1 bit ACK/NACK.
- Byte đầu sau START được hiểu là address + R/W bit.

### UART Default Config

```text
RX = CH7
Baudrate = 9600
Data bits = 8
Parity = None
Stop bits = 1
Idle = HIGH
Display = HEX/ASCII
```

UART decoder hoạt động bằng cách:

- Tìm start bit: tín hiệu từ HIGH xuống LOW.
- Dựa vào baudrate để tính `samples_per_bit`.
- Lấy mẫu ở giữa mỗi bit.
- UART 8N1 gồm 1 start bit, 8 data bit, 1 stop bit.
- Data bit gửi theo thứ tự LSB first.

---

## Why Decode Can Be Wrong

Decoder có thể sai do:

- Chọn sai channel.
- Sample rate quá thấp.
- SPI sai CPOL/CPHA hoặc bit order.
- SPI chọn sai CS active LOW/HIGH.
- I2C nhầm SDA/SCL.
- I2C thiếu pull-up.
- UART sai baudrate/parity/stop bit.
- Capture thiếu đầu/cuối frame.
- Nhiễu hoặc chưa nối GND chung.

Mục tiêu của app không chỉ decode được, mà còn giúp người dùng hiểu tại sao decode sai.

Ví dụ warning nên có trong app:

```text
SPI warning: incomplete word before CS inactive.
I2C warning: START found but no STOP condition.
UART warning: stop bit is LOW, possible baudrate mismatch.
```

---

## Session File Design

Dự kiến dùng file session dạng ZIP container:

```text
capture.la
├─ meta.json
├─ samples.bin
└─ annotations.csv
```

Trong đó:

- `meta.json`: sample rate, số kênh, tên kênh.
- `samples.bin`: raw sample logic, mỗi sample 1 byte cho 8 kênh.
- `annotations.csv`: kết quả decode.

Lý do thiết kế như vậy:

- Metadata đọc được bằng mắt.
- Raw sample lưu binary cho nhẹ.
- Annotation lưu CSV để dễ kiểm tra bằng Excel.
- Dạng container giống nhiều file hiện đại như `.docx`, `.epub`, `.sr`.

---

## Data Representation

Mỗi sample là một byte `uint8`.

Ví dụ:

```text
sample = 0b01110001
```

Tương ứng:

```text
bit 0 = CH1 = 1
bit 1 = CH2 = 0
bit 2 = CH3 = 0
bit 3 = CH4 = 0
bit 4 = CH5 = 1
bit 5 = CH6 = 1
bit 6 = CH7 = 1
bit 7 = CH8 = 0
```

Nghĩa là:

```text
CH1 SPI CS idle HIGH
CH2 SPI MOSI idle LOW
CH3 SPI MISO idle LOW
CH4 SPI SCK idle LOW
CH5 I2C SDA idle HIGH
CH6 I2C SCL idle HIGH
CH7 UART idle HIGH
CH8 unused LOW
```

---

## Development Roadmap

### Milestone 1: Core Data + DemoDriver

- Tạo `LogicSampleBuffer`.
- Tạo `DemoDriver`.
- Sinh dữ liệu giả SPI/I2C/UART.
- In thông tin sample ra GUI.

### Milestone 2: Waveform View

- Vẽ waveform 8 kênh.
- Zoom bằng chuột lăn.
- Pan bằng kéo chuột.
- Hiển thị grid thời gian.

### Milestone 3: Decoder Framework

- Tạo `DecodeAnnotation`.
- Tạo interface/base class cho decoder.
- Tạo bảng kết quả decode.
- Cho chọn SPI/I2C/UART.

### Milestone 4: SPI Decoder

- Decode SPI Mode 0.
- Config CS/MOSI/MISO/SCK.
- Hiển thị data dạng hex.

### Milestone 5: I2C Decoder

- Detect START/STOP.
- Decode address + R/W.
- Decode data + ACK/NACK.

### Milestone 6: UART Decoder

- Decode UART 8N1.
- Config baudrate.
- Hiển thị hex/ASCII.

### Milestone 7: Export CSV

- Export kết quả decode ra CSV.
- Có start/end time, protocol, type, value, text.

### Milestone 8: Save/Load Session

- Lưu `meta.json`.
- Lưu `samples.bin`.
- Lưu `annotations.csv`.
- Đóng gói thành `.la`.

### Milestone 9: Hardware Drivers

- `SigrokCliDriver` cho Saleae clone.
- `PicoDriver` cho Raspberry Pi Pico 2.

---

## Defense Notes

### Vì sao dùng `__init__.py`?

`__init__.py` giúp Python nhận diện thư mục là package. Nhờ đó project có thể tách thành các module như `driver`, `data`, `decoder`, `ui` và import rõ ràng.

### Vì sao dùng `LogicSampleBuffer`?

`LogicSampleBuffer` là lớp dữ liệu trung gian chuẩn. Mọi nguồn dữ liệu như DemoDriver, Saleae clone hoặc Pico 2 đều được chuyển về cùng định dạng này. Nhờ đó waveform renderer và decoder không phụ thuộc phần cứng cụ thể.

### Vì sao mỗi sample là 1 byte?

Logic analyzer hiện tại có 8 kênh, nên có thể lưu trạng thái 8 kênh trong 1 byte. Cách này tiết kiệm bộ nhớ và dễ xử lý bit.

### Vì sao cần decoder?

Waveform chỉ cho thấy tín hiệu 0/1 theo thời gian. Decoder giúp chuyển chuỗi bit thành thông tin có ý nghĩa như byte SPI, address/data I2C hoặc ký tự UART.

### Vì sao decoder có thể sai?

Vì decoder phụ thuộc vào sample rate, mapping kênh và tham số giao thức. Nếu chọn sai kênh, sample rate quá thấp, sai SPI mode hoặc sai baudrate UART thì byte decode sẽ sai.

### Vì sao chọn Python + PyQt6?

Python giúp phát triển nhanh, dễ thử thuật toán decoder. PyQt6 hỗ trợ GUI desktop và vẽ waveform bằng QPainter. Nếu PyQt6 lỗi môi trường, có thể dự phòng PyQt5 bằng lớp tương thích.

### Vì sao vẫn dùng Saleae clone nếu mục tiêu là Pico 2?

Saleae clone qua PulseView/sigrok là nguồn dữ liệu thật để test sớm. Pico 2 là mục tiêu phần cứng cuối. Vì app tách driver riêng, việc đổi nguồn capture không ảnh hưởng decoder và UI.

---

## License / Notes

Project phục vụ mục đích học tập và đồ án. Một số ý tưởng kiến trúc tham khảo từ sigrok/PulseView, nhưng code được xây dựng lại theo module đơn giản để dễ hiểu và bảo vệ.