"""
SQLAlchemy models for the aMonitoringHub application.

This module defines the database schema using SQLAlchemy's ORM. It includes
models for storing sensor readings (temperature, humidity, pressure, etc.)
and a DatabaseManager class to handle all database interactions, such as
session management, data insertion, and querying.
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
    """SQLAlchemy model for storing temperature readings.

    Attributes:
        id (int): The primary key for the reading.
        timestamp (datetime): The UTC timestamp when the reading was taken.
        timestamp_unix (float): The Unix timestamp of the reading.
        temperature_c (float): The temperature in degrees Celsius.
        sensor_type (str): The type of sensor that produced the reading.
        sensor_id (str): The unique identifier of the sensor.
    """
    
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
        """Converts the TemperatureReading model instance to a dictionary.

        Returns:
            A dictionary representation of the model.
        """
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'timestamp_unix': self.timestamp.timestamp() if self.timestamp else None,
            'temperature_c': self.temperature_c,
            'sensor_type': self.sensor_type,
            'sensor_id': self.sensor_id
        }
    
    def __repr__(self) -> str:
        """Provides a developer-friendly representation of the object."""
        return f"<TemperatureReading(id={self.id}, temp={self.temperature_c}°C, sensor={self.sensor_id}, time={self.timestamp})>"




class HumidityReading(Base):
    """SQLAlchemy model for storing humidity readings.

    Attributes:
        id (int): The primary key for the reading.
        timestamp (datetime): The UTC timestamp when the reading was taken.
        timestamp_unix (float): The Unix timestamp of the reading.
        humidity_percent (float): The relative humidity in percent.
        sensor_type (str): The type of sensor that produced the reading.
        sensor_id (str): The unique identifier of the sensor.
    """
    
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Converts the HumidityReading model instance to a dictionary.

        Returns:
            A dictionary representation of the model.
        """
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'timestamp_unix': self.timestamp.timestamp() if self.timestamp else None,
            'humidity_percent': self.humidity_percent,
            'sensor_type': self.sensor_type,
            'sensor_id': self.sensor_id
        }
    
    def __repr__(self) -> str:
        """Provides a developer-friendly representation of the object."""
        return f'<HumidityReading(id={self.id}, humidity={self.humidity_percent}%, sensor={self.sensor_id}, time={self.timestamp})>'

