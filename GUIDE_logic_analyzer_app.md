# GUIDE.md — Logic Analyzer App dùng Raspberry Pi Pico 2

## 0. Mục tiêu chính

Xây dựng một app Logic Analyzer đơn giản kiểu PulseView/sigrok, nhưng dễ hiểu để bảo vệ. App dùng **Python + Qt GUI** ở phía PC và định hướng cuối cùng là dùng **Raspberry Pi Pico 2 làm lõi thu tín hiệu logic**.

Mục tiêu không phải copy nguyên PulseView, mà là tự xây pipeline cơ bản:

```text
Pico 2 / Demo data / file input
        ↓
Capture session
        ↓
SampleBuffer 8 kênh
        ↓
Waveform renderer
        ↓
Cursor / ruler
        ↓
Protocol decoder: SPI / I2C / UART
        ↓
Annotation table + export CSV + save session
```

Logic analyzer của tôi dùng nhãn kênh **CH1 → CH8**, không dùng CH0 → CH7 khi hướng dẫn cắm dây. Nếu PulseView hiện D0 → D7 thì mapping thường là:

```text
CH1 vật lý → D0 trong PulseView
CH2 vật lý → D1
CH3 vật lý → D2
CH4 vật lý → D3
CH5 vật lý → D4
CH6 vật lý → D5
CH7 vật lý → D6
CH8 vật lý → D7
```

---

## 1. Stack đã chọn

Ưu tiên dùng:

```text
Language: Python
GUI: PyQt6
Fallback: PyQt5 nếu PyQt6 lỗi dai
Environment: conda
```

Nên có file `qt_compat.py` để code chạy được cả PyQt6 và PyQt5.

Tạo môi trường:

```bat
conda create -n logic_analyzer python=3.11 -y
conda activate logic_analyzer
python -m pip install --upgrade pip
pip install PyQt6 numpy
```

Test PyQt6:

```bat
python -c "from PyQt6.QtWidgets import QApplication, QLabel; import sys; app=QApplication(sys.argv); w=QLabel('PyQt6 OK'); w.show(); app.exec()"
```

Nếu PyQt6 lỗi, chuyển PyQt5:

```bat
pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip -y
pip install PyQt5 numpy
```

Test PyQt5:

```bat
python -c "from PyQt5.QtWidgets import QApplication, QLabel; import sys; app=QApplication(sys.argv); w=QLabel('PyQt5 OK'); w.show(); app.exec_()"
```

---

## 2. Tính năng MVP bắt buộc

App bản đầu cần đạt:

```text
1. Hiển thị 8 kênh CH1 → CH8
2. Vẽ waveform HIGH/LOW theo thời gian
3. Có zoom / pan cơ bản
4. Có cursor A/B đo Δt và tần số
5. Có cấu hình sample rate
6. Có panel chọn decoder
7. Có 3 decoder mặc định giống tinh thần sigrok:
   - SPI
   - I2C
   - UART
8. Có annotation trên waveform hoặc bảng decode
9. Có export kết quả decode ra CSV
10. Có save/load session đơn giản
```

Decode là tính năng bắt buộc, không phải optional. Kể cả decode sai thì app cần giúp hiểu tại sao sai.

---

## 3. Package/module đề xuất

Cấu trúc project:

```text
logic_analyzer_app/
├─ main.py
├─ qt_compat.py
├─ config/
│  ├─ app_config.py
│  ├─ channel_config.py
│  └─ theme.py
├─ core/
│  ├─ capture_config.py
│  ├─ capture_session.py
│  └─ time_base.py
├─ data/
│  ├─ logic_sample_buffer.py
│  ├─ sample_chunk.py
│  ├─ segment_builder.py
│  └─ edge_finder.py
├─ driver/
│  ├─ analyzer_driver.py
│  ├─ demo_driver.py
│  ├─ pico_driver.py
│  └─ sigrok_cli_driver.py
├─ decoder/
│  ├─ protocol_decoder.py
│  ├─ decode_annotation.py
│  ├─ spi_decoder.py
│  ├─ i2c_decoder.py
│  └─ uart_decoder.py
├─ render/
│  ├─ waveform_renderer.py
│  ├─ grid_renderer.py
│  ├─ cursor_renderer.py
│  └─ annotation_renderer.py
├─ fileio/
│  ├─ session_writer.py
│  ├─ session_reader.py
│  └─ csv_exporter.py
└─ ui/
   ├─ main_window.py
   ├─ waveform_view.py
   ├─ decoder_panel.py
   ├─ channel_panel.py
   └─ status_bar.py
```

