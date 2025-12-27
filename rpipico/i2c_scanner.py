"""
Advanced I2C Scanner for Raspberry Pi Pico
Comprehensive scanning across all possible I2C configurations
"""

from machine import Pin, I2C
import time

print("=" * 50)
print("ADVANCED I2C SCANNER FOR RASPBERRY PI PICO")
print("=" * 50)

# All possible I2C pin combinations for Raspberry Pi Pico
i2c_configs = [
    # I2C0 configurations
    (0, 0, 1, "I2C0 - GP0(SDA)/GP1(SCL)"),
    (0, 2, 3, "I2C0 - GP2(SDA)/GP3(SCL)"),
    (0, 4, 5, "I2C0 - GP4(SDA)/GP5(SCL)"),
    (0, 6, 7, "I2C0 - GP6(SDA)/GP7(SCL)"),
    (0, 8, 9, "I2C0 - GP8(SDA)/GP9(SCL)"),
    (0, 10, 11, "I2C0 - GP10(SDA)/GP11(SCL)"),
    (0, 12, 13, "I2C0 - GP12(SDA)/GP13(SCL)"),
    (0, 14, 15, "I2C0 - GP14(SDA)/GP15(SCL)"),
    (0, 16, 17, "I2C0 - GP16(SDA)/GP17(SCL)"),
    (0, 18, 19, "I2C0 - GP18(SDA)/GP19(SCL)"),
    (0, 20, 21, "I2C0 - GP20(SDA)/GP21(SCL)"),
    
    # I2C1 configurations  
    (1, 2, 3, "I2C1 - GP2(SDA)/GP3(SCL)"),
    (1, 6, 7, "I2C1 - GP6(SDA)/GP7(SCL)"),
    (1, 10, 11, "I2C1 - GP10(SDA)/GP11(SCL)"),
    (1, 14, 15, "I2C1 - GP14(SDA)/GP15(SCL)"),
    (1, 18, 19, "I2C1 - GP18(SDA)/GP19(SCL)"),
    (1, 22, 27, "I2C1 - GP22(SDA)/GP27(SCL)"),
]

# Known I2C device addresses and their common names
known_devices = {
    0x23: "BH1750 (Light Sensor)",
    0x27: "PCF8574 (I/O Expander) / LCD",
    0x3C: "SSD1306 (OLED Display)",
    0x3D: "SSD1306 (OLED Display)",
    0x40: "INA219 (Current Sensor)",
    0x44: "SHT30/SHT31 (Temp/Humidity)",
    0x45: "SHT30/SHT31 (Temp/Humidity)",
    0x48: "ADS1115/PCF8591 (ADC)",
    0x4A: "ADS1115 (ADC)",
    0x4B: "ADS1115 (ADC)",
    0x50: "EEPROM (24C32/24C64)",
    0x51: "EEPROM (24C32/24C64)",
    0x57: "EEPROM (24C32/24C64)",
    0x5A: "MLX90614 (IR Thermometer)",
    0x68: "DS3231/DS1307 (RTC) / MPU6050 (IMU)",
    0x69: "MPU6050/MPU9250 (IMU)",
    0x76: "BME280/BMP280 (Environmental)",
    0x77: "BME280/BMP280 (Environmental)",
    0x3E: "SH1106 (OLED Display)",
    0x1E: "HMC5883L (Magnetometer)",
}

found_devices = []
total_configs = len(i2c_configs)

print(f"Scanning {total_configs} I2C configurations...\n")

