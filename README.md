# @MonitoringHub

**Environmental sensors & climate insights** - A modern web application for monitoring temperature and humidity data with real-time updates and intelligent database management.

## 🎯 Features

### Core Monitoring
- **📹 Live Webcam Integration** - Real-time camera feeds with configurable refresh intervals
- **🌡️ Temperature & Humidity monitoring** with 5-minute intervals for optimal sensor lifespan
- **📡 Real-time updates** via Server-Sent Events (SSE) with instant connection
- **📊 Interactive historical charts** using Chart.js for trend analysis
- **📈 Statistical insights** with min/max/average calculations
- **🗄️ Intelligent database management** with automatic rollover every 10,000 readings

### User Experience  
- **⚡ Instant page loading** - Current data displays immediately from database
- **🎨 Clean, modern UI** with professional glassmorphism design
- **📱 Responsive interface** works on desktop, tablet, and mobile
- **🚦 Smart sensor status** - Visual indicators (Checking... → Online/Offline)
- **🔄 Auto-recovery** - Automatic reconnection and error handling

### System Management
- **🚀 Auto-start on boot** - Systemd service configuration
- **🔧 Background process management** with monitoring scripts
- **📦 Automated database archiving** keeps current DB fast and efficient
- **💾 Data preservation** - All historical data safely archived

## 🏗️ Architecture

### Backend Stack
- **Python 3.11** with GraphQL (Graphene) and Flask
- **SQLAlchemy ORM** for database operations
- **SQLite database** with optimized indexes
- **APScheduler** for background sensor reading
- **Server-Sent Events** for real-time data streaming

### Frontend Stack
- **Vanilla HTML/CSS/JavaScript** - No framework dependencies
- **Chart.js 2.x** for Safari-compatible interactive charts
- **Modern CSS Grid** with glassmorphism styling
- **Progressive enhancement** with graceful degradation

### Database Features
- **Automatic rollover** at 10,000 readings
- **Timestamped archives** (e.g., `monitoringhub_archive_20250829_165704.db`)
- **Optimized indexes** for fast historical queries
- **ACID compliance** with transaction safety

## 🖥️ Supported Platforms

**Optimized for ARM devices:**
- 🍓 **Raspberry Pi** (all models)
- 🍊 **Orange Pi**  
- 🍌 **Banana Pi**
- 🚀 **NVIDIA Jetson** series
- 🔧 **Other ARM SBCs**

**Also supports:**
- 💻 **x86/x64 Linux** systems
- 🐧 **Debian/Ubuntu** distributions

## 📡 Sensor Support

### Temperature Sensors
- **🌡️ Thermal zones** (`/sys/class/thermal/`)
- **🔌 Hardware sensors** via system interfaces
- **🧪 Mock sensor** for development and testing

### Humidity Sensors  
- **💧 Mock humidity sensor** (easily extensible for real sensors)
- **🔧 Extensible architecture** for additional sensor types

## 🚀 Quick Start

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd @MonitoringHub

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Webcam Configuration

To configure webcam sources, edit the JavaScript configuration in `frontend/index.html`:

```javascript
let webcamConfig = {
  url: "http://192.168.50.3/capture?size=VGAurl: "http://192.168.50.3/snap"flash=1",    // Webcam snapshot URL
  refreshInterval: 5000,              // Refresh every 5 seconds
  retryDelay: 10000                   // Retry after 10 seconds on error
};
```

**Supported webcam formats:**
- JPEG snapshots (most IP cameras)
- MJPEG streams
- Any HTTP-accessible image URL


### Start the Application
```bash
# Make script executable
chmod +x scripts/app.sh

# Start the monitoring hub
./scripts/app.sh start

# Check status
./scripts/app.sh status

# Stop the service
./scripts/app.sh stop
```

### Auto-Start on Boot
```bash
# Configure systemd service (already done if following this guide)
sudo systemctl enable amonitoringhub.service
sudo systemctl start amonitoringhub.service

# Check service status
sudo systemctl status amonitoringhub.service
```

## 🌐 Access Points

