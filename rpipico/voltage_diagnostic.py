"""
Voltage and Connection Diagnostic Script
Helps troubleshoot BME280 and sensor connection issues
"""

import machine
import time
from machine import Pin, I2C, ADC

print("=== Raspberry Pi Pico Voltage & Connection Diagnostic ===")
print("This script helps diagnose sensor connection issues")
print("=" * 60)

# Test I2C initialization with different pin combinations
i2c_configs = [
    (4, 5, "Default"),
    (6, 7, "Alternative 1"), 
    (16, 17, "Alternative 2"),
    (8, 9, "Alternative 3")
]

print("--- Testing I2C Pin Configurations ---")
working_i2c = None

for sda, scl, name in i2c_configs:
    try:
        test_i2c = I2C(0, sda=Pin(sda), scl=Pin(scl), freq=400000)
        devices = test_i2c.scan()
        print(f"✓ {name} (SDA=GP{sda}, SCL=GP{scl}): Found {len(devices)} device(s)")
        
        if devices:
            for device in devices:
                print(f"    Device at 0x{device:02X}")
                if device == 0x76 or device == 0x77:
                    print(f"    → BME280 found!")
                    working_i2c = test_i2c
            
        if working_i2c:
            break
            
    except Exception as e:
        print(f"✗ {name} (SDA=GP{sda}, SCL=GP{scl}): Failed - {e}")

print("\n--- Power Supply Test ---")
print("Testing 3.3V rail stability (indirect measurement)")

# Test ADC channels to check for power issues
test_pins = [26, 27, 28]  # ADC0, ADC1, ADC2
print("ADC Reference Voltage Test:")

for pin in test_pins:
    try:
        # Read with no sensor connected to check noise/stability
        adc = ADC(Pin(pin))
        readings = []
        for _ in range(5):
            raw = adc.read_u16()
            voltage = (raw / 65535) * 3.3
            readings.append(voltage)
            time.sleep(0.1)
        
        avg_v = sum(readings) / len(readings)
        std_dev = (sum((x - avg_v) ** 2 for x in readings) / len(readings)) ** 0.5
        
        print(f"  GP{pin} (ADC{pin-26}): Avg={avg_v:.3f}V, StdDev={std_dev:.4f}V")
        
    except Exception as e:
        print(f"  GP{pin}: Error - {e}")

print("\n--- BME280 Voltage Compatibility Check ---")
print("CRITICAL: BME280 voltage requirements:")
print("  ✓ Safe voltage range: 1.71V - 3.6V")  
print("  ✓ Recommended voltage: 3.3V")
print("  ⚠️  DANGER: 5V will damage the sensor!")
print("  → Connect BME280 VCC to Pico Pin 36 (3.3V)")

print("\n--- MQ135 Voltage Requirements ---")
print("MQ135 voltage requirements:")
print("  ✓ Operating voltage: 5V (preferred) or 3.3V")
print("  → Connect MQ135 VCC to Pico Pin 40 (5V)")

if working_i2c:
    print("\n--- BME280 Recovery Test ---")
    print("Attempting to communicate with BME280...")
    
    devices = working_i2c.scan()
    for addr in [0x76, 0x77]:
        if addr in devices:
            try:
                # Try to read chip ID
                chip_id = working_i2c.readfrom_mem(addr, 0xD0, 1)[0]
                print(f"✓ BME280 responds at 0x{addr:02X}, Chip ID: 0x{chip_id:02X}")
                
                if chip_id == 0x60:
                    print("  → BME280 appears functional!")
                else:
                    print("  ⚠️  Unexpected chip ID - sensor may be damaged")
                    
                # Try reading status register
                status = working_i2c.readfrom_mem(addr, 0xF3, 1)[0]
                print(f"  Status register: 0x{status:02X}")
                
            except Exception as e:
                print(f"✗ BME280 communication failed: {e}")
                print("  → Sensor may be damaged by overvoltage")

print("\n--- Troubleshooting Recommendations ---")

if not working_i2c or not any(d in [0x76, 0x77] for d in working_i2c.scan()):
    print("BME280 Not Found - Try these steps:")
    print("1. IMMEDIATELY disconnect any 5V connection from BME280")
    print("2. Connect BME280 VCC to 3.3V (Pin 36) only")
    print("3. Check all connections:")
    print("   - VCC: Pin 36 (3.3V)")
    print("   - GND: Pin 38") 
    print("   - SDA: Pin 6 (GP4)")
    print("   - SCL: Pin 7 (GP5)")
    print("4. Check for loose connections")
    print("5. Try a different BME280 module if available")
    print("6. If sensor was connected to 5V, it may be permanently damaged")

print("\n--- Safety Reminders ---")
print("⚠️  Always check sensor voltage requirements before connecting!")
print("⚠️  BME280: 3.3V MAX - 5V will destroy it!")
print("⚠️  When in doubt, check the datasheet!")

print("\nDiagnostic completed!")