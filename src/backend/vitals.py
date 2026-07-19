"""
vitals.py — the machine's own health.

Reads the Raspberry Pi's core temperature, throttle state and uptime
straight from /sys and /proc. Matters more than usual here: the Pi
lives sealed inside a 3D-printed cabinet with no fan, so thermal
headroom is a real concern. Everything degrades gracefully to None on
a desktop, and nothing ever raises.
"""

import os
import time

THERM = "/sys/class/thermal/thermal_zone0/temp"

# Pi 3B+ soft-throttles at 60 C and hard-throttles at 80 C.
WARN_C = 62.0
HOT_C = 72.0

_last = {"t": 0.0, "temp": None, "uptime": None}


def core_temp_c():
    """Core temperature in Celsius, or None off-Pi. Cached for 5 s."""
    now = time.time()
    if now - _last["t"] < 5.0:
        return _last["temp"]
    _last["t"] = now
    try:
        with open(THERM, "r", encoding="utf-8") as f:
            _last["temp"] = int(f.read().strip()) / 1000.0
    except Exception:
        _last["temp"] = None
    return _last["temp"]


def uptime_s():
    """Seconds since boot, or None if unavailable."""
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            return float(f.read().split()[0])
    except Exception:
        return None


def uptime_str():
    up = uptime_s()
    if up is None:
        return "--"
    d, rem = divmod(int(up), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}D {h:02d}H"
    return f"{h:02d}H {m:02d}M"


def thermal_level():
    """'nominal' | 'warn' | 'hot' | 'unknown'."""
    t = core_temp_c()
    if t is None:
        return "unknown"
    if t >= HOT_C:
        return "hot"
    if t >= WARN_C:
        return "warn"
    return "nominal"
