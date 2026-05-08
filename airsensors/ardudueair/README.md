# Arduino Due Sensor Monitoring Sketch

Auto-boot JSON sensor monitor for Arduino Due. Outputs BME280 (I2C) + MQ135 (ADC) sensor data in JSON format every 5 seconds over the Programming Port (Serial).

## Wiring

### BME280 → Arduino Due (I2C)
| BME280 pin | Due pin | Notes |
|---|---|---|
| VIN | **5V** | power input (module has onboard regulator to 3.3V) |
| GND | **GND** | |
| SCL | **D20** (Wire SCL) | I2C clock |
| SDA | **D21** (Wire SDA) | I2C data |
| 3V3 | (unconnected) | output from regulator, not needed |

### MQ135 → Arduino Due (analog sensor)
| MQ135 pin | Due pin | Notes |
|---|---|---|
| VCC | **3.3V** | must match ADC reference (3.3V) for valid ppm math |
| GND | **GND** | |
| A0 | **A0** | analog pin (0–3.3V, scaled to 0–4095) |
| D0 | (unconnected) | digital threshold not used |

> **Note:** MQ135 modules are often labeled "5V". Powering at 3.3V is safe for the heater and keeps the analog output within the Due's 3.3V ADC range. If you must use 5V, add a voltage divider on A0 and update `VOLTAGE_REFERENCE` in `Config.h`.

### LED
- Onboard **D13** (no wiring needed)

### USB
- **Programming Port** (center USB port, closer to power jack) @ 115200 baud → `/dev/tty.usbmodem*` or `/dev/ttyACM*`

## Build & Upload

1. **Install Arduino IDE** (https://www.arduino.cc/en/software)
2. **Add Arduino SAM Boards**:
   - IDE → Preferences → Additional Boards Manager URLs
   - Add: `https://downloads.arduino.cc/packages/package_index.json`
   - Tools → Board: Board Manager → Search "Arduino SAM" → Install "Arduino SAM Boards (32-bits ARM Cortex-M3)"
3. **Select board**:
   - Tools → Board → Arduino Due (Programming Port)
   - Tools → Port → `/dev/tty.usbmodem*` (macOS) or `/dev/ttyACM*` (Linux)
4. **Compile & upload**:
   - Sketch → Upload (Ctrl+U)
   - IDE will auto-trigger 1200-baud bootloader entry; press ERASE+RESET if upload stalls

## JSON Output Format

Every 5 seconds:
```json
{
  "timestamp": 1234.567,
  "timestamp_since_boot": 123.456,
  "bme280": {
    "temperature_c": 23.45,
    "humidity_percent": 55.0,
    "pressure_hpa": 1013.2,
    "pressure_pa": 101320.0
  },
  "mq135": {
    "raw_adc": 2048,
    "voltage_v": 1.234,
    "resistance_ohm": 10234.5,
    "ratio_rs_r0": 0.242,
    "co2_ppm": 560.1,
    "nh3_ppm": 12.3,
    "alcohol_ppm": 45.6,
    "air_quality_status": "Good",
    "air_quality_index": 2,
    "r_zero_ohm": 42304.5
  }
}
```

Plus diagnostic messages (`starting`, `led_initialized`, `bme280_initialized`, `mq135_initialized`, `monitoring_started`, etc.).

## Status Messages (JSON `status` field)

| Status | Meaning |
|---|---|
| `starting` | Boot sequence starting |
| `led_initialized` | LED ready |
| `bme280_initialized` | BME280 sensor ready |
| `mq135_initialized` | MQ135 sensor ready |
| `monitoring_started` | Both sensors OK, continuous read loop began |
| `bme280_reconnect_attempt` | BME280 lost during runtime, attempting reconnect |
| `recovered` | Sensor reconnected successfully |
| `warning` | Non-fatal error (e.g., BME280 unavailable, continuing with MQ135) |
| `error` | Fatal error (e.g., both sensors failed) |
| `diagnostic` | LED blink pattern diagnostic |

## LED Blink Pattern

- **1 blink**: BME280 only (MQ135 failed)
- **2 blinks**: MQ135 only (BME280 failed)
- **3 blinks**: Both sensors OK
- **Slow 3-blink**: Both sensors failed (error state)

## Troubleshooting

### Upload fails / "No device found"
- Plug into **Programming Port** (center USB port, closer to power jack)
- Press **ERASE** button, then **RESET**, wait for bootloader (amber LED on Due)
- Retry upload

### No JSON output on Serial
- Open a serial monitor at 115200 baud on the correct port
- Check LED pattern: 1/2/3 blinks = sensors working, slow blinks = both failed
- If slow blinks: check wiring, voltage on 3.3V rail

### BME280 readings stuck / "BME280 not ready"
- Check SDA/SCL continuity and pull-ups
- Verify BME280 module VIN is connected to 5V (not 3.3V)
- Ensure module has onboard 3.3V regulator

### MQ135 ppm values unrealistic
- Confirm MQ135 **VCC = 3.3V** to match `VOLTAGE_REFERENCE` in `Config.h`
- Let sensor warm up for 2–5 minutes on first power-up or after extended cold soak
- 24 hours first-time burn-in recommended; recalibrate `R_ZERO` if needed

## Backend Integration

The backend (`backend/usb_json_reader.py`) auto-detects `/dev/tty.usbmodem*` and parses this JSON. The field names and structure must match exactly for the backend to ingest data without errors.

## Power Budget

- Arduino Due board: ~100–130 mA
- BME280 (normal mode): <1 mA
- MQ135 heater @ 3.3V: ~60–80 mA
- **Total**: ~160–210 mA (well within 500 mA USB limit)

USB 2.0 @ 500 mA is sufficient.

## Source Files

- `ardudueair.ino` — main sketch (setup + loop)
- `Config.h` — pin definitions, calibration constants, timing
- `BME280_I2C.h` / `BME280_I2C.cpp` — BME280 driver (I2C)
- `MQ135.h` / `MQ135.cpp` — MQ135 driver
- `README.md` — this file
