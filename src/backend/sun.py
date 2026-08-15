"""
sun.py — when the sun actually rises and sets, computed locally.

The drift circuit is supposed to follow the sun. It was following the
*clock*: the glasshouse at 05:00 all year, the aerodrome's "golden hour"
at 17:00 in June and 17:00 in December. In Stuttgart that is wrong by
over two hours at the solstices — in December the sun is down before the
aerodrome even arrives.

This computes the real thing. Two reasons it does the maths rather than
reading the weather API, which already returns sunrise and sunset:

  1. It must answer *synchronously*. Drift asks "which station owns this
     moment?" on enter and on every card rebuild. A network fetch there
     would block the render loop — see docs/UI_GUIDELINES.md §7.
  2. Kea boots offline more often than you would like, and the rounds
     still have to be in the right place.

So: the NOAA sunrise equation, pure stdlib, no network, microseconds to
evaluate. Accurate to well under a minute for our latitude, which is far
better than the circuit needs.

    from backend import sun
    sun.times(datetime.date.today())   -> (sunrise, noon, sunset) local
    sun.hours(datetime.date.today())   -> the same as float hours

Near the poles there are days with no sunrise at all; `times()` returns
None for those and callers fall back to fixed hours. Stuttgart never
gets there, but Kea should not break if someone runs it in Tromsø.
"""

import datetime
import math
import os

try:
    from zoneinfo import ZoneInfo
except Exception:                       # pragma: no cover - py<3.9
    ZoneInfo = None

# Stuttgart, matching backend/weather_api.py. Override for anywhere else.
try:
    LAT = float(os.getenv("KEA_LAT", "48.742844833881485"))
    LON = float(os.getenv("KEA_LON", "9.101519425845058"))
except ValueError:
    LAT, LON = 48.742844833881485, 9.101519425845058

TZ_NAME = os.getenv("KEA_TZ", "Europe/Berlin")

# The sun's centre is 0.833° below the horizon at the moment we call
# "sunrise" — half its disc plus atmospheric refraction.
ZENITH = -0.833

_J2000 = 2451545.0
_cache = {}                             # date -> result, one entry per day


def _tz():
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(TZ_NAME)
    except Exception:
        return None


def _julian(date):
    """Julian day number for a civil date (Fliegel-Van Flandern)."""
    a = (14 - date.month) // 12
    y = date.year + 4800 - a
    m = date.month + 12 * a - 3
    jdn = (date.day + (153 * m + 2) // 5 + 365 * y + y // 4
           - y // 100 + y // 400 - 32045)
    return jdn - 0.5                    # midnight rather than noon


def _from_julian(jd):
    """Julian date -> aware UTC datetime."""
    secs = (jd - _J2000) * 86400.0
    epoch = datetime.datetime(2000, 1, 1, 12, 0,
                              tzinfo=datetime.timezone.utc)
    return epoch + datetime.timedelta(seconds=secs)


def times(date=None, lat=None, lon=None):
    """(sunrise, solar_noon, sunset) as local aware datetimes.

    Returns None on a day with no sunrise or no sunset at this latitude.
    """
    date = date or datetime.date.today()
    lat = LAT if lat is None else lat
    lon = LON if lon is None else lon

    key = (date, round(lat, 4), round(lon, 4))
    if key in _cache:
        return _cache[key]

    rad = math.radians
    # days since J2000, corrected for longitude (the "mean solar time")
    n = round(_julian(date) - _J2000 + 0.0008)
    j_star = n - lon / 360.0

    # solar mean anomaly, and the equation of the centre
    M = (357.5291 + 0.98560028 * j_star) % 360.0
    C = (1.9148 * math.sin(rad(M))
         + 0.0200 * math.sin(rad(2 * M))
         + 0.0003 * math.sin(rad(3 * M)))
    lam = (M + C + 180.0 + 102.9372) % 360.0        # ecliptic longitude

    j_transit = (_J2000 + j_star
                 + 0.0053 * math.sin(rad(M))
                 - 0.0069 * math.sin(rad(2 * lam)))

    sin_dec = math.sin(rad(lam)) * math.sin(rad(23.4397))
    cos_dec = math.cos(math.asin(sin_dec))

    denom = math.cos(rad(lat)) * cos_dec
    if abs(denom) < 1e-12:
        _cache[key] = None
        return None
    cos_omega = ((math.sin(rad(ZENITH)) - math.sin(rad(lat)) * sin_dec)
                 / denom)
    if not -1.0 <= cos_omega <= 1.0:
        _cache[key] = None              # midnight sun, or polar night
        return None

    omega = math.degrees(math.acos(cos_omega))      # hour angle, degrees
    j_rise = j_transit - omega / 360.0
    j_set = j_transit + omega / 360.0

    tz = _tz()
    out = tuple(_from_julian(j).astimezone(tz) if tz else _from_julian(j)
                for j in (j_rise, j_transit, j_set))
    if len(_cache) > 8:                 # only ever a handful of days
        _cache.clear()
    _cache[key] = out
    return out


def hours(date=None, lat=None, lon=None):
    """(sunrise, noon, sunset) as float hours after local midnight.

    This is the form the drift circuit wants, since it compares against a
    wall-clock hour. Returns None where `times()` does.
    """
    t = times(date, lat, lon)
    if t is None:
        return None
    return tuple(d.hour + d.minute / 60.0 + d.second / 3600.0 for d in t)


def is_daylight(when=None):
    """Is the sun up right now? Falls back to a sane guess above the
    Arctic circle rather than raising."""
    when = when or datetime.datetime.now(_tz())
    t = times(when.date())
    if t is None:
        return 6 <= when.hour < 18
    if when.tzinfo is None and t[0].tzinfo is not None:
        when = when.replace(tzinfo=t[0].tzinfo)
    return t[0] <= when <= t[2]
