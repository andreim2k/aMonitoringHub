#include <Wire.h>
#include "Config.h"
#include "BME280_I2C.h"
#include "MQ135.h"

BME280_I2C *bme280 = NULL;
MQ135 *mq135 = NULL;
unsigned long boot_timestamp_ms = 0;
bool bme280_available = false;
bool mq135_available = false;

unsigned long last_bme280_init_attempt_ms = 0;

void blink_pattern(int count, int duration_ms = LED_BLINK_DURATION_MS, int pause_ms = 150);
void blink_error(int duration_ms = 200);

static void ts(float t) {
  Serial.print(t, 3);
}

static void json_msg(const char* status, const char* key1 = NULL, const char* val1 = NULL,
                     const char* key2 = NULL, const char* val2 = NULL) {
  Serial.print(F("{\"timestamp\":"));
  ts(millis() / 1000.0);
  Serial.print(F(",\"status\":\""));
  Serial.print(status);
  Serial.print(F("\""));
  if (key1) {
    Serial.print(F(",\""));
    Serial.print(key1);
    Serial.print(F("\":\""));
    Serial.print(val1);
    Serial.print(F("\""));
  }
  if (key2) {
    Serial.print(F(",\""));
    Serial.print(key2);
    Serial.print(F("\":\""));
    Serial.print(val2);
    Serial.print(F("\""));
  }
  Serial.println(F("}"));
}

static void json_start(float timestamp, float since_boot) {
  Serial.print(F("{\"timestamp\":"));
  ts(timestamp);
  Serial.print(F(",\"timestamp_since_boot\":"));
  ts(since_boot);
}

static void json_field(const char* key, float value, int decimals) {
  Serial.print(F(",\""));
  Serial.print(key);
  Serial.print(F("\":"));
  Serial.print(value, decimals);
}

static void json_string(const char* key, const char* value) {
  Serial.print(F(",\""));
  Serial.print(key);
  Serial.print(F("\":\""));
  Serial.print(value);
  Serial.print(F("\""));
}

static void json_end() {
  Serial.println(F("}"));
}

