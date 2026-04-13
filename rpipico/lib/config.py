"""
Configuration constants for Raspberry Pi Pico sensor monitoring.
SPI is used for the BMP280; ADC for the MQ135. No I2C devices are wired.
"""

# SPI Configuration (BMP280 on SPI0)
# RP2040 SPI0: SCK=GP18, MOSI=GP19, MISO=GP16, CS=GP17
SPI_BUS = 0
SPI_SCK_PIN = 18
SPI_MOSI_PIN = 19
SPI_MISO_PIN = 16
SPI_CS_PIN = 17
SPI_FREQ = 100_000      # 100 kHz: extra margin for long-run SPI stability
SPI_POLARITY = 0        # BMP280 SPI mode 0
SPI_PHASE = 0

# BMP280 register map
BMP280_CHIP_ID_REG = 0xD0
BMP280_RESET_REG = 0xE0
BMP280_RESET_VALUE = 0xB6
BMP280_STATUS_REG = 0xF3
BMP280_CTRL_MEAS_REG = 0xF4
BMP280_CONFIG_REG = 0xF5
BMP280_DATA_REG = 0xF7   # pressure/temp burst start

# Status register bit positions
BMP280_MEASURING_BIT = 3
BMP280_IM_UPDATE_BIT = 0

# Sensor configuration bytes
# ctrl_meas: temp x1, press x1, normal mode
BMP280_CTRL_MEAS_VALUE = 0x27
# config: standby 62.5 ms, filter off, SPI 4-wire
BMP280_CONFIG_VALUE = 0x20

# SPI retry / timing
SPI_OP_RETRIES = 3
SPI_RETRY_DELAY_MS = 10

# LED Configuration
LED_PIN = 25
LED_BLINK_DURATION_MS = 100

# MQ135 Configuration
MQ135_PIN = 28
MQ135_R_LOAD = 10000
MQ135_R_ZERO = 42304.5

# MQ135 gas calculation constants
MQ135_CO2_A = 116.6020682
MQ135_CO2_B = -2.769034857
MQ135_NH3_A = 102.694
MQ135_NH3_B = -2.815
MQ135_ALCOHOL_A = 77.255
MQ135_ALCOHOL_B = -3.18

MQ135_CO2_MAX = 10000
MQ135_NH3_MAX = 500
MQ135_ALCOHOL_MAX = 1000

AQ_EXCELLENT = 400
AQ_GOOD = 600
AQ_FAIR = 1000
AQ_POOR = 1500
AQ_VERY_POOR = 2500

# Timing
BOOT_DELAY_SEC = 2.0
BMP280_RETRY_DELAY_SEC = 2.0
SENSOR_READ_INTERVAL_SEC = 5.0
GC_COLLECT_INTERVAL = 10        # collect every N iterations (was 60 — too sparse)
BMP280_REQUIRED = False         # When False, firmware keeps running with MQ135 only
BMP280_INIT_RETRIES = 10        # Startup retries when BMP280 is required
BMP280_RECOVERY_INIT_RETRIES = 1
BMP280_RECOVERY_RETRY_DELAY_SEC = 0.0
BMP280_MAX_CONSEC_FAILS_BEFORE_REBOOT = 12  # Consecutive failed recovery cycles
BMP280_OPTIONAL_RETRY_DELAY_SEC = 60.0      # Backoff when BMP280 is optional

# ADC
ADC_MAX_VALUE = 65535
VOLTAGE_REFERENCE = 3.3
MIN_VOLTAGE_THRESHOLD = 0.01

# Validation
VALID_ADC_PINS = list(range(26, 30))
MIN_R_ZERO = 1000.0
MAX_R_ZERO = 1000000.0
MIN_R_LOAD = 100.0
MAX_R_LOAD = 1000000.0
