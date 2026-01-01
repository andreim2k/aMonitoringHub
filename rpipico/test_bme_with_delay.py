"""
Test BME280 with longer initialization delay
"""
import json
import time
from machine import Pin, I2C
from lib.bme280 import BME280

print(json.dumps({"test": "BME280_with_delays"}))

try:
    i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=400000)
    time.sleep(0.5)

    print(json.dumps({"step": "initializing_bme280"}))
    bme280 = BME280(i2c, address=0x76)

    # Give sensor time to initialize and start measuring
    print(json.dumps({"step": "waiting_for_sensor_ready", "delay_ms": 2000}))
    time.sleep(2.0)

    print(json.dumps({"step": "reading_data"}))
    for attempt in range(3):
        try:
            temp_c, pressure_pa, humidity_pct = bme280.read_compensated_data()
            print(json.dumps({
                "attempt": attempt + 1,
                "status": "success",
                "temperature_c": round(temp_c, 2),
                "humidity_percent": round(humidity_pct, 1),
                "pressure_hpa": round(pressure_pa / 100.0, 1)
            }))
            break
        except Exception as e:
            print(json.dumps({
                "attempt": attempt + 1,
                "error": str(e)
            }))
            if attempt < 2:
                time.sleep(1.0)

except Exception as e:
    print(json.dumps({
        "fatal_error": str(e),
        "type": type(e).__name__
    }))
