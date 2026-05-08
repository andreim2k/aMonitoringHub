#include "BME280_I2C.h"
#include "Config.h"

#define BME280_CHIP_ID_HUMIDITY 0x60
#define BME280_CHIP_ID_PRESSURE_ONLY 0x58
#define BME280_STATUS_REGISTER 0xF3
#define BME280_RESET_REGISTER 0xE0
#define BME280_RESET_VALUE 0xB6

BME280_I2C::BME280_I2C(uint8_t i2cAddr)
    : i2c_addr(i2cAddr), chip_id(0), has_humidity(false) {
  uint8_t id = 0;
  if (!_read_register(0xD0, id)) {
    return;
  }
  if (id != BME280_CHIP_ID_HUMIDITY && id != BME280_CHIP_ID_PRESSURE_ONLY) {
    return;
  }

  chip_id = id;
  has_humidity = (chip_id == BME280_CHIP_ID_HUMIDITY);

  if (!reset()) {
    chip_id = 0;
    return;
  }
  if (!wait_for_ready(500)) {
    chip_id = 0;  // mark as invalid
    return;
  }

  if (!_read_calibration_data()) {
    chip_id = 0;
    return;
  }
  if (!_configure_sensor()) {
    chip_id = 0;
    return;
  }
}

bool BME280_I2C::_read_register(uint8_t reg, uint8_t &out) {
  Wire.beginTransmission(i2c_addr);
  Wire.write(reg);
  if (Wire.endTransmission() != 0) return false;

  if (Wire.requestFrom(i2c_addr, (uint8_t)1) != 1) return false;
  out = Wire.read();
  return true;
}

bool BME280_I2C::_read_registers(uint8_t reg, uint8_t count, uint8_t *buf) {
  Wire.beginTransmission(i2c_addr);
  Wire.write(reg);
  if (Wire.endTransmission() != 0) return false;

  if (Wire.requestFrom(i2c_addr, count) != count) return false;
  for (uint8_t i = 0; i < count; i++) {
    buf[i] = Wire.read();
  }
  return true;
}