class DatabaseManager:
    """Manages all database interactions for the application.

    This class handles the initialization of the database, session management,
    and provides methods for adding, querying, and managing sensor data.

    Attributes:
        database_url (str): The connection URL for the database.
        engine: The SQLAlchemy engine instance.
        Session: The SQLAlchemy session factory.
        logger: The logger instance for this class.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """Initializes the DatabaseManager.

        Args:
            database_url: The SQLAlchemy database URL. If not provided, it
                defaults to a local SQLite database named 'monitoringhub.db'.
        """
        self.database_url = database_url or "sqlite:///monitoringhub.db"
        self.engine = None
        self.Session = None
        self.logger = logging.getLogger(__name__)
        
    def initialize(self):
        """Initializes the database engine and creates all tables.

        This method sets up the SQLAlchemy engine and session factory based on the
        configured database URL. It creates the database tables if they do not
        already exist.
        """
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
        """Provides a new database session.

        Returns:
            A new SQLAlchemy Session instance.

        Raises:
            RuntimeError: If the database has not been initialized.
        """
        if not self.Session:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.Session()
        
    def close(self):
        """Disposes of the database engine's connection pool."""
        if self.engine:
            self.engine.dispose()
            
    def get_total_readings_count(self) -> int:
        """Calculates the total number of temperature and humidity readings.

        Returns:
            The combined count of all readings in the database.
        """
        try:
            with self.get_session() as session:
                temp_count = session.query(func.count(TemperatureReading.id)).scalar() or 0
                humidity_count = session.query(func.count(HumidityReading.id)).scalar() or 0
                return temp_count + humidity_count
        except Exception as e:
            self.logger.error(f"Error getting total readings count: {e}")
            return 0
    
    def rollover_database(self) -> bool:
        """Archives the current database file and creates a new one.

        This is useful for managing database size. The current database file
        is renamed with a timestamp, and a new, empty database is created.

        Returns:
            True if the rollover was successful, False otherwise.
        """
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
        """Checks if the database needs to be rolled over and performs it.

        The rollover is triggered if the total number of readings exceeds a
        predefined threshold (10,000).

        Returns:
            True if a rollover was performed, False otherwise.
        """
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
                               sensor_id: str = "default", timestamp: Optional[datetime] = None) -> Optional[TemperatureReading]:
        """Adds a new temperature reading to the database.

        Args:
            temperature_c: The temperature in degrees Celsius.
            sensor_type: The type of sensor.
            sensor_id: The unique ID of the sensor.
            timestamp: The timestamp of the reading. Defaults to now (UTC).

        Returns:
            The created TemperatureReading object, or None on failure.
        """
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

    def get_recent_readings(self, limit: int = 100, sensor_id: Optional[str] = None) -> List[TemperatureReading]:
        """Retrieves the most recent temperature readings.

        Args:
            limit: The maximum number of readings to return.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of TemperatureReading objects.
        """
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
            
    def get_readings_by_time_range(self, start_time: datetime, end_time: Optional[datetime] = None,
                                   sensor_id: Optional[str] = None) -> List[TemperatureReading]:
        """Retrieves temperature readings within a specific time range.

        Args:
            start_time: The start of the time range.
            end_time: The end of the time range. Defaults to now.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of TemperatureReading objects.
        """
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
            
    def get_daily_readings(self, days_back: int = 1, sensor_id: Optional[str] = None) -> List[TemperatureReading]:
        """Retrieves temperature readings from the last N days.

        Args:
            days_back: The number of days to look back.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of TemperatureReading objects.
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days_back)
        return self.get_readings_by_time_range(start_time, end_time, sensor_id)
        
    def get_weekly_readings(self, weeks_back: int = 1, sensor_id: Optional[str] = None) -> List[TemperatureReading]:
        """Retrieves temperature readings from the last N weeks.

        Args:
            weeks_back: The number of weeks to look back.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of TemperatureReading objects.
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(weeks=weeks_back)
        return self.get_readings_by_time_range(start_time, end_time, sensor_id)
        
    def get_statistics(self, sensor_id: Optional[str] = None, hours_back: int = 24) -> Dict[str, Any]:
        """Calculates temperature statistics for a given period.

        Args:
            sensor_id: An optional sensor ID to filter by.
            hours_back: The number of hours to look back for statistics.

        Returns:
            A dictionary containing the count, total count, average, minimum,
            and maximum temperature, along with timestamps for min/max values.
        """
        try:
            with self.get_session() as session:
                # Calculate start time
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(hours=hours_back)
                
                # Get total count of all readings (not filtered by time)
                total_count_query = session.query(func.count(TemperatureReading.id))
                if sensor_id:
                    total_count_query = total_count_query.filter(TemperatureReading.sensor_id == sensor_id)
                total_count = total_count_query.scalar() or 0

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
                    'total_count': total_count,
                    'average': round(result.avg or 0, 2),
                    'minimum': round(result.min or 0, 2),
                    'maximum': round(result.max or 0, 2),
                    'hours_back': hours_back,
                    'min_timestamp': min_ts,
                    'max_timestamp': max_ts
                }

        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {'count': 0, 'total_count': 0, 'average': 0, 'minimum': 0, 'maximum': 0, 'hours_back': hours_back, 'min_timestamp': None, 'max_timestamp': None}
            
    def cleanup_old_readings(self, days_to_keep: int = 30) -> int:
        """Removes old temperature readings from the database.

        Args:
            days_to_keep: The number of days of readings to retain.

        Returns:
            The number of readings that were deleted.
        """
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
                            sensor_id: str = "default", timestamp: Optional[datetime] = None) -> Optional[HumidityReading]:
        """Adds a new humidity reading to the database.

        Args:
            humidity_percent: The relative humidity in percent.
            sensor_type: The type of sensor.
            sensor_id: The unique ID of the sensor.
            timestamp: The timestamp of the reading. Defaults to now (UTC).

        Returns:
            The created HumidityReading object, or None on failure.
        """
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

    def get_recent_humidity_readings(self, limit: int = 100, sensor_id: Optional[str] = None) -> List[HumidityReading]:
        """Retrieves the most recent humidity readings.

        Args:
            limit: The maximum number of readings to return.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of HumidityReading objects.
        """
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

    def get_humidity_statistics(self, sensor_id: Optional[str] = None, hours_back: int = 24) -> Dict[str, Any]:
        """Calculates humidity statistics for a given period.

        Args:
            sensor_id: An optional sensor ID to filter by.
            hours_back: The number of hours to look back for statistics.

        Returns:
            A dictionary containing the count, min, max, average, and latest
            humidity values, along with timestamps for min/max values.
        """
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

    def get_humidity_readings_by_year(self, year: int, sensor_id: Optional[str] = None) -> List['HumidityReading']:
        """Retrieves humidity readings for a specific year.

        Args:
            year: The year to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of HumidityReading objects.
        """
        try:
            with self.get_session() as session:
                start_time = datetime(year, 1, 1, tzinfo=timezone.utc)
                end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

                query = session.query(HumidityReading).filter(
                    HumidityReading.timestamp >= start_time,
                    HumidityReading.timestamp < end_time
                )

                if sensor_id:
                    query = query.filter(HumidityReading.sensor_id == sensor_id)

                return query.order_by(HumidityReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting humidity readings for year {year}: {e}")
            return []

    def get_humidity_readings_by_month(self, year: int, month: int, sensor_id: Optional[str] = None) -> List['HumidityReading']:
        """Retrieves humidity readings for a specific month.

        Args:
            year: The year of the month.
            month: The month to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of HumidityReading objects.
        """
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, 1, tzinfo=timezone.utc)
                if month == 12:
                    end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                else:
                    end_time = datetime(year, month + 1, 1, tzinfo=timezone.utc)

                query = session.query(HumidityReading).filter(
                    HumidityReading.timestamp >= start_time,
                    HumidityReading.timestamp < end_time
                )

                if sensor_id:
                    query = query.filter(HumidityReading.sensor_id == sensor_id)

                return query.order_by(HumidityReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting humidity readings for {year}-{month}: {e}")
            return []

    def get_humidity_readings_by_day(self, year: int, month: int, day: int, sensor_id: Optional[str] = None) -> List['HumidityReading']:
        """Retrieves humidity readings for a specific day.

        Args:
            year: The year of the day.
            month: The month of the day.
            day: The day to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of HumidityReading objects.
        """
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, day, tzinfo=timezone.utc)
                end_time = start_time + timedelta(days=1)

                query = session.query(HumidityReading).filter(
                    HumidityReading.timestamp >= start_time,
                    HumidityReading.timestamp < end_time
                )

                if sensor_id:
                    query = query.filter(HumidityReading.sensor_id == sensor_id)

                return query.order_by(HumidityReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting humidity readings for {year}-{month}-{day}: {e}")
            return []




    def add_pressure_reading(self, pressure_hpa: float, sensor_type: str = "unknown", sensor_id: str = "default", timestamp: Optional[datetime] = None) -> Optional['PressureReading']:
        """Adds a new pressure reading to the database.

        Args:
            pressure_hpa: The atmospheric pressure in hectopascals.
            sensor_type: The type of sensor.
            sensor_id: The unique ID of the sensor.
            timestamp: The timestamp of the reading. Defaults to now (UTC).

        Returns:
            The created PressureReading object, or None on failure.
        """
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

    def get_recent_pressure_readings(self, limit: int = 100, sensor_id: Optional[str] = None) -> List['PressureReading']:
        """Retrieves the most recent pressure readings.

        Args:
            limit: The maximum number of readings to return.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of PressureReading objects.
        """
        try:
            with self.get_session() as session:
                query = session.query(PressureReading)
                if sensor_id:
                    query = query.filter(PressureReading.sensor_id == sensor_id)
                return query.order_by(PressureReading.timestamp.desc()).limit(limit).all()
        except Exception as e:
            self.logger.error(f"Error getting recent pressure readings: {e}")
            return []

    def get_pressure_statistics(self, sensor_id: Optional[str] = None, hours_back: int = 24) -> Dict[str, Any]:
        """Calculates pressure statistics for a given period.

        Args:
            sensor_id: An optional sensor ID to filter by.
            hours_back: The number of hours to look back for statistics.

        Returns:
            A dictionary containing the count, average, min, and max pressure.
        """
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

    def get_pressure_readings_by_year(self, year: int, sensor_id: Optional[str] = None) -> List['PressureReading']:
        """Retrieves pressure readings for a specific year.

        Args:
            year: The year to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of PressureReading objects.
        """
        try:
            with self.get_session() as session:
                start_time = datetime(year, 1, 1, tzinfo=timezone.utc)
                end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

                query = session.query(PressureReading).filter(
                    PressureReading.timestamp >= start_time,
                    PressureReading.timestamp < end_time
                )

                if sensor_id:
                    query = query.filter(PressureReading.sensor_id == sensor_id)

                return query.order_by(PressureReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting pressure readings for year {year}: {e}")
            return []

    def get_pressure_readings_by_month(self, year: int, month: int, sensor_id: Optional[str] = None) -> List['PressureReading']:
        """Retrieves pressure readings for a specific month.

        Args:
            year: The year of the month.
            month: The month to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of PressureReading objects.
        """
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, 1, tzinfo=timezone.utc)
                if month == 12:
                    end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                else:
                    end_time = datetime(year, month + 1, 1, tzinfo=timezone.utc)

                query = session.query(PressureReading).filter(
                    PressureReading.timestamp >= start_time,
                    PressureReading.timestamp < end_time
                )

                if sensor_id:
                    query = query.filter(PressureReading.sensor_id == sensor_id)

                return query.order_by(PressureReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting pressure readings for {year}-{month}: {e}")
            return []

    def get_pressure_readings_by_day(self, year: int, month: int, day: int, sensor_id: Optional[str] = None) -> List['PressureReading']:
        """Retrieves pressure readings for a specific day.

        Args:
            year: The year of the day.
            month: The month of the day.
            day: The day to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of PressureReading objects.
        """
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, day, tzinfo=timezone.utc)
                end_time = start_time + timedelta(days=1)

                query = session.query(PressureReading).filter(
                    PressureReading.timestamp >= start_time,
                    PressureReading.timestamp < end_time
                )

                if sensor_id:
                    query = query.filter(PressureReading.sensor_id == sensor_id)

                return query.order_by(PressureReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting pressure readings for {year}-{month}-{day}: {e}")
            return []

    def add_air_quality_reading(self, data: dict, sensor_type: str = "unknown", sensor_id: str = "default", timestamp: Optional[datetime] = None) -> Optional['AirQualityReading']:
        """Adds a new air quality reading to the database.

        Args:
            data: A dictionary containing the air quality data points.
            sensor_type: The type of sensor.
            sensor_id: The unique ID of the sensor.
            timestamp: The timestamp of the reading. Defaults to now (UTC).

        Returns:
            The created AirQualityReading object, or None on failure.
        """
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

    def get_recent_air_quality_readings(self, limit: int = 100, sensor_id: Optional[str] = None) -> List['AirQualityReading']:
        """Retrieves the most recent air quality readings.

        Args:
            limit: The maximum number of readings to return.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of AirQualityReading objects.
        """
        try:
            with self.get_session() as session:
                query = session.query(AirQualityReading)
                if sensor_id:
                    query = query.filter(AirQualityReading.sensor_id == sensor_id)
                return query.order_by(AirQualityReading.timestamp.desc()).limit(limit).all()
        except Exception as e:
            self.logger.error(f"Error getting recent AQ readings: {e}")
            return []

    def get_air_quality_statistics(self, sensor_id: Optional[str] = None, hours_back: int = 24) -> Dict[str, Any]:
        """Calculates air quality statistics for a given period.

        Args:
            sensor_id: An optional sensor ID to filter by.
            hours_back: The number of hours to look back for statistics.

        Returns:
            A dictionary containing the count, average, min, and max CO2 levels.
        """
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

    def get_air_quality_readings_by_year(self, year: int, sensor_id: Optional[str] = None) -> List['AirQualityReading']:
        """Retrieves air quality readings for a specific year.

        Args:
            year: The year to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of AirQualityReading objects.
        """
        try:
            with self.get_session() as session:
                start_time = datetime(year, 1, 1, tzinfo=timezone.utc)
                end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

                query = session.query(AirQualityReading).filter(
                    AirQualityReading.timestamp >= start_time,
                    AirQualityReading.timestamp < end_time
                )

                if sensor_id:
                    query = query.filter(AirQualityReading.sensor_id == sensor_id)

                return query.order_by(AirQualityReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting air quality readings for year {year}: {e}")
            return []

    def get_air_quality_readings_by_month(self, year: int, month: int, sensor_id: Optional[str] = None) -> List['AirQualityReading']:
        """Retrieves air quality readings for a specific month.

        Args:
            year: The year of the month.
            month: The month to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of AirQualityReading objects.
        """
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, 1, tzinfo=timezone.utc)
                if month == 12:
                    end_time = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
                else:
                    end_time = datetime(year, month + 1, 1, tzinfo=timezone.utc)

                query = session.query(AirQualityReading).filter(
                    AirQualityReading.timestamp >= start_time,
                    AirQualityReading.timestamp < end_time
                )

                if sensor_id:
                    query = query.filter(AirQualityReading.sensor_id == sensor_id)

                return query.order_by(AirQualityReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting air quality readings for {year}-{month}: {e}")
            return []

    def get_air_quality_readings_by_day(self, year: int, month: int, day: int, sensor_id: Optional[str] = None) -> List['AirQualityReading']:
        """Retrieves air quality readings for a specific day.

        Args:
            year: The year of the day.
            month: The month of the day.
            day: The day to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of AirQualityReading objects.
        """
        try:
            with self.get_session() as session:
                start_time = datetime(year, month, day, tzinfo=timezone.utc)
                end_time = start_time + timedelta(days=1)

                query = session.query(AirQualityReading).filter(
                    AirQualityReading.timestamp >= start_time,
                    AirQualityReading.timestamp < end_time
                )

                if sensor_id:
                    query = query.filter(AirQualityReading.sensor_id == sensor_id)

                return query.order_by(AirQualityReading.timestamp.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting air quality readings for {year}-{month}-{day}: {e}")
            return []

    def add_meter_reading(self, meter_value: str, ocr_engine: Optional[str] = None, raw_ocr_text: Optional[str] = None,
                         sensor_type: str = "esp32cam_ocr", sensor_id: str = "cabana1_meter",
                         timestamp: Optional[datetime] = None) -> Optional['MeterReading']:
        """Adds a new meter reading to the database.

        Args:
            meter_value: The value read from the meter.
            ocr_engine: The name of the OCR engine used.
            raw_ocr_text: The raw text output from the OCR engine.
            sensor_type: The type of sensor.
            sensor_id: The unique ID of the sensor.
            timestamp: The timestamp of the reading. Defaults to now (UTC).

        Returns:
            The created MeterReading object, or None on failure.
        """
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

    def get_recent_meter_readings(self, limit: int = 100, sensor_id: Optional[str] = None) -> List['MeterReading']:
        """Retrieves the most recent meter readings.

        Args:
            limit: The maximum number of readings to return.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of MeterReading objects.
        """
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

    def get_meter_readings_by_year(self, year: int, sensor_id: Optional[str] = None) -> List['MeterReading']:
        """Retrieves meter readings for a specific year.

        Args:
            year: The year to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of MeterReading objects.
        """
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

    def get_meter_readings_by_month(self, year: int, month: int, sensor_id: Optional[str] = None) -> List['MeterReading']:
        """Retrieves meter readings for a specific month.

        Args:
            year: The year of the month.
            month: The month to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of MeterReading objects.
        """
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

    def get_meter_readings_by_day(self, year: int, month: int, day: int, sensor_id: Optional[str] = None) -> List['MeterReading']:
        """Retrieves meter readings for a specific day.

        Args:
            year: The year of the day.
            month: The month of the day.
            day: The day to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of MeterReading objects.
        """
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

    def get_meter_statistics(self, sensor_id: Optional[str] = None, hours_back: int = 24) -> Dict[str, Any]:
        """Calculates meter reading statistics for a given period.

        Args:
            sensor_id: An optional sensor ID to filter by.
            hours_back: The number of hours to look back for statistics.

        Returns:
            A dictionary containing the count, first and last values, and
            their corresponding timestamps.
        """
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
    def get_readings_by_year(self, year: int, sensor_id: Optional[str] = None) -> List[TemperatureReading]:
        """Retrieves temperature readings for a specific year.

        Args:
            year: The year to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of TemperatureReading objects.
        """
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
    
    def get_readings_by_month(self, year: int, month: int, sensor_id: Optional[str] = None) -> List[TemperatureReading]:
        """Retrieves temperature readings for a specific month.

        Args:
            year: The year of the month.
            month: The month to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of TemperatureReading objects.
        """
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
    
    def get_readings_by_day(self, year: int, month: int, day: int, sensor_id: Optional[str] = None) -> List[TemperatureReading]:
        """Retrieves temperature readings for a specific day.

        Args:
            year: The year of the day.
            month: The month of the day.
            day: The day to retrieve data for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A list of TemperatureReading objects.
        """
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
    
    def get_yearly_statistics(self, year: int, sensor_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculates temperature statistics for a specific year.

        Args:
            year: The year to calculate statistics for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A dictionary containing yearly statistics.
        """
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
    
    def get_monthly_statistics(self, year: int, month: int, sensor_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculates temperature statistics for a specific month.

        Args:
            year: The year of the month.
            month: The month to calculate statistics for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A dictionary containing monthly statistics.
        """
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
    
    def get_daily_statistics(self, year: int, month: int, day: int, sensor_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculates temperature statistics for a specific day.

        Args:
            year: The year of the day.
            month: The month of the day.
            day: The day to calculate statistics for.
            sensor_id: An optional sensor ID to filter by.

        Returns:
            A dictionary containing daily statistics.
        """
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
    """SQLAlchemy model for storing atmospheric pressure readings.

    Attributes:
        id (int): The primary key for the reading.
        timestamp (datetime): The UTC timestamp when the reading was taken.
        timestamp_unix (float): The Unix timestamp of the reading.
        pressure_hpa (float): The pressure in hectopascals (hPa).
        sensor_type (str): The type of sensor that produced the reading.
        sensor_id (str): The unique identifier of the sensor.
    """
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
    """SQLAlchemy model for storing air quality readings.

    Attributes:
        id (int): The primary key for the reading.
        timestamp (datetime): The UTC timestamp when the reading was taken.
        timestamp_unix (float): The Unix timestamp of the reading.
        co2_ppm (float): CO2 concentration in parts per million.
        nh3_ppm (float): NH3 (ammonia) concentration in parts per million.
        alcohol_ppm (float): Alcohol vapor concentration in parts per million.
        aqi (int): The calculated Air Quality Index.
        status (str): A descriptive status of the air quality (e.g., "Good").
        raw_adc (int): The raw ADC value from the sensor.
        voltage_v (float): The voltage reading from the sensor.
        resistance_ohm (float): The calculated resistance of the sensor.
        ratio_rs_r0 (float): The ratio of sensor resistance to base resistance.
        sensor_type (str): The type of sensor that produced the reading.
        sensor_id (str): The unique identifier of the sensor.
    """
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

    def to_dict(self) -> Dict[str, Any]:
        """Converts the AirQualityReading model instance to a dictionary.

        Returns:
            A dictionary representation of the model.
        """
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
    """SQLAlchemy model for storing electricity meter readings from OCR.

    Attributes:
        id (int): The primary key for the reading.
        timestamp (datetime): The UTC timestamp when the reading was taken.
        timestamp_unix (float): The Unix timestamp of the reading.
        meter_value (str): The value read from the meter.
        ocr_engine (str): The name of the OCR engine used for the reading.
        raw_ocr_text (str): The raw text output from the OCR engine.
        sensor_type (str): The type of sensor (e.g., 'esp32cam_ocr').
        sensor_id (str): The unique identifier of the meter.
    """

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

    def to_dict(self) -> Dict[str, Any]:
        """Converts the MeterReading model instance to a dictionary.

        Returns:
            A dictionary representation of the model.
        """
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

    def __repr__(self) -> str:
        """Provides a developer-friendly representation of the object."""
        return f'<MeterReading(id={self.id}, value={self.meter_value}, sensor={self.sensor_id}, time={self.timestamp})>'

def init_database(database_url: Optional[str] = None):
    """Initializes the global database instance.

    This function creates and initializes the global `db` object which is an
    instance of DatabaseManager.

    Args:
        database_url: An optional database URL to use for initialization.
    """
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