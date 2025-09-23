"""
Advanced Raspberry Pi Pico Sensor Test
Complete functionality test for BME280 and MQ135 sensors
"""

import machine
import time
from machine import Pin, I2C, ADC
import sys

# Import our BME280 library
try:
    from bme280 import BME280
except ImportError:
    print("Warning: BME280 library not found, using basic communication test only")
    BME280 = None

print("=== Advanced Raspberry Pi Pico Sensor Test ===")
print("Complete functionality test for BME280 and MQ135")
print("=" * 50)

# Configuration
I2C_SDA = 4
I2C_SCL = 5
MQ135_PIN = 28

# Initialize I2C
try:
    i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=400000)
    print(f"✓ I2C initialized (SDA=GP{I2C_SDA}, SCL=GP{I2C_SCL})")
except Exception as e:
    print(f"✗ I2C initialization failed: {e}")
    sys.exit(1)

# Initialize MQ135 ADC
try:
    mq135_adc = ADC(Pin(MQ135_PIN))
    print(f"✓ MQ135 ADC initialized (GP{MQ135_PIN})")
except Exception as e:
    print(f"✗ MQ135 ADC initialization failed: {e}")

print("\\n" + "=" * 50)

# BME280 Advanced Test
print("BME280 ADVANCED FUNCTIONALITY TEST")
print("=" * 50)

devices = i2c.scan()
bme280_found = False
bme280_sensor = None

for addr in [0x76, 0x77]:
    if addr in devices:
        try:
            if BME280:
                bme280_sensor = BME280(i2c, addr)
                print(f"✓ BME280 initialized successfully at address 0x{addr:02X}")
                bme280_found = True
                break
            else:
                # Basic communication test
                chip_id = i2c.readfrom_mem(addr, 0xD0, 1)[0]
                if chip_id == 0x60:
                    print(f"✓ BME280 detected at address 0x{addr:02X} (Chip ID: 0x{chip_id:02X})")
                    bme280_found = True
                    break
        except Exception as e:
            print(f"✗ BME280 communication error at 0x{addr:02X}: {e}")

if bme280_found and bme280_sensor:
    print("\\n--- BME280 Sensor Readings ---")
    try:
        for i in range(5):
            temp, pressure, humidity = bme280_sensor.read_all()
            
            # Convert pressure to different units
            pressure_hpa = pressure / 100  # hPa (mbar)
            pressure_inhg = pressure * 0.0002953  # inches of mercury
            
            print(f"Reading #{i+1}:")
            print(f"  Temperature: {temp:.2f}°C ({temp*9/5+32:.2f}°F)")
            print(f"  Pressure:    {pressure:.2f} Pa ({pressure_hpa:.2f} hPa)")
            print(f"  Humidity:    {humidity:.2f}%")
            print()
            
            time.sleep(2)
            
    except Exception as e:
        print(f"✗ BME280 reading error: {e}")

elif bme280_found:
    print("BME280 detected but advanced library not available")
else:
    print("✗ BME280 not found or not responding")

print("=" * 50)

# MQ135 Advanced Test
print("MQ135 ADVANCED AIR QUALITY TEST")
print("=" * 50)

class MQ135:
    def __init__(self, adc):
        self.adc = adc
        # Calibration constants (these may need adjustment based on your specific sensor)
        self.r_load = 10000  # 10kΩ load resistor
        self.r_zero = 76.63  # Sensor resistance in clean air (needs calibration)
        
    def read_voltage(self):
        """Read voltage from ADC"""
        raw = self.adc.read_u16()
        voltage = (raw / 65535) * 3.3
        return voltage
    
    def read_resistance(self):
        """Calculate sensor resistance"""
        voltage = self.read_voltage()
        if voltage == 0:
            return float('inf')
        # Calculate resistance using voltage divider
        resistance = ((3.3 - voltage) / voltage) * self.r_load
        return resistance
    
    def read_ratio(self):
        """Read Rs/R0 ratio"""
        resistance = self.read_resistance()
        if self.r_zero == 0:
            return 0
        return resistance / self.r_zero
    
    def read_ppm(self):
        """Estimate CO2 concentration in ppm"""
        ratio = self.read_ratio()
        if ratio <= 0:
            return 0
        # Approximation formula (needs calibration with known gas concentrations)
        ppm = 116.6020682 * (ratio ** -2.769034857)
        return max(0, ppm)
    
    def get_air_quality_status(self, ppm):
        """Get air quality status based on CO2 levels"""
        if ppm < 400:
            return "Excellent"
        elif ppm < 800:
            return "Good"
        elif ppm < 1200:
            return "Fair"
        elif ppm < 1800:
            return "Poor"
        else:
            return "Very Poor"

