"""
world_weather.py — the sky above the desk, for the worlds to feel.

A shared, background-refreshed weather condition service. States poll
`conditions()` (never blocks, never raises) and react: the neon city
rains when Stuttgart rains, the zeppelin stays grounded in a gale, the
conservatory glass streaks with water.

Returns a dict:
  rain      0.0-1.0 intensity (from WMO weather code + precipitation)
  wind      km/h
  storm     bool (thunder codes)
  is_day    bool
Disable with KEA_FEEDS=0 (same switch as the protocol feeds).
"""

import json
import os
import threading
import time
import urllib.request

LAT, LON = 48.7428, 9.1015
ENABLED = os.getenv("KEA_FEEDS", "1").strip().lower() not in {"0", "false", "off"}
REFRESH = 900  # 15 min

_lock = threading.Lock()
_value = {"rain": 0.0, "wind": 0.0, "storm": False, "is_day": True}
_stamp = 0.0
_busy = False


def _rain_from_code(code):
    """WMO weather code -> rough 0..1 intensity."""
    if code in (95, 96, 99):
        return 0.9
    if code in (65, 67, 82):
        return 0.8
    if code in (63, 66, 81):
        return 0.5
    if code in (51, 53, 55, 61, 80):
        return 0.3
    if code in (71, 73, 75, 77, 85, 86):   # snow reads as gentle rain here
        return 0.25
    return 0.0


def _fetch():
    global _value, _busy
    try:
        url = ("https://api.open-meteo.com/v1/forecast?"
               f"latitude={LAT}&longitude={LON}&current_weather=true"
               "&timezone=Europe%2FBerlin&forecast_days=1")
        req = urllib.request.Request(url, headers={"User-Agent": "KeaDisplay/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            cur = json.loads(r.read().decode()).get("current_weather", {})
        code = int(cur.get("weathercode", 0))
        with _lock:
            _value = {
                "rain": _rain_from_code(code),
                "wind": float(cur.get("windspeed", 0.0)),
                "storm": code in (95, 96, 99),
                "is_day": bool(cur.get("is_day", 1)),
            }
    except Exception:
        pass  # keep last known conditions
    finally:
        _busy = False


def conditions():
    """Current conditions, refreshing in the background when stale."""
    global _stamp, _busy
    if not ENABLED:
        return dict(_value)
    if time.time() - _stamp > REFRESH and not _busy:
        _busy = True
        _stamp = time.time()
        threading.Thread(target=_fetch, daemon=True).start()
    with _lock:
        return dict(_value)
