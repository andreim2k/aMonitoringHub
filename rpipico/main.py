"""
Auto-boot JSON Sensor Monitor for Raspberry Pi Pico
This file runs automatically when the Pico boots up
Outputs BME280 + MQ135 sensor data in JSON format every second over USB
"""

import json
import time
import machine
from machine import Pin, I2C, ADC

# Import sensor libraries
try:
    from lib.bme280 import BME280
    from lib.mq135 import MQ135
    from lib.config import (
        I2C_BUS, I2C_SDA_PIN, I2C_SCL_PIN, I2C_FREQ,
        MQ135_PIN, MQ135_R_ZERO
    )
    USE_LIB_MODULES = True
except ImportError:
    # Fallback if lib directory not available
    print("Warning: Using inline sensor classes. Install lib modules for better performance.")
    USE_LIB_MODULES = False
    # Use default values if config not available
    I2C_BUS = 1
    I2C_SDA_PIN = 2
    I2C_SCL_PIN = 3
    I2C_FREQ = 400000
    MQ135_PIN = 28
    MQ135_R_ZERO = 42304.5


# Auto-start monitoring function
def auto_start_monitoring():
    """Auto-start monitoring on boot"""
    print("🚀 Auto-starting JSON sensor monitoring...")
    
    # Small delay to ensure USB is ready
    time.sleep(2)
    
    # Retry loop for initialization
    max_retries = 10
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Initialize I2C for BME280
            i2c = I2C(I2C_BUS, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=I2C_FREQ)
            bme280 = BME280(i2c)
            print(f"✓ BME280 initialized on I2C{I2C_BUS} (SDA=GP{I2C_SDA_PIN}, SCL=GP{I2C_SCL_PIN})")
            
            # Initialize MQ135
            mq135 = MQ135(MQ135_PIN, r_zero=MQ135_R_ZERO)
            print(f"✓ MQ135 initialized on GPIO {MQ135_PIN} (calibrated)")
            
            print("📡 Starting continuous JSON monitoring (auto-boot)")
            print("💡 Press Ctrl+C to stop, or reset Pico to restart")
            print("-" * 50)
            
            # Start continuous monitoring loop
            while True:
                try:
                    # Get current timestamp
                    timestamp = time.ticks_ms() / 1000.0
                    
                    # Read BME280 data
                    temp_c, pressure_pa, humidity_pct = bme280.read_compensated_data()
                    pressure_hpa = pressure_pa / 100.0
                    
                    # Read MQ135 data
                    mq135_data = mq135.get_all_readings()
                    
                    # Create JSON payload
                    sensor_data = {
                        "timestamp": timestamp,
                        "bme280": {
                            "temperature_c": round(temp_c, 2),
                            "humidity_percent": round(humidity_pct, 1),
                            "pressure_hpa": round(pressure_hpa, 1),
                            "pressure_pa": round(pressure_pa, 0)
                        },
                        "mq135": mq135_data
                    }
                    
                    # Output JSON to USB serial
                    print(json.dumps(sensor_data))
                    
                    # Wait 1 second
                    time.sleep(1)
                    
                except KeyboardInterrupt:
                    print("\n⏹️  Monitoring stopped by user")
                    return
                except OSError as e:
                    # I2C/ADC communication errors
                    error_data = {
                        "timestamp": time.ticks_ms() / 1000.0,
                        "error": f"I/O error: {str(e)}",
                        "status": "sensor_error"
                    }
                    print(json.dumps(error_data))
                    time.sleep(1)
                except ValueError as e:
                    # Sensor validation errors
                    error_data = {
                        "timestamp": time.ticks_ms() / 1000.0,
                        "error": f"Validation error: {str(e)}",
                        "status": "sensor_error"
                    }
                    print(json.dumps(error_data))
                    time.sleep(1)
                except Exception as e:
                    # Other unexpected errors
                    error_data = {
                        "timestamp": time.ticks_ms() / 1000.0,
                        "error": f"Unexpected error: {str(e)}",
                        "status": "sensor_error"
                    }
                    print(json.dumps(error_data))
                    time.sleep(1)
                    
        except OSError as e:
            # I2C initialization failed
            retry_count += 1
            print(f"❌ Failed to initialize sensors (attempt {retry_count}/{max_retries}): {e}")
            print(f"🔧 Check wiring and sensor connections")
            if retry_count < max_retries:
                print(f"🔄 Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print("❌ Max retries reached. Please check hardware connections.")
                return
        except ValueError as e:
            # Sensor validation failed
            retry_count += 1
            print(f"❌ Sensor validation failed (attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                print(f"🔄 Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print("❌ Max retries reached. Please check sensor connections.")
                return
        except Exception as e:
            # Other initialization errors
            retry_count += 1
            print(f"❌ Unexpected initialization error (attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                print(f"🔄 Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print("❌ Max retries reached.")
                return


# This runs automatically when Pico boots
if __name__ == "__main__":
    auto_start_monitoring()
