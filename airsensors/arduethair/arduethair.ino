#include <Wire.h>
#include <SPI.h>
#include <Ethernet.h>
#include <EthernetUDP.h>
#include "Config.h"
#include "BME280_I2C.h"
#include "MQ135.h"

BME280_I2C *bm280 = NULL;
MQ135 *mq135 = NULL;
EthernetUDP udp;
IPAddress serverIP = SERVER_IP;
unsigned long boot_timestamp_ms = 0;
bool bm280_available = false;
bool mq135_available = false;
int led_pin = LED_PIN;

unsigned long bm280_retry_interval_ms = BM280_RUNTIME_RETRY_INTERVAL_MS;
unsigned long last_bm280_init_attempt_ms = 0;

void blink_pattern(int count, int duration_ms = 100, int pause_ms = 150);
void blink_error(int duration_ms = 200);
void print_json(Print &out, float ts, float ts_boot,
                bool bm280_ok, float temp, float press, float humid,
                bool mq135_ok, int raw_adc, float voltage, float resistance,
                float ratio, float co2, float nh3, float alcohol,
                const char* aq_status, int aqi);

void setup() {
  Serial.begin(115200);
  pinMode(led_pin, OUTPUT);
  digitalWrite(led_pin, LOW);

  boot_timestamp_ms = millis();
  delay(BOOT_DELAY_MS);

  Serial.println(F("{\"timestamp\":0,\"status\":\"starting\",\"message\":\"Auto-starting JSON sensor monitoring...\"}"));

  Wire.begin();

  // Initialize Ethernet with DHCP, fallback to static IP
  if (Ethernet.begin(ETHERNET_MAC) == 0) {
    Serial.println(F("{\"timestamp\":0,\"status\":\"warning\",\"message\":\"DHCP failed, using static IP\"}"));
    Ethernet.begin(ETHERNET_MAC, STATIC_IP);
  }

  // Start UDP socket
  udp.begin(LOCAL_PORT);
  serverIP = SERVER_IP;

  delay(1000);

  Serial.print(F("{\"timestamp\":"));
  Serial.print(millis() / 1000.0, 3);
  Serial.print(F(",\"status\":\"ethernet_initialized\",\"local_ip\":\""));
  Serial.print(Ethernet.localIP());
  Serial.println(F("\"}"));

  bm280 = new BME280_I2C(BME280_I2C_ADDR);
  if (bm280 != NULL && bm280->getChipId() != 0) {
    bm280_available = true;
    Serial.print(F("{\"timestamp\":"));
    Serial.print(millis() / 1000.0, 3);
    Serial.println(F(",\"status\":\"bm280_initialized\",\"interface\":\"I2C\"}"));
  } else {
    bm280_available = false;
    Serial.print(F("{\"timestamp\":"));
    Serial.print(millis() / 1000.0, 3);
    Serial.println(F(",\"status\":\"warning\",\"message\":\"BME280 unavailable - will send MQ135 data only\"}"));
  }

  mq135 = new MQ135(MQ135_PIN, MQ135_R_ZERO, MQ135_R_LOAD);
  if (mq135 != NULL) {
    mq135_available = true;
    Serial.print(F("{\"timestamp\":"));
    Serial.print(millis() / 1000.0, 3);
    Serial.print(F(",\"status\":\"mq135_initialized\",\"pin\":"));
    Serial.print(MQ135_PIN);
    Serial.print(F(",\"r_zero\":"));
    Serial.print(MQ135_R_ZERO);
    Serial.print(F(",\"r_load\":"));
    Serial.print(MQ135_R_LOAD);
    Serial.println(F("}"));
  } else {
    Serial.print(F("{\"timestamp\":"));
    Serial.print(millis() / 1000.0, 3);
    Serial.println(F(",\"status\":\"error\",\"error\":\"MQ135 initialization failed\"}"));
    while (1);
  }

  if (!bm280_available && !mq135_available) {
    Serial.print(F("{\"timestamp\":"));
    Serial.print(millis() / 1000.0, 3);
    Serial.println(F(",\"status\":\"error\",\"error\":\"No sensors available\"}"));
    blink_error();
    while (1);
  }

  delay(500);
  if (bm280_available && mq135_available) {
    Serial.print(F("{\"timestamp\":"));
    Serial.print(millis() / 1000.0, 3);
    Serial.println(F(",\"status\":\"diagnostic\",\"message\":\"Both sensors available (3 blinks)\"}"));
    blink_pattern(3);
  } else if (bm280_available) {
    Serial.print(F("{\"timestamp\":"));
    Serial.print(millis() / 1000.0, 3);
    Serial.println(F(",\"status\":\"diagnostic\",\"message\":\"Only BME280 available (1 blink)\"}"));
    blink_pattern(1);
  } else {
    Serial.print(F("{\"timestamp\":"));
    Serial.print(millis() / 1000.0, 3);
    Serial.println(F(",\"status\":\"diagnostic\",\"message\":\"Only MQ135 available (2 blinks)\"}"));
    blink_pattern(2);
  }

  Serial.print(F("{\"timestamp\":"));
  Serial.print(millis() / 1000.0, 3);
  Serial.print(F(",\"status\":\"monitoring_started\",\"message\":\"Starting continuous JSON monitoring (auto-boot)\",\"bm280_available\":"));
  Serial.print(bm280_available ? F("true") : F("false"));
  Serial.print(F(",\"mq135_available\":"));
  Serial.print(mq135_available ? F("true") : F("false"));
  Serial.println(F("}"));
}

