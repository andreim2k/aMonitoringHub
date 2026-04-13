"""
Auto-boot JSON sensor monitor for Raspberry Pi Pico.
BMP280 over SPI + MQ135 over ADC.
Emits one JSON object per cycle on USB serial.
"""

import builtins
import gc
import json
import time

from machine import Pin, SPI
import machine

try:
    from lib.bmp280_spi import BMP280_SPI
    from lib.mq135 import MQ135
    from lib.config import (
        SPI_BUS, SPI_SCK_PIN, SPI_MOSI_PIN, SPI_MISO_PIN, SPI_CS_PIN,
        SPI_FREQ, SPI_POLARITY, SPI_PHASE,
        MQ135_PIN, MQ135_R_ZERO, MQ135_R_LOAD,
        BOOT_DELAY_SEC, BMP280_RETRY_DELAY_SEC, BMP280_INIT_RETRIES,
        BMP280_RECOVERY_INIT_RETRIES, BMP280_RECOVERY_RETRY_DELAY_SEC,
        SENSOR_READ_INTERVAL_SEC, GC_COLLECT_INTERVAL,
        LED_PIN, LED_BLINK_DURATION_MS,
        BMP280_MAX_CONSEC_FAILS_BEFORE_REBOOT,
        BMP280_OPTIONAL_RETRY_DELAY_SEC, BMP280_REQUIRED,
    )
except ImportError as e:
    print(json.dumps({
        "error": "Failed to import required libraries",
        "details": str(e),
    }))
    raise

_BOOT_TICKS_MS = time.ticks_ms()
_POS_INF = float("inf")
_NEG_INF = float("-inf")


def _now():
    """Monotonic seconds since boot, safe across ticks_ms wraparound."""
    return time.ticks_diff(time.ticks_ms(), _BOOT_TICKS_MS) / 1000.0