void setup() {
  Serial.begin(115200);
  delay(100);  // brief settle for Programming Port UART
  analogReadResolution(12);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  boot_timestamp_ms = millis();

  delay(BOOT_DELAY_MS);

  Serial.print(F("{\"timestamp\":"));
  ts(millis() / 1000.0);
  Serial.println(F(",\"status\":\"starting\",\"message\":\"Auto-starting JSON sensor monitoring...\"}"));

  // LED initialized
  Serial.print(F("{\"timestamp\":"));
  ts(millis() / 1000.0);
  Serial.println(F(",\"status\":\"led_initialized\",\"pin\":\"13\"}"));

  Wire.begin();

  // Initialize BME280
  bme280 = new BME280_I2C(BME280_I2C_ADDR);
  if (bme280 != NULL && bme280->getChipId() != 0) {
    bme280_available = true;
    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    Serial.println(F(",\"status\":\"bme280_initialized\",\"interface\":\"I2C\"}"));
  } else {
    bme280_available = false;
    if (bme280 != NULL) {
      delete bme280;
      bme280 = NULL;
    }
    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    Serial.println(F(",\"status\":\"warning\",\"message\":\"BME280 unavailable - will send MQ135 data only\"}"));
  }

  // Initialize MQ135
  mq135 = new MQ135(MQ135_PIN, MQ135_R_ZERO, MQ135_R_LOAD);
  if (mq135 != NULL) {
    mq135_available = true;
    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    Serial.print(F(",\"status\":\"mq135_initialized\",\"pin\":"));
    Serial.print(MQ135_PIN);
    Serial.print(F(",\"r_zero\":"));
    Serial.print(MQ135_R_ZERO, 1);
    Serial.print(F(",\"r_load\":"));
    Serial.print(MQ135_R_LOAD, 0);
    Serial.println(F("}"));
  } else {
    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    if (mq135 != NULL) {
      Serial.println(F(",\"status\":\"error\",\"error\":\"MQ135 initialization failed\",\"message\":\"Check wiring on A0\"}"));
      while (1);
    } else {
      Serial.println(F(",\"status\":\"error\",\"error\":\"MQ135 initialization failed\",\"message\":\"Check wiring on A0\"}"));
      while (1);
    }
  }

  if (!bme280_available && !mq135_available) {
    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    Serial.println(F(",\"status\":\"error\",\"error\":\"No sensors available\",\"message\":\"Check all connections\"}"));
    blink_error();
    while (1);
  }

  // Auto-calibrate MQ135 in clean mountain air
  if (mq135_available) {
    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    Serial.println(F(",\"status\":\"calibrating\",\"message\":\"Waiting for MQ135 to settle before auto-calibration\"}"));
    delay(MQ135_CALIBRATION_SETTLE_MS);

    // Warm up ADC with a few dummy reads
    for (int i = 0; i < 3; i++) {
      mq135->read_voltage();
      delay(50);
    }

    float cal_temp = 20.0f, cal_humid = 50.0f;
    if (bme280_available && bme280 != NULL) {
      float temp, press, humid;
      bool bme_ok = false;
      for (int attempt = 0; attempt < 5; attempt++) {
        if (bme280->read_compensated_data(temp, press, humid)) {
          cal_temp = temp;
          cal_humid = humid;
          bme_ok = true;
          break;
        }
        delay(100);
      }
      if (!bme_ok) {
        Serial.print(F("{\"timestamp\":"));
        ts(millis() / 1000.0);
        Serial.println(F(",\"status\":\"warning\",\"message\":\"BME280 read failed during calibration, using default T/H\"}"));
      }
    }

    mq135->auto_calibrate(cal_temp, cal_humid, MQ135_ASSUMED_CLEAN_AIR_CO2_PPM);

    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    Serial.print(F(",\"status\":\"calibrated\",\"sensor\":\"mq135\",\"r_zero\":"));
    Serial.print(mq135->get_r_zero(), 1);
    Serial.print(F(",\"cal_temp_c\":"));
    Serial.print(mq135->get_cal_temp(), 1);
    Serial.print(F(",\"cal_humidity_percent\":"));
    Serial.print(mq135->get_cal_humidity(), 1);
    Serial.print(F(",\"assumed_co2_ppm\":"));
    Serial.print(MQ135_ASSUMED_CLEAN_AIR_CO2_PPM, 0);
    Serial.println(F("}"));
  }

  // Diagnostic blink: 1=BME only, 2=MQ only, 3=both
  delay(500);
  if (bme280_available && mq135_available) {
    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    Serial.println(F(",\"status\":\"diagnostic\",\"message\":\"Both sensors available (3 blinks)\"}"));
    blink_pattern(3);
  } else if (bme280_available) {
    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    Serial.println(F(",\"status\":\"diagnostic\",\"message\":\"Only BME280 available (1 blink)\"}"));
    blink_pattern(1);
  } else {
    Serial.print(F("{\"timestamp\":"));
    ts(millis() / 1000.0);
    Serial.println(F(",\"status\":\"diagnostic\",\"message\":\"Only MQ135 available (2 blinks)\"}"));
    blink_pattern(2);
  }

  Serial.print(F("{\"timestamp\":"));
  ts(millis() / 1000.0);
  Serial.print(F(",\"status\":\"monitoring_started\",\"message\":\"Starting continuous JSON monitoring (auto-boot)\",\"bme280_available\":"));
  Serial.print(bme280_available ? F("true") : F("false"));
  Serial.print(F(",\"mq135_available\":"));
  Serial.print(mq135_available ? F("true") : F("false"));
  Serial.println(F(",\"note\":\"Reset board to restart\"}"));
}

