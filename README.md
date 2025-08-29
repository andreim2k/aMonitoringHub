# @WeatherStation

A modern, real-time web application for monitoring temperature data on ARM devices using GraphQL and Server-Sent Events (SSE).

## Features

- **Real-time temperature monitoring** with Server-Sent Events (SSE)
- **Interactive charts** using Chart.js for beautiful data visualization
- **GraphQL API** for efficient data queries
- **Modern responsive web interface** with vanilla JavaScript
- **SQLite database** for data persistence
- **Background process management** with monitoring scripts
- **Temperature sensor abstraction** supporting multiple sensor types
- **Professional glassmorphism UI** with aTorrent-inspired design

## Architecture

- **Backend**: Python with GraphQL (Graphene), Flask, and SQLAlchemy
- **Real-time Updates**: Server-Sent Events (SSE) for live temperature streaming
- **Frontend**: Vanilla HTML/CSS/JavaScript with Chart.js for interactive charts

## Supported Platforms

**Designed specifically for ARM devices:**
- Raspberry Pi (all models)
- Orange Pi
- Banana Pi
- NVIDIA Jetson series
- Other ARM-based single-board computers

**Requirements:**
- ARM-based processor (ARMv6, ARMv7, ARMv8/AArch64)
- Linux operating system
- Python 3.7+
- GPIO access for temperature sensors

## Supported Platforms

**Designed specifically for ARM devices:**
- Raspberry Pi (all models)
- Orange Pi
- Banana Pi
- NVIDIA Jetson series
- Other ARM-based single-board computers

**Requirements:**
- ARM-based processor (ARMv6, ARMv7, ARMv8/AArch64)
- Linux operating system
- Python 3.7+
- GPIO access for temperature sensors
- **Database**: SQLite with SQLAlchemy ORM for temperature data storage
- **Deployment**: Local network accessible with background process management

## Technology Stack

### Backend
- **Python 3.7+** - Core runtime
- **Flask** - Web framework
- **Graphene** - GraphQL implementation for Python
- **SQLAlchemy** - Database ORM
- **SQLite** - Database engine
- **Server-Sent Events (SSE)** - Real-time temperature streaming
- **APScheduler** - Background temperature collection

### Frontend
- **Vanilla JavaScript** - No heavy frameworks, lightweight and fast
- **Chart.js 2.9.4** - Interactive temperature charts (real-time & historical)
- **Pure CSS** - Modern glassmorphism design with gradients
- **Server-Sent Events (SSE)** - Real-time updates from backend

### Sensors
- **System thermal sensors** (`/sys/class/thermal/thermal_zone*/temp`)
- **Mock sensor** for development and testing
- **Extensible sensor interface** for adding new sensor types

## Project Structure

```
aWeatherStation/
├── backend/
│   ├── app.py              # Main GraphQL + SSE application
│   ├── models.py           # SQLAlchemy database models
│   ├── sensor_reader.py    # Temperature sensor abstraction
│   └── weatherstation.db      # SQLite database (created at runtime)
├── frontend/
│   └── index.html          # Complete single-file web application
├── scripts/
│   └── app.sh              # Process management script
├── logs/                   # Application logs (created at runtime)
├── venv/                   # Python virtual environment
├── requirements.txt        # Python dependencies
└── README.md
```

## API Endpoints

### GraphQL Endpoint
- **URL**: `http://192.168.50.2:5000/graphql`
- **Method**: POST
- **Content-Type**: application/json

#### Available Queries
```graphql
query {
  # Health check
  health {
    status
    timestamp
    database
  }
  
  # Current temperature
  currentTemperature {
    temperatureC
    timestamp
    sensorType
    sensorId
  }
  
  # Temperature history
  temperatureHistory(limit: 50) {
    temperatureC
    timestamp
    sensorId
  }
  
  # Temperature statistics
  temperatureStatistics {
    average
    minimum
    maximum
    count
  }
  
  # Sensor information
  sensorInfo {
    sensorType
    sensorId
    isActive
    lastReading
  }
}
```

### Server-Sent Events (SSE)
- **URL**: `http://192.168.50.2:5000/events`
- **Method**: GET
- **Content-Type**: text/event-stream

Real-time temperature updates are streamed as JSON events:
```json
{
  "type": "temperature_update",
  "data": {
    "temperature_c": 36.5,
    "timestamp_iso": "2025-08-28T04:15:30.123456+00:00",
    "sensor_type": "thermal_zone",
    "sensor_id": "cpu-thermal",
    "change_reason": "temp_change_0.20°C",
    "previous_temp": 36.3
  }
}
```