bool BME280_I2C::_write_register(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(i2c_addr);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool BME280_I2C::_read_calibration_data() {
  uint8_t calib[24];
  if (!_read_registers(0x88, 24, calib)) return false;

  dig_T1 = (calib[1] << 8) | calib[0];
  dig_T2 = (int16_t)((calib[3] << 8) | calib[2]);
  dig_T3 = (int16_t)((calib[5] << 8) | calib[4]);

  dig_P1 = (calib[7] << 8) | calib[6];
  dig_P2 = (int16_t)((calib[9] << 8) | calib[8]);
  dig_P3 = (int16_t)((calib[11] << 8) | calib[10]);
  dig_P4 = (int16_t)((calib[13] << 8) | calib[12]);
  dig_P5 = (int16_t)((calib[15] << 8) | calib[14]);
  dig_P6 = (int16_t)((calib[17] << 8) | calib[16]);
  dig_P7 = (int16_t)((calib[19] << 8) | calib[18]);
  dig_P8 = (int16_t)((calib[21] << 8) | calib[20]);
  dig_P9 = (int16_t)((calib[23] << 8) | calib[22]);

  if (has_humidity) {
    if (!_read_register(0xA1, dig_H1)) return false;
    uint8_t calib2[7];
    if (!_read_registers(0xE1, 7, calib2)) return false;
    dig_H2 = (int16_t)((calib2[1] << 8) | calib2[0]);
    dig_H3 = calib2[2];
    dig_H4 = _to_signed((calib2[3] << 4) | (calib2[4] & 0x0F), 12);
    dig_H5 = _to_signed((calib2[5] << 4) | (calib2[4] >> 4), 12);
    dig_H6 = _to_signed(calib2[6], 8);
  }
  return true;
}

bool BME280_I2C::_configure_sensor() {
  if (has_humidity) {
    if (!_write_register(0xF2, 0x01)) return false;  // Humidity x1 oversample
  }
  if (!_write_register(0xF4, 0x27)) return false;    // Temp x1, Press x1, normal mode
  if (!_write_register(0xF5, 0x20)) return false;    // Standby 62.5ms, filter off
  return true;
}

bool BME280_I2C::reset() {
  if (!_write_register(BME280_RESET_REGISTER, BME280_RESET_VALUE)) return false;
  delay(3);
  return true;
}

void BME280_I2C::reconfigure() {
  _configure_sensor();
}

uint8_t BME280_I2C::check_status() {
  uint8_t status = 0xFF;
  _read_register(BME280_STATUS_REGISTER, status);
  return status;
}

bool BME280_I2C::is_ready() {
  uint8_t status = check_status();
  uint8_t measuring = (status >> 3) & 0x01;
  uint8_t im_update = status & 0x01;
  return measuring == 0 && im_update == 0;
}

bool BME280_I2C::wait_for_ready(unsigned long timeoutMs) {
  unsigned long start = millis();
  while (millis() - start < timeoutMs) {
    if (is_ready()) return true;
    delay(10);
  }
  return false;
}

bool BME280_I2C::_read_raw_data(uint32_t &raw_temp, uint32_t &raw_press, uint32_t &raw_hum) {
  if (!wait_for_ready()) {
    return false;
  }

  uint8_t data_len = has_humidity ? 8 : 6;
  uint8_t data[8];
  if (!_read_registers(0xF7, data_len, data)) return false;

  raw_press = ((uint32_t)data[0] << 12) | ((uint32_t)data[1] << 4) | (data[2] >> 4);
  raw_temp = ((uint32_t)data[3] << 12) | ((uint32_t)data[4] << 4) | (data[5] >> 4);

  if (has_humidity) {
    raw_hum = ((uint32_t)data[6] << 8) | data[7];
  } else {
    raw_hum = 0;
  }
  return true;
}

bool BME280_I2C::read_compensated_data(float &temp, float &pressure, float &humidity) {
  uint32_t raw_temp, raw_press, raw_hum;
  if (!_read_raw_data(raw_temp, raw_press, raw_hum)) return false;

  // Temperature compensation
  float var1 = (raw_temp / 16384.0 - dig_T1 / 1024.0) * dig_T2;
  float var2 = ((raw_temp / 131072.0 - dig_T1 / 8192.0) * (raw_temp / 131072.0 - dig_T1 / 8192.0)) * dig_T3;
  int32_t t_fine = (int32_t)(var1 + var2);
  temp = (var1 + var2) / 5120.0;

  // Pressure compensation
  var1 = (t_fine / 2.0) - 64000.0;
  var2 = var1 * var1 * dig_P6 / 32768.0;
  var2 = var2 + var1 * dig_P5 * 2.0;
  var2 = (var2 / 4.0) + (dig_P4 * 65536.0);
  var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0;
  var1 = (1.0 + var1 / 32768.0) * dig_P1;

  if (fabs(var1) < EPSILON) {
    pressure = 0;
    return false;
  } else {
    pressure = 1048576.0 - raw_press;
    pressure = (pressure - (var2 / 4096.0)) * 6250.0 / var1;
    var1 = dig_P9 * pressure * pressure / 2147483648.0;
    var2 = pressure * dig_P8 / 32768.0;
    pressure = pressure + (var1 + var2 + dig_P7) / 16.0;
  }

  // Humidity compensation
  if (has_humidity) {
    float h = t_fine - 76800.0;
    h = ((raw_hum - (dig_H4 * 64.0 + dig_H5 / 16384.0 * h)) *
         (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * h *
         (1.0 + dig_H3 / 67108864.0 * h))));
    humidity = h * (1.0 - dig_H1 * h / 524288.0);

    if (humidity > 100) humidity = 100;
    else if (humidity < 0) humidity = 0;
  } else {
    humidity = 0;
  }
  return true;
}

float BME280_I2C::read_temperature() {
  float t, p, h;
  read_compensated_data(t, p, h);
  return t;
}

float BME280_I2C::read_pressure() {
  float t, p, h;
  read_compensated_data(t, p, h);
  return p;
}

float BME280_I2C::read_humidity() {
  float t, p, h;
  read_compensated_data(t, p, h);
  return h;
}

int16_t BME280_I2C::_to_signed(int16_t value, uint8_t bits) {
  if (value & (1 << (bits - 1))) {
    return value - (1 << bits);
  }
  return value;
}
