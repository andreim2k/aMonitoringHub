"""
Diagnose why every read is failing
"""
import json
import time
from machine import Pin, I2C
from lib.bme280 import BME280

print(json.dumps({"diagnostic": "sensor_read_failures"}))

try:
    i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=400000)
    time.sleep(0.5)

    bme280 = BME280(i2c, address=0x76)
    time.sleep(2.0)

    print(json.dumps({"step": "attempting_multiple_reads", "count": 5}))

    for attempt in range(5):
        try:
            print(json.dumps({"read_attempt": attempt + 1}))
            temp_c, pressure_pa, humidity_pct = bme280.read_compensated_data()
            print(json.dumps({
                "attempt": attempt + 1,
                "result": "success",
                "temp": round(temp_c, 2)
            }))
        except Exception as e:
            print(json.dumps({
                "attempt": attempt + 1,
                "result": "failed",
                "error": str(e),
                "error_type": type(e).__name__
            }))

            # Try to read status register to see what's happening
            try:
                status = i2c.readfrom_mem(0x76, 0xF3, 1)[0]
                print(json.dumps({
                    "status_register": f"0x{status:02X}",
                    "measuring": bool(status & 0x01),
                    "im_update": bool(status & 0x01)
                }))
            except:
                pass

        time.sleep(0.5)

except Exception as e:
    print(json.dumps({
        "fatal_error": str(e),
        "type": type(e).__name__
    }))
