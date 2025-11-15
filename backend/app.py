"""
Optimized GraphQL + SSE Flask application for aMonitoringHub monitoring system.

This module sets up a Flask web server that provides a GraphQL API for querying
sensor data and a Server-Sent Events (SSE) stream for real-time updates.

Features:
- GraphQL API using Graphene for flexible data querying.
- Server-Sent Events for pushing real-time sensor updates to clients.
- Background task scheduling with APScheduler for periodic jobs like OCR.
- Integration with various sensor types, including a USB JSON reader.
- Database management with SQLAlchemy for storing sensor readings.
- Configurable throttling system to manage data ingestion rates.
"""

import os
import sys
import json
import time
import logging
import argparse
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from queue import Queue
import threading


# Helper to present timestamps in local system time
from datetime import timezone as _tzmod, datetime as _dtmod

def _to_local_iso_unix(dt: Optional[datetime]) -> Tuple[Optional[str], Optional[float]]:
    """Converts a datetime object to a local timezone ISO 8601 string and a Unix timestamp.

    If the input datetime is naive, it is assumed to be in UTC.

    Args:
        dt: The datetime object to convert.

    Returns:
        A tuple containing the ISO 8601 formatted string and the Unix timestamp,
        or (None, None) if the input is None.
    """
    if dt is None:
        return None, None
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tzmod.utc).astimezone()
        else:
            dt = dt.astimezone()
        return dt.isoformat(), dt.timestamp()
    except Exception:
        now = _dtmod.now().astimezone()
        return now.isoformat(), now.timestamp()


from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from graphql import build_schema, graphql_sync
from graphql.execution import ExecutionResult

import graphene
from config import get_config as load_app_config

# Load application configuration
app_config = load_app_config()
from graphene import ObjectType, String, Float, List as GrapheneList, Field, Int, Schema

# Import our modules
from models import init_database, db, TemperatureReading as DBTemperatureReading, HumidityReading as DBHumidityReading, MeterReading as DBMeterReading
from sensor_reader import TemperatureSensorReader, HumiditySensorReader
from usb_json_reader import USBJSONReader

# Configure logging (use config.json instead of .env)
log_level = app_config.get('app', {}).get('log_level', 'ERROR').upper()
# Ensure USBJSONReader health checks are visible (use WARNING level minimum for health checks)
logging.basicConfig(
    level=getattr(logging, log_level, logging.ERROR),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/backend.log'),
        logging.StreamHandler()
    ]
)

# Set USBJSONReader logger to WARNING level to ensure health check messages are visible
# This ensures health check warnings are logged even when app log level is ERROR
_usb_logger = logging.getLogger(__name__ if '__main__' in __name__ else 'usb_json_reader')
_usb_logger.setLevel(logging.WARNING)
# Also set for the module name
logging.getLogger('usb_json_reader').setLevel(logging.WARNING)

# Enforce ERROR level on root and common noisy libraries
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.ERROR)
for _h in list(_root_logger.handlers):
    try:
        _h.setLevel(logging.ERROR)
    except Exception:
        pass

for _name in ['werkzeug', 'urllib3', 'requests', 'apscheduler', 'graphql', 'PIL', 'google', 'sqlalchemy']:
    try:
        logging.getLogger(_name).setLevel(logging.ERROR)
    except Exception:
        pass

logger = logging.getLogger(__name__)

# Flask application setup
app = Flask(__name__)
# Use environment variable for secret key, generate secure fallback if not set
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(32).hex())

