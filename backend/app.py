"""
Optimized GraphQL + SSE Flask application for aMonitoringHub monitoring system.

Features:
- GraphQL API using pure graphene
- Server-Sent Events for real-time updates (ONLY when temperature changes)
- Temperature data collection service with change detection
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List
from queue import Queue
import threading

from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from graphql import build_schema, graphql_sync
from graphql.execution import ExecutionResult

import graphene
from config import get_config as load_app_config
from graphene import ObjectType, String, Float, List as GrapheneList, Field, Int, Schema

# Import our modules
from models import init_database, db, TemperatureReading as DBTemperatureReading, HumidityReading as DBHumidityReading
from sensor_reader import TemperatureSensorReader, HumiditySensorReader
from usb_json_reader import USBJSONReader

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL','INFO').upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask application setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'temperature-monitoring-graphql-2025'

# Enable CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Cache-Control"]
    }
})

# Global variables
temperature_sensor = None
scheduler = None
usb_reader = None
sse_clients = Queue()
last_db_store = time.time()  # Track when we last stored to DB


# GraphQL Types (same as before)
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
    min_timestamp = String()
    max_timestamp = String()
    hours_back = Int()




class HumidityReading(ObjectType):
    id = Int()
    humidity_percent = Float()
    timestamp = String()
    timestamp_unix = Float()
    sensor_type = String()
    sensor_id = String()


class HumidityStatistics(ObjectType):
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    min_timestamp = String()
    max_timestamp = String()
    hours_back = Int()

class PressureReading(ObjectType):
    id = Int()
    pressure_hpa = Float()
    timestamp = String()
    timestamp_unix = Float()
    sensor_type = String()
    sensor_id = String()

class PressureStatistics(ObjectType):
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    min_timestamp = String()
    max_timestamp = String()
    hours_back = Int()

class AirQualityReading(ObjectType):
    id = Int()
    co2_ppm = Float()
    nh3_ppm = Float()
    alcohol_ppm = Float()
    aqi = Int()
    status = String()
    timestamp = String()
    timestamp_unix = Float()
    sensor_type = String()
    sensor_id = String()

class AirQualityStatistics(ObjectType):
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    min_timestamp = String()
    max_timestamp = String()
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
    health = Field(HealthStatus)
    current_temperature = Field(TemperatureReading)
    temperature_history = GrapheneList(
        TemperatureReading,
        range=String(default_value="daily"),
        limit=Int(default_value=1000)
    )
    temperature_statistics = Field(
        TemperatureStatistics,
        hours=Int(default_value=24)
    )
    sensor_info = Field(SensorInfo)

    # Humidity queries
    current_humidity = Field(HumidityReading)
    humidity_history = GrapheneList(
        HumidityReading,
        range=String(default_value="daily"),
        limit=Int(default_value=1000)
    )
    humidity_statistics = Field(
        HumidityStatistics,
        hours=Int(default_value=24)
    )


    # Pressure queries
    current_pressure = Field(PressureReading)
    pressure_history = GrapheneList(
        PressureReading,
        range=String(default_value="daily"),
        limit=Int(default_value=1000)
    )
    pressure_statistics = Field(
        PressureStatistics,
        hours=Int(default_value=24)
    )

    # Air quality queries
    current_air_quality = Field(AirQualityReading)
    air_quality_history = GrapheneList(
        AirQualityReading,
        range=String(default_value="daily"),
        limit=Int(default_value=1000)
    )
    air_quality_statistics = Field(
        AirQualityStatistics,
        hours=Int(default_value=24)
    )

    def resolve_health(self, info):
        try:
            stats = db.get_statistics(hours_back=1)
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
            limit = min(limit, 5000)
            
            if range == "daily":
                readings = db.get_daily_readings(days_back=1)
            elif range == "weekly":
                readings = db.get_weekly_readings(weeks_back=1)
            elif range == "recent":
                readings = db.get_recent_readings(limit=limit)
            else:
                readings = db.get_recent_readings(limit=limit)
                
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
                min_timestamp=stats.get('min_timestamp'),
                max_timestamp=stats.get('max_timestamp'),
                hours_back=stats['hours_back']
            )
        except Exception as e:
            logger.error(f"Error getting temperature statistics: {e}")
            return TemperatureStatistics(
                count=0, average=0.0, minimum=0.0, maximum=0.0, hours_back=hours
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
            return None
        except Exception as e:
            logger.error(f"Error getting sensor info: {e}")
            return None



    # Humidity resolvers
    def resolve_current_humidity(self, info):
        try:
            recent_readings = db.get_recent_humidity_readings(limit=1)
            if not recent_readings:
                return None
                
            reading = recent_readings[0]
            return HumidityReading(
                id=reading.id,
                humidity_percent=reading.humidity_percent,
                timestamp=reading.timestamp.isoformat(),
                timestamp_unix=reading.timestamp.timestamp(),
                sensor_type=reading.sensor_type,
                sensor_id=reading.sensor_id
            )
        except Exception as e:
            logger.error(f'Error getting current humidity: {e}')
            return None
            
    def resolve_humidity_history(self, info, range='daily', limit=1000):
        try:
            if range == 'recent':
                readings = db.get_recent_humidity_readings(limit=limit)
            elif range == 'daily':
                readings = db.get_recent_humidity_readings(limit=min(limit, 1440))  # Max 1 day of minute readings
            elif range == 'weekly':
                readings = db.get_recent_humidity_readings(limit=min(limit, 10080))  # Max 1 week of minute readings
            else:
                readings = db.get_recent_humidity_readings(limit=limit)
                
            return [
                HumidityReading(
                    id=reading.id,
                    humidity_percent=reading.humidity_percent,
                    timestamp=reading.timestamp.isoformat(),
                    timestamp_unix=reading.timestamp.timestamp(),
                    sensor_type=reading.sensor_type,
                    sensor_id=reading.sensor_id
                )
                for reading in readings
            ]
        except Exception as e:
            logger.error(f'Error getting humidity history: {e}')
            return []
            
    def resolve_humidity_statistics(self, info, hours=24):
        try:
            stats = db.get_humidity_statistics(hours_back=hours)
            
            if stats.get('count', 0) > 0:
                return HumidityStatistics(
                    count=stats['count'],
                    average=round(stats['avg'], 2),
                    minimum=stats['min'],
                    maximum=stats['max'],
                    min_timestamp=stats.get('min_timestamp'),
                    max_timestamp=stats.get('max_timestamp'),
                    hours_back=hours
                )
            return HumidityStatistics(
                count=0, average=0.0, minimum=0.0, maximum=0.0, hours_back=hours
            )
        except Exception as e:
            logger.error(f'Error getting humidity statistics: {e}')
            return HumidityStatistics(
                count=0, average=0.0, minimum=0.0, maximum=0.0, hours_back=hours
            )



    def resolve_current_pressure(self, info):
        try:
            readings = db.get_recent_pressure_readings(limit=1)
            if not readings:
                return None
            r = readings[0]
            return PressureReading(
                id=r.id,
                pressure_hpa=r.pressure_hpa,
                timestamp=r.timestamp.isoformat(),
                timestamp_unix=r.timestamp.timestamp(),
                sensor_type=r.sensor_type,
                sensor_id=r.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current pressure: {e}")
            return None

    def resolve_pressure_history(self, info, range="daily", limit=1000):
        try:
            readings = db.get_recent_pressure_readings(limit=min(limit, 5000))
            result = [
                PressureReading(
                    id=r.id,
                    pressure_hpa=r.pressure_hpa,
                    timestamp=r.timestamp.isoformat(),
                    timestamp_unix=r.timestamp.timestamp(),
                    sensor_type=r.sensor_type,
                    sensor_id=r.sensor_id
                ) for r in readings
            ]
            result.sort(key=lambda x: x.timestamp_unix)
            return result
        except Exception as e:
            logger.error(f"Error getting pressure history: {e}")
            return []

    def resolve_pressure_statistics(self, info, hours=24):
        try:
            stats = db.get_pressure_statistics(hours_back=hours)
            return PressureStatistics(
                count=stats['count'],
                average=stats['average'],
                minimum=stats['minimum'],
                maximum=stats['maximum'],
                min_timestamp=stats.get('min_timestamp'),
                max_timestamp=stats.get('max_timestamp'),
                hours_back=hours
            )
        except Exception as e:
            logger.error(f"Error getting pressure statistics: {e}")
            return PressureStatistics(count=0, average=0.0, minimum=0.0, maximum=0.0, hours_back=hours)

    def resolve_current_air_quality(self, info):
        try:
            readings = db.get_recent_air_quality_readings(limit=1)
            if not readings:
                return None
            r = readings[0]
            return AirQualityReading(
                id=r.id,
                co2_ppm=r.co2_ppm,
                nh3_ppm=r.nh3_ppm,
                alcohol_ppm=r.alcohol_ppm,
                aqi=r.aqi,
                status=r.status,
                timestamp=r.timestamp.isoformat(),
                timestamp_unix=r.timestamp.timestamp(),
                sensor_type=r.sensor_type,
                sensor_id=r.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current air quality: {e}")
            return None

    def resolve_air_quality_history(self, info, range="daily", limit=1000):
        try:
            readings = db.get_recent_air_quality_readings(limit=min(limit, 5000))
            result = [
                AirQualityReading(
                    id=r.id,
                    co2_ppm=r.co2_ppm,
                    nh3_ppm=r.nh3_ppm,
                    alcohol_ppm=r.alcohol_ppm,
                    aqi=r.aqi,
                    status=r.status,
                    timestamp=r.timestamp.isoformat(),
                    timestamp_unix=r.timestamp.timestamp(),
                    sensor_type=r.sensor_type,
                    sensor_id=r.sensor_id
                ) for r in readings
            ]
            result.sort(key=lambda x: x.timestamp_unix)
            return result
        except Exception as e:
            logger.error(f"Error getting air quality history: {e}")
            return []

    def resolve_air_quality_statistics(self, info, hours=24):
        try:
            stats = db.get_air_quality_statistics(hours_back=hours)
            return AirQualityStatistics(
                count=stats['count'],
                average=stats['average'],
                minimum=stats['minimum'],
                maximum=stats['maximum'],
                min_timestamp=stats.get('min_timestamp'),
                max_timestamp=stats.get('max_timestamp'),
                hours_back=hours
            )
        except Exception as e:
            logger.error(f"Error getting air quality statistics: {e}")
            return AirQualityStatistics(count=0, average=0.0, minimum=0.0, maximum=0.0, hours_back=hours)

# GraphQL Schema
schema = Schema(query=Query)


# USB Data Processor - Handles real sensor data from USB device
class USBDataProcessor:
    def __init__(self, logger):
        self.last_emit_time = 0
        self.logger = logger
        self.error_count = 0
        self.max_errors = 10
        
    def process_sensor_data(self, data):
        """Process incoming sensor data from USB and update system."""
        global last_db_store
        try:
            # Use host wall-clock time; device timestamp is monotonic (ticks_ms), not epoch
            current_time = time.time()
            timestamp = datetime.fromtimestamp(current_time, tz=timezone.utc)

            # Throttle to 30s intervals
            if current_time - self.last_emit_time < 30:
                return
            
            # Extract data
            temp_c = data.get('temperature_c')
            humidity_pct = data.get('humidity_percent')
            pressure_hpa = data.get('pressure_hpa')
            air_data = data.get('air', {})
            
            # Send SSE updates for temperature
            if temp_c is not None:
                temperature_data = {
                    'type': 'temperature_update',
                    'data': {
                        'temperature_c': round(temp_c, 2),
                        'timestamp': current_time,
                        'timestamp_iso': timestamp.isoformat(),
                        'sensor_type': 'bme280_usb',
                        'sensor_id': 'micropython_device',
                        'change_reason': 'usb_update'
                    }
                }
                try:
                    sse_clients.put_nowait(temperature_data)
                    self.logger.info(f"Temperature SSE: {temp_c:.2f}°C")
                except:
                    pass  # Queue full

            # Send SSE updates for humidity
            if humidity_pct is not None:
                humidity_data = {
                    'type': 'humidity_update',
                    'data': {
                        'humidity_percent': round(humidity_pct, 1),
                        'timestamp': current_time,
                        'timestamp_iso': timestamp.isoformat(),
                        'sensor_type': 'bme280_usb',
                        'sensor_id': 'micropython_device'
                    }
                }
                try:
                    sse_clients.put_nowait(humidity_data)
                    self.logger.info(f"Humidity SSE: {humidity_pct:.1f}%")
                except:
                    pass

            # Send SSE updates for pressure
            if pressure_hpa is not None:
                pressure_data = {
                    'type': 'pressure_update',
                    'data': {
                        'pressure_hpa': round(pressure_hpa, 1),
                        'timestamp': current_time,
                        'timestamp_iso': timestamp.isoformat(),
                        'sensor_type': 'bme280_usb',
                        'sensor_id': 'micropython_device'
                    }
                }
                try:
                    sse_clients.put_nowait(pressure_data)
                    self.logger.info(f"Pressure SSE: {pressure_hpa:.1f} hPa")
                except:
                    pass

            # Send SSE updates for air quality
            if air_data.get('co2_ppm') is not None:
                air_quality_data = {
                    'type': 'air_quality_update',
                    'data': {
                        'co2_ppm': round(air_data.get('co2_ppm', 0), 1),
                        'aqi': air_data.get('aqi', 0),
                        'status': air_data.get('status', 'Unknown'),
                        'nh3_ppm': air_data.get('nh3_ppm'),
                        'alcohol_ppm': air_data.get('alcohol_ppm'),
                        'timestamp': current_time,
                        'timestamp_iso': timestamp.isoformat(),
                        'sensor_type': 'mq135_usb',
                        'sensor_id': 'micropython_device'
                    }
                }
                try:
                    sse_clients.put_nowait(air_quality_data)
                    self.logger.info(f"Air Quality SSE: {air_data.get('co2_ppm', 0):.1f} ppm CO2")
                except:
                    pass

            # Store to database periodically (every 30 seconds to avoid overload)
            if current_time - last_db_store >= 30:
                if temp_c is not None:
                    db.add_temperature_reading(
                        temperature_c=temp_c,
                        sensor_type='bme280_usb',
                        sensor_id='micropython_device',
                        timestamp=timestamp
                    )
                
                if humidity_pct is not None:
                    db.add_humidity_reading(
                        humidity_percent=humidity_pct,
                        sensor_type='bme280_usb',
                        sensor_id='micropython_device',
                        timestamp=timestamp
                    )
                
                if pressure_hpa is not None:
                    db.add_pressure_reading(
                        pressure_hpa=pressure_hpa,
                        sensor_type='bme280_usb',
                        sensor_id='micropython_device',
                        timestamp=timestamp
                    )
                if air_data:
                    db.add_air_quality_reading(
                        data=air_data,
                        sensor_type='mq135_usb',
                        sensor_id='micropython_device',
                        timestamp=timestamp
                    )
                self.last_emit_time = current_time
                last_db_store = current_time
                self.logger.info("Stored readings to database")
            
            self.error_count = 0  # Reset error count on success
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error processing USB sensor data: {e}")


# GraphQL endpoint
@app.route('/graphql', methods=['POST'])
def graphql_endpoint():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        query = data.get('query')
        variables = data.get('variables', {})
        
        if not query:
            return jsonify({'error': 'No query provided'}), 400
        
        # Execute GraphQL query
        result = schema.execute(query, variables=variables)
        
        response_data = {'data': result.data}
        if result.errors:
            response_data['errors'] = [str(error) for error in result.errors]
            
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"GraphQL endpoint error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# GraphiQL interface for development
@app.route('/graphql', methods=['GET'])
def graphiql():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>GraphiQL</title>
        <link href="https://unpkg.com/graphiql@1.4.7/graphiql.min.css" rel="stylesheet" />
    </head>
    <body style="margin: 0;">
        <div id="graphiql" style="height: 100vh;"></div>
        <script crossorigin src="https://unpkg.com/react@17/umd/react.production.min.js"></script>
        <script crossorigin src="https://unpkg.com/react-dom@17/umd/react-dom.production.min.js"></script>
        <script crossorigin src="https://unpkg.com/graphiql@1.4.7/graphiql.min.js"></script>
        <script>
            const fetcher = (graphQLParams) =>
                fetch('/graphql', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(graphQLParams),
                })
                .then(response => response.json());

            ReactDOM.render(
                React.createElement(GraphiQL, { fetcher }),
                document.getElementById('graphiql')
            );
        </script>
    </body>
    </html>
    '''


# Server-Sent Events (optimized)
@app.route('/events')
def events():
    def event_stream():
        # Send immediate connection confirmation with latest data
        yield f"data: {json.dumps({'type': 'connected', 'timestamp': time.time()})}\n\n"
        
        # Immediately send latest temperature from database
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT temperature_c, timestamp, sensor_type, sensor_id FROM temperature_readings ORDER BY timestamp DESC LIMIT 1")
                temp_row = cursor.fetchone()
                if temp_row:
                    temp_data = {
                        'temperature_c': temp_row[0],
                        'timestamp_iso': temp_row[1],
                        'sensor_type': temp_row[2],
                        'sensor_id': temp_row[3]
                    }
                    sse_message = {
                        'type': 'temperature_update',
                        'data': temp_data,
                        'timestamp': temp_row[1]
                    }
                    yield f"data: {json.dumps(sse_message)}\n\n"
                
                # Also send latest humidity
                cursor.execute("SELECT humidity_percent, timestamp, sensor_type, sensor_id FROM humidity_readings ORDER BY timestamp DESC LIMIT 1")
                humidity_row = cursor.fetchone()
                if humidity_row:
                    humidity_data = {
                        'humidity_percent': humidity_row[0],
                        'timestamp_iso': humidity_row[1],
                        'sensor_type': humidity_row[2],
                        'sensor_id': humidity_row[3]
                    }
                    sse_message = {
                        'type': 'humidity_update',
                        'data': humidity_data,
                        'timestamp': humidity_row[1]
                    }
                    yield f"data: {json.dumps(sse_message)}\n\n"
        except Exception as e:
            print(f"Error sending initial data: {e}")
        
        while True:
            try:
                data = sse_clients.get(timeout=5)  # Much shorter timeout
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


# Static file serving
@app.route('/')
def serve_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_path, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_path, filename)


def initialize_application():
    global temperature_sensor, humidity_sensor, scheduler, usb_reader
    
    try:
        logger.info("Initializing database...")
        init_database()
        
        # Initialize USB reader instead of mock sensors
        logger.info("Initializing USB JSON reader...")
        cfg = load_app_config()
        usb_cfg = cfg.get('usb', {})
        processor = USBDataProcessor(logger)
        usb_reader = USBJSONReader(device=usb_cfg.get('port'), baudrate=usb_cfg.get('baudrate', 115200), callback=processor.process_sensor_data, logger=logger)
        usb_reader.start()
        logger.info("USB JSON reader started")
        
        # Keep original sensor objects for compatibility but they won't be used
        logger.info("Initializing fallback sensors...")
        temperature_sensor = TemperatureSensorReader("mock")
        from sensor_reader import HumiditySensorReader
        humidity_sensor = HumiditySensorReader("mock")
        
        # No scheduler needed - USB reader handles real-time data
        logger.info("Application initialized with USB sensor data")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        return False
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        return False


def cleanup_application():
    global scheduler, usb_reader
    
    logger.info("Cleaning up application...")
    
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler shutdown complete")
    
    if usb_reader:
        usb_reader.stop()
        logger.info("USB reader stopped")
        
    if db:
        db.close()
        logger.info("Database connections closed")



@app.route("/config")
def get_config():
    """Serve frontend configuration"""
    try:
        import json
        import os
        
        # Return minimal working config
        return jsonify({
            "webcam": {
                "url": "http://192.168.50.3/snapshot",
                "enabled": True,
                "title": "📹 Cabana 1 Electricity Meter"
            },
            "ocr": {
                "enabled": True
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/webcam/capture", methods=['POST'])
def capture_webcam():
    """Capture image from ESP32-CAM using POST API - NO automatic OCR"""
    import base64
    import json
    import os
    import requests
    from datetime import datetime, timezone
    
    try:
        # Load config
        with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
            config = json.load(f)
        
        webcam_url = config.get('webcam', {}).get('url', 'http://192.168.50.3/snapshot')
        
        # Prepare the exact payload as specified
        payload = {
            "resolution": "UXGA",
            "flash": "on",
            "brightness": 0,
            "contrast": 0,
            "saturation": 0,
            "exposure": 300,
            "gain": 8,
            "special_effect": 1,
            "wb_mode": 0,
            "hmirror": False,
            "vflip": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "api_endpoint": webcam_url,
            "method": "POST",
            "content_type": "application/json"
        }
        
        logger.info(f"Webcam capture payload: {json.dumps(payload)}")
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(webcam_url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        
        image_data = response.content
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": f"data:image/jpeg;base64,{image_base64}",
            "timestamp": payload["timestamp"],
            "source": "ESP32-CAM POST API"
        })
    except Exception as e:
        logger.error(f"Webcam capture failed: {e}")
        return jsonify({
            "success": False,
            "error": f"Capture failed: {str(e)}"
        }), 500


@app.route("/webcam/ocr", methods=['POST'])
def run_ocr():
    """Run OCR on a freshly captured image - Manual trigger only"""
    import base64
    import json
    import os
    import requests
    from datetime import datetime
    
    try:
        # Capture a fresh image (no auto-OCR elsewhere)
        cap_resp = capture_webcam()
        cap_json = json.loads(cap_resp.get_data(as_text=True))
        if not cap_json.get('success'):
            return jsonify({
                "success": False,
                "error": "Failed to capture image for OCR",
                "index": "-----"
            }), 500
        
        # Decode base64
        image_b64 = cap_json['image']
        prefix = 'data:image/jpeg;base64,'
        if image_b64.startswith(prefix):
            image_b64 = image_b64[len(prefix):]
        image_data = base64.b64decode(image_b64)
        
        # Load config for OCR
        with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
            config = json.load(f)
        
        # Try Gemini OCR
        try:
            import google.generativeai as genai
            from PIL import Image
            import io, re
            
            api_key = config.get('ocr', {}).get('engines', {}).get('gemini', {}).get('api_key')
            if not api_key:
                raise Exception("Gemini API key not configured")
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(config.get('ocr', {}).get('engines', {}).get('gemini', {}).get('model', 'gemini-1.5-flash'))
            image = Image.open(io.BytesIO(image_data))
            prompt = "Extract only the numbers from this electricity meter display. Return only digits, no text."
            ocr_response = model.generate_content([prompt, image])
            ocr_text = (ocr_response.text or '').strip()
            numbers = re.findall(r'\d+', ocr_text)
            
            return jsonify({
                "success": True if numbers else False,
                "index": max(numbers, key=len) if numbers else "-----",
                "engine": "Gemini AI",
                "image": cap_json['image'],
                "timestamp": datetime.now().isoformat() + "Z",
                "raw_ocr": ocr_text
            })
        except Exception as ocr_error:
            return jsonify({
                "success": False,
                "index": "-----",
                "error": f"Reading index failed: {str(ocr_error)}",
                "engine": "Gemini AI - Error",
                "image": cap_json['image'],
                "timestamp": datetime.now().isoformat() + "Z"
            })
    except Exception as e:
        logger.error(f"Index reading failed: {e}")
        return jsonify({
            "success": False,
            "error": f"Reading index failed: {str(e)}",
            "index": "-----",
            "engine": "Error"
        }), 500


# Deprecate legacy /snapshot route for webcam - keep but no auto OCR
@app.route("/snapshot", methods=['GET', 'POST'])
def snapshot():
    """Snapshot endpoint - accessible via GET or POST for compatibility"""
    return capture_webcam()



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='aMonitoringHub GraphQL monitoring server (OPTIMIZED)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--threshold', type=float, default=0.1, help='Temperature change threshold for SSE (default: 0.1°C)')
    parser.add_argument('--heartbeat', type=int, default=30, help='Max seconds between SSE updates (default: 30)')
    
    args = parser.parse_args()
    
    try:
        if not initialize_application():
            logger.error("Failed to initialize application")
            sys.exit(1)
            
        logger.info(f"Starting OPTIMIZED aMonitoringHub GraphQL server on {args.host}:{args.port}")
        logger.info("GraphQL endpoint: http://192.168.50.2:5000/graphql")
        logger.info("SSE endpoint: http://192.168.50.2:5000/events")
        logger.info(f"SSE optimization: Updates only when temp changes >= {args.threshold}°C")
        logger.info("Press Ctrl+C to stop the server")
        
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=False,
            threaded=True
        )
        
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        cleanup_application()
