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
        SENSOR_READ_INTERVAL_SEC, GC_COLLECT_INTERVAL,
        I2C_RECOVERY_RETRIES, BME280_RESET_INTERVAL,
        LED_PIN, LED_BLINK_DURATION_MS
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


# I2C and sensor recovery functions
def reinitialize_i2c(max_retries=None):
    """
    Reinitialize the I2C bus with exponential backoff retry logic
    Returns: I2C object or None if failed
    """
    if max_retries is None:
        max_retries = I2C_RECOVERY_RETRIES
    
    for attempt in range(max_retries):
        try:
            # Try to create a new I2C bus
            i2c = I2C(I2C_BUS, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=I2C_FREQ)
            # Verify bus is working by scanning
            devices = i2c.scan()
            if len(devices) > 0:
                return i2c
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff: 2^attempt * 0.1 seconds
                delay = (2 ** attempt) * 0.1
                time.sleep(delay)
            else:
                error_msg = {
                    "timestamp": time.ticks_ms() / 1000.0,
                    "status": "error",
                    "error": "I2C reinitialization failed",
                    "details": str(e),
                    "attempts": max_retries
                }
                print(json.dumps(error_msg))
    
    return None


def recover_bme280(i2c, current_bme280=None, max_retries=None):
    """
    Attempt to recover BME280 sensor
    Returns: BME280 object or None if recovery failed
    """
    if max_retries is None:
        max_retries = I2C_RECOVERY_RETRIES
    
    if i2c is None:
        return None
    
    # Step 1: Try to reset existing sensor if available
    if current_bme280 is not None:
        try:
            current_bme280.reset()
            # Verify sensor is responding
            _ = current_bme280.check_status()
            recovery_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "recovered",
                "sensor": "bme280",
                "method": "reset"
            }
            print(json.dumps(recovery_msg))
            return current_bme280
        except Exception:
            pass  # Reset failed, try reinitializing
    
    # Step 2: Try to reinitialize sensor with exponential backoff
    for address in BME280_ADDRESSES:
        for attempt in range(max_retries):
            try:
                bme280 = BME280(i2c, address=address)
                recovery_msg = {
                    "timestamp": time.ticks_ms() / 1000.0,
                    "status": "recovered",
                    "sensor": "bme280",
                    "method": "reinitialize",
                    "address": f"0x{address:02X}",
                    "attempt": attempt + 1
                }
                print(json.dumps(recovery_msg))
                return bme280
            except Exception as e:
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt * base delay
                    delay = (2 ** attempt) * BME280_RETRY_DELAY_SEC
                    time.sleep(delay)
                else:
                    error_msg = {
                        "timestamp": time.ticks_ms() / 1000.0,
                        "status": "error",
                        "error": "BME280 recovery failed",
                        "address": f"0x{address:02X}",
                        "details": str(e),
                        "attempts": max_retries
                    }
                    print(json.dumps(error_msg))
    
    return None


def check_i2c_bus_health(i2c):
    """
    Check if I2C bus is healthy by scanning for devices
    Returns: True if bus is healthy, False otherwise
    """
    if i2c is None:
        return False
    try:
        devices = i2c.scan()
        return len(devices) > 0
    except Exception:
        return False


def blink_led(led_pin, duration_ms=LED_BLINK_DURATION_MS):
    """
    Single blink of the LED for a specified duration
    """
    try:
        led_pin.on()
        time.sleep(duration_ms / 1000.0)
        led_pin.off()
    except Exception:
        pass  # Silently fail if LED operation fails


def blink_pattern(led_pin, count, duration_ms=LED_BLINK_DURATION_MS, pause_ms=150):
    """
    Blink the LED multiple times with pauses between blinks
    count: number of blinks (1=BME280 only, 2=MQ135 only, 3=both sensors)
    """
    if led_pin is None:
        return
    try:
        for i in range(count):
            led_pin.on()
            time.sleep(duration_ms / 1000.0)
            led_pin.off()
            if i < count - 1:  # Pause between blinks, not after last
                time.sleep(pause_ms / 1000.0)
    except Exception:
        pass  # Silently fail if LED operation fails


