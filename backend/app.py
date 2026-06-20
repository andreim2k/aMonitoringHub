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
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional
from queue import Queue
import threading
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Helper to present timestamps in local system time
from datetime import timezone as _tzmod, datetime as _dtmod

def _thin(items: list, limit: int) -> list:
    """Evenly downsample a list to at most `limit` items."""
    if len(items) <= limit:
        return items
    step = len(items) / limit
    return [items[int(i * step)] for i in range(limit)]


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
from graphene import ObjectType, String, Float, List as GrapheneList, Field, Int, Schema, Boolean

# Import our modules
from models import init_database, db, TemperatureReading as DBTemperatureReading, HumidityReading as DBHumidityReading, MeterReading as DBMeterReading, WeatherReading as DBWeatherReading
from sensor_reader import TemperatureSensorReader, HumiditySensorReader
from usb_json_reader import USBJSONReader

# Configure logging (use config.json instead of .env)
log_level = app_config.get('app', {}).get('log_level', 'INFO').upper()
# Ensure USBJSONReader health checks are visible (use WARNING level minimum for health checks)
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../logs/backend.log'),
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

# Weather calculation constants
ALTITUDE_M = 650  # Mountain location altitude in meters

def calculate_local_weather(temp_c: float, humidity: float, pressure_hpa: float) -> Dict[str, Any]:
    """Calculate local weather conditions from BME280 sensor data.

    Accounts for 650m altitude. Returns weather condition, description, sea-level pressure, and dew point.

    Args:
        temp_c: Temperature in Celsius
        humidity: Relative humidity (0-100%)
        pressure_hpa: Barometric pressure in hPa

    Returns:
        Dict with keys: condition, description, sea_level_pressure_hpa, dew_point_c
    """
    import math

    # Calculate sea-level pressure (hypsometric formula)
    if temp_c != -273.15:  # Avoid division by zero
        sea_level_pressure = pressure_hpa / pow(
            1 - (0.0065 * ALTITUDE_M) / (temp_c + 273.15 + 0.0065 * ALTITUDE_M),
            5.257
        )
    else:
        sea_level_pressure = pressure_hpa

    # Calculate dew point (Magnus formula)
    a, b = 17.27, 237.7
    if humidity > 0:
        alpha = (a * temp_c / (b + temp_c)) + math.log(humidity / 100.0)
        dew_point = (b * alpha) / (a - alpha)
    else:
        dew_point = temp_c

    temp_dew_spread = temp_c - dew_point

    # Determine weather condition (priority order)
    if sea_level_pressure < 990 and humidity > 80:
        condition, description = "Thunderstorm", "violent thunderstorm"
    elif sea_level_pressure < 1000 and humidity > 75 and temp_c >= 5:
        condition, description = "Rain", "heavy rain"
    elif sea_level_pressure < 1000 and humidity > 75 and 2 <= temp_c < 5:
        condition, description = "Sleet", "sleet/ice pellets"
    elif sea_level_pressure < 1000 and humidity > 75 and temp_c < 2:
        condition, description = "Snow", "heavy snowfall"
    elif sea_level_pressure < 1005 and humidity > 70 and temp_c >= 5:
        condition, description = "Drizzle", "light rain"
    elif sea_level_pressure < 1005 and humidity > 70 and 2 <= temp_c < 5:
        condition, description = "Sleet", "light sleet"
    elif sea_level_pressure < 1005 and humidity > 70 and temp_c < 2:
        condition, description = "Snow", "light snowfall"
    elif temp_dew_spread < 2.5 and humidity > 85:
        condition, description = "Fog", "foggy conditions"
    elif sea_level_pressure < 1010 and humidity > 60:
        condition, description = "CloudsHeavy", "overcast/cloudy"
    elif humidity > 60 or sea_level_pressure < 1015:
        condition, description = "Clouds", "partly cloudy"
    else:
        condition, description = "Clear", "clear sky"

    return {
        'condition': condition,
        'description': description,
        'sea_level_pressure_hpa': round(sea_level_pressure, 1),
        'dew_point_c': round(dew_point, 1)
    }

# Global variables
temperature_sensor = None
scheduler = None
usb_reader = None
sse_clients = Queue()
sse_subscribers = 0
sse_subscribers_lock = threading.Lock()

# Configurable throttling system
THROTTLE_INTERVAL = 60  # Default: 1 minute in seconds (reduced from 1 hour for more data points)
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




_esp32cam_last_status = {'up': False, 'ready': False, 'checked_at': 0, 'uptime_ms': None}

_PLUG_DPS_CURRENT = "21"   # mA
_PLUG_DPS_POWER   = "22"   # 0.1 W
_PLUG_DPS_VOLTAGE = "23"   # 0.1 V
_smartplug_last = {'volts': None, 'amps': None, 'watts': None, 'polled_at': 0, 'online': False}
_smartplug_lock = threading.Lock()  # only one TCP connection to the device at a time


def scheduled_heartbeat_task():
    """Records a per-minute system heartbeat (which sensors are up)."""
    try:
        current_time = time.time()

        bm280_up = False
        mq135_up = False
        if hasattr(app, 'usb_data_processor') and app.usb_data_processor:
            if app.usb_data_processor.last_bm280_reading:
                bm280_up = (current_time - app.usb_data_processor.last_bm280_reading) < 120
            if app.usb_data_processor.last_mq135_reading:
                mq135_up = (current_time - app.usb_data_processor.last_mq135_reading) < 120

        esp32cam_up = False
        esp32cam_ready = False
        try:
            cfg = load_app_config()
            esp32_url = cfg.get('webcam', {}).get('url', '').replace('/snapshot', '').replace('/capture', '')
            if esp32_url:
                response = requests.get(f"{esp32_url}/status", timeout=3)
                esp32cam_up = response.status_code == 200
                if esp32cam_up:
                    try:
                        body = response.json()
                        cam = body.get('camera') if isinstance(body, dict) else None
                        esp32cam_ready = bool(cam.get('ready')) if isinstance(cam, dict) else True
                        _esp32cam_last_status['uptime_ms'] = body.get('uptime_ms') if isinstance(body, dict) else None
                    except Exception:
                        esp32cam_ready = True
        except Exception:
            esp32cam_up = False
            esp32cam_ready = False

        _esp32cam_last_status['up'] = esp32cam_up
        _esp32cam_last_status['ready'] = esp32cam_ready
        _esp32cam_last_status['checked_at'] = current_time

        db.add_heartbeat(bm280_up, mq135_up, esp32cam_up and esp32cam_ready)
    except Exception as e:
        logger.error(f"Heartbeat task error: {e}")


def _poll_smartplug_device():
    """Connect to the Tuya device and return fresh (volts, amps, watts) or raise."""
    import tinytuya
    cfg = load_app_config()
    plug_cfg = cfg.get('smartplug', {})
    key = plug_cfg.get('local_key', '')
    device_id = plug_cfg.get('device_id', '')
    ip = plug_cfg.get('ip', '')
    version = plug_cfg.get('version', 3.5)
    if not key or not device_id or not ip:
        raise ValueError("Smart plug not configured")
    plug = tinytuya.OutletDevice(dev_id=device_id, address=ip, local_key=key, version=version)
    plug.set_socketTimeout(6)
    result = plug.updatedps(index=[int(_PLUG_DPS_CURRENT), int(_PLUG_DPS_POWER), int(_PLUG_DPS_VOLTAGE)])
    dps = result.get('dps', {}) if isinstance(result, dict) else {}
    # updatedps sometimes returns partial DPS (missing voltage); fall back to status() for a full read
    if _PLUG_DPS_VOLTAGE not in dps or _PLUG_DPS_POWER not in dps or _PLUG_DPS_CURRENT not in dps:
        status = plug.status()
        full_dps = status.get('dps', {}) if isinstance(status, dict) else {}
        dps = {**full_dps, **dps}  # merge: updatedps values win over status() values
    if _PLUG_DPS_VOLTAGE not in dps or _PLUG_DPS_POWER not in dps:
        raise ValueError("No complete DPS data from device")
    volts = dps.get(_PLUG_DPS_VOLTAGE, 0) / 10.0
    amps  = dps.get(_PLUG_DPS_CURRENT, 0) / 1000.0
    watts = dps.get(_PLUG_DPS_POWER,   0) / 10.0
    return volts, amps, watts


