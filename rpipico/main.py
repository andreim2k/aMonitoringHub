"""
Auto-boot JSON Sensor Monitor for Raspberry Pi Pico
This file runs automatically when the Pico boots up
Outputs BME280 + MQ135 sensor data in JSON format every second over USB
"""

import json
import time
from machine import Pin, I2C, ADC

# Import sensor libraries and configuration
from lib.bme280 import BME280
from lib.mq135 import MQ135
from lib.config import (
    I2C_BUS, I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQ,
    MQ135_PIN, MQ135_R_ZERO
)


# Auto-start monitoring function
def auto_start_monitoring():
    """Auto-start monitoring on boot"""
    print("[START] Auto-starting JSON sensor monitoring...")
    
    # Small delay to ensure USB is ready
    time.sleep(2)
    
    # Initialize sensors independently
    bme280 = None
    mq135 = None

    # Try to initialize BME280 (retry up to 10 times)
    max_retries = 10
    retry_count = 0
    while retry_count < max_retries and bme280 is None:
        try:
            i2c = I2C(I2C_BUS, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=I2C_FREQ)
            bme280 = BME280(i2c)
            print(f"[OK] BME280 initialized on I2C{I2C_BUS} (SDA=GP{I2C_SDA_PIN}, SCL=GP{I2C_SCL_PIN})")
            break
        except Exception as e:
            retry_count += 1
            print(f"[WARN] BME280 init attempt {retry_count}/{max_retries} failed: {e}")
            if retry_count < max_retries:
                time.sleep(2)
            else:
                print("[WARN] BME280 unavailable - will send MQ135 data only")

    # Try to initialize MQ135 (critical sensor for air quality)
    try:
        mq135 = MQ135(MQ135_PIN, r_zero=MQ135_R_ZERO)
        print(f"[OK] MQ135 initialized on GPIO {MQ135_PIN} (calibrated)")
    except Exception as e:
        print(f"[ERROR] MQ135 initialization failed: {e}")
        print(f"[INFO] Check wiring on GPIO {MQ135_PIN}")
        return

    # Require at least one sensor to be working
    if bme280 is None and mq135 is None:
        print("[ERROR] No sensors available. Check all connections.")
        return

    print("[INFO] Starting continuous JSON monitoring (auto-boot)")
    print("[INFO] Press Ctrl+C to stop, or reset Pico to restart")
    print("-" * 50)

    # Start continuous monitoring loop
    while True:
        try:
            # Get current timestamp
            timestamp = time.ticks_ms() / 1000.0
            sensor_data = {"timestamp": timestamp}

            # Read BME280 if available
            if bme280 is not None:
                try:
                    temp_c, pressure_pa, humidity_pct = bme280.read_compensated_data()
                    pressure_hpa = pressure_pa / 100.0
                    sensor_data["bme280"] = {
                        "temperature_c": round(temp_c, 2),
                        "humidity_percent": round(humidity_pct, 1),
                        "pressure_hpa": round(pressure_hpa, 1),
                        "pressure_pa": round(pressure_pa, 0)
                    }
                except Exception as e:
                    # BME280 error, but continue with MQ135
                    print(json.dumps({"timestamp": timestamp, "error": f"BME280 read error: {str(e)}"}))

            # Always try to read MQ135
            if mq135 is not None:
                try:
                    mq135_data = mq135.get_all_readings()
                    sensor_data["mq135"] = mq135_data
                except Exception as e:
                    print(json.dumps({"timestamp": timestamp, "error": f"MQ135 read error: {str(e)}"}))

            # Output JSON to USB serial
            print(json.dumps(sensor_data))

            # Wait 1 second
            time.sleep(1)

        except KeyboardInterrupt:
            print("\n[STOP] Monitoring stopped by user")
            return
        except Exception as e:
            # Other unexpected errors
            error_data = {
                "timestamp": time.ticks_ms() / 1000.0,
                "error": f"Unexpected error: {str(e)}",
                "status": "sensor_error"
            }
            print(json.dumps(error_data))
            time.sleep(1)


# This runs automatically when Pico boots
if __name__ == "__main__":
    auto_start_monitoring()
