/*
 * BME280 Weather Station Reader - IMPROVED VERSION
 *
 * Reads temperature, humidity, and pressure from BME280 sensor every second
 * and sends data via USB serial connection to the weather station backend.
 *
 * IMPROVEMENTS IN THIS VERSION:
 * - Replaced String usage with C-style strings for better memory management
 * - Added watchdog timer for production reliability
 * - Defined constants for all magic numbers
 * - Enhanced error recovery and stability
 *
 * Hardware Requirements:
 * - Arduino Uno/Nano/ESP32 (any compatible board)
 * - BME280 sensor module
 * - I2C connection (SDA, SCL)
 *
 * Wiring:
 * BME280 VCC -> 3.3V (or 5V if module supports it)
 * BME280 GND -> GND
 * BME280 SDA -> A4 (Uno/Nano) or SDA pin
 * BME280 SCL -> A5 (Uno/Nano) or SCL pin
 *
 * Libraries Required:
 * - Adafruit BME280 Library
 * - Adafruit Sensor Library
 *
 * Serial Output Format (JSON):
 * {"temp":22.50,"humidity":45.30,"pressure":1013.25,"timestamp":123456789}
 */

#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

// Watchdog timer support (AVR boards only)
#if defined(__AVR__)
  #include <avr/wdt.h>
  #define WATCHDOG_SUPPORTED
#endif

// =============================================================================
// CONSTANTS - All magic numbers defined here
// =============================================================================

// Communication constants
const unsigned long SERIAL_BAUD_RATE = 9600;
const unsigned long SERIAL_TIMEOUT = 1000;       // 1 second timeout for serial
const int MAX_COMMAND_LENGTH = 32;               // Maximum command string length

// Timing constants
const unsigned long READING_INTERVAL = 1000;     // 1 second = 1000ms
const unsigned long SENSOR_STABILIZATION_DELAY = 100;
const unsigned long RETRY_DELAY = 1000;          // Delay between sensor retries
const unsigned long TEST_READING_DELAY = 500;    // Delay between test readings

// Sensor constants
const uint8_t BME280_I2C_ADDR_PRIMARY = 0x76;
const uint8_t BME280_I2C_ADDR_SECONDARY = 0x77;
const int SENSOR_INIT_MAX_RETRIES = 3;
const int TEST_READING_COUNT = 5;

// Data validation ranges
const float TEMP_MIN_VALID = -40.0;              // BME280 minimum temperature
const float TEMP_MAX_VALID = 85.0;               // BME280 maximum temperature
const float HUMIDITY_MIN_VALID = 0.0;            // Minimum humidity
const float HUMIDITY_MAX_VALID = 100.0;          // Maximum humidity
const float PRESSURE_MIN_VALID = 300.0;          // Minimum pressure in hPa
const float PRESSURE_MAX_VALID = 1100.0;         // Maximum pressure in hPa

// Precision constants
const int DECIMAL_PLACES = 2;                    // Decimal places for sensor readings

// Version information
const char* DEVICE_NAME = "BME280_Weather_Reader";
const char* DEVICE_VERSION = "1.1";
const char* DEVICE_AUTHOR = "aWeatherStation";

// JSON string constants to save flash memory
const char JSON_STATUS[] PROGMEM = "status";
const char JSON_TEMP[] PROGMEM = "temp";
const char JSON_HUMIDITY[] PROGMEM = "humidity";
const char JSON_PRESSURE[] PROGMEM = "pressure";
const char JSON_TIMESTAMP[] PROGMEM = "timestamp";
const char JSON_MESSAGE[] PROGMEM = "message";
const char JSON_ERROR[] PROGMEM = "error";

// =============================================================================
// GLOBAL VARIABLES
// =============================================================================

// BME280 sensor object
Adafruit_BME280 bme;

// Timing variables
unsigned long lastReading = 0;

// Status variables
bool sensorInitialized = false;
unsigned long startTime = 0;

// Command buffer for serial input (replaces String)
char commandBuffer[MAX_COMMAND_LENGTH];

// =============================================================================
// DATA STRUCTURES
// =============================================================================

struct SensorData {
  float temperature;
  float humidity;
  float pressure;
  unsigned long timestamp;
  bool valid;
};

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

void resetWatchdog() {
#ifdef WATCHDOG_SUPPORTED
  wdt_reset();
#endif
}

void enableWatchdog() {
#ifdef WATCHDOG_SUPPORTED
  wdt_enable(WDTO_8S);  // 8 second timeout
#endif
}

// Safe JSON string printing using PROGMEM
void printJsonKey(const char* key) {
  Serial.print(F("\""));
  Serial.print((__FlashStringHelper*)key);
  Serial.print(F("\":"));
}

