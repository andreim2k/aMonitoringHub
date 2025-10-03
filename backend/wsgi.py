"""
WSGI entry point for the aMonitoringHub application.

This file is used by Gunicorn or other WSGI servers to run the application.
It imports the Flask app instance from the main `app` module.
"""

from app import app as application

# Example Gunicorn entrypoint command:
# gunicorn -w 2 -k gthread -b 0.0.0.0:5000 backend.wsgi:application --log-level info
