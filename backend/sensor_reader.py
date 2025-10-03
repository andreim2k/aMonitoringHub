"""
Sensor reader module for the aMonitoringHub application.

This module provides classes for reading data from various hardware sensors,
including temperature and humidity sensors. It supports auto-detection of
available sensors and provides a mock sensor for development and testing
purposes.
"""

import logging
import random
import time
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class SensorReading:
    """A dataclass to hold a single sensor reading with its metadata.

    Attributes:
        temperature_c: The temperature reading in degrees Celsius.
        sensor_type: The type of the sensor (e.g., 'mock', 'w1_sensor').
        sensor_id: The unique identifier for the sensor.
        timestamp: The Unix timestamp when the reading was taken.
        metadata: A dictionary for any extra sensor-specific information.
    """
    temperature_c: float
    sensor_type: str
    sensor_id: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None


class TemperatureSensorReader:
    """A class to read temperature from various supported sensor types.

    This class can auto-detect available sensors (thermal zones, 1-Wire) or
    can be configured to use a specific type, including a mock sensor for
    development.

    Attributes:
        logger: The logger instance for this class.
        sensor_config: A dictionary of configuration options for the sensor.
        sensor_type: The type of sensor being used.
        active_sensor: A dictionary containing details of the active sensor.
    """
    
    def __init__(self, sensor_type: str = "auto", sensor_config: Optional[Dict[str, Any]] = None):
        """Initializes the TemperatureSensorReader.

        Args:
            sensor_type: The type of sensor to use ('auto', 'thermal_zone',
                'w1_sensor', 'mock'). Defaults to 'auto'.
            sensor_config: A dictionary with configuration for the sensor,
                especially for the mock sensor.
        """
        self.logger = logging.getLogger(__name__)
        self.sensor_config = sensor_config or {}
        
        if sensor_type == "auto":
            self.sensor_type = self._detect_sensor_type()
        else:
            self.sensor_type = sensor_type
            
        self._initialize_sensor()
        
    def _detect_sensor_type(self) -> str:
        """Auto-detects the first available hardware temperature sensor.

        It checks for system thermal zones and 1-Wire devices in that order.
        If no hardware is found, it falls back to the mock sensor.

        Returns:
            The detected sensor type as a string.
        """
        # Check for system thermal zones
        thermal_zones = self._find_thermal_zones()
        if thermal_zones:
            self.logger.info(f"Found thermal zones: {thermal_zones}")
            return "thermal_zone"
            
        # Check for 1-Wire devices
        w1_devices = self._find_w1_devices()
        if w1_devices:
            self.logger.info(f"Found 1-Wire devices: {w1_devices}")
            return "w1_sensor"
            
        # Fallback to mock sensor
        self.logger.warning("No hardware sensors detected, using mock sensor")
        return "mock"
        
    def _find_thermal_zones(self) -> List[Dict[str, str]]:
        """Scans the system for available thermal zones.

        Looks in '/sys/class/thermal' for directories representing thermal zones.

        Returns:
            A list of dictionaries, where each dictionary represents a found
            thermal zone with its name, path, and type.
        """
        thermal_zones = []
        thermal_base = "/sys/class/thermal"
        
        if os.path.exists(thermal_base):
            for item in os.listdir(thermal_base):
                if item.startswith("thermal_zone"):
                    zone_path = os.path.join(thermal_base, item)
                    temp_file = os.path.join(zone_path, "temp")
                    type_file = os.path.join(zone_path, "type")
                    
                    if os.path.exists(temp_file) and os.path.exists(type_file):
                        try:
                            with open(type_file, 'r') as f:
                                zone_type = f.read().strip()
                            thermal_zones.append({
                                'zone': item,
                                'path': temp_file,
                                'type': zone_type
                            })
                        except Exception as e:
                            self.logger.debug(f"Could not read {type_file}: {e}")
                            
        return thermal_zones
        
    def _find_w1_devices(self) -> List[Dict[str, str]]:
        """Scans the system for available 1-Wire temperature devices.

        Looks in '/sys/bus/w1/devices' for devices with common temperature
        sensor prefixes (e.g., '28-').

        Returns:
            A list of dictionaries, where each dictionary represents a found
            1-Wire device with its ID and path.
        """
        w1_devices = []
        w1_base = "/sys/bus/w1/devices"
        
        if os.path.exists(w1_base):
            for device in os.listdir(w1_base):
                if device.startswith(("10-", "22-", "28-")):  # Common temp sensor prefixes
                    device_path = os.path.join(w1_base, device, "w1_slave")
                    if os.path.exists(device_path):
                        w1_devices.append({
                            'device_id': device,
                            'path': device_path
                        })
                        
        return w1_devices
        
    def _initialize_sensor(self):
        """Initializes the sensor based on the determined sensor_type."""
        if self.sensor_type == "thermal_zone":
            self.thermal_zones = self._find_thermal_zones()
            if self.thermal_zones:
                # Use the first available thermal zone (typically CPU)
                self.active_sensor = self.thermal_zones[0]
                self.logger.info(f"Using thermal zone: {self.active_sensor['type']} at {self.active_sensor['path']}")
            else:
                raise ValueError("No thermal zones available")
                
        elif self.sensor_type == "w1_sensor":
            self.w1_devices = self._find_w1_devices()
            if self.w1_devices:
                self.active_sensor = self.w1_devices[0]
                self.logger.info(f"Using 1-Wire sensor: {self.active_sensor['device_id']}")
            else:
                raise ValueError("No 1-Wire devices available")
                
        elif self.sensor_type == "mock":
            # Mock sensor configuration
            self.mock_base_temp = self.sensor_config.get("base_temperature", 22.5)
            self.mock_variation = self.sensor_config.get("temperature_variation", 2.0)
            self.logger.info("Using mock temperature sensor")
            
        else:
            raise ValueError(f"Unsupported sensor type: {self.sensor_type}")
            
    def get_current_temp(self) -> Optional[float]:
        """Reads the current temperature from the active sensor.

        Returns:
            The temperature in degrees Celsius as a float, or None if the
            reading fails.
        """
        try:
            if self.sensor_type == "thermal_zone":
                return self._read_thermal_zone()
            elif self.sensor_type == "w1_sensor":
                return self._read_w1_sensor()
            elif self.sensor_type == "mock":
                return self._read_mock_sensor()
            else:
                self.logger.error(f"Unknown sensor type: {self.sensor_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error reading temperature: {e}")
            return None
            
    def get_reading(self) -> Optional[SensorReading]:
        """Gets a complete sensor reading, including metadata.

        Returns:
            A SensorReading object containing the temperature and metadata,
            or None if the reading fails.
        """
        temp = self.get_current_temp()
        if temp is None:
            return None
            
        sensor_id = "unknown"
        metadata = {}
        
        if self.sensor_type == "thermal_zone":
            sensor_id = self.active_sensor['type']
            metadata = {
                "zone": self.active_sensor['zone'],
                "path": self.active_sensor['path']
            }
        elif self.sensor_type == "w1_sensor":
            sensor_id = self.active_sensor['device_id']
            metadata = {
                "path": self.active_sensor['path']
            }
        elif self.sensor_type == "mock":
            sensor_id = "mock_sensor"
            metadata = {
                "base_temp": self.mock_base_temp,
                "variation": self.mock_variation
            }
            
        return SensorReading(
            temperature_c=temp,
            sensor_type=self.sensor_type,
            sensor_id=sensor_id,
            timestamp=time.time(),
            metadata=metadata
        )
        
    def _read_thermal_zone(self) -> float:
        """Reads temperature from a sysfs thermal zone file.

        Returns:
            The temperature in degrees Celsius.
        """
        with open(self.active_sensor['path'], 'r') as f:
            # Thermal zone temperature is in millidegrees Celsius
            temp_millidegrees = int(f.read().strip())
            return temp_millidegrees / 1000.0
            
    def _read_w1_sensor(self) -> float:
        """Reads temperature from a 1-Wire sensor device file.

        Returns:
            The temperature in degrees Celsius.

        Raises:
            ValueError: If the sensor data cannot be parsed.
        """
        with open(self.active_sensor['path'], 'r') as f:
            content = f.read()
            
        # Parse 1-Wire sensor output
        lines = content.strip().split('\n')
        if len(lines) >= 2 and lines[0].strip().endswith('YES'):
            temp_line = lines[1]
            temp_start = temp_line.find('t=')
            if temp_start != -1:
                temp_string = temp_line[temp_start + 2:]
                temp_millidegrees = int(temp_string)
                return temp_millidegrees / 1000.0
                
        raise ValueError("Could not parse 1-Wire sensor data")
        
    def _read_mock_sensor(self) -> float:
        """Generates a mock temperature reading.

        The reading is based on a base temperature with some random variation
        and a slow time-based drift to simulate realistic changes.

        Returns:
            The mock temperature in degrees Celsius.
        """
        # Generate realistic temperature variation
        variation = random.uniform(-self.mock_variation, self.mock_variation)
        # Add some time-based slow drift
        time_factor = time.time() % 3600  # Hour cycle
        drift = 0.5 * (time_factor / 1800 - 1)  # ±0.5°C over hour
        
        return self.mock_base_temp + variation + drift
        
    def get_sensor_info(self) -> Dict[str, Any]:
        """Retrieves information about the currently configured sensor.

        Returns:
            A dictionary containing details about the sensor type, its
            initialization status, and available devices/zones.
        """
        info = {
            "sensor_type": self.sensor_type,
            "initialized": True
        }
        
        if hasattr(self, 'active_sensor'):
            info["active_sensor"] = self.active_sensor
            
        if self.sensor_type == "thermal_zone" and hasattr(self, 'thermal_zones'):
            info["available_zones"] = self.thermal_zones
            
        if self.sensor_type == "w1_sensor" and hasattr(self, 'w1_devices'):
            info["available_devices"] = self.w1_devices
            
        return info




