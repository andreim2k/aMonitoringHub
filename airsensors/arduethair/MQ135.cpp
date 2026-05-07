#include "MQ135.h"
#include "Config.h"

#define EPSILON 1e-6

MQ135::MQ135(int adcPin, float rZero, float rLoad)
    : adcPin(adcPin), r_load(rLoad), r_zero(rZero) {
  pinMode(adcPin, INPUT);
}

float MQ135::read_voltage() {
  int raw = analogRead(adcPin);
  float voltage = (raw / (float)ADC_MAX_VALUE) * VOLTAGE_REFERENCE;
  return voltage;
}

float MQ135::read_resistance() {
  float voltage = read_voltage();
  if (voltage < MIN_VOLTAGE_THRESHOLD + EPSILON) {
    return INFINITY;
  }
  float resistance = ((VOLTAGE_REFERENCE - voltage) / voltage) * r_load;
  return resistance;
}

float MQ135::read_ratio() {
  float resistance = read_resistance();
  if (isinf(resistance) || fabs(r_zero) < EPSILON) {
    return 0;
  }
  return resistance / r_zero;
}

float MQ135::read_co2_ppm() {
  float ratio = read_ratio();
  return _calculate_co2_ppm(ratio);
}

float MQ135::read_nh3_ppm() {
  float ratio = read_ratio();
  return _calculate_nh3_ppm(ratio);
}

float MQ135::read_alcohol_ppm() {
  float ratio = read_ratio();
  return _calculate_alcohol_ppm(ratio);
}

const char* MQ135::get_air_quality_status(float co2_ppm) {
  if (co2_ppm < AQ_EXCELLENT) return "Excellent";
  if (co2_ppm < AQ_GOOD) return "Good";
  if (co2_ppm < AQ_FAIR) return "Fair";
  if (co2_ppm < AQ_POOR) return "Poor";
  if (co2_ppm < AQ_VERY_POOR) return "Very Poor";
  return "Hazardous";
}

int MQ135::get_air_quality_index(float co2_ppm) {
  if (co2_ppm < AQ_EXCELLENT) return 1;
  if (co2_ppm < AQ_GOOD) return 2;
  if (co2_ppm < AQ_FAIR) return 3;
  if (co2_ppm < AQ_POOR) return 4;
  if (co2_ppm < AQ_VERY_POOR) return 5;
  return 6;
}

float MQ135::_calculate_co2_ppm(float ratio) {
  if (ratio < EPSILON) return 0;
  float ppm = MQ135_CO2_A * pow(ratio, MQ135_CO2_B);
  return max(0.0f, min(MQ135_CO2_MAX, ppm));
}

float MQ135::_calculate_nh3_ppm(float ratio) {
  if (ratio < EPSILON) return 0;
  float ppm = MQ135_NH3_A * pow(ratio, MQ135_NH3_B);
  return max(0.0f, min(MQ135_NH3_MAX, ppm));
}

float MQ135::_calculate_alcohol_ppm(float ratio) {
  if (ratio < EPSILON) return 0;
  float ppm = MQ135_ALCOHOL_A * pow(ratio, MQ135_ALCOHOL_B);
  return max(0.0f, min(MQ135_ALCOHOL_MAX, ppm));
}
