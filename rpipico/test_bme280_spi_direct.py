#!/usr/bin/env python3
"""
Direct SPI diagnostic for BME280
Run this on the Pico to test SPI communication and calibration data
"""
import json
import time
from machine import Pin, SPI

print(json.dumps({"test": "BME280_SPI_DIRECT_DIAGNOSTIC"}))

# Config from lib.config
SPI_BUS = 0
SPI_SCK_PIN = 18
SPI_MOSI_PIN = 19
SPI_MISO_PIN = 16
SPI_CS_PIN = 17
SPI_FREQ = 1000000

print(json.dumps({
    "step": 1,
    "action": "Initialize SPI",
    "pins": {
        "sck": SPI_SCK_PIN,
        "mosi": SPI_MOSI_PIN,
        "miso": SPI_MISO_PIN,
        "cs": SPI_CS_PIN,
        "freq": SPI_FREQ
    }
}))

try:
    spi = SPI(
        SPI_BUS,
        baudrate=SPI_FREQ,
        polarity=0,
        phase=0,
        sck=Pin(SPI_SCK_PIN),
        mosi=Pin(SPI_MOSI_PIN),
        miso=Pin(SPI_MISO_PIN),
    )
    cs = Pin(SPI_CS_PIN, Pin.OUT)
    cs.on()
    print(json.dumps({"status": "spi_initialized", "ok": True}))
except Exception as e:
    print(json.dumps({"status": "spi_init_failed", "error": str(e)}))
    import sys
    sys.exit(1)

# Step 2: Read Chip ID (0xD0)
print(json.dumps({"step": 2, "action": "Read Chip ID from register 0xD0"}))

def read_register(reg):
    try:
        cs.off()
        time.sleep(0.001)
        tx_buf = bytearray([reg | 0x80, 0x00])
        rx_buf = bytearray(2)
        spi.write_readinto(tx_buf, rx_buf)
        result = rx_buf[1]
        time.sleep(0.001)
        cs.on()
        return result
    except Exception as e:
        cs.on()
        raise e

try:
    chip_id = read_register(0xD0)
    print(json.dumps({
        "status": "chip_id_read",
        "chip_id": f"0x{chip_id:02X}",
        "expected": "0x60 (BME280) or 0x58 (BMP280)",
        "valid": chip_id in (0x60, 0x58)
    }))
except Exception as e:
    print(json.dumps({"status": "chip_id_read_failed", "error": str(e)}))

# Step 3: Read Calibration Data (0x88-0xA1)
print(json.dumps({"step": 3, "action": "Read Calibration Data"}))

def read_registers(reg, count):
    try:
        cs.off()
        time.sleep(0.001)
        tx_buf = bytearray(count + 1)
        tx_buf[0] = reg | 0x80
        rx_buf = bytearray(count + 1)
        spi.write_readinto(tx_buf, rx_buf)
        result = rx_buf[1:]
        time.sleep(0.001)
        cs.on()
        return result
    except Exception as e:
        cs.on()
        raise e

try:
    calib_data = read_registers(0x88, 24)

    # Parse temperature calibration
    dig_T1 = calib_data[1] << 8 | calib_data[0]

    print(json.dumps({
        "status": "calibration_data_read",
        "bytes_read": len(calib_data),
        "first_10_bytes": [f"0x{b:02X}" for b in calib_data[:10]],
        "dig_T1": dig_T1,
        "dig_T1_hex": f"0x{dig_T1:04X}",
        "all_zero": all(b == 0x00 for b in calib_data),
        "all_ff": all(b == 0xFF for b in calib_data)
    }))

    if all(b == 0x00 for b in calib_data):
        print(json.dumps({
            "error": "CRITICAL: Calibration data is all zeros!",
            "diagnosis": "SPI communication is broken - sensor not responding"
        }))
    elif all(b == 0xFF for b in calib_data):
        print(json.dumps({
            "error": "CRITICAL: Calibration data is all 0xFF!",
            "diagnosis": "CS pin not working or SPI bus not initialized"
        }))
    elif dig_T1 == 0:
        print(json.dumps({
            "error": "CRITICAL: Temperature calibration (dig_T1) is zero!",
            "diagnosis": "Sensor not responding to SPI reads"
        }))
    elif dig_T1 > 50000:
        print(json.dumps({
            "error": "WARNING: dig_T1 seems high",
            "diagnosis": "Might be data corruption - check SPI timing"
        }))

except Exception as e:
    print(json.dumps({"status": "calibration_read_failed", "error": str(e)}))

# Step 4: Read Humidity Calibration (0xA1, 0xE1-0xE7)
print(json.dumps({"step": 4, "action": "Read Humidity Calibration"}))

try:
    dig_H1 = read_register(0xA1)
    calib_H = read_registers(0xE1, 7)

    print(json.dumps({
        "status": "humidity_calib_read",
        "dig_H1": dig_H1,
        "H_bytes_read": len(calib_H),
        "H_first_5": [f"0x{b:02X}" for b in calib_H[:5]]
    }))

except Exception as e:
    print(json.dumps({"status": "humidity_calib_failed", "error": str(e)}))

# Step 5: Read Status Register (0xF3)
print(json.dumps({"step": 5, "action": "Read Status Register"}))

try:
    status = read_register(0xF3)
    print(json.dumps({
        "status": "status_read",
        "value": f"0x{status:02X}",
        "measuring": bool(status & 0x01),
        "im_update": bool(status & 0x02)
    }))
except Exception as e:
    print(json.dumps({"status": "status_read_failed", "error": str(e)}))

print(json.dumps({"step": "complete", "status": "diagnostic_finished"}))
