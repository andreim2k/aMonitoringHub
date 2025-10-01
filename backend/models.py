"""
SQLAlchemy models for aMonitoringHub application.
"""

from datetime import datetime, timezone, timedelta
import time
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, Float, DateTime, String, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
import logging
import os
import shutil

Base = declarative_base()


class TemperatureReading(Base):
    """Temperature reading model."""
    
    __tablename__ = 'temperature_readings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    timestamp_unix = Column(Float, nullable=False, default=lambda: time.time())
    temperature_c = Column(Float, nullable=False)
    sensor_type = Column(String(50), nullable=False, default='unknown')
    sensor_id = Column(String(100), nullable=False, default='default')
    
    # Add indices for common queries
    __table_args__ = (
        Index('idx_timestamp', 'timestamp'),
        Index('idx_sensor_timestamp', 'sensor_id', 'timestamp'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'timestamp_unix': self.timestamp.timestamp() if self.timestamp else None,
            'temperature_c': self.temperature_c,
            'sensor_type': self.sensor_type,
            'sensor_id': self.sensor_id
        }
    
    def __repr__(self):
        return f"<TemperatureReading(id={self.id}, temp={self.temperature_c}°C, sensor={self.sensor_id}, time={self.timestamp})>"




class HumidityReading(Base):
    """Humidity reading model."""
    
    __tablename__ = 'humidity_readings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    timestamp_unix = Column(Float, nullable=False, default=lambda: time.time())
    humidity_percent = Column(Float, nullable=False)
    sensor_type = Column(String(50), nullable=False, default='unknown')
    sensor_id = Column(String(100), nullable=False, default='default')
    
    # Add indices for common queries
    __table_args__ = (
        Index('idx_humidity_timestamp', 'timestamp'),
        Index('idx_humidity_sensor_timestamp', 'sensor_id', 'timestamp'),
    )
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'timestamp_unix': self.timestamp.timestamp() if self.timestamp else None,
            'humidity_percent': self.humidity_percent,
            'sensor_type': self.sensor_type,
            'sensor_id': self.sensor_id
        }
    
    def __repr__(self):
        return f'<HumidityReading(id={self.id}, humidity={self.humidity_percent}%, sensor={self.sensor_id}, time={self.timestamp})>'

