# arduethair — Arduino Ethernet Air Monitor

A sketch for the **Arduino Ethernet R3** board that reads BME280 (I2C) and MQ135 (analog) sensors and streams air quality measurements as newline-delimited JSON over UDP every 5 seconds.

---

## Hardware

**Target Board:** Arduino Ethernet R3 (ATmega328P + W5100 Ethernet controller)

**Sensors:**
- **BME280** (I2C at address 0x77): temperature (°C), relative humidity (%), barometric pressure (Pa/hPa)
- **MQ135** (analog on A0): CO₂, NH₃, alcohol/VOC ppm estimates, and air quality status

**Wiring:**

| Signal | Arduino Ethernet Pin | Notes |
|--------|----------------------|-------|
| BME280 VIN | 5V | Module has onboard 3.3V regulator |
| BME280 GND | GND | |
| BME280 SDA | A4 | I2C data (Wire library auto-detects) |
| BME280 SCL | A5 | I2C clock |
| MQ135 VCC | 5V | Heater supply (5V required) |
| MQ135 GND | GND | |
| MQ135 A0 | A0 | Analog output |
| Ethernet | Built-in W5100 | SPI bus (D11/D12/D13) + D10 CS |
| LED | D13 (onboard) | Status indicator; may flicker with Ethernet SPI activity |

**Note on LED:** D13 doubles as the SPI clock (SCK) for the W5100 chip. Blinks may flicker slightly when the Ethernet interface is actively transmitting or receiving. This is normal and does not indicate a fault.

---

## Network Configuration

Edit `Config.h` to set your network parameters:

```cpp
// DHCP mode (automatic IP assignment, recommended for development)
const bool USE_DHCP = true;
const IPAddress STATIC_IP(192, 168, 1, 101);   // Fallback only

// Static IP mode (manual configuration)
const bool USE_DHCP = false;
const IPAddress STATIC_IP(192, 168, 1, 101);

// Destination server receiving sensor data
const IPAddress SERVER_IP(192, 168, 1, 100);
const uint16_t SERVER_PORT = 5005;

// Local port (both listen and send)
const uint16_t LOCAL_PORT = 5005;

// Ethernet MAC address (must be unique on your network)
const uint8_t ETHERNET_MAC[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};
```

**Startup behavior:**
- If `USE_DHCP = true`, the board attempts DHCP. If DHCP fails, it falls back to `STATIC_IP`.
- The board prints its assigned IP address to the serial monitor during setup.

---

## Sensor Calibration

The MQ135 requires a **one-time calibration** of the `R_ZERO` constant to match your specific environment and altitude.

1. Edit `Config.h` and set `MQ135_R_ZERO = 280000.0` (default for 650m mountain air).
2. Upload the sketch and let it run outdoors in fresh air for **30–60 minutes** to warm the sensor.
3. Open the serial monitor at 115200 baud. After stabilization, note the `resistance_ohm` value from a stable reading.
4. Set `MQ135_R_ZERO` to that resistance value and re-upload.
5. The ppm values will now be calibrated relative to your environment's baseline.

See `CALIBRATION_GUIDE.md` in the `ardudueair` project for a detailed walkthrough.

---

## JSON Output Format (every 5 seconds)

```json
{
  "timestamp": 1234.567,
  "timestamp_since_boot": 123.456,
  "bm280": {
    "temperature_c": 23.45,
    "humidity_percent": 55.0,
    "pressure_hpa": 1013.2,
    "pressure_pa": 101320.0
  },
  "mq135": {
    "raw_adc": 512,
    "voltage_v": 2.50,
    "resistance_ohm": 8234.5,
    "ratio_rs_r0": 0.294,
    "co2_ppm": 560.1,
    "nh3_ppm": 12.3,
    "alcohol_ppm": 45.6,
    "air_quality_status": "Good",
    "air_quality_index": 2,
    "r_zero_ohm": 280000.0
  }
}
```