class HumiditySensorReader:
    """A class to read humidity, currently supporting a mock sensor.

    This class is designed for extensibility with real hardware but currently
    only implements a mock sensor for development and testing.

    Attributes:
        logger: The logger instance for this class.
        sensor_config: A dictionary of configuration options for the sensor.
        sensor_type: The type of sensor being used (e.g., 'mock').
    """
    
    def __init__(self, sensor_type: str = "mock", sensor_config: Optional[Dict[str, Any]] = None):
        """Initializes the HumiditySensorReader.

        Args:
            sensor_type: The type of sensor to use. Defaults to 'mock'.
            sensor_config: A dictionary with configuration for the sensor.
        """
        self.logger = logging.getLogger(__name__)
        self.sensor_config = sensor_config or {}
        self.sensor_type = sensor_type
        
        # For now, primarily using mock sensor since humidity sensors are less common
        if sensor_type == "auto":
            self.sensor_type = "mock"
            
        self._initialize_sensor()
        
    def _initialize_sensor(self):
        """Initializes the sensor based on the selected type."""
        if self.sensor_type == "mock":
            self.mock_base_humidity = self.sensor_config.get('base_humidity', 45.0)  # Base 45% humidity
            self.mock_variation = self.sensor_config.get('variation', 15.0)  # ±15% variation
            self.logger.info(f"Initialized mock humidity sensor: base={self.mock_base_humidity}%, variation=±{self.mock_variation}%")
        else:
            raise ValueError(f"Unsupported humidity sensor type: {self.sensor_type}")
    
    def get_current_humidity(self) -> Optional[float]:
        """Reads the current humidity from the active sensor.

        Returns:
            The relative humidity in percent, or None if the reading fails.
        """
        try:
            if self.sensor_type == "mock":
                return self._read_mock_sensor()
            else:
                raise ValueError(f"Unsupported sensor type: {self.sensor_type}")
                
        except Exception as e:
            self.logger.error(f"Error reading humidity sensor: {e}")
            return None
            
    def _read_mock_sensor(self) -> float:
        """Generates a mock humidity reading.

        The reading is based on a base humidity with random variation and
        a slow time-based drift.

        Returns:
            The mock humidity in percent, clamped between 0 and 100.
        """
        import random
        import time
        
        # Generate realistic humidity variation
        variation = random.uniform(-self.mock_variation, self.mock_variation)
        # Add some time-based slow drift
        time_factor = time.time() % 7200  # 2-hour cycle
        drift = 10.0 * (time_factor / 3600 - 1)  # ±10% over 2 hours
        
        humidity = self.mock_base_humidity + variation + drift
        # Clamp between 0 and 100
        return max(0.0, min(100.0, humidity))
        
    def get_sensor_info(self) -> Dict[str, Any]:
        """Retrieves information about the currently configured humidity sensor.

        Returns:
            A dictionary containing details about the sensor.
        """
        info = {
            "sensor_type": self.sensor_type,
            "initialized": True
        }
        
        if self.sensor_type == "mock":
            info["base_humidity"] = self.mock_base_humidity
            info["variation"] = self.mock_variation
            
        return info


