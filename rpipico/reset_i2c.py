"""
I2C Bus Recovery - Try to reset a stuck I2C bus
"""
import json
import time
from machine import Pin, I2C

print(json.dumps({"status": "starting_i2c_reset"}))

# Step 1: Try to manually reset I2C lines
print(json.dumps({"step": "1_manual_reset"}))
try:
    sda = Pin(2, Pin.OUT, Pin.PULL_UP)
    scl = Pin(3, Pin.OUT, Pin.PULL_UP)

    # Release lines (set high)
    sda.on()
    scl.on()
    time.sleep(0.1)

    print(json.dumps({"status": "lines_released"}))

    # Try clock pulse to clear stuck slave
    for i in range(10):
        scl.off()
        time.sleep(0.01)
        scl.on()
        time.sleep(0.01)

    print(json.dumps({"status": "clock_pulses_done"}))
    time.sleep(0.2)
except Exception as e:
    print(json.dumps({"status": "manual_reset_error", "error": str(e)}))

# Step 2: Try to create new I2C with lower frequency
print(json.dumps({"step": "2_create_i2c_low_freq"}))
try:
    i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=100000)  # 100kHz instead of 400kHz
    time.sleep(0.1)
    devices = i2c.scan()
    print(json.dumps({
        "status": "i2c_scan_low_freq",
        "devices_found": len(devices),
        "addresses": [f"0x{d:02X}" for d in devices]
    }))
except Exception as e:
    print(json.dumps({"status": "i2c_low_freq_error", "error": str(e)}))

# Step 3: Try with default frequency again
print(json.dumps({"step": "3_create_i2c_default_freq"}))
try:
    i2c = I2C(1, sda=Pin(2), scl=Pin(3), freq=400000)
    time.sleep(0.1)
    devices = i2c.scan()
    print(json.dumps({
        "status": "i2c_scan_default_freq",
        "devices_found": len(devices),
        "addresses": [f"0x{d:02X}" for d in devices]
    }))
except Exception as e:
    print(json.dumps({"status": "i2c_default_freq_error", "error": str(e)}))

print(json.dumps({"status": "reset_complete"}))
print("\nTry running diagnose_bme280.py again")
