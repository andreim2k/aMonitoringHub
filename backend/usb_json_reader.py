import json
import logging
import threading
import time
from typing import Callable, Optional, Dict, Any

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except ImportError:
    serial = None
    list_ports = None


class USBJSONReader:
    """Reads line-delimited JSON from a USB CDC serial device.

    This class runs in a separate thread to continuously read data from a
    serial device, such as a MicroPython board. It auto-detects the device,
    parses incoming JSON lines, normalizes the data, and invokes a callback
    with the processed data.

    Expected JSON format:
      {
        "timestamp": <seconds>,
        "bme280": {"temperature_c": 23.4, "humidity_percent": 55.0, ...},
        "mq135": {"co2_ppm": 560.0, "air_quality_index": 3, ...}
      }
    """

    def __init__(
        self,
        device: Optional[str] = None,
        baudrate: int = 115200,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Initializes the USBJSONReader.

        Args:
            device: The path to the serial device (e.g., '/dev/ttyACM0').
                If None, the device will be auto-detected.
            baudrate: The baud rate for the serial connection.
            callback: A function to call with each normalized data packet.
            logger: A logger instance for logging messages.
        """
        self.device = device
        self.baudrate = baudrate
        self.callback = callback
        self.logger = logger
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def detect_device(self) -> Optional[str]:
        """Auto-detects the serial device.

        It prioritizes devices with the Raspberry Pi VID and then common
        Linux device names like 'ttyACM' and 'ttyUSB'.

        Returns:
            The path to the detected device, or None if no device is found.
        """
        # Prefer PySerial enumeration with VID/PID 0x2e8a:0005 (Raspberry Pi)
        try:
            if list_ports is not None:
                candidates = []
                for p in list_ports.comports():
                    # Prioritize Raspberry Pi (VID 0x2e8a)
                    if (getattr(p, 'vid', None) == 0x2e8A) or ('ttyACM' in p.device) or ('ttyUSB' in p.device):
                        candidates.append(p.device)
                if candidates:
                    # Prefer ttyACM first
                    candidates.sort(key=lambda d: (0 if 'ttyACM' in d else 1, d))
                    return candidates[0]
        except Exception:
            pass

        # Fallback to common paths
        for prefix in ('/dev/ttyACM', '/dev/ttyUSB'):
            for i in range(0, 4):
                path = f"{prefix}{i}"
                try:
                    import os
                    if os.path.exists(path):
                        return path
                except Exception:
                    pass
        return None

    def start(self) -> None:
        """Starts the reader thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='USBJSONReader', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops the reader thread."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        """The main loop for the reader thread.

        This method handles connecting to the serial port, reading lines,
        parsing JSON, and calling the callback. It includes error handling
        and a backoff mechanism for reconnection.
        """
        if serial is None:
            if self.logger:
                self.logger.error('pyserial not installed; cannot read USB JSON')
            return

        port = self.device or self.detect_device()
        if not port:
            if self.logger:
                self.logger.error('No serial device found for USB JSON reader')
            return

        if self.logger:
            self.logger.info(f'USBJSONReader connecting to {port} @ {self.baudrate} baud')

        ser = None
        while not self._stop.is_set():
            try:
                if ser is None:
                    ser = serial.Serial(port=port, baudrate=self.baudrate, timeout=2)
                    # Give device a moment
                    time.sleep(0.2)

                line = ser.readline()
                if not line:
                    continue

                try:
                    text = line.decode('utf-8', errors='ignore').strip()
                except Exception:
                    continue

                if not text:
                    continue

                # Parse JSON
                try:
                    payload = json.loads(text)
                except Exception:
                    # Not JSON; ignore
                    continue

                normalized = self._normalize(payload)
                if normalized and self.callback:
                    self.callback(normalized)

            except Exception as e:
                if self.logger:
                    self.logger.error(f'USBJSONReader error: {e}')
                # Backoff and try to reopen
                try:
                    if ser:
                        ser.close()
                except Exception:
                    pass
                ser = None
                time.sleep(1.0)

        try:
            if ser:
                ser.close()
        except Exception:
            pass

    def _normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes the raw JSON payload into a standardized dictionary format.

        Args:
            payload: The raw dictionary parsed from the JSON line.

        Returns:
            A standardized dictionary containing sensor data.
        """
        ts = payload.get('timestamp', time.time())
        bme = payload.get('bme280', {})
        mq = payload.get('mq135', {})
        result = {
            'timestamp': ts,
            'temperature_c': bme.get('temperature_c'),
            'humidity_percent': bme.get('humidity_percent'),
            'pressure_hpa': bme.get('pressure_hpa') or (bme.get('pressure_pa') / 100.0 if bme.get('pressure_pa') else None),
            'air': {
                'co2_ppm': mq.get('co2_ppm'),
                'nh3_ppm': mq.get('nh3_ppm'),
                'alcohol_ppm': mq.get('alcohol_ppm'),
                'aqi': mq.get('air_quality_index'),
                'status': mq.get('air_quality_status'),
                'raw_adc': mq.get('raw_adc'),
                'voltage_v': mq.get('voltage_v'),
                'resistance_ohm': mq.get('resistance_ohm'),
                'ratio_rs_r0': mq.get('ratio_rs_r0'),
            }
        }
        return result