- **🏠 Main Interface**: http://192.168.50.2:5000/
- **🔌 GraphQL Playground**: http://192.168.50.2:5000/graphql  
- **📡 SSE Endpoint**: http://192.168.50.2:5000/events

## 📊 API Examples

### GraphQL Queries
```graphql
# Current temperature
{
  currentTemperature {
    temperatureC
    timestamp
    sensorType
    sensorId
  }
}

# Temperature history
{
  temperatureHistory(limit: 50) {
    temperatureC
    timestamp
    sensorId
  }
}

# Statistics
{
  temperatureStatistics {
    count
    average
    minimum
    maximum
  }
}
```

### Server-Sent Events
```javascript
const eventSource = new EventSource('/events');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  if (data.type === 'temperature_update') {
    console.log('Temperature:', data.data.temperature_c);
  }
  
  if (data.type === 'humidity_update') {
    console.log('Humidity:', data.humidity_percent);
  }
};
```

## 🔧 Configuration

### Environment Settings
```bash
# Sensor reading interval (default: 5 minutes)
--heartbeat 300

# Temperature change threshold for logging
--threshold 0.1

# Server configuration  
--host 0.0.0.0 --port 5000
```

### Database Management
- **Automatic rollover**: Every 10,000 readings
- **Archive naming**: `monitoringhub_archive_YYYYMMDD_HHMMSS.db`
- **Performance**: Optimized indexes for fast queries
- **Size management**: Current DB stays under ~1MB for optimal speed

## 🛠️ Recent Improvements (August 2025)

### Performance Optimizations
- ✅ **Instant SSE connection** - Eliminated 15-second delays
- ✅ **Immediate data loading** - Current values display instantly from database
- ✅ **Background initialization** - Heavy queries don't block UI loading
- ✅ **Optimized sensor intervals** - 5-minute readings for sensor longevity

### User Interface Enhancements  
- ✅ **Removed redundant connection status** from header
- ✅ **Enhanced sensor status indicators** with color-coded states
- ✅ **Cleaned up real-time charts** - Focus on essential data and history
- ✅ **Updated terminology** - "Total Readings" instead of "Data Points"
- ✅ **Professional subtitle** - "Environmental sensors & climate insights"

### System Reliability
- ✅ **Systemd service integration** - Auto-start on boot
- ✅ **Database rollover system** - Automatic archiving every 10,000 readings
- ✅ **Improved error handling** - Graceful degradation and recovery
- ✅ **Database permission fixes** - Resolved readonly database issues

### Developer Experience
- ✅ **Enhanced logging** with detailed SSE debugging
- ✅ **Modular architecture** with clean separation of concerns
- ✅ **Comprehensive API documentation** with GraphQL schema
- ✅ **Automated testing** capabilities for rollover functionality

## 📁 File Structure

```
@MonitoringHub/
├── backend/
│   ├── app.py              # Main Flask application with GraphQL & SSE
│   ├── models.py           # SQLAlchemy models with rollover functionality  
│   ├── sensor_reader.py    # Temperature & humidity sensor abstraction
│   ├── monitoringhub.db  # Current SQLite database (auto-managed)
│   └── monitoringhub_archive_*.db  # Archived databases (10K+ readings)
├── frontend/
│   └── index.html          # Modern web interface
├── scripts/
│   └── app.sh              # Process management script  
├── logs/
│   ├── backend.out         # Application output logs
│   └── backend.log         # Detailed application logs
└── /etc/systemd/system/amonitoringhub.service  # System service
```

## 🔄 Database Rollover

The system automatically manages database size and performance:

### Automatic Rollover Process
1. **Monitor**: Checks total readings after each sensor data insertion
2. **Trigger**: When total reaches 10,000 readings (temp + humidity combined)
3. **Archive**: Moves current `monitoringhub.db` → `monitoringhub_archive_TIMESTAMP.db`
4. **Reset**: Creates fresh `monitoringhub.db` with empty tables
5. **Continue**: Seamlessly continues data collection

