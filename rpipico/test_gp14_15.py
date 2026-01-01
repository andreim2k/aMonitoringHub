"""
Test BME280 on GPIO 14 (SDA) and GPIO 15 (SCL) - I2C Bus 1
"""
import json
import time
from machine import Pin, I2C

print(json.dumps({"test": "GPIO_14_15_I2C1_BME280"}))

try:
    # Explicitly use I2C1 with GPIO 14 and 15
    print(json.dumps({"step": "init_i2c", "bus": 1, "sda": 14, "scl": 15}))
    i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=400000)
    time.sleep(0.2)

    # Scan for devices
    devices = i2c.scan()
    print(json.dumps({
        "status": "scan_complete",
        "devices_found": len(devices),
        "addresses_hex": [f"0x{d:02X}" for d in devices]
    }))

    # If found, try to read chip ID from both possible BME280 addresses
    if devices:
        for addr in devices:
            try:
                chip_id = i2c.readfrom_mem(addr, 0xD0, 1)[0]
                is_bme280 = chip_id == 0x60
                print(json.dumps({
                    "address": f"0x{addr:02X}",
                    "chip_id": f"0x{chip_id:02X}",
                    "is_bme280": is_bme280
                }))
            except Exception as e:
                print(json.dumps({
                    "address": f"0x{addr:02X}",
                    "chip_id_read_error": str(e)
                }))
    else:
        print(json.dumps({"warning": "No devices found on I2C1 (GP14/GP15)"}))

except Exception as e:
    print(json.dumps({"error": str(e), "type": type(e).__name__}))
