"""
Configuration constants for Raspberry Pi Pico sensor monitoring
Centralized configuration for I2C pins, sensor addresses, and calibration values
"""

# I2C Configuration
# Canonical I2C configuration: I2C1 with SDA=GP2, SCL=GP3
# This is the standard configuration used across all scripts
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

# MQ135 Configuration
MQ135_PIN = 28  # GPIO 28 (ADC2, Pin 34)
MQ135_R_LOAD = 10000  # 10kΩ load resistor
MQ135_R_ZERO = 42304.5  # Calibrated resistance in clean air (adjust based on your sensor)

# Air Quality Thresholds (CO2 ppm)
AQ_EXCELLENT = 400
AQ_GOOD = 600
AQ_FAIR = 1000
AQ_POOR = 1500
AQ_VERY_POOR = 2500

