"""
Try to directly access BME280 without scanning first
"""
import json
import time
from machine import Pin, I2C

print(json.dumps({"test": "direct_bme280_access"}))

try:
    i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=100000)  # Try lower speed first
    time.sleep(0.5)

    # Try to read directly from 0x76 without scanning
    print(json.dumps({"attempt": 1, "address": "0x76", "freq": 100000}))
    try:
        chip_id = i2c.readfrom_mem(0x76, 0xD0, 1)
        print(json.dumps({
            "success": True,
            "chip_id": f"0x{chip_id[0]:02X}",
            "address": "0x76"
        }))
    except Exception as e:
        print(json.dumps({
            "address": "0x76",
            "error": str(e)
        }))

    # Try 0x77
    print(json.dumps({"attempt": 2, "address": "0x77", "freq": 100000}))
    try:
        chip_id = i2c.readfrom_mem(0x77, 0xD0, 1)
        print(json.dumps({
            "success": True,
            "chip_id": f"0x{chip_id[0]:02X}",
            "address": "0x77"
        }))
    except Exception as e:
        print(json.dumps({
            "address": "0x77",
            "error": str(e)
        }))

    # Try higher frequency
    i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=400000)
    time.sleep(0.5)

    print(json.dumps({"attempt": 3, "address": "0x76", "freq": 400000}))
    try:
        chip_id = i2c.readfrom_mem(0x76, 0xD0, 1)
        print(json.dumps({
            "success": True,
            "chip_id": f"0x{chip_id[0]:02X}",
            "address": "0x76"
        }))
    except Exception as e:
        print(json.dumps({
            "address": "0x76",
            "error": str(e)
        }))

except Exception as e:
    print(json.dumps({"fatal_error": str(e)}))