**Notes:**
- If a sensor is unavailable, its section is omitted from the output.
- Timestamps are in seconds (float with 3 decimal places).
- All numeric fields use appropriate precision for plotting / analysis.
- Air quality index: 1=Excellent, 2=Good, 3=Fair, 4=Poor, 5=Very Poor, 6=Hazardous.

---

## Serial Monitor Output (Debugging)

The sketch echoes all JSON to the serial port at 115200 baud for debugging:

```
{...sensor JSON...}
{...sensor JSON...}
```

Connect via the USB Programming port (not Ethernet). Useful for verifying sensor readings before trusting network transmission.

---

## UDP Listener (Backend)

To receive and log the sensor stream on your backend:

**Python example:**
```python
import socket
import json

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('0.0.0.0', 5005))  # Listen on port 5005

while True:
    data, addr = s.recvfrom(1024)
    print(f"From {addr}: {data.decode()}")
    try:
        j = json.loads(data)
        print(f"  CO₂: {j['mq135']['co2_ppm']:.1f} ppm")
    except:
        pass
```

**Bash one-liner (nc):**
```bash
nc -u -l 5005
```

---

## Compilation

```bash
arduino-cli compile --fqbn arduino:avr:ethernet arduethair
```

Verify that SRAM usage is within acceptable limits (< 1500 bytes). The sketch uses F() macros on all string literals to keep them in flash, minimizing RAM footprint.

---

## Upload

```bash
arduino-cli upload --fqbn arduino:avr:ethernet -p /dev/ttyUSB0 arduethair
```

Replace `/dev/ttyUSB0` with your actual USB serial port (e.g., `/dev/ttyACM0` on Linux, `COM3` on Windows, `/dev/cu.usbserial-*` on macOS).

---

## Troubleshooting

**Board not responding on network:**
- Verify Ethernet cable is connected and active (W5100 has no onboard LED).
- Check `Config.h`: `SERVER_IP` and `SERVER_PORT` must match your backend listener.
- Verify MAC address is unique on your network.
- Try pinging the board's assigned IP (watch serial monitor for IP during boot).

**Sensors not appearing in JSON:**
- Check wiring (I2C on A4/A5, MQ135 analog on A0).
- Serial monitor will show `"status":"warning"` or `"status":"error"` during setup if sensors fail to initialize.
- MQ135 failure is fatal (halts the board); BME280 failure is non-fatal (board continues with MQ135 only and retries every 10 seconds).

**JSON format incorrect:**
- Validate using `python3 -c "import json; json.loads('<your_json>')"`
- All fields are floats or ints; no null values.

**Serial monitor shows gibberish:**
- Verify baud rate is set to 115200.
- Check USB driver is installed (CH340 on some clone boards).

**LED not blinking:**
- LED is on D13, which is the SPI clock. Blinks may be faint or flicker with network activity.
- If no blinks at all: check power supply and that LED_PIN is correctly configured in `Config.h`.

---

## MQ135 Air Quality Thresholds

| Status | CO₂ Range (ppm) |
|--------|-----------------|
| Excellent | < 400 |
| Good | 400–600 |
| Fair | 600–1000 |
| Poor | 1000–1500 |
| Very Poor | 1500–2500 |
| Hazardous | ≥ 2500 |

These thresholds are defined in `Config.h` and can be adjusted for your application.

---

## Performance

- **Polling interval:** 5 seconds (adjustable via `SENSOR_READ_INTERVAL_MS` in `Config.h`)
- **UDP packet size:** ~400–500 bytes (typical; depends on sensor availability)
- **Ethernet throughput:** Negligible (< 1 kbps average)
- **Power consumption:** ~100 mA (Arduino + sensors + Ethernet; 5V supply)
- **Startup time:** ~3–4 seconds (includes Ethernet init and sensor boot)

---

## See Also

- [ardudueair](../ardudueair/) — Equivalent sketch for Arduino Due (USB serial output)
- `CALIBRATION_GUIDE.md` — Detailed MQ135 R_ZERO calibration procedure
- Bosch BME280 Datasheet — Temperature/humidity/pressure sensor specification

---

## License

Same as the parent `aMonitoringHub` project.