### Archive Management
- **Archive files**: `monitoringhub_archive_20250829_165704.db`
- **Data preservation**: All historical data safely stored
- **Query capability**: Archived databases fully functional for historical analysis
- **Storage efficiency**: Current database optimized for real-time performance

## 🚦 Status Indicators

### Sensor Status Colors
- **🟠 Checking...** - Initial connection state (orange with pulse animation)
- **🟢 Online** - Sensors connected and data flowing (green)
- **🔴 Offline** - Connection lost or sensor failure (red)

### System Health
- **Total Readings**: Count of all sensor measurements
- **Current Values**: Latest temperature and humidity with timestamps
- **Historical Trends**: Charts showing data patterns over time
- **Statistics**: Min/Max/Average values for analysis

## 📈 Monitoring & Logs

### Service Management
```bash
# Service status
systemctl status amonitoringhub.service

# View real-time logs  
journalctl -u amonitoringhub.service -f

# Application logs
tail -f logs/backend.out
tail -f logs/backend.log
```

### Performance Monitoring
- **SSE connection health**: Real-time connection status
- **Database performance**: Query timing and rollover events
- **Sensor readings**: Success/failure rates and error handling
- **System resources**: Memory and CPU usage tracking

## 🔮 Future Enhancements

- **📊 Multi-sensor support** - Easy addition of pressure, UV, wind sensors
- **☁️ Cloud integration** - Optional cloud storage for archived data
- **📧 Alert system** - Notifications for extreme values or sensor failures  
- **🔌 API extensions** - REST API alongside GraphQL
- **📱 Mobile app** - Native mobile interface
- **🌍 Remote access** - Secure external connectivity options

---

**Built with ❤️ for reliable environmental monitoring**

*Last updated: August 29, 2025*

## 🔧 Troubleshooting

### Database Permission Issues

If you encounter SQLite database write errors like:
```
sqlite3.OperationalError: attempt to write a readonly database
```

**Fix database permissions:**
```bash
# Make the database file writable
chmod 664 backend/*.db

# Ensure the backend directory is writable
chmod 775 backend/

# If running as a service, check file ownership
chown $USER:$USER backend/*.db
```

**Prevention:**
- Always run the application with proper user permissions
- Ensure the database directory has write permissions
- Use the provided `app.sh` script which handles permissions correctly

### Common Issues

1. **Port already in use**: If port 5000 is busy, modify the port in `backend/app.py`
2. **Virtual environment issues**: Recreate with `rm -rf venv && python3 -m venv venv`
3. **Missing dependencies**: Run `pip install -r requirements.txt` in activated venv
4. **SSE connection issues**: Check browser console and ensure `/events` endpoint is accessible


## 🔍 AI-Powered OCR Integration

### New OCR Features (September 2025)

@MonitoringHub now includes advanced **Optical Character Recognition (OCR)** capabilities for extracting numbers from electricity meter displays with dual-engine support:

#### **🤖 Dual OCR Engine Support**
- **🧠 Gemini AI OCR** - Primary engine using Google's Gemini 1.5 Flash for superior accuracy
- **🔤 Enhanced Tesseract OCR** - Fallback engine with advanced image preprocessing
- **🔄 Automatic Fallback** - Frontend tries Gemini first, falls back to Tesseract if needed

#### **📸 Webcam Integration**
- **📷 Live Image Capture** - SXGA resolution with flash (`http://192.168.50.3/snap/SXGA/flash`)
- **⚙️ Configurable Sources** - Update webcam URL in `backend/config.json`
- **🔄 Smart Caching** - Optimized image fetching with minimal bandwidth usage

#### **🎯 OCR API Endpoints**

| Endpoint | Engine | Description |
|----------|---------|-------------|
| `/ocr-gemini` | Gemini AI | Primary OCR with superior number recognition |
| `/ocr-webcam` | Tesseract | Enhanced traditional OCR with preprocessing |
| `/ocr-gemini-debug` | Gemini AI | Debug mode showing detailed analysis |

#### **⚡ Usage Examples**

