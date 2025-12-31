"""
Configuration constants for Raspberry Pi Pico sensor monitoring
Centralized configuration for I2C pins, sensor addresses, and calibration values
"""

# I2C Configuration
# I2C1 configuration: SDA=GP2, SCL=GP3
# This configuration uses I2C1 bus with GPIO 2 and 3
I2C_BUS = 1
I2C_SDA_PIN = 2  # GPIO 2 (Pin 4)
I2C_SCL_PIN = 3  # GPIO 3 (Pin 5)
I2C_FREQ = 400000  # 400kHz

# Alternative I2C configuration (I2C0)
# I2C_BUS_ALT = 0
# I2C_SDA_PIN_ALT = 4  # GPIO 4 (Pin 6)
# I2C_SCL_PIN_ALT = 5  # GPIO 5 (Pin 7)

# BME280 Configuration
BME280_ADDRESSES = [0x76, 0x77]  # Common addresses (try both)
BME280_DEFAULT_ADDRESS = 0x76
BME280_CHIP_ID = 0x60
BME280_STATUS_REGISTER = 0xF3  # Status register address
BME280_DATA_READY_BIT = 3  # Bit 3 indicates data ready
BME280_MEASURING_BIT = 0  # Bit 0 indicates measuring in progress
BME280_RESET_REGISTER = 0xE0  # Reset register address
BME280_RESET_VALUE = 0xB6  # Reset command value

# MQ135 Configuration
MQ135_PIN = 28  # GPIO 28 (ADC2, Pin 34)
MQ135_R_LOAD = 10000  # 10kΩ load resistor
MQ135_R_ZERO = 42304.5  # Calibrated resistance in clean air (adjust based on your sensor)

# MQ135 Gas Calculation Constants
MQ135_CO2_A = 116.6020682
MQ135_CO2_B = -2.769034857
MQ135_NH3_A = 102.694
MQ135_NH3_B = -2.815
MQ135_ALCOHOL_A = 77.255
MQ135_ALCOHOL_B = -3.18

# MQ135 PPM Limits
MQ135_CO2_MAX = 10000
MQ135_NH3_MAX = 500
MQ135_ALCOHOL_MAX = 1000

# Air Quality Thresholds (CO2 ppm)
AQ_EXCELLENT = 400
AQ_GOOD = 600
AQ_FAIR = 1000
AQ_POOR = 1500
AQ_VERY_POOR = 2500

# Timing Configuration
BOOT_DELAY_SEC = 2.0  # Delay after boot to ensure USB is ready
BME280_RETRY_DELAY_SEC = 2.0  # Delay between BME280 retry attempts
SENSOR_READ_INTERVAL_SEC = 5.0  # Interval between sensor readings
GC_COLLECT_INTERVAL = 60  # Garbage collection every N iterations
BME280_RESET_INTERVAL = 100  # Reset sensor every N readings (0 = disabled)

# I2C Recovery Configuration
I2C_RECOVERY_RETRIES = 3  # Number of retries for I2C operations
I2C_OPERATION_TIMEOUT_MS = 100  # Timeout for I2C operations in milliseconds
I2C_STATUS_CHECK_TIMEOUT_MS = 500  # Timeout for waiting for sensor status

# ADC Configuration
ADC_MAX_VALUE = 65535
VOLTAGE_REFERENCE = 3.3
MIN_VOLTAGE_THRESHOLD = 0.01  # Minimum voltage threshold for resistance calculation

# Validation Constants
VALID_ADC_PINS = list(range(26, 30))  # Valid ADC pins on Pico: GP26-GP29
MIN_R_ZERO = 1000.0  # Minimum valid R0 value
MAX_R_ZERO = 1000000.0  # Maximum valid R0 value
MIN_R_LOAD = 100.0  # Minimum valid load resistor value
MAX_R_LOAD = 1000000.0  # Maximum valid load resistor value
VALID_I2C_ADDRESSES = list(range(0x08, 0x78))  # Valid I2C addresses (excluding reserved)

