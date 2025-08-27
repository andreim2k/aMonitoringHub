"""
GraphQL-based Flask application for aTemperature monitoring system.

Features:
- GraphQL API for querying temperature data
- Server-Sent Events (SSE) for real-time temperature pushing
- Lightweight and efficient real-time updates
- Temperature data collection service
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Generator
from queue import Queue
import threading

from flask import Flask, request, jsonify, Response, send_from_directory
from flask_graphql import GraphQLView
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

import graphene
from graphene import ObjectType, String, Float, List as GrapheneList, Field, Int, Schema

# Import our modules
from models import init_database, db, TemperatureReading as DBTemperatureReading
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
app.config['SECRET_KEY'] = 'temperature-monitoring-graphql-2025'

# Enable CORS
CORS(app, origins=['http://192.168.50.2:3000', 'http://192.168.50.2:5000', 'http://localhost:3000'])

# Global variables
temperature_sensor = None
scheduler = None
sse_clients = Queue()  # Queue for SSE connections


# GraphQL Types
class TemperatureReading(ObjectType):
    id = Int()
    temperature_c = Float()
    timestamp = String()
    timestamp_unix = Float()
    sensor_type = String()
    sensor_id = String()


class TemperatureStatistics(ObjectType):
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    hours_back = Int()


class SensorInfo(ObjectType):
    sensor_type = String()
    sensor_id = String()
    initialized = String()
    active_sensor = String()


class HealthStatus(ObjectType):
    status = String()
    timestamp = String()
    database = String()
    sensor = Field(SensorInfo)
    recent_readings = Int()


# GraphQL Queries
class Query(ObjectType):
    # Health check
    health = Field(HealthStatus)
    
    # Current temperature
    current_temperature = Field(TemperatureReading)
    
    # Temperature history
    temperature_history = GrapheneList(
        TemperatureReading,
        range=String(default_value="daily"),
        limit=Int(default_value=1000)
    )
    
    # Temperature statistics
    temperature_statistics = Field(
        TemperatureStatistics,
        hours=Int(default_value=24)
    )
    
    # Sensor information
    sensor_info = Field(SensorInfo)

    def resolve_health(self, info):
        try:
            # Check database connectivity
            stats = db.get_statistics(hours_back=1)
            
            # Check sensor status
            sensor_info_dict = temperature_sensor.get_sensor_info() if temperature_sensor else {}
            
            return HealthStatus(
                status="ok",
                timestamp=datetime.now(timezone.utc).isoformat(),
                database="connected",
                sensor=SensorInfo(
                    sensor_type=sensor_info_dict.get('sensor_type', 'unknown'),
                    sensor_id=sensor_info_dict.get('active_sensor', {}).get('type', 'unknown'),
                    initialized="true" if sensor_info_dict.get('initialized') else "false",
                    active_sensor=str(sensor_info_dict.get('active_sensor', {}))
                ),
                recent_readings=stats.get('count', 0)
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                status="error",
                timestamp=datetime.now(timezone.utc).isoformat(),
                database="error",
                sensor=None,
                recent_readings=0
            )

    def resolve_current_temperature(self, info):
        try:
            recent_readings = db.get_recent_readings(limit=1)
            
            if not recent_readings:
                return None
                
            reading = recent_readings[0]
            
            return TemperatureReading(
                id=reading.id,
                temperature_c=reading.temperature_c,
                timestamp=reading.timestamp.isoformat(),
                timestamp_unix=reading.timestamp.timestamp(),
                sensor_type=reading.sensor_type,
                sensor_id=reading.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current temperature: {e}")
            return None

    def resolve_temperature_history(self, info, range="daily", limit=1000):
        try:
            # Limit to reasonable maximum
            limit = min(limit, 5000)
            
            # Get readings based on range
            if range == "daily":
                readings = db.get_daily_readings(days_back=1)
            elif range == "weekly":
                readings = db.get_weekly_readings(weeks_back=1)
            elif range == "recent":
                readings = db.get_recent_readings(limit=limit)
            else:
                # Default to recent readings
                readings = db.get_recent_readings(limit=limit)
                
            # Convert to GraphQL objects
            result = []
            for reading in readings[:limit]:
                result.append(TemperatureReading(
                    id=reading.id,
                    temperature_c=reading.temperature_c,
                    timestamp=reading.timestamp.isoformat(),
                    timestamp_unix=reading.timestamp.timestamp(),
                    sensor_type=reading.sensor_type,
                    sensor_id=reading.sensor_id
                ))
                
            # Sort by timestamp (ascending for charts)
            result.sort(key=lambda x: x.timestamp_unix)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting temperature history: {e}")
            return []

    def resolve_temperature_statistics(self, info, hours=24):
        try:
            stats = db.get_statistics(hours_back=hours)
            
            return TemperatureStatistics(
                count=stats['count'],
                average=stats['average'],
                minimum=stats['minimum'],
                maximum=stats['maximum'],
                hours_back=stats['hours_back']
            )
        except Exception as e:
            logger.error(f"Error getting temperature statistics: {e}")
            return TemperatureStatistics(
                count=0,
                average=0.0,
                minimum=0.0,
                maximum=0.0,
                hours_back=hours
            )

    def resolve_sensor_info(self, info):
        try:
            if temperature_sensor:
                sensor_info_dict = temperature_sensor.get_sensor_info()
                return SensorInfo(
                    sensor_type=sensor_info_dict.get('sensor_type', 'unknown'),
                    sensor_id=sensor_info_dict.get('active_sensor', {}).get('type', 'unknown'),
                    initialized="true" if sensor_info_dict.get('initialized') else "false",
                    active_sensor=str(sensor_info_dict.get('active_sensor', {}))
                )
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting sensor info: {e}")
            return None


# GraphQL Schema
schema = Schema(query=Query)


class TemperatureCollector:
    """Handles temperature data collection and broadcasting via SSE."""
    
    def __init__(self, sensor_reader: TemperatureSensorReader):
        self.sensor = sensor_reader
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.last_reading = None
        self.error_count = 0
        self.max_errors = 10
        
    def collect_temperature(self):
        """Collect temperature reading and broadcast to SSE clients."""
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
                # Broadcast to SSE clients
                temperature_data = {
                    'type': 'temperature_update',
                    'data': {
                        'temperature_c': round(reading.temperature_c, 2),
                        'timestamp': reading.timestamp,
                        'timestamp_iso': datetime.fromtimestamp(reading.timestamp, tz=timezone.utc).isoformat(),
                        'sensor_type': reading.sensor_type,
                        'sensor_id': reading.sensor_id
                    }
                }
                
                # Add to SSE broadcast queue
                try:
                    sse_clients.put_nowait(temperature_data)
                except:
                    pass  # Queue is full, skip this update
                
                self.logger.debug(f"Collected and queued temperature: {reading.temperature_c:.2f}°C")
            else:
                self.logger.error("Failed to store temperature reading in database")
                
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error in temperature collection: {e}")


# Server-Sent Events for real-time updates
@app.route('/events')
def events():
    """Server-Sent Events endpoint for real-time temperature updates."""
    def event_stream():
        while True:
            try:
                # Get temperature update from queue (blocking with timeout)
                data = sse_clients.get(timeout=30)  # 30 second timeout
                yield f"data: {json.dumps(data)}\n\n"
                sse_clients.task_done()
            except:
                # Send heartbeat to keep connection alive
                yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
    
    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Cache-Control'
        }
    )


# GraphQL endpoint
app.add_url_rule(
    '/graphql',
    view_func=GraphQLView.as_view(
        'graphql',
        schema=schema,
        graphiql=True  # Enable GraphiQL interface for development
    )
)


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
        collector = TemperatureCollector(temperature_sensor)
        
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
    parser = argparse.ArgumentParser(description='aTemperature GraphQL monitoring server')
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
            
        logger.info(f"Starting aTemperature GraphQL server on {args.host}:{args.port}")
        logger.info("GraphQL endpoint: http://192.168.50.2:5000/graphql")
        logger.info("SSE endpoint: http://192.168.50.2:5000/events")
        logger.info("Press Ctrl+C to stop the server")
        
        # Run the Flask server
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=False,  # Disable reloader to avoid double initialization
            threaded=True  # Enable threading for SSE
        )
        
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        cleanup_application()
