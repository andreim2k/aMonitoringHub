"""
BME280 MicroPython Library
Simple library for reading temperature, humidity, and pressure from BME280 sensor
"""

import time
from machine import I2C

class BME280:
    def __init__(self, i2c, address=0x76):
        self.i2c = i2c
        self.address = address
        
        # Verify chip ID
        chip_id = self._read_register(0xD0)
        if chip_id != 0x60:
            raise Exception(f"Invalid chip ID: 0x{chip_id:02X}, expected 0x60")
        
        # Reset sensor
        self._write_register(0xE0, 0xB6)
        time.sleep(0.01)
        
        # Read calibration data
        self._read_calibration_data()
        
        # Configure sensor
        self._configure_sensor()
    
    def _read_register(self, reg):
        """Read a single register"""
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]
    
    def _read_registers(self, reg, count):
        """Read multiple registers"""
        return self.i2c.readfrom_mem(self.address, reg, count)
    
    def _write_register(self, reg, value):
        """Write to a register"""
        self.i2c.writeto_mem(self.address, reg, bytes([value]))
    
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
        
        # Set config: standby 1000ms, filter off
        self._write_register(0xF5, 0xA0)
    
    def read_raw_data(self):
        """Read raw sensor data"""
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
        
        if var1 == 0:
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