#ifndef MQ135_H
#define MQ135_H

#include <Arduino.h>
#include <stdint.h>
#include <math.h>

struct MQ135Readings {
  int raw_adc;
  float voltage_v;
  float resistance_ohm;
  float ratio_rs_r0;
  float co2_ppm;
  float nh3_ppm;
  float alcohol_ppm;
  const char* air_quality_status;
  int air_quality_index;
  float r_zero_ohm;
};

class MQ135 {
public:
  MQ135(int adcPin, float rZero, float rLoad = 10000.0);

  float read_voltage();
  float read_resistance();
  float read_ratio();
  float read_co2_ppm();
  float read_nh3_ppm();
  float read_alcohol_ppm();

  MQ135Readings get_all_readings();
  MQ135Readings get_compensated_readings(float temp_c, float humidity_percent);

  void auto_calibrate(float temp_c, float humidity_percent, float assumed_co2_ppm);
  bool is_calibrated() const;

  const char* get_air_quality_status(float co2_ppm) const;
  int get_air_quality_index(float co2_ppm) const;

  bool is_present() const;

  float get_r_zero() const { return r_zero; }
  float get_cal_temp() const { return cal_temp_c; }
  float get_cal_humidity() const { return cal_humidity; }

private:
  int adcPin;
  float r_load;
  float r_zero;

  // Calibration context
  float cal_r_zero;
  float cal_temp_c;
  float cal_humidity;
  bool calibrated;

  float _calculate_co2_ppm(float ratio) const;
  float _calculate_nh3_ppm(float ratio) const;
  float _calculate_alcohol_ppm(float ratio) const;
  float _compensate_ratio(float ratio, float temp_c, float humidity_percent) const;
};

#endif