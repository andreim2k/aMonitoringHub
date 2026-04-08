"""
BME280 SPI MicroPython Library
Library for reading temperature, humidity, and pressure from BME280 sensor via SPI
"""

import time
from machine import SPI, Pin

try:
    from lib.config import (
        BME280_DEFAULT_ADDRESS, BME280_CHIP_ID,
        BME280_STATUS_REGISTER, BME280_DATA_READY_BIT, BME280_MEASURING_BIT,
        BME280_RESET_REGISTER, BME280_RESET_VALUE,
        I2C_RECOVERY_RETRIES, I2C_OPERATION_TIMEOUT_MS, I2C_STATUS_CHECK_TIMEOUT_MS,
        SPI_POLARITY, SPI_PHASE
    )
except ImportError:
    # Fallback defaults if config not available
    BME280_CHIP_ID = 0x60
    BME280_STATUS_REGISTER = 0xF3
    BME280_DATA_READY_BIT = 3
    BME280_MEASURING_BIT = 0
    BME280_RESET_REGISTER = 0xE0
    BME280_RESET_VALUE = 0xB6
    I2C_RECOVERY_RETRIES = 3
    I2C_OPERATION_TIMEOUT_MS = 100
    I2C_STATUS_CHECK_TIMEOUT_MS = 500
    SPI_POLARITY = 0
    SPI_PHASE = 0

# Float comparison epsilon
EPSILON = 1e-6

