"""
SQLAlchemy models for aTemperature application.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, Float, DateTime, String, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
import logging

Base = declarative_base()


class TemperatureReading(Base):
    """Temperature reading model."""
    
    __tablename__ = 'temperature_readings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
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


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or "sqlite:///temperature.db"
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
            
    def add_temperature_reading(self, temperature_c: float, sensor_type: str = "unknown", 
                               sensor_id: str = "default", timestamp: datetime = None) -> Optional[TemperatureReading]:
        """Add a temperature reading to the database."""
        try:
            with self.get_session() as session:
                reading = TemperatureReading(
                    temperature_c=temperature_c,
                    sensor_type=sensor_type,
                    sensor_id=sensor_id,
                    timestamp=timestamp or datetime.now(timezone.utc)
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
                
                return {
                    'count': result.count or 0,
                    'average': round(result.avg or 0, 2),
                    'minimum': round(result.min or 0, 2),
                    'maximum': round(result.max or 0, 2),
                    'hours_back': hours_back
                }
                
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {'count': 0, 'average': 0, 'minimum': 0, 'maximum': 0, 'hours_back': hours_back}
            
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


# Global database instance
db = DatabaseManager()


def init_database(database_url: str = None):
    """Initialize the global database instance."""
    global db
    if database_url:
        db = DatabaseManager(database_url)
    db.initialize()
    

if __name__ == "__main__":
    # Test the database models
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Initialize database
        init_database()
        
        # Add some test data
        print("Adding test temperature readings...")
        base_time = datetime.now(timezone.utc)
        
        for i in range(10):
            temp = 20.0 + (i % 5) * 0.5  # Temperatures between 20-22°C
            timestamp = base_time - timedelta(minutes=i)
            reading = db.add_temperature_reading(temp, "test", "test_sensor", timestamp)
            print(f"Added: {reading}")
            
        # Test queries
        print("\nRecent readings:")
        recent = db.get_recent_readings(5)
        for reading in recent:
            print(f"  {reading}")
            
        print("\nStatistics:")
        stats = db.get_statistics()
        print(f"  {stats}")
        
        print("\nDatabase test completed successfully!")
        
    except Exception as e:
        print(f"Database test failed: {e}")
        sys.exit(1)
