# Implementation Guide - Code Review Fixes
**Quick reference for implementing the code review recommendations**

---

## 1. ADD API KEY AUTHENTICATION

### Step 1: Create auth decorator
```python
# backend/auth.py
from functools import wraps
from flask import request, jsonify
import os

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        expected_key = os.environ.get('API_KEY')
        
        if not expected_key:
            return jsonify({'error': 'API_KEY not configured'}), 500
        
        if not api_key or api_key != expected_key:
            return jsonify({'error': 'Unauthorized'}), 401
        
        return f(*args, **kwargs)
    return decorated_function
```

### Step 2: Apply to sensitive endpoints
```python
# backend/app.py
from auth import require_api_key

@app.route('/webcam/ocr', methods=['POST'])
@require_api_key
def run_ocr():
    # Protected endpoint
    ...

@app.route('/config', methods=['POST'])
@require_api_key
def update_config():
    # Protected endpoint
    ...
```

### Step 3: Set environment variable
```bash
export API_KEY="your-secure-random-key-here"
# Or in .env file
API_KEY=your-secure-random-key-here
```

---

## 2. ADD RATE LIMITING

### Step 1: Install package
```bash
pip install flask-limiter
```

### Step 2: Configure in app.py
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Apply to endpoints
@app.route('/graphql', methods=['POST'])
@limiter.limit("100 per hour")
def graphql_endpoint():
    ...

@app.route('/webcam/ocr', methods=['POST'])
@limiter.limit("10 per hour")  # Stricter for expensive operations
def run_ocr():
    ...
```

---

## 3. ADD INPUT VALIDATION

### Step 1: Install marshmallow
```bash
pip install marshmallow
```

### Step 2: Create validation schemas
```python
# backend/schemas.py
from marshmallow import Schema, fields, validate, ValidationError

class TemperatureReadingSchema(Schema):
    temperature_c = fields.Float(
        required=True,
        validate=validate.Range(min=-50, max=150)
    )
    sensor_type = fields.Str(required=True)
    sensor_id = fields.Str(required=True)

class QueryParamsSchema(Schema):
    year = fields.Int(validate=validate.Range(min=2000, max=2100))
    month = fields.Int(validate=validate.Range(min=1, max=12))
    day = fields.Int(validate=validate.Range(min=1, max=31))
    limit = fields.Int(validate=validate.Range(min=1, max=10000))
    hours = fields.Int(validate=validate.Range(min=1, max=8760))
```

### Step 3: Use in endpoints
```python
from schemas import TemperatureReadingSchema

@app.route('/api/temperature', methods=['POST'])
def add_temperature():
    schema = TemperatureReadingSchema()
    try:
        data = schema.load(request.get_json())
    except ValidationError as e:
        return jsonify({'error': e.messages}), 400
    
    # Process validated data
    reading = db.add_temperature_reading(**data)
    return jsonify({'success': True, 'id': reading.id})
```

---

## 4. FIX EXCEPTION HANDLING

### Before (Too Broad)
```python
try:
    result = db.query(...)
except Exception as e:  # ❌ Catches everything
    logger.error(f"Error: {e}")
    return None
```

### After (Specific)
```python
from sqlalchemy.exc import SQLAlchemyError

try:
    result = db.query(...)
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    return None
except Exception as e:
    logger.critical(f"Unexpected error: {e}", exc_info=True)
    raise
```

---

## 5. ADD HEALTH CHECK ENDPOINT

```python
# backend/app.py
@app.route('/health', methods=['GET'])
def health_check():
    """Standard health check endpoint"""
    try:
        # Check database
        db_healthy = db.get_total_readings_count() >= 0
        
        # Check USB connection
        usb_healthy = usb_reader.is_connected() if usb_reader else False
        
        # Overall status
        healthy = db_healthy
        
        return jsonify({
            "status": "healthy" if healthy else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "database": "ok" if db_healthy else "error",
                "usb_sensor": "ok" if usb_healthy else "disconnected"
            }
        }), 200 if healthy else 503
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 503
```

---

## 6. STANDARDIZE ERROR RESPONSES

```python
# backend/app.py
def error_response(message: str, code: int = 500, **extra):
    """Standardized error response"""
    return jsonify({
        "success": False,
        "error": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **extra
    }), code

