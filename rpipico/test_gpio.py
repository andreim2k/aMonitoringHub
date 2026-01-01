"""
Test GPIO to see if pins are working
"""
import json
import time
from machine import Pin

print(json.dumps({"test": "gpio_led"}))

try:
    # Test LED on GPIO 25
    led = Pin(25, Pin.OUT)
    for i in range(5):
        led.on()
        time.sleep(0.2)
        led.off()
        time.sleep(0.2)
    print(json.dumps({"status": "led_works", "pin": 25}))
except Exception as e:
    print(json.dumps({"status": "led_error", "error": str(e)}))

# Test GPIO 2 and 3 (I2C pins) as outputs
print(json.dumps({"test": "gpio_i2c_pins"}))
try:
    sda = Pin(2, Pin.OUT)
    scl = Pin(3, Pin.OUT)

    # Try to toggle them
    sda.on()
    scl.on()
    time.sleep(0.1)

    sda_state = sda.value()
    scl_state = scl.value()

    print(json.dumps({
        "status": "gpio_pins_controllable",
        "gpio2_state": sda_state,
        "gpio3_state": scl_state
    }))
except Exception as e:
    print(json.dumps({"status": "gpio_pins_error", "error": str(e)}))

# Now try I2C as input to check for stuck bus
print(json.dumps({"test": "check_i2c_bus_state"}))
try:
    sda_in = Pin(2, Pin.IN)
    scl_in = Pin(3, Pin.IN)

    sda_read = sda_in.value()
    scl_read = scl_in.value()

    print(json.dumps({
        "status": "i2c_bus_state",
        "sda_pulled_high": sda_read == 1,
        "scl_pulled_high": scl_read == 1,
        "sda_value": sda_read,
        "scl_value": scl_read
    }))
except Exception as e:
    print(json.dumps({"status": "bus_state_error", "error": str(e)}))