---

## 4. Thầy hỏi sửa gì thì sửa ở đâu

| Câu hỏi/sửa đổi | Module/file cần sửa |
|---|---|
| Đổi màu waveform | `config/theme.py`, `render/waveform_renderer.py` |
| Đổi màu nền/grid | `config/theme.py`, `render/grid_renderer.py` |
| Đổi số kênh 8 → 16 | `config/app_config.py`, `data/logic_sample_buffer.py`, UI channel panel |
| Đổi tên CH1 thành CS | `config/channel_config.py`, `ui/channel_panel.py` |
| Đổi sample rate | `core/capture_config.py`, `ui/main_window.py` hoặc `ui/capture_control_panel.py` |
| Sửa công thức đổi sample sang thời gian | `core/time_base.py` |
| Sửa cách lấy bit của kênh | `data/logic_sample_buffer.py` |
| Sửa thuật toán SPI | `decoder/spi_decoder.py` |
| Sửa thuật toán I2C | `decoder/i2c_decoder.py` |
| Sửa thuật toán UART | `decoder/uart_decoder.py` |
| Sửa bảng kết quả decode | `ui/decoder_panel.py` |
| Sửa vẽ annotation | `render/annotation_renderer.py` |
| Sửa zoom/pan | `ui/waveform_view.py` |
| Sửa save/load file | `fileio/session_writer.py`, `fileio/session_reader.py` |
| Sửa export CSV | `fileio/csv_exporter.py` |
| Sửa nguồn dữ liệu giả | `driver/demo_driver.py` |
| Sửa giao tiếp Pico 2 | `driver/pico_driver.py` |
| Sửa gọi sigrok-cli | `driver/sigrok_cli_driver.py` |
| Lỗi PyQt6/PyQt5 | `qt_compat.py` |

Câu bảo vệ nên nhớ:

> App được tách thành các lớp driver, data, decoder, renderer và UI. Driver lấy dữ liệu, data lưu sample, decoder giải mã giao thức, renderer vẽ waveform, UI chỉ điều khiển và hiển thị. Vì vậy khi cần sửa màu, số kênh, thuật toán decoder hay định dạng file thì sửa đúng module tương ứng.

---

## 5. Dữ liệu nội bộ

Vì logic analyzer có 8 kênh CH1 → CH8, mỗi sample nên lưu bằng 1 byte:

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

Ví dụ:

```text
sample = 0b00001001
```

nghĩa là:

```text
CH1 = 1
CH2 = 0
CH3 = 0
CH4 = 1
CH5 = 0
CH6 = 0
CH7 = 0
CH8 = 0
```

Hàm lõi:

```python
def get_bit(sample_byte: int, channel_index: int) -> int:
    return (sample_byte >> channel_index) & 1
```

Mapping index:

```text
CH1 → channel_index = 0
CH2 → channel_index = 1
...
CH8 → channel_index = 7
```

Công thức thời gian:

```text
time_seconds = sample_index / sample_rate_hz
time_us = sample_index * 1_000_000 / sample_rate_hz
```

---

## 6. Save/load session

Dùng file session tự chế dạng ZIP, ví dụ:

```text
capture.la
├─ meta.json
├─ samples.bin
└─ annotations.csv
```

Trong đó:

```text
meta.json       lưu sampleRate, số kênh, tên kênh, version format
samples.bin     lưu raw sample dạng byte, mỗi byte = trạng thái CH1-CH8
annotations.csv lưu kết quả decode
```

