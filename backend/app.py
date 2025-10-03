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


# Helper to present timestamps in local system time
from datetime import timezone as _tzmod, datetime as _dtmod

def _to_local_iso_unix(dt):
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
from graphene import ObjectType, String, Float, List as GrapheneList, Field, Int, Schema

# Import our modules
from models import init_database, db, TemperatureReading as DBTemperatureReading, HumidityReading as DBHumidityReading, MeterReading as DBMeterReading
from sensor_reader import TemperatureSensorReader, HumiditySensorReader
from usb_json_reader import USBJSONReader

# Configure logging (force ERROR by default)
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'ERROR').upper(), logging.ERROR),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/backend.log'),
        logging.StreamHandler()
    ]
)

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

# Configurable throttling system
THROTTLE_INTERVAL = 3600  # Default: 1 hour in seconds
last_throttle_time = 0    # Global throttle timestamp

def should_throttle():
    """Check if we should throttle based on global interval setting"""
    global last_throttle_time
    current_time = time.time()
    return current_time - last_throttle_time < THROTTLE_INTERVAL

def update_throttle_time():
    """Update the global throttle timestamp"""
    global last_throttle_time
    last_throttle_time = time.time()

def get_throttle_interval():
    """Get the current throttle interval"""
    return THROTTLE_INTERVAL

def set_throttle_interval(seconds):
    """Set the throttle interval (for configuration)"""
    global THROTTLE_INTERVAL
    THROTTLE_INTERVAL = max(1, int(seconds))  # Minimum 1 second


def scheduled_ocr_task():
    """Scheduled task to capture webcam and run OCR daily at 12:00"""
    logger.info("Running scheduled OCR task...")
    try:
        # Use Flask test client to call the OCR endpoint
        with app.test_client() as client:
            response = client.post('/webcam/ocr')
            result = response.get_json()

            if result and result.get('success'):
                logger.info(f"Scheduled OCR succeeded: {result.get('index')}")
            else:
                logger.warning(f"Scheduled OCR failed or no value recognized: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"Scheduled OCR task error: {e}")



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
    total_count = Int()
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

class MeterReading(ObjectType):
    id = Int()
    meter_value = String()
    timestamp = String()
    timestamp_unix = Float()
    ocr_engine = String()
    raw_ocr_text = String()
    sensor_type = String()
    sensor_id = String()

class MeterStatistics(ObjectType):
    count = Int()
    first_value = String()
    last_value = String()
    first_timestamp = String()
    last_timestamp = String()
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


# Time-based Statistics Types
class YearlyStatistics(ObjectType):
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    year = Int()

class MonthlyStatistics(ObjectType):
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    year = Int()
    month = Int()

class DailyStatistics(ObjectType):
    count = Int()
    average = Float()
    minimum = Float()
    maximum = Float()
    year = Int()
    month = Int()
    day = Int()


# GraphQL Queries
class Query(ObjectType):
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

    def resolve_health(self, info):
        try:
            stats = db.get_statistics(hours_back=1)
            sensor_info_dict = temperature_sensor.get_sensor_info() if temperature_sensor else {}
            
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
                recent_readings=stats.get('count', 0)
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                status="error",
                timestamp=datetime.now().astimezone().isoformat(),
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
                timestamp=_to_local_iso_unix(reading.timestamp)[0],
                timestamp_unix=_to_local_iso_unix(reading.timestamp)[1],
                sensor_type=reading.sensor_type,
                sensor_id=reading.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current temperature: {e}")
            return None

    def resolve_temperature_history(self, info, range="daily", limit=1000, year=None, month=None, day=None):
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

    

    def resolve_temperature_statistics(self, info, hours=24):
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
                timestamp=_to_local_iso_unix(reading.timestamp)[0],
                timestamp_unix=_to_local_iso_unix(reading.timestamp)[1],
                sensor_type=reading.sensor_type,
                sensor_id=reading.sensor_id
            )
        except Exception as e:
            logger.error(f'Error getting current humidity: {e}')
            return None
            
    def resolve_humidity_history(self, info, range='daily', limit=1000, year=None, month=None, day=None):
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
                timestamp=_to_local_iso_unix(r.timestamp)[0],
                timestamp_unix=_to_local_iso_unix(r.timestamp)[1],
                sensor_type=r.sensor_type,
                sensor_id=r.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current pressure: {e}")
            return None

    def resolve_pressure_history(self, info, range="daily", limit=1000, year=None, month=None, day=None):
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
                timestamp=_to_local_iso_unix(r.timestamp)[0],
                timestamp_unix=_to_local_iso_unix(r.timestamp)[1],
                sensor_type=r.sensor_type,
                sensor_id=r.sensor_id
            )
        except Exception as e:
            logger.error(f"Error getting current air quality: {e}")
            return None

    def resolve_air_quality_history(self, info, range="daily", limit=1000, year=None, month=None, day=None):
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

    # Meter reading resolvers
    def resolve_current_meter_reading(self, info):
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

    def resolve_meter_history(self, info, limit=1000, year=None, month=None, day=None):
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

    def resolve_meter_statistics(self, info, hours=24):
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
    def resolve_temperature_history_by_year(self, info, year):
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
    
    def resolve_temperature_history_by_month(self, info, year, month):
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
    
    def resolve_temperature_history_by_day(self, info, year, month, day):
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
    
    def resolve_yearly_statistics(self, info, year):
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
    
    def resolve_monthly_statistics(self, info, year, month):
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
    
    def resolve_daily_statistics(self, info, year, month, day):
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
    def __init__(self, logger):
        self.logger = logger
        self.error_count = 0
        self.max_errors = 10
        
    def process_sensor_data(self, data):
        """Process incoming sensor data from USB and update system."""
        try:
            # Use host wall-clock time; device timestamp is monotonic (ticks_ms), not epoch
            current_time = time.time()
            timestamp = datetime.fromtimestamp(current_time, tz=timezone.utc)

            # Use unified throttling system
            if should_throttle():
                return

            # Update throttle time for all operations
            update_throttle_time()

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

            # Store to database (controlled by unified throttling)
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
                data = sse_clients.get(timeout=get_throttle_interval())  # Much shorter timeout
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

        # Initialize scheduler for daily OCR task at 12:00
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            scheduled_ocr_task,
            'cron',
            hour=12,
            minute=0,
            id='daily_ocr_task',
            name='Daily OCR Meter Reading at 12:00'
        )
        scheduler.start()
        logger.info("Scheduler started - OCR task will run daily at 12:00")

        logger.info("Application initialized with USB sensor data")
        return True

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
            "flash": True,
            "brightness": 0,
            "contrast": 0,
            "saturation": 0,
            "exposure": 300,
            "gain": 2,
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
def run_ocr():
    """Run OCR on a freshly captured image using Gemini API - Used by scheduled daily task and can be called programmatically"""
    import base64
    import json
    import os
    import requests
    import re
    from datetime import datetime
    
    try:
        # Capture a fresh image (no auto-OCR elsewhere)
        with app.test_client() as client:
            cap_resp = client.post('/webcam/capture')
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
            api_key = gemini_config.get('api_key')
            model = gemini_config.get('model', 'gemini-2.0-flash-exp')
            prompt = gemini_config.get('prompt', 'Extract only the numbers from this image.')
            
            if not api_key:
                raise Exception("Gemini API key not configured")
            
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
def snapshot():
    """Snapshot endpoint - accessible via GET or POST for compatibility"""
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