void loop() {
  unsigned long now_ms = millis();
  float timestamp = now_ms / 1000.0;
  float timestamp_since_boot = (now_ms - boot_timestamp_ms) / 1000.0;

  bool bme280_read_ok = false;
  bool mq135_read_ok = false;

  // Periodic BME280 reconnect if unavailable
  if (!bme280_available) {
    if (now_ms - last_bme280_init_attempt_ms >= BME280_RUNTIME_RETRY_INTERVAL_MS) {
      last_bme280_init_attempt_ms = now_ms;
      Serial.print(F("{\"timestamp\":"));
      ts(timestamp);
      Serial.println(F(",\"status\":\"bme280_reconnect_attempt\",\"message\":\"Attempting to reinitialize BME280\"}"));
      if (bme280 != NULL) delete bme280;
      bme280 = new BME280_I2C(BME280_I2C_ADDR);
      if (bme280 != NULL && bme280->getChipId() != 0) {
        bme280_available = true;
        Serial.print(F("{\"timestamp\":"));
        ts(timestamp);
        Serial.println(F(",\"status\":\"recovered\",\"sensor\":\"bme280\",\"method\":\"runtime_reconnect\"}"));
      }
    }
  }

  // Build sensor JSON
  json_start(timestamp, timestamp_since_boot);

  float current_temp = 20.0f;
  float current_humid = 50.0f;

  // Read BME280
  if (bme280_available && bme280 != NULL) {
    float temp, press, humid;
    if (bme280->read_compensated_data(temp, press, humid)) {
      current_temp = temp;
      current_humid = humid;
      Serial.print(F(",\"bme280\":{\"temperature_c\":"));
      Serial.print(temp, 2);
      Serial.print(F(",\"humidity_percent\":"));
      Serial.print(humid, 1);
      Serial.print(F(",\"pressure_hpa\":"));
      Serial.print(press / 100.0, 1);
      Serial.print(F(",\"pressure_pa\":"));
      Serial.print((unsigned long)round(press));
      Serial.print(F(".0}"));
      bme280_read_ok = true;
    } else {
      // Read failed — attempt recovery: reset then reconfigure
      json_end();
      Serial.print(F("{\"timestamp\":"));
      ts(timestamp);
      Serial.println(F(",\"status\":\"error\",\"sensor\":\"bme280\",\"error\":\"BME280 read error\",\"attempting_recovery\":true}"));

      bool recovered = false;
      bme280->reset();
      delay(3);
      bme280->reconfigure();
      if (bme280->check_status() != 0xFF) {
        Serial.print(F("{\"timestamp\":"));
        ts(timestamp);
        Serial.println(F(",\"status\":\"recovered\",\"sensor\":\"bme280\",\"method\":\"reset\"}"));
        recovered = true;
      }
      if (!recovered) {
        bme280_available = false;
        last_bme280_init_attempt_ms = now_ms;
        Serial.print(F("{\"timestamp\":"));
        ts(timestamp);
        Serial.println(F(",\"status\":\"warning\",\"sensor\":\"bme280\",\"message\":\"BME280 unavailable after recovery attempts\"}"));
      }
      delay(SENSOR_READ_INTERVAL_MS);
      return;
    }
  }

  // Opportunistic loop calibration if boot calibration was somehow missed
  if (mq135_available && bme280_available && !mq135->is_calibrated()) {
    mq135->auto_calibrate(current_temp, current_humid, MQ135_ASSUMED_CLEAN_AIR_CO2_PPM);
  }

  // Read MQ135
  if (mq135_available && mq135 != NULL) {
    MQ135Readings m;
    if (bme280_available && mq135->is_calibrated()) {
      m = mq135->get_compensated_readings(current_temp, current_humid);
    } else {
      m = mq135->get_all_readings();
    }
    Serial.print(F(",\"mq135\":{\"raw_adc\":"));
    Serial.print(m.raw_adc);
    json_field("voltage_v", m.voltage_v, 3);
    json_field("resistance_ohm", m.resistance_ohm, 1);
    json_field("ratio_rs_r0", m.ratio_rs_r0, 3);
    json_field("co2_ppm", m.co2_ppm, 1);
    json_field("nh3_ppm", m.nh3_ppm, 1);
    json_field("alcohol_ppm", m.alcohol_ppm, 1);
    json_string("air_quality_status", m.air_quality_status);
    Serial.print(F(",\"air_quality_index\":"));
    Serial.print(m.air_quality_index);
    json_field("r_zero_ohm", m.r_zero_ohm, 1);
    Serial.print(F("}"));
    mq135_read_ok = true;
  }

  json_end();

  // LED blink: 1=BME only, 2=MQ only, 3=both, error=neither
  if (bme280_read_ok && mq135_read_ok) {
    blink_pattern(3);
  } else if (bme280_read_ok) {
    blink_pattern(1);
  } else if (mq135_read_ok) {
    blink_pattern(2);
  } else {
    blink_error();
  }

  delay(SENSOR_READ_INTERVAL_MS);
}

void blink_pattern(int count, int duration_ms, int pause_ms) {
  for (int i = 0; i < count; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(duration_ms);
    digitalWrite(LED_PIN, LOW);
    if (i < count - 1) delay(pause_ms);
  }
}

void blink_error(int duration_ms) {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(duration_ms);
    digitalWrite(LED_PIN, LOW);
    delay(duration_ms);
  }
}
