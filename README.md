# @MonitoringHub

**Environmental sensors & climate insights** - A modern web application for monitoring temperature, humidity, and electricity meter readings with real-time updates and AI-powered OCR.

## 🎯 Features

### Core Monitoring
- **📹 ESP32-CAM Integration** - Professional POST API with configurable camera settings
- **🔍 AI-Powered OCR** - Read electricity meter displays using Gemini AI
- **🌡️ Temperature & Humidity** - Real-time monitoring with 5-minute intervals
- **📡 Live Updates** - Server-Sent Events (SSE) for instant data streaming
- **📊 Interactive Charts** - Historical trends with Chart.js
- **📈 Statistical Insights** - Min/max/average calculations

### User Experience  
- **⚡ Instant Loading** - Current data displays immediately from database
- **🎨 Modern UI** - Clean glassmorphism design with MonitoringHub branding
- **📱 Responsive Interface** - Works on desktop, tablet, and mobile
- **🚦 Smart Status Indicators** - Visual sensor health monitoring
- **🔄 Auto-Recovery** - Automatic reconnection and error handling

### System Management
- **🚀 Auto-Start on Boot** - Systemd service configuration
- **🔧 Process Management** - Background monitoring scripts
- **💾 Database Rollover** - Automatic archiving every 10,000 readings
- **📦 Data Preservation** - All historical data safely archived

## 🏗️ Architecture

### Backend Stack
- **Python 3.11** with GraphQL (Graphene) and Flask
- **SQLAlchemy ORM** with SQLite database
- **APScheduler** for background sensor reading
- **Server-Sent Events** for real-time streaming
- **Google Gemini AI** for OCR processing

### Frontend Stack
- **Vanilla HTML/CSS/JavaScript** - No framework dependencies
- **Chart.js 2.x** for interactive charts
- **Modern CSS Grid** with responsive design
- **Progressive Enhancement** with graceful degradation

## 📹 ESP32-CAM Integration

### POST-Only API Architecture
The system uses a professional POST-based approach for webcam integration:

**Backend Endpoints:**
- `POST /webcam/capture` - Capture image from ESP32-CAM
- `POST /webcam/ocr` - Run OCR analysis on captured image

### ESP32-CAM Request Format

**Capture Request Payload:**
```json
{
  "resolution": "UXGA",
  "flash": "off",
  "brightness": 0,
  "contrast": 0,
  "saturation": 0,
  "exposure": 300,
  "gain": 15,
  "special_effect": 0,
  "wb_mode": 0,
  "hmirror": false,
  "vflip": false,
  "timestamp": "2025-09-14T14:49:08.241Z",
  "api_endpoint": "http://192.168.50.3/snapshot",
  "method": "POST",
  "content_type": "application/json"
}
```

**Supported Camera Settings:**
- **Resolution**: `UXGA`, `SXGA`, `XGA`, `SVGA`, `VGA`, `CIF`, `QVGA`
- **Flash**: `"on"` or `"off"`
- **Brightness**: -2 to +2 (exposure compensation)
- **Contrast**: -2 to +2 (image contrast)
- **Exposure**: 0-1200 (manual exposure value)
- **Gain**: 0-30 (sensor gain)
- **Special Effects**: 0-6 (None, Negative, Grayscale, etc.)
- **White Balance**: 0-4 (Auto, Sunny, Cloudy, Office, Home)
- **Image Options**: `hmirror` and `vflip` (boolean)

### Configuration

Edit `backend/config.json`:
```json
{
  "webcam": {
    "url": "http://192.168.50.3/snapshot",
    "enabled": true,
    "title": "📹 Cabana 1 Electricity Meter"
  },
  "ocr": {
    "enabled": true,
    "engines": {
      "gemini": {
        "enabled": true,
        "api_key": "your-gemini-api-key-here",
        "model": "gemini-1.5-flash"
      }
    }
  }
}
```

## 🔍 OCR System

### AI-Powered Text Recognition
- **🧠 Gemini AI** - Primary OCR engine with superior accuracy (95%+)
- **📸 Automatic Capture** - Image loads on page load
- **🔍 Manual Reading** - "Read Index No." button for OCR processing
- **🧹 Clean Interface** - Index resets before each OCR operation

### OCR Workflow
1. **Page Load** → Automatic image capture from ESP32-CAM
2. **Image Display** → Shows captured electricity meter photo
3. **Manual OCR** → User clicks "🔍 Read Index No." button
4. **AI Processing** → Gemini AI analyzes the meter display
5. **Result Display** → Shows extracted meter reading

### API Response Format
```json
{
  "success": true,
  "index": "123456",
  "engine": "Gemini AI",
  "image": "data:image/jpeg;base64,/9j/4AAQ...",
  "timestamp": "2025-09-14T15:42:00Z"
}
```

## 🚀 Quick Start

### Prerequisites
```bash
# System dependencies
sudo apt update
sudo apt install python3 python3-venv python3-pip

# Clone repository
git clone https://github.com/andreim2k/aMonitoringHub.git
cd aMonitoringHub
```

### Installation
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create logs directory
mkdir -p backend/logs
```

### Configuration Setup
1. **Edit ESP32-CAM URL** in `backend/config.json`
2. **Add Gemini API Key** for OCR functionality
3. **Configure network settings** if needed

### Start Application
```bash
# Make script executable
chmod +x scripts/app.sh

