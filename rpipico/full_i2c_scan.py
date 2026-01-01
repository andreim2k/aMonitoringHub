"""
Full I2C address scan to find any connected devices
"""
import json
import time
from machine import Pin, I2C

print(json.dumps({"scan": "full_i2c_bus"}))

try:
    i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=400000)

    devices = i2c.scan()
    print(json.dumps({
        "status": "scan_complete",
        "devices_found": len(devices),
        "addresses_decimal": devices,
        "addresses_hex": [f"0x{addr:02X}" for addr in devices]
    }))

    # If any devices found, try to read chip ID
    if devices:
        print(json.dumps({"checking_devices": True}))
        for addr in devices:
            try:
                # Try to read first byte (could be chip ID)
                data = i2c.readfrom(addr, 1)
                print(json.dumps({
                    "address": f"0x{addr:02X}",
                    "first_byte": f"0x{data[0]:02X}",
                    "decimal": data[0]
                }))

                # Check if it's BME280 (chip ID 0x60)
                if addr in [0x76, 0x77]:
                    try:
                        chip_id = i2c.readfrom_mem(addr, 0xD0, 1)[0]
                        print(json.dumps({
                            "address": f"0x{addr:02X}",
                            "chip_id": f"0x{chip_id:02X}",
                            "is_bme280": chip_id == 0x60
                        }))
                    except:
                        pass
            except Exception as e:
                pass
    else:
        print(json.dumps({"warning": "no_devices_found"}))

except Exception as e:
    print(json.dumps({"error": str(e)}))