# Enable CORS with restricted origins
allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000').split(',')
CORS(app, resources={
    r"/*": {
        "origins": allowed_origins,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Cache-Control"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

# Global variables
temperature_sensor = None
scheduler = None
usb_reader = None
sse_clients = Queue()

# Configurable throttling system
THROTTLE_INTERVAL = 3600  # Default: 1 hour in seconds
last_throttle_time = 0    # Global throttle timestamp

def should_throttle() -> bool:
    """Checks if an operation should be throttled based on the global interval.

    Returns:
        True if the time since the last throttled operation is less than
        THROTTLE_INTERVAL, False otherwise.
    """
    global last_throttle_time
    current_time = time.time()
    return current_time - last_throttle_time < THROTTLE_INTERVAL

def update_throttle_time():
    """Updates the global throttle timestamp to the current time."""
    global last_throttle_time
    last_throttle_time = time.time()

def get_throttle_interval() -> int:
    """Gets the current throttle interval in seconds.

    Returns:
        The value of THROTTLE_INTERVAL.
    """
    return THROTTLE_INTERVAL

def set_throttle_interval(seconds: int):
    """Sets the global throttle interval.

    Args:
        seconds: The new throttle interval in seconds. Must be at least 1.
    """
    global THROTTLE_INTERVAL
    THROTTLE_INTERVAL = max(1, int(seconds))  # Minimum 1 second


def scheduled_ocr_task():
    """Performs a scheduled OCR task by calling the /webcam/ocr endpoint.

    This function is intended to be run by a scheduler (e.g., APScheduler)
    to automatically read the electricity meter at a configured time.
    """
    import traceback
    logger.info("=== SCHEDULED OCR TASK STARTED ===")
    logger.info(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Use Flask test client to call the OCR endpoint
        with app.test_client() as client:
            logger.info("Making POST request to /webcam/ocr endpoint...")
            response = client.post('/webcam/ocr')
            logger.info(f"Response status code: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"OCR endpoint returned status {response.status_code}")
                return
                
            result = response.get_json()
            logger.info(f"OCR response: {result}")

            if result and result.get('success'):
                logger.info(f"✅ SCHEDULED OCR SUCCEEDED: {result.get('index')}")
            else:
                logger.error(f"❌ SCHEDULED OCR FAILED: {result.get('error', 'Unknown error')}")
                logger.error(f"Full OCR response: {result}")
    except Exception as e:
        logger.error(f"❌ SCHEDULED OCR TASK EXCEPTION: {e}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
    
    logger.info("=== SCHEDULED OCR TASK COMPLETED ===")



# GraphQL Types
class TemperatureReading(ObjectType):
    """GraphQL type for a single temperature reading."""
    id = Int()
    temperature_c = Float()
    timestamp = String()
    timestamp_unix = Float()
    sensor_type = String()
    sensor_id = String()


class TemperatureStatistics(ObjectType):
    """GraphQL type for temperature statistics over a given period."""
    count = Int()
    total_count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    min_timestamp = String()
    max_timestamp = String()
    hours_back = Int()


class HumidityReading(ObjectType):
    """GraphQL type for a single humidity reading."""
    id = Int()
    humidity_percent = Float()
    timestamp = String()
    timestamp_unix = Float()
    sensor_type = String()
    sensor_id = String()


class HumidityStatistics(ObjectType):
    """GraphQL type for humidity statistics over a given period."""
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    min_timestamp = String()
    max_timestamp = String()
    hours_back = Int()

class PressureReading(ObjectType):
    """GraphQL type for a single pressure reading."""
    id = Int()
    pressure_hpa = Float()
    timestamp = String()
    timestamp_unix = Float()
    sensor_type = String()
    sensor_id = String()

class PressureStatistics(ObjectType):
    """GraphQL type for pressure statistics over a given period."""
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    min_timestamp = String()
    max_timestamp = String()
    hours_back = Int()

class AirQualityReading(ObjectType):
    """GraphQL type for a single air quality reading."""
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
    """GraphQL type for air quality statistics over a given period."""
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    min_timestamp = String()
    max_timestamp = String()
    hours_back = Int()

class MeterReading(ObjectType):
    """GraphQL type for a single electricity meter reading from OCR."""
    id = Int()
    meter_value = String()
    timestamp = String()
    timestamp_unix = Float()
    ocr_engine = String()
    raw_ocr_text = String()
    sensor_type = String()
    sensor_id = String()

class MeterStatistics(ObjectType):
    """GraphQL type for meter reading statistics over a given period."""
    count = Int()
    first_value = String()
    last_value = String()
    first_timestamp = String()
    last_timestamp = String()
    hours_back = Int()


class SensorInfo(ObjectType):
    """GraphQL type for information about the active sensor."""
    sensor_type = String()
    sensor_id = String()
    initialized = String()
    active_sensor = String()


class USBSensorStatus(ObjectType):
    """GraphQL type for USB sensor status information."""
    name = String()
    connected = String()
    last_reading = Float()
    seconds_since_last_reading = Float()
    error = String()


class HealthStatus(ObjectType):
    """GraphQL type for the overall health status of the application."""
    status = String()
    timestamp = String()
    database = String()
    sensor = Field(SensorInfo)
    recent_readings = Int()
    usb_connection = String()
    bme280_status = Field(USBSensorStatus)
    mq135_status = Field(USBSensorStatus)


# Time-based Statistics Types
class YearlyStatistics(ObjectType):
    """GraphQL type for statistics aggregated by year."""
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    year = Int()

class MonthlyStatistics(ObjectType):
    """GraphQL type for statistics aggregated by month."""
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    year = Int()
    month = Int()

class DailyStatistics(ObjectType):
    """GraphQL type for statistics aggregated by day."""
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    year = Int()
    month = Int()
    day = Int()


# GraphQL Queries
class Query(ObjectType):
    """Defines the root GraphQL queries for the application."""
    health = Field(HealthStatus)
    current_temperature = Field(TemperatureReading)
    temperature_history = GrapheneList(
        TemperatureReading,
        range=String(default_value="daily"),
        year=Int(),
        month=Int(),
        day=Int(),
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
        year=Int(),
        month=Int(),
        day=Int(),
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
        year=Int(),
        month=Int(),
        day=Int(),
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
        year=Int(),
        month=Int(),
        day=Int(),
        limit=Int(default_value=1000)
    )
    air_quality_statistics = Field(
        AirQualityStatistics,
        hours=Int(default_value=24)
    )

    # Meter reading queries
    current_meter_reading = Field(MeterReading)
    meter_history = GrapheneList(
        MeterReading,
        year=Int(),
        month=Int(),
        day=Int(),
        limit=Int(default_value=1000)
    )
    meter_statistics = Field(
        MeterStatistics,
        hours=Int(default_value=24)
    )

    # Time-based statistics queries
    temperature_history_by_year = GrapheneList(
        TemperatureReading,
        year=Int(required=True)
    )
    temperature_history_by_month = GrapheneList(
        TemperatureReading,
        year=Int(required=True),
        month=Int(required=True)
    )
    temperature_history_by_day = GrapheneList(
        TemperatureReading,
        year=Int(required=True),
        month=Int(required=True),
        day=Int(required=True)
    )
    yearly_statistics = Field(
        YearlyStatistics,
        year=Int(required=True)
    )
    monthly_statistics = Field(
        MonthlyStatistics,
        year=Int(required=True),
        month=Int(required=True)
    )
    daily_statistics = Field(
        DailyStatistics,
        year=Int(required=True),
        month=Int(required=True),
        day=Int(required=True)
    )

    def resolve_health(self, info: Any) -> HealthStatus:
        """Resolves the health check query.

        Args:
            info: The GraphQL resolve info object.

        Returns:
            A HealthStatus object with the current application status.
        """
        try:
            stats = db.get_statistics(hours_back=1)
            sensor_info_dict = temperature_sensor.get_sensor_info() if temperature_sensor else {}

            # Get USB connection status
            global usb_reader
            usb_status = usb_reader.get_status() if usb_reader else {'connected': False, 'last_error': 'Not initialized', 'last_success_time': None}

            # USB is truly connected only if we have successful readings
            usb_truly_connected = usb_status['connected'] and usb_status['last_success_time'] is not None
            usb_connected = "connected" if usb_truly_connected else "disconnected"

            # Get BME280 sensor status
            current_time = time.time()
            bme280_last_reading = None
            bme280_seconds_ago = None
            bme280_connected_str = "disconnected"

            if hasattr(app, 'usb_data_processor') and app.usb_data_processor:
                if app.usb_data_processor.last_bme280_reading:
                    bme280_last_reading = app.usb_data_processor.last_bme280_reading
                    bme280_seconds_ago = current_time - bme280_last_reading
                    # Consider online if reading within last 120 seconds
                    bme280_connected_str = "online" if bme280_seconds_ago < 120 else "stale"

            # Get MQ135 sensor status
            mq135_last_reading = None
            mq135_seconds_ago = None
            mq135_connected_str = "disconnected"

            if hasattr(app, 'usb_data_processor') and app.usb_data_processor:
                if app.usb_data_processor.last_mq135_reading:
                    mq135_last_reading = app.usb_data_processor.last_mq135_reading
                    mq135_seconds_ago = current_time - mq135_last_reading
                    # Consider online if reading within last 120 seconds
                    mq135_connected_str = "online" if mq135_seconds_ago < 120 else "stale"

            return HealthStatus(
                status="ok",
                timestamp=datetime.now().astimezone().isoformat(),
                database="connected",
                sensor=SensorInfo(
                    sensor_type=sensor_info_dict.get('sensor_type', 'unknown'),
                    sensor_id=sensor_info_dict.get('active_sensor', {}).get('type', 'unknown'),
                    initialized="true" if sensor_info_dict.get('initialized') else "false",
                    active_sensor=str(sensor_info_dict.get('active_sensor', {}))
                ),
                recent_readings=stats.get('count', 0),
                usb_connection=usb_connected,
                bme280_status=USBSensorStatus(
                    name="BME280 (Temp/Humidity/Pressure)",
                    connected=bme280_connected_str,
                    last_reading=bme280_last_reading,
                    seconds_since_last_reading=bme280_seconds_ago,
                    error=usb_status['last_error'] if not usb_status['connected'] else None
                ),
                mq135_status=USBSensorStatus(
                    name="MQ135 (Air Quality)",
                    connected=mq135_connected_str,
                    last_reading=mq135_last_reading,
                    seconds_since_last_reading=mq135_seconds_ago,
                    error=usb_status['last_error'] if not usb_status['connected'] else None
                )
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                status="error",
                timestamp=datetime.now().astimezone().isoformat(),
                database="error",
                sensor=None,
                recent_readings=0,
                usb_connection="error",
                bme280_status=None,
                mq135_status=None
            )

    def resolve_current_temperature(self, info: Any) -> Optional[TemperatureReading]:
        """Resolves the query for the most recent temperature reading.

        Args:
            info: The GraphQL resolve info object.

        Returns:
            A TemperatureReading object or None if no readings are available.
        """
        try:
            recent_readings = db.get_recent_readings(limit=1)
            if not recent_readings:
                return None
                
            reading = recent_readings[0]
            return TemperatureReading(
                id=reading.id,
                temperature_c=reading.temperature_c,
                timestamp=_to_local_iso_unix(reading.timestamp)[0],
                timestamp_unix=_to_local_iso_unix(reading.timestamp)[1],
                sensor_type=reading.sensor_type,
                sensor_id=reading.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current temperature: {e}")
            return None

    def resolve_temperature_history(self, info: Any, range: str = "daily", limit: int = 1000, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> List[TemperatureReading]:
        """Resolves the query for historical temperature readings.

        Args:
            info: The GraphQL resolve info object.
            range: The time range to query ("daily", "weekly", "recent").
            limit: The maximum number of readings to return.
            year: The year to query for historical data.
            month: The month to query for historical data.
            day: The day to query for historical data.

        Returns:
            A list of TemperatureReading objects.
        """
        try:
            limit = min(limit, 5000)
            # Handle time-based queries first
            if year is not None:
                if month is not None and day is not None:
                    readings = db.get_readings_by_day(year, month, day)
                elif month is not None:
                    readings = db.get_readings_by_month(year, month)
                else:
                    readings = db.get_readings_by_year(year)
            elif range == "daily":
                readings = db.get_daily_readings(days_back=1)
            elif range == "weekly":
                readings = db.get_weekly_readings(weeks_back=1)
            elif range == "recent":
                readings = db.get_recent_readings(limit=limit)
            else:
                readings = db.get_recent_readings(limit=limit)
                
            # Ensure we return the most recent N items for time-range queries
            if range in ("daily", "weekly"):
                readings = readings[-limit:]
                
            result = []
            for reading in readings:
                result.append(TemperatureReading(
                    id=reading.id,
                    temperature_c=reading.temperature_c,
                    timestamp=_to_local_iso_unix(reading.timestamp)[0],
                    timestamp_unix=_to_local_iso_unix(reading.timestamp)[1],
                    sensor_type=reading.sensor_type,
                    sensor_id=reading.sensor_id
                ))
                
            result.sort(key=lambda x: x.timestamp_unix)
            return result
            
        except Exception as e:
            logger.error(f"Error getting temperature history: {e}")
            return []

    

    def resolve_temperature_statistics(self, info: Any, hours: int = 24) -> TemperatureStatistics:
        """Resolves the query for temperature statistics.

        Args:
            info: The GraphQL resolve info object.
            hours: The number of hours to look back for statistics.

        Returns:
            A TemperatureStatistics object.
        """
        try:
            stats = db.get_statistics(hours_back=hours)
            return TemperatureStatistics(
                count=stats['count'],
                total_count=stats['total_count'],
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
                count=0, total_count=0, average=0.0, minimum=0.0, maximum=0.0, hours_back=hours
            )

    def resolve_sensor_info(self, info: Any) -> Optional[SensorInfo]:
        """Resolves the query for information about the active sensor.

        Args:
            info: The GraphQL resolve info object.

        Returns:
            A SensorInfo object or None if no sensor is active.
        """
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
    def resolve_current_humidity(self, info: Any) -> Optional[HumidityReading]:
        """Resolves the query for the most recent humidity reading.

        Args:
            info: The GraphQL resolve info object.

        Returns:
            A HumidityReading object or None if no readings are available.
        """
        try:
            recent_readings = db.get_recent_humidity_readings(limit=1)
            if not recent_readings:
                return None
                
            reading = recent_readings[0]
            return HumidityReading(
                id=reading.id,
                humidity_percent=reading.humidity_percent,
                timestamp=_to_local_iso_unix(reading.timestamp)[0],
                timestamp_unix=_to_local_iso_unix(reading.timestamp)[1],
                sensor_type=reading.sensor_type,
                sensor_id=reading.sensor_id
            )
        except Exception as e:
            logger.error(f'Error getting current humidity: {e}')
            return None
            
    def resolve_humidity_history(self, info: Any, range: str = 'daily', limit: int = 1000, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> List[HumidityReading]:
        """Resolves the query for historical humidity readings.

        Args:
            info: The GraphQL resolve info object.
            range: The time range to query ("daily", "weekly", "recent").
            limit: The maximum number of readings to return.
            year: The year to query for historical data.
            month: The month to query for historical data.
            day: The day to query for historical data.

        Returns:
            A list of HumidityReading objects.
        """
        try:
            # Handle time-based queries
            if year is not None:
                if month is not None and day is not None:
                    readings = db.get_humidity_readings_by_day(year, month, day)
                elif month is not None:
                    readings = db.get_humidity_readings_by_month(year, month)
                else:
                    readings = db.get_humidity_readings_by_year(year)
            elif range == 'recent':
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
                    timestamp=_to_local_iso_unix(reading.timestamp)[0],
                    timestamp_unix=_to_local_iso_unix(reading.timestamp)[1],
                    sensor_type=reading.sensor_type,
                    sensor_id=reading.sensor_id
                )
                for reading in readings
            ]
        except Exception as e:
            logger.error(f'Error getting humidity history: {e}')
            return []
            
    def resolve_humidity_statistics(self, info: Any, hours: int = 24) -> HumidityStatistics:
        """Resolves the query for humidity statistics.

        Args:
            info: The GraphQL resolve info object.
            hours: The number of hours to look back for statistics.

        Returns:
            A HumidityStatistics object.
        """
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



    def resolve_current_pressure(self, info: Any) -> Optional[PressureReading]:
        """Resolves the query for the most recent pressure reading.

        Args:
            info: The GraphQL resolve info object.

        Returns:
            A PressureReading object or None if no readings are available.
        """
        try:
            readings = db.get_recent_pressure_readings(limit=1)
            if not readings:
                return None
            r = readings[0]
            return PressureReading(
                id=r.id,
                pressure_hpa=r.pressure_hpa,
                timestamp=_to_local_iso_unix(r.timestamp)[0],
                timestamp_unix=_to_local_iso_unix(r.timestamp)[1],
                sensor_type=r.sensor_type,
                sensor_id=r.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current pressure: {e}")
            return None

    def resolve_pressure_history(self, info: Any, range: str = "daily", limit: int = 1000, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> List[PressureReading]:
        """Resolves the query for historical pressure readings.

        Args:
            info: The GraphQL resolve info object.
            range: The time range to query ("daily", "weekly", "recent").
            limit: The maximum number of readings to return.
            year: The year to query for historical data.
            month: The month to query for historical data.
            day: The day to query for historical data.

        Returns:
            A list of PressureReading objects.
        """
        try:
            # Handle time-based queries
            if year is not None:
                if month is not None and day is not None:
                    readings = db.get_pressure_readings_by_day(year, month, day)
                elif month is not None:
                    readings = db.get_pressure_readings_by_month(year, month)
                else:
                    readings = db.get_pressure_readings_by_year(year)
            else:
                readings = db.get_recent_pressure_readings(limit=min(limit, 5000))

            result = [
                PressureReading(
                    id=r.id,
                    pressure_hpa=r.pressure_hpa,
                    timestamp=_to_local_iso_unix(r.timestamp)[0],
                    timestamp_unix=_to_local_iso_unix(r.timestamp)[1],
                    sensor_type=r.sensor_type,
                    sensor_id=r.sensor_id
                ) for r in readings
            ]
            result.sort(key=lambda x: x.timestamp_unix)
            return result
        except Exception as e:
            logger.error(f"Error getting pressure history: {e}")
            return []

    def resolve_pressure_statistics(self, info: Any, hours: int = 24) -> PressureStatistics:
        """Resolves the query for pressure statistics.

        Args:
            info: The GraphQL resolve info object.
            hours: The number of hours to look back for statistics.

        Returns:
            A PressureStatistics object.
        """
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

    def resolve_current_air_quality(self, info: Any) -> Optional[AirQualityReading]:
        """Resolves the query for the most recent air quality reading.

        Args:
            info: The GraphQL resolve info object.

        Returns:
            An AirQualityReading object or None if no readings are available.
        """
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
                timestamp=_to_local_iso_unix(r.timestamp)[0],
                timestamp_unix=_to_local_iso_unix(r.timestamp)[1],
                sensor_type=r.sensor_type,
                sensor_id=r.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current air quality: {e}")
            return None

    def resolve_air_quality_history(self, info: Any, range: str = "daily", limit: int = 1000, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> List[AirQualityReading]:
        """Resolves the query for historical air quality readings.

        Args:
            info: The GraphQL resolve info object.
            range: The time range to query ("daily", "weekly", "recent").
            limit: The maximum number of readings to return.
            year: The year to query for historical data.
            month: The month to query for historical data.
            day: The day to query for historical data.

        Returns:
            A list of AirQualityReading objects.
        """
        try:
            # Handle time-based queries
            if year is not None:
                if month is not None and day is not None:
                    readings = db.get_air_quality_readings_by_day(year, month, day)
                elif month is not None:
                    readings = db.get_air_quality_readings_by_month(year, month)
                else:
                    readings = db.get_air_quality_readings_by_year(year)
            else:
                readings = db.get_recent_air_quality_readings(limit=min(limit, 5000))

            result = [
                AirQualityReading(
                    id=r.id,
                    co2_ppm=r.co2_ppm,
                    nh3_ppm=r.nh3_ppm,
                    alcohol_ppm=r.alcohol_ppm,
                    aqi=r.aqi,
                    status=r.status,
                    timestamp=_to_local_iso_unix(r.timestamp)[0],
                    timestamp_unix=_to_local_iso_unix(r.timestamp)[1],
                    sensor_type=r.sensor_type,
                    sensor_id=r.sensor_id
                ) for r in readings
            ]
            result.sort(key=lambda x: x.timestamp_unix)
            return result
        except Exception as e:
            logger.error(f"Error getting air quality history: {e}")
            return []

    def resolve_air_quality_statistics(self, info: Any, hours: int = 24) -> AirQualityStatistics:
        """Resolves the query for air quality statistics.

        Args:
            info: The GraphQL resolve info object.
            hours: The number of hours to look back for statistics.

        Returns:
            An AirQualityStatistics object.
        """
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

    # Meter reading resolvers
    def resolve_current_meter_reading(self, info: Any) -> Optional[MeterReading]:
        """Resolves the query for the most recent meter reading.

        Args:
            info: The GraphQL resolve info object.

        Returns:
            A MeterReading object or None if no readings are available.
        """
        try:
            readings = db.get_recent_meter_readings(limit=1)
            if not readings:
                return None
            r = readings[0]
            return MeterReading(
                id=r.id,
                meter_value=r.meter_value,
                timestamp=_to_local_iso_unix(r.timestamp)[0],
                timestamp_unix=_to_local_iso_unix(r.timestamp)[1],
                ocr_engine=r.ocr_engine,
                raw_ocr_text=r.raw_ocr_text,
                sensor_type=r.sensor_type,
                sensor_id=r.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current meter reading: {e}")
            return None

    def resolve_meter_history(self, info: Any, limit: int = 1000, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> List[MeterReading]:
        """Resolves the query for historical meter readings.

        Args:
            info: The GraphQL resolve info object.
            limit: The maximum number of readings to return.
            year: The year to query for historical data.
            month: The month to query for historical data.
            day: The day to query for historical data.

        Returns:
            A list of MeterReading objects.
        """
        try:
            # Handle time-based queries
            if year is not None:
                if month is not None and day is not None:
                    readings = db.get_meter_readings_by_day(year, month, day)
                elif month is not None:
                    readings = db.get_meter_readings_by_month(year, month)
                else:
                    readings = db.get_meter_readings_by_year(year)
            else:
                readings = db.get_recent_meter_readings(limit=min(limit, 5000))

            result = [
                MeterReading(
                    id=r.id,
                    meter_value=r.meter_value,
                    timestamp=_to_local_iso_unix(r.timestamp)[0],
                    timestamp_unix=_to_local_iso_unix(r.timestamp)[1],
                    ocr_engine=r.ocr_engine,
                    raw_ocr_text=r.raw_ocr_text,
                    sensor_type=r.sensor_type,
                    sensor_id=r.sensor_id
                ) for r in readings
            ]
            result.sort(key=lambda x: x.timestamp_unix)
            return result
        except Exception as e:
            logger.error(f"Error getting meter history: {e}")
            return []

    def resolve_meter_statistics(self, info: Any, hours: int = 24) -> MeterStatistics:
        """Resolves the query for meter reading statistics.

        Args:
            info: The GraphQL resolve info object.
            hours: The number of hours to look back for statistics.

        Returns:
            A MeterStatistics object.
        """
        try:
            stats = db.get_meter_statistics(hours_back=hours)
            return MeterStatistics(
                count=stats.get('count', 0),
                first_value=stats.get('first_value'),
                last_value=stats.get('last_value'),
                first_timestamp=stats.get('first_timestamp'),
                last_timestamp=stats.get('last_timestamp'),
                hours_back=hours
            )
        except Exception as e:
            logger.error(f"Error getting meter statistics: {e}")
            return MeterStatistics(count=0, hours_back=hours)

    # Time-based resolvers
    def resolve_temperature_history_by_year(self, info: Any, year: int) -> List[TemperatureReading]:
        """Resolves the query for temperature history for a specific year.

        Args:
            info: The GraphQL resolve info object.
            year: The year to retrieve data for.

        Returns:
            A list of TemperatureReading objects for the specified year.
        """
        try:
            readings = db.get_readings_by_year(year)
            result = []
            for reading in readings:
                timestamp_str, timestamp_unix = _to_local_iso_unix(reading.timestamp)
                result.append(TemperatureReading(
                    id=reading.id,
                    temperature_c=reading.temperature_c,
                    timestamp=timestamp_str,
                    timestamp_unix=timestamp_unix,
                    sensor_type=reading.sensor_type,
                    sensor_id=reading.sensor_id
                ))
            return result
        except Exception as e:
            logger.error(f"Error getting temperature history for year {year}: {e}")
            return []
    
    def resolve_temperature_history_by_month(self, info: Any, year: int, month: int) -> List[TemperatureReading]:
        """Resolves the query for temperature history for a specific month.

        Args:
            info: The GraphQL resolve info object.
            year: The year of the month to retrieve data for.
            month: The month to retrieve data for.

        Returns:
            A list of TemperatureReading objects for the specified month.
        """
        try:
            readings = db.get_readings_by_month(year, month)
            result = []
            for reading in readings:
                timestamp_str, timestamp_unix = _to_local_iso_unix(reading.timestamp)
                result.append(TemperatureReading(
                    id=reading.id,
                    temperature_c=reading.temperature_c,
                    timestamp=timestamp_str,
                    timestamp_unix=timestamp_unix,
                    sensor_type=reading.sensor_type,
                    sensor_id=reading.sensor_id
                ))
            return result
        except Exception as e:
            logger.error(f"Error getting temperature history for {year}-{month}: {e}")
            return []
    
    def resolve_temperature_history_by_day(self, info: Any, year: int, month: int, day: int) -> List[TemperatureReading]:
        """Resolves the query for temperature history for a specific day.

        Args:
            info: The GraphQL resolve info object.
            year: The year of the day to retrieve data for.
            month: The month of the day to retrieve data for.
            day: The day to retrieve data for.

        Returns:
            A list of TemperatureReading objects for the specified day.
        """
        try:
            readings = db.get_readings_by_day(year, month, day)
            result = []
            for reading in readings:
                timestamp_str, timestamp_unix = _to_local_iso_unix(reading.timestamp)
                result.append(TemperatureReading(
                    id=reading.id,
                    temperature_c=reading.temperature_c,
                    timestamp=timestamp_str,
                    timestamp_unix=timestamp_unix,
                    sensor_type=reading.sensor_type,
                    sensor_id=reading.sensor_id
                ))
            return result
        except Exception as e:
            logger.error(f"Error getting temperature history for {year}-{month}-{day}: {e}")
            return []
    
    def resolve_yearly_statistics(self, info: Any, year: int) -> YearlyStatistics:
        """Resolves the query for yearly temperature statistics.

        Args:
            info: The GraphQL resolve info object.
            year: The year to calculate statistics for.

        Returns:
            A YearlyStatistics object.
        """
        try:
            stats = db.get_yearly_statistics(year)
            return YearlyStatistics(
                count=stats["count"],
                average=stats["average"],
                minimum=stats["minimum"],
                maximum=stats["maximum"],
                year=stats["year"]
            )
        except Exception as e:
            logger.error(f"Error getting yearly statistics for {year}: {e}")
            return YearlyStatistics(count=0, average=0.0, minimum=0.0, maximum=0.0, year=year)
    
    def resolve_monthly_statistics(self, info: Any, year: int, month: int) -> MonthlyStatistics:
        """Resolves the query for monthly temperature statistics.

        Args:
            info: The GraphQL resolve info object.
            year: The year of the month to calculate statistics for.
            month: The month to calculate statistics for.

        Returns:
            A MonthlyStatistics object.
        """
        try:
            stats = db.get_monthly_statistics(year, month)
            return MonthlyStatistics(
                count=stats["count"],
                average=stats["average"],
                minimum=stats["minimum"],
                maximum=stats["maximum"],
                year=stats["year"],
                month=stats["month"]
            )
        except Exception as e:
            logger.error(f"Error getting monthly statistics for {year}-{month}: {e}")
            return MonthlyStatistics(count=0, average=0.0, minimum=0.0, maximum=0.0, year=year, month=month)
    
    def resolve_daily_statistics(self, info: Any, year: int, month: int, day: int) -> DailyStatistics:
        """Resolves the query for daily temperature statistics.

        Args:
            info: The GraphQL resolve info object.
            year: The year of the day to calculate statistics for.
            month: The month of the day to calculate statistics for.
            day: The day to calculate statistics for.

        Returns:
            A DailyStatistics object.
        """
        try:
            stats = db.get_daily_statistics(year, month, day)
            return DailyStatistics(
                count=stats["count"],
                average=stats["average"],
                minimum=stats["minimum"],
                maximum=stats["maximum"],
                year=stats["year"],
                month=stats["month"],
                day=stats["day"]
            )
        except Exception as e:
            logger.error(f"Error getting daily statistics for {year}-{month}-{day}: {e}")
            return DailyStatistics(count=0, average=0.0, minimum=0.0, maximum=0.0, year=year, month=month, day=day)

# GraphQL Schema
schema = Schema(query=Query)


# USB Data Processor - Handles real sensor data from USB device
class USBDataProcessor:
    """Processes sensor data received from a USB JSON reader."""
    def __init__(self, logger: logging.Logger):
        """Initializes the USBDataProcessor.

        Args:
            logger: The logger instance to use for logging.
        """
        self.logger = logger
        self.error_count = 0
        self.max_errors = 10
        self.last_bme280_reading = None  # Track last BME280 (temp/humidity/pressure) reading time
        self.last_mq135_reading = None   # Track last MQ135 (air quality) reading time
        
    def process_sensor_data(self, data: Dict[str, Any]):
        """Processes a single data packet from the USB sensor.

        This method throttles operations, sends SSE updates, and stores
        the data in the database.

        Args:
            data: A dictionary containing the sensor data.
        """
        try:
            # Use host wall-clock time; device timestamp is monotonic (ticks_ms), not epoch
            current_time = time.time()
            timestamp = datetime.fromtimestamp(current_time, tz=timezone.utc)

            # IMPORTANT: Update timestamps FIRST, even if throttled
            # This ensures health checks reflect data reception, not just processing
            # Extract data to check what sensors are present
            temp_c = data.get('temperature_c')
            humidity_pct = data.get('humidity_percent')
            pressure_hpa = data.get('pressure_hpa')
            air_data = data.get('air', {})
            
            # Update timestamps immediately when data is received (before throttling check)
            # This prevents false stale detection when data is throttled
            if temp_c is not None or humidity_pct is not None or pressure_hpa is not None:
                self.last_bme280_reading = current_time
            
            if air_data and air_data.get('co2_ppm') is not None:
                self.last_mq135_reading = current_time

            # Use unified throttling system
            if should_throttle():
                return  # Skip processing but timestamps already updated above

            # Update throttle time for all operations
            update_throttle_time()

            # Data already extracted above for timestamp updates
            
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

            # Store to database (controlled by unified throttling)
            # Note: Timestamps already updated above (before throttling check)
            # This ensures health checks work even when data is throttled

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

            if air_data and air_data.get('co2_ppm') is not None:
                # Note: last_mq135_reading already updated above (before throttling check)
                db.add_air_quality_reading(
                    data=air_data,
                    sensor_type='mq135_usb',
                    sensor_id='micropython_device',
                    timestamp=timestamp
                )

            self.logger.info("Stored readings to database")

            self.error_count = 0  # Reset error count on success
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error processing USB sensor data: {e}")


# GraphQL endpoint
@app.route('/graphql', methods=['POST'])
def graphql_endpoint() -> Response:
    """Handles incoming GraphQL queries.

    Returns:
        A Flask Response object containing the GraphQL query result.
    """
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
def graphiql() -> str:
    """Serves the GraphiQL interactive API explorer.

    Returns:
        The HTML content for the GraphiQL interface.
    """
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
def events() -> Response:
    """Sets up a Server-Sent Events (SSE) stream for real-time updates.

    Yields:
        A stream of SSE-formatted data.
    """
    def event_stream():
        """Generator function for the SSE stream."""
        try:
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

            # Track last sensor status update
            last_sensor_status_time = 0
            sensor_status_interval = 1  # Send sensor status every 1 second

            while True:
                try:
                    data = sse_clients.get(timeout=1)  # Check every 1 second for sensor status updates
                    yield f"data: {json.dumps(data)}\n\n"
                    sse_clients.task_done()
                except:
                    # Send heartbeat to keep connection alive
                    current_time = time.time()

                    # Periodically send sensor status
                    if current_time - last_sensor_status_time >= sensor_status_interval:
                        try:
                            global usb_reader
                            usb_status = usb_reader.get_status() if usb_reader else {'connected': False, 'last_error': 'Not initialized', 'last_success_time': None}

                            # Get sensor status
                            bme280_connected = "disconnected"
                            mq135_connected = "disconnected"
                            bme280_seconds_ago = None
                            mq135_seconds_ago = None

                            if hasattr(app, 'usb_data_processor') and app.usb_data_processor:
                                if app.usb_data_processor.last_bme280_reading:
                                    bme280_seconds_ago = current_time - app.usb_data_processor.last_bme280_reading
                                    bme280_connected = "online" if bme280_seconds_ago < 120 else "stale"

                                if app.usb_data_processor.last_mq135_reading:
                                    mq135_seconds_ago = current_time - app.usb_data_processor.last_mq135_reading
                                    mq135_connected = "online" if mq135_seconds_ago < 120 else "stale"

                            sensor_status_message = {
                                'type': 'sensor_status',
                                'timestamp': current_time,
                                'data': {
                                    'usb_connected': usb_status['connected'],
                                    'usb_error': str(usb_status['last_error']) if usb_status['last_error'] else None,
                                    'bme280': {
                                        'status': bme280_connected,
                                        'seconds_since_reading': bme280_seconds_ago
                                    },
                                    'mq135': {
                                        'status': mq135_connected,
                                        'seconds_since_reading': mq135_seconds_ago
                                    }
                                }
                            }
                            yield f"data: {json.dumps(sensor_status_message)}\n\n"
                            last_sensor_status_time = current_time
                        except Exception as e:
                            logger.error(f"Error sending sensor status: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                    else:
                        # Regular heartbeat
                        yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': current_time})}\n\n"
        except GeneratorExit:
            # Handle client disconnect gracefully
            logger.debug("SSE generator exiting due to client disconnect")
            return
        except Exception as e:
            logger.error(f"SSE generator error: {e}")
            return

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
def serve_frontend() -> Response:
    """Serves the main frontend HTML file.

    Returns:
        A Flask Response object containing the index.html file.
    """
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_path, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename: str) -> Response:
    """Serves static files for the frontend.

    Args:
        filename: The path to the static file.

    Returns:
        A Flask Response object containing the requested static file.
    """
    frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    return send_from_directory(frontend_path, filename)


def initialize_application() -> bool:
    """Initializes all application components.

    This includes the database, sensor readers, and the background scheduler.

    Returns:
        True if initialization was successful, False otherwise.
    """
    global temperature_sensor, humidity_sensor, scheduler, usb_reader

    try:
        logger.info("Initializing database...")
        init_database()

        # Initialize USB reader instead of mock sensors
        logger.info("Initializing USB JSON reader...")
        cfg = load_app_config()
        usb_cfg = cfg.get('usb', {})
        processor = USBDataProcessor(logger)
        app.usb_data_processor = processor  # Store globally for health checks
        # Create USB reader with logger that has WARNING level set
        usb_logger = logging.getLogger('USBJSONReader')
        usb_logger.setLevel(logging.WARNING)
        # Ensure handlers are added if not present
        if not usb_logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.WARNING)
            usb_logger.addHandler(handler)
        usb_reader = USBJSONReader(device=usb_cfg.get('port'), baudrate=usb_cfg.get('baudrate', 115200), callback=processor.process_sensor_data, logger=usb_logger, processor=processor)
        usb_reader.start()
        logger.info("USB JSON reader started with health check monitoring")
        
        # Keep original sensor objects for compatibility but they won't be used
        logger.info("Initializing fallback sensors...")
        temperature_sensor = TemperatureSensorReader("mock")
        from sensor_reader import HumiditySensorReader
        humidity_sensor = HumiditySensorReader("mock")

        # Initialize scheduler for daily OCR task at 23:59
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            scheduled_ocr_task,
            'cron',
            hour=23,
            minute=59,
            id='daily_ocr_task',
            name='Daily OCR Meter Reading at 23:59'
        )
        scheduler.start()
        logger.info("Scheduler started - OCR task will run daily at 23:59")

        logger.info("Application initialized with USB sensor data")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        return False


def cleanup_application():
    """Cleans up application resources on shutdown."""
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
def get_config() -> Response:
    """Serves a minimal frontend configuration.

    Returns:
        A JSON response with basic configuration for the webcam and OCR.
    """
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
def capture_webcam() -> Response:
    """Captures an image from the ESP32-CAM via a POST request.

    This endpoint does not perform OCR automatically. It constructs a payload
    with camera settings and sends it to the configured webcam URL.

    Returns:
        A JSON response containing the base64-encoded image and metadata,
        or an error message if the capture fails.
    """
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
            "flash": True,
            "brightness": 0,
            "contrast": 0,
            "saturation": 0,
            "exposure": 300,
            "gain": 8,
            "special_effect": 1,
            "wb_mode": 0,
            "hmirror": False,
            "vflip": False,
            "timestamp": datetime.now().astimezone().isoformat(),
            "api_endpoint": webcam_url,
            "method": "POST",
            "content_type": "application/json"
        }
        # Merge user overrides (from frontend/backend caller)
        try:
            req_payload= request.get_json(silent=True) or {}
            if isinstance(req_payload, dict):
                payload.update(req_payload)
        except Exception:
            pass
        
        logger.info(f"Webcam capture payload: {json.dumps(payload)}")
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'image/jpeg',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'close'
        }
        import time, hashlib
        params = {'ts': int(time.time()*1000)}
        response = requests.post(webcam_url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()

        image_data = response.content
        md5 = hashlib.md5(image_data).hexdigest()
        logger.info(f"Webcam response: bytes={len(image_data)} md5={md5}")
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        return jsonify({
            "success": True,
            "image": f"data:image/jpeg;base64,{image_base64}",
            "timestamp": payload["timestamp"],
            "md5": md5,
            "source": "ESP32-CAM POST API"
        })
    except Exception as e:
        logger.error(f"Webcam capture failed: {e}")
        return jsonify({
            "success": False,
            "error": f"Capture failed: {str(e)}"
        }), 500


@app.route("/webcam/ocr", methods=['POST'])
def run_ocr() -> Response:
    """Captures a fresh image and runs OCR on it using the Gemini API.

    This endpoint is used by the scheduled daily task and can also be called
    programmatically. It handles image capture, calls the Gemini API,
    parses the result, and saves successful readings to the database.

    Returns:
        A JSON response with the OCR result, including the meter value,
        or an error message if the process fails.
    """
    import base64
    import json
    import os
    import requests
    from datetime import datetime
    
    try:
        # Capture a fresh image (no auto-OCR elsewhere)
        with app.test_client() as client:
            cap_resp = client.post('/webcam/capture', json={"gain": 5})
            cap_json = cap_resp.get_json()
        if not cap_json.get('success'):
            return jsonify({
                "success": False,
                "error": "Failed to capture image for OCR"
            }), 500
        
        # Decode base64
        image_b64 = cap_json['image']
        prefix = 'data:image/jpeg;base64,'
        if image_b64.startswith(prefix):
            image_b64 = image_b64[len(prefix):]
        
        # Load config for OCR
        with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
            config = json.load(f)
        
        # Try Gemini OCR
        try:
            gemini_config = config.get('ocr', {}).get('engines', {}).get('gemini', {})
            # Prioritize environment variable over config file for security
            api_key = os.environ.get('GEMINI_API_KEY') or gemini_config.get('api_key')
            model = gemini_config.get('model', 'gemini-2.5-flash-lite')
            prompt = gemini_config.get('prompt', 'Extract only the numbers from this image.')
            
            if not api_key:
                raise Exception("Gemini API key not configured. Set GEMINI_API_KEY environment variable.")
            
            # Prepare Gemini API request
            url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            },
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": image_b64
                                }
                            }
                        ]
                    }
                ]
            }
            
            # Make API call to Gemini
            ocr_response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )
            ocr_response.raise_for_status()
            
            result = ocr_response.json()
            ocr_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip()
            
            # Check if OCR failed according to the prompt (EXACT match)
            if 'Failed to read index!' in ocr_text:
                # Gemini wasn't confident - return the exact failure message
                return jsonify({
                    "success": False,
                    "engine": f"Google Gemini ({model})",
                    "image": cap_json['image'],
                    "timestamp": datetime.now().isoformat() + "Z",
                    "raw_ocr": ocr_text,
                    "error": "Failed to read index!"
                })
            
            # Extract numbers from response
            numbers = re.findall(r'\d+', ocr_text)
            
            # Find exactly 4-digit number
            four_digit = None
            for num in numbers:
                if len(num) == 4:
                    four_digit = num
                    break
            
            if four_digit:
                # Prepend "1" to the successfully read 4-digit number
                meter_value_with_prefix = "1" + four_digit

                # Save successful reading to database
                try:
                    db.add_meter_reading(
                        meter_value=meter_value_with_prefix,
                        ocr_engine=f"Google Gemini ({model})",
                        raw_ocr_text=ocr_text,
                        sensor_type="esp32cam_ocr",
                        sensor_id="cabana1_meter"
                    )
                    logger.info(f"Saved meter reading to database: {meter_value_with_prefix}")

                    return jsonify({
                        "success": True,
                        "index": meter_value_with_prefix,
                        "engine": f"Google Gemini ({model})",
                        "image": cap_json['image'],
                        "timestamp": datetime.now().isoformat() + "Z",
                        "raw_ocr": ocr_text
                    })
                except Exception as db_err:
                    logger.error(f"Failed to save meter reading to database: {db_err}")
                    return jsonify({
                        "success": False,
                        "error": f"OCR succeeded but database save failed: {str(db_err)}",
                        "engine": f"Google Gemini ({model})",
                        "image": cap_json['image'],
                        "timestamp": datetime.now().isoformat() + "Z",
                        "raw_ocr": ocr_text
                    }), 500
            else:
                return jsonify({
                    "success": False,
                    "engine": f"Google Gemini ({model})",
                    "image": cap_json['image'],
                    "timestamp": datetime.now().isoformat() + "Z",
                    "raw_ocr": ocr_text,
                    "error": "No 4-digit number found in response"
                })
                
        except Exception as ocr_error:
            logger.error(f"Gemini OCR error: {ocr_error}")
            return jsonify({
                "success": False,
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
            "engine": "Error"
        }), 500


@app.route("/snapshot", methods=['GET', 'POST'])
def snapshot() -> Response:
    """A compatibility endpoint for capturing a snapshot.

    This route supports both GET and POST requests and simply calls the
    main `capture_webcam` function.

    Returns:
        The JSON response from the `capture_webcam` function.
    """
    return capture_webcam()



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='aMonitoringHub GraphQL monitoring server (OPTIMIZED)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--threshold', type=float, default=0.1, help='Temperature change threshold for SSE (default: 0.1°C)')
    parser.add_argument('--throttle', type=int, default=3600, help='Throttle interval for all operations - SSE, DB storage, USB reading (default: 3600 seconds = 1 hour)')
    
    args = parser.parse_args()

    # Apply throttle interval from command line
    if hasattr(args, 'throttle'):
        set_throttle_interval(args.throttle)
        print(f"Throttle interval set to {args.throttle} seconds")

    
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