# Start MonitoringHub
./scripts/app.sh start

# Check status
./scripts/app.sh status
```

## 🌐 Access Points

- **🏠 Main Interface**: http://localhost:5000/
- **🔌 GraphQL API**: http://localhost:5000/graphql
- **📡 SSE Stream**: http://localhost:5000/events

## 📊 API Documentation

### GraphQL Queries
```graphql
# Current temperature and humidity
{
  currentTemperature {
    temperatureC
    timestamp
    sensorType
  }
  currentHumidity {
    humidityPercent
    timestamp
  }
}

# Historical data
{
  temperatureHistory(limit: 50) {
    temperatureC
    timestamp
  }
  temperatureStatistics {
    count
    average
    minimum
    maximum
  }
}
```

### Webcam Endpoints
```bash
# Capture image from ESP32-CAM
curl -X POST "http://localhost:5000/webcam/capture" \
  -H "Content-Type: application/json"

# Run OCR on captured image
curl -X POST "http://localhost:5000/webcam/ocr" \
  -H "Content-Type: application/json"
```

### Server-Sent Events
```javascript
const eventSource = new EventSource('/events');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  if (data.type === 'temperature_update') {
    console.log('Temperature:', data.data.temperature_c);
  }
};
```

## 🔧 Configuration Options

### Environment Variables
```bash
# Application settings
--host 0.0.0.0          # Bind to all interfaces
--port 5000              # Default port
--debug                  # Enable debug mode

# Sensor settings
--threshold 0.1          # Temperature change threshold
--heartbeat 300          # Reading interval (seconds)
```

### Database Management
- **Automatic Rollover**: Every 10,000 readings
- **Archive Format**: `monitoringhub_archive_YYYYMMDD_HHMMSS.db`
- **Performance**: Optimized indexes for fast queries
- **Data Safety**: All historical data preserved

## 🛠️ System Management

### Service Management
```bash
# Application control
./scripts/app.sh start    # Start service
./scripts/app.sh stop     # Stop service
./scripts/app.sh restart  # Restart service
./scripts/app.sh status   # Check status
./scripts/app.sh logs 50  # View recent logs
./scripts/app.sh follow   # Follow logs real-time
```

### Auto-Start Configuration
```bash
# Install systemd service
sudo systemctl enable amonitoringhub.service
sudo systemctl start amonitoringhub.service

# Monitor service
sudo systemctl status amonitoringhub.service
journalctl -u amonitoringhub.service -f
```

## 📁 Project Structure

```
aMonitoringHub/
├── backend/
│   ├── app.py              # Main Flask application
│   ├── models.py           # Database models
│   ├── sensor_reader.py    # Sensor abstraction
│   ├── config.json         # ESP32-CAM & OCR settings
│   ├── monitoringhub.db    # Current database
│   └── logs/               # Application logs
├── frontend/
│   └── index.html          # Web interface
├── scripts/
│   └── app.sh              # Process management
└── README.md               # This documentation
```

## 🔧 Troubleshooting

### Common Issues

**ESP32-CAM Connection:**
```bash
# Test ESP32-CAM endpoint
curl -X POST "http://192.168.50.3/snapshot" \
  -H "Content-Type: application/json" \
  -d '{"resolution": "UXGA", "flash": "off"}'
```

**Database Permissions:**
```bash
# Fix database permissions
chmod 664 backend/*.db
chmod 775 backend/
chown $USER:$USER backend/*.db
```

**Port Already in Use:**
```bash
# Find process using port 5000
sudo lsof -i :5000
# Kill process if needed
sudo kill -9 <PID>
```

**OCR Issues:**
- Verify Gemini API key in `backend/config.json`
- Check ESP32-CAM image quality and lighting
- Ensure meter display is clearly visible

### Performance Optimization
- **Database rollover** keeps current DB under 1MB
- **5-minute sensor intervals** optimize sensor lifespan
- **Immediate SSE connection** for instant updates
- **Background processing** doesn't block UI loading

## 🎯 Recent Updates (September 2025)

### Major Improvements
- ✅ **ESP32-CAM POST Integration** - Professional camera API with exact payload
- ✅ **AI-Powered OCR** - Gemini AI for electricity meter reading
- ✅ **UI Rebranding** - Complete @MonitoringHub branding
- ✅ **Clean Capture Experience** - Streamlined image loading with spinner
- ✅ **Manual OCR Control** - User-initiated index reading
- ✅ **Removed Legacy APIs** - Clean POST-only architecture

### User Experience Enhancements
- ✅ **Automatic Image Capture** - Loads on page refresh
- ✅ **Professional Terminology** - "Read Index No." instead of technical terms
- ✅ **Clean Status Messages** - User-friendly error handling
- ✅ **Immediate Visual Feedback** - Spinner shows instantly on load

## 🔮 Future Roadmap

- **📊 Historical Meter Readings** - Track electricity usage over time
- **⚠️ Anomaly Detection** - Alert on unusual reading patterns
- **📱 Mobile Optimization** - Enhanced mobile interface
- **☁️ Cloud Integration** - Optional cloud data backup
- **🔌 Multi-Meter Support** - Monitor multiple electricity meters
- **📧 Notification System** - Email/SMS alerts for extreme values

---

**Built with ❤️ for reliable environmental and utility monitoring**

*@MonitoringHub - Professional monitoring solution for modern homes*

**Repository**: https://github.com/andreim2k/aMonitoringHub