# Convenience function for quick temperature reading
def get_current_temp(sensor_type: str = "auto") -> Optional[float]:
    """A convenience function to get a single temperature reading.

    This creates a temporary TemperatureSensorReader instance to get the current
    temperature.

    Args:
        sensor_type: The type of sensor to use. Defaults to 'auto'.

    Returns:
        The current temperature in degrees Celsius, or None on failure.
    """
    try:
        sensor = TemperatureSensorReader(sensor_type=sensor_type)
        return sensor.get_current_temp()
    except Exception as e:
        logging.getLogger(__name__).error(f"Error getting temperature: {e}")
        return None




# Convenience function for quick humidity reading
def get_current_humidity(sensor_type: str = "mock") -> Optional[float]:
    """A convenience function to get a single humidity reading.

    This creates a temporary HumiditySensorReader instance to get the current
    humidity.

    Args:
        sensor_type: The type of sensor to use. Defaults to 'mock'.

    Returns:
        The current relative humidity in percent, or None on failure.
    """
    try:
        sensor = HumiditySensorReader(sensor_type=sensor_type)
        return sensor.get_current_humidity()
    except Exception as e:
        logging.getLogger(__name__).error(f"Error getting humidity: {e}")
        return None

if __name__ == "__main__":
    # Test the sensor reader
    import sys
    
    logging.basicConfig(level=logging.ERROR)
    
    sensor_type = sys.argv[1] if len(sys.argv) > 1 else "auto"
    
    try:
        sensor = TemperatureSensorReader(sensor_type=sensor_type)
        
        for i in range(5):
            reading = sensor.get_reading()
            if reading:
                pass  # Reading successful
            
            if i < 4:  # Don't sleep after last reading
                time.sleep(1)
                
    except Exception as e:
        sys.exit(1)