class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or "sqlite:///monitoringhub.db"
        self.engine = None
        self.Session = None
        self.logger = logging.getLogger(__name__)
        
    def initialize(self):
        """Initialize database connection and create tables."""
        try:
            self.engine = create_engine(
                self.database_url,
                echo=False,  # Set to True for SQL debugging
                connect_args={"check_same_thread": False} if "sqlite" in self.database_url else {}
            )
            
            # Create tables
            Base.metadata.create_all(self.engine)
            
            # Create session factory
            self.Session = sessionmaker(bind=self.engine)
            
            self.logger.info(f"Database initialized: {self.database_url}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
            
    def get_session(self) -> Session:
        """Get a new database session."""
        if not self.Session:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.Session()
        
    def close(self):
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            
    def get_total_readings_count(self) -> int:
        """Get total count of all readings (temperature + humidity)."""
        try:
            with self.get_session() as session:
                temp_count = session.query(func.count(TemperatureReading.id)).scalar() or 0
                humidity_count = session.query(func.count(HumidityReading.id)).scalar() or 0
                return temp_count + humidity_count
        except Exception as e:
            self.logger.error(f"Error getting total readings count: {e}")
            return 0
    
    def rollover_database(self) -> bool:
        """Archive current database and create a new one."""
        try:
            # Close current connections
            if self.engine:
                self.engine.dispose()
            
            # Create timestamp for archive filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Determine database file path
            if self.database_url.startswith("sqlite:///"):
                db_file = self.database_url.replace("sqlite:///", "")
            else:
                self.logger.error("Rollover only supported for SQLite databases")
                return False
            
            # Create archive filename
            base_name = os.path.splitext(db_file)[0]
            archive_name = f"{base_name}_archive_{timestamp}.db"
            
            # Move current database to archive
            if os.path.exists(db_file):
                shutil.move(db_file, archive_name)
                self.logger.info(f"Database archived to: {archive_name}")
            
            # Reinitialize database (creates new empty database)
            self.initialize()
            self.logger.info("New database created after rollover")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during database rollover: {e}")
            return False
    
    def check_and_rollover(self) -> bool:
        """Check if rollover is needed and perform it."""
        try:
            total_readings = self.get_total_readings_count()
            self.logger.debug(f"Current total readings: {total_readings}")
            
            if total_readings >= 10000:
                self.logger.info(f"Database rollover triggered at {total_readings} readings")
                return self.rollover_database()
            
            return False  # No rollover needed
            
        except Exception as e:
            self.logger.error(f"Error checking rollover: {e}")
            return False
            
    def add_temperature_reading(self, temperature_c: float, sensor_type: str = "unknown", 
                               sensor_id: str = "default", timestamp: datetime = None) -> Optional[TemperatureReading]:
        """Add a temperature reading to the database."""
        try:
            with self.get_session() as session:
                reading_ts = timestamp or datetime.now(timezone.utc)
                reading = TemperatureReading(
                    temperature_c=temperature_c,
                    sensor_type=sensor_type,
                    sensor_id=sensor_id,
                    timestamp=reading_ts,
                    timestamp_unix=reading_ts.timestamp()
                )
                session.add(reading)
                session.commit()
                session.refresh(reading)
                self.logger.debug(f"Added temperature reading: {reading}")
                return reading
        except Exception as e:
            self.logger.error(f"Error adding temperature reading: {e}")
            return None

    def get_recent_readings(self, limit: int = 100, sensor_id: str = None) -> List[TemperatureReading]:
        """Get recent temperature readings."""
        try:
            with self.get_session() as session:
                query = session.query(TemperatureReading)
                
                if sensor_id:
                    query = query.filter(TemperatureReading.sensor_id == sensor_id)
                    
                readings = query.order_by(TemperatureReading.timestamp.desc()).limit(limit).all()
                
                # Detach objects from session to prevent issues after session closes
                for reading in readings:
                    session.expunge(reading)
                    
                return readings
                
        except Exception as e:
            self.logger.error(f"Error getting recent readings: {e}")
            return []
            
    def get_readings_by_time_range(self, start_time: datetime, end_time: datetime = None,
                                   sensor_id: str = None) -> List[TemperatureReading]:
        """Get temperature readings within a time range."""
        try:
            with self.get_session() as session:
                query = session.query(TemperatureReading)
                
                # Add time range filters
                query = query.filter(TemperatureReading.timestamp >= start_time)
                if end_time:
                    query = query.filter(TemperatureReading.timestamp <= end_time)
                    
                if sensor_id:
                    query = query.filter(TemperatureReading.sensor_id == sensor_id)
                    
                readings = query.order_by(TemperatureReading.timestamp.asc()).all()
                
                # Detach objects from session
                for reading in readings:
                    session.expunge(reading)
                    
                return readings
                
        except Exception as e:
            self.logger.error(f"Error getting readings by time range: {e}")
            return []
            
    def get_daily_readings(self, days_back: int = 1, sensor_id: str = None) -> List[TemperatureReading]:
        """Get temperature readings from the last N days."""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days_back)
        return self.get_readings_by_time_range(start_time, end_time, sensor_id)
        
    def get_weekly_readings(self, weeks_back: int = 1, sensor_id: str = None) -> List[TemperatureReading]:
        """Get temperature readings from the last N weeks."""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(weeks=weeks_back)
        return self.get_readings_by_time_range(start_time, end_time, sensor_id)
        
    def get_statistics(self, sensor_id: str = None, hours_back: int = 24) -> Dict[str, float]:
        """Get temperature statistics for the last N hours."""
        try:
            with self.get_session() as session:
                # Calculate start time
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=hours_back)
                
                query = session.query(
                    func.count(TemperatureReading.id).label('count'),
                    func.avg(TemperatureReading.temperature_c).label('avg'),
                    func.min(TemperatureReading.temperature_c).label('min'),
                    func.max(TemperatureReading.temperature_c).label('max')
                ).filter(TemperatureReading.timestamp >= start_time)
                
                if sensor_id:
                    query = query.filter(TemperatureReading.sensor_id == sensor_id)
                    
                result = query.first()
                
                # Find timestamps for min and max within window
                min_row_q = session.query(TemperatureReading).filter(TemperatureReading.timestamp >= start_time)
                max_row_q = session.query(TemperatureReading).filter(TemperatureReading.timestamp >= start_time)
                if sensor_id:
                    min_row_q = min_row_q.filter(TemperatureReading.sensor_id == sensor_id)
                    max_row_q = max_row_q.filter(TemperatureReading.sensor_id == sensor_id)
                min_row = min_row_q.order_by(TemperatureReading.temperature_c.asc(), TemperatureReading.timestamp.asc()).first()
                max_row = max_row_q.order_by(TemperatureReading.temperature_c.desc(), TemperatureReading.timestamp.asc()).first()
                min_ts = min_row.timestamp.isoformat() if min_row else None
                max_ts = max_row.timestamp.isoformat() if max_row else None

                return {
                    'count': result.count or 0,
                    'average': round(result.avg or 0, 2),
                    'minimum': round(result.min or 0, 2),
                    'maximum': round(result.max or 0, 2),
                    'hours_back': hours_back,
                    'min_timestamp': min_ts,
                    'max_timestamp': max_ts
                }
                
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {'count': 0, 'average': 0, 'minimum': 0, 'maximum': 0, 'hours_back': hours_back, 'min_timestamp': None, 'max_timestamp': None}
            
    def cleanup_old_readings(self, days_to_keep: int = 30) -> int:
        """Remove old temperature readings beyond retention period."""
        try:
            with self.get_session() as session:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
                
                deleted_count = session.query(TemperatureReading)\
                    .filter(TemperatureReading.timestamp < cutoff_date)\
                    .delete()
                    
                session.commit()
                
                self.logger.info(f"Cleaned up {deleted_count} old temperature readings (older than {days_to_keep} days)")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old readings: {e}")
            return 0



    def add_humidity_reading(self, humidity_percent: float, sensor_type: str = "unknown", 
                            sensor_id: str = "default", timestamp: datetime = None):
        """Add a humidity reading to the database."""
        try:
            with self.get_session() as session:
                reading_ts = timestamp or datetime.now(timezone.utc)
                reading = HumidityReading(
                    humidity_percent=humidity_percent,
                    sensor_type=sensor_type,
                    sensor_id=sensor_id,
                    timestamp=reading_ts,
                    timestamp_unix=reading_ts.timestamp()
                )
                session.add(reading)
                session.commit()
                session.refresh(reading)
                self.logger.debug(f"Added humidity reading: {reading}")
                return reading
        except Exception as e:
            self.logger.error(f"Error adding humidity reading: {e}")
            return None

    def get_recent_humidity_readings(self, limit: int = 100, sensor_id: str = None):
        """Get recent humidity readings."""
        try:
            with self.get_session() as session:
                query = session.query(HumidityReading)
                
                if sensor_id:
                    query = query.filter(HumidityReading.sensor_id == sensor_id)
                    
                readings = query.order_by(HumidityReading.timestamp.desc()).limit(limit).all()
                return readings
                
        except Exception as e:
            self.logger.error(f"Error getting recent humidity readings: {e}")
            return []

    def get_humidity_statistics(self, sensor_id: str = None, hours_back: int = 24):
        """Get humidity statistics."""
        try:
            with self.get_session() as session:
                from datetime import timedelta
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
                
                query = session.query(HumidityReading).filter(
                    HumidityReading.timestamp >= cutoff_time
                )
                
                if sensor_id:
                    query = query.filter(HumidityReading.sensor_id == sensor_id)
                    
                readings = query.all()
                
                if not readings:
                    return {'count': 0}
                    
                humidity_values = [r.humidity_percent for r in readings]

                # Determine timestamps when min/max occurred
                min_val = min(humidity_values)
                max_val = max(humidity_values)
                min_ts = None
                max_ts = None
                for r in sorted(readings, key=lambda x: x.timestamp):
                    if min_ts is None and r.humidity_percent == min_val:
                        min_ts = r.timestamp.isoformat()
                    if max_ts is None and r.humidity_percent == max_val:
                        max_ts = r.timestamp.isoformat()

                
                return {
                    'count': len(readings),
                    'min': min(humidity_values),
                    'max': max(humidity_values),
                    'avg': sum(humidity_values) / len(humidity_values), 'min_timestamp': min_ts, 'max_timestamp': max_ts,
                    'latest': readings[0].humidity_percent if readings else None
                }
                
        except Exception as e:
            self.logger.error(f"Error getting humidity statistics: {e}")
            return {'count': 0, 'error': str(e)}




    def add_pressure_reading(self, pressure_hpa: float, sensor_type: str = "unknown", sensor_id: str = "default", timestamp: datetime = None):
        try:
            with self.get_session() as session:
                reading_ts = timestamp or datetime.now(timezone.utc)
                reading = PressureReading(
                    pressure_hpa=pressure_hpa,
                    sensor_type=sensor_type,
                    sensor_id=sensor_id,
                    timestamp=reading_ts,
                    timestamp_unix=reading_ts.timestamp()
                )
                session.add(reading)
                session.commit()
                session.refresh(reading)
                return reading
        except Exception as e:
            self.logger.error(f"Error adding pressure reading: {e}")
            return None

    def get_recent_pressure_readings(self, limit: int = 100, sensor_id: str = None):
        try:
            with self.get_session() as session:
                query = session.query(PressureReading)
                if sensor_id:
                    query = query.filter(PressureReading.sensor_id == sensor_id)
                return query.order_by(PressureReading.timestamp.desc()).limit(limit).all()
        except Exception as e:
            self.logger.error(f"Error getting recent pressure readings: {e}")
            return []

    def get_pressure_statistics(self, sensor_id: str = None, hours_back: int = 24):
        try:
            with self.get_session() as session:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=hours_back)
                query = session.query(
                    func.count(PressureReading.id).label('count'),
                    func.avg(PressureReading.pressure_hpa).label('avg'),
                    func.min(PressureReading.pressure_hpa).label('min'),
                    func.max(PressureReading.pressure_hpa).label('max')
                ).filter(PressureReading.timestamp >= start_time)
                if sensor_id:
                    query = query.filter(PressureReading.sensor_id == sensor_id)
                result = query.first()
                # Find timestamps for min and max within window
                min_row = session.query(PressureReading)\
                    .filter(PressureReading.timestamp >= start_time)\
                    .order_by(PressureReading.pressure_hpa.asc(), PressureReading.timestamp.asc())\
                    .first()
                max_row = session.query(PressureReading)\
                    .filter(PressureReading.timestamp >= start_time)\
                    .order_by(PressureReading.pressure_hpa.desc(), PressureReading.timestamp.asc())\
                    .first()
                if sensor_id:
                    if min_row and min_row.sensor_id != sensor_id:
                        min_row = session.query(PressureReading)\
                            .filter(PressureReading.timestamp >= start_time, PressureReading.sensor_id == sensor_id)\
                            .order_by(PressureReading.pressure_hpa.asc(), PressureReading.timestamp.asc())\
                            .first()
                    if max_row and max_row.sensor_id != sensor_id:
                        max_row = session.query(PressureReading)\
                            .filter(PressureReading.timestamp >= start_time, PressureReading.sensor_id == sensor_id)\
                            .order_by(PressureReading.pressure_hpa.desc(), PressureReading.timestamp.asc())\
                            .first()
                min_ts = min_row.timestamp.isoformat() if min_row else None
                max_ts = max_row.timestamp.isoformat() if max_row else None
                return {
                    'count': result.count or 0,
                    'average': round(result.avg or 0, 2),
                    'minimum': round(result.min or 0, 2),
                    'maximum': round(result.max or 0, 2),
                    'hours_back': hours_back, 'min_timestamp': min_ts, 'max_timestamp': max_ts
                }
        except Exception as e:
            self.logger.error(f"Error getting pressure statistics: {e}")
            return {'count': 0, 'average': 0, 'minimum': 0, 'maximum': 0, 'hours_back': hours_back, 'min_timestamp': None, 'max_timestamp': None}

    def add_air_quality_reading(self, data: dict, sensor_type: str = "unknown", sensor_id: str = "default", timestamp: datetime = None):
        try:
            with self.get_session() as session:
                reading_ts = timestamp or datetime.now(timezone.utc)
                reading = AirQualityReading(
                    co2_ppm=data.get('co2_ppm'),
                    nh3_ppm=data.get('nh3_ppm'),
                    alcohol_ppm=data.get('alcohol_ppm'),
                    aqi=data.get('aqi'),
                    status=data.get('status'),
                    raw_adc=data.get('raw_adc'),
                    voltage_v=data.get('voltage_v'),
                    resistance_ohm=data.get('resistance_ohm'),
                    ratio_rs_r0=data.get('ratio_rs_r0'),
                    sensor_type=sensor_type,
                    sensor_id=sensor_id,
                    timestamp=reading_ts,
                    timestamp_unix=reading_ts.timestamp()
                )
                session.add(reading)
                session.commit()
                session.refresh(reading)
                return reading
        except Exception as e:
            self.logger.error(f"Error adding air quality reading: {e}")
            return None

    def get_recent_air_quality_readings(self, limit: int = 100, sensor_id: str = None):
        try:
            with self.get_session() as session:
                query = session.query(AirQualityReading)
                if sensor_id:
                    query = query.filter(AirQualityReading.sensor_id == sensor_id)
                return query.order_by(AirQualityReading.timestamp.desc()).limit(limit).all()
        except Exception as e:
            self.logger.error(f"Error getting recent AQ readings: {e}")
            return []

    def get_air_quality_statistics(self, sensor_id: str = None, hours_back: int = 24):
        try:
            with self.get_session() as session:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=hours_back)
                query = session.query(
                    func.count(AirQualityReading.id).label('count'),
                    func.avg(AirQualityReading.co2_ppm).label('avg'),
                    func.min(AirQualityReading.co2_ppm).label('min'),
                    func.max(AirQualityReading.co2_ppm).label('max')
                ).filter(AirQualityReading.timestamp >= start_time)
                if sensor_id:
                    query = query.filter(AirQualityReading.sensor_id == sensor_id)
                result = query.first()
                # Find timestamps for min and max CO2 within window
                base_q = session.query(AirQualityReading).filter(AirQualityReading.timestamp >= start_time)
                if sensor_id:
                    base_q = base_q.filter(AirQualityReading.sensor_id == sensor_id)
                min_row = base_q.order_by(AirQualityReading.co2_ppm.asc(), AirQualityReading.timestamp.asc()).first()
                max_row = base_q.order_by(AirQualityReading.co2_ppm.desc(), AirQualityReading.timestamp.asc()).first()
                min_ts = min_row.timestamp.isoformat() if min_row else None
                max_ts = max_row.timestamp.isoformat() if max_row else None
                return {
                    'count': result.count or 0,
                    'average': round(result.avg or 0, 1),
                    'minimum': round(result.min or 0, 1),
                    'maximum': round(result.max or 0, 1),
                    'hours_back': hours_back, 'min_timestamp': min_ts, 'max_timestamp': max_ts
                }
        except Exception as e:
            self.logger.error(f"Error getting AQ statistics: {e}")
            return {'count': 0, 'average': 0, 'minimum': 0, 'maximum': 0, 'hours_back': hours_back, 'min_timestamp': None, 'max_timestamp': None}

    def add_meter_reading(self, meter_value: str, ocr_engine: str = None, raw_ocr_text: str = None,
                         sensor_type: str = "esp32cam_ocr", sensor_id: str = "cabana1_meter",
                         timestamp: datetime = None):
        """Add a meter reading to the database."""
        try:
            with self.get_session() as session:
                reading_ts = timestamp or datetime.now(timezone.utc)
                reading = MeterReading(
                    meter_value=meter_value,
                    ocr_engine=ocr_engine,
                    raw_ocr_text=raw_ocr_text,
                    sensor_type=sensor_type,
                    sensor_id=sensor_id,
                    timestamp=reading_ts,
                    timestamp_unix=reading_ts.timestamp()
                )
                session.add(reading)
                session.commit()
                session.refresh(reading)
                self.logger.info(f"Added meter reading: {reading}")
                return reading
        except Exception as e:
            self.logger.error(f"Error adding meter reading: {e}")
            return None

    def get_recent_meter_readings(self, limit: int = 100, sensor_id: str = None):
        """Get recent meter readings."""
        try:
            with self.get_session() as session:
                query = session.query(MeterReading)
                if sensor_id:
                    query = query.filter(MeterReading.sensor_id == sensor_id)
                readings = query.order_by(MeterReading.timestamp.desc()).limit(limit).all()
                for reading in readings:
                    session.expunge(reading)
                return readings
        except Exception as e:
            self.logger.error(f"Error getting recent meter readings: {e}")
            return []

    def get_meter_readings_by_year(self, year: int, sensor_id: str = None):
        """Get meter readings for a specific year."""
        try:
            with self.get_session() as session:
                start_time = datetime(year, 1, 1, tzinfo=timezone.utc)
                end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                query = session.query(MeterReading).filter(
                    MeterReading.timestamp >= start_time,
                    MeterReading.timestamp < end_time
                )
                if sensor_id:
                    query = query.filter(MeterReading.sensor_id == sensor_id)
                readings = query.order_by(MeterReading.timestamp.asc()).all()
                for reading in readings:
                    session.expunge(reading)
                return readings
        except Exception as e:
            self.logger.error(f"Error getting meter readings for year {year}: {e}")
            return []

    def get_meter_readings_by_month(self, year: int, month: int, sensor_id: str = None):
        """Get meter readings for a specific month."""
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, 1, tzinfo=timezone.utc)
                if month == 12:
                    end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                else:
                    end_time = datetime(year, month + 1, 1, tzinfo=timezone.utc)
                query = session.query(MeterReading).filter(
                    MeterReading.timestamp >= start_time,
                    MeterReading.timestamp < end_time
                )
                if sensor_id:
                    query = query.filter(MeterReading.sensor_id == sensor_id)
                readings = query.order_by(MeterReading.timestamp.asc()).all()
                for reading in readings:
                    session.expunge(reading)
                return readings
        except Exception as e:
            self.logger.error(f"Error getting meter readings for {year}-{month}: {e}")
            return []

    def get_meter_readings_by_day(self, year: int, month: int, day: int, sensor_id: str = None):
        """Get meter readings for a specific day."""
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, day, tzinfo=timezone.utc)
                end_time = start_time + timedelta(days=1)
                query = session.query(MeterReading).filter(
                    MeterReading.timestamp >= start_time,
                    MeterReading.timestamp < end_time
                )
                if sensor_id:
                    query = query.filter(MeterReading.sensor_id == sensor_id)
                readings = query.order_by(MeterReading.timestamp.asc()).all()
                for reading in readings:
                    session.expunge(reading)
                return readings
        except Exception as e:
            self.logger.error(f"Error getting meter readings for {year}-{month}-{day}: {e}")
            return []

    def get_meter_statistics(self, sensor_id: str = None, hours_back: int = 24):
        """Get meter reading statistics."""
        try:
            with self.get_session() as session:
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=hours_back)
                query = session.query(MeterReading).filter(MeterReading.timestamp >= start_time)
                if sensor_id:
                    query = query.filter(MeterReading.sensor_id == sensor_id)
                readings = query.order_by(MeterReading.timestamp.asc()).all()

                if not readings:
                    return {'count': 0, 'hours_back': hours_back}

                # Get first and last reading
                first_reading = readings[0]
                last_reading = readings[-1]

                return {
                    'count': len(readings),
                    'first_value': first_reading.meter_value,
                    'last_value': last_reading.meter_value,
                    'first_timestamp': first_reading.timestamp.isoformat(),
                    'last_timestamp': last_reading.timestamp.isoformat(),
                    'hours_back': hours_back
                }
        except Exception as e:
            self.logger.error(f"Error getting meter statistics: {e}")
            return {'count': 0, 'hours_back': hours_back}

    # Time-based aggregation methods for charts
    def get_readings_by_year(self, year: int, sensor_id: str = None) -> List[TemperatureReading]:
        """Get temperature readings for a specific year."""
        try:
            with self.get_session() as session:
                start_time = datetime(year, 1, 1, tzinfo=timezone.utc)
                end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                
                query = session.query(TemperatureReading).filter(
                    TemperatureReading.timestamp >= start_time,
                    TemperatureReading.timestamp < end_time
                )
                
                if sensor_id:
                    query = query.filter(TemperatureReading.sensor_id == sensor_id)
                
                return query.order_by(TemperatureReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting readings for year {year}: {e}")
            return []
    
    def get_readings_by_month(self, year: int, month: int, sensor_id: str = None) -> List[TemperatureReading]:
        """Get temperature readings for a specific month."""
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, 1, tzinfo=timezone.utc)
                if month == 12:
                    end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                else:
                    end_time = datetime(year, month + 1, 1, tzinfo=timezone.utc)
                
                query = session.query(TemperatureReading).filter(
                    TemperatureReading.timestamp >= start_time,
                    TemperatureReading.timestamp < end_time
                )
                
                if sensor_id:
                    query = query.filter(TemperatureReading.sensor_id == sensor_id)
                
                return query.order_by(TemperatureReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting readings for {year}-{month}: {e}")
            return []
    
    def get_readings_by_day(self, year: int, month: int, day: int, sensor_id: str = None) -> List[TemperatureReading]:
        """Get temperature readings for a specific day."""
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, day, tzinfo=timezone.utc)
                end_time = start_time + timedelta(days=1)
                
                query = session.query(TemperatureReading).filter(
                    TemperatureReading.timestamp >= start_time,
                    TemperatureReading.timestamp < end_time
                )
                
                if sensor_id:
                    query = query.filter(TemperatureReading.sensor_id == sensor_id)
                
                return query.order_by(TemperatureReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting readings for {year}-{month}-{day}: {e}")
            return []
    
    def get_yearly_statistics(self, year: int, sensor_id: str = None) -> Dict[str, Any]:
        """Get temperature statistics for a specific year."""
        try:
            with self.get_session() as session:
                start_time = datetime(year, 1, 1, tzinfo=timezone.utc)
                end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                
                query = session.query(
                    func.count(TemperatureReading.id).label("count"),
                    func.avg(TemperatureReading.temperature_c).label("avg"),
                    func.min(TemperatureReading.temperature_c).label("min"),
                    func.max(TemperatureReading.temperature_c).label("max")
                ).filter(
                    TemperatureReading.timestamp >= start_time,
                    TemperatureReading.timestamp < end_time
                )
                
                if sensor_id:
                    query = query.filter(TemperatureReading.sensor_id == sensor_id)
                
                result = query.first()
                
                return {
                    "count": result.count or 0,
                    "average": round(result.avg or 0, 2),
                    "minimum": result.min or 0,
                    "maximum": result.max or 0,
                    "year": year
                }
        except Exception as e:
            self.logger.error(f"Error getting yearly statistics for {year}: {e}")
            return {"count": 0, "average": 0, "minimum": 0, "maximum": 0, "year": year}
    
    def get_monthly_statistics(self, year: int, month: int, sensor_id: str = None) -> Dict[str, Any]:
        """Get temperature statistics for a specific month."""
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, 1, tzinfo=timezone.utc)
                if month == 12:
                    end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                else:
                    end_time = datetime(year, month + 1, 1, tzinfo=timezone.utc)
                
                query = session.query(
                    func.count(TemperatureReading.id).label("count"),
                    func.avg(TemperatureReading.temperature_c).label("avg"),
                    func.min(TemperatureReading.temperature_c).label("min"),
                    func.max(TemperatureReading.temperature_c).label("max")
                ).filter(
                    TemperatureReading.timestamp >= start_time,
                    TemperatureReading.timestamp < end_time
                )
                
                if sensor_id:
                    query = query.filter(TemperatureReading.sensor_id == sensor_id)
                
                result = query.first()
                
                return {
                    "count": result.count or 0,
                    "average": round(result.avg or 0, 2),
                    "minimum": result.min or 0,
                    "maximum": result.max or 0,
                    "year": year,
                    "month": month
                }
        except Exception as e:
            self.logger.error(f"Error getting monthly statistics for {year}-{month}: {e}")
            return {"count": 0, "average": 0, "minimum": 0, "maximum": 0, "year": year, "month": month}
    
    def get_daily_statistics(self, year: int, month: int, day: int, sensor_id: str = None) -> Dict[str, Any]:
        """Get temperature statistics for a specific day."""
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, day, tzinfo=timezone.utc)
                end_time = start_time + timedelta(days=1)
                
                query = session.query(
                    func.count(TemperatureReading.id).label("count"),
                    func.avg(TemperatureReading.temperature_c).label("avg"),
                    func.min(TemperatureReading.temperature_c).label("min"),
                    func.max(TemperatureReading.temperature_c).label("max")
                ).filter(
                    TemperatureReading.timestamp >= start_time,
                    TemperatureReading.timestamp < end_time
                )
                
                if sensor_id:
                    query = query.filter(TemperatureReading.sensor_id == sensor_id)
                
                result = query.first()
                
                return {
                    "count": result.count or 0,
                    "average": round(result.avg or 0, 2),
                    "minimum": result.min or 0,
                    "maximum": result.max or 0,
                    "year": year,
                    "month": month,
                    "day": day
                }
        except Exception as e:
            self.logger.error(f"Error getting daily statistics for {year}-{month}-{day}: {e}")
            return {"count": 0, "average": 0, "minimum": 0, "maximum": 0, "year": year, "month": month, "day": day}