Format này giống ý tưởng `.sr` của sigrok: một file container nén chứa metadata + dữ liệu nhị phân.

Nên ưu tiên làm:

```text
1. Export annotations.csv
2. Save meta.json + samples.bin + annotations.csv trong folder
3. Sau đó mới zip thành .la
```

---

## 7. Protocol decoder bắt buộc

Ba decoder mặc định:

```text
SPI
I2C
UART
```

Decoder input:

```text
LogicSampleBuffer chứa sample 0/1 theo thời gian
DecoderConfig chứa mapping kênh và thông số giao thức
```

Decoder output:

```text
DecodeAnnotation[]
```

Annotation nên có:

```python
@dataclass
class DecodeAnnotation:
    start_sample: int
    end_sample: int
    protocol: str   # SPI/I2C/UART
    type: str       # DATA/ADDRESS/START/STOP/ERROR
    value: str      # 0xAA, 170, etc.
    text: str       # mô tả đầy đủ
    error: bool = False
    error_reason: str = ""
```

### 7.1 SPI default

Default config:

```text
CS   = CH1
MOSI = CH2
MISO = CH3
SCK  = CH4
Mode = 0
CPOL = 0
CPHA = 0
Bit order = MSB first
Word size = 8 bit
CS active = LOW
Display = HEX
```

Thuật toán SPI mode 0:

```text
1. Chỉ decode khi CS = LOW.
2. Tìm rising edge của SCK.
3. Tại mỗi rising edge, đọc MOSI/MISO.
4. Gom đủ 8 bit thành byte.
5. MSB first: byte = (byte << 1) | bit.
6. Emit annotation.
```

Các lý do SPI decode sai:

```text
- Nhầm kênh CS/MOSI/MISO/SCK
- Sai SPI mode CPOL/CPHA
- Sai bit order
- Sai CS active LOW/HIGH
- Sample rate quá thấp
- Capture thiếu đầu/cuối frame
- Không chung GND hoặc nhiễu
```

### 7.2 I2C default

Default config:

```text
SDA = CH5
SCL = CH6
Address mode = 7-bit
Display = HEX
```

Thuật toán I2C:

```text
1. START: SDA falling khi SCL đang HIGH.
2. STOP: SDA rising khi SCL đang HIGH.
3. Trong frame, đọc SDA tại rising edge của SCL.
4. Gom 8 bit MSB first thành 1 byte.
5. Bit thứ 9 là ACK/NACK.
6. Byte đầu sau START là address + R/W.
7. Các byte sau là data.
```

Các lý do I2C decode sai:

```text
- Nhầm SDA/SCL
- Thiếu pull-up
- Sample rate quá thấp
- Không thấy START/STOP
- SDA bị đổi khi SCL HIGH do nhiễu
- Dữ liệu test không có address nhưng decoder hiểu byte đầu là address
```

### 7.3 UART default

Default config:

```text
RX = CH7
Baudrate = 9600
Data bits = 8
Parity = None
Stop bits = 1
Idle = HIGH
Display = HEX/ASCII
```

Thuật toán UART 8N1:

```text
1. Tìm falling edge HIGH → LOW để phát hiện start bit.
2. Kiểm tra giữa start bit vẫn LOW.
3. samples_per_bit = sample_rate / baudrate.
4. Lấy mẫu giữa từng data bit.
5. UART gửi LSB first.
6. Ghép 8 bit thành byte.
7. Kiểm tra stop bit phải HIGH.
8. Emit annotation hoặc framing error.
```

Các lý do UART decode sai:

```text
- Sai baudrate
- Sai kênh RX
- Sai idle polarity
- Sai data bits/parity/stop bits
- Sample rate quá thấp so với baudrate
- Capture bắt giữa frame, mất start bit
```

---

## 8. Debug decode

Nên có chế độ log/debug để biết vì sao sai.

SPI debug:

```text
CS active range: sample A → B
Clock edges found: N
Bits per word: 8
Decoded words: M
Incomplete word: yes/no
```

I2C debug:

