#include "MQ135.h"
#include "Config.h"

MQ135::MQ135(int adcPin, float rZero, float rLoad)
    : adcPin(adcPin), r_load(rLoad), r_zero(rZero),
      cal_r_zero(rZero), cal_temp_c(20.0f), cal_humidity(50.0f), calibrated(false) {
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

const char* MQ135::get_air_quality_status(float co2_ppm) const {
  if (co2_ppm < AQ_EXCELLENT) return "Excellent";
  if (co2_ppm < AQ_GOOD) return "Good";
  if (co2_ppm < AQ_FAIR) return "Fair";
  if (co2_ppm < AQ_POOR) return "Poor";
  if (co2_ppm < AQ_VERY_POOR) return "Very Poor";
  return "Hazardous";
}

int MQ135::get_air_quality_index(float co2_ppm) const {
  if (co2_ppm < AQ_EXCELLENT) return 1;
  if (co2_ppm < AQ_GOOD) return 2;
  if (co2_ppm < AQ_FAIR) return 3;
  if (co2_ppm < AQ_POOR) return 4;
  if (co2_ppm < AQ_VERY_POOR) return 5;
  return 6;
}

float MQ135::_calculate_co2_ppm(float ratio) const {
  if (ratio < EPSILON) return 0;
  float ppm = MQ135_CO2_A * pow(ratio, MQ135_CO2_B);
  return max(0.0f, min(MQ135_CO2_MAX, ppm));
}

float MQ135::_calculate_nh3_ppm(float ratio) const {
  if (ratio < EPSILON) return 0;
  float ppm = MQ135_NH3_A * pow(ratio, MQ135_NH3_B);
  return max(0.0f, min(MQ135_NH3_MAX, ppm));
}

float MQ135::_calculate_alcohol_ppm(float ratio) const {
  if (ratio < EPSILON) return 0;
  float ppm = MQ135_ALCOHOL_A * pow(ratio, MQ135_ALCOHOL_B);
  return max(0.0f, min(MQ135_ALCOHOL_MAX, ppm));
}

float MQ135::_compensate_ratio(float ratio, float temp_c, float humidity_percent) const {
  if (!calibrated) return ratio;
  // Empirical T/RH compensation relative to calibration baseline.
  // Resistance drifts ~2%/°C and ~1.5%/%RH from baseline.
  float temp_factor = 1.0f - 0.02f * (temp_c - cal_temp_c);
  float hum_factor  = 1.0f - 0.015f * (humidity_percent - cal_humidity);
  float factor = temp_factor * hum_factor;
  if (fabs(factor) < EPSILON) return ratio;
  return ratio / factor;
}

MQ135Readings MQ135::get_all_readings() {
  MQ135Readings r;
  r.raw_adc = analogRead(adcPin);
  r.voltage_v = (r.raw_adc / (float)ADC_MAX_VALUE) * VOLTAGE_REFERENCE;
  if (r.voltage_v < MIN_VOLTAGE_THRESHOLD + EPSILON) {
    r.resistance_ohm = INFINITY;
    r.ratio_rs_r0 = 0;
  } else {
    r.resistance_ohm = ((VOLTAGE_REFERENCE - r.voltage_v) / r.voltage_v) * r_load;
    r.ratio_rs_r0 = (fabs(r_zero) < EPSILON) ? 0 : r.resistance_ohm / r_zero;
  }
  r.co2_ppm = _calculate_co2_ppm(r.ratio_rs_r0);
  r.nh3_ppm = _calculate_nh3_ppm(r.ratio_rs_r0);
  r.alcohol_ppm = _calculate_alcohol_ppm(r.ratio_rs_r0);
  r.air_quality_status = get_air_quality_status(r.co2_ppm);
  r.air_quality_index = get_air_quality_index(r.co2_ppm);
  r.r_zero_ohm = r_zero;
  return r;
}

MQ135Readings MQ135::get_compensated_readings(float temp_c, float humidity_percent) {
  MQ135Readings r = get_all_readings();
  if (!calibrated) return r;

  float compensated_ratio = _compensate_ratio(r.ratio_rs_r0, temp_c, humidity_percent);
  r.ratio_rs_r0 = compensated_ratio;
  r.co2_ppm = _calculate_co2_ppm(compensated_ratio);
  r.nh3_ppm = _calculate_nh3_ppm(compensated_ratio);
  r.alcohol_ppm = _calculate_alcohol_ppm(compensated_ratio);
  r.air_quality_status = get_air_quality_status(r.co2_ppm);
  r.air_quality_index = get_air_quality_index(r.co2_ppm);
  return r;
}

void MQ135::auto_calibrate(float temp_c, float humidity_percent, float assumed_co2_ppm) {
  if (assumed_co2_ppm < EPSILON || assumed_co2_ppm > MQ135_CO2_MAX) return;

  // Average multiple readings for a stable baseline
  float resistance_sum = 0;
  int valid_samples = 0;
  for (int i = 0; i < MQ135_CALIBRATION_SAMPLES; i++) {
    float r = read_resistance();
    if (!isinf(r) && r >= EPSILON) {
      resistance_sum += r;
      valid_samples++;
    }
    delay(MQ135_CALIBRATION_SAMPLE_DELAY_MS);
  }
  if (valid_samples == 0) return;
  float resistance = resistance_sum / valid_samples;

  // Inverse of: ppm = A * ratio^B  =>  ratio = (ppm / A)^(1/B)
  float target_ratio = pow(assumed_co2_ppm / MQ135_CO2_A, 1.0f / MQ135_CO2_B);
  if (target_ratio < EPSILON) return;

  cal_r_zero = resistance / target_ratio;
  cal_temp_c = temp_c;
  cal_humidity = humidity_percent;
  r_zero = cal_r_zero;
  calibrated = true;
}

bool MQ135::is_calibrated() const {
  return calibrated;
}

bool MQ135::is_present() const {
  // A floating or disconnected pin reads near 0V or rail; a connected MQ135
  // pulls the analog pin into a mid-range voltage. Average 5 reads for stability.
  long sum = 0;
  for (int i = 0; i < 5; i++) {
    sum += analogRead(adcPin);
    delay(10);
  }
  float voltage = (sum / 5.0f / ADC_MAX_VALUE) * VOLTAGE_REFERENCE;
  return voltage > 0.05f && voltage < (VOLTAGE_REFERENCE - 0.05f);
}