def scheduled_smartplug_task():
    """Poll the Tuya T34 smart plug and record voltage, current, and power."""
    global _smartplug_last
    if not _smartplug_lock.acquire(blocking=False):
        return  # another poll is already in progress
    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_poll_smartplug_device)
            try:
                volts, amps, watts = future.result(timeout=12)
            except FuturesTimeout:
                future.cancel()
                raise RuntimeError("Device poll timed out after 12s")
        now = time.time()
        _smartplug_last.update({'volts': volts, 'amps': amps, 'watts': watts, 'polled_at': now, 'online': True})
        db.add_plug_reading(volts, amps, watts)
        if has_sse_subscribers():
            try:
                sse_clients.put_nowait({
                    'type': 'smartplug_update',
                    'data': {
                        'voltage_v': volts,
                        'current_a': amps,
                        'power_w': watts,
                        'timestamp': now,
                        'timestamp_iso': datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
                    }
                })
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Smart plug poll error: {e}")
        # Don't touch _smartplug_last on failure — preserve last good state.
        # The sensor_status SSE age check will show 'stale' after 90s naturally.
    finally:
        _smartplug_lock.release()


# Power outage monitoring (Clopotiva, Hunedoara) — polls the public ArcGIS map API
OUTAGE_API_URL = "https://services-eu1.arcgis.com/ZugzWQbNk6XT3BMo/arcgis/rest/services/OutagesMapViewLayer/FeatureServer/0/query"
OUTAGE_TARGET_COUNTY = "HUNEDOARA"
OUTAGE_TARGET_LOCALITY_SUBSTR = "CLOPOTIVA"
_outage_last_poll: Optional[datetime] = None  # set by scheduled_outage_check_task


def _parse_outage_dt(s: Optional[str]) -> Optional[datetime]:
    """Parse 'DD/MM/YYYY HH:MM' as Europe/Bucharest local time, return UTC datetime."""
    if not s:
        return None
    try:
        naive = datetime.strptime(s.strip(), "%d/%m/%Y %H:%M")
        # Bucharest is UTC+2 (winter) or UTC+3 (summer DST). zoneinfo handles both correctly.
        try:
            from zoneinfo import ZoneInfo
            local = naive.replace(tzinfo=ZoneInfo("Europe/Bucharest"))
            return local.astimezone(timezone.utc)
        except Exception:
            return naive.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def scheduled_outage_check_task():
    """Polls the public outage map API and stores any outages matching the target locality."""
    global _outage_last_poll
    try:
        params = {
            "where": f"provincia='{OUTAGE_TARGET_COUNTY}'",
            "outFields": "*",
            "f": "json",
            "resultRecordCount": 2000,
        }
        r = requests.get(OUTAGE_API_URL, params=params, timeout=15)
        if r.status_code != 200:
            logger.warning(f"Outage API returned status {r.status_code}")
            return
        data = r.json()
        features = data.get("features", []) or []

        target = OUTAGE_TARGET_LOCALITY_SUBSTR.upper()
        active_codes = []
        matched = 0
        for f in features:
            a = f.get("attributes", {}) or {}
            descr = (a.get("descrizion") or "").upper()
            if target not in descr:
                continue
            code = a.get("outage_unique_code") or f"FID_{a.get('fid0')}"
            if not code:
                continue
            start_str = a.get("data_inter")
            attrs = {
                "cause_type":     a.get("causa_disa"),
                "locality":       a.get("descrizion"),
                "county":         a.get("provincia"),
                "region":         a.get("regione"),
                "start_time":     _parse_outage_dt(start_str),
                "start_time_str": start_str,
                "expected_end":   a.get("data_prev_") or a.get("data_prev_en"),
                "latitude":       a.get("latitudine"),
                "longitude":      a.get("longitudin"),
                "num_affected":   int(a.get("num_cli_di") or 0),
            }
            if db.upsert_outage(code, attrs):
                active_codes.append(code)
                matched += 1

        # Anything we had marked active that isn't in this poll → resolved.
        # Scope the resolution to the target county so we never touch outages
        # from a future expansion of the filter.
        resolved = db.mark_outages_inactive(active_codes,
                                            scope_filter_county=OUTAGE_TARGET_COUNTY,
                                            exclude_prefix='PDF_')
        _outage_last_poll = datetime.now(timezone.utc)
        logger.info(f"Outage poll: {matched} active match(es) for {target}/{OUTAGE_TARGET_COUNTY}, {resolved} resolved")
    except Exception as e:
        logger.error(f"Outage poll error: {e}")


# --- PDF-based scheduled outage parsing ---
OUTAGE_LIST_PAGE_URL = "https://www.reteleelectrice.ro/intreruperi/programate/"
_outage_pdf_last_check: Optional[datetime] = None  # set by scheduled_pdf_outage_check_task

_ROMANIAN_DAYS_RE = r'(Luni|Marți|Miercuri|Joi|Vineri|Sâmbătă|Duminică)'
_PDF_DATE_RE   = re.compile(_ROMANIAN_DAYS_RE + r'[,\s]+(\d{2})\.(\d{2})\.(\d{4})')
_PDF_TIME_RE   = re.compile(r'(\d{2}):(\d{2})\s*[-–]\s*(\d{2}):(\d{2})')
_PDF_STREET_RE = re.compile(r'^(Str\.|Strada\s|Sos\.|Soseaua|DN\d|DJ\d|DC\d)', re.IGNORECASE)
_PDF_FNAME_RE  = re.compile(r'(\d{2})\.(\d{2})\.(\d{4})\s*-\s*(\d{2})\.(\d{2})\.(\d{4})\.pdf')


def parse_outages_pdf(pdf_path: str, target_loc: str) -> list:
    """Parse a weekly outage PDF and return entries matching the target locality."""
    try:
        import pypdf
    except ImportError:
        logger.warning("pypdf not installed - skipping PDF parsing")
        return []
    try:
        reader = pypdf.PdfReader(pdf_path)
    except Exception as e:
        logger.warning(f"Cannot read PDF {pdf_path}: {e}")
        return []

    text = ''
    for p in reader.pages:
        text += '\n' + (p.extract_text() or '')

    matches = list(_PDF_DATE_RE.finditer(text))
    target_up = target_loc.upper()
    LOC_HEAD = 80  # only check first 80 chars after each date marker
    out = []
    for i, m in enumerate(matches):
        chunk_start = m.end()
        chunk_end = matches[i+1].start() if i+1 < len(matches) else min(chunk_start + 1500, len(text))
        chunk = text[chunk_start:chunk_end].lstrip()

        if _PDF_STREET_RE.match(chunk):
            continue
        head = chunk[:LOC_HEAD].upper()
        pos = head.find(target_up)
        if pos < 0:
            continue
        # Word boundary checks
        if pos > 0 and (chunk[pos-1].isalpha() or chunk[pos-1] in '.-/'):
            continue
        end_pos = pos + len(target_up)
        if end_pos < len(chunk) and chunk[end_pos].isalpha():
            continue

        tm = _PDF_TIME_RE.search(chunk)
        if tm:
            time_str = f'{tm.group(1)}:{tm.group(2)} - {tm.group(3)}:{tm.group(4)}'
            details = chunk[end_pos:tm.start()].strip()
            sh, sm_, eh, em = int(tm.group(1)), int(tm.group(2)), int(tm.group(3)), int(tm.group(4))
        else:
            time_str = None
            details = chunk[end_pos:].strip()
            sh = sm_ = eh = em = None
        details = re.sub(r'\s+', ' ', details)
        details = re.sub(r'^Alte\s+detalii:\s*', '', details, flags=re.IGNORECASE)
        details = details.strip(' ,;')[:500]

        out.append({
            'day': m.group(1),
            'date_iso': f'{m.group(4)}-{m.group(3)}-{m.group(2)}',
            'time_range': time_str,
            'start_h': sh, 'start_m': sm_, 'end_h': eh, 'end_m': em,
            'locality': chunk[pos:end_pos],
            'details': details,
        })
    return out


