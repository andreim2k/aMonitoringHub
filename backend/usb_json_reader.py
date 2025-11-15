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
        max_silence_seconds: float = 300.0,  # 5 minutes without data triggers reconnect
        health_check_interval: float = 60.0,  # Check health every 60 seconds
    ) -> None:
        """Initializes the USBJSONReader.

        Args:
            device: The path to the serial device (e.g., '/dev/ttyACM0').
                If None, the device will be auto-detected.
            baudrate: The baud rate for the serial connection.
            callback: A function to call with each normalized data packet.
            logger: A logger instance for logging messages.
            max_silence_seconds: Maximum seconds without data before forcing reconnection.
            health_check_interval: Interval in seconds for health checks.
        """
        self.device = device
        self.baudrate = baudrate
        self.callback = callback
        self.logger = logger
        self.max_silence_seconds = max_silence_seconds
        self.health_check_interval = health_check_interval
        self._thread: Optional[threading.Thread] = None
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._connected = False
        self._last_error = None
        self._last_success_time = None
        self._last_data_time = None
        self._reconnect_count = 0
        self._lock = threading.Lock()

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
        """Starts the reader thread and health check thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='USBJSONReader', daemon=True)
        self._thread.start()
        # Start health check thread
        if self._health_check_thread is None or not self._health_check_thread.is_alive():
            self._health_check_thread = threading.Thread(target=self._health_check_loop, name='USBJSONReaderHealth', daemon=True)
            self._health_check_thread.start()

    def stop(self) -> None:
        """Stops the reader thread and health check thread."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if self._health_check_thread:
            self._health_check_thread.join(timeout=2)

    def is_connected(self) -> bool:
        """Returns True if the USB device is currently connected and reading data.

        Returns:
            bool: Connection status.
        """
        return self._connected

    def get_status(self) -> Dict[str, Any]:
        """Returns the current status of the USB reader.

        Returns:
            dict: Status information including connection state, last error, and last success time.
        """
        with self._lock:
            return {
                'connected': self._connected,
                'last_error': self._last_error,
                'last_success_time': self._last_success_time,
                'last_data_time': self._last_data_time,
                'reconnect_count': self._reconnect_count
            }
    
    def _force_reconnect(self) -> None:
        """Forces a reconnection by resetting connection state."""
        with self._lock:
            was_connected = self._connected
            if self.logger:
                self.logger.warning(
                    f'USBJSONReader: Forcing reconnection (no data for {self.max_silence_seconds}s). '
                    f'Reconnect count: {self._reconnect_count + 1}'
                )
            self._connected = False
            self._last_error = 'Watchdog timeout - no data received'
            self._reconnect_count += 1
        
        # Log the forced reconnect action
        if self.logger and was_connected:
            self.logger.info('USBJSONReader: Connection state reset, main loop will reconnect')
    
    def _health_check_loop(self) -> None:
        """Periodic health check loop that monitors connection health."""
        if self.logger:
            self.logger.info(f'USBJSONReader health check thread started (interval: {self.health_check_interval}s, threshold: {self.max_silence_seconds}s)')
        
        while not self._stop.is_set():
            try:
                time.sleep(self.health_check_interval)
                
                if self._stop.is_set():
                    break
                
                current_time = time.time()
                with self._lock:
                    last_data = self._last_data_time
                    connected = self._connected
                    last_success = self._last_success_time
                
                # Use last_success_time if last_data_time is not available (for backward compatibility)
                check_time = last_data if last_data is not None else last_success
                
                # Check if we're connected but haven't received data recently
                if connected:
                    if check_time is not None:
                        silence_duration = current_time - check_time
                        if silence_duration > self.max_silence_seconds:
                            if self.logger:
                                self.logger.warning(
                                    f'USBJSONReader health check: No data for {silence_duration:.1f}s '
                                    f'(threshold: {self.max_silence_seconds}s). Forcing reconnection.'
                                )
                            self._force_reconnect()
                        elif silence_duration > self.max_silence_seconds * 0.7:  # Warn at 70% threshold
                            if self.logger:
                                self.logger.warning(
                                    f'USBJSONReader health check: No data for {silence_duration:.1f}s. '
                                    f'Will reconnect if exceeds {self.max_silence_seconds}s.'
                                )
                    else:
                        # Connected but never received data - suspicious, but give it some time
                        # Check if we've been connected for a while without data
                        if self.logger:
                            self.logger.debug('USBJSONReader health check: Connected but no data received yet')
                elif not connected:
                    # Not connected - main loop should be trying to reconnect
                    if self.logger:
                        self.logger.debug(f'USBJSONReader health check: Not connected, main loop should reconnect')
                        
            except Exception as e:
                if self.logger:
                    self.logger.error(f'USBJSONReader health check error: {e}', exc_info=True)

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
            self._connected = False
            self._last_error = 'No serial device found'
            return

        if self.logger:
            self.logger.info(f'USBJSONReader connecting to {port} @ {self.baudrate} baud')

        ser = None
        backoff_seconds = 1.0
        max_backoff = 30.0
        consecutive_empty_reads = 0
        max_empty_reads = 100  # After 100 empty reads, force reconnect
        
        while not self._stop.is_set():
            try:
                # Check if health check forced a reconnection
                should_reconnect = False
                with self._lock:
                    if not self._connected and ser is not None:
                        # Health check detected stale connection and forced disconnect
                        should_reconnect = True
                
                if should_reconnect:
                    # Close current connection immediately
                    try:
                        if ser:
                            ser.close()
                            if self.logger:
                                self.logger.info('USBJSONReader: Closed stale connection, reconnecting...')
                    except Exception as close_error:
                        if self.logger:
                            self.logger.debug(f'USBJSONReader: Error closing connection: {close_error}')
                    ser = None
                    consecutive_empty_reads = 0
                    backoff_seconds = 1.0  # Reset backoff for immediate reconnect attempt
                    time.sleep(0.5)  # Brief pause before reconnecting
                
                if ser is None:
                    # Try to detect device again in case it changed
                    current_port = self.device or self.detect_device()
                    if current_port != port:
                        if self.logger:
                            self.logger.info(f'USBJSONReader: Device changed from {port} to {current_port}')
                        port = current_port
                    
                    if not port:
                        with self._lock:
                            self._connected = False
                            self._last_error = 'No serial device found'
                        if self.logger:
                            self.logger.warning('USBJSONReader: No serial device found, retrying...')
                        time.sleep(backoff_seconds)
                        backoff_seconds = min(backoff_seconds * 1.5, max_backoff)
                        continue
                    
                    try:
                        ser = serial.Serial(port=port, baudrate=self.baudrate, timeout=2)
                        # Give device a moment to initialize
                        time.sleep(0.2)
                        # Flush any stale data
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()
                        
                        with self._lock:
                            self._connected = True
                            self._last_error = None
                            consecutive_empty_reads = 0
                            backoff_seconds = 1.0  # Reset backoff on successful connection
                        
                        if self.logger:
                            self.logger.info(f'USBJSONReader connected to {port} @ {self.baudrate} baud')
                    except Exception as e:
                        with self._lock:
                            self._connected = False
                            self._last_error = str(e)
                        if self.logger:
                            self.logger.error(f'USBJSONReader connection error: {e}')
                        ser = None
                        time.sleep(backoff_seconds)
                        backoff_seconds = min(backoff_seconds * 1.5, max_backoff)
                        continue

                # Read with timeout
                line = ser.readline()
                
                if not line:
                    consecutive_empty_reads += 1
                    # If too many empty reads, force reconnect
                    if consecutive_empty_reads >= max_empty_reads:
                        if self.logger:
                            self.logger.warning(
                                f'USBJSONReader: {consecutive_empty_reads} consecutive empty reads. '
                                'Forcing reconnection.'
                            )
                        with self._lock:
                            self._connected = False
                        try:
                            if ser:
                                ser.close()
                        except Exception:
                            pass
                        ser = None
                        consecutive_empty_reads = 0
                        time.sleep(1.0)
                    continue
                
                # Reset empty read counter on successful read
                consecutive_empty_reads = 0
                
                # Update last data time
                current_time = time.time()
                with self._lock:
                    self._last_data_time = current_time

                try:
                    text = line.decode('utf-8', errors='ignore').strip()
                except Exception as decode_error:
                    if self.logger:
                        self.logger.debug(f'USBJSONReader decode error: {decode_error}')
                    continue

                if not text:
                    continue

                # Parse JSON
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError as json_error:
                    # Not valid JSON; log occasionally but don't spam
                    if self.logger:
                        self.logger.debug(f'USBJSONReader JSON parse error: {json_error}, line: {text[:50]}')
                    continue

                normalized = self._normalize(payload)
                if normalized and self.callback:
                    try:
                        self.callback(normalized)
                        with self._lock:
                            self._last_success_time = current_time
                    except Exception as callback_error:
                        if self.logger:
                            self.logger.error(f'USBJSONReader callback error: {callback_error}')

            except serial.SerialException as e:
                with self._lock:
                    self._connected = False
                    self._last_error = f'Serial error: {str(e)}'
                if self.logger:
                    self.logger.error(f'USBJSONReader SerialException: {e}')
                # Close and reconnect
                try:
                    if ser:
                        ser.close()
                except Exception:
                    pass
                ser = None
                consecutive_empty_reads = 0
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 1.5, max_backoff)
                
            except Exception as e:
                with self._lock:
                    self._connected = False
                    self._last_error = str(e)
                if self.logger:
                    self.logger.error(f'USBJSONReader unexpected error: {e}', exc_info=True)
                # Backoff and try to reopen
                try:
                    if ser:
                        ser.close()
                except Exception:
                    pass
                ser = None
                consecutive_empty_reads = 0
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 1.5, max_backoff)

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
