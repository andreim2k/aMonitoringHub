"""
Flask application for aTemperature monitoring system.

Provides:
- REST API endpoints for temperature data access
- WebSocket server for real-time temperature updates
- Temperature data collection service
- Static file serving for frontend
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

# Import our modules
from models import init_database, db
from sensor_reader import TemperatureSensorReader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../logs/backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask application setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'temperature-monitoring-secret-key-2025'

# Enable CORS for frontend access
CORS(app, origins=['http://192.168.50.2:3000', 'http://localhost:3000'])

# SocketIO setup with eventlet
socketio = SocketIO(
    app, 
    cors_allowed_origins=['http://192.168.50.2:3000', 'http://localhost:3000'],
    async_mode='eventlet',
    logger=False,  # Reduce noise in logs
    engineio_logger=False
)

# Global variables
temperature_sensor = None
scheduler = None


class TemperatureCollector:
    """Handles temperature data collection and broadcasting."""
    
    def __init__(self, sensor_reader: TemperatureSensorReader, socketio_instance: SocketIO):
        self.sensor = sensor_reader
        self.socketio = socketio_instance
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.last_reading = None
        self.error_count = 0
        self.max_errors = 10  # Max consecutive errors before switching to mock
        
    def collect_temperature(self):
        """Collect temperature reading and broadcast to clients."""
        try:
            # Get sensor reading with metadata
            reading = self.sensor.get_reading()
            
            if reading is None:
                self.error_count += 1
                self.logger.warning(f"Failed to read temperature (error count: {self.error_count})")
                
                # Switch to mock sensor if too many consecutive errors
                if self.error_count >= self.max_errors and self.sensor.sensor_type != "mock":
                    self.logger.error("Too many sensor errors, switching to mock sensor")
                    self.sensor = TemperatureSensorReader("mock")
                    self.error_count = 0
                return
                
            # Reset error count on successful reading
            self.error_count = 0
            self.last_reading = reading
            
            # Store in database
            db_reading = db.add_temperature_reading(
                temperature_c=reading.temperature_c,
                sensor_type=reading.sensor_type,
                sensor_id=reading.sensor_id,
                timestamp=datetime.fromtimestamp(reading.timestamp, tz=timezone.utc)
            )
            
            if db_reading:
                # Broadcast to WebSocket clients
                temperature_data = {
                    'temperature_c': round(reading.temperature_c, 2),
                    'timestamp': reading.timestamp,
                    'timestamp_iso': datetime.fromtimestamp(reading.timestamp, tz=timezone.utc).isoformat(),
                    'sensor_type': reading.sensor_type,
                    'sensor_id': reading.sensor_id
                }
                
                self.socketio.emit('temperature_update', temperature_data, namespace='/')
                
                self.logger.debug(f"Collected and broadcast temperature: {reading.temperature_c:.2f}°C")
            else:
                self.logger.error("Failed to store temperature reading in database")
                
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error in temperature collection: {e}")


# REST API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Check database connectivity
        stats = db.get_statistics(hours_back=1)
        
        # Check sensor status
        sensor_info = temperature_sensor.get_sensor_info() if temperature_sensor else {}
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database': 'connected',
            'sensor': sensor_info,
            'recent_readings': stats.get('count', 0)
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500


@app.route('/api/current', methods=['GET'])
def get_current_temperature():
    """Get the most recent temperature reading."""
    try:
        recent_readings = db.get_recent_readings(limit=1)
        
        if not recent_readings:
            return jsonify({
                'error': 'No temperature readings available'
            }), 404
            
        reading = recent_readings[0]
        
        return jsonify({
            'temperature_c': reading.temperature_c,
            'timestamp': reading.timestamp.isoformat(),
            'timestamp_unix': reading.timestamp.timestamp(),
            'sensor_type': reading.sensor_type,
            'sensor_id': reading.sensor_id,
            'id': reading.id
        })
    except Exception as e:
        logger.error(f"Error getting current temperature: {e}")
        return jsonify({'error': 'Failed to get current temperature'}), 500


@app.route('/api/history', methods=['GET'])
def get_temperature_history():
    """Get historical temperature data."""
    try:
        # Get query parameters
        range_param = request.args.get('range', 'daily')  # daily, weekly, custom
        limit = min(int(request.args.get('limit', 1000)), 5000)  # Max 5000 points
        sensor_id = request.args.get('sensor_id')
        
        # Get readings based on range
        if range_param == 'daily':
            readings = db.get_daily_readings(days_back=1, sensor_id=sensor_id)
        elif range_param == 'weekly':
            readings = db.get_weekly_readings(weeks_back=1, sensor_id=sensor_id)
        elif range_param == 'recent':
            readings = db.get_recent_readings(limit=limit, sensor_id=sensor_id)
        else:
            # Default to recent readings
            readings = db.get_recent_readings(limit=limit, sensor_id=sensor_id)
            
        # Convert to JSON-serializable format
        data = []
        for reading in readings[:limit]:  # Ensure limit is respected
            data.append({
                'temperature_c': reading.temperature_c,
                'timestamp': reading.timestamp.isoformat(),
                'timestamp_unix': reading.timestamp.timestamp(),
                'sensor_type': reading.sensor_type,
                'sensor_id': reading.sensor_id
            })
            
        # Sort by timestamp (ascending for charts)
        data.sort(key=lambda x: x['timestamp_unix'])
        
        return jsonify({
            'data': data,
            'count': len(data),
            'range': range_param,
            'sensor_id': sensor_id
        })
        
    except Exception as e:
        logger.error(f"Error getting temperature history: {e}")
        return jsonify({'error': 'Failed to get temperature history'}), 500


@app.route('/api/statistics', methods=['GET'])
def get_temperature_statistics():
    """Get temperature statistics."""
    try:
        hours_back = int(request.args.get('hours', 24))
        sensor_id = request.args.get('sensor_id')
        
        stats = db.get_statistics(sensor_id=sensor_id, hours_back=hours_back)
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting temperature statistics: {e}")
        return jsonify({'error': 'Failed to get temperature statistics'}), 500


@app.route('/api/sensors', methods=['GET'])
def get_sensor_info():
    """Get information about available sensors."""
    try:
        if temperature_sensor:
            sensor_info = temperature_sensor.get_sensor_info()
            return jsonify(sensor_info)
        else:
            return jsonify({'error': 'No sensor initialized'}), 500
    except Exception as e:
        logger.error(f"Error getting sensor info: {e}")
        return jsonify({'error': 'Failed to get sensor info'}), 500


# WebSocket Events

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f"Client connected: {request.sid}")
    
    # Send current temperature on connection
    try:
        recent_readings = db.get_recent_readings(limit=1)
        if recent_readings:
            reading = recent_readings[0]
            temperature_data = {
                'temperature_c': reading.temperature_c,
                'timestamp': reading.timestamp.timestamp(),
                'timestamp_iso': reading.timestamp.isoformat(),
                'sensor_type': reading.sensor_type,
                'sensor_id': reading.sensor_id
            }
            emit('temperature_update', temperature_data)
    except Exception as e:
        logger.error(f"Error sending initial temperature: {e}")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on('request_current')
def handle_request_current():
    """Handle request for current temperature."""
    try:
        recent_readings = db.get_recent_readings(limit=1)
        if recent_readings:
            reading = recent_readings[0]
            temperature_data = {
                'temperature_c': reading.temperature_c,
                'timestamp': reading.timestamp.timestamp(),
                'timestamp_iso': reading.timestamp.isoformat(),
                'sensor_type': reading.sensor_type,
                'sensor_id': reading.sensor_id
            }
            emit('temperature_update', temperature_data)
    except Exception as e:
        logger.error(f"Error handling current temperature request: {e}")


# Static file serving for frontend
@app.route('/')
def serve_frontend():
    """Serve the main frontend page."""
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_path, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files from frontend directory."""
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_path, filename)