void printJsonString(const char* key, const char* value) {
  printJsonKey(key);
  Serial.print(F("\""));
  Serial.print(value);
  Serial.print(F("\""));
}

void printJsonNumber(const char* key, float value, int decimals = DECIMAL_PLACES) {
  printJsonKey(key);
  Serial.print(value, decimals);
}

void printJsonNumber(const char* key, unsigned long value) {
  printJsonKey(key);
  Serial.print(value);
}

void printJsonNumber(const char* key, int value) {
  printJsonKey(key);
  Serial.print(value);
}

void printJsonBoolean(const char* key, bool value) {
  printJsonKey(key);
  Serial.print(value ? F("true") : F("false"));
}

// =============================================================================
// SENSOR FUNCTIONS
// =============================================================================

bool initializeSensorWithRetry() {
  for (int attempt = 0; attempt < SENSOR_INIT_MAX_RETRIES; attempt++) {
    resetWatchdog();

    if (bme.begin(BME280_I2C_ADDR_PRIMARY)) {
      Serial.print(F("{"));
      printJsonString(JSON_STATUS, "initialized");
      Serial.print(F(","));
      printJsonString("address", "0x76");
      Serial.println(F("}"));
      return true;
    }

    if (bme.begin(BME280_I2C_ADDR_SECONDARY)) {
      Serial.print(F("{"));
      printJsonString(JSON_STATUS, "initialized");
      Serial.print(F(","));
      printJsonString("address", "0x77");
      Serial.println(F("}"));
      return true;
    }

    if (attempt < SENSOR_INIT_MAX_RETRIES - 1) {
      Serial.print(F("{"));
      printJsonString(JSON_STATUS, "retrying");
      Serial.print(F(","));
      printJsonNumber("attempt", attempt + 1);
      Serial.println(F("}"));
      delay(RETRY_DELAY);
    }
  }

  Serial.print(F("{"));
  printJsonString(JSON_STATUS, JSON_ERROR);
  Serial.print(F(","));
  printJsonString(JSON_MESSAGE, "BME280 sensor not found after retries!");
  Serial.println(F("}"));

  Serial.print(F("{"));
  printJsonString(JSON_STATUS, JSON_ERROR);
  Serial.print(F(","));
  printJsonString(JSON_MESSAGE, "Check wiring and I2C address");
  Serial.println(F("}"));

  return false;
}

SensorData readSensorData() {
  resetWatchdog();

  SensorData data;
  data.timestamp = millis() - startTime; // Time since startup in milliseconds
  data.valid = false;

  if (!sensorInitialized) {
    // Return invalid data if sensor not initialized
    data.temperature = 0.0;
    data.humidity = 0.0;
    data.pressure = 0.0;
    return data;
  }

  // Read sensor data
  data.temperature = bme.readTemperature();
  data.humidity = bme.readHumidity();
  data.pressure = bme.readPressure() / 100.0F; // Convert Pa to hPa

  // Validate readings (BME280 returns NaN for failed reads)
  if (isnan(data.temperature) || isnan(data.humidity) || isnan(data.pressure)) {
    data.valid = false;
    return data;
  }

  // Additional sanity checks with named constants
  if (data.temperature < TEMP_MIN_VALID || data.temperature > TEMP_MAX_VALID) {
    data.valid = false;
    return data;
  }

  if (data.humidity < HUMIDITY_MIN_VALID || data.humidity > HUMIDITY_MAX_VALID) {
    data.valid = false;
    return data;
  }

  if (data.pressure < PRESSURE_MIN_VALID || data.pressure > PRESSURE_MAX_VALID) {
    data.valid = false;
    return data;
  }

  data.valid = true;
  return data;
}

void sendSensorData(const SensorData& data) {
  resetWatchdog();

  if (data.valid) {
    // Send valid sensor data as JSON
    Serial.print(F("{"));
    printJsonNumber(JSON_TEMP, data.temperature);
    Serial.print(F(","));
    printJsonNumber(JSON_HUMIDITY, data.humidity);
    Serial.print(F(","));
    printJsonNumber(JSON_PRESSURE, data.pressure);
    Serial.print(F(","));
    printJsonNumber(JSON_TIMESTAMP, data.timestamp);
    Serial.println(F("}"));
  } else {
    // Send error status
    Serial.print(F("{"));
    printJsonString(JSON_STATUS, JSON_ERROR);
    Serial.print(F(","));
    printJsonString(JSON_MESSAGE, "Invalid sensor reading");
    Serial.print(F(","));
    printJsonNumber(JSON_TIMESTAMP, data.timestamp);
    Serial.println(F("}"));
  }
}

// =============================================================================
// SERIAL COMMAND FUNCTIONS
// =============================================================================

// Safe string comparison
bool commandEquals(const char* cmd1, const char* cmd2) {
  return strcmp(cmd1, cmd2) == 0;
}

void handleSerialInput() {
  if (Serial.available() > 0) {
    resetWatchdog();

    // Read command into buffer (replaces String usage)
    int bytesRead = Serial.readBytesUntil('\n', commandBuffer, MAX_COMMAND_LENGTH - 1);
    commandBuffer[bytesRead] = '\0';  // Null terminate

    // Trim whitespace manually
    int start = 0;
    int end = bytesRead - 1;

    // Find start of non-whitespace
    while (start < bytesRead && (commandBuffer[start] == ' ' || commandBuffer[start] == '\t' || commandBuffer[start] == '\r')) {
      start++;
    }

    // Find end of non-whitespace
    while (end >= start && (commandBuffer[end] == ' ' || commandBuffer[end] == '\t' || commandBuffer[end] == '\r' || commandBuffer[end] == '\0')) {
      end--;
    }

    // Move trimmed string to beginning and null terminate
    if (start > 0) {
      for (int i = 0; i <= end - start; i++) {
        commandBuffer[i] = commandBuffer[start + i];
      }
    }
    commandBuffer[end - start + 1] = '\0';

    // Process commands
    if (commandEquals(commandBuffer, "status")) {
      sendStatusInfo();
    } else if (commandEquals(commandBuffer, "reset")) {
      resetSensor();
    } else if (commandEquals(commandBuffer, "test")) {
      performSensorTest();
    } else if (commandEquals(commandBuffer, "info")) {
      sendDeviceInfo();
    } else if (commandEquals(commandBuffer, "help")) {
      sendHelpInfo();
    } else {
      // Send error for unknown command
      Serial.print(F("{"));
      printJsonString(JSON_STATUS, JSON_ERROR);
      Serial.print(F(","));
      printJsonString(JSON_MESSAGE, "Unknown command");
      Serial.print(F(","));
      printJsonString("command", commandBuffer);
      Serial.println(F("}"));
      sendHelpInfo();
    }
  }
}

void sendStatusInfo() {
  resetWatchdog();

  Serial.print(F("{"));
  printJsonString(JSON_STATUS, "running");
  Serial.print(F(","));
  printJsonNumber("uptime", millis() - startTime);
  Serial.print(F(","));
  printJsonBoolean("sensor_initialized", sensorInitialized);
  Serial.print(F(","));
  printJsonNumber("free_memory", getFreeMemory());
  Serial.print(F(","));
  printJsonNumber("reading_interval", READING_INTERVAL);
  Serial.println(F("}"));
}

void resetSensor() {
  resetWatchdog();

  Serial.print(F("{"));
  printJsonString(JSON_STATUS, "resetting_sensor");
  Serial.println(F("}"));

  // Re-initialize the sensor with retry logic
  sensorInitialized = initializeSensorWithRetry();

  if (sensorInitialized) {
    // Reconfigure sensor settings
    bme.setSampling(Adafruit_BME280::MODE_NORMAL,     // Operating Mode
                    Adafruit_BME280::SAMPLING_X2,     // Temperature oversampling
                    Adafruit_BME280::SAMPLING_X2,     // Pressure oversampling
                    Adafruit_BME280::SAMPLING_X2,     // Humidity oversampling
                    Adafruit_BME280::FILTER_X4,       // Filtering
                    Adafruit_BME280::STANDBY_MS_1000); // Standby time

    Serial.print(F("{"));
    printJsonString(JSON_STATUS, "sensor_reset_success");
    Serial.println(F("}"));
  } else {
    Serial.print(F("{"));
    printJsonString(JSON_STATUS, "sensor_reset_failed");
    Serial.println(F("}"));
  }
}

void performSensorTest() {
  resetWatchdog();

  Serial.print(F("{"));
  printJsonString(JSON_STATUS, "testing_sensor");
  Serial.println(F("}"));

  for (int i = 0; i < TEST_READING_COUNT; i++) {
    resetWatchdog();

    SensorData testData = readSensorData();
    Serial.print(F("{"));
    printJsonNumber("test_reading", i + 1);
    Serial.print(F(","));
    printJsonBoolean("valid", testData.valid);

    if (testData.valid) {
      Serial.print(F(","));
      printJsonNumber(JSON_TEMP, testData.temperature);
      Serial.print(F(","));
      printJsonNumber(JSON_HUMIDITY, testData.humidity);
      Serial.print(F(","));
      printJsonNumber(JSON_PRESSURE, testData.pressure);
    }
    Serial.println(F("}"));
    delay(TEST_READING_DELAY);
  }

  Serial.print(F("{"));
  printJsonString(JSON_STATUS, "test_complete");
  Serial.println(F("}"));
}

