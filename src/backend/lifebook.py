"""
lifebook.py — Kea's long-term memory.

A tiny persistent counter store so the device accumulates a life:
garden generations, specimen batches, characters telegraphed,
pomodoros completed, boots survived. Thread-safe, fail-silent.
"""

import datetime
import json
import os
import threading

PATH = os.path.join(os.path.expanduser("~"), ".kea_lifebook.json")

_lock = threading.Lock()
_data = None


def _load():
    global _data
    if _data is None:
        try:
            with open(PATH, "r", encoding="utf-8") as f:
                _data = dict(json.load(f))
        except Exception:
            _data = {}
    return _data


def _save():
    try:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(_data, f)
    except Exception:
        pass  # memory is a nicety — never crash the display over it


def get(key, default=0):
    with _lock:
        return _load().get(key, default)


def set_value(key, value):
    with _lock:
        _load()[key] = value
        _save()


def bump(key, amount=1):
    """Increment and return the new value."""
    with _lock:
        d = _load()
        d[key] = d.get(key, 0) + amount
        _save()
        return d[key]


# ── daily buckets, so the Logbook can chart a week ─────────────────────────
def bump_day(key, amount=1, when=None):
    """Increment today's bucket for `key` as well as its lifetime total."""
    day = (when or datetime.date.today()).isoformat()
    with _lock:
        d = _load()
        d[f"{key}:{day}"] = d.get(f"{key}:{day}", 0) + amount
        _save()


def recent_days(key, n=7):
    """[(date, count)] for the last n days, oldest first."""
    today = datetime.date.today()
    with _lock:
        d = _load()
        out = []
        for i in range(n - 1, -1, -1):
            day = today - datetime.timedelta(days=i)
            out.append((day, d.get(f"{key}:{day.isoformat()}", 0)))
        return out
