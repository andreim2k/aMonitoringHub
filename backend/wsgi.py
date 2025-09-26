from app import app as application

# Gunicorn entrypoint:
# gunicorn -w 2 -k gthread -b 0.0.0.0:5000 backend.wsgi:application --log-level info
