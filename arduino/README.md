# Arduino BME280 Weather Station

This directory contains the Arduino code for reading BME280 sensor data and transmitting it to the weather station backend via USB serial connection.

## Hardware Requirements

### Arduino Board (Choose one)
- Arduino Uno
- Arduino Nano 
- Arduino Pro Mini
- **Arduino Due** (32-bit ARM Cortex-M3)
- ESP32 (for WiFi capabilities)
- Any Arduino-compatible board with I2C support

### Sensor
- **BME280** temperature, humidity, and pressure sensor module
- Operating voltage: 3.3V or 5V (depending on module)
- Communication: I2C protocol

### Connections
- USB cable for programming and serial communication
- Jumper wires for sensor connections

## Wiring Diagram

### Arduino Uno/Nano Wiring
```
BME280 Module    Arduino Pin
-----------      -----------
VCC          ->  3.3V (or 5V if module supports it)
GND          ->  GND
SDA          ->  A4 (SDA)
SCL          ->  A5 (SCL)
```

### ESP32 Wiring
```
BME280 Module    ESP32 Pin
-----------      ---------
VCC          ->  3.3V
GND          ->  GND
SDA          ->  GPIO21 (SDA)
SCL          ->  GPIO22 (SCL)
```

### Arduino Due Wiring
```
BME280 Module    Arduino Due Pin
-----------      ---------------
VCC          ->  3.3V (IMPORTANT: Due is 3.3V only!)
GND          ->  GND
SDA          ->  20 (SDA1) or SDA
SCL          ->  21 (SCL1) or SCL
```

**Important Notes:**
- Some BME280 modules are 3.3V only - check your module's specifications
- If using a 5V Arduino with a 3.3V-only BME280, use level shifters or a 3.3V power supply
- **Arduino Due is 3.3V only** - Never connect 5V to Due pins or you may damage the board!
- Arduino Due has two I2C interfaces: Wire (pins 20/21) and Wire1 (pins 70/71)
- Ensure good connections as I2C is sensitive to loose wires

## Library Dependencies

Install these libraries through the Arduino IDE Library Manager:

1. **Adafruit BME280 Library** by Adafruit
   - Search: "BME280" 
   - Install the official Adafruit library

2. **Adafruit Unified Sensor** by Adafruit
   - This is automatically installed with the BME280 library
   - Required for sensor abstraction

### Installation Steps
1. Open Arduino IDE
2. Go to **Tools > Manage Libraries...**
3. Search for "Adafruit BME280"
4. Click **Install** on "Adafruit BME280 Library"
5. Install dependencies when prompted

## Arduino Due Specific Setup

### Important Due Considerations
- **Voltage Warning**: Arduino Due operates at **3.3V only**. Never apply 5V to any pin!
- **USB Connection**: Due has two USB ports:
  - **Programming Port** (closest to power jack) - Use for uploading sketches
  - **Native USB Port** - Can be used for serial communication after programming
- **I2C Interfaces**: Due has two I2C buses:
  - **Wire** (pins 20/21) - Primary I2C bus (recommended)
  - **Wire1** (pins 70/71) - Secondary I2C bus
- **Memory**: Due has much more memory (96KB RAM) compared to Uno (2KB)

### Due Upload Process
1. Connect Due to computer using **Programming Port** (micro USB)
2. In Arduino IDE, select **"Arduino Due (Programming Port)"** from Tools > Board
3. Select correct COM port
4. Press **Reset** button on Due before uploading if upload fails
5. Upload sketch normally

### Using Native USB Port for Serial
If you want to use the Native USB port for serial communication:
1. Upload sketch using Programming Port
2. Disconnect Programming Port cable
3. Connect Native USB Port cable
4. In Arduino IDE, select **"Arduino Due (Native USB Port)"**
5. Open Serial Monitor - it should connect to Native USB

## Setup Instructions

### 1. Hardware Assembly
1. Connect the BME280 sensor to your Arduino according to the wiring diagram above
2. Double-check all connections
3. Connect Arduino to computer via USB cable

### 2. Software Setup
1. Open Arduino IDE
2. Install required libraries (see above)
3. Open `bme280_reader.ino` from this directory
4. Select your board type: **Tools > Board**
5. Select correct COM port: **Tools > Port**
6. Upload the sketch: **Sketch > Upload**

### 3. Testing
1. Open Serial Monitor: **Tools > Serial Monitor**
2. Set baud rate to **9600**
3. You should see JSON output like:
   ```json
   {"status":"starting","device":"BME280_Reader","version":"1.0"}
   {"status":"initialized","address":"0x76"}
   {"status":"ready","sampling":"weather_mode","interval":"1000ms"}
   {"temp":22.50,"humidity":45.30,"pressure":1013.25,"timestamp":123456}
   ```

