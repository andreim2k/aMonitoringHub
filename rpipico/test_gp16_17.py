"""
Test BME280 on GPIO 16 (SDA) and GPIO 17 (SCL) - I2C Bus 0
"""
import json
import time
from machine import Pin, I2C

print(json.dumps({"test": "GPIO_16_17_I2C0"}))

try:
    # Explicitly use I2C0 with GPIO 16 and 17
    print(json.dumps({"step": "init_i2c", "bus": 0, "sda": 16, "scl": 17}))
    i2c = I2C(0, sda=Pin(16), scl=Pin(17), freq=400000)
    time.sleep(0.2)

    # Scan for devices
    devices = i2c.scan()
    print(json.dumps({
        "status": "scan_complete",
        "devices_found": len(devices),
        "addresses_hex": [f"0x{d:02X}" for d in devices]
    }))

    # If found, try to read chip ID
    if devices:
        for addr in devices:
            try:
                chip_id = i2c.readfrom_mem(addr, 0xD0, 1)[0]
                print(json.dumps({
                    "address": f"0x{addr:02X}",
                    "chip_id": f"0x{chip_id:02X}",
                    "is_bme280": chip_id == 0x60
                }))
            except:
                pass
    else:
        print(json.dumps({"warning": "No devices found on I2C0"}))

except Exception as e:
    print(json.dumps({"error": str(e), "type": type(e).__name__}))
