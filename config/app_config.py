# config/app_config.py

CHANNEL_COUNT = 8

CHANNEL_NAMES = [
    "CH1",
    "CH2",
    "CH3",
    "CH4",
    "CH5",
    "CH6",
    "CH7",
    "CH8",
]

DEFAULT_SAMPLE_RATE_HZ = 1_000_000

# Mapping test mặc định
# SPI: CH1-CS, CH2-MOSI, CH3-MISO, CH4-SCK
# I2C: CH5-SDA, CH6-SCL
# UART: CH7-RX/TX