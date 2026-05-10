// BME280 I2C Diagnostic — Arduino Due
// Scans Wire (D20/D21) and Wire1 (pins 70/71), then probes chip ID at 0x76 and 0x77.
// Output is plain text on SerialUSB at 115200.
//
// Expected good output (BME280 wired correctly to Wire bus at default 0x77):
//   [scan] bus=Wire (D20/D21) addresses=0x77 total=1
//   [probe] bus=Wire addr=0x77 chip_id=0x60 => BME280 OK
//
// See task #3 thread for the full normal-vs-error decision table.

#include <Wire.h>

static const uint16_t SCAN_DELAY_MS = 2;
static const uint16_t LOOP_DELAY_MS = 5000;

static void scanBus(TwoWire &bus, const char *name) {
  bus.begin();
  SerialUSB.print("[scan] bus="); SerialUSB.print(name);
  SerialUSB.print(" addresses=");
  uint8_t found = 0;
  for (uint8_t addr = 0x01; addr < 0x7F; addr++) {
    bus.beginTransmission(addr);
    if (bus.endTransmission() == 0) {
      if (found++) SerialUSB.print(",");
      SerialUSB.print("0x"); SerialUSB.print(addr, HEX);
    }
    delay(SCAN_DELAY_MS);
  }
  if (!found) SerialUSB.print("(none)");
  SerialUSB.print(" total="); SerialUSB.println(found);
}

static void probeChipId(TwoWire &bus, const char *name, uint8_t addr) {
  bus.beginTransmission(addr);
  bus.write(0xD0);
  uint8_t err = bus.endTransmission(false);
  SerialUSB.print("[probe] bus="); SerialUSB.print(name);
  SerialUSB.print(" addr=0x"); SerialUSB.print(addr, HEX);
  if (err != 0) {
    SerialUSB.print(" no_ack err="); SerialUSB.println(err);
    return;
  }
  bus.requestFrom(addr, (uint8_t)1);
  if (bus.available()) {
    uint8_t id = bus.read();
    SerialUSB.print(" chip_id=0x"); SerialUSB.print(id, HEX);
    if (id == 0x60)      SerialUSB.println(" => BME280 OK");
    else if (id == 0x58) SerialUSB.println(" => BMP280 (no humidity)");
    else if (id == 0xFF || id == 0x00) SerialUSB.println(" => bus floating / dead");
    else                 SerialUSB.println(" => UNKNOWN chip");
  } else {
    SerialUSB.println(" no_data");
  }
}

void setup() {
  SerialUSB.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  delay(2000);
  SerialUSB.println();
  SerialUSB.println("BME280 diag starting (Due, 115200 baud)");
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  SerialUSB.println("---- BME280 I2C diagnostic ----");
  scanBus(Wire,  "Wire (D20/D21)");
  scanBus(Wire1, "Wire1 (pins 70/71)");
  probeChipId(Wire,  "Wire",  0x76);
  probeChipId(Wire,  "Wire",  0x77);
  probeChipId(Wire1, "Wire1", 0x76);
  probeChipId(Wire1, "Wire1", 0x77);
  SerialUSB.println("---- end ----");
  digitalWrite(LED_BUILTIN, LOW);
  delay(LOOP_DELAY_MS);
}