void sendDeviceInfo() {
  resetWatchdog();

  Serial.print(F("{"));
  printJsonString("device", DEVICE_NAME);
  Serial.print(F(","));
  printJsonString("version", DEVICE_VERSION);
  Serial.print(F(","));
  printJsonString("author", DEVICE_AUTHOR);
  Serial.println(F("}"));

  Serial.print(F("{"));
  printJsonString("arduino_board",
#if defined(ARDUINO_AVR_UNO)
    "Arduino Uno"
#elif defined(ARDUINO_AVR_NANO)
    "Arduino Nano"
#elif defined(ARDUINO_SAM_DUE)
    "Arduino Due"
#elif defined(ARDUINO_ESP32_DEV)
    "ESP32"
#else
    "Unknown"
#endif
  );
  Serial.println(F("}"));

  Serial.print(F("{"));
  printJsonString("compile_date", __DATE__);
  Serial.print(F(" "));
  Serial.print(__TIME__);
  Serial.println(F("\"}"));

  Serial.print(F("{"));
  printJsonBoolean("watchdog_enabled",
#ifdef WATCHDOG_SUPPORTED
    true
#else
    false
#endif
  );
  Serial.println(F("}"));
}

void sendHelpInfo() {
  Serial.print(F("{"));
  printJsonString("help", "Available commands: status, reset, test, info, help");
  Serial.println(F("}"));
}

// =============================================================================
// MEMORY MONITORING
// =============================================================================

int getFreeMemory() {
  // Simple free memory calculation for different boards
#if defined(__AVR__)
  extern int __heap_start, *__brkval;
  int v;
  return (int) &v - (__brkval == 0 ? (int) &__heap_start : (int) __brkval);
#else
  return -1; // Memory calculation only implemented for AVR boards
#endif
}

// =============================================================================
// MAIN ARDUINO FUNCTIONS
// =============================================================================

void setup() {
  // Enable watchdog timer early for maximum protection
  enableWatchdog();

  // Initialize serial communication with named constant
  Serial.begin(SERIAL_BAUD_RATE);
  Serial.setTimeout(SERIAL_TIMEOUT);

  while (!Serial) {
    resetWatchdog();
    ; // Wait for serial port to connect (needed for native USB)
  }

  // Record start time
  startTime = millis();
  resetWatchdog();

  // Initialize I2C communication
  Wire.begin();
  resetWatchdog();

  // Print startup message
  Serial.print(F("{"));
  printJsonString(JSON_STATUS, "starting");
  Serial.print(F(","));
  printJsonString("device", DEVICE_NAME);
  Serial.print(F(","));
  printJsonString("version", DEVICE_VERSION);
  Serial.println(F("}"));

  // Initialize BME280 sensor with retry logic
  sensorInitialized = initializeSensorWithRetry();

  if (sensorInitialized) {
    resetWatchdog();

    // Configure sensor settings for weather monitoring
    bme.setSampling(Adafruit_BME280::MODE_NORMAL,     // Operating Mode
                    Adafruit_BME280::SAMPLING_X2,     // Temperature oversampling
                    Adafruit_BME280::SAMPLING_X2,     // Pressure oversampling
                    Adafruit_BME280::SAMPLING_X2,     // Humidity oversampling
                    Adafruit_BME280::FILTER_X4,       // Filtering
                    Adafruit_BME280::STANDBY_MS_1000); // Standby time

    Serial.print(F("{"));
    printJsonString(JSON_STATUS, "ready");
    Serial.print(F(","));
    printJsonString("sampling", "weather_mode");
    Serial.print(F(","));
    printJsonNumber("interval_ms", READING_INTERVAL);
    Serial.println(F("}"));
  }

  // Short delay for sensor stabilization
  delay(SENSOR_STABILIZATION_DELAY);
  resetWatchdog();
}

void loop() {
  resetWatchdog(); // Reset watchdog at start of each loop iteration

  unsigned long currentTime = millis();

  // Check if it's time for a new reading
  if (currentTime - lastReading >= READING_INTERVAL) {
    lastReading = currentTime;

    SensorData data = readSensorData();
    sendSensorData(data);
  }

  // Handle serial commands if any
  handleSerialInput();

  // Small delay to prevent overwhelming the loop (but keep it small for watchdog)
  delay(10);
}