### Static Files
- **Frontend**: `http://192.168.50.2:5000/` (serves index.html)

## Getting Started

### Prerequisites
- **ARM-based device** (Raspberry Pi, Orange Pi, etc.)
- Python 3.7 or higher
- Linux operating system with GPIO support
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/andreim2k/aWeatherStation.git
   cd aWeatherStation
   ```

2. **Set up Python virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database** (automatic on first run):
   ```bash
   cd backend
   python app.py --host 0.0.0.0 --port 5000
   ```

### Running the Application

#### Using the Management Script (Recommended)
```bash
# Start the server
./scripts/app.sh start

# Check status
./scripts/app.sh status

# View logs
./scripts/app.sh logs

# Stop the server
./scripts/app.sh stop

# Restart the server
./scripts/app.sh restart

# Test endpoints
./scripts/app.sh test
```

#### Manual Execution
```bash
cd backend
source ../venv/bin/activate
python app.py --host 0.0.0.0 --port 5000
```

## Network Access

When running, the application will be accessible at:
- **Frontend Interface**: http://192.168.50.2:5000/
- **GraphQL Endpoint**: http://192.168.50.2:5000/graphql
- **SSE Events Stream**: http://192.168.50.2:5000/events

## Dashboard Features

### 🌡️ Main Temperature Display
- **Large temperature reading**: Current temperature prominently displayed
- **Last update timestamp**: Shows when the reading was taken
- **Live updates**: Automatically refreshes via SSE

### 📊 Statistics Cards
- **Sensor Status**: Online/Offline with sensor type information
- **Minimum Temperature**: Lowest recorded temperature
- **Maximum Temperature**: Highest recorded temperature  
- **Data Points**: Total number of temperature readings collected

### 📈 Interactive Charts
- **Real-time Chart**: Live updating line chart showing last 20 temperature readings
- **Historical Chart**: Displays up to 50 historical temperature readings
- **Responsive Design**: Charts adapt to screen size and are mobile-friendly

### 🔄 Real-time Features
- **Live connection status**: Green/yellow/red indicator in header
- **Automatic reconnection**: SSE connection auto-recovers from interruptions
- **Smooth animations**: Chart updates with smooth transitions
- **Error handling**: User-friendly error messages with retry options

## Temperature Sensors

The application automatically detects and uses available temperature sensors:

1. **System Thermal Sensors**: Reads from `/sys/class/thermal/thermal_zone*/temp`
2. **Mock Sensor**: Used when no physical sensors are available (generates realistic temperature data)
3. **Extensible Design**: Easy to add support for additional sensor types

### Sensor Interface
- Automatic sensor detection and fallback
- Configurable reading intervals (default: 1 second)
- Error handling and sensor health monitoring
- Temperature change detection with configurable thresholds

## Development

### GraphQL Schema
The GraphQL schema is automatically generated and can be explored by sending introspection queries to `/graphql`.

### Real-time Updates
Temperature readings are:
1. Collected every second by the background collector using APScheduler
2. Stored in the SQLite database
3. Broadcast to connected clients via Server-Sent Events
4. Displayed in real-time on the web interface with smooth chart animations

### Database Schema
```sql
CREATE TABLE temperature_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    temperature REAL NOT NULL,
    unit TEXT DEFAULT 'C',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    sensor_id TEXT DEFAULT 'default'
);
```

### Adding New Sensor Types
To add a new sensor type, extend the `sensor_reader.py` module:

1. Create a new sensor class implementing the sensor interface
2. Add detection logic to `get_sensor_reader()` function
3. Test with mock data before deploying to hardware

## Process Management

The `scripts/app.sh` script provides comprehensive process management:

- **Start/Stop/Restart**: Full process lifecycle management
- **Status Monitoring**: Real-time status with resource usage
- **Log Management**: Centralized logging with rotation
- **Health Checks**: Automatic endpoint testing
- **Background Execution**: Runs as daemon process with nohup

## Troubleshooting

### Common Issues

1. **No Temperature Data**:
   - Check if thermal sensors exist: `ls /sys/class/thermal/`
   - Application automatically falls back to mock sensor

2. **Connection Issues**:
   - Verify port 5000 is available: `netstat -tuln | grep 5000`
   - Check firewall settings for local network access

3. **Database Issues**:
   - Database is created automatically on first run
   - Check permissions in `backend/` directory

4. **Chart Not Loading**:
   - Ensure internet connection for Chart.js CDN
   - Check browser console for JavaScript errors

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source and available under the MIT License.

---

**@WeatherStation** - Real-time temperature monitoring made beautiful and simple.
