# USBJSONReader Anti-Stall Improvements

**Date:** 2025-11-15  
**Status:** ✅ Implemented

## Overview

Implemented comprehensive safeguards to prevent the USBJSONReader from stalling and ensure reliable data collection from USB sensors.

---

## 🔧 Improvements Implemented

### 1. **Watchdog Health Check Thread**
- **New Feature:** Separate background thread that monitors connection health every 60 seconds
- **Functionality:**
  - Tracks last data reception time
  - Detects stale connections (no data for 5 minutes)
  - Automatically forces reconnection when stalled
  - Warns at 70% threshold (3.5 minutes) before forcing reconnect

### 2. **Automatic Reconnection with Exponential Backoff**
- **Improved:** Reconnection logic with smart backoff strategy
- **Features:**
  - Exponential backoff: starts at 1 second, increases to max 30 seconds
  - Resets backoff on successful connection
  - Handles device changes (e.g., `/dev/ttyACM0` → `/dev/ttyACM1`)
  - Flushes stale buffers on reconnect

### 3. **Connection State Management**
- **New:** Thread-safe connection state tracking
- **Features:**
  - Uses `threading.Lock()` for safe concurrent access
  - Tracks multiple metrics:
    - `_connected`: Current connection status
    - `_last_data_time`: Timestamp of last data received
    - `_last_success_time`: Timestamp of last successful callback
    - `_reconnect_count`: Number of reconnections
    - `_last_error`: Last error message

### 4. **Empty Read Detection**
- **New:** Detects when device stops sending data
- **Functionality:**
  - Counts consecutive empty reads
  - Forces reconnection after 100 consecutive empty reads
  - Resets counter on successful data read

### 5. **Enhanced Error Handling**
- **Improved:** Better exception handling and recovery
- **Features:**
  - Separate handling for `SerialException` vs general exceptions
  - Proper cleanup of serial connections
  - Detailed error logging with context
  - Callback error handling (prevents reader crash on callback failure)

### 6. **Connection Initialization Improvements**
- **Enhanced:** Better connection setup
- **Features:**
  - Flushes input/output buffers on connect
  - Device re-detection on reconnect
  - Proper timeout handling (2 seconds)

---

## 📊 Configuration Parameters

The USBJSONReader now accepts additional parameters:

```python
USBJSONReader(
    device='/dev/ttyACM0',           # Device path (auto-detected if None)
    baudrate=115200,                  # Serial baud rate
    callback=process_sensor_data,     # Data callback function
    logger=logger,                    # Logger instance
    max_silence_seconds=300.0,        # Max seconds without data (default: 5 min)
    health_check_interval=60.0        # Health check interval (default: 60 sec)
)
```

---

## 🔍 How It Works

### Health Check Loop
1. Runs every 60 seconds (configurable)
2. Checks if data was received within the last 5 minutes
3. If no data for >5 minutes → Forces reconnection
4. If no data for >3.5 minutes → Logs warning

### Main Read Loop
1. Attempts to connect to serial device
2. Reads data with 2-second timeout
3. Tracks empty reads (no data)
4. After 100 empty reads → Forces reconnection
5. On successful read → Resets counters and updates timestamps
6. On error → Closes connection, waits with backoff, retries

### Reconnection Logic
1. Health check detects stale connection
2. Sets `_connected = False`
3. Main loop detects disconnected state
4. Closes current connection
5. Re-detects device (in case it changed)
6. Opens new connection with buffer flush
7. Resets all counters and backoff

---

## 📈 Benefits

1. **Automatic Recovery:** No manual intervention needed when connection stalls
2. **Proactive Detection:** Detects issues before they become critical
3. **Resilient:** Handles device disconnections, reconnections, and changes
4. **Observable:** Detailed logging for troubleshooting
5. **Configurable:** Adjustable thresholds for different use cases
6. **Thread-Safe:** Safe concurrent access from multiple threads

---

## 🧪 Testing

To verify the improvements are working:

1. **Check health status:**
   ```bash
   curl -X POST http://localhost:5000/graphql \
     -H "Content-Type: application/json" \
     -d '{"query": "{ health { usbConnection bme280Status { connected secondsSinceLastReading } } }"}'
   ```

2. **Monitor logs:**
   ```bash
   tail -f logs/backend.log | grep USBJSONReader
   ```

3. **Test reconnection:** Disconnect USB device, wait 5+ minutes, reconnect
   - Should automatically reconnect without restarting app

---

## 📝 Log Messages

### Normal Operation
- `USBJSONReader connected to /dev/ttyACM0 @ 115200 baud`
- `USBJSONReader health check: No data for X.Xs. Will reconnect if exceeds 300s.` (warning at 70% threshold)

### Reconnection Events
- `USBJSONReader: Reconnecting due to health check`
- `USBJSONReader: Forcing reconnection (no data for 300s)`
- `USBJSONReader: X consecutive empty reads. Forcing reconnection.`

### Errors
- `USBJSONReader SerialException: ...` (handled, will reconnect)
- `USBJSONReader connection error: ...` (handled, will retry with backoff)
- `USBJSONReader callback error: ...` (logged, doesn't crash reader)

---

## 🔄 Migration Notes

**No changes required** - The improvements are backward compatible:
- Default parameters work for existing installations
- Existing code continues to work without modification
- Optional parameters can be added for fine-tuning

---

## 🎯 Future Enhancements

Potential improvements for future versions:
- Configurable thresholds via config.json
- Metrics/statistics endpoint for monitoring
- WebSocket notifications for connection status changes
- Adaptive timeout based on historical data patterns

---

## ✅ Summary

The USBJSONReader now has robust anti-stall mechanisms that:
- ✅ Automatically detect and recover from stalled connections
- ✅ Handle device disconnections gracefully
- ✅ Provide detailed logging for troubleshooting
- ✅ Require no manual intervention
- ✅ Are fully backward compatible

**Result:** The USB sensor reader will automatically recover from stalls without requiring application restarts!