# Global database instance

db = DatabaseManager()

class PressureReading(Base):
    __tablename__ = 'pressure_readings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    timestamp_unix = Column(Float, nullable=False, default=lambda: time.time())
    pressure_hpa = Column(Float, nullable=False)
    sensor_type = Column(String(50), nullable=False, default='unknown')
    sensor_id = Column(String(100), nullable=False, default='default')
    __table_args__ = (
        Index('idx_pressure_timestamp', 'timestamp'),
        Index('idx_pressure_sensor_timestamp', 'sensor_id', 'timestamp'),
    )

class AirQualityReading(Base):
    __tablename__ = 'air_quality_readings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    timestamp_unix = Column(Float, nullable=False, default=lambda: time.time())
    co2_ppm = Column(Float, nullable=True)
    nh3_ppm = Column(Float, nullable=True)
    alcohol_ppm = Column(Float, nullable=True)
    aqi = Column(Integer, nullable=True)
    status = Column(String(50), nullable=True)
    raw_adc = Column(Integer, nullable=True)
    voltage_v = Column(Float, nullable=True)
    resistance_ohm = Column(Float, nullable=True)
    ratio_rs_r0 = Column(Float, nullable=True)
    sensor_type = Column(String(50), nullable=False, default='unknown')
    sensor_id = Column(String(100), nullable=False, default='default')
    __table_args__ = (
        Index('idx_aq_timestamp', 'timestamp'),
        Index('idx_aq_sensor_timestamp', 'sensor_id', 'timestamp'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'timestamp_unix': self.timestamp.timestamp() if self.timestamp else None,
            'co2_ppm': self.co2_ppm,
            'nh3_ppm': self.nh3_ppm,
            'alcohol_ppm': self.alcohol_ppm,
            'aqi': self.aqi,
            'status': self.status,
            'raw_adc': self.raw_adc,
            'voltage_v': self.voltage_v,
            'resistance_ohm': self.resistance_ohm,
            'ratio_rs_r0': self.ratio_rs_r0,
            'sensor_type': self.sensor_type,
            'sensor_id': self.sensor_id,
        }

class MeterReading(Base):
    """Meter reading model for OCR-captured electricity meter values."""

    __tablename__ = 'meter_readings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    timestamp_unix = Column(Float, nullable=False, default=lambda: time.time())
    meter_value = Column(String(50), nullable=False)
    ocr_engine = Column(String(100), nullable=True)
    raw_ocr_text = Column(String(500), nullable=True)
    sensor_type = Column(String(50), nullable=False, default='esp32cam_ocr')
    sensor_id = Column(String(100), nullable=False, default='cabana1_meter')

    __table_args__ = (
        Index('idx_meter_timestamp', 'timestamp'),
        Index('idx_meter_sensor_timestamp', 'sensor_id', 'timestamp'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'timestamp_unix': self.timestamp.timestamp() if self.timestamp else None,
            'meter_value': self.meter_value,
            'ocr_engine': self.ocr_engine,
            'raw_ocr_text': self.raw_ocr_text,
            'sensor_type': self.sensor_type,
            'sensor_id': self.sensor_id,
        }

    def __repr__(self):
        return f'<MeterReading(id={self.id}, value={self.meter_value}, sensor={self.sensor_id}, time={self.timestamp})>'

def init_database(database_url: str = None):
    """Initialize the global database instance."""
    global db
    if database_url:
        db = DatabaseManager(database_url)
    db.initialize()
    

if __name__ == "__main__":
    # Test the database models
    import sys
    
    logging.basicConfig(level=logging.ERROR)
    
    try:
        # Initialize database
        init_database()
        
        # Add some test data
        base_time = datetime.now(timezone.utc)
        
        for i in range(10):
            temp = 20.0 + (i % 5) * 0.5  # Temperatures between 20-22°C
            timestamp = base_time - timedelta(minutes=i)
            reading = db.add_temperature_reading(temp, "test", "test_sensor", timestamp)
            
        # Test queries
        recent = db.get_recent_readings(5)
        for reading in recent:
            pass  # Process reading
        stats = db.get_statistics()
        
        
    except Exception as e:
        sys.exit(1)