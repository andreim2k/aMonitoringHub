#ifndef MQ135_H
#define MQ135_H

#include <Arduino.h>
#include <stdint.h>

class MQ135 {
public:
  MQ135(int adcPin, float rZero = 42304.5, float rLoad = 10000.0);

  float read_voltage();
  float read_resistance();
  float read_ratio();
  float read_co2_ppm();
  float read_nh3_ppm();
  float read_alcohol_ppm();

  const char* get_air_quality_status(float co2_ppm);
  int get_air_quality_index(float co2_ppm);

private:
  int adcPin;
  float r_load;
  float r_zero;

  float _calculate_co2_ppm(float ratio);
  float _calculate_nh3_ppm(float ratio);
  float _calculate_alcohol_ppm(float ratio);
};

#endif
