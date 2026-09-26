"""Time, measured system load and opt-in location weather; no generated forecasts."""
from __future__ import annotations

import json
import os
import threading
import time

_WEATHER_CACHE = {}
_WEATHER_LOCK = threading.Lock()
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen


def _get_json(base, params):
    params = dict(params)
    key = os.getenv('OPEN_METEO_API_KEY', '').strip()
    if key:
        base = base.replace('https://api.open-meteo.com', 'https://customer-api.open-meteo.com').replace('https://air-quality-api.open-meteo.com', 'https://customer-air-quality-api.open-meteo.com').replace('https://geocoding-api.open-meteo.com', 'https://customer-geocoding-api.open-meteo.com')
        params['apikey'] = key
    elif os.getenv('JARVIS_COMMERCIAL_WEATHER', '').lower() == 'true':
        raise RuntimeError('Commercial weather API key is not configured.')
    with urlopen(base + '?' + urlencode(params), timeout=4) as response:
        data = response.read(256001)
    if len(data) > 256000:
        raise ValueError('Weather response too large.')
    return json.loads(data)


def valid_location(location):
    if not isinstance(location, dict) or not isinstance(location.get('name'), str) or not location['name'].strip():
        return False
    try:
        if isinstance(location['latitude'], bool) or isinstance(location['longitude'], bool):
            return False
        return (-90 <= float(location['latitude']) <= 90 and
                -180 <= float(location['longitude']) <= 180)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def uses_commercial_proxy():
    return os.getenv('JARVIS_COMMERCIAL_WEATHER', '').lower() == 'true' and not os.getenv('OPEN_METEO_API_KEY', '').strip()


def proxy_report(location, mode):
    from .subscription_client import active_client
    endpoint = '/pro/forecast' if mode == 'week' else '/weather/report'
    return active_client().request('POST', endpoint, dict(location or {}, mode=mode))['report']


def find_locations(city):
    city = city.strip()
    if not 2 <= len(city) <= 100:
        raise ValueError('Enter a city name between 2 and 100 characters.')
    if uses_commercial_proxy():
        from .subscription_client import active_client
        return active_client().request('POST', '/weather/cities', {'city': city})['results']
    response = _get_json('https://geocoding-api.open-meteo.com/v1/search',
                     {'name': city, 'count': 5, 'language': 'en', 'format': 'json'})
    rows = response.get('results') if isinstance(response, dict) else None
    return [row for row in rows if valid_location(row)][:5] if isinstance(rows, list) else []


def weather_report(location, mode="today"):
    if mode not in {"today", "tomorrow", "week"}:
        raise ValueError("Unknown forecast period.")
    if not location:
        return 'Weather ke liye Background Settings mein apna shehar select kijiye.'
    if not valid_location(location):
        raise ValueError('Invalid weather location.')
    if uses_commercial_proxy():
        return proxy_report(location, mode)
    lat, lon = float(location['latitude']), float(location['longitude'])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid weather coordinates.')
    cache_key = (lat, lon, location['name'], datetime.now().date(), mode, bool(os.getenv('OPEN_METEO_API_KEY')))
    with _WEATHER_LOCK:
        cached = _WEATHER_CACHE.get(cache_key)
        if cached and time.monotonic() - cached[0] < 300:
            return cached[1] + ' (Pichhle 5 minute ka cached forecast.)'
    try:
        data = _get_json('https://api.open-meteo.com/v1/forecast', {
            'latitude': lat, 'longitude': lon, 'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,cloud_cover',
            'daily': 'precipitation_probability_max,temperature_2m_min,temperature_2m_max,weather_code,sunrise,sunset,wind_gusts_10m_max', 'timezone': 'auto', 'forecast_days': 7 if mode == 'week' else 2,
            'temperature_unit': 'celsius', 'wind_speed_unit': 'kmh',
        })
        if not isinstance(data, dict) or data.get('error'):
            raise ValueError('Weather service returned an invalid forecast.')
    except Exception:
        if cached and time.monotonic() - cached[0] < 1800:
            return 'Live weather unavailable. Pichhle 30 minute ka purana forecast: ' + cached[1]
        raise
    from .weather_details import forecast_text
    report = forecast_text(data, location['name'], mode)
    with _WEATHER_LOCK:
        if len(_WEATHER_CACHE) > 20:
            _WEATHER_CACHE.clear()
        _WEATHER_CACHE[cache_key] = (time.monotonic(), report)
    return report



def air_report(location):
    if not valid_location(location):
        return 'AQI ke liye Background Settings mein apna shehar select kijiye.'
    if uses_commercial_proxy():
        return proxy_report(location, 'air')
    key = ('air', float(location['latitude']), float(location['longitude']), bool(os.getenv('OPEN_METEO_API_KEY')))
    with _WEATHER_LOCK:
        cached = _WEATHER_CACHE.get(key)
    if cached and time.monotonic() - cached[0] < 300:
        return cached[1] + ' (Pichhle 5 minute ka cached air estimate.)'
    try:
        data = _get_json('https://air-quality-api.open-meteo.com/v1/air-quality', {
            'latitude': location['latitude'], 'longitude': location['longitude'],
            'current': 'us_aqi,pm2_5', 'timezone': 'auto', 'forecast_days': 1,
        })
        if not isinstance(data, dict) or data.get('error'):
            raise ValueError('Invalid air quality response.')
        from .weather_details import air_text
        report = air_text(data)
        with _WEATHER_LOCK:
            if len(_WEATHER_CACHE) > 20:
                _WEATHER_CACHE.clear()
            _WEATHER_CACHE[key] = (time.monotonic(), report)
        return report
    except Exception:
        return 'Live AQI abhi available nahi hai.'


def rich_weather_report(location):
    if uses_commercial_proxy():
        return proxy_report(location, 'today')
    # Independent bounded requests: a failed AQI feed must not discard weather.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='weather') as pool:
        weather = pool.submit(weather_report, location)
        air = pool.submit(air_report, location)
        try:
            report = weather.result()
        except Exception:
            report = 'Live weather abhi available nahi hai.'
        return report + ' ' + air.result()


def wake_greeting(name):
    name = ' '.join(str(name or '').split())[:60]
    return f'Hello {name}, kaise hain? Main sun rahi hoon.' if name else 'Hello, main sun rahi hoon.'

def build_briefing(location=None, now=None):
    import psutil
    now = now or datetime.now().astimezone()
    period = 'morning' if 5 <= now.hour < 12 else 'afternoon' if 12 <= now.hour < 17 else 'evening'
    parts = [f'Yes boss, good {period}!']
    try:
        parts.append(weather_report(location))
    except Exception:
        parts.append('Weather service abhi available nahi hai. Barish ka forecast confirm nahi kar sakti.')
    parts.append(system_report())
    return ' '.join(parts)


def system_report():
    import psutil
    parts = []
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        parts.append(f'Aapke system ka CPU {cpu:g} percent aur RAM {ram:g} percent use ho raha hai.')
        battery = psutil.sensors_battery()
        if battery:
            parts.append(f'Battery {battery.percent:g} percent hai' + (', charging par hai.' if battery.power_plugged else '.'))
    except Exception:
        parts.append('System metrics abhi available nahi hain.')
    return ' '.join(parts)
