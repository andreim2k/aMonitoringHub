"""
Boot script for Raspberry Pi Pico
Runs automatically on power-up and starts the monitoring system
"""

import machine
import time
import sys

# Optional: Set up a safe boot by holding a button
# Press GP0 during boot to enter REPL-only mode (no auto-start)
try:
    from machine import Pin
    boot_pin = Pin(0, Pin.IN, Pin.PULL_UP)

    # Give user time to press the button
    time.sleep_ms(100)

    if boot_pin.value() == 0:  # Button pressed (active low)
        print("🔧 Safe boot mode: Auto-start disabled")
        print("💡 Enter REPL with Ctrl+A, or press RESET to restart normally")
    else:
        # Normal boot - import and run main.py
        print("🚀 Normal boot - starting monitoring...")
        try:
            import main
        except ImportError as e:
            print(f"❌ Failed to import main module: {e}")
            print("💡 Check that main.py exists and all dependencies are available")
            print(f"   Import error details: {type(e).__name__}: {e}")
        except Exception as e:
            print(f"❌ Error running main module: {e}")
            print(f"   Error type: {type(e).__name__}")
            print("💡 Entering REPL mode for debugging")
            import traceback
            sys.print_exception(e)
except Exception as e:
    print(f"❌ Boot initialization error: {e}")
    print(f"   Error type: {type(e).__name__}")
    print("💡 Entering REPL mode for debugging")
    try:
        import traceback
        sys.print_exception(e)
    except:
        pass
