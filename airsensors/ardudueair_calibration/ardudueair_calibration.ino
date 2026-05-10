#include <Wire.h>
#include "Config.h"
#include "MQ135.h"

MQ135 *mq135 = NULL;
unsigned long sample_count = 0;
float voltage_sum = 0;
float resistance_sum = 0;

void setup() {
  SerialUSB.begin(115200);
  analogReadResolution(12);
  delay(2000);

  SerialUSB.println("\n\n=== MQ135 CALIBRATION FIRMWARE ===");
  SerialUSB.println("Location: 650m altitude, mountain air (CLEAN)");
  SerialUSB.println("Let sensor warm up for 30-60 minutes");
  SerialUSB.println("Then note the STABLE resistance reading\n");

  mq135 = new MQ135(MQ135_PIN, MQ135_R_ZERO, MQ135_R_LOAD);
  if (mq135 == NULL) {
    SerialUSB.println("ERROR: Failed to initialize MQ135!");
    while (1);
  }

  SerialUSB.println("Sensor initialized. Starting warm-up...\n");
}

void loop() {
  float voltage = mq135->read_voltage();
  float resistance = mq135->read_resistance();
  float ratio = mq135->read_ratio();

  voltage_sum += voltage;
  resistance_sum += resistance;
  sample_count++;

  // Every 10 samples (~50 seconds), print stats
  if (sample_count % 10 == 0) {
    float avg_voltage = voltage_sum / sample_count;
    float avg_resistance = resistance_sum / sample_count;

    SerialUSB.print("Sample #");
    SerialUSB.print(sample_count);
    SerialUSB.print(" | V=");
    SerialUSB.print(avg_voltage, 3);
    SerialUSB.print("V | R=");
    SerialUSB.print(avg_resistance, 1);
    SerialUSB.print("Ω | Rs/R0=");
    SerialUSB.println(ratio, 3);
  }

  delay(5000); // Read every 5 seconds
}
