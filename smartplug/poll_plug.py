import json
import time
import sys
from pathlib import Path

import tinytuya

DEVICE_ID = "bff469d209baf7cb01sjqu"
DEVICE_IP = "192.168.50.105"
PROTOCOL_VERSION = 3.5

# This T34-Smart Plug+ unit reports energy data on DPS 21/22/23 (confirmed via
# raw status dump - 23 reads ~230V, matching EU mains).
# Units: current in mA, power in 0.1 W, voltage in 0.1 V.
DPS_CURRENT = "21"
DPS_POWER = "22"
DPS_VOLTAGE = "23"

DEVICES_FILE = Path(__file__).parent / "devices.json"


def load_local_key() -> str:
    if not DEVICES_FILE.exists():
        sys.exit(
            f"{DEVICES_FILE.name} not found. Run 'tinytuya wizard' first to pull "
            "the local_key for your devices."
        )
    devices = json.loads(DEVICES_FILE.read_text())
    for d in devices:
        if d.get("id") == DEVICE_ID:
            return d["key"]
    sys.exit(f"Device {DEVICE_ID} not found in {DEVICES_FILE.name}.")


def main():
    local_key = load_local_key()
    plug = tinytuya.OutletDevice(DEVICE_ID, DEVICE_IP, local_key, version=PROTOCOL_VERSION)

    print(f"Polling {DEVICE_IP} every 3s. Ctrl+C to stop.\n")
    while True:
        status = plug.status()
        dps = status.get("dps", {})

        if DPS_CURRENT in dps or DPS_POWER in dps or DPS_VOLTAGE in dps:
            amps = dps.get(DPS_CURRENT, 0) / 1000
            watts = dps.get(DPS_POWER, 0) / 10
            volts = dps.get(DPS_VOLTAGE, 0) / 10
            print(f"{time.strftime('%H:%M:%S')}  {volts:6.1f} V   {amps:6.3f} A   {watts:7.1f} W")
        else:
            print(f"{time.strftime('%H:%M:%S')}  raw dps: {dps}")

        time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