# Test each configuration
for config_num, (bus, sda, scl, description) in enumerate(i2c_configs, 1):
    print(f"[{config_num:2d}/{total_configs}] Testing {description}")
    
    try:
        # Try different frequencies
        frequencies = [100000, 400000, 50000]  # 100kHz, 400kHz, 50kHz
        
        for freq in frequencies:
            try:
                i2c = I2C(bus, sda=Pin(sda), scl=Pin(scl), freq=freq)
                devices = i2c.scan()
                
                if devices:
                    print(f"         [OK] DEVICES FOUND at {freq}Hz!")
                    for addr in devices:
                        device_name = known_devices.get(addr, "Unknown Device")
                        print(f"           Address 0x{addr:02X} ({addr:3d}) - {device_name}")
                        
                        # Special handling for BME280/BMP280
                        if addr in [0x76, 0x77]:
                            try:
                                chip_id = i2c.readfrom_mem(addr, 0xD0, 1)[0]
                                if chip_id == 0x60:
                                    print(f"           >>> CONFIRMED BME280! Chip ID: 0x{chip_id:02X}")
                                elif chip_id == 0x58:
                                    print(f"           >>> CONFIRMED BMP280! Chip ID: 0x{chip_id:02X}")
                                else:
                                    print(f"           >>> Unknown chip ID: 0x{chip_id:02X}")
                            except OSError:
                                print(f"           >>> Cannot read chip ID (I/O error)")
                            except Exception as e:
                                print(f"           >>> Cannot read chip ID: {str(e)}")
                        
                        found_devices.append((bus, sda, scl, addr, device_name, freq))
                    break  # Found devices, no need to try other frequencies
                
            except OSError as e:
                # Try next frequency on I/O error
                pass
            except Exception as e:
                # Log other errors but continue
                print(f"         Unexpected error: {str(e)}")
        
        # If no devices found at any frequency
        if not any(d[0] == bus and d[1] == sda and d[2] == scl for d in found_devices):
            print(f"         No devices found")
            
    except Exception as e:
        print(f"         Error: {str(e)}")
    
    # Small delay between tests
    time.sleep(0.1)

print("\n" + "=" * 50)
print("SCAN RESULTS SUMMARY")
print("=" * 50)

if found_devices:
    print(f"Found {len(found_devices)} device(s) across {len(set((d[0], d[1], d[2]) for d in found_devices))} configuration(s):")
    print()
    
    # Group by configuration
    configs_with_devices = {}
    for bus, sda, scl, addr, name, freq in found_devices:
        config_key = (bus, sda, scl)
        if config_key not in configs_with_devices:
            configs_with_devices[config_key] = []
        configs_with_devices[config_key].append((addr, name, freq))
    
    for (bus, sda, scl), devices in configs_with_devices.items():
        print(f"I2C{bus} - GP{sda}(SDA)/GP{scl}(SCL):")
        for addr, name, freq in devices:
            print(f"  - 0x{addr:02X} ({addr:3d}) - {name} @ {freq}Hz")
        print()
    
    # BME280 specific results
    bme280_devices = [d for d in found_devices if d[3] in [0x76, 0x77]]
    if bme280_devices:
        print("[SUCCESS] BME280/BMP280 ENVIRONMENTAL SENSOR(S) DETECTED!")
        for bus, sda, scl, addr, name, freq in bme280_devices:
            print(f"   -> Use I2C{bus} with SDA=GP{sda}, SCL=GP{scl}")
            print(f"   -> Device address: 0x{addr:02X}")
            print(f"   -> Working frequency: {freq}Hz")
    else:
        print("[FAIL] No BME280/BMP280 sensors found")

else:
    print("[FAIL] NO I2C DEVICES FOUND")
    print("\nPossible issues:")
    print("- No devices connected")
    print("- Wrong wiring connections")
    print("- Power supply problems")
    print("- Damaged sensors (especially if 5V was applied to 3.3V sensors)")

print("\n" + "=" * 50)
print("RECOMMENDED NEXT STEPS")
print("=" * 50)

if bme280_devices:
    bus, sda, scl, addr, name, freq = bme280_devices[0]
    print("[OK] BME280 found! Update your code to use:")
    print(f"    i2c = I2C({bus}, sda=Pin({sda}), scl=Pin({scl}), freq={freq})")
    print(f"    bme280 = BME280(i2c, address=0x{addr:02X})")
elif found_devices:
    print("[OK] Other I2C devices found, but no BME280")
    print("- Check BME280 wiring and power (3.3V only!)")
    print("- Try a different BME280 module")
else:
    print("- Check all wiring connections")
    print("- Verify 3.3V power supply")
    print("- Test with a known working I2C device")
    print("- Consider that sensors may be damaged")

print("\nScan completed!")