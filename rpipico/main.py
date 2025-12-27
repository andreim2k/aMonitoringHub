"""
Auto-boot JSON Sensor Monitor for Raspberry Pi Pico
This file runs automatically when the Pico boots up
Outputs BME280 + MQ135 sensor data in JSON format every second over USB
"""

import json
import time
import machine
from machine import Pin, I2C, ADC

# Import sensor libraries and configuration
try:
    from lib.bme280 import BME280
    from lib.mq135 import MQ135
    from lib.config import (
        I2C_BUS, I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQ,
        MQ135_PIN, MQ135_R_ZERO, MQ135_R_LOAD,
        BME280_ADDRESSES, BME280_DEFAULT_ADDRESS,
        BOOT_DELAY_SEC, BME280_RETRY_DELAY_SEC,
        SENSOR_READ_INTERVAL_SEC, GC_COLLECT_INTERVAL
    )
except ImportError as e:
    # Library modules are required - fail fast with clear error
    error_msg = {
        "error": "Failed to import required libraries",
        "details": str(e),
        "message": "Ensure lib/ directory is present with bme280.py, mq135.py, and config.py"
    }
    print(json.dumps(error_msg))
    raise


# Auto-start monitoring function
def auto_start_monitoring():
    """Auto-start monitoring on boot"""
    boot_timestamp = time.ticks_ms() / 1000.0
    
    # Output startup message as JSON for consistency
    startup_msg = {
        "timestamp": boot_timestamp,
        "status": "starting",
        "message": "Auto-starting JSON sensor monitoring..."
    }
    print(json.dumps(startup_msg))
    
    # Delay to ensure USB is ready (from config)
    time.sleep(BOOT_DELAY_SEC)
    
    # Initialize I2C bus once (do not create in loop)
    i2c = None
    try:
        i2c = I2C(I2C_BUS, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=I2C_FREQ)
        i2c_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "i2c_initialized",
            "bus": I2C_BUS,
            "sda_pin": I2C_SDA_PIN,
            "scl_pin": I2C_SCL_PIN,
            "frequency": I2C_FREQ
        }
        print(json.dumps(i2c_msg))
    except Exception as e:
        error_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "error",
            "error": "I2C bus initialization failed",
            "details": str(e)
        }
        print(json.dumps(error_msg))

    # Initialize sensors independently
    bme280 = None
    mq135 = None

    # Try to initialize BME280 with address fallback (try both 0x76 and 0x77)
    if i2c is not None:
        max_retries = 10
        bme280_initialized = False
        
        for address in BME280_ADDRESSES:
            if bme280_initialized:
                break
            
            retry_count = 0
            while retry_count < max_retries and bme280 is None:
                try:
                    bme280 = BME280(i2c, address=address)
                    bme280_msg = {
                        "timestamp": time.ticks_ms() / 1000.0,
                        "status": "bme280_initialized",
                        "address": f"0x{address:02X}"
                    }
                    print(json.dumps(bme280_msg))
                    bme280_initialized = True
                    break
                except OSError as e:
                    retry_count += 1
                    retry_msg = {
                        "timestamp": time.ticks_ms() / 1000.0,
                        "status": "bme280_retry",
                        "address": f"0x{address:02X}",
                        "attempt": retry_count,
                        "max_retries": max_retries,
                        "error": str(e)
                    }
                    print(json.dumps(retry_msg))
                    if retry_count < max_retries:
                        time.sleep(BME280_RETRY_DELAY_SEC)
                except ValueError as e:
                    # Wrong address or chip ID - try next address
                    break
                except Exception as e:
                    error_msg = {
                        "timestamp": time.ticks_ms() / 1000.0,
                        "status": "error",
                        "error": "BME280 initialization error",
                        "address": f"0x{address:02X}",
                        "details": str(e)
                    }
                    print(json.dumps(error_msg))
                    break
        
        if not bme280_initialized:
            warning_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "warning",
                "message": "BME280 unavailable - will send MQ135 data only"
            }
            print(json.dumps(warning_msg))

    # Try to initialize MQ135 (critical sensor for air quality)
    try:
        mq135 = MQ135(MQ135_PIN, r_zero=MQ135_R_ZERO, r_load=MQ135_R_LOAD)
        mq135_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "mq135_initialized",
            "pin": MQ135_PIN,
            "r_zero": MQ135_R_ZERO,
            "r_load": MQ135_R_LOAD
        }
        print(json.dumps(mq135_msg))
    except Exception as e:
        error_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "error",
            "error": "MQ135 initialization failed",
            "pin": MQ135_PIN,
            "details": str(e),
            "message": f"Check wiring on GPIO {MQ135_PIN}"
        }
        print(json.dumps(error_msg))
        return

    # Require at least one sensor to be working
    if bme280 is None and mq135 is None:
        error_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "error",
            "error": "No sensors available",
            "message": "Check all connections"
        }
        print(json.dumps(error_msg))
        return

    # Start monitoring message
    start_msg = {
        "timestamp": time.ticks_ms() / 1000.0,
        "status": "monitoring_started",
        "message": "Starting continuous JSON monitoring (auto-boot)",
        "bme280_available": bme280 is not None,
        "mq135_available": mq135 is not None,
        "note": "Press Ctrl+C to stop, or reset Pico to restart"
    }
    print(json.dumps(start_msg))

    # Start continuous monitoring loop
    import gc
    gc.collect()
    iteration_count = 0

    while True:
        try:
            # Get current timestamp (relative to boot, with boot offset for reference)
            timestamp = time.ticks_ms() / 1000.0
            sensor_data = {
                "timestamp": timestamp,
                "timestamp_since_boot": timestamp - boot_timestamp
            }

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
                    # BME280 error, but continue with MQ135 - output as JSON
                    error_data = {
                        "timestamp": timestamp,
                        "status": "error",
                        "sensor": "bme280",
                        "error": "BME280 read error",
                        "details": str(e)
                    }
                    print(json.dumps(error_data))

            # Always try to read MQ135
            if mq135 is not None:
                try:
                    mq135_data = mq135.get_all_readings()
                    sensor_data["mq135"] = mq135_data
                except Exception as e:
                    # MQ135 error - output as JSON
                    error_data = {
                        "timestamp": timestamp,
                        "status": "error",
                        "sensor": "mq135",
                        "error": "MQ135 read error",
                        "details": str(e)
                    }
                    print(json.dumps(error_data))

            # Output JSON to USB serial
            print(json.dumps(sensor_data))

            # Periodic garbage collection (from config)
            iteration_count += 1
            if iteration_count % GC_COLLECT_INTERVAL == 0:
                gc.collect()

            # Wait for next reading (from config)
            time.sleep(SENSOR_READ_INTERVAL_SEC)

        except KeyboardInterrupt:
            stop_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "stopped",
                "message": "Monitoring stopped by user"
            }
            print(json.dumps(stop_msg))
            return
        except Exception as e:
            # Other unexpected errors - always output as JSON
            error_data = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "error",
                "error": "Unexpected error",
                "details": str(e),
                "type": type(e).__name__
            }
            print(json.dumps(error_data))
            time.sleep(SENSOR_READ_INTERVAL_SEC)


# This runs automatically when Pico boots
if __name__ == "__main__":
    auto_start_monitoring()
