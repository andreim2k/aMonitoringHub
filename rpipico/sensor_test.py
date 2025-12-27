"""
Raspberry Pi Pico Sensor Test
Tests BME280 (temperature, humidity, pressure) and MQ135 (air quality) sensors
"""

import machine
import time
from machine import Pin, I2C, ADC
import sys

print("=== Raspberry Pi Pico Sensor Test ===")
print("Testing BME280 and MQ135 sensors...")
print("=" * 40)

# Import configuration from lib/config
try:
    from lib.config import I2C_BUS, I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQ, MQ135_PIN
except ImportError:
    # Fallback defaults from lib/config
    I2C_BUS = 1
    I2C_SDA_PIN = 2
    I2C_SCL_PIN = 3
    I2C_FREQ = 400000
    MQ135_PIN = 28

# Initialize I2C for BME280
try:
    i2c = I2C(I2C_BUS, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=I2C_FREQ)
    print(f"✓ I2C{I2C_BUS} initialized on SDA=GP{I2C_SDA_PIN}, SCL=GP{I2C_SCL_PIN}")
except Exception as e:
    print(f"✗ Failed to initialize I2C: {e}")
    sys.exit(1)

# Initialize ADC for MQ135
try:
    mq135_adc = ADC(Pin(MQ135_PIN))
    print(f"✓ ADC initialized for MQ135 on GPIO {MQ135_PIN}")
except Exception as e:
    print(f"✗ Failed to initialize ADC: {e}")

# Scan for I2C devices
print("\n--- I2C Device Scan ---")
devices = i2c.scan()
print(f"Found {len(devices)} I2C device(s)")

if devices:
    for device in devices:
        print(f"  Device at address: 0x{device:02X}")
        if device == 0x76 or device == 0x77:
            print(f"    → Likely BME280 sensor!")
        elif device == 0x48:
            print(f"    → Possible MQ135 with I2C interface")
else:
    print("  No I2C devices found")

# BME280 Basic Communication Test
print("\n--- BME280 Communication Test ---")
BME280_ADDR = 0x76  # Default BME280 address (can also be 0x77)

# Try both common BME280 addresses
for addr in [0x76, 0x77]:
    if addr in devices:
        BME280_ADDR = addr
        break

if BME280_ADDR in devices:
    try:
        # Read BME280 chip ID (should be 0x60)
        chip_id = i2c.readfrom_mem(BME280_ADDR, 0xD0, 1)[0]
        print(f"✓ BME280 found at address 0x{BME280_ADDR:02X}")
        print(f"  Chip ID: 0x{chip_id:02X}", end="")
        if chip_id == 0x60:
            print(" (Valid BME280)")
        else:
            print(" (Unexpected chip ID)")
            
        # Read BME280 status register
        status = i2c.readfrom_mem(BME280_ADDR, 0xF3, 1)[0]
        print(f"  Status: 0x{status:02X}")
        
    except Exception as e:
        print(f"✗ Failed to communicate with BME280: {e}")
else:
    print("✗ BME280 not found on I2C bus")

# MQ135 ADC Test
print("\n--- MQ135 ADC Test ---")
try:
    # Read multiple samples from MQ135
    samples = []
    for i in range(10):
        raw_value = mq135_adc.read_u16()
        voltage = (raw_value / 65535) * 3.3  # Convert to voltage
        samples.append((raw_value, voltage))
        time.sleep(0.1)
    
    print(f"✓ MQ135 ADC readings successful")
    print(f"  Sample readings (last 5):")
    for i, (raw, volt) in enumerate(samples[-5:], len(samples)-4):
        print(f"    #{i}: Raw={raw:5d}, Voltage={volt:.3f}V")
    
    # Calculate average
    avg_raw = sum(s[0] for s in samples) / len(samples)
    avg_volt = sum(s[1] for s in samples) / len(samples)
    print(f"  Average: Raw={avg_raw:.1f}, Voltage={avg_volt:.3f}V")
    
    # Basic air quality indication
    if avg_volt < 1.0:
        quality = "Good"
    elif avg_volt < 2.0:
        quality = "Moderate"
    else:
        quality = "Poor"
    print(f"  Air Quality Indication: {quality}")
    
except Exception as e:
    print(f"✗ Failed to read MQ135: {e}")

# Connection Status Summary
print("\n" + "=" * 40)
print("SENSOR CONNECTION SUMMARY")
print("=" * 40)

bme280_status = "✓ Connected" if BME280_ADDR in devices else "✗ Not Found"
print(f"BME280 (I2C):     {bme280_status}")

try:
    test_read = mq135_adc.read_u16()
    mq135_status = "✓ Connected"
except OSError:
    mq135_status = "✗ Not Found (I/O error)"
except Exception:
    mq135_status = "✗ Not Found"
print(f"MQ135 (ADC):      {mq135_status}")

print("\n--- Wiring Guide ---")
print("BME280 Connections:")
print(f"  VCC → 3.3V")
print(f"  GND → GND")
print(f"  SDA → GP{I2C_SDA_PIN}")
print(f"  SCL → GP{I2C_SCL_PIN}")

print("MQ135 Connections:")
print(f"  VCC → 5V (or 3.3V)")
print(f"  GND → GND")
print(f"  A0  → GP{MQ135_PIN} (ADC2)")

print("\nTest completed!")