"""
Auto-boot JSON sensor monitor for Raspberry Pi Pico.
BME280 over SPI + MQ135 over ADC. Emits one JSON object per cycle on USB serial.
"""

import gc
import json
import time

from machine import Pin, SPI

try:
    from lib.bme280_spi import BME280_SPI
    from lib.mq135 import MQ135
    from lib.config import (
        SPI_BUS, SPI_SCK_PIN, SPI_MOSI_PIN, SPI_MISO_PIN, SPI_CS_PIN,
        SPI_FREQ, SPI_POLARITY, SPI_PHASE,
        MQ135_PIN, MQ135_R_ZERO, MQ135_R_LOAD,
        BOOT_DELAY_SEC, BME280_RETRY_DELAY_SEC, BME280_INIT_RETRIES,
        SENSOR_READ_INTERVAL_SEC, GC_COLLECT_INTERVAL,
        LED_PIN, LED_BLINK_DURATION_MS,
    )
except ImportError as e:
    print(json.dumps({
        "error": "Failed to import required libraries",
        "details": str(e),
    }))
    raise


def _now():
    """Monotonic seconds since boot, safe across ticks_ms wraparound."""
    return time.ticks_ms() / 1000.0


def _emit(obj):
    print(json.dumps(obj))


# ---- SPI / sensor lifecycle ----

def _make_spi():
    """Build a fresh SPI bus + CS pin. Caller is responsible for deinit of old."""
    spi = SPI(
        SPI_BUS,
        baudrate=SPI_FREQ,
        polarity=SPI_POLARITY,
        phase=SPI_PHASE,
        sck=Pin(SPI_SCK_PIN),
        mosi=Pin(SPI_MOSI_PIN),
        miso=Pin(SPI_MISO_PIN),
    )
    cs = Pin(SPI_CS_PIN, Pin.OUT, value=1)
    return spi, cs


def _safe_deinit_spi(spi):
    """Release the underlying SPI peripheral so the next _make_spi() is clean.
    Without this, repeated recovery attempts leak peripheral state and
    eventually wedge the bus — the suspected long-run failure mode."""
    if spi is None:
        return
    try:
        spi.deinit()
    except Exception:
        pass


def _init_bme280(spi, cs):
    """Try to init the BME280, with retries. Returns sensor or None."""
    last_err = None
    for attempt in range(1, BME280_INIT_RETRIES + 1):
        try:
            sensor = BME280_SPI(spi, cs)
            _emit({"status": "bme280_initialized", "attempt": attempt})
            return sensor
        except ValueError as e:
            _emit({"status": "error", "error": "BME280 chip ID mismatch",
                   "details": str(e)})
            return None
        except Exception as e:
            last_err = e
            _emit({"status": "bme280_retry", "attempt": attempt, "error": str(e)})
            time.sleep(BME280_RETRY_DELAY_SEC)
    _emit({"status": "warning", "message": "BME280 unavailable",
           "last_error": str(last_err) if last_err else None})
    return None


def _recover_bme280(spi, cs):
    """Tear down the SPI bus and bring up a fresh BME280. Returns
    (sensor_or_None, new_spi, new_cs). Always returns valid spi/cs so the
    caller can keep retrying on the next cycle."""
    _safe_deinit_spi(spi)
    gc.collect()
    try:
        new_spi, new_cs = _make_spi()
    except Exception as e:
        _emit({"status": "error", "error": "SPI reinit failed", "details": str(e)})
        return None, spi, cs
    sensor = _init_bme280(new_spi, new_cs)
    if sensor is not None:
        _emit({"status": "recovered", "sensor": "bme280"})
    return sensor, new_spi, new_cs


# ---- LED ----

def _blink(led, count, on_ms=LED_BLINK_DURATION_MS, gap_ms=150):
    if led is None:
        return
    try:
        for i in range(count):
            led.on()
            time.sleep_ms(on_ms)
            led.off()
            if i < count - 1:
                time.sleep_ms(gap_ms)
    except Exception:
        pass


def _blink_error(led):
    if led is None:
        return
    try:
        for _ in range(3):
            led.on()
            time.sleep_ms(200)
            led.off()
            time.sleep_ms(200)
    except Exception:
        pass


# ---- main loop ----

def auto_start_monitoring():
    _emit({"status": "starting", "message": "Auto-starting JSON sensor monitoring"})
    time.sleep(BOOT_DELAY_SEC)

    led = None
    try:
        led = Pin(LED_PIN, Pin.OUT, value=0)
    except Exception as e:
        _emit({"status": "warning", "message": "LED init failed", "details": str(e)})

    spi = cs = None
    try:
        spi, cs = _make_spi()
        _emit({"status": "spi_initialized", "bus": SPI_BUS,
               "sck": SPI_SCK_PIN, "mosi": SPI_MOSI_PIN,
               "miso": SPI_MISO_PIN, "cs": SPI_CS_PIN, "freq": SPI_FREQ})
    except Exception as e:
        _emit({"status": "error", "error": "SPI init failed", "details": str(e)})

    bme280 = _init_bme280(spi, cs) if spi is not None else None

    mq135 = None
    try:
        mq135 = MQ135(MQ135_PIN, r_zero=MQ135_R_ZERO, r_load=MQ135_R_LOAD)
        _emit({"status": "mq135_initialized", "pin": MQ135_PIN})
    except Exception as e:
        _emit({"status": "error", "error": "MQ135 init failed", "details": str(e)})

    if bme280 is None and mq135 is None:
        _emit({"status": "error", "error": "No sensors available"})
        _blink_error(led)
        return

    _emit({"status": "monitoring_started",
           "bme280_available": bme280 is not None,
           "mq135_available": mq135 is not None})

    iteration = 0
    while True:
        try:
            data = {"timestamp": _now()}
            bme_ok = False
            mq_ok = False

            if bme280 is not None:
                try:
                    t_c, p_pa, h_pct = bme280.read_compensated_data()
                    data["bme280"] = {
                        "temperature_c": round(t_c, 2),
                        "humidity_percent": round(h_pct, 1),
                        "pressure_hpa": round(p_pa / 100.0, 1),
                        "pressure_pa": round(p_pa, 0),
                    }
                    bme_ok = True
                except Exception as e:
                    _emit({"status": "error", "sensor": "bme280",
                           "error": "read failed", "details": str(e),
                           "attempting_recovery": True})
                    bme280, spi, cs = _recover_bme280(spi, cs)

            if mq135 is not None:
                try:
                    data["mq135"] = mq135.get_all_readings()
                    mq_ok = True
                except Exception as e:
                    _emit({"status": "error", "sensor": "mq135",
                           "error": "read failed", "details": str(e)})

            _emit(data)

            if led is not None:
                if bme_ok and mq_ok:
                    _blink(led, 3)
                elif bme_ok:
                    _blink(led, 1)
                elif mq_ok:
                    _blink(led, 2)
                else:
                    _blink_error(led)

            iteration += 1
            if iteration % GC_COLLECT_INTERVAL == 0:
                gc.collect()

            time.sleep(SENSOR_READ_INTERVAL_SEC)

        except KeyboardInterrupt:
            _emit({"status": "stopped", "message": "Monitoring stopped by user"})
            return
        except Exception as e:
            _emit({"status": "error", "error": "Unexpected error in loop",
                   "details": str(e), "type": type(e).__name__})
            time.sleep(SENSOR_READ_INTERVAL_SEC)


if __name__ == "__main__":
    auto_start_monitoring()