## Serial Commands

The Arduino sketch supports several commands for debugging and testing:

| Command | Description | Example Output |
|---------|-------------|----------------|
| `status` | Show current status and uptime | `{"status":"running","uptime":45000,...}` |
| `test` | Perform 5 test readings | Multiple test readings with validation |
| `reset` | Reset the BME280 sensor | `{"status":"sensor_reset_success"}` |
| `info` | Show device information | Board type, compile date, etc. |

**Usage:** Type command in Serial Monitor and press Enter.

## Data Format

The Arduino sends sensor data in JSON format every second:

```json
{
  "temp": 22.50,        // Temperature in Celsius
  "humidity": 45.30,    // Humidity percentage (0-100)
  "pressure": 1013.25,  // Pressure in hPa
  "timestamp": 123456   // Milliseconds since startup
}
```

### Error Messages
```json
{"status":"error","message":"Invalid sensor reading","timestamp":123456}
{"status":"error","message":"BME280 sensor not found!"}
```

## Troubleshooting

### Sensor Not Found
```
{"status":"error","message":"BME280 sensor not found!"}
{"status":"error","message":"Check wiring and I2C address"}
```

**Solutions:**
1. Check all wiring connections
2. Verify power supply (3.3V vs 5V compatibility)
3. Try different I2C address (code tries both 0x76 and 0x77)
4. Test I2C scanner sketch to detect connected devices

### Invalid Readings
```
{"status":"error","message":"Invalid sensor reading","timestamp":123456}
```

**Solutions:**
1. Check sensor power supply stability
2. Verify I2C connections (SDA/SCL)
3. Send `reset` command via Serial Monitor
4. Try `test` command to run diagnostics

### Connection Issues
- Ensure Arduino drivers are installed
- Check COM port selection in Arduino IDE
- Verify USB cable supports data (not just charging)
- Try different USB port

### Arduino Due Specific Issues
- **Upload fails**: Press Reset button on Due and try uploading again immediately
- **Serial Monitor empty**: Make sure you selected the correct USB port (Programming vs Native)
- **"Port not found"**: Due may need drivers on some systems - check Arduino Due driver installation
- **Sensor not detected**: Double-check 3.3V connection (Due cannot use 5V BME280 modules)
- **Random resets**: Check power supply - Due needs stable 3.3V power

## Integration with Weather Station

The weather station backend can read this serial data by:

1. **Manual Testing:** Use any serial monitor to view data
2. **Backend Integration:** The Python backend in `backend/sensor_reader.py` can be extended to read from Arduino serial port
3. **USB Connection:** Keep Arduino connected via USB while running the weather station

### Backend Integration Example
```python
import serial
import json

# Connect to Arduino
ser = serial.Serial('/dev/ttyUSB0', 9600)  # Linux
# ser = serial.Serial('COM3', 9600)        # Windows

# Read data
line = ser.readline().decode('utf-8').strip()
try:
    data = json.loads(line)
    if 'temp' in data:
        temperature = data['temp']
        humidity = data['humidity']
        pressure = data['pressure']
        # Process data...
except json.JSONDecodeError:
    print("Invalid JSON received")
```

## Specifications

### BME280 Sensor Specifications
- **Temperature Range:** -40°C to +85°C
- **Temperature Accuracy:** ±1.0°C
- **Humidity Range:** 0-100% RH
- **Humidity Accuracy:** ±3% RH
- **Pressure Range:** 300-1100 hPa
- **Pressure Accuracy:** ±1 hPa
- **Interface:** I2C (addresses 0x76 or 0x77)

### Performance
- **Reading Interval:** 1 second (1 Hz)
- **Startup Time:** ~2 seconds for initialization
- **Power Consumption:** ~3.4µA in sleep mode, ~714µA during measurement
- **Serial Speed:** 9600 baud
- **Arduino Due Performance:** 84 MHz ARM processor, 96KB RAM (much faster than Uno)

## Files in This Directory

- **`bme280_reader.ino`** - Main Arduino sketch
- **`README.md`** - This documentation file
- **`wiring_diagram.png`** - Visual wiring reference (if available)

## Version History

- **v1.0** - Initial release with basic BME280 reading and JSON output
  - 1-second reading interval
  - I2C auto-detection (0x76/0x77)
  - Serial command interface
  - Error handling and validation
  - Memory optimization for Arduino Uno