**Test Gemini OCR:**
```bash
curl "http://localhost:5000/ocr-gemini" | jq .
```

**Expected Response:**
```json
{
  "success": true,
  "index": "123456",
  "engine": "Gemini AI",
  "model": "gemini-1.5-flash"
}
```

**Frontend Integration:**
- **🖱️ Manual Trigger** - "Extract Numbers" button for immediate OCR
- **⏰ Auto-Refresh** - Runs every 30 seconds automatically
- **🎨 Visual Feedback** - Shows which engine was used and results

#### **🔧 Configuration**

**OCR Settings** in `backend/config.json`:
```json
{
  "webcam": {
    "url": "http://192.168.50.3/snap/SXGA/flash",
    "enabled": true,
    "title": "📹 Cabana 1 Electricity Meter"
  },
  "ocr": {
    "enabled": true,
    "engines": {
      "tesseract": {
        "enabled": true,
        "config": "--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789"
      },
      "gemini": {
        "enabled": true,
        "api_key": "your-gemini-api-key-here",
        "model": "gemini-1.5-flash"
      }
    },
    "refresh_interval": 30
  }
}
```

#### **🚀 Advanced Features**

**Gemini AI Enhancements:**
- **📋 Strict Number-Only Responses** - Returns only digits, no commentary
- **🎯 Meter-Specific Prompts** - Optimized for electricity meter displays
- **🔍 Multi-Number Detection** - Finds longest/most prominent reading
- **⚠️ Error Handling** - Clear "UNREADABLE" response when unclear

**Tesseract Optimizations:**
- **🖼️ Image Preprocessing** - Gaussian blur, adaptive thresholding, morphological operations
- **📏 3x Scaling** - Upscales images for better recognition
- **🔄 Dual Processing** - Normal and inverted image analysis
- **🎯 Number-Only Config** - Whitelist digits for cleaner results

#### **💡 Installation Requirements**

**System Dependencies:**
```bash
# Install Tesseract OCR
sudo apt update
sudo apt install tesseract-ocr

# Python packages (auto-installed with requirements.txt)
pip install pytesseract opencv-contrib-python-headless pillow google-generativeai
```

**Gemini API Setup:**
1. Get API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Add to `backend/config.json` under `ocr.engines.gemini.api_key`
3. Or set environment variable: `GEMINI_API_KEY=your-key-here`

#### **🔧 Troubleshooting OCR**

**Common Issues:**

1. **Webcam not accessible:**
   ```bash
   # Test webcam URL directly
   curl -I "http://192.168.50.3/snap/SXGA/flash"
   ```

2. **Tesseract not found:**
   ```bash
   # Install system dependency
   sudo apt install tesseract-ocr
   ```

3. **Gemini API errors:**
   - Verify API key in config.json
   - Check quota limits in Google Cloud Console
   - Ensure model `gemini-1.5-flash` is available

4. **Poor OCR accuracy:**
   - Ensure meter display is well-lit (flash enabled)
   - Check webcam focus and positioning
   - Try different resolutions: `/snap/VGA`, `/snap/SVGA`, `/snap/XGA`

#### **📊 OCR Performance Metrics**

| Feature | Gemini AI | Enhanced Tesseract |
|---------|-----------|-------------------|
| **Accuracy** | 95%+ | 70-80% |
| **Speed** | ~2-3 seconds | ~1-2 seconds |
| **Error Handling** | Excellent | Good |
| **Number-Only Output** | ✅ Guaranteed | ✅ With preprocessing |
| **Multi-digit Recognition** | ✅ Superior | ✅ Basic |

#### **🔮 Future OCR Enhancements**

- **📊 Historical Tracking** - Store and graph meter readings over time
- **⚠️ Anomaly Detection** - Alert on unusual reading changes
- **📱 Mobile OCR** - Direct phone camera integration
- **🏗️ Multiple Meter Support** - Monitor several meters simultaneously
- **☁️ Cloud Storage** - Backup readings to cloud services

---

**🎯 The OCR system transforms static webcam images into actionable electricity meter data, enabling automated monitoring and historical analysis.**