try:
    mq135 = MQ135(mq135_adc)
    print("✓ MQ135 sensor interface initialized")
    
    print("\\n--- MQ135 Calibration Info ---")
    print("Note: This sensor requires calibration in clean air for accurate readings")
    print("Current calibration values:")
    print(f"  R_Load: {mq135.r_load}Ω")
    print(f"  R_Zero: {mq135.r_zero}Ω (may need adjustment)")
    
    print("\\n--- MQ135 Sensor Readings ---")
    print("Taking multiple readings for stability...")
    
    readings = []
    for i in range(10):
        voltage = mq135.read_voltage()
        resistance = mq135.read_resistance()
        ratio = mq135.read_ratio()
        ppm = mq135.read_ppm()
        
        readings.append((voltage, resistance, ratio, ppm))
        
        if i < 5 or i % 2 == 0:  # Show first 5 and then every other reading
            status = mq135.get_air_quality_status(ppm)
            print(f"Reading #{i+1:2d}: {voltage:.3f}V, {resistance:.1f}Ω, "
                  f"Ratio: {ratio:.3f}, ~{ppm:.1f}ppm ({status})")
        
        time.sleep(0.5)
    
    # Calculate averages
    avg_voltage = sum(r[0] for r in readings) / len(readings)
    avg_resistance = sum(r[1] for r in readings) / len(readings)
    avg_ratio = sum(r[2] for r in readings) / len(readings)
    avg_ppm = sum(r[3] for r in readings) / len(readings)
    
    print(f"\\nAverage values:")
    print(f"  Voltage: {avg_voltage:.3f}V")
    print(f"  Resistance: {avg_resistance:.1f}Ω")
    print(f"  Rs/R0 Ratio: {avg_ratio:.3f}")
    print(f"  Estimated CO2: {avg_ppm:.1f}ppm")
    print(f"  Air Quality: {mq135.get_air_quality_status(avg_ppm)}")
    
except Exception as e:
    print(f"✗ MQ135 test failed: {e}")

print("\\n" + "=" * 50)
print("SENSOR CONNECTION STATUS SUMMARY")
print("=" * 50)

# Final status check
print(f"BME280 (I2C):    {'✓ Working' if bme280_found else '✗ Not detected'}")

try:
    test_voltage = mq135_adc.read_u16()
    mq135_status = "✓ Working"
except:
    mq135_status = "✗ Not working"
print(f"MQ135 (Analog):  {mq135_status}")

print("\\n--- Troubleshooting Guide ---")
if not bme280_found:
    print("BME280 Issues:")
    print("  • Check I2C wiring (SDA, SCL, VCC, GND)")
    print("  • Verify sensor address (0x76 or 0x77)")
    print("  • Check 3.3V power supply")
    print("  • Try different I2C pins")

print("\\nMQ135 Notes:")
print("  • Sensor needs 24-48h burn-in time for stable readings")
print("  • Calibrate R_zero in clean air for accurate CO2 measurements")
print("  • Values are estimates - use calibrated equipment for precision")

print("\\nWiring Reference:")
print("BME280: VCC→3.3V, GND→GND, SDA→GP4, SCL→GP5")
print("MQ135:  VCC→5V, GND→GND, A0→GP28")

print("\\nTest completed!")