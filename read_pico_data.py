#!/usr/bin/env python3
"""
Read JSON sensor data from Raspberry Pi Pico auto-boot monitoring
This script reads the continuous JSON output from the Pico over USB serial
"""

import subprocess
import json
import time
import signal
import sys

PICO_PORT = "/dev/cu.usbmodem101"

class PicoDataReader:
    def __init__(self, port=PICO_PORT):
        self.port = port
        self.process = None
        self.running = False
        
    def start_reading(self):
        """Start reading JSON data from Pico"""
        print(f"🔌 Connecting to Pico at {self.port}")
        print("📡 Reading JSON sensor data...")
        print("💡 Press Ctrl+C to stop")
        print("-" * 60)
        
        try:
            # Start mpremote in repl mode to read the auto-boot output
            cmd = ["mpremote", "connect", self.port]
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.running = True
            json_line_count = 0
            
            for line in iter(self.process.stdout.readline, ''):
                if not self.running:
                    break
                    
                line = line.strip()
                if not line:
                    continue
                
                # Skip non-JSON lines (boot messages, etc.)
                if not line.startswith('{'):
                    if "Auto-starting" in line or "initialized" in line or "monitoring" in line:
                        print(f"📟 {line}")
                    continue
                
                try:
                    # Parse JSON data
                    data = json.loads(line)
                    json_line_count += 1
                    
                    # Pretty print the sensor data
                    if "bme280" in data and "mq135" in data:
                        bme = data["bme280"]
                        mq = data["mq135"]
                        timestamp = data.get("timestamp", 0)
                        
                        print(f"📊 Reading #{json_line_count:03d} @ {timestamp:.1f}s:")
                        print(f"   🌡️  Temp: {bme['temperature_c']:.1f}°C")
                        print(f"   💧  Humidity: {bme['humidity_percent']:.1f}%") 
                        print(f"   🏔️  Pressure: {bme['pressure_hpa']:.1f} hPa")
                        print(f"   🌬️  CO2: {mq['co2_ppm']:.1f} ppm ({mq['air_quality_status']})")
                        print(f"   💨  NH3: {mq['nh3_ppm']:.1f} ppm")
                        print(f"   🍷  Alcohol: {mq['alcohol_ppm']:.1f} ppm")
                        print()
                    elif "error" in data:
                        print(f"⚠️  Sensor error: {data['error']}")
                    else:
                        # Raw JSON output
                        print(f"📄 JSON: {line}")
                        
                except json.JSONDecodeError:
                    # Not JSON, might be boot message
                    if line:
                        print(f"📟 {line}")
                        
        except KeyboardInterrupt:
            print("\n⏹️  Stopped by user")
        except Exception as e:
            print(f"❌ Error reading from Pico: {e}")
        finally:
            self.stop_reading()
    
    def stop_reading(self):
        """Stop reading and cleanup"""
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                self.process.kill()
        print("🔌 Disconnected from Pico")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Interrupt received, stopping...")
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create reader and start
    reader = PicoDataReader()
    
    try:
        reader.start_reading()
    except KeyboardInterrupt:
        reader.stop_reading()
        print("👋 Goodbye!")