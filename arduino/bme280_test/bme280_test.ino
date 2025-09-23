#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

// BME280 sensor object
Adafruit_BME280 bme;

// BME280 I2C addresses (try both common addresses)
#define BME280_ADDRESS_PRIMARY   0x77
#define BME280_ADDRESS_SECONDARY 0x76

bool sensorFound = false;
unsigned long lastReading = 0;
const unsigned long readingInterval = 2000; // Read every 2 seconds

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    delay(10); // Wait for serial port to connect
  }
  
  Serial.println("BME280 Sensor Test for Arduino Due");
  Serial.println("==================================");
  
  // Initialize I2C
  Wire.begin();
  
  // Try to initialize BME280 with primary address
  Serial.print("Trying BME280 at address 0x77... ");
  if (bme.begin(BME280_ADDRESS_PRIMARY)) {
    Serial.println("SUCCESS!");
    sensorFound = true;
  } else {
    Serial.println("FAILED");
    
    // Try secondary address
    Serial.print("Trying BME280 at address 0x76... ");
    if (bme.begin(BME280_ADDRESS_SECONDARY)) {
      Serial.println("SUCCESS!");
      sensorFound = true;
    } else {
      Serial.println("FAILED");
    }
  }
  
  if (!sensorFound) {
    Serial.println("\nERROR: Could not find a valid BME280 sensor!");
    Serial.println("Check wiring and I2C address:");
    Serial.println("- VCC to 3.3V (NOT 5V!)");
    Serial.println("- GND to GND");
    Serial.println("- SDA to SDA (pin 20 on Due)");
    Serial.println("- SCL to SCL (pin 21 on Due)");
    Serial.println("\nScanning I2C bus for devices...");
    scanI2C();
  } else {
    Serial.println("\nBME280 sensor initialized successfully!");
    Serial.println("Starting readings...\n");
    
    // Configure sensor settings
    bme.setSampling(Adafruit_BME280::MODE_NORMAL,     // Operating Mode
                    Adafruit_BME280::SAMPLING_X2,     // Temp. oversampling
                    Adafruit_BME280::SAMPLING_X16,    // Pressure oversampling
                    Adafruit_BME280::SAMPLING_X1,     // Humidity oversampling
                    Adafruit_BME280::FILTER_X16,      // Filtering
                    Adafruit_BME280::STANDBY_MS_500); // Standby time
  }
}

void loop() {
  if (!sensorFound) {
    // If sensor not found, keep scanning every 5 seconds
    delay(5000);
    Serial.println("Retrying sensor initialization...");
    setup();
    return;
  }
  
  unsigned long currentTime = millis();
  
  if (currentTime - lastReading >= readingInterval) {
    lastReading = currentTime;
    
    // Read sensor values
    float temperature = bme.readTemperature();
    float pressure = bme.readPressure() / 100.0F; // Convert Pa to hPa
    float humidity = bme.readHumidity();
    
    // Check if readings are valid
    if (isnan(temperature) || isnan(pressure) || isnan(humidity)) {
      Serial.println("ERROR: Failed to read from BME280 sensor!");
      return;
    }
    
    // Print timestamp
    Serial.print("Time: ");
    Serial.print(currentTime / 1000);
    Serial.print("s | ");
    
    // Print temperature
    Serial.print("Temp: ");
    Serial.print(temperature);
    Serial.print("°C (");
    Serial.print(temperature * 9.0 / 5.0 + 32.0);
    Serial.print("°F) | ");
    
    // Print humidity
    Serial.print("Humidity: ");
    Serial.print(humidity);
    Serial.print("% | ");
    
    // Print pressure
    Serial.print("Pressure: ");
    Serial.print(pressure);
    Serial.print(" hPa (");
    Serial.print(pressure * 0.02953);
    Serial.println(" inHg)");
    
    // Calculate approximate altitude (assuming sea level pressure = 1013.25 hPa)
    float altitude = bme.readAltitude(1013.25);
    Serial.print("Approx. Altitude: ");
    Serial.print(altitude);
    Serial.println(" m");
    
    Serial.println("---");
  }
}

void scanI2C() {
  byte error, address;
  int nDevices = 0;
  
  Serial.println("Scanning I2C addresses from 0x01 to 0x7F...");
  
  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    
    if (error == 0) {
      Serial.print("I2C device found at address 0x");
      if (address < 16) Serial.print("0");
      Serial.print(address, HEX);
      Serial.println(" !");
      nDevices++;
    } else if (error == 4) {
      Serial.print("Unknown error at address 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
    }
  }
  
  if (nDevices == 0) {
    Serial.println("No I2C devices found");
    Serial.println("Check your wiring!");
  } else {
    Serial.print("Found ");
    Serial.print(nDevices);
    Serial.println(" device(s)");
  }
  Serial.println("---");
}