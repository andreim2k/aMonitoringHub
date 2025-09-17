# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Common Development Commands

### Application Management
```bash
# Start the weather station
./scripts/app.sh start

# Check application status
./scripts/app.sh status

# Stop the service
./scripts/app.sh stop

# View live application logs
tail -f logs/backend.out
tail -f logs/backend.log
```

### Python Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Development Testing
```bash
# Test sensor reading directly
python3 backend/sensor_reader.py

# Test database models
python3 backend/models.py

# Run Flask app directly (development mode)
cd backend && python3 app.py --debug
```

### System Service Management
```bash
# Check system service status
sudo systemctl status aweatherstation.service

# View service logs
journalctl -u aweatherstation.service -f

# Restart service
sudo systemctl restart aweatherstation.service
```

## Architecture Overview

### High-Level Structure
This is a full-stack environmental monitoring system with these key components:

- **Backend**: Python Flask application with GraphQL API and SQLite database
- **Frontend**: Vanilla HTML/CSS/JavaScript with real-time charts
- **Arduino**: Hardware sensor interface (BME280 support)
- **Real-time Communication**: Server-Sent Events (SSE) for live data streaming
- **Data Management**: Automatic database rollover every 10,000 readings

### Backend Architecture (`backend/`)

**Core Components:**
- `app.py` - Main Flask application with GraphQL schema, SSE endpoints, and background data collection
- `models.py` - SQLAlchemy ORM models with automatic database rollover functionality 
- `sensor_reader.py` - Sensor abstraction layer supporting thermal zones, 1-Wire, and mock sensors

**Key Design Patterns:**
- **Smart SSE Updates**: Only sends real-time updates when temperature changes significantly (≥0.1°C threshold)
- **Database Rollover**: Automatically archives database when reaching 10,000 total readings (temp + humidity)
- **Sensor Abstraction**: Auto-detection of available sensors with fallback to mock sensor
- **Background Scheduling**: APScheduler for periodic sensor reading (5-minute intervals)

### Data Flow
1. **Sensor Reading**: Background scheduler reads sensors every 5 minutes
2. **Database Storage**: All readings stored in SQLite with indexed timestamps
3. **Real-time Updates**: SSE broadcasts changes to connected web clients
4. **GraphQL API**: Provides structured access to current/historical data and statistics
5. **Database Management**: Automatic archiving prevents database bloat

### Frontend Integration
- **Real-time Charts**: Chart.js 2.x for Safari compatibility
- **SSE Connection**: Immediate connection with latest data from database
- **Progressive Enhancement**: Works without JavaScript for basic functionality

### Arduino Integration (`arduino/`)
- **BME280 Support**: Temperature, humidity, and pressure readings
- **Serial Communication**: 1-second interval data transmission
- **USB Connection**: Direct connection for sensor data collection
- **Board Support**: Arduino Uno, Nano, Due, ESP32, and compatible boards

## Development Guidelines

### Adding New Sensor Types
1. Extend `TemperatureSensorReader` or `HumiditySensorReader` in `sensor_reader.py`
2. Add detection logic in `_detect_sensor_type()` method
3. Implement read methods following existing patterns
4. Update sensor info methods for metadata

### Database Schema Changes
- Modify models in `models.py`
- Consider rollover impact on archived databases
- Add migration logic if needed for existing installations
- Test with both current and archived databases

### GraphQL API Extensions
- Add new types to GraphQL schema in `app.py`
- Implement resolvers following error handling patterns
- Consider caching for expensive queries
- Maintain consistency with existing naming conventions

### Frontend Modifications
- Location: `frontend/index.html` (single-file application)
- Real-time updates handled via SSE event listeners
- Chart.js configuration for Safari compatibility
- CSS uses modern grid with glassmorphism styling

### Arduino Development
- BME280 library required for sensor communication
- Serial output format should match backend parsing expectations
- 1-second reading interval for responsive updates
- Include error handling for sensor failures

## Key Configuration Points

### Application Settings
- **Sensor reading interval**: 300 seconds (5 minutes) - adjustable via `--heartbeat`
- **SSE temperature threshold**: 0.1°C - adjustable via `--threshold` 
- **Database rollover**: 10,000 total readings
- **Server binding**: `0.0.0.0:5000` by default

### File Structure Context
```
aWeatherStation/
├── backend/           # Python Flask application
├── frontend/          # Single-page web interface  
├── arduino/           # Arduino sensor sketches
├── scripts/           # Process management scripts
├── logs/              # Application logs
└── weatherstation*.db # SQLite databases (current + archives)
```

### Environment Dependencies
- **Python 3.11+** with Flask, GraphQL (Graphene), and SQLAlchemy
- **APScheduler** for background sensor reading
- **Chart.js 2.x** for frontend visualization
- **Arduino IDE** with BME280 libraries for hardware interface

### Access Endpoints
- **Main Interface**: http://localhost:5000/
- **GraphQL Playground**: http://localhost:5000/graphql
- **SSE Stream**: http://localhost:5000/events
- **System Service**: `aweatherstation.service`
