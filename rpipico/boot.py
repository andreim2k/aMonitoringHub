"""
Boot script for Raspberry Pi Pico
Runs automatically on power-up and starts the monitoring system
"""

import time
from machine import Pin

# Optional: Set up a safe boot by holding a button
# Press GP0 during boot to enter REPL-only mode (no auto-start)
try:
    boot_pin = Pin(0, Pin.IN, Pin.PULL_UP)

    # Give user 2 seconds to press the button
    time.sleep_ms(2000)

    if boot_pin.value() == 0:  # Button pressed (active low)
        print("[INFO] Safe boot mode: Auto-start disabled")
        print("[INFO] Enter REPL with Ctrl+A, or press RESET to restart normally")
    else:
        # Normal boot - import and run main.py
        print("[START] Normal boot - starting monitoring...")
        import main
except Exception as e:
    print(f"[ERROR] Boot error: {e}")
    print("[INFO] Entering REPL mode for debugging")
