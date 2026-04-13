"""
Auto-boot JSON Sensor Monitor for Raspberry Pi Pico
This file runs automatically when the Pico boots up
Outputs BM280 (SPI) + MQ135 sensor data in JSON format every second over USB
"""

import json
import time
import machine
from machine import Pin, SPI, ADC

# Import sensor libraries and configuration
try:
    from lib.bm280_spi import BM280_SPI
    from lib.mq135 import MQ135
    from lib.config import (
        SPI_BUS,
        SPI_SCK_PIN,
        SPI_MOSI_PIN,
        SPI_MISO_PIN,
        SPI_CS_PIN,
        SPI_FREQ,
        SPI_POLARITY,
        SPI_PHASE,
        MQ135_PIN,
        MQ135_R_ZERO,
        MQ135_R_LOAD,
        BOOT_DELAY_SEC,
        BM280_RETRY_DELAY_SEC,
        SENSOR_READ_INTERVAL_SEC,
        GC_COLLECT_INTERVAL,
        I2C_RECOVERY_RETRIES,
        LED_PIN,
        LED_BLINK_DURATION_MS,
    )
except ImportError as e:
    # Library modules are required - fail fast with clear error
    error_msg = {
        "error": "Failed to import required libraries",
        "details": str(e),
        "message": "Ensure lib/ directory is present with bm280_spi.py, mq135.py, and config.py",
    }
    print(json.dumps(error_msg))
    raise


# BM280 reliability tuning
BM280_STARTUP_RETRIES = 10
BM280_RUNTIME_RETRY_INTERVAL_SEC = 10.0
BM280_RUNTIME_INIT_RETRIES = 2
BM280_RUNTIME_RETRY_DELAY_SEC = 0.5
BM280_MAX_BACKOFF_SEC = 5.0


# SPI and sensor recovery functions
def reinitialize_spi(old_spi=None, max_retries=None):
    """
    Reinitialize the SPI bus with exponential backoff retry logic.
    Deinits old_spi before creating the new bus to release RP2040 SPI peripheral resources.
    Returns: (SPI object, CS pin object) or (None, None) if failed
    """
    if max_retries is None:
        max_retries = I2C_RECOVERY_RETRIES

    if old_spi is not None:
        try:
            old_spi.deinit()
        except Exception:
            pass  # Best-effort; proceed regardless

    for attempt in range(max_retries):
        try:
            # Try to create a new SPI bus with proper BM280 mode (SPI Mode 0)
            spi = SPI(
                SPI_BUS,
                baudrate=SPI_FREQ,
                polarity=SPI_POLARITY,
                phase=SPI_PHASE,
                sck=Pin(SPI_SCK_PIN),
                mosi=Pin(SPI_MOSI_PIN),
                miso=Pin(SPI_MISO_PIN),
            )
            cs_pin = Pin(SPI_CS_PIN, Pin.OUT)
            cs_pin.on()  # Deselect initially
            return spi, cs_pin
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff: 2^attempt * 0.1 seconds
                delay = (2**attempt) * 0.1
                time.sleep(delay)
            else:
                error_msg = {
                    "timestamp": time.ticks_ms() / 1000.0,
                    "status": "error",
                    "error": "SPI reinitialization failed",
                    "details": str(e),
                    "attempts": max_retries,
                }
                print(json.dumps(error_msg))

    return None, None


def initialize_bm280_spi(
    spi,
    cs_pin,
    max_retries=None,
    retry_delay_sec=None,
    reinitialize_bus_on_retry=True,
    context="initialization",
):
    """
    Initialize BM280 sensor with retries.
    Returns: (BM280_SPI object or None, SPI object, CS pin object)
    """
    if max_retries is None:
        max_retries = BM280_STARTUP_RETRIES
    if retry_delay_sec is None:
        retry_delay_sec = BM280_RETRY_DELAY_SEC

    if spi is None or cs_pin is None:
        return None, spi, cs_pin

    last_error = None

    for attempt in range(max_retries):
        try:
            sensor = BM280_SPI(spi, cs_pin)
            return sensor, spi, cs_pin
        except Exception as e:
            last_error = e
            is_last_attempt = attempt >= max_retries - 1

            retry_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "bm280_retry",
                "context": context,
                "attempt": attempt + 1,
                "max_retries": max_retries,
                "error": str(e),
                "error_type": type(e).__name__,
            }
            print(json.dumps(retry_msg))

            if is_last_attempt:
                break

            if reinitialize_bus_on_retry:
                new_spi, new_cs_pin = reinitialize_spi(
                    old_spi=spi, max_retries=I2C_RECOVERY_RETRIES
                )
                if new_spi is not None and new_cs_pin is not None:
                    spi = new_spi
                    cs_pin = new_cs_pin

            delay = min((2**attempt) * retry_delay_sec, BM280_MAX_BACKOFF_SEC)
            time.sleep(delay)

    error_msg = {
        "timestamp": time.ticks_ms() / 1000.0,
        "status": "error",
        "error": "BM280 initialization failed",
        "context": context,
        "details": str(last_error) if last_error is not None else "unknown",
        "attempts": max_retries,
    }
    print(json.dumps(error_msg))
    return None, spi, cs_pin


