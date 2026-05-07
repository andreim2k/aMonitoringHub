#ifndef BME280_SPI_H
#define BME280_SPI_H

#include <Arduino.h>
#include <SPI.h>
#include <stdint.h>

class BME280_SPI {
public:
  BME280_SPI(SPISettings spiSettings, int csPin);

  float read_temperature();
  float read_pressure();
  float read_humidity();
  void read_compensated_data(float &temp, float &pressure, float &humidity);

  void reset();
  void reconfigure();
  uint8_t check_status();
  bool is_ready();
  bool wait_for_ready(unsigned long timeoutMs = 500);

  uint8_t getChipId() { return chip_id; }
  bool hasHumidity() { return has_humidity; }

private:
  SPISettings spiSettings;
  int csPin;
  uint8_t chip_id;
  bool has_humidity;

  // Calibration coefficients
  uint16_t dig_T1;
  int16_t dig_T2, dig_T3;
  uint16_t dig_P1;
  int16_t dig_P2, dig_P3, dig_P4, dig_P5, dig_P6, dig_P7, dig_P8, dig_P9;
  uint8_t dig_H1;
  int16_t dig_H2, dig_H4, dig_H5;
  uint8_t dig_H3, dig_H6;

  uint8_t _read_register(uint8_t reg);
  void _read_registers(uint8_t reg, uint8_t count, uint8_t *buf);
  void _write_register(uint8_t reg, uint8_t value);
  void _read_calibration_data();
  void _configure_sensor();
  void _read_raw_data(uint32_t &raw_temp, uint32_t &raw_press, uint32_t &raw_hum);
  void _read_compensated_data(float &temp, float &pressure, float &humidity);

  int16_t _to_signed(int16_t value, uint8_t bits);
};

#endif
