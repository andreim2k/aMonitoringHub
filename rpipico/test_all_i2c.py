"""
Test all possible I2C configurations to find where BME280 is
"""
import json
import time
from machine import Pin, I2C

configs = [
    {"bus": 0, "sda": 16, "scl": 17, "name": "I2C0: GP16(SDA) GP17(SCL)"},
    {"bus": 0, "sda": 17, "scl": 16, "name": "I2C0: GP17(SDA) GP16(SCL) [SWAPPED]"},
    {"bus": 1, "sda": 2, "scl": 3, "name": "I2C1: GP2(SDA) GP3(SCL)"},
    {"bus": 1, "sda": 6, "scl": 7, "name": "I2C1: GP6(SDA) GP7(SCL)"},
]

for config in configs:
    print(json.dumps({"testing": config["name"]}))
    try:
        i2c = I2C(config["bus"], sda=Pin(config["sda"]), scl=Pin(config["scl"]), freq=400000)
        time.sleep(0.1)
        devices = i2c.scan()

        if devices:
            print(json.dumps({
                "config": config["name"],
                "result": "FOUND DEVICES",
                "addresses": [f"0x{d:02X}" for d in devices]
            }))
            # Check if BME280 (0x76 or 0x77)
            for addr in [0x76, 0x77]:
                if addr in devices:
                    try:
                        chip_id = i2c.readfrom_mem(addr, 0xD0, 1)[0]
                        print(json.dumps({
                            "address": f"0x{addr:02X}",
                            "chip_id": f"0x{chip_id:02X}",
                            "is_bme280": chip_id == 0x60
                        }))
                    except:
                        pass
        else:
            print(json.dumps({
                "config": config["name"],
                "result": "No devices"
            }))
    except Exception as e:
        print(json.dumps({
            "config": config["name"],
            "error": str(e)
        }))
    print()
