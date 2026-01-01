"""
BME280 MicroPython Library
Simple library for reading temperature, humidity, and pressure from BME280 sensor
"""

import time
from machine import I2C

try:
    from lib.config import (
        BME280_DEFAULT_ADDRESS, BME280_CHIP_ID, VALID_I2C_ADDRESSES,
        BME280_STATUS_REGISTER, BME280_DATA_READY_BIT, BME280_MEASURING_BIT,
        BME280_RESET_REGISTER, BME280_RESET_VALUE,
        I2C_RECOVERY_RETRIES, I2C_OPERATION_TIMEOUT_MS, I2C_STATUS_CHECK_TIMEOUT_MS
    )
except ImportError:
    # Fallback defaults if config not available
    BME280_DEFAULT_ADDRESS = 0x76
    BME280_CHIP_ID = 0x60
    VALID_I2C_ADDRESSES = list(range(0x08, 0x78))
    BME280_STATUS_REGISTER = 0xF3
    BME280_DATA_READY_BIT = 3
    BME280_MEASURING_BIT = 0
    BME280_RESET_REGISTER = 0xE0
    BME280_RESET_VALUE = 0xB6
    I2C_RECOVERY_RETRIES = 3
    I2C_OPERATION_TIMEOUT_MS = 100
    I2C_STATUS_CHECK_TIMEOUT_MS = 500

# Float comparison epsilon
EPSILON = 1e-6

class BME280:
    def __init__(self, i2c, address=None):
        """
        Initialize BME280 sensor
        
        Args:
            i2c: I2C bus object
            address: I2C address (default from config, typically 0x76 or 0x77)
        
        Raises:
            ValueError: If address is invalid or chip ID doesn't match
            OSError: If I2C communication fails
        """
        if i2c is None:
            raise ValueError("I2C bus object cannot be None")
        
        # Use default address if not provided
        if address is None:
            address = BME280_DEFAULT_ADDRESS
        
        # Validate I2C address
        if address not in VALID_I2C_ADDRESSES:
            raise ValueError(f"Invalid I2C address: 0x{address:02X}. Must be between 0x08 and 0x77")
        
        self.i2c = i2c
        self.address = address
        
        # Verify chip ID
        chip_id = self._read_register(0xD0)
        if chip_id != BME280_CHIP_ID:
            raise ValueError(f"Invalid chip ID: 0x{chip_id:02X}, expected 0x{BME280_CHIP_ID:02X}")
        
        # Reset sensor
        self.reset()
        
        # Read calibration data
        self._read_calibration_data()
        
        # Configure sensor
        self._configure_sensor()
    
    def _read_register(self, reg):
        """Read a single register with retry logic"""
        last_error = None
        for attempt in range(I2C_RECOVERY_RETRIES):
            try:
                start_time = time.ticks_ms()
                result = self.i2c.readfrom_mem(self.address, reg, 1)[0]
                # Check for timeout
                if time.ticks_diff(time.ticks_ms(), start_time) > I2C_OPERATION_TIMEOUT_MS:
                    raise OSError("I2C read timeout")
                return result
            except (OSError, ValueError) as e:
                last_error = e
                if attempt < I2C_RECOVERY_RETRIES - 1:
                    time.sleep(0.01)  # Short delay before retry
                else:
                    raise last_error
        raise last_error
    
    def _read_registers(self, reg, count):
        """Read multiple registers with retry logic"""
        last_error = None
        for attempt in range(I2C_RECOVERY_RETRIES):
            try:
                start_time = time.ticks_ms()
                result = self.i2c.readfrom_mem(self.address, reg, count)
                # Check for timeout
                if time.ticks_diff(time.ticks_ms(), start_time) > I2C_OPERATION_TIMEOUT_MS:
                    raise OSError("I2C read timeout")
                return result
            except (OSError, ValueError) as e:
                last_error = e
                if attempt < I2C_RECOVERY_RETRIES - 1:
                    time.sleep(0.01)  # Short delay before retry
                else:
                    raise last_error
        raise last_error
    
    def _write_register(self, reg, value):
        """Write to a register with retry logic"""
        last_error = None
        for attempt in range(I2C_RECOVERY_RETRIES):
            try:
                start_time = time.ticks_ms()
                self.i2c.writeto_mem(self.address, reg, bytes([value]))
                # Check for timeout
                if time.ticks_diff(time.ticks_ms(), start_time) > I2C_OPERATION_TIMEOUT_MS:
                    raise OSError("I2C write timeout")
                return
            except (OSError, ValueError) as e:
                last_error = e
                if attempt < I2C_RECOVERY_RETRIES - 1:
                    time.sleep(0.01)  # Short delay before retry
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
        
        # Humidity calibration
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

        # Set config: standby 62.5ms (was 1000ms), filter off
        # 0x20 = bits 7-5 (t_sb) = 001 = 62.5ms standby
        self._write_register(0xF5, 0x20)
    
    def reset(self):
        """Reset the BME280 sensor"""
        try:
            self._write_register(BME280_RESET_REGISTER, BME280_RESET_VALUE)
            time.sleep(0.01)  # Wait for reset to complete
            # Wait for sensor to be ready after reset
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
            # Data is ready when measuring bit is 0 and data ready bit is 1
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
            time.sleep(0.01)  # Small delay between checks
        
        return False
    
    def read_raw_data(self):
        """Read raw sensor data"""
        # Wait for sensor to be ready before reading
        if not self.wait_for_ready():
            raise OSError("BME280 sensor not ready - timeout waiting for data")
        
        # Read pressure, temperature, and humidity data
        data = self._read_registers(0xF7, 8)
        
        raw_press = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_temp = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        raw_hum = (data[6] << 8) | data[7]
        
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
        
        # Compensate humidity
        h = t_fine - 76800.0
        h = ((raw_hum - (self.dig_H4 * 64.0 + self.dig_H5 / 16384.0 * h)) * 
             (self.dig_H2 / 65536.0 * (1.0 + self.dig_H6 / 67108864.0 * h * 
             (1.0 + self.dig_H3 / 67108864.0 * h))))
        humidity = h * (1.0 - self.dig_H1 * h / 524288.0)
        
        if humidity > 100:
            humidity = 100
        elif humidity < 0:
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