void loop() {
  Ethernet.maintain();

  unsigned long timestamp_ms = millis();
  float timestamp = timestamp_ms / 1000.0;
  float timestamp_since_boot = (timestamp_ms - boot_timestamp_ms) / 1000.0;

  bool bm280_read_ok = false;
  bool mq135_read_ok = false;

  if (!bm280_available) {
    if (timestamp_ms - last_bm280_init_attempt_ms >= bm280_retry_interval_ms) {
      last_bm280_init_attempt_ms = timestamp_ms;
      Serial.print(F("{\"timestamp\":"));
      Serial.print(timestamp, 3);
      Serial.println(F(",\"status\":\"bm280_reconnect_attempt\",\"message\":\"Attempting to reinitialize BME280\"}"));
      bm280 = new BME280_I2C(BME280_I2C_ADDR);
      if (bm280 != NULL && bm280->getChipId() != 0) {
        bm280_available = true;
        Serial.print(F("{\"timestamp\":"));
        Serial.print(timestamp, 3);
        Serial.println(F(",\"status\":\"recovered\",\"sensor\":\"bm280\",\"method\":\"runtime_reconnect\"}"));
      }
    }
  }

  float temp = 0, press = 0, humid = 0;
  if (bm280_available && bm280 != NULL) {
    bm280->read_compensated_data(temp, press, humid);
    bm280_read_ok = true;
  }

  float voltage = 0, resistance = 0, ratio = 0;
  float co2_ppm = 0, nh3_ppm = 0, alcohol_ppm = 0;
  int raw_adc = 0;
  const char* aq_status = "Unknown";
  int aqi = 0;

  if (mq135_available && mq135 != NULL) {
    voltage = mq135->read_voltage();
    resistance = mq135->read_resistance();
    ratio = mq135->read_ratio();
    co2_ppm = mq135->read_co2_ppm();
    nh3_ppm = mq135->read_nh3_ppm();
    alcohol_ppm = mq135->read_alcohol_ppm();
    raw_adc = analogRead(MQ135_PIN);
    aq_status = mq135->get_air_quality_status(co2_ppm);
    aqi = mq135->get_air_quality_index(co2_ppm);
    mq135_read_ok = true;
  }

  // Send JSON via UDP
  udp.beginPacket(serverIP, SERVER_PORT);
  print_json(udp, timestamp, timestamp_since_boot,
             bm280_read_ok, temp, press, humid,
             mq135_read_ok, raw_adc, voltage, resistance,
             ratio, co2_ppm, nh3_ppm, alcohol_ppm,
             aq_status, aqi);
  udp.endPacket();

  // Echo to Serial for debugging
  print_json(Serial, timestamp, timestamp_since_boot,
             bm280_read_ok, temp, press, humid,
             mq135_read_ok, raw_adc, voltage, resistance,
             ratio, co2_ppm, nh3_ppm, alcohol_ppm,
             aq_status, aqi);

  if (bm280_read_ok && mq135_read_ok) {
    blink_pattern(3);
  } else if (bm280_read_ok) {
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
    digitalWrite(led_pin, HIGH);
    delay(duration_ms);
    digitalWrite(led_pin, LOW);
    if (i < count - 1) delay(pause_ms);
  }
}

void blink_error(int duration_ms) {
  for (int i = 0; i < 3; i++) {
    digitalWrite(led_pin, HIGH);
    delay(duration_ms);
    digitalWrite(led_pin, LOW);
    delay(duration_ms);
  }
}

void print_json(Print &out, float ts, float ts_boot,
                bool bm280_ok, float temp, float press, float humid,
                bool mq135_ok, int raw_adc, float voltage, float resistance,
                float ratio, float co2, float nh3, float alcohol,
                const char* aq_status, int aqi) {
  out.print(F("{\"timestamp\":"));
  out.print(ts, 3);
  out.print(F(",\"timestamp_since_boot\":"));
  out.print(ts_boot, 3);

  if (bm280_ok) {
    out.print(F(",\"bm280\":{\"temperature_c\":"));
    out.print(temp, 2);
    out.print(F(",\"humidity_percent\":"));
    out.print(humid, 1);
    out.print(F(",\"pressure_hpa\":"));
    out.print(press / 100.0, 1);
    out.print(F(",\"pressure_pa\":"));
    out.print(press, 0);
    out.print(F("}"));
  }

  if (mq135_ok) {
    out.print(F(",\"mq135\":{\"raw_adc\":"));
    out.print(raw_adc);
    out.print(F(",\"voltage_v\":"));
    out.print(voltage, 3);
    out.print(F(",\"resistance_ohm\":"));
    out.print(resistance, 1);
    out.print(F(",\"ratio_rs_r0\":"));
    out.print(ratio, 3);
    out.print(F(",\"co2_ppm\":"));
    out.print(co2, 1);
    out.print(F(",\"nh3_ppm\":"));
    out.print(nh3, 1);
    out.print(F(",\"alcohol_ppm\":"));
    out.print(alcohol, 1);
    out.print(F(",\"air_quality_status\":\""));
    out.print(aq_status);
    out.print(F("\",\"air_quality_index\":"));
    out.print(aqi);
    out.print(F(",\"r_zero_ohm\":"));
    out.print(MQ135_R_ZERO);
    out.print(F("}"));
  }

  out.println(F("}"));
}
