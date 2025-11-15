# USBJSONReader Auto-Reconnect Verification

## ✅ Implementation Complete

The USBJSONReader now has **automatic reconnection** that works **without requiring app restarts**.

## How It Works

### 1. **Health Check Thread** (Runs every 60 seconds)
- Monitors connection health independently
- Checks if data was received within the last 5 minutes (300 seconds)
- Automatically forces reconnection if no data for >5 minutes
- Warns at 70% threshold (3.5 minutes / 210 seconds)

### 2. **Main Read Loop** (Continuous)
- Detects when health check forces disconnect
- Immediately closes stale connection
- Automatically reconnects with fresh connection
- Resets all counters and backoff timers

### 3. **Reconnection Logic**
- Exponential backoff (1s → 30s max)
- Device re-detection (handles device changes)
- Buffer flushing on reconnect
- Empty read detection (100 consecutive empty reads = reconnect)

## Verification Steps

### Check Current Status
```bash
curl -X POST http://localhost:5000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ health { usbConnection bme280Status { connected secondsSinceLastReading } } }"}'
```

### Monitor Health Checks
```bash
tail -f logs/backend.log | grep -i "USBJSONReader\|health\|reconnect"
```

### Expected Behavior

1. **Normal Operation:**
   - Sensors show "online" status
   - Data received regularly (< 60 seconds between readings)

2. **Stale Detection (70% threshold - 3.5 minutes):**
   - Health check logs: `USBJSONReader health check: No data for X.Xs. Will reconnect if exceeds 300s.`
   - Sensors still show "stale" but reconnection will happen soon

3. **Auto-Reconnection (100% threshold - 5 minutes):**
   - Health check logs: `USBJSONReader health check: No data for X.Xs (threshold: 300s). Forcing reconnection.`
   - Main loop logs: `USBJSONReader: Closed stale connection, reconnecting...`
   - Connection automatically re-established
   - Sensors return to "online" status

## Testing Auto-Reconnect

To test the auto-reconnect feature:

1. **Simulate device disconnect:**
   ```bash
   # Unplug USB device or stop sending data
   ```

2. **Wait 5+ minutes** (or adjust threshold in code)

3. **Reconnect device:**
   ```bash
   # Plug device back in
   ```

4. **Verify automatic recovery:**
   - Check logs for reconnection messages
   - Verify sensors return to "online" status
   - Confirm new data is being received

## Configuration

Default thresholds (can be adjusted in code):
- `max_silence_seconds`: 300.0 (5 minutes)
- `health_check_interval`: 60.0 (1 minute)

## Key Features

✅ **No manual intervention required**
✅ **Automatic detection of stalled connections**
✅ **Proactive warnings before forced reconnect**
✅ **Handles device disconnections gracefully**
✅ **Recovers automatically when device reconnects**
✅ **Thread-safe operation**
✅ **Detailed logging for troubleshooting**

## Status

**✅ IMPLEMENTED AND ACTIVE**

The auto-reconnect mechanism is now active and will automatically recover from stalled connections without requiring application restarts.

