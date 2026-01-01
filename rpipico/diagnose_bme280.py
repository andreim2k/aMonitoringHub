"""
BME280 diagnostic script to check sensor connectivity and status
"""
import json
import time
from machine import Pin, I2C

print("=== BME280 DIAGNOSTIC ===\n")

# 1. Check I2C bus
print(json.dumps({"step": "1_i2c_scan"}))
try:
    i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=400000)
    devices = i2c.scan()
    print(json.dumps({
        "status": "i2c_ok",
        "devices_found": len(devices),
        "addresses": [f"0x{d:02X}" for d in devices]
    }))
except Exception as e:
    print(json.dumps({
        "status": "i2c_error",
        "error": str(e)
    }))
    import sys
    sys.exit(1)

# 2. Check if 0x76 or 0x77 is present
print("\n" + json.dumps({"step": "2_check_bme280_address"}))
bme280_found = False
bme280_addr = None
for addr in [0x76, 0x77]:
    if addr in devices:
        print(json.dumps({
            "status": "bme280_detected",
            "address": f"0x{addr:02X}"
        }))
        bme280_found = True
        bme280_addr = addr
        break

if not bme280_found:
    print(json.dumps({
        "status": "bme280_not_found",
        "message": "BME280 not detected on I2C bus"
    }))
    import sys
    sys.exit(1)

# 3. Try to read BME280 chip ID
print("\n" + json.dumps({"step": "3_read_chip_id"}))
try:
    chip_id = i2c.readfrom_mem(bme280_addr, 0xD0, 1)[0]
    print(json.dumps({
        "status": "chip_id_read",
        "chip_id": f"0x{chip_id:02X}",
        "expected": "0x60",
        "match": chip_id == 0x60
    }))
except Exception as e:
    print(json.dumps({
        "status": "chip_id_error",
        "error": str(e)
    }))

# 4. Try to read status register
print("\n" + json.dumps({"step": "4_read_status"}))
try:
    status = i2c.readfrom_mem(bme280_addr, 0xF3, 1)[0]
    print(json.dumps({
        "status": "status_read",
        "value": f"0x{status:02X}",
        "measuring": bool(status & 0x01),
        "im_update": bool(status & 0x01)
    }))
except Exception as e:
    print(json.dumps({
        "status": "status_error",
        "error": str(e)
    }))

# 5. Try to instantiate BME280
print("\n" + json.dumps({"step": "5_instantiate_bme280"}))
try:
    from lib.bme280 import BME280
    bme280 = BME280(i2c, address=bme280_addr)
    print(json.dumps({
        "status": "bme280_instantiated",
        "address": f"0x{bme280_addr:02X}"
    }))

    # Try to read data
    print("\n" + json.dumps({"step": "6_read_data"}))
    time.sleep(0.5)
    try:
        temp, press, hum = bme280.read_compensated_data()
        print(json.dumps({
            "status": "data_read_success",
            "temperature_c": round(temp, 2),
            "pressure_pa": round(press, 0),
            "humidity_percent": round(hum, 1)
        }))
    except Exception as e:
        print(json.dumps({
            "status": "data_read_error",
            "error": str(e),
            "error_type": type(e).__name__
        }))

except Exception as e:
    print(json.dumps({
        "status": "bme280_instantiate_error",
        "error": str(e),
        "error_type": type(e).__name__
    }))

print("\n=== END DIAGNOSTIC ===")