def initialize_application():
    """Initialize the application components."""
    global temperature_sensor, scheduler
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_database()
        
        # Initialize temperature sensor
        logger.info("Initializing temperature sensor...")
        temperature_sensor = TemperatureSensorReader()
        sensor_info = temperature_sensor.get_sensor_info()
        logger.info(f"Temperature sensor initialized: {sensor_info}")
        
        # Initialize temperature collector
        collector = TemperatureCollector(temperature_sensor, socketio)
        
        # Set up scheduled temperature collection
        logger.info("Setting up temperature collection scheduler...")
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            func=collector.collect_temperature,
            trigger='interval',
            seconds=1,  # Collect every second
            id='temperature_collection'
        )
        scheduler.start()
        logger.info("Temperature collection scheduler started")
        
        # Collect initial reading
        collector.collect_temperature()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        return False


def cleanup_application():
    """Clean up application resources."""
    global scheduler
    
    logger.info("Cleaning up application...")
    
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler shutdown complete")
        
    if db:
        db.close()
        logger.info("Database connections closed")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='aTemperature monitoring server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--sensor-type', default='auto', choices=['auto', 'thermal_zone', 'w1_sensor', 'mock'],
                       help='Temperature sensor type to use')
    
    args = parser.parse_args()
    
    try:
        # Initialize application
        if not initialize_application():
            logger.error("Failed to initialize application")
            sys.exit(1)
            
        logger.info(f"Starting aTemperature server on {args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop the server")
        
        # Run the Flask-SocketIO server
        socketio.run(
            app,
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=False  # Disable reloader to avoid double initialization
        )
        
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        cleanup_application()