# Usage
return error_response("Invalid input", 400)
return error_response("Database error", 500, details="Connection failed")
```

---

## 7. PIN DEPENDENCY VERSIONS

### Before
```txt
gunicorn>=21.2.0
requests>=2.32.0
Pillow>=11.3.0
```

### After
```txt
# Exact versions for reproducibility
gunicorn==21.2.0
requests==2.32.3
Pillow==11.3.0
Flask==3.1.2
flask-cors==6.0.1
Werkzeug==3.1.3
graphene==3.4.3
graphql-core==3.2.6
SQLAlchemy==2.0.43
APScheduler==3.11.0
pyserial==3.5
```

---

## 8. ADD FRONTEND ERROR HANDLING

```javascript
// frontend/js/error-handler.js
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
    showErrorNotification('An error occurred. Refreshing data...');
    
    // Attempt recovery
    setTimeout(() => {
        location.reload();
    }, 5000);
});

window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    showErrorNotification('Connection error. Retrying...');
});

// Add request timeout
async function fetchWithTimeout(url, options = {}, timeout = 10000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(id);
        return response;
    } catch (error) {
        clearTimeout(id);
        if (error.name === 'AbortError') {
            throw new Error('Request timeout');
        }
        throw error;
    }
}
```

---

## 9. ADD BASIC UNIT TESTS

```python
# tests/test_models.py
import pytest
from backend.models import DatabaseManager, TemperatureReading

@pytest.fixture
def db():
    """Create in-memory database for testing"""
    db = DatabaseManager(database_url="sqlite:///:memory:")
    db.initialize()
    return db

def test_add_temperature_reading(db):
    reading = db.add_temperature_reading(
        temperature_c=22.5,
        sensor_type="test",
        sensor_id="test_sensor"
    )
    
    assert reading is not None
    assert reading.temperature_c == 22.5
    assert reading.sensor_type == "test"

def test_temperature_validation(db):
    with pytest.raises(ValueError):
        db.add_temperature_reading(
            temperature_c=999.0,  # Invalid
            sensor_type="test",
            sensor_id="test_sensor"
        )

def test_get_recent_readings(db):
    # Add test data
    for i in range(5):
        db.add_temperature_reading(
            temperature_c=20.0 + i,
            sensor_type="test",
            sensor_id="test_sensor"
        )
    
    # Query
    readings = db.get_recent_readings(3)
    assert len(readings) == 3
```

---

## 10. SETUP TESTING FRAMEWORK

```bash
# Install dependencies
pip install pytest pytest-cov pytest-flask

# Create test structure
mkdir tests
touch tests/__init__.py
touch tests/test_models.py
touch tests/test_api.py
touch tests/conftest.py

# Run tests
pytest tests/ -v --cov=backend --cov-report=html

# Check coverage
open htmlcov/index.html
```

---

## IMPLEMENTATION CHECKLIST

- [ ] Create auth.py with require_api_key decorator
- [ ] Apply @require_api_key to sensitive endpoints
- [ ] Set API_KEY environment variable
- [ ] Install and configure flask-limiter
- [ ] Create schemas.py with validation schemas
- [ ] Add input validation to endpoints
- [ ] Fix exception handling (use specific exceptions)
- [ ] Add /health endpoint
- [ ] Create error_response helper function
- [ ] Pin all dependency versions
- [ ] Add frontend error handlers
- [ ] Set up pytest framework
- [ ] Write unit tests (target 70% coverage)
- [ ] Add CI/CD pipeline

---

**Estimated Time:** 20-30 hours for all fixes  
**Priority Order:** Security → Testing → Code Quality → Architecture

