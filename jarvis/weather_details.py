"""Grounded Open-Meteo reports. Missing observations are never converted to zero."""
from __future__ import annotations

import math
from datetime import datetime


def number(value, minimum=-1e6, maximum=1e6):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


def condition(code):
    if not number(code, 0, 99):
        return ''
    if code == 0:
        return 'aasman saaf hai'
    if code in (1, 2, 3):
        return 'aasman mein badal hain'
    if code in (45, 48):
        return 'kohra hai'
    if code in (51, 53, 55, 56, 57):
        return 'boonda-bandi hai'
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return 'barish ho rahi hai'
    if code in (71, 73, 75, 77, 85, 86):
        return 'baraf gir rahi hai'
    if code in (95, 96, 99):
        return 'garaj ke saath aandhi-barish hai'
    return ''


def daily_value(daily, key, index=0):
    values = daily.get(key) if isinstance(daily, dict) else None
    return values[index] if isinstance(values, list) and len(values) > index else None


def clock(value):
    try:
        return datetime.fromisoformat(value).strftime('%H:%M')
    except (ValueError, TypeError):
        return None


def forecast_text(data, name, mode='today'):
    current = data.get('current') if isinstance(data.get('current'), dict) else {}
    daily = data.get('daily') if isinstance(data.get('daily'), dict) else {}
    parts = [f'{name} ka Open-Meteo forecast.']
    if mode == 'today':
        temp = current.get('temperature_2m')
        parts.append(f'Abhi temperature {temp:g} degree Celsius hai.' if number(temp, -100, 70) else 'Temperature abhi available nahi hai.')
        apparent = current.get('apparent_temperature')
        if number(apparent, -100, 90):
            parts.append(f'Mehsoos {apparent:g} degree jaisa ho raha hai.')
        sky = condition(current.get('weather_code'))
        if sky:
            parts.append('Abhi ' + sky + '.')
        cloud = current.get('cloud_cover')
        if number(cloud, 0, 100):
            parts.append(f'Cloud cover {cloud:g} percent hai.')
        for key, label, unit, high in (
            ('relative_humidity_2m', 'Humidity', 'percent', 100),
            ('wind_speed_10m', 'Hawa ki speed', 'kilometre per hour', 500),
        ):
            value = current.get(key)
            if number(value, 0, high):
                parts.append(f'{label} {value:g} {unit} hai.')
        observed = current.get('time')
        if clock(observed):
            parts.append(f'Weather model ka samay {observed.replace("T", " ")}, shehar ke local time mein.')
    indices = range(7) if mode == 'week' else (1,) if mode == 'tomorrow' else (0,)
    for index in indices:
        day = daily_value(daily, 'time', index)
        if mode == 'week' and not day:
            continue
        label = str(day) if mode == 'week' else 'Kal' if index else 'Aaj'
        chance = daily_value(daily, 'precipitation_probability_max', index)
        if number(chance, 0, 100):
            parts.append(f'{label} barish ya anya precipitation ka maximum chance {chance:g} percent hai. Yeh forecast hai, guarantee nahi.')
            if chance >= 60 and mode != 'week':
                parts.append('Bahar jaate waqt chhata rakh lijiye.')
        else:
            parts.append(f'{label} barish ka chance abhi available nahi hai.')
        low, high = (daily_value(daily, k, index) for k in ('temperature_2m_min', 'temperature_2m_max'))
        if number(low, -100, 70) and number(high, -100, 70):
            parts.append(f'{label} temperature {low:g} se {high:g} degree Celsius rahega.')
        if mode != 'week':
            for key, title in (('sunrise', 'Suraj nikalne'), ('sunset', 'Suraj dhalne')):
                value = clock(daily_value(daily, key, index))
                if value:
                    parts.append(f'{title} ka local samay {value} hai.')
            code = daily_value(daily, 'weather_code', index)
            if code in (95, 96, 99):
                parts.append('Thunderstorm forecast hai; local weather alerts check kijiye.')
            gust = daily_value(daily, 'wind_gusts_10m_max', index)
            if number(gust, 50, 500):
                parts.append(f'Tez hawa ke jhonke {gust:g} kilometre per hour tak forecast hain.')
    return ' '.join(parts)


def air_text(data):
    current = data.get('current') if isinstance(data, dict) else None
    current = current if isinstance(current, dict) else {}
    aqi, pm = current.get('us_aqi'), current.get('pm2_5')
    parts = ['Open-Meteo / CAMS ka air-quality model estimate.']
    if number(aqi, 0, 1000):
        label = next((text for limit, text in ((50, 'good'), (100, 'moderate'), (150, 'unhealthy for sensitive groups'), (200, 'unhealthy'), (300, 'very unhealthy'), (1000, 'hazardous')) if aqi <= limit))
        parts.append(f'Pollution US AQI {aqi:g}, {label}. Yeh Indian AQI scale nahi hai.')
    else:
        parts.append('AQI abhi available nahi hai.')
    if number(pm, 0, 10000):
        parts.append(f'PM2.5 {pm:g} microgram per cubic metre hai.')
    if clock(current.get('time')):
        parts.append('Air model ka local samay ' + current['time'].replace('T', ' ') + '.')
    return ' '.join(parts)
