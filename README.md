# aTemperature

A modern web application for monitoring temperature data in real-time.

## Features

- Real-time temperature monitoring with WebSocket updates
- Historical data visualization with interactive charts
- Modern responsive web interface
- RESTful API for data access
- SQLite database for data persistence
- Background process management

## Architecture

- **Backend**: Python Flask with Flask-SocketIO for real-time communication
- **Frontend**: Modern HTML/CSS/JS with Chart.js for data visualization
- **Database**: SQLite for temperature data storage
- **Deployment**: Local network accessible with background process management

## Project Structure

```
aTemperature/
├── backend/          # Python Flask backend
├── frontend/         # HTML/CSS/JS frontend
├── scripts/          # Management scripts (app.sh)
├── logs/             # Application logs
├── venv/             # Python virtual environment
└── README.md
```

## Getting Started

1. Set up the Python virtual environment: `python3 -m venv venv`
2. Activate the environment: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Start the application: `./scripts/app.sh start`

## Network Access

The application will be accessible at:
- Backend API: http://192.168.50.2:5000
- Frontend: http://192.168.50.2:3000

## Temperature Sensor

This application is designed to work with various temperature sensors including:
- System thermal sensors (`/sys/class/thermal/`)
- 1-Wire sensors (DS18B20)
- I²C sensors (BMP280, DHT22)
- Mock sensor for development and testing
