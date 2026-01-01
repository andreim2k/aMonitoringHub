"""
Test reading data from BME280 on GP14/GP15
"""
import json
import time
from machine import Pin, I2C
from lib.bme280 import BME280

print(json.dumps({"test": "BME280_data_read"}))

try:
    # Initialize I2C on correct pins
    i2c = I2C(1, sda=Pin(14), scl=Pin(15), freq=400000)
    time.sleep(0.2)

    # Initialize BME280
    print(json.dumps({"step": "bme280_init"}))
    bme280 = BME280(i2c, address=0x76)
    time.sleep(0.5)

    # Read data
    print(json.dumps({"step": "reading_sensor_data"}))
    temp_c, pressure_pa, humidity_pct = bme280.read_compensated_data()

    print(json.dumps({
        "status": "success",
        "temperature_c": round(temp_c, 2),
        "humidity_percent": round(humidity_pct, 1),
        "pressure_hpa": round(pressure_pa / 100.0, 1),
        "pressure_pa": round(pressure_pa, 0)
    }))

except Exception as e:
    print(json.dumps({
        "status": "error",
        "error": str(e),
        "type": type(e).__name__
    }))
