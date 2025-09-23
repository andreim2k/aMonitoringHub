"""
Continuous JSON Sensor Monitor for Raspberry Pi Pico
Outputs BME280 + MQ135 sensor data in JSON format every second over USB
"""

import json
import time
import machine
from machine import Pin, I2C, ADC

# BME280 Library (corrected for I2C1)
class BME280:
    def __init__(self, i2c, address=0x76):
        self.i2c = i2c
        self.address = address
        
        # Verify chip ID
        chip_id = self._read_register(0xD0)
        if chip_id != 0x60:
            raise Exception(f"Invalid chip ID: 0x{chip_id:02X}")
        
        # Reset and configure sensor
        self._write_register(0xE0, 0xB6)
        time.sleep(0.01)
        self._read_calibration_data()
        self._configure_sensor()
    
    def _read_register(self, reg):
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]
    
    def _read_registers(self, reg, count):
        return self.i2c.readfrom_mem(self.address, reg, count)
    
    def _write_register(self, reg, value):
        self.i2c.writeto_mem(self.address, reg, bytes([value]))
    
    def _read_calibration_data(self):
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
        if value & (1 << (bits - 1)):
            return value - (1 << bits)
        return value
    
    def _configure_sensor(self):
        self._write_register(0xF2, 0x01)  # Humidity oversampling x1
        self._write_register(0xF4, 0x27)  # Temp/pressure oversampling x1, normal mode
        self._write_register(0xF5, 0xA0)  # Config: standby 1000ms, filter off
    
    def read_raw_data(self):
        data = self._read_registers(0xF7, 8)
        raw_press = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_temp = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        raw_hum = (data[6] << 8) | data[7]
        return raw_temp, raw_press, raw_hum
    
    def read_compensated_data(self):
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


# MQ135 Air Quality Sensor (calibrated)
class MQ135:
    def __init__(self, adc_pin, r_zero=42304.5):
        self.adc = ADC(Pin(adc_pin))
        self.r_load = 10000  # 10kΩ load resistor
        self.r_zero = r_zero  # Calibrated resistance in clean air
        
    def read_voltage(self):
        raw = self.adc.read_u16()
        voltage = (raw / 65535) * 3.3
        return voltage, raw
    
    def read_resistance(self):
        voltage, raw = self.read_voltage()
        if voltage <= 0.01:
            return float('inf'), voltage, raw
        resistance = ((3.3 - voltage) / voltage) * self.r_load
        return resistance, voltage, raw
    
    def read_ratio(self):
        resistance, voltage, raw = self.read_resistance()
        if resistance == float('inf') or self.r_zero == 0:
            return 0, resistance, voltage, raw
        ratio = resistance / self.r_zero
        return ratio, resistance, voltage, raw
    
    def read_co2_ppm(self):
        ratio, resistance, voltage, raw = self.read_ratio()
        if ratio <= 0:
            return 0, ratio, resistance, voltage, raw
        ppm = 116.6020682 * (ratio ** -2.769034857)
        return max(0, min(10000, ppm)), ratio, resistance, voltage, raw
    
    def read_nh3_ppm(self):
        ratio, resistance, voltage, raw = self.read_ratio()
        if ratio <= 0:
            return 0, ratio, resistance, voltage, raw
        ppm = 102.694 * (ratio ** -2.815)
        return max(0, min(500, ppm)), ratio, resistance, voltage, raw
    
    def read_alcohol_ppm(self):
        ratio, resistance, voltage, raw = self.read_ratio()
        if ratio <= 0:
            return 0, ratio, resistance, voltage, raw
        ppm = 77.255 * (ratio ** -3.18)
        return max(0, min(1000, ppm)), ratio, resistance, voltage, raw
    
    def get_air_quality_status(self, co2_ppm):
        if co2_ppm < 400:
            return 'Excellent', 1
        elif co2_ppm < 600:
            return 'Good', 2
        elif co2_ppm < 1000:
            return 'Fair', 3
        elif co2_ppm < 1500:
            return 'Poor', 4
        elif co2_ppm < 2500:
            return 'Very Poor', 5
        else:
            return 'Hazardous', 6
    
    def get_all_readings(self):
        co2_ppm, ratio, resistance, voltage, raw = self.read_co2_ppm()
        nh3_ppm, _, _, _, _ = self.read_nh3_ppm()
        alcohol_ppm, _, _, _, _ = self.read_alcohol_ppm()
        status, aqi = self.get_air_quality_status(co2_ppm)
        
        return {
            'raw_adc': raw,
            'voltage_v': round(voltage, 3),
            'resistance_ohm': round(resistance, 1),
            'ratio_rs_r0': round(ratio, 3),
            'co2_ppm': round(co2_ppm, 1),
            'nh3_ppm': round(nh3_ppm, 1),
            'alcohol_ppm': round(alcohol_ppm, 1),
            'air_quality_status': status,
            'air_quality_index': aqi,
            'r_zero_ohm': self.r_zero
        }


# Main monitoring function
def start_json_monitoring():
    print("Initializing sensors...")
    
    try:
        # Initialize I2C1 for BME280 (corrected pins)
        i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=400000)
        bme280 = BME280(i2c)
        print("✓ BME280 initialized on I2C1 (SDA=GP2, SCL=GP3)")
        
        # Initialize MQ135 (calibrated)
        mq135 = MQ135(28, r_zero=42304.5)
        print("✓ MQ135 initialized on GPIO 28 (calibrated)")
        
        print("Starting continuous JSON monitoring...")
        print("Press Ctrl+C to stop")
        print("-" * 50)
        
        while True:
            try:
                # Get current timestamp
                timestamp = time.ticks_ms() / 1000.0
                
                # Read BME280 data
                temp_c, pressure_pa, humidity_pct = bme280.read_compensated_data()
                pressure_hpa = pressure_pa / 100.0
                
                # Read MQ135 data
                mq135_data = mq135.get_all_readings()
                
                # Create JSON payload
                sensor_data = {
                    "timestamp": timestamp,
                    "bme280": {
                        "temperature_c": round(temp_c, 2),
                        "humidity_percent": round(humidity_pct, 1),
                        "pressure_hpa": round(pressure_hpa, 1),
                        "pressure_pa": round(pressure_pa, 0)
                    },
                    "mq135": mq135_data
                }
                
                # Output JSON to USB serial
                print(json.dumps(sensor_data))
                
                # Wait 1 second
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
                break
            except Exception as e:
                # Continue monitoring even if one reading fails
                error_data = {
                    "timestamp": time.ticks_ms() / 1000.0,
                    "error": str(e),
                    "status": "sensor_error"
                }
                print(json.dumps(error_data))
                time.sleep(1)
                
    except Exception as e:
        print(f"Failed to initialize sensors: {e}")


# Start monitoring when script runs
if __name__ == "__main__":
    start_json_monitoring()