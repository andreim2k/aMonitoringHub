#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>
#include <Arduino.h>
#include <Ethernet.h>

// I2C Configuration (BME280 on I2C)
const int BME280_I2C_ADDR = 0x77;  // BME280 default I2C address (0x76 if SDO→GND, 0x77 if SDO→VCC)

// LED Configuration
const int LED_PIN = 13;
const int LED_BLINK_DURATION_MS = 100;

// MQ135 Configuration
const int MQ135_PIN = A0;        // Analog pin A0
const float MQ135_R_LOAD = 10000.0;      // 10kΩ load resistor
const float MQ135_R_ZERO = 280000.0;     // Calibrated for 650m mountain air (410ppm CO2 baseline)

// MQ135 Gas Calculation Constants
const float MQ135_CO2_A = 116.6020682;
const float MQ135_CO2_B = -2.769034857;
const float MQ135_NH3_A = 102.694;
const float MQ135_NH3_B = -2.815;
const float MQ135_ALCOHOL_A = 77.255;
const float MQ135_ALCOHOL_B = -3.18;

// MQ135 PPM Limits
const float MQ135_CO2_MAX = 10000.0;
const float MQ135_NH3_MAX = 500.0;
const float MQ135_ALCOHOL_MAX = 1000.0;

// Air Quality Thresholds (CO2 ppm)
const int AQ_EXCELLENT = 400;
const int AQ_GOOD = 600;
const int AQ_FAIR = 1000;
const int AQ_POOR = 1500;
const int AQ_VERY_POOR = 2500;

// Timing Configuration (milliseconds)
const unsigned long BOOT_DELAY_MS = 2000;
const unsigned long BM280_RETRY_DELAY_MS = 2000;
const unsigned long SENSOR_READ_INTERVAL_MS = 5000;

// BM280 Recovery Configuration
const int I2C_RECOVERY_RETRIES = 3;
const int I2C_OPERATION_TIMEOUT_MS = 100;
const int I2C_STATUS_CHECK_TIMEOUT_MS = 500;

// ADC Configuration (ATmega328P = 10-bit, 5V reference)
const int ADC_MAX_VALUE = 1023;  // 10-bit ADC on ATmega328P
const float VOLTAGE_REFERENCE = 5.0;  // Arduino Ethernet ADC reference is 5V
const float MIN_VOLTAGE_THRESHOLD = 0.01;

// BM280 Reliability Tuning
const int BM280_STARTUP_RETRIES = 10;
const unsigned long BM280_RUNTIME_RETRY_INTERVAL_MS = 10000;
const int BM280_RUNTIME_INIT_RETRIES = 2;
const unsigned long BM280_RUNTIME_RETRY_DELAY_MS = 500;
const unsigned long BM280_MAX_BACKOFF_MS = 5000;

// Ethernet Configuration
const uint8_t ETHERNET_MAC[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};
const IPAddress SERVER_IP(192, 168, 1, 100);  // Backend server receiving UDP
const uint16_t SERVER_PORT = 5005;             // UDP port on backend
const uint16_t LOCAL_PORT = 5005;              // Local UDP port (listen and send)
const bool USE_DHCP = true;                    // Set to false for static IP
const IPAddress STATIC_IP(192, 168, 1, 101);   // Fallback static IP if DHCP fails

#endif