```text
START found: yes/no
STOP found: yes/no
SCL rising edges: N
Bytes decoded: M
ACK count: K
```

UART debug:

```text
samplesPerBit: X
Falling edges found: N
Frames decoded: M
Framing errors: K
```

---

## 9. Test Arduino hiện tại

### 9.1 SPI wiring

```text
Arduino D10 → CH1  // CS
Arduino D11 → CH2  // MOSI
Arduino D12 → CH3  // MISO
Arduino D13 → CH4  // SCK
Arduino GND → GND
```

Nếu muốn MISO cũng có dữ liệu:

```text
Arduino D11 MOSI → Arduino D12 MISO
```

PulseView thường mapping:

```text
CH1 → D0
CH2 → D1
CH3 → D2
CH4 → D3
```

SPI decoder trong app:

```text
CS   = CH1
MOSI = CH2
MISO = CH3
SCK  = CH4
Mode 0
MSB first
8 bit
CS active LOW
```

Với hardware SPI Arduino 125 kHz, sample rate nên để ít nhất:

```text
1 MHz hoặc 2 MHz
```

Lý do: sample rate nên lớn hơn clock bus khoảng 8–10 lần. 250 kHz dễ sai nếu SPI clock là 125 kHz.

### 9.2 I2C wiring

```text
Arduino A4 → CH5  // SDA
Arduino A5 → CH6  // SCL
Arduino GND → GND
```

PulseView thường mapping:

```text
CH5 → D4
CH6 → D5
```

I2C decoder trong app:

```text
SDA = CH5
SCL = CH6
```

Trong PulseView:

```text
SDA = D4
SCL = D5
```

I2C cần pull-up. Nếu có điện trở:

```text
A4/SDA → 4.7kΩ → 5V
A5/SCL → 4.7kΩ → 5V
```

Nếu chưa có, code test dùng `INPUT_PULLUP` vẫn đủ test chậm.

---

## 10. Kiến thức I2C cần nhớ

I2C có 2 dây:

```text
SDA = data
SCL = clock
```

Bus rảnh:

```text
SDA = HIGH
SCL = HIGH
```

Quy tắc:

```text
START: SDA xuống LOW khi SCL đang HIGH
STOP : SDA lên HIGH khi SCL đang HIGH
DATA : SDA được đọc tại cạnh lên/rising edge của SCL
```

Mỗi byte:

```text
8 bit data + 1 bit ACK/NACK
```

I2C gửi MSB first.

Byte đầu sau START thường là:

```text
7-bit address + 1 bit R/W
```

Ví dụ address `0x3C` write:

```text
addressWrite = 0x3C << 1 = 0x78
```

Trên dây gửi `0x78`, nhưng decoder thường hiển thị là:

```text
Address 0x3C Write ACK
```

`0xAA` là cách hiển thị hex. Trên dây chỉ là bit:

```text
0xAA = 10101010 = 170 decimal
```

App nên cho tùy chọn display:

```text
HEX / DEC / BIN / ASCII
```

Default nên là HEX.

---

## 11. Raspberry Pi Pico 2 là lõi cuối cùng

Đây là mục tiêu chính cần nhớ: **PC app chỉ là giao diện và decoder; Pico 2 là phần capture tín hiệu logic**.

Kiến trúc định hướng:

```text
CH1-CH8 input pins trên Pico 2
        ↓
PIO / DMA / timer sampling
        ↓
Buffer mẫu logic dạng byte
        ↓
USB CDC hoặc custom USB transfer về PC
        ↓
Python app nhận data
        ↓
LogicSampleBuffer
        ↓
Waveform + Decoder
```

Giai đoạn đầu chưa cần viết firmware Pico 2 ngay. Nên làm theo thứ tự:

```text
1. DemoDriver sinh dữ liệu giả trong app
2. Arduino + PulseView để hiểu SPI/I2C/UART
3. App đọc sample giả và decode đúng
4. App save/load session
5. Sau đó mới viết PicoDriver để nhận dữ liệu từ Pico 2
```

`driver/pico_driver.py` về sau chịu trách nhiệm:

