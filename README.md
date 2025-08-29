# @WeatherStation

**Environmental sensors & climate insights** - A modern web application for monitoring temperature and humidity data with real-time updates and intelligent database management.

## 🎯 Features

### Core Monitoring
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
- **Timestamped archives** (e.g., `weatherstation_archive_20250829_165704.db`)
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
cd aWeatherStation

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### Start the Application
```bash
# Make script executable
chmod +x scripts/app.sh

# Start the weather station
./scripts/app.sh start

# Check status
./scripts/app.sh status

# Stop the service
./scripts/app.sh stop
```

### Auto-Start on Boot
```bash
# Configure systemd service (already done if following this guide)
sudo systemctl enable aweatherstation.service
sudo systemctl start aweatherstation.service

# Check service status
sudo systemctl status aweatherstation.service
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
- **Archive naming**: `weatherstation_archive_YYYYMMDD_HHMMSS.db`
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
aWeatherStation/
├── backend/
│   ├── app.py              # Main Flask application with GraphQL & SSE
│   ├── models.py           # SQLAlchemy models with rollover functionality  
│   ├── sensor_reader.py    # Temperature & humidity sensor abstraction
│   ├── weatherstation.db  # Current SQLite database (auto-managed)
│   └── weatherstation_archive_*.db  # Archived databases (10K+ readings)
├── frontend/
│   └── index.html          # Modern web interface
├── scripts/
│   └── app.sh              # Process management script  
├── logs/
│   ├── backend.out         # Application output logs
│   └── backend.log         # Detailed application logs
└── /etc/systemd/system/aweatherstation.service  # System service
```

## 🔄 Database Rollover

The system automatically manages database size and performance:

### Automatic Rollover Process
1. **Monitor**: Checks total readings after each sensor data insertion
2. **Trigger**: When total reaches 10,000 readings (temp + humidity combined)
3. **Archive**: Moves current `weatherstation.db` → `weatherstation_archive_TIMESTAMP.db`
4. **Reset**: Creates fresh `weatherstation.db` with empty tables
5. **Continue**: Seamlessly continues data collection

### Archive Management
- **Archive files**: `weatherstation_archive_20250829_165704.db`
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
systemctl status aweatherstation.service

# View real-time logs  
journalctl -u aweatherstation.service -f

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
