"""
Boot script for Raspberry Pi Pico
Runs automatically on power-up and starts the monitoring system
"""

import machine
import time

# Optional: Set up a safe boot by holding a button
# Press GP0 during boot to enter REPL-only mode (no auto-start)
try:
    from machine import Pin
    boot_pin = Pin(0, Pin.IN, Pin.PULL_UP)

    # Give user 2 seconds to press the button
    time.sleep_ms(100)

    if boot_pin.value() == 0:  # Button pressed (active low)
        print("🔧 Safe boot mode: Auto-start disabled")
        print("💡 Enter REPL with Ctrl+A, or press RESET to restart normally")
    else:
        # Normal boot - import and run main.py
        print("🚀 Normal boot - starting monitoring...")
        import main
except Exception as e:
    print(f"❌ Boot error: {e}")
    print("💡 Entering REPL mode for debugging")