```text
- Tìm cổng Pico 2
- Gửi config sample rate / số mẫu / enabled channels
- Nhận stream sample byte
- Đưa vào LogicSampleBuffer
```

Firmware Pico 2 cần làm sau:

```text
- Chọn 8 GPIO làm CH1-CH8
- Sample đồng thời 8 chân thành 1 byte
- Dùng buffer vòng hoặc double buffer
- Gửi dữ liệu qua USB về PC
- Có command START/STOP/CONFIG
```

Câu bảo vệ:

> Raspberry Pi Pico 2 đóng vai trò phần cứng lấy mẫu. Ứng dụng Python trên PC không trực tiếp đọc chân tín hiệu, mà nhận các sample đã được Pico 2 đóng gói thành byte. Mỗi byte biểu diễn trạng thái 8 kênh CH1-CH8 tại một thời điểm lấy mẫu. Sau đó app vẽ waveform và chạy decoder SPI/I2C/UART trên dữ liệu này.

---


---

## 12. Kết nối phần cứng thật và các nguồn dữ liệu test

App phải được thiết kế để có nhiều nguồn dữ liệu, không phụ thuộc ngay vào Pico 2. Giai đoạn đầu cần có ít nhất 3 driver/source:

```text
1. DemoDriver
   - Không cần phần cứng.
   - Tự sinh sample SPI/I2C/UART để test waveform và decoder.

2. SigrokCliDriver / SaleaeCloneDriver
   - Dùng logic analyzer clone hiện tại, loại cần cài driver bằng Zadig.
   - App gọi sigrok-cli hoặc đọc file .sr/.csv xuất từ PulseView/sigrok.
   - Dùng để test phần cứng thật trước khi firmware Pico 2 hoàn thành.

3. PicoDriver
   - Mục tiêu cuối.
   - PC app nhận sample từ Raspberry Pi Pico 2 qua USB.
```

Package liên quan:

```text
driver/
├─ analyzer_driver.py      # interface chung
├─ demo_driver.py          # dữ liệu giả
├─ sigrok_cli_driver.py    # gọi sigrok-cli / đọc capture từ sigrok
├─ saleae_clone_driver.py  # có thể là wrapper riêng cho clone FX2/Saleae
└─ pico_driver.py          # lõi cuối: Pico 2
```

Nếu thầy hỏi “đổi nguồn dữ liệu ở đâu?” thì sửa ở `driver/`. UI chỉ chọn source, còn cách lấy sample nằm trong từng driver.

### 12.1 Thứ tự test phần cứng nên làm

Không test thẳng Pico 2 ngay. Nên đi theo thứ tự:

```text
Bước 1: DemoDriver
- App tự sinh waveform SPI/I2C/UART.
- Mục tiêu: renderer + decoder chạy đúng mà không cần phần cứng.

Bước 2: Saleae clone / FX2 clone qua PulseView hoặc sigrok-cli
- Arduino phát SPI/I2C/UART.
- Logic analyzer clone bắt tín hiệu thật.
- Dùng PulseView để xác nhận dây và decoder đúng.
- Sau đó app đọc lại dữ liệu qua sigrok-cli/file để so sánh.

Bước 3: Pico 2
- Pico 2 tự capture CH1-CH8.
- PC app nhận byte sample qua USB.
- So kết quả với Saleae clone/PulseView để kiểm chứng.
```

### 12.2 Saleae clone / logic analyzer clone dùng Zadig

Thiết bị hiện tại là logic analyzer clone kiểu Saleae/FX2, thường xuất hiện trong PulseView như `fx2lafw` hoặc tương tự. Trên Windows thường cần dùng Zadig để cài driver USB phù hợp cho libusb/sigrok.

Quy trình dự phòng:

```text
1. Cắm logic analyzer clone vào PC.
2. Mở Zadig.
3. Options → List All Devices.
4. Chọn đúng thiết bị logic analyzer / Saleae clone / USB logic analyzer.
5. Cài driver WinUSB hoặc libusbK/libusb-win32 tùy cái PulseView/sigrok nhận ổn.
6. Mở PulseView → Scan for devices.
7. Nếu thấy fx2lafw/Saleae clone thì capture thử.
```

