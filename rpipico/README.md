# Raspberry Pi Pico Sensor Testing

This directory contains MicroPython scripts to test BME280 and MQ135 sensors with the Raspberry Pi Pico.

## Files

- `sensor_test.py` - Basic sensor connectivity test
- `advanced_sensor_test.py` - Complete functionality test with detailed readings
- `bme280.py` - Full BME280 sensor library
- `README.md` - This file

## Hardware Requirements

### BME280 Environmental Sensor
- Temperature, humidity, and pressure sensor
- I2C interface
- Operating voltage: 3.3V

### MQ135 Air Quality Sensor
- Gas sensor for air quality monitoring
- Analog output
- Operating voltage: 5V (can work with 3.3V)

## Wiring Connections

### BME280 (I2C)
```
BME280    Raspberry Pi Pico
VCC   →   3.3V (Pin 36)
GND   →   GND (Pin 38)
SDA   →   GP4 (Pin 6)
SCL   →   GP5 (Pin 7)
```

### MQ135 (Analog)
```
MQ135     Raspberry Pi Pico
VCC   →   5V (Pin 40) or 3.3V (Pin 36)
GND   →   GND (Pin 38)
A0    →   GP28 (Pin 34) - ADC2
```

## Running the Tests

### Prerequisites
1. Install MicroPython on your Raspberry Pi Pico
2. Connect the Pico to your computer via USB
3. Use a terminal/IDE that supports MicroPython (Thonny, rshell, etc.)

### Method 1: Using Thonny IDE
1. Open Thonny IDE
2. Select "MicroPython (Raspberry Pi Pico)" as the interpreter
3. Upload the test files to the Pico
4. Run the desired test script

### Method 2: Using rshell
```bash
# Install rshell if not already installed
pip install rshell

# Connect to the Pico (replace /dev/cu.usbmodem2101 with your port)
rshell -p /dev/cu.usbmodem2101

# Copy files to the Pico
cp sensor_test.py /pyboard/
cp bme280.py /pyboard/
cp advanced_sensor_test.py /pyboard/

# Enter REPL mode
repl

# Run the basic test
exec(open('sensor_test.py').read())

# Or run the advanced test
exec(open('advanced_sensor_test.py').read())
```

### Method 3: Command Line Upload
```bash
# Check if the Pico is connected
ls /dev/cu.usbmodem*

# Use mpremote (install with: pip install mpremote)
mpremote connect /dev/cu.usbmodem2101 cp sensor_test.py :
mpremote connect /dev/cu.usbmodem2101 cp bme280.py :
mpremote connect /dev/cu.usbmodem2101 exec "exec(open('sensor_test.py').read())"
```

## Test Scripts

### `sensor_test.py`
- Basic connectivity test
- I2C device scanning
- BME280 chip ID verification
- MQ135 ADC reading test
- Provides wiring guide

### `advanced_sensor_test.py`
- Complete BME280 functionality with calibrated readings
- Temperature in Celsius and Fahrenheit
- Pressure in Pascals, hPa, and inches of mercury
- Humidity percentage
- MQ135 air quality analysis with CO2 estimation
- Air quality status (Excellent/Good/Fair/Poor/Very Poor)

## Expected Output

### Successful BME280 Connection
```
✓ BME280 found at address 0x76
Chip ID: 0x60 (Valid BME280)
Reading #1:
  Temperature: 23.45°C (74.21°F)
  Pressure: 101325.00 Pa (1013.25 hPa)
  Humidity: 45.67%
```

### Successful MQ135 Connection
```
✓ MQ135 ADC readings successful
Reading # 1: 1.234V, 15432.1Ω, Ratio: 0.203, ~567.8ppm (Good)
Average values:
  Voltage: 1.234V
  Resistance: 15432.1Ω
  Air Quality: Good
```

## Troubleshooting

### BME280 Issues
- **No I2C devices found**: Check wiring, especially SDA and SCL connections
- **Wrong chip ID**: May be a different sensor (BMP280, etc.)
- **Communication errors**: Check power supply (3.3V) and I2C pull-up resistors

### MQ135 Issues
- **Unstable readings**: Sensor needs 24-48 hour burn-in period
- **Readings too high/low**: Calibration needed (adjust R_zero value)
- **No ADC readings**: Check analog pin connection (GP28)

### General Issues
- **Device not found**: Check USB connection and drivers
- **Permission denied**: Try running with sudo or check user permissions
- **Import errors**: Ensure all files are uploaded to the Pico

## Calibration Notes

### MQ135 Calibration
The MQ135 sensor requires calibration for accurate readings:

1. **Clean Air Calibration**: Place sensor in clean outdoor air for 24 hours
2. **Record R_zero**: Note the resistance value in clean air
3. **Update Script**: Modify the `r_zero` value in the MQ135 class
4. **Verify**: Test with known gas concentrations if possible

### BME280 Calibration
The BME280 uses internal calibration coefficients stored in the sensor. No user calibration is typically required.

## Advanced Usage

### Continuous Monitoring
```python
# Example: Log data every 5 minutes
import time

while True:
    temp, pressure, humidity = bme280_sensor.read_all()
    co2_ppm = mq135.read_ppm()
    
    print(f"Temp: {temp:.1f}°C, RH: {humidity:.1f}%, CO2: {co2_ppm:.0f}ppm")
    time.sleep(300)  # 5 minutes
```

### Data Logging to File
```python
# Save readings to CSV file
with open('sensor_data.csv', 'w') as f:
    f.write('timestamp,temperature,humidity,pressure,co2_ppm\n')
    # Add your data logging loop here
```

## Contributing

Feel free to submit improvements, calibration data, or additional sensor support!