def fetch_outage_pdf_urls(now_utc: datetime) -> list:
    """Scrape the listing page and return [(url, range_start_date, range_end_date)] for
    PDFs that cover today or any of the next 28 days. URLs include AWS presigned params."""
    try:
        import html as html_mod, urllib.parse
        r = requests.get(OUTAGE_LIST_PAGE_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if r.status_code != 200:
            logger.warning(f"Outage listing page returned status {r.status_code}")
            return []
        src = r.text
        urls = re.findall(r'href="(https://[^"]+\.pdf\?[^"]+)"', src)
        today = now_utc.date()
        cutoff_future = today + timedelta(days=28)
        results = []
        for raw_url in urls:
            url = html_mod.unescape(raw_url)
            fname = urllib.parse.unquote(url.split('?')[0])
            m = _PDF_FNAME_RE.search(fname)
            if not m:
                continue
            try:
                start = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()
                end   = datetime(int(m.group(6)), int(m.group(5)), int(m.group(4))).date()
            except ValueError:
                continue
            # Keep weeks that overlap [today, today+28d]
            if end >= today and start <= cutoff_future:
                results.append((url, start, end))
        # Dedupe by start date (some listings repeat)
        seen = set()
        deduped = []
        for u, s, e in sorted(results, key=lambda r: r[1]):
            if s in seen:
                continue
            seen.add(s)
            deduped.append((u, s, e))
        return deduped
    except Exception as e:
        logger.error(f"fetch_outage_pdf_urls error: {e}")
        return []


def scheduled_pdf_outage_check_task():
    """Download and parse weekly outage PDFs for upcoming Clopotiva entries."""
    global _outage_pdf_last_check
    try:
        from zoneinfo import ZoneInfo
        BUC = ZoneInfo('Europe/Bucharest')
    except Exception:
        BUC = None

    now_utc = datetime.now(timezone.utc)
    pdfs = fetch_outage_pdf_urls(now_utc)
    logger.info(f"PDF scan: {len(pdfs)} candidate weekly PDF(s)")

    total_matches = 0
    for url, start_d, end_d in pdfs:
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"PDF download failed ({resp.status_code}) for week {start_d}")
                continue
            tmp_path = f'/tmp/outage_week_{start_d.isoformat()}.pdf'
            with open(tmp_path, 'wb') as f:
                f.write(resp.content)
            entries = parse_outages_pdf(tmp_path, OUTAGE_TARGET_LOCALITY_SUBSTR)
            for e in entries:
                date_iso = e['date_iso']  # YYYY-MM-DD
                sh, sm_ = e['start_h'] or 0, e['start_m'] or 0
                eh, em  = e['end_h']   or 0, e['end_m']   or 0
                try:
                    y, mo, d = (int(x) for x in date_iso.split('-'))
                    naive_start = datetime(y, mo, d, sh, sm_)
                    naive_end   = datetime(y, mo, d, eh, em)
                    if BUC:
                        start_utc = naive_start.replace(tzinfo=BUC).astimezone(timezone.utc)
                        end_utc   = naive_end.replace(tzinfo=BUC).astimezone(timezone.utc)
                    else:
                        start_utc = naive_start.replace(tzinfo=timezone.utc)
                        end_utc   = naive_end.replace(tzinfo=timezone.utc)
                except Exception:
                    start_utc = end_utc = None
                code = f"PDF_{date_iso}_{e['locality'].upper().replace(' ','')}_{sh:02d}{sm_:02d}"
                attrs = {
                    'cause_type':     'Planificat',
                    'locality':       e['locality'],
                    'county':         OUTAGE_TARGET_COUNTY,
                    'region':         'BANAT',
                    'start_time':     start_utc,
                    'start_time_str': f"{e['day']}, {date_iso} {sh:02d}:{sm_:02d}",
                    'end_time':       end_utc,
                    'expected_end':   f"{date_iso} {eh:02d}:{em:02d}",
                    'details':        e['details'],
                    'latitude':       None,
                    'longitude':      None,
                    'num_affected':   0,
                }
                if db.upsert_outage(code, attrs):
                    total_matches += 1
        except Exception as ex:
            logger.error(f"PDF process error for week {start_d}: {ex}")

    _outage_pdf_last_check = datetime.now(timezone.utc)
    logger.info(f"PDF scan complete: {total_matches} Clopotiva entries upserted")


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

class PressureTrend(ObjectType):
    """GraphQL type for pressure trend and rain risk prediction."""
    pressure_now = Float()
    change_1h = Float()
    trend_direction = String()
    rain_risk = String()
    description = String()
    readings_used = Int()

class WeatherReading(ObjectType):
    """GraphQL type for a single weather reading."""
    id = Int()
    condition = String()
    description = String()
    timestamp = String()
    timestamp_unix = Float()
    sensor_type = String()
    sensor_id = String()

class CurrentWeather(ObjectType):
    """GraphQL type for calculated current weather from sensor data."""
    condition = String()
    description = String()
    temperature_c = Float()
    humidity_percent = Float()
    pressure_hpa = Float()
    sea_level_pressure_hpa = Float()
    dew_point_c = Float()
    timestamp = String()

class SystemHeartbeat(ObjectType):
    """GraphQL type for a single per-minute system heartbeat."""
    timestamp = String()
    timestamp_unix = Float()
    bm280_up = Boolean()
    mq135_up = Boolean()
    esp32cam_up = Boolean()

class UptimeStats(ObjectType):
    """GraphQL type for sensor uptime percentages over a period."""
    hours_back = Int()
    bm280_uptime_percent = Float()
    mq135_uptime_percent = Float()
    esp32cam_uptime_percent = Float()
    total_uptime_percent = Float()
    total_minutes = Int()

class DowntimeEvent(ObjectType):
    """GraphQL type for a sensor downtime event."""
    sensor = String()
    start_time = String()
    end_time = String()
    duration_seconds = Int()


class SmartPlugReading(ObjectType):
    """GraphQL type for a single smart plug reading."""
    id = Int()
    voltage_v = Float()
    current_a = Float()
    power_w = Float()
    timestamp = String()
    timestamp_unix = Float()

class SmartPlugStats(ObjectType):
    """GraphQL type for live smart plug stats + 24h aggregates."""
    online = Boolean()
    polled_at = Float()
    current_watts = Float()
    current_volts = Float()
    current_amps = Float()
    avg_watts = Float()
    max_watts = Float()
    min_watts = Float()


class PowerOutage(ObjectType):
    """GraphQL type for a power outage near the monitored location."""
    id              = Int()
    outage_code     = String()
    source          = String()  # 'pdf' or 'api'
    cause_type      = String()
    locality        = String()
    county          = String()
    region          = String()
    start_time      = String()
    start_time_unix = Float()
    start_time_str  = String()
    end_time        = String()
    end_time_unix   = Float()
    expected_end    = String()
    details         = String()
    latitude        = Float()
    longitude       = Float()
    num_affected    = Int()
    first_seen      = String()
    last_seen       = String()
    is_active       = Boolean()
    resolved_at     = String()


class PowerOutagesSummary(ObjectType):
    """Aggregate view for the dashboard card."""
    target_locality       = String()
    target_county         = String()
    last_check            = String()
    last_pdf_check        = String()
    active_count          = Int()
    accidental_count      = Int()
    planned_count         = Int()
    upcoming_count        = Int()      # PDF-sourced scheduled events in the next 28 days
    next_upcoming_start   = String()   # ISO of next upcoming start time
    next_upcoming_locality = String()
    total_affected        = Int()


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
    bm280_status = Field(USBSensorStatus)
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
    pressure_trend = Field(PressureTrend)

    # Weather queries
    current_weather = Field(CurrentWeather)
    weather_history = GrapheneList(
        WeatherReading,
        year=Int(),
        month=Int(),
        day=Int(),
        limit=Int(default_value=1000)
    )

    # System health queries
    system_health_history = GrapheneList(
        SystemHeartbeat,
        hours_back=Int(default_value=24)
    )
    uptime_stats = Field(
        UptimeStats,
        hours_back=Int(default_value=24)
    )
    downtime_events = GrapheneList(
        DowntimeEvent,
        hours_back=Int(default_value=24)
    )

    # Smart plug queries
    current_smart_plug = Field(SmartPlugStats)
    smart_plug_history = GrapheneList(
        SmartPlugReading,
        range=String(default_value='day'),
        limit=Int(default_value=1000)
    )

    # Power outage queries (Clopotiva, Hunedoara)
    current_power_outages  = GrapheneList(PowerOutage)
    upcoming_power_outages = GrapheneList(PowerOutage, days_ahead=Int(default_value=28))
    power_outage_history   = GrapheneList(PowerOutage, limit=Int(default_value=50))
    power_outages_summary  = Field(PowerOutagesSummary)

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
        range=String(default_value="day"),
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

            # Get BM280 sensor status
            current_time = time.time()
            bm280_last_reading = None
            bm280_seconds_ago = None
            bm280_connected_str = "disconnected"

            if hasattr(app, 'usb_data_processor') and app.usb_data_processor:
                if app.usb_data_processor.last_bm280_reading:
                    bm280_last_reading = app.usb_data_processor.last_bm280_reading
                    bm280_seconds_ago = current_time - bm280_last_reading
                    # Consider online if reading within last 120 seconds
                    bm280_connected_str = "online" if bm280_seconds_ago < 120 else "stale"

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
                bm280_status=USBSensorStatus(
                    name="BM280 (Temp/Humidity/Pressure)",
                    connected=bm280_connected_str,
                    last_reading=bm280_last_reading,
                    seconds_since_last_reading=bm280_seconds_ago,
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
                bm280_status=None,
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
        """Resolves the query for historical temperature readings."""
        try:
            readings = []
            now = datetime.now(timezone.utc)

            if range == 'day':
                readings = db.get_daily_readings(days_back=1)
            elif range == 'week':
                readings = db.get_daily_readings(days_back=7)
            elif range == 'month':
                readings = db.get_readings_by_month(year=now.year, month=now.month)
            elif range == 'year':
                readings = db.get_readings_by_year(year=now.year)
            else:
                readings = db.get_recent_readings(limit=min(limit, 5000))

            readings = _thin(readings, limit)
            result = [
                TemperatureReading(
                    id=reading.id,
                    temperature_c=reading.temperature_c,
                    timestamp=_to_local_iso_unix(reading.timestamp)[0],
                    timestamp_unix=_to_local_iso_unix(reading.timestamp)[1],
                    sensor_type=reading.sensor_type,
                    sensor_id=reading.sensor_id
                ) for reading in readings
            ]
            result.sort(key=lambda x: x.timestamp_unix)
            return result
        except Exception as e:
            logger.error(f'Error getting temperature history: {e}')
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

        Prefers USB sensor (BME280) humidity, falls back to OpenWeatherMap.

        Args:
            info: The GraphQL resolve info object.

        Returns:
            A HumidityReading object or None if no readings are available.
        """
        try:
            # First, try to get humidity from USB sensor (BME280)
            usb_readings = db.get_recent_humidity_readings(limit=1, sensor_id='micropython_device')
            if usb_readings:
                reading = usb_readings[0]
                return HumidityReading(
                    id=reading.id,
                    humidity_percent=reading.humidity_percent,
                    timestamp=_to_local_iso_unix(reading.timestamp)[0],
                    timestamp_unix=_to_local_iso_unix(reading.timestamp)[1],
                    sensor_type=reading.sensor_type,
                    sensor_id=reading.sensor_id
                )

            return None
        except Exception as e:
            logger.error(f'Error getting current humidity: {e}')
            return None
            
    def resolve_humidity_history(self, info: Any, range: str = 'daily', limit: int = 1000, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> List[HumidityReading]:
        """Resolves the query for historical humidity readings from USB sensor (BME280).

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
            # Get USB sensor data only
            sensor_id = 'micropython_device'
            readings = []

            # Handle time-based queries
            if year is not None:
                if month is not None and day is not None:
                    readings = db.get_humidity_readings_by_day(year, month, day, sensor_id=sensor_id)
                elif month is not None:
                    readings = db.get_humidity_readings_by_month(year, month, sensor_id=sensor_id)
                else:
                    readings = db.get_humidity_readings_by_year(year, sensor_id=sensor_id)
            else:
                now = datetime.now(timezone.utc)
                if range in ('day', 'daily'):
                    readings = db.get_humidity_readings_by_day(now.year, now.month, now.day, sensor_id=sensor_id)
                elif range in ('week', 'weekly'):
                    cutoff_unix = time.time() - 7 * 86400
                    readings = db.get_recent_humidity_readings(limit=99999, sensor_id=sensor_id)
                    readings = [r for r in readings if r.timestamp_unix and r.timestamp_unix >= cutoff_unix]
                elif range == 'month':
                    readings = db.get_humidity_readings_by_month(now.year, now.month, sensor_id=sensor_id)
                elif range == 'year':
                    readings = db.get_humidity_readings_by_year(now.year, sensor_id=sensor_id)
                else:
                    readings = db.get_recent_humidity_readings(limit=limit, sensor_id=sensor_id)

            readings = _thin(readings, limit)
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

        Resolves humidity statistics from USB sensor (BME280).

        Args:
            info: The GraphQL resolve info object.
            hours: The number of hours to look back for statistics.

        Returns:
            A HumidityStatistics object.
        """
        try:
            # Get USB sensor statistics
            stats = db.get_humidity_statistics(sensor_id='micropython_device', hours_back=hours)

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

    def resolve_current_weather(self, info: Any) -> Optional[CurrentWeather]:
        """Resolves the current weather query by calculating from latest sensor readings.

        Args:
            info: The GraphQL resolve info object.

        Returns:
            A CurrentWeather object with calculated conditions, or None if any reading is missing.
        """
        try:
            temp_readings = db.get_recent_readings(limit=1)
            humidity_readings = db.get_recent_humidity_readings(limit=1, sensor_id='micropython_device')
            pressure_readings = db.get_recent_pressure_readings(limit=1)

            if not temp_readings or not humidity_readings or not pressure_readings:
                return None

            latest_temp = temp_readings[0]
            latest_humidity = humidity_readings[0]
            latest_pressure = pressure_readings[0]

            weather_data = calculate_local_weather(
                latest_temp.temperature_c,
                latest_humidity.humidity_percent,
                latest_pressure.pressure_hpa
            )

            db.add_weather_reading(
                condition=weather_data['condition'],
                description=weather_data['description'],
                sensor_type='BME280',
                sensor_id='micropython_device'
            )

            iso_time, unix_time = _to_local_iso_unix(datetime.now(timezone.utc))

            return CurrentWeather(
                condition=weather_data['condition'],
                description=weather_data['description'],
                temperature_c=latest_temp.temperature_c,
                humidity_percent=latest_humidity.humidity_percent,
                pressure_hpa=latest_pressure.pressure_hpa,
                sea_level_pressure_hpa=weather_data['sea_level_pressure_hpa'],
                dew_point_c=weather_data['dew_point_c'],
                timestamp=iso_time
            )
        except Exception as e:
            logger.error(f'Error calculating current weather: {e}')
            return None

    def resolve_weather_history(self, info: Any, limit: int = 1000, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> list:
        """Resolves the query for weather history.

        Args:
            info: The GraphQL resolve info object.
            limit: Maximum number of readings to return.
            year: Optional year filter.
            month: Optional month filter.
            day: Optional day filter.

        Returns:
            A list of WeatherReading objects.
        """
        try:
            readings = []
            now = datetime.now(timezone.utc)
            if year is not None:
                if month is not None and day is not None:
                    readings = db.get_weather_readings_by_day(year, month, day)
                elif month is not None:
                    readings = db.get_weather_readings_by_month(year, month)
                else:
                    readings = db.get_weather_readings_by_year(year)
            else:
                readings = db.get_recent_weather_readings(limit=min(limit, 5000))

            readings = _thin(readings, limit)
            return [WeatherReading(
                id=reading.id,
                condition=reading.condition,
                description=reading.description,
                timestamp=reading.timestamp.isoformat() if reading.timestamp else None,
                timestamp_unix=reading.timestamp_unix,
                sensor_type=reading.sensor_type,
                sensor_id=reading.sensor_id
            ) for reading in readings]
        except Exception as e:
            logger.error(f"Error getting weather history: {e}")
            return []

    def resolve_system_health_history(self, info: Any, hours_back: int = 24) -> list:
        """Returns per-minute heartbeats for the requested window."""
        try:
            beats = db.get_heartbeats_by_range(hours_back=hours_back)
            beats = _thin(beats, 1000)
            return [SystemHeartbeat(
                timestamp=b.timestamp.isoformat() if b.timestamp else None,
                timestamp_unix=b.timestamp_unix,
                bm280_up=bool(b.bm280_up),
                mq135_up=bool(b.mq135_up),
                esp32cam_up=bool(b.esp32cam_up),
            ) for b in beats]
        except Exception as e:
            logger.error(f"Error getting system health history: {e}")
            return []

    def resolve_uptime_stats(self, info: Any, hours_back: int = 24) -> UptimeStats:
        """Returns uptime percentages over the requested window."""
        try:
            stats = db.get_uptime_stats(hours_back=hours_back)
            return UptimeStats(
                hours_back=stats['hours_back'],
                bm280_uptime_percent=stats['bm280_uptime_percent'],
                mq135_uptime_percent=stats['mq135_uptime_percent'],
                esp32cam_uptime_percent=stats['esp32cam_uptime_percent'],
                total_uptime_percent=stats['total_uptime_percent'],
                total_minutes=stats['total_minutes'],
            )
        except Exception as e:
            logger.error(f"Error getting uptime stats: {e}")
            return UptimeStats(
                hours_back=hours_back, bm280_uptime_percent=0.0,
                mq135_uptime_percent=0.0, esp32cam_uptime_percent=0.0,
                total_uptime_percent=0.0, total_minutes=0
            )

    def resolve_downtime_events(self, info: Any, hours_back: int = 24) -> list:
        """Returns downtime events over the requested window."""
        try:
            events = db.get_downtime_events(hours_back=hours_back)
            return [DowntimeEvent(
                sensor=e['sensor'],
                start_time=e['start_time'],
                end_time=e['end_time'],
                duration_seconds=e['duration_seconds'],
            ) for e in events]
        except Exception as e:
            logger.error(f"Error getting downtime events: {e}")
            return []

    def resolve_current_smart_plug(self, info: Any) -> SmartPlugStats:
        try:
            readings = db.get_plug_readings_by_range(hours_back=24)
            watts_vals = [r.power_w for r in readings if r.power_w is not None]
            return SmartPlugStats(
                online=_smartplug_last.get('online', False),
                polled_at=_smartplug_last.get('polled_at', 0),
                current_watts=_smartplug_last.get('watts'),
                current_volts=_smartplug_last.get('volts'),
                current_amps=_smartplug_last.get('amps'),
                avg_watts=round(sum(watts_vals) / len(watts_vals), 1) if watts_vals else None,
                max_watts=max(watts_vals) if watts_vals else None,
                min_watts=min(watts_vals) if watts_vals else None,
            )
        except Exception as e:
            logger.error(f"Error getting smart plug stats: {e}")
            return SmartPlugStats(online=False)

    def resolve_smart_plug_history(self, info: Any, range: str = 'day', limit: int = 1000) -> List[SmartPlugReading]:
        try:
            hours_map = {'day': 24, 'week': 168, 'month': 720, 'year': 8760}
            readings = db.get_plug_readings_by_range(hours_back=hours_map.get(range, 24))
            readings = _thin(readings, limit)
            result = [
                SmartPlugReading(
                    id=r.id,
                    voltage_v=r.voltage_v,
                    current_a=r.current_a,
                    power_w=r.power_w,
                    timestamp=_to_local_iso_unix(r.timestamp)[0],
                    timestamp_unix=_to_local_iso_unix(r.timestamp)[1],
                ) for r in readings
            ]
            result.sort(key=lambda x: x.timestamp_unix)
            return result
        except Exception as e:
            logger.error(f"Error getting smart plug history: {e}")
            return []

    @staticmethod
    def _outage_to_gql(row) -> 'PowerOutage':
        # SQLite drops tzinfo on round-trip — re-attach UTC so isoformat() gives proper "+00:00"
        st = row.start_time
        et = row.end_time
        if st and st.tzinfo is None: st = st.replace(tzinfo=timezone.utc)
        if et and et.tzinfo is None: et = et.replace(tzinfo=timezone.utc)
        return PowerOutage(
            id=row.id,
            outage_code=row.outage_code,
            source='pdf' if (row.outage_code or '').startswith('PDF_') else 'api',
            cause_type=row.cause_type,
            locality=row.locality,
            county=row.county,
            region=row.region,
            start_time=st.isoformat() if st else None,
            start_time_unix=st.timestamp() if st else None,
            start_time_str=row.start_time_str,
            end_time=et.isoformat() if et else None,
            end_time_unix=et.timestamp() if et else None,
            expected_end=row.expected_end,
            details=row.details,
            latitude=row.latitude,
            longitude=row.longitude,
            num_affected=row.num_affected or 0,
            first_seen=row.first_seen.isoformat() if row.first_seen else None,
            last_seen=row.last_seen.isoformat() if row.last_seen else None,
            is_active=bool(row.is_active),
            resolved_at=row.resolved_at.isoformat() if row.resolved_at else None,
        )

    def resolve_current_power_outages(self, info: Any) -> list:
        try:
            rows = db.get_active_outages()
            return [Query._outage_to_gql(r) for r in rows]
        except Exception as e:
            logger.error(f"Error getting current power outages: {e}")
            return []

    def resolve_upcoming_power_outages(self, info: Any, days_ahead: int = 28) -> list:
        try:
            rows = db.get_upcoming_outages(days_ahead=days_ahead)
            return [Query._outage_to_gql(r) for r in rows]
        except Exception as e:
            logger.error(f"Error getting upcoming power outages: {e}")
            return []

    def resolve_power_outage_history(self, info: Any, limit: int = 50) -> list:
        try:
            rows = db.get_recent_outages(limit=limit)
            return [Query._outage_to_gql(r) for r in rows]
        except Exception as e:
            logger.error(f"Error getting power outage history: {e}")
            return []

    def resolve_power_outages_summary(self, info: Any) -> 'PowerOutagesSummary':
        try:
            active = db.get_active_outages()
            upcoming = db.get_upcoming_outages(days_ahead=28)
            acc  = sum(1 for r in active if (r.cause_type or '').lower().startswith('acc'))
            plan = sum(1 for r in active if (r.cause_type or '').lower().startswith('plan'))
            total_aff = sum((r.num_affected or 0) for r in active)
            nxt = upcoming[0] if upcoming else None
            return PowerOutagesSummary(
                target_locality=OUTAGE_TARGET_LOCALITY_SUBSTR,
                target_county=OUTAGE_TARGET_COUNTY,
                last_check=_outage_last_poll.isoformat() if _outage_last_poll else None,
                last_pdf_check=_outage_pdf_last_check.isoformat() if _outage_pdf_last_check else None,
                active_count=len(active),
                accidental_count=acc,
                planned_count=plan,
                upcoming_count=len(upcoming),
                next_upcoming_start=(nxt.start_time.isoformat() if nxt and nxt.start_time else None),
                next_upcoming_locality=(nxt.locality if nxt else None),
                total_affected=total_aff,
            )
        except Exception as e:
            logger.error(f"Error getting power outages summary: {e}")
            return PowerOutagesSummary(
                target_locality=OUTAGE_TARGET_LOCALITY_SUBSTR,
                target_county=OUTAGE_TARGET_COUNTY,
                active_count=0, accidental_count=0, planned_count=0,
                upcoming_count=0, total_affected=0,
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
            now = datetime.now(timezone.utc)
            if year is not None:
                if month is not None and day is not None:
                    readings = db.get_pressure_readings_by_day(year, month, day)
                elif month is not None:
                    readings = db.get_pressure_readings_by_month(year, month)
                else:
                    readings = db.get_pressure_readings_by_year(year)
            elif range == 'day':
                readings = db.get_pressure_readings_by_day(now.year, now.month, now.day)
            elif range == 'week':
                cutoff_unix = time.time() - 7 * 86400
                readings = db.get_pressure_readings_by_month(now.year, now.month)
                readings = [r for r in readings if r.timestamp_unix and r.timestamp_unix >= cutoff_unix]
            elif range == 'month':
                readings = db.get_pressure_readings_by_month(now.year, now.month)
            elif range == 'year':
                readings = db.get_pressure_readings_by_year(now.year)
            else:
                readings = db.get_recent_pressure_readings(limit=min(limit, 5000))

            readings = _thin(readings, limit)
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

    def resolve_pressure_trend(self, info: Any) -> PressureTrend:
        """Resolves the query for pressure trend and rain risk prediction.

        Calculates 1-hour pressure change and determines rain risk based on:
        - Absolute pressure (at 610m elevation, normal ~943 hPa)
        - Rate of change (hPa/hour)

        Returns:
            A PressureTrend object with rain risk assessment.
        """
        from datetime import datetime, timedelta

        try:
            readings = db.get_recent_pressure_readings(limit=1500)
            if not readings or len(readings) < 2:
                return PressureTrend(
                    pressure_now=None,
                    change_1h=0.0,
                    trend_direction="unknown",
                    rain_risk="UNKNOWN",
                    description="Insufficient data",
                    readings_used=len(readings) if readings else 0
                )

            # Most recent reading
            now_reading = readings[0]
            pressure_now = now_reading.pressure_hpa
            now_time = now_reading.timestamp_unix if now_reading.timestamp_unix else now_reading.timestamp.timestamp()

            # Find reading closest to 60 minutes ago
            target_time = now_time - 3600  # 60 minutes in seconds
            hour_ago_reading = None
            min_diff = float('inf')

            for reading in readings[1:]:
                reading_time = reading.timestamp_unix if reading.timestamp_unix else reading.timestamp.timestamp()
                time_diff = abs(reading_time - target_time)
                if time_diff < min_diff:
                    min_diff = time_diff
                    hour_ago_reading = reading

            if hour_ago_reading is None:
                return PressureTrend(
                    pressure_now=pressure_now,
                    change_1h=0.0,
                    trend_direction="stable",
                    rain_risk="LOW",
                    description="Less than 1 hour of data",
                    readings_used=len(readings)
                )

            pressure_1h_ago = hour_ago_reading.pressure_hpa
            change_1h = pressure_now - pressure_1h_ago

            # Determine trend direction
            if change_1h > 2:
                trend_direction = "rising"
            elif change_1h < -2:
                trend_direction = "falling"
            else:
                trend_direction = "stable"

            # Rain risk logic for 610m elevation (normal pressure ~943 hPa)
            if pressure_now < 930 or change_1h < -10:
                rain_risk = "HIGH"
                if pressure_now < 930:
                    description = f"Very low pressure ({pressure_now:.1f} hPa) - rain likely"
                else:
                    description = f"Pressure falling fast ({change_1h:.1f} hPa/h) - rain coming"
            elif -10 <= change_1h <= -3:
                rain_risk = "MEDIUM"
                description = f"Pressure falling ({change_1h:.1f} hPa/h) - possible rain"
            else:
                rain_risk = "LOW"
                if change_1h > 0:
                    description = f"Pressure rising ({change_1h:.1f} hPa/h) - clearing"
                else:
                    description = f"Pressure stable ({change_1h:.1f} hPa/h) - no change"

            return PressureTrend(
                pressure_now=pressure_now,
                change_1h=change_1h,
                trend_direction=trend_direction,
                rain_risk=rain_risk,
                description=description,
                readings_used=len(readings)
            )
        except Exception as e:
            logger.error(f"Error calculating pressure trend: {e}")
            return PressureTrend(
                pressure_now=None,
                change_1h=0.0,
                trend_direction="error",
                rain_risk="UNKNOWN",
                description=f"Error: {str(e)}",
                readings_used=0
            )

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
            now = datetime.now(timezone.utc)
            if year is not None:
                if month is not None and day is not None:
                    readings = db.get_air_quality_readings_by_day(year, month, day)
                elif month is not None:
                    readings = db.get_air_quality_readings_by_month(year, month)
                else:
                    readings = db.get_air_quality_readings_by_year(year)
            elif range == 'day':
                readings = db.get_air_quality_readings_by_day(now.year, now.month, now.day)
            elif range == 'week':
                cutoff_unix = time.time() - 7 * 86400
                readings = db.get_recent_air_quality_readings(limit=99999)
                readings = [r for r in readings if r.timestamp_unix and r.timestamp_unix >= cutoff_unix]
            elif range == 'month':
                readings = db.get_air_quality_readings_by_month(now.year, now.month)
            elif range == 'year':
                readings = db.get_air_quality_readings_by_year(now.year)
            else:
                readings = db.get_recent_air_quality_readings(limit=min(limit, 5000))

            readings = _thin(readings, limit)
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

    def resolve_meter_history(self, info: Any, range: str = "day", limit: int = 1000, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> List[MeterReading]:
        """Resolves the query for historical meter readings.

        Args:
            info: The GraphQL resolve info object.
            range: Time range filter ('day', 'week', 'month', 'year').
            limit: The maximum number of readings to return.
            year: The year to query for historical data.
            month: The month to query for historical data.
            day: The day to query for historical data.

        Returns:
            A list of MeterReading objects.
        """
        try:
            # Handle time-based queries
            now = datetime.now(timezone.utc)

            if range == 'day' or range == 'week':
                # For day and week, just get recent readings
                readings = db.get_recent_meter_readings(limit=min(limit, 5000))
            elif range == 'month':
                readings = db.get_meter_readings_by_month(year=now.year, month=now.month)
            elif range == 'year':
                readings = db.get_meter_readings_by_year(year=now.year)
            elif year is not None:
                if month is not None and day is not None:
                    readings = db.get_meter_readings_by_day(year, month, day)
                elif month is not None:
                    readings = db.get_meter_readings_by_month(year, month)
                else:
                    readings = db.get_meter_readings_by_year(year)
            else:
                readings = db.get_recent_meter_readings(limit=min(limit, 5000))

            readings = _thin(readings, limit)
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
        self.last_bm280_reading = None  # Track last BM280 (temp/humidity/pressure) reading time
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
            pressure_hpa = data.get('pressure_hpa')
            # Get humidity from USB sensor (BME280)
            humidity_pct = data.get('humidity_percent')
            air_data = data.get('air', {})
            
            # Update timestamps immediately when data is received (before throttling check)
            # This prevents false stale detection when data is throttled
            if temp_c is not None or pressure_hpa is not None:
                self.last_bm280_reading = current_time
            
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
                        'sensor_type': 'bm280_usb',
                        'sensor_id': 'micropython_device',
                        'change_reason': 'usb_update'
                    }
                }
                if has_sse_subscribers():
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
                        'sensor_type': 'bm280_usb',
                        'sensor_id': 'micropython_device'
                    }
                }
                if has_sse_subscribers():
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
                        'sensor_type': 'bm280_usb',
                        'sensor_id': 'micropython_device'
                    }
                }
                if has_sse_subscribers():
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
                if has_sse_subscribers():
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
                    sensor_type='bm280_usb',
                    sensor_id='micropython_device',
                    timestamp=timestamp
                )

            if humidity_pct is not None:
                db.add_humidity_reading(
                    humidity_percent=humidity_pct,
                    sensor_type='bm280_usb',
                    sensor_id='micropython_device',
                    timestamp=timestamp
                )

            if pressure_hpa is not None:
                db.add_pressure_reading(
                    pressure_hpa=pressure_hpa,
                    sensor_type='bm280_usb',
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
        global sse_subscribers
        registered = False
        try:
            with sse_subscribers_lock:
                sse_subscribers += 1
                registered = True

            # Send immediate connection confirmation with latest data
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': time.time()})}\n\n"

            # Immediately send latest temperature from database
            try:
                readings = db.get_recent_readings(limit=1)
                if readings:
                    r = readings[0]
                    temp_data = {
                        'temperature_c': r.temperature_c,
                        'timestamp_iso': r.timestamp.isoformat() if r.timestamp else None,
                        'sensor_type': r.sensor_type,
                        'sensor_id': r.sensor_id
                    }
                    sse_message = {
                        'type': 'temperature_update',
                        'data': temp_data,
                        'timestamp': temp_data['timestamp_iso']
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
                            bm280_connected = "disconnected"
                            mq135_connected = "disconnected"
                            bm280_seconds_ago = None
                            mq135_seconds_ago = None

                            if hasattr(app, 'usb_data_processor') and app.usb_data_processor:
                                if app.usb_data_processor.last_bm280_reading:
                                    bm280_seconds_ago = current_time - app.usb_data_processor.last_bm280_reading
                                    bm280_connected = "online" if bm280_seconds_ago < 120 else "stale"

                                if app.usb_data_processor.last_mq135_reading:
                                    mq135_seconds_ago = current_time - app.usb_data_processor.last_mq135_reading
                                    mq135_connected = "online" if mq135_seconds_ago < 120 else "stale"

                            esp32cam_status = "offline"
                            esp32cam_seconds_ago = None
                            if _esp32cam_last_status['checked_at']:
                                esp32cam_seconds_ago = current_time - _esp32cam_last_status['checked_at']
                                if esp32cam_seconds_ago > 180:
                                    esp32cam_status = "stale"
                                elif _esp32cam_last_status['up'] and _esp32cam_last_status['ready']:
                                    esp32cam_status = "online"
                                elif _esp32cam_last_status['up']:
                                    esp32cam_status = "not ready"
                                else:
                                    esp32cam_status = "offline"

                            smartplug_status = "offline"
                            if _smartplug_last['polled_at']:
                                sp_age = current_time - _smartplug_last['polled_at']
                                if sp_age > 30:
                                    smartplug_status = "stale"
                                else:
                                    smartplug_status = "online"

                            sensor_status_message = {
                                'type': 'sensor_status',
                                'timestamp': current_time,
                                'data': {
                                    'usb_connected': usb_status['connected'],
                                    'usb_error': str(usb_status['last_error']) if usb_status['last_error'] else None,
                                    'bm280': {
                                        'status': bm280_connected,
                                        'seconds_since_reading': bm280_seconds_ago
                                    },
                                    'mq135': {
                                        'status': mq135_connected,
                                        'seconds_since_reading': mq135_seconds_ago
                                    },
                                    'esp32cam': {
                                        'status': esp32cam_status,
                                        'seconds_since_reading': esp32cam_seconds_ago,
                                        'uptime_ms': _esp32cam_last_status.get('uptime_ms')
                                    },
                                    'smartplug': {
                                        'status': smartplug_status,
                                        'watts': _smartplug_last.get('watts'),
                                        'volts': _smartplug_last.get('volts'),
                                        'amps': _smartplug_last.get('amps'),
                                        'polled_at': _smartplug_last.get('polled_at') or None,
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
        finally:
            if registered:
                with sse_subscribers_lock:
                    sse_subscribers = max(0, sse_subscribers - 1)

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

        # Initialize scheduler for daily OCR task at 12:00 (noon) and ESP32-CAM reset at midnight
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            scheduled_ocr_task,
            'cron',
            hour=12,
            minute=0,
            id='daily_ocr_task',
            name='Daily OCR Meter Reading at 12:00 (noon)'
        )
        scheduler.add_job(
            scheduled_heartbeat_task,
            'interval',
            seconds=20,
            id='system_heartbeat',
            name='System Heartbeat (every minute)'
        )
        scheduler.add_job(
            scheduled_smartplug_task,
            'interval',
            seconds=5,
            id='smartplug_poll',
            name='Smart Plug poll (every 5s)'
        )
        scheduler.add_job(
            scheduled_outage_check_task,
            'interval',
            hours=1,
            id='outage_check',
            name='Clopotiva outage check (hourly)'
        )
        scheduler.add_job(
            scheduled_pdf_outage_check_task,
            'cron',
            hour=5, minute=30,
            id='outage_pdf_check',
            name='Clopotiva scheduled outage PDF scan (daily 05:30)'
        )
        scheduler.start()
        logger.info("Scheduler started - OCR 12:00, ESP32-CAM 00:00, heartbeat 60s, outage API hourly, outage PDF 05:30 daily")

        # Pre-populate _smartplug_last from DB so page refresh shows data immediately,
        # even before the first live poll completes.
        try:
            recent = db.get_recent_plug_readings(limit=1)
            if recent:
                r = recent[0]
                _smartplug_last.update({
                    'volts': r.voltage_v,
                    'amps': r.current_a,
                    'watts': r.power_w,
                    'polled_at': r.timestamp_unix,
                    'online': True,
                })
                logger.info(f"Smart plug pre-seeded from DB: {r.power_w}W @ {r.voltage_v}V")
        except Exception as e:
            logger.warning(f"Could not pre-seed smart plug from DB: {e}")

        # Pre-check ESP32-CAM so it shows online immediately rather than waiting 60s for heartbeat.
        try:
            cfg = load_app_config()
            esp32_base = cfg.get('webcam', {}).get('url', '').replace('/snapshot', '').replace('/capture', '')
            if esp32_base:
                r = requests.get(f"{esp32_base}/status", timeout=3)
                if r.status_code == 200:
                    _esp32cam_last_status['up'] = True
                    _esp32cam_last_status['ready'] = True
                    _esp32cam_last_status['checked_at'] = time.time()
                    try:
                        body = r.json()
                        cam = body.get('camera') if isinstance(body, dict) else None
                        _esp32cam_last_status['ready'] = bool(cam.get('ready')) if isinstance(cam, dict) else True
                        _esp32cam_last_status['uptime_ms'] = body.get('uptime_ms')
                    except Exception:
                        pass
        except Exception:
            pass

        # Run immediate polls so the card has fresh data at startup.
        try:
            threading.Thread(target=scheduled_outage_check_task, daemon=True, name='OutageInitialPoll').start()
            threading.Thread(target=scheduled_pdf_outage_check_task, daemon=True, name='OutagePdfInitialScan').start()
            threading.Thread(target=scheduled_smartplug_task, daemon=True, name='SmartPlugInitialPoll').start()
        except Exception as e:
            logger.warning(f"Could not start initial poll threads: {e}")

        logger.info("Application initialized with USB sensor data")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        return False


def has_sse_subscribers() -> bool:
    """Returns True when at least one SSE client is connected."""
    with sse_subscribers_lock:
        return sse_subscribers > 0


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
        
        # Prepare the camera payload defaults.
        payload = {
            "resolution": "UXGA (1600x1200)",
            "quality": 10,
            "flash": False,
            "brightness": 0,
            "contrast": 0,
            "saturation": 0,
            "exposure": 300,
            "gain": 0,
            "special_effect": 0,
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
    """Captures a fresh image and runs OCR on it using Google Cloud Vision API.

    This endpoint is used by the scheduled daily task and can also be called
    programmatically. It handles image capture, calls Google Cloud Vision API,
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
        logger.info("Starting OCR process...")
        # Capture a fresh image
        with app.test_client() as client:
            logger.info("Capturing fresh image for OCR...")
            cap_resp = client.post('/webcam/capture')
            cap_json = cap_resp.get_json()
        if not cap_json.get('success'):
            logger.error(f"Failed to capture image for OCR: {cap_json.get('error')}")
            return jsonify({
                "success": False,
                "error": "Failed to capture image for OCR"
            }), 500

        # Decode base64
        image_b64 = cap_json['image']
        prefix = 'data:image/jpeg;base64,'
        if image_b64.startswith(prefix):
            image_b64 = image_b64[len(prefix):]

        # Use Google Gemini API with configurable model selection.
        try:
            api_key = os.environ.get('GOOGLE_API_KEY')
            ocr_engines = app_config.get('ocr', {}).get('engines', {})
            configured_model = (
                ocr_engines.get('google', {}).get('model')
                or ocr_engines.get('requesty', {}).get('model')
                or 'gemini-2.5-flash-lite'
            )
            gemini_model = (
                configured_model.split('/', 1)[1]
                if isinstance(configured_model, str) and configured_model.startswith('google/')
                else configured_model
            )
            if not gemini_model:
                gemini_model = 'gemini-2.5-flash-lite'
            engine_name = f"Google Gemini API ({gemini_model})"

            logger.info(f"Using OCR engine: {engine_name}")
            if not api_key:
                raise Exception("Google API key not configured. Set GOOGLE_API_KEY environment variable or add to .env file.")

            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    "You are reading a mechanical electricity meter. "
                                    "The image shows a dark horizontal band with exactly 4 white digits on rotating wheels.\n\n"
                                    "The photo may be slightly blurry — that is expected and acceptable. "
                                    "Read the digits as a human would: look at the overall shape of each number, not pixel-perfect sharpness.\n\n"
                                    "RULES:\n"
                                    "1. Focus on the dark display band — the 4 white/light digits are your target.\n"
                                    "2. Read left to right. Each wheel shows one digit 0–9.\n"
                                    "3. If a wheel is mid-rotation (halfway between two digits), read the lower digit.\n"
                                    "4. If you can identify all 4 digits with reasonable confidence, respond with ONLY those 4 digits — nothing else. Example: 9772\n"
                                    "5. Only respond with UNREADABLE if a digit is completely impossible to determine "
                                    "(e.g. fully obscured, pitch black, or totally smeared beyond recognition).\n\n"
                                    "Do NOT hallucinate. Do NOT guess randomly. But DO read what a human could read from this image."
                                )
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

            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
            logger.info(f"Sending request to Google Gemini API model: {gemini_model}")
            ocr_response = requests.post(
                gemini_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30
            )
            ocr_response.raise_for_status()

            result = ocr_response.json()

            # Check for errors in response
            if 'error' in result:
                error_msg = result['error'].get('message', 'Unknown error')
                logger.error(f"Gemini API error: {error_msg}")
                return jsonify({
                    "success": False,
                    "engine": engine_name,
                    "image": cap_json['image'],
                    "timestamp": datetime.now().isoformat() + "Z",
                    "error": f"Gemini API error: {error_msg}"
                }), 500

            # Extract text from response
            ocr_text = ""
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    for part in candidate['content']['parts']:
                        if 'text' in part:
                            ocr_text = part['text'].strip()
                            break

            logger.info(f"Raw OCR output: {ocr_text}")

            if not ocr_text:
                logger.warning("No text detected in image")
                return jsonify({
                    "success": False,
                    "engine": engine_name,
                    "image": cap_json['image'],
                    "timestamp": datetime.now().isoformat() + "Z",
                    "raw_ocr": ocr_text,
                    "error": "No text detected in image"
                })

            # Extract numbers from response
            numbers = re.findall(r'\d+', ocr_text)

            # Find exactly 4-digit number (meter reading)
            four_digit = None
            for num in numbers:
                if len(num) == 4:
                    four_digit = num
                    break

            if four_digit:
                meter_value_with_prefix = "2" + four_digit

                # Validation 1: Check minimum threshold (must be >= 20000)
                try:
                    meter_int = int(meter_value_with_prefix)
                    if meter_int < 20000:
                        logger.warning(f"❌ Reading {meter_value_with_prefix} below minimum threshold 20000")
                        return jsonify({
                            "success": False,
                            "error": f"Reading {meter_value_with_prefix} is below minimum threshold 20000",
                            "engine": engine_name,
                            "image": cap_json['image'],
                            "timestamp": datetime.now().isoformat() + "Z",
                            "raw_ocr": ocr_text
                        })
                except ValueError:
                    logger.error(f"Failed to parse meter value: {meter_value_with_prefix}")
                    return jsonify({
                        "success": False,
                        "error": f"Invalid meter value format: {meter_value_with_prefix}",
                        "engine": engine_name,
                        "image": cap_json['image'],
                        "timestamp": datetime.now().isoformat() + "Z",
                        "raw_ocr": ocr_text
                    })

                # Validation 2: Check against previous reading (max 100 unit difference)
                try:
                    previous_readings = db.session.query(db.models.MeterReading).order_by(db.models.MeterReading.id.desc()).limit(1).all()
                    if previous_readings:
                        prev_reading = previous_readings[0].meter_value
                        try:
                            prev_int = int(prev_reading)
                            diff = meter_int - prev_int
                            if diff < 0:
                                logger.warning(f"❌ Reading went backwards: {prev_int} → {meter_int}")
                                return jsonify({
                                    "success": False,
                                    "error": f"Invalid: meter decreased from {prev_int} to {meter_int}",
                                    "engine": engine_name,
                                    "image": cap_json['image'],
                                    "timestamp": datetime.now().isoformat() + "Z",
                                    "raw_ocr": ocr_text
                                })
                            elif diff > 100:
                                logger.warning(f"❌ Reading jumped too much: {prev_int} → {meter_int} (diff: {diff})")
                                return jsonify({
                                    "success": False,
                                    "error": f"Invalid: meter jumped {diff} units (max 100 allowed). Previous: {prev_int}, Current: {meter_int}",
                                    "engine": engine_name,
                                    "image": cap_json['image'],
                                    "timestamp": datetime.now().isoformat() + "Z",
                                    "raw_ocr": ocr_text
                                })
                            logger.info(f"✅ Validation passed: {prev_int} → {meter_int} (diff: {diff})")
                        except ValueError:
                            logger.warning(f"Could not parse previous reading: {prev_reading}")
                except Exception as validation_err:
                    logger.error(f"Validation check error: {validation_err}")

                try:
                    db.add_meter_reading(
                        meter_value=meter_value_with_prefix,
                        ocr_engine=engine_name,
                        raw_ocr_text=ocr_text,
                        sensor_type="esp32cam_ocr",
                        sensor_id="cabana1_meter"
                    )
                    logger.info(f"✅ Saved meter reading to database: {meter_value_with_prefix}")

                    return jsonify({
                        "success": True,
                        "index": meter_value_with_prefix,
                        "engine": engine_name,
                        "image": cap_json['image'],
                        "timestamp": datetime.now().isoformat() + "Z",
                        "raw_ocr": ocr_text
                    })
                except Exception as db_err:
                    logger.error(f"Failed to save meter reading to database: {db_err}")
                    return jsonify({
                        "success": False,
                        "error": f"OCR succeeded but database save failed: {str(db_err)}",
                        "engine": engine_name,
                        "image": cap_json['image'],
                        "timestamp": datetime.now().isoformat() + "Z",
                        "raw_ocr": ocr_text
                    }), 500
            else:
                logger.warning(f"No 4-digit number found. Numbers detected: {numbers}")
                return jsonify({
                    "success": False,
                    "engine": engine_name,
                    "image": cap_json['image'],
                    "timestamp": datetime.now().isoformat() + "Z",
                    "raw_ocr": ocr_text,
                    "error": "No 4-digit number found in response"
                })

        except Exception as ocr_error:
            logger.error(f"Google Gemini API OCR error: {ocr_error}")
            return jsonify({
                "success": False,
                "error": f"OCR failed: {str(ocr_error)}",
                "engine": f"{engine_name} - Error",
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
    parser.add_argument('--throttle', type=int, default=60, help='Throttle interval for all operations - SSE, DB storage, USB reading (default: 60 seconds = 1 minute)')
    
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
