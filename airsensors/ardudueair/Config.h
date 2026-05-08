#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>
#include <Arduino.h>

// I2C Configuration (BME280 on I2C)
const int BME280_I2C_ADDR = 0x76;  // BME280 I2C address (SDO→GND)

// LED Configuration
const int LED_PIN = 13;
const int LED_BLINK_DURATION_MS = 100;

// MQ135 Configuration
const int MQ135_PIN = A0;        // Analog pin A0 (A0 on module)
const float MQ135_R_LOAD = 10000.0;      // 10kΩ load resistor
const float MQ135_R_ZERO = 280000.0;     // Initial guess; overridden by auto-calibration

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
const unsigned long SENSOR_READ_INTERVAL_MS = 5000;

// ADC Configuration
const int ADC_MAX_VALUE = 4095;       // 12-bit ADC on Due
const float VOLTAGE_REFERENCE = 3.3;  // Arduino Due ADC reference is 3.3V
const float MIN_VOLTAGE_THRESHOLD = 0.01;

// BME280 Reliability Tuning
const unsigned long BME280_RUNTIME_RETRY_INTERVAL_MS = 10000;

// Math helper
const float EPSILON = 1e-6;

// MQ135 Auto-Calibration
const float MQ135_ASSUMED_CLEAN_AIR_CO2_PPM = 410.0;  // Global outdoor baseline (~650m mountain air)
const unsigned long MQ135_CALIBRATION_SETTLE_MS = 5000; // Extra settle time before calibrating
const int MQ135_CALIBRATION_SAMPLES = 10;               // Number of ADC readings to average during calibration
const int MQ135_CALIBRATION_SAMPLE_DELAY_MS = 50;       // Delay between calibration samples

#endif