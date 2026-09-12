"""Time, measured system load and opt-in location weather; no generated forecasts."""
from __future__ import annotations

import json
import math
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen


def _get_json(base, params):
    with urlopen(base + '?' + urlencode(params), timeout=8) as response:
        data = response.read(256001)
    if len(data) > 256000:
        raise ValueError('Weather response too large.')
    return json.loads(data)


def valid_location(location):
    if not isinstance(location, dict) or not isinstance(location.get('name'), str) or not location['name'].strip():
        return False
    try:
        return (-90 <= float(location['latitude']) <= 90 and
                -180 <= float(location['longitude']) <= 180)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def find_locations(city):
    city = city.strip()
    if not 2 <= len(city) <= 100:
        raise ValueError('Enter a city name between 2 and 100 characters.')
    response = _get_json('https://geocoding-api.open-meteo.com/v1/search',
                     {'name': city, 'count': 5, 'language': 'en', 'format': 'json'})
    rows = response.get('results') if isinstance(response, dict) else None
    return [row for row in rows if valid_location(row)][:5] if isinstance(rows, list) else []


def weather_report(location):
    if not location:
        return 'Weather ke liye Background Settings mein apna shehar select kijiye.'
    if not valid_location(location):
        raise ValueError('Invalid weather location.')
    lat, lon = float(location['latitude']), float(location['longitude'])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid weather coordinates.')
    data = _get_json('https://api.open-meteo.com/v1/forecast', {
        'latitude': lat, 'longitude': lon, 'current': 'temperature_2m',
        'daily': 'precipitation_probability_max', 'timezone': 'auto', 'forecast_days': 1,
    })
    current = data.get('current') or {}
    daily = data.get('daily') or {}
    temp = current.get('temperature_2m') if isinstance(current, dict) else None
    probabilities = daily.get('precipitation_probability_max') if isinstance(daily, dict) else None
    chance = probabilities[0] if isinstance(probabilities, list) and probabilities else None
    parts = [f"{location['name']} ka Open-Meteo forecast."]
    if isinstance(temp, (int, float)) and math.isfinite(temp):
        parts.append(f'Abhi temperature {temp:g} degree Celsius hai.')
    else:
        parts.append('Temperature abhi available nahi hai.')
    if isinstance(chance, (int, float)) and 0 <= chance <= 100:
        parts.append(f'Aaj barish ya anya precipitation ka maximum chance {chance:g} percent hai. Yeh forecast hai, guarantee nahi.')
    else:
        parts.append('Aaj barish ka chance abhi available nahi hai.')
    return ' '.join(parts)


def build_briefing(location=None, now=None):
    import psutil
    now = now or datetime.now().astimezone()
    period = 'morning' if 5 <= now.hour < 12 else 'afternoon' if 12 <= now.hour < 17 else 'evening'
    parts = [f'Yes boss, good {period}!']
    try:
        parts.append(weather_report(location))
    except Exception:
        parts.append('Weather service abhi available nahi hai. Barish ka forecast confirm nahi kar sakti.')
    try:
        cpu = psutil.cpu_percent(interval=0.25)
        ram = psutil.virtual_memory().percent
        parts.append(f'Aapke system ka CPU {cpu:g} percent aur RAM {ram:g} percent use ho raha hai.')
        battery = psutil.sensors_battery()
        if battery:
            parts.append(f'Battery {battery.percent:g} percent hai' + (', charging par hai.' if battery.power_plugged else '.'))
    except Exception:
        parts.append('System metrics abhi available nahi hain.')
    return ' '.join(parts)