def blink_error(led_pin, duration_ms=200):
    """
    Slow continuous blinks (error state)
    """
    if led_pin is None:
        return
    try:
        for _ in range(3):  # 3 slow blinks
            led_pin.on()
            time.sleep(duration_ms / 1000.0)
            led_pin.off()
            time.sleep(duration_ms / 1000.0)
    except Exception:
        pass  # Silently fail if LED operation fails


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

    # Initialize LED
    led = None
    try:
        led = Pin(LED_PIN, Pin.OUT)
        led.off()
        led_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "led_initialized",
            "pin": LED_PIN
        }
        print(json.dumps(led_msg))
    except Exception as e:
        led_error_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "warning",
            "message": "LED initialization failed",
            "details": str(e)
        }
        print(json.dumps(led_error_msg))

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
        # Blink error pattern
        blink_error(led)
        return

    # Diagnostic blink pattern to show which sensors are available
    # 1 blink = BME280 only, 2 blinks = MQ135 only, 3 blinks = both
    time.sleep(0.5)  # Pause before diagnostic
    if bme280 is not None and mq135 is not None:
        diagnostic_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "diagnostic",
            "message": "Both sensors available (3 blinks)"
        }
        print(json.dumps(diagnostic_msg))
        blink_pattern(led, 3)  # Both sensors
    elif bme280 is not None:
        diagnostic_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "diagnostic",
            "message": "Only BME280 available (1 blink)"
        }
        print(json.dumps(diagnostic_msg))
        blink_pattern(led, 1)  # BME280 only
    else:  # mq135 is not None
        diagnostic_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "diagnostic",
            "message": "Only MQ135 available (2 blinks)"
        }
        print(json.dumps(diagnostic_msg))
        blink_pattern(led, 2)  # MQ135 only

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
    bme280_read_count = 0  # Counter for periodic reset

    while True:
        try:
            # Get current timestamp (relative to boot, with boot offset for reference)
            timestamp = time.ticks_ms() / 1000.0
            sensor_data = {
                "timestamp": timestamp,
                "timestamp_since_boot": timestamp - boot_timestamp
            }

            # Track which sensors successfully read
            bme280_read_ok = False
            mq135_read_ok = False

            # Read BME280 if available
            if bme280 is not None:
                try:
                    # Note: Removed aggressive I2C bus health check - it was locking up the sensor
                    # Health checks will happen only if read fails (in exception handler)

                    # Periodic sensor reset (if enabled) - DISABLED for now to prevent sensor lockup
                    # if BME280_RESET_INTERVAL > 0 and bme280_read_count > 0 and bme280_read_count % BME280_RESET_INTERVAL == 0:
                    #     try:
                    #         bme280.reset()
                    #         time.sleep(0.5)  # Give sensor time to recover
                    #         reset_msg = {
                    #             "timestamp": timestamp,
                    #             "status": "info",
                    #             "sensor": "bme280",
                    #             "message": "Periodic reset performed",
                    #             "read_count": bme280_read_count
                    #         }
                    #         print(json.dumps(reset_msg))
                    #     except Exception as reset_error:
                    #         reset_error_msg = {
                    #             "timestamp": timestamp,
                    #             "status": "warning",
                    #             "sensor": "bme280",
                    #             "error": "Periodic reset failed",
                    #             "details": str(reset_error)
                    #         }
                    #         print(json.dumps(reset_error_msg))
                    
                    # Read sensor data
                    temp_c, pressure_pa, humidity_pct = bme280.read_compensated_data()
                    pressure_hpa = pressure_pa / 100.0
                    sensor_data["bme280"] = {
                        "temperature_c": round(temp_c, 2),
                        "humidity_percent": round(humidity_pct, 1),
                        "pressure_hpa": round(pressure_hpa, 1),
                        "pressure_pa": round(pressure_pa, 0)
                    }
                    bme280_read_count += 1
                    bme280_read_ok = True
                except Exception as e:
                    # BME280 error - attempt recovery
                    error_data = {
                        "timestamp": timestamp,
                        "status": "error",
                        "sensor": "bme280",
                        "error": "BME280 read error",
                        "details": str(e),
                        "attempting_recovery": True
                    }
                    print(json.dumps(error_data))
                    
                    # Attempt recovery: first try reset, then reinitialize bus if needed
                    recovery_successful = False
                    
                    # Step 1: Try to reset sensor
                    try:
                        if bme280 is not None:
                            bme280.reset()
                            # Verify sensor responds
                            _ = bme280.check_status()
                            recovery_successful = True
                            recovery_msg = {
                                "timestamp": timestamp,
                                "status": "recovered",
                                "sensor": "bme280",
                                "method": "reset"
                            }
                            print(json.dumps(recovery_msg))
                    except Exception:
                        pass  # Reset failed, try bus recovery
                    
                    # Step 2: If reset failed, try reinitializing I2C bus
                    if not recovery_successful:
                        new_i2c = reinitialize_i2c()
                        if new_i2c is not None:
                            i2c = new_i2c
                            # Step 3: Try to recover BME280 with new bus
                            recovered_bme280 = recover_bme280(i2c, current_bme280=bme280)
                            if recovered_bme280 is not None:
                                bme280 = recovered_bme280
                                recovery_successful = True
                    
                    if not recovery_successful:
                        # Recovery failed - sensor unavailable for this cycle
                        unavailable_msg = {
                            "timestamp": timestamp,
                            "status": "warning",
                            "sensor": "bme280",
                            "message": "BME280 unavailable after recovery attempts"
                        }
                        print(json.dumps(unavailable_msg))

            # Always try to read MQ135
            if mq135 is not None:
                try:
                    mq135_data = mq135.get_all_readings()
                    sensor_data["mq135"] = mq135_data
                    mq135_read_ok = True
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

            # Blink LED pattern based on which sensors read successfully
            # 1 blink = BME280 only, 2 blinks = MQ135 only, 3 blinks = both
            if led is not None:
                if bme280_read_ok and mq135_read_ok:
                    blink_pattern(led, 3)  # Both sensors OK
                elif bme280_read_ok:
                    blink_pattern(led, 1)  # BME280 only
                elif mq135_read_ok:
                    blink_pattern(led, 2)  # MQ135 only
                else:
                    blink_error(led)  # Neither sensor read OK

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