class BME280_SPI:
    def __init__(self, spi, cs_pin):
        """
        Initialize BME280 sensor via SPI

        Args:
            spi: SPI bus object (already configured)
            cs_pin: Chip Select GPIO pin object

        Raises:
            ValueError: If chip ID doesn't match
            OSError: If SPI communication fails
        """
        if spi is None:
            raise ValueError("SPI bus object cannot be None")
        if cs_pin is None:
            raise ValueError("CS pin object cannot be None")

        self.spi = spi
        self.cs = cs_pin
        self.cs.on()  # Deselect by default

        # Verify chip ID (0x60 = BME280, 0x58 = BMP280)
        chip_id = self._read_register(0xD0)
        if chip_id not in (0x60, 0x58):  # Both BME280 and BMP280 supported
            raise ValueError(f"Invalid chip ID: 0x{chip_id:02X}, expected 0x60 (BME280) or 0x58 (BMP280)")

        # Store chip ID - but ALWAYS try to read humidity (some sensors may have it despite chip ID)
        self.chip_id = chip_id
        self.has_humidity = True  # Always assume humidity is available

        # Reset sensor
        self.reset()

        # Read calibration data
        self._read_calibration_data()

        # Configure sensor
        self._configure_sensor()

    def _read_register(self, reg):
        """Read a single register via SPI"""
        last_error = None
        for attempt in range(I2C_RECOVERY_RETRIES):
            try:
                start_time = time.ticks_ms()

                # BME280 SPI read protocol:
                # 1. Pull CS low
                # 2. Send address byte (MSB=1 for read operation)
                # 3. Read response byte
                # 4. Pull CS high
                self.cs.off()
                time.sleep(0.001)  # Small delay after CS

                # Send address and read in single transaction
                tx_buf = bytearray([reg | 0x80, 0x00])
                rx_buf = bytearray(2)
                self.spi.write_readinto(tx_buf, rx_buf)
                result = rx_buf[1]  # Second byte is the data

                time.sleep(0.001)  # Small delay before CS high
                self.cs.on()

                if time.ticks_diff(time.ticks_ms(), start_time) > I2C_OPERATION_TIMEOUT_MS:
                    raise OSError("SPI read timeout")
                return result
            except (OSError, ValueError) as e:
                self.cs.on()
                last_error = e
                if attempt < I2C_RECOVERY_RETRIES - 1:
                    time.sleep(0.01)
                else:
                    raise last_error
        raise last_error

    def _read_registers(self, reg, count):
        """Read multiple consecutive registers via SPI"""
        last_error = None
        for attempt in range(I2C_RECOVERY_RETRIES):
            try:
                start_time = time.ticks_ms()

                # BME280 SPI read protocol for multiple bytes
                self.cs.off()
                time.sleep(0.001)

                # Send address byte (MSB=1 for read) + padding for data bytes
                tx_buf = bytearray(count + 1)
                tx_buf[0] = reg | 0x80
                rx_buf = bytearray(count + 1)
                self.spi.write_readinto(tx_buf, rx_buf)
                result = rx_buf[1:]  # Skip first byte (response to address)

                time.sleep(0.001)
                self.cs.on()

                if time.ticks_diff(time.ticks_ms(), start_time) > I2C_OPERATION_TIMEOUT_MS:
                    raise OSError("SPI read timeout")
                return result
            except (OSError, ValueError) as e:
                self.cs.on()
                last_error = e
                if attempt < I2C_RECOVERY_RETRIES - 1:
                    time.sleep(0.01)
                else:
                    raise last_error
        raise last_error

    def _write_register(self, reg, value):
        """Write to a register via SPI"""
        last_error = None
        for attempt in range(I2C_RECOVERY_RETRIES):
            try:
                start_time = time.ticks_ms()

                # SPI write: MSB must be 0 for write operation
                self.cs.off()
                self.spi.write(bytes([reg & 0x7F, value]))
                self.cs.on()

                # Check for timeout
                if time.ticks_diff(time.ticks_ms(), start_time) > I2C_OPERATION_TIMEOUT_MS:
                    raise OSError("SPI write timeout")
                return
            except (OSError, ValueError) as e:
                self.cs.on()  # Ensure CS is deselected
                last_error = e
                if attempt < I2C_RECOVERY_RETRIES - 1:
                    time.sleep(0.01)
                else:
                    raise last_error
        raise last_error

    def _read_calibration_data(self):
        """Read calibration coefficients"""
        # Temperature calibration
        calib = self._read_registers(0x88, 24)

        self.dig_T1 = calib[1] << 8 | calib[0]
        self.dig_T2 = self._to_signed(calib[3] << 8 | calib[2], 16)
        self.dig_T3 = self._to_signed(calib[5] << 8 | calib[4], 16)

        # Pressure calibration
        self.dig_P1 = calib[7] << 8 | calib[6]
        self.dig_P2 = self._to_signed(calib[9] << 8 | calib[8], 16)
        self.dig_P3 = self._to_signed(calib[11] << 8 | calib[10], 16)
        self.dig_P4 = self._to_signed(calib[13] << 8 | calib[12], 16)
        self.dig_P5 = self._to_signed(calib[15] << 8 | calib[14], 16)
        self.dig_P6 = self._to_signed(calib[17] << 8 | calib[16], 16)
        self.dig_P7 = self._to_signed(calib[19] << 8 | calib[18], 16)
        self.dig_P8 = self._to_signed(calib[21] << 8 | calib[20], 16)
        self.dig_P9 = self._to_signed(calib[23] << 8 | calib[22], 16)

        # Humidity calibration (BME280 only, skip for BMP280)
        if self.has_humidity:
            self.dig_H1 = self._read_register(0xA1)
            calib2 = self._read_registers(0xE1, 7)
            self.dig_H2 = self._to_signed(calib2[1] << 8 | calib2[0], 16)
            self.dig_H3 = calib2[2]
            self.dig_H4 = self._to_signed(calib2[3] << 4 | (calib2[4] & 0x0F), 12)
            self.dig_H5 = self._to_signed((calib2[5] << 4) | (calib2[4] >> 4), 12)
            self.dig_H6 = self._to_signed(calib2[6], 8)

    def _to_signed(self, value, bits):
        """Convert unsigned to signed integer"""
        if value & (1 << (bits - 1)):
            return value - (1 << bits)
        return value

    def _configure_sensor(self):
        """Configure sensor settings"""
        # Set humidity oversampling to x1
        self._write_register(0xF2, 0x01)

        # Set temperature and pressure oversampling to x1, normal mode
        self._write_register(0xF4, 0x27)

        # Set config: standby 62.5ms, filter off
        self._write_register(0xF5, 0x20)

    def reset(self):
        """Reset the BME280 sensor"""
        try:
            self._write_register(BME280_RESET_REGISTER, BME280_RESET_VALUE)
            time.sleep(0.01)  # Wait for reset to complete
            time.sleep(0.01)
        except Exception as e:
            raise OSError(f"BME280 reset failed: {e}")

    def check_status(self):
        """Read the status register"""
        try:
            return self._read_register(BME280_STATUS_REGISTER)
        except Exception as e:
            raise OSError(f"Failed to read status register: {e}")

    def is_ready(self):
        """Check if sensor data is ready (not measuring and data ready)"""
        try:
            status = self.check_status()
            # Bit 0 = measuring, Bit 3 = data ready
            measuring = (status >> BME280_MEASURING_BIT) & 0x01
            data_ready = (status >> BME280_DATA_READY_BIT) & 0x01
            return measuring == 0 and data_ready == 1
        except Exception:
            return False

    def wait_for_ready(self, timeout_ms=None):
        """Wait for sensor to be ready with timeout"""
        if timeout_ms is None:
            timeout_ms = I2C_STATUS_CHECK_TIMEOUT_MS

        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            if self.is_ready():
                return True
            time.sleep(0.01)

        return False

    def read_raw_data(self):
        """Read raw sensor data"""
        # Wait for sensor to be ready before reading
        if not self.wait_for_ready():
            raise OSError("BME280/BMP280 sensor not ready - timeout waiting for data")

        # Read pressure, temperature, and humidity data (humidity only on BME280)
        data = self._read_registers(0xF7, 8)

        raw_press = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_temp = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)

        # BMP280 doesn't have humidity, so return 0 if not available
        raw_hum = (data[6] << 8) | data[7] if self.has_humidity else 0

        return raw_temp, raw_press, raw_hum

    def read_compensated_data(self):
        """Read and compensate sensor data"""
        raw_temp, raw_press, raw_hum = self.read_raw_data()

        # Compensate temperature
        var1 = (raw_temp / 16384.0 - self.dig_T1 / 1024.0) * self.dig_T2
        var2 = ((raw_temp / 131072.0 - self.dig_T1 / 8192.0) *
                (raw_temp / 131072.0 - self.dig_T1 / 8192.0)) * self.dig_T3
        t_fine = int(var1 + var2)
        temperature = (var1 + var2) / 5120.0

        # Compensate pressure
        var1 = (t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * self.dig_P6 / 32768.0
        var2 = var2 + var1 * self.dig_P5 * 2.0
        var2 = (var2 / 4.0) + (self.dig_P4 * 65536.0)
        var1 = (self.dig_P3 * var1 * var1 / 524288.0 + self.dig_P2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.dig_P1

        # Fix float comparison: use epsilon instead of == 0
        if abs(var1) < EPSILON:
            pressure = 0
        else:
            pressure = 1048576.0 - raw_press
            pressure = (pressure - (var2 / 4096.0)) * 6250.0 / var1
            var1 = self.dig_P9 * pressure * pressure / 2147483648.0
            var2 = pressure * self.dig_P8 / 32768.0
            pressure = pressure + (var1 + var2 + self.dig_P7) / 16.0

        # Compensate humidity (BME280 only)
        if self.has_humidity:
            h = t_fine - 76800.0
            h = ((raw_hum - (self.dig_H4 * 64.0 + self.dig_H5 / 16384.0 * h)) *
                 (self.dig_H2 / 65536.0 * (1.0 + self.dig_H6 / 67108864.0 * h *
                 (1.0 + self.dig_H3 / 67108864.0 * h))))
            humidity = h * (1.0 - self.dig_H1 * h / 524288.0)

            if humidity > 100:
                humidity = 100
            elif humidity < 0:
                humidity = 0
        else:
            # BMP280 doesn't have humidity
            humidity = 0

        return temperature, pressure, humidity

    def read_temperature(self):
        """Read temperature in Celsius"""
        temp, _, _ = self.read_compensated_data()
        return temp

    def read_pressure(self):
        """Read pressure in Pascals"""
        _, press, _ = self.read_compensated_data()
        return press

    def read_humidity(self):
        """Read humidity as percentage"""
        _, _, hum = self.read_compensated_data()
        return hum

    def read_all(self):
        """Read all sensor values"""
        return self.read_compensated_data()