def recover_bm280_spi(spi, cs_pin, current_bm280=None, max_retries=None):
    """
    Attempt to recover BM280 sensor via SPI
    Returns: BM280_SPI object or None if recovery failed
    """
    if max_retries is None:
        max_retries = I2C_RECOVERY_RETRIES

    if spi is None or cs_pin is None:
        return None

    # Step 1: Try to reset existing sensor if available
    if current_bm280 is not None:
        try:
            current_bm280.reset()
            # CRITICAL: reset() returns BM280 to sleep mode — must reconfigure
            # to restore normal operating mode before sensor will produce data again.
            current_bm280.reconfigure()
            # Verify sensor is responding
            _ = current_bm280.check_status()
            recovery_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "recovered",
                "sensor": "bm280",
                "method": "reset",
            }
            print(json.dumps(recovery_msg))
            return current_bm280
        except Exception:
            pass  # Reset failed, try reinitializing

    # Step 2: Reinitialize sensor
    recovered_sensor, _, _ = initialize_bm280_spi(
        spi,
        cs_pin,
        max_retries=max_retries,
        retry_delay_sec=BM280_RETRY_DELAY_SEC,
        reinitialize_bus_on_retry=False,
        context="recovery",
    )

    if recovered_sensor is not None:
        recovery_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "recovered",
            "sensor": "bm280",
            "method": "reinitialize",
        }
        print(json.dumps(recovery_msg))

    return recovered_sensor


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
    count: number of blinks (1=BM280 only, 2=MQ135 only, 3=both sensors)
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
        "message": "Auto-starting JSON sensor monitoring...",
    }
    print(json.dumps(startup_msg))

    # Delay to ensure USB is ready (from config)
    time.sleep(BOOT_DELAY_SEC)

    # Initialize LED (supports Pico and Pico W)
    led = None
    led_identifier = None
    try:
        # Pico W exposes onboard LED as "LED"
        led = Pin("LED", Pin.OUT)
        led_identifier = "LED"
    except Exception:
        try:
            # Pico (non-W) uses GPIO25
            led = Pin(LED_PIN, Pin.OUT)
            led_identifier = str(LED_PIN)
        except Exception as e:
            led_error_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "warning",
                "message": "LED initialization failed",
                "details": str(e),
            }
            print(json.dumps(led_error_msg))

    if led is not None:
        try:
            led.off()
            led_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "led_initialized",
                "pin": led_identifier,
            }
            print(json.dumps(led_msg))
        except Exception as e:
            led_error_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "warning",
                "message": "LED initialization failed",
                "details": str(e),
            }
            print(json.dumps(led_error_msg))

    # I2C bus not used in current configuration (BM280 uses SPI, MQ135 uses ADC).
    # Skip I2C initialization to avoid locking the bus.
    # If future sensors need I2C, initialize here.
    i2c = None

    # Initialize SPI bus for GY-BM280
    spi = None
    cs_pin = None
    try:
        # BM280 requires SPI Mode 0 (CPOL=0, CPHA=0)
        spi = SPI(
            SPI_BUS,
            baudrate=SPI_FREQ,
            polarity=SPI_POLARITY,
            phase=SPI_PHASE,
            sck=Pin(SPI_SCK_PIN),
            mosi=Pin(SPI_MOSI_PIN),
            miso=Pin(SPI_MISO_PIN),
        )
        cs_pin = Pin(SPI_CS_PIN, Pin.OUT)
        cs_pin.on()  # Deselect initially
        spi_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "spi_initialized",
            "bus": SPI_BUS,
            "sck_pin": SPI_SCK_PIN,
            "mosi_pin": SPI_MOSI_PIN,
            "miso_pin": SPI_MISO_PIN,
            "cs_pin": SPI_CS_PIN,
            "frequency": SPI_FREQ,
        }
        print(json.dumps(spi_msg))
    except Exception as e:
        error_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "error",
            "error": "SPI bus initialization failed",
            "details": str(e),
        }
        print(json.dumps(error_msg))

    # Initialize sensors independently
    bm280 = None
    mq135 = None

    # Try to initialize BM280 via SPI
    if spi is not None and cs_pin is not None:
        bm280, spi, cs_pin = initialize_bm280_spi(
            spi,
            cs_pin,
            max_retries=BM280_STARTUP_RETRIES,
            retry_delay_sec=BM280_RETRY_DELAY_SEC,
            reinitialize_bus_on_retry=True,
            context="startup",
        )

        if bm280 is None:
            warning_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "warning",
                "message": "BM280 unavailable - will send MQ135 data only",
            }
            print(json.dumps(warning_msg))
        else:
            bm280_msg = {
                "timestamp": time.ticks_ms() / 1000.0,
                "status": "bm280_initialized",
                "interface": "SPI",
            }
            print(json.dumps(bm280_msg))

    # Try to initialize MQ135 (critical sensor for air quality)
    try:
        mq135 = MQ135(MQ135_PIN, r_zero=MQ135_R_ZERO, r_load=MQ135_R_LOAD)
        mq135_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "mq135_initialized",
            "pin": MQ135_PIN,
            "r_zero": MQ135_R_ZERO,
            "r_load": MQ135_R_LOAD,
        }
        print(json.dumps(mq135_msg))
    except Exception as e:
        error_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "error",
            "error": "MQ135 initialization failed",
            "pin": MQ135_PIN,
            "details": str(e),
            "message": f"Check wiring on GPIO {MQ135_PIN}",
        }
        print(json.dumps(error_msg))
        return

    # Require at least one sensor to be working
    if bm280 is None and mq135 is None:
        error_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "error",
            "error": "No sensors available",
            "message": "Check all connections",
        }
        print(json.dumps(error_msg))
        # Blink error pattern
        blink_error(led)
        return

    # Diagnostic blink pattern to show which sensors are available
    # 1 blink = BM280 only, 2 blinks = MQ135 only, 3 blinks = both
    time.sleep(0.5)  # Pause before diagnostic
    if bm280 is not None and mq135 is not None:
        diagnostic_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "diagnostic",
            "message": "Both sensors available (3 blinks)",
        }
        print(json.dumps(diagnostic_msg))
        blink_pattern(led, 3)  # Both sensors
    elif bm280 is not None:
        diagnostic_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "diagnostic",
            "message": "Only BM280 available (1 blink)",
        }
        print(json.dumps(diagnostic_msg))
        blink_pattern(led, 1)  # BM280 only
    else:  # mq135 is not None
        diagnostic_msg = {
            "timestamp": time.ticks_ms() / 1000.0,
            "status": "diagnostic",
            "message": "Only MQ135 available (2 blinks)",
        }
        print(json.dumps(diagnostic_msg))
        blink_pattern(led, 2)  # MQ135 only

    # Start monitoring message
    start_msg = {
        "timestamp": time.ticks_ms() / 1000.0,
        "status": "monitoring_started",
        "message": "Starting continuous JSON monitoring (auto-boot)",
        "bm280_available": bm280 is not None,
        "mq135_available": mq135 is not None,
        "note": "Press Ctrl+C to stop, or reset Pico to restart",
    }
    print(json.dumps(start_msg))

    # Start continuous monitoring loop
    import gc

    gc.collect()
    iteration_count = 0
    bm280_read_count = 0  # Counter for periodic reset
    bm280_retry_interval_ms = int(BM280_RUNTIME_RETRY_INTERVAL_SEC * 1000)
    last_bm280_init_attempt_ms = time.ticks_ms()

    while True:
        try:
            # Get current timestamp (relative to boot, with boot offset for reference)
            timestamp = time.ticks_ms() / 1000.0
            sensor_data = {
                "timestamp": timestamp,
                "timestamp_since_boot": timestamp - boot_timestamp,
            }

            # Track which sensors successfully read
            bm280_read_ok = False
            mq135_read_ok = False

            # If BM280 is currently unavailable, retry initialization periodically.
            if bm280 is None:
                now_ms = time.ticks_ms()
                if (
                    time.ticks_diff(now_ms, last_bm280_init_attempt_ms)
                    >= bm280_retry_interval_ms
                ):
                    last_bm280_init_attempt_ms = now_ms
                    reconnect_msg = {
                        "timestamp": timestamp,
                        "status": "bm280_reconnect_attempt",
                        "message": "Attempting to reinitialize BM280",
                    }
                    print(json.dumps(reconnect_msg))

                    if spi is None or cs_pin is None:
                        spi, cs_pin = reinitialize_spi(old_spi=spi)

                    if spi is not None and cs_pin is not None:
                        recovered_bm280, spi, cs_pin = initialize_bm280_spi(
                            spi,
                            cs_pin,
                            max_retries=BM280_RUNTIME_INIT_RETRIES,
                            retry_delay_sec=BM280_RUNTIME_RETRY_DELAY_SEC,
                            reinitialize_bus_on_retry=True,
                            context="runtime_reconnect",
                        )
                        if recovered_bm280 is not None:
                            bm280 = recovered_bm280
                            recovered_msg = {
                                "timestamp": timestamp,
                                "status": "recovered",
                                "sensor": "bm280",
                                "method": "runtime_reconnect",
                            }
                            print(json.dumps(recovered_msg))

            # Read BM280 if available
            if bm280 is not None:
                try:
                    # Read sensor data
                    temp_c, pressure_pa, humidity_pct = bm280.read_compensated_data()
                    pressure_hpa = pressure_pa / 100.0
                    sensor_data["bm280"] = {
                        "temperature_c": round(temp_c, 2),
                        "humidity_percent": round(humidity_pct, 1),
                        "pressure_hpa": round(pressure_hpa, 1),
                        "pressure_pa": round(pressure_pa, 0),
                    }
                    bm280_read_count += 1
                    bm280_read_ok = True
                except Exception as e:
                    # BM280 error - attempt recovery
                    error_data = {
                        "timestamp": timestamp,
                        "status": "error",
                        "sensor": "bm280",
                        "error": "BM280 read error",
                        "details": str(e),
                        "attempting_recovery": True,
                    }
                    print(json.dumps(error_data))

                    # Attempt recovery: first try reset, then reinitialize bus if needed
                    recovery_successful = False

                    # Step 1: Try to reset sensor
                    try:
                        if bm280 is not None:
                            bm280.reset()
                            # CRITICAL: reset() returns BM280 to sleep mode — must
                            # reconfigure to restore normal mode before reads will work.
                            bm280.reconfigure()
                            # Verify sensor responds
                            _ = bm280.check_status()
                            recovery_successful = True
                            recovery_msg = {
                                "timestamp": timestamp,
                                "status": "recovered",
                                "sensor": "bm280",
                                "method": "reset",
                            }
                            print(json.dumps(recovery_msg))
                    except Exception:
                        pass  # Reset failed, try bus recovery

                    # Step 2: If reset failed, try reinitializing SPI bus
                    if not recovery_successful:
                        new_spi, new_cs_pin = reinitialize_spi(old_spi=spi)
                        if new_spi is not None and new_cs_pin is not None:
                            spi = new_spi
                            cs_pin = new_cs_pin
                            # Step 3: Try to recover BM280 with new bus
                            recovered_bm280 = recover_bm280_spi(
                                spi, cs_pin, current_bm280=bm280
                            )
                            if recovered_bm280 is not None:
                                bm280 = recovered_bm280
                                recovery_successful = True

                    if not recovery_successful:
                        bm280 = None  # Mark missing so periodic reconnect can restore it
                        last_bm280_init_attempt_ms = time.ticks_add(
                            time.ticks_ms(), -bm280_retry_interval_ms
                        )
                        # Recovery failed - sensor unavailable for this cycle
                        unavailable_msg = {
                            "timestamp": timestamp,
                            "status": "warning",
                            "sensor": "bm280",
                            "message": "BM280 unavailable after recovery attempts",
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
                        "details": str(e),
                    }
                    print(json.dumps(error_data))

            # Output JSON to USB serial
            print(json.dumps(sensor_data))

            # Blink LED pattern based on which sensors read successfully
            # 1 blink = BM280 only, 2 blinks = MQ135 only, 3 blinks = both
            if led is not None:
                if bm280_read_ok and mq135_read_ok:
                    blink_pattern(led, 3)  # Both sensors OK
                elif bm280_read_ok:
                    blink_pattern(led, 1)  # BM280 only
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
                "message": "Monitoring stopped by user",
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
                "type": type(e).__name__,
            }
            print(json.dumps(error_data))
            time.sleep(SENSOR_READ_INTERVAL_SEC)


# This runs automatically when Pico boots
if __name__ == "__main__":
    auto_start_monitoring()
