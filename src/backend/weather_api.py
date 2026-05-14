import urllib.request
import json
import threading
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

def fetch_stuttgart_weather(callback):
    """Fetches weather on a background thread and returns data via callback."""
    def _fetch():
        try:
            # Open-Meteo API (No auth required)
            url = "https://api.open-meteo.com/v1/forecast?latitude=48.742844833881485&longitude=9.101519425845058&current_weather=true&hourly=temperature_2m,precipitation_probability,weathercode&daily=sunrise,sunset&timezone=Europe%2FBerlin&forecast_days=1"
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                current = data.get("current_weather", {})
                hourly = data.get("hourly", {})
                
                temp = current.get("temperature", 0)
                code = current.get("weathercode", 0)
                # Determine day/night using sunrise/sunset if available
                is_day_raw = current.get("is_day", None)
                is_day = True
                try:
                    daily = data.get('daily', {})
                    sunrise_list = daily.get('sunrise', [])
                    sunset_list = daily.get('sunset', [])
                    if sunrise_list and sunset_list and ZoneInfo is not None:
                        sunrise = datetime.fromisoformat(sunrise_list[0])
                        sunset = datetime.fromisoformat(sunset_list[0])
                        now = datetime.now(ZoneInfo('Europe/Berlin'))
                        is_day = sunrise <= now <= sunset
                    else:
                        is_day = bool(is_day_raw if is_day_raw is not None else 1)
                except Exception:
                    is_day = bool(is_day_raw if is_day_raw is not None else 1)
                
                # Get max rain chance for the day
                precip_probs = hourly.get("precipitation_probability", [0])
                rain_chance = max(precip_probs) if precip_probs else 0
                
                # Extract 4 column points (e.g., 9:00, 13:00, 17:00, 21:00)
                # indices 9, 13, 17, 21
                forecast_columns = []
                for idx in [9, 13, 17, 21]:
                    if idx < len(hourly.get("temperature_2m", [])):
                        forecast_columns.append({
                            "hour": f"{idx}:00",
                            "temp": hourly["temperature_2m"][idx],
                            "precip": hourly["precipitation_probability"][idx],
                            "code": hourly["weathercode"][idx]
                        })
                
                # WMO Weather interpretation codes: 50+ generally means drizzle/rain/snow
                needs_umbrella = code >= 50 or rain_chance > 40
                is_sunny = code <= 3 
                
                callback({
                    "temp": temp,
                    "rain_chance": rain_chance,
                    "forecast_columns": forecast_columns,
                    "needs_umbrella": needs_umbrella,
                    "is_sunny": is_sunny,
                    "is_day": bool(is_day),
                    "error": None
                })
        except Exception as e:
            callback({"error": str(e)})
            
    threading.Thread(target=_fetch, daemon=True).start()