Lưu ý:

```text
- Đừng chọn nhầm chuột, bàn phím, USB hub trong Zadig.
- Nếu cài sai driver cho thiết bị khác, thiết bị đó có thể tạm không hoạt động.
- Khi PulseView nhận được thì coi như phần driver Windows đã ổn.
- App của mình giai đoạn đầu không cần tự nói chuyện USB trực tiếp với clone; có thể gọi sigrok-cli hoặc đọc file capture do PulseView xuất ra.
```

Vai trò của Saleae clone trong đồ án:

```text
- Là phần cứng test dự phòng.
- Dùng để xác minh thuật toán decoder của app.
- Dùng để so sánh với Pico 2 khi PicoDriver/firmware chưa ổn.
```

Nếu thầy hỏi “Pico 2 chưa xong thì app test bằng gì?”:

> Em có `DemoDriver` để test luồng dữ liệu giả và có `SigrokCliDriver`/`SaleaeCloneDriver` để đọc dữ liệu từ logic analyzer clone qua sigrok. Sau khi firmware Pico 2 ổn định, chỉ cần thay driver đầu vào sang `PicoDriver`; các module buffer, waveform và decoder không đổi.

### 12.3 Cách app nhận dữ liệu từ Saleae clone giai đoạn đầu

Có 2 cách đơn giản:

#### Cách A — dùng PulseView xuất file trước

```text
Arduino phát tín hiệu
→ Saleae clone capture trong PulseView
→ Save thành .sr hoặc export CSV/binary
→ App load file đó
→ Convert về LogicSampleBuffer
→ Decode bằng decoder của app
```

Ưu điểm:

```text
- Dễ debug.
- Không cần app tự capture realtime ngay.
- So được kết quả app với PulseView.
```

#### Cách B — app gọi sigrok-cli

App chạy command bên ngoài, ví dụ ý tưởng:

```bat
sigrok-cli --scan
sigrok-cli -d fx2lafw --config samplerate=1m --samples 100000 -o capture.sr
```

Sau đó app đọc `capture.sr` hoặc gọi thêm bước convert. Cách này nên để sau khi GUI và decoder đã chạy ổn.

Module chịu trách nhiệm:

```text
driver/sigrok_cli_driver.py
```

### 12.4 Mapping phần cứng test chuẩn

SPI bằng Arduino Uno/Nano:

```text
Arduino D10 → CH1  // CS
Arduino D11 → CH2  // MOSI
Arduino D12 → CH3  // MISO
Arduino D13 → CH4  // SCK
Arduino GND → GND
```

I2C bằng Arduino Uno/Nano:

```text
Arduino A4 → CH5  // SDA
Arduino A5 → CH6  // SCL
Arduino GND → GND
```

UART test đề xuất:

```text
Arduino TX hoặc pin TX bit-bang → CH7
Arduino GND → GND
```

Nếu dùng PulseView, mapping thường là:

```text
CH1 → D0
CH2 → D1
CH3 → D2
CH4 → D3
CH5 → D4
CH6 → D5
CH7 → D6
CH8 → D7
```

Trong app vẫn hiển thị theo CH1 → CH8 để khỏi nhầm khi cắm dây thật.

### 12.5 Hardware abstraction cần nhớ

Các driver khác nhau nhưng output phải giống nhau:

```text
DemoDriver        → LogicSampleBuffer
SigrokCliDriver   → LogicSampleBuffer
SaleaeCloneDriver → LogicSampleBuffer
PicoDriver        → LogicSampleBuffer
```

Vì vậy decoder không cần biết dữ liệu đến từ đâu. SPI/I2C/UART decoder chỉ nhận `LogicSampleBuffer` và channel mapping.

Câu bảo vệ:

> Em dùng abstraction `AnalyzerDriver`. Bất kể dữ liệu đến từ DemoDriver, Saleae clone qua sigrok hay Pico 2, driver đều trả về cùng định dạng `LogicSampleBuffer`. Do đó phần waveform và decoder được tái sử dụng, không phụ thuộc phần cứng cụ thể.


## 13. Roadmap xây app

```text
Milestone 1: Tạo project Python + PyQt6/PyQt5 compatibility
Milestone 2: LogicSampleBuffer + DemoDriver sinh dữ liệu 8 kênh
Milestone 3: Vẽ waveform CH1-CH8 bằng QPainter
Milestone 4: Cursor A/B, đo Δt và frequency
Milestone 5: Decoder framework + DecodeAnnotation
Milestone 6: SPI decoder mode 0
Milestone 7: I2C decoder
Milestone 8: UART 8N1 decoder
Milestone 9: Annotation table + export CSV
Milestone 10: Save/load session .la
Milestone 11: PicoDriver nhận dữ liệu từ Raspberry Pi Pico 2
Milestone 12: Firmware Pico 2 capture 8 kênh
```

Bản đầu có thể dùng DemoDriver để test toàn bộ GUI/decoder trước khi Pico 2 sẵn sàng.

---

## 14. Những câu cần nhớ khi bảo vệ

### Logic analyzer app làm gì?

Ứng dụng hiển thị tín hiệu số theo thời gian, cho phép đo thời gian bằng cursor và giải mã các giao thức số phổ biến như SPI, I2C, UART.

### Một sample là gì?

Một sample là trạng thái các kênh logic tại một thời điểm lấy mẫu. Với 8 kênh, mỗi sample được lưu bằng 1 byte, mỗi bit tương ứng một kênh CH1-CH8.

### Vì sao cần sample rate?

Sample rate dùng để đổi sample index sang thời gian và quyết định khả năng bắt đúng cạnh tín hiệu. Nếu sample rate quá thấp so với tốc độ bus, decoder có thể sai.

### Vì sao decoder có thể sai?

Do chọn sai kênh, sai thông số giao thức, sample rate quá thấp, nhiễu, thiếu GND chung, hoặc capture thiếu frame.

### SPI/I2C/UART decode khác nhau thế nào?

```text
SPI: dùng CS và cạnh SCK, phụ thuộc CPOL/CPHA.
I2C: dùng START/STOP và cạnh lên SCL, có ACK/NACK.
UART: không có clock riêng, phải dựa vào baudrate để lấy mẫu giữa bit.
```

### Vì sao hiển thị 0xAA thay vì 170?

Vì decoder thường hiển thị byte theo hệ hex. Trên bus chỉ có bit `10101010`; byte này có thể hiển thị là `0xAA`, `170`, hoặc `10101010`. Hex gọn và phổ biến trong phân tích giao thức.

---

## 15. Ghi chú lỗi Arduino upload từng gặp

Lỗi từng gặp:

```text
avrdude: ser_open(): can't set com-state for "\\.\COM15"
Error: cannot set com-state for \\.\COM15
```

Nguyên nhân không phải code SPI/I2C. Đây thường là lỗi Windows/driver USB-Serial/CH340 hoặc COM port bị kẹt.

Cách xử lý đã hiệu quả:

```text
Device Manager → Ports → USB-SERIAL CH340 / Arduino Uno
Right click → Uninstall device
Rút Arduino → cắm lại để Windows tự cài lại driver
```

Cũng nên thử:

```text
- Đóng PulseView/Serial Monitor
- Kill serial-discovery.exe/avrdude.exe nếu kẹt
- Đổi COM15 về COM4/COM5
- Đổi cáp USB/cổng USB
```

---

## 16. Chốt định hướng

Chọn hướng:

```text
Python + PyQt6/PyQt5
DemoDriver trước
Decode SPI/I2C/UART là bắt buộc
Save session dạng .la ZIP
Pico 2 là lõi capture cuối cùng
```

Khi tiếp tục code, bắt đầu từ:

```text
1. qt_compat.py
2. main.py
3. data/logic_sample_buffer.py
4. driver/demo_driver.py
5. ui/waveform_view.py
```