def _sanitize_numbers(value):
    if isinstance(value, dict):
        return {k: _sanitize_numbers(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_numbers(v) for v in value]
    if isinstance(value, float):
        if value != value or value == _POS_INF or value == _NEG_INF:
            return None
    return value


def _emit(obj):
    print(json.dumps(_sanitize_numbers(obj)))


def _validate_bmp280_reading(temp_c, pressure_pa):
    if temp_c < -40.0 or temp_c > 85.0:
        raise ValueError("BMP280 temperature out of range: %.2f C" % temp_c)
    if pressure_pa < 30000.0 or pressure_pa > 110000.0:
        raise ValueError("BMP280 pressure out of range: %.1f Pa" % pressure_pa)


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
    time.sleep_ms(5)
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


def _init_bmp280(spi, cs, retries, retry_delay_sec, context):
    """Try to init the BMP280. Returns sensor or None."""
    if retries < 1:
        retries = 1

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            sensor = BMP280_SPI(spi, cs)
            _emit({"status": "bmp280_initialized", "attempt": attempt})
            return sensor
        except Exception as e:
            last_err = e
            _emit({
                "status": "bmp280_retry",
                "context": context,
                "attempt": attempt,
                "retries": retries,
                "error": str(e),
            })
            if attempt < retries and retry_delay_sec > 0:
                time.sleep(retry_delay_sec)
    _emit({"status": "warning", "message": "BMP280 unavailable",
           "context": context,
           "last_error": str(last_err) if last_err else None})
    return None


def _recover_bmp280(spi, cs):
    """Tear down the SPI bus and bring up a fresh BMP280. Returns
    (sensor_or_None, new_spi_or_None, new_cs_or_None)."""
    _safe_deinit_spi(spi)
    gc.collect()
    try:
        new_spi, new_cs = _make_spi()
    except Exception as e:
        _emit({"status": "error", "error": "SPI reinit failed", "details": str(e)})
        return None, None, None
    sensor = _init_bmp280(
        new_spi,
        new_cs,
        retries=BMP280_RECOVERY_INIT_RETRIES,
        retry_delay_sec=BMP280_RECOVERY_RETRY_DELAY_SEC,
        context="recovery",
    )
    if sensor is not None:
        _emit({"status": "recovered", "sensor": "bmp280"})
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
    if getattr(builtins, "PICO_SAFE_BOOT", False):
        _emit({"status": "safe_boot", "message": "Auto-start disabled by boot pin"})
        return

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

    startup_bmp_retries = BMP280_INIT_RETRIES if BMP280_REQUIRED else 1
    startup_bmp_retry_delay = BMP280_RETRY_DELAY_SEC if startup_bmp_retries > 1 else 0.0
    bmp280 = _init_bmp280(
        spi, cs,
        retries=startup_bmp_retries,
        retry_delay_sec=startup_bmp_retry_delay,
        context="startup",
    ) if spi is not None else None

    mq135 = None
    try:
        mq135 = MQ135(MQ135_PIN, r_zero=MQ135_R_ZERO, r_load=MQ135_R_LOAD)
        _emit({"status": "mq135_initialized", "pin": MQ135_PIN})
    except Exception as e:
        _emit({"status": "error", "error": "MQ135 init failed", "details": str(e)})

    if bmp280 is None and mq135 is None:
        _emit({"status": "error", "error": "No sensors available"})
        _blink_error(led)
        return

    _emit({"status": "monitoring_started",
           "bmp280_available": bmp280 is not None,
           "bmp280_required": BMP280_REQUIRED,
           "mq135_available": mq135 is not None})

    iteration = 0
    next_bmp_retry_at = _now()
    bmp_fail_streak = 0
    while True:
        try:
            data = {"timestamp": _now()}
            bmp_ok = False
            mq_ok = False

            if bmp280 is None and _now() >= next_bmp_retry_at:
                _emit({"status": "bmp280_recovery_attempt"})
                bmp280, spi, cs = _recover_bmp280(spi, cs)
                if bmp280 is None:
                    bmp_fail_streak += 1
                    next_bmp_retry_at = _now() + BMP280_RETRY_DELAY_SEC
                else:
                    bmp_fail_streak = 0

            if bmp280 is not None:
                try:
                    t_c, p_pa = bmp280.read_compensated_data()
                    _validate_bmp280_reading(t_c, p_pa)
                    data["bmp280"] = {
                        "temperature_c": round(t_c, 2),
                        "pressure_hpa": round(p_pa / 100.0, 1),
                        "pressure_pa": round(p_pa, 0),
                    }
                    bmp_ok = True
                    bmp_fail_streak = 0
                except Exception as e:
                    _emit({"status": "error", "sensor": "bmp280",
                           "error": "read failed", "details": str(e),
                           "attempting_recovery": True})
                    bmp280, spi, cs = _recover_bmp280(spi, cs)
                    if bmp280 is None:
                        bmp_fail_streak += 1
                        next_bmp_retry_at = _now() + BMP280_RETRY_DELAY_SEC
                    else:
                        bmp_fail_streak = 0

            if mq135 is not None:
                try:
                    data["mq135"] = mq135.get_all_readings()
                    mq_ok = True
                except Exception as e:
                    _emit({"status": "error", "sensor": "mq135",
                           "error": "read failed", "details": str(e)})

            _emit(data)

            if led is not None:
                if bmp_ok and mq_ok:
                    _blink(led, 3)
                elif bmp_ok:
                    _blink(led, 1)
                elif mq_ok:
                    _blink(led, 2)
                else:
                    _blink_error(led)

            if bmp_fail_streak >= BMP280_MAX_CONSEC_FAILS_BEFORE_REBOOT:
                if BMP280_REQUIRED:
                    _emit({
                        "status": "error",
                        "sensor": "bmp280",
                        "error": "persistent_failure",
                        "fail_streak": bmp_fail_streak,
                        "action": "machine_reset"
                    })
                    time.sleep_ms(200)
                    machine.reset()
                else:
                    _emit({
                        "status": "warning",
                        "sensor": "bmp280",
                        "error": "persistent_failure_optional",
                        "fail_streak": bmp_fail_streak,
                        "action": "continue_without_bmp280",
                        "next_retry_sec": BMP280_OPTIONAL_RETRY_DELAY_SEC,
                    })
                    bmp_fail_streak = 0
                    next_bmp_retry_at = _now() + BMP280_OPTIONAL_RETRY_DELAY_SEC

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
