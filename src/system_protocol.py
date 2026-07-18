"""SYSTEM PROTOCOL — local themed message engine.

Generates short, personal, Claude-style greetings ("BACK AT IT, CYRUS")
in the project's cyberpunk / steampunk voices. Time-of-day aware, with a
persisted history so messages stay fresh: nothing repeats until most of
the pool has been seen. Zero network calls.
"""

import json
import os
import random
import threading
import time
import urllib.request
from datetime import datetime

USER_NAME = os.getenv("KEA_USER", "CYRUS")
HISTORY_PATH = os.path.join(os.path.expanduser("~"), ".kea_protocol_history.json")

# ---------------------------------------------------------------------------
# Message pools. {name} is substituted. Buckets: dawn/morning/afternoon/
# evening/night, plus "any". Both themes are always mixed together.
# ---------------------------------------------------------------------------
CYBERPUNK = {
    "dawn": [
        "BOOT SEQUENCE COMPLETE. EARLY START, {name}.",
        "THE GRID IS QUIET AT THIS HOUR, {name}.",
        "FIRST LIGHT OVER THE SPRAWL, {name}.",
        "DAWN PATROL, {name}? RESPECT.",
    ],
    "morning": [
        "MORNING, {name}. CACHE CLEARED, EYES FRESH.",
        "COFFEE.EXE LOADED, {name}?",
        "SUNRISE OVER THE SPRAWL, {name}.",
        "GOOD MORNING, OPERATOR {name}.",
        "NEW DAY, CLEAN LOGS, {name}.",
        "DAYLIGHT MODE ENGAGED. LET'S RUN, {name}.",
    ],
    "afternoon": [
        "MIDDAY GRIND, {name}. HYDRATION CHECK.",
        "THE GRID HUMS ALONG, {name}.",
        "STILL COMPILING, {name}?",
        "AFTERNOON, {name}. SIGNAL HOLDING STEADY.",
        "HALF THE DAY BANKED, {name}. SPEND THE REST WELL.",
    ],
    "evening": [
        "NEON'S COMING ON, {name}.",
        "GOOD EVENING, OPERATOR {name}.",
        "CITY LIGHTS LOOK GOOD ON YOU, {name}.",
        "EVENING SHIFT, {name}. THE BEST IDEAS RUN AT DUSK.",
        "SUNSET RENDERED AT FULL RESOLUTION, {name}.",
    ],
    "night": [
        "THE CITY NEVER SLEEPS. NEITHER DO YOU, {name}?",
        "LATE SHIFT AGAIN, {name}?",
        "MIDNIGHT PROTOCOL ENGAGED.",
        "DREAM IN CHROME, {name}.",
        "THE QUIET HOURS ARE YOURS, {name}.",
        "NIGHT RUN, {name}. WATCH YOUR SIX.",
    ],
    "any": [
        "BACK AT IT, {name}.",
        "BACK ON THE GRID, {name}.",
        "WELCOME BACK TO THE MAINFRAME, {name}.",
        "SIGNAL'S CLEAN TODAY, {name}.",
        "ALL SYSTEMS NOMINAL. ALL EYES FORWARD.",
        "ANOTHER RUN THROUGH THE SPRAWL, {name}?",
        "CHROME POLISHED. PROTOCOLS LOADED.",
        "JACKED IN AND READY, {name}.",
        "YOUR TABLE IN CYBERSPACE IS RESERVED, {name}.",
        "FIRMWARE STEADY. HEART RATE OPTIONAL.",
        "GOOD TO SEE YOU ON THIS SIDE OF THE SCREEN, {name}.",
        "THE FEED MISSED YOU, {name}.",
    ],
}

STEAMPUNK = {
    "dawn": [
        "BOILERS WARMING WITH THE SUN, {name}.",
        "EARLY STEAM RISES CLEANEST, {name}.",
        "THE NIGHT WATCH STANDS RELIEVED, {name}.",
    ],
    "morning": [
        "BOILERS AT PRESSURE. GOOD MORNING, {name}.",
        "STOKE THE FURNACE, {name} — THE DAY AWAITS.",
        "MORNING WHISTLE'S BLOWN, {name}.",
        "TEA AND TORQUE, {name}?",
        "GEARS OILED, LEDGERS OPEN. MORNING, {name}.",
    ],
    "afternoon": [
        "GEARS TURNING SMOOTHLY THIS AFTERNOON, {name}.",
        "PRESSURE STEADY AT MIDDAY, {name}.",
        "THE WORKSHOP HUMS ALONG, {name}.",
    ],
    "evening": [
        "GASLAMPS LIT. EVENING, {name}.",
        "THE WORKSHOP GLOWS WARM TONIGHT, {name}.",
        "EVENING POST DELIVERED, {name}. NOTHING URGENT.",
        "WIND THE CLOCKS, {name}. THE DAY IS EASING OUT.",
    ],
    "night": [
        "NIGHT WATCH ENGAGED. STEAM LOW, {name}.",
        "THE AIRSHIPS SLEEP. DO YOU, {name}?",
        "MOONLIT BRASS AND QUIET GEARS.",
        "BANK THE FIRES SOON, {name}.",
    ],
    "any": [
        "TELEGRAPH LINES HUM WITH YOUR RETURN, {name}.",
        "COGS ALIGNED. STEAM RISING.",
        "AIRSHIP DOCKED. WELCOME HOME, {name}.",
        "THE BRASS IS POLISHED, {name}.",
        "FULL STEAM AHEAD, {name}.",
        "YOUR GOGGLES, AS ALWAYS, ARE ON YOUR FOREHEAD, {name}.",
        "CLOCKWORK IN MOTION, CAPTAIN {name}.",
        "MANIFEST SIGNED. DESTINATION: ANYWHERE.",
        "A FINE DAY FOR INVENTION, {name}.",
        "THE DIFFERENCE ENGINE SENDS ITS REGARDS, {name}.",
    ],
}

# Date-flavoured templates — these renew themselves daily/weekly for free.
DATED = [
    "IT'S {weekday}, {name}. MAKE IT COUNT.",
    "{weekday} PROTOCOL ENGAGED.",
    "DAY {doy} OF THE YEAR. STILL SHINY.",
    "WEEK {week}: THE GEARS GRIND ON.",
    "{weekday}. THE SPRAWL EXPECTS GREAT THINGS.",
]


def _bucket(hour):
    if 5 <= hour < 8:
        return "dawn"
    if 8 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


# ═══════════════════════════════════════════════════════════════════════════
# LIVE DATA FEEDS — free, no-auth realtime APIs rendered in the punk voices.
# Everything is async, cached and fail-silent: no network, no problem —
# the local pool always carries the show. Disable with KEA_FEEDS=0.
# ═══════════════════════════════════════════════════════════════════════════
FEEDS_ENABLED = os.getenv("KEA_FEEDS", "1").strip().lower() not in {"0", "false", "off"}
LAT, LON = 48.7428, 9.1015          # Stuttgart (same as weather_api)


def _get_json(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "KeaDisplay/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _clip(text, n=88):
    text = " ".join(str(text).split())
    return (text[: n - 1].rstrip() + "…") if len(text) > n else text


class _Feed:
    """Background-refreshed cached value. get() never blocks."""

    def __init__(self, ttl, fetcher):
        self.ttl = ttl
        self.fetcher = fetcher
        self.value = None
        self.stamp = 0.0
        self._busy = False

    def get(self):
        if not FEEDS_ENABLED:
            return None
        if (time.time() - self.stamp > self.ttl) and not self._busy:
            self._busy = True
            threading.Thread(target=self._refresh, daemon=True).start()
        return self.value

    def _refresh(self):
        try:
            v = self.fetcher()
            if v is not None:
                self.value = v
                self.stamp = time.time()
            else:
                self.stamp = time.time() - self.ttl + 300
        except Exception:
            self.stamp = time.time() - self.ttl + 300   # retry in ~5 min
        finally:
            self._busy = False


def _fetch_iss():
    d = _get_json("http://api.open-notify.org/iss-now.json")
    p = d.get("iss_position", {})
    return {"lat": float(p["latitude"]), "lon": float(p["longitude"])}


def _fetch_astros():
    d = _get_json("http://api.open-notify.org/astros.json")
    return {"n": int(d.get("number", 0))}


def _fetch_onthisday():
    now = datetime.now()
    d = _get_json("https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/"
                  f"{now.month}/{now.day}")
    events = [(e.get("year"), e.get("text", "")) for e in d.get("events", [])
              if e.get("text")]
    return {"events": random.sample(events, min(6, len(events)))} if events else None


def _fetch_wire():
    ids = _get_json("https://hacker-news.firebaseio.com/v0/topstories.json")[:8]
    item = _get_json(f"https://hacker-news.firebaseio.com/v0/item/{random.choice(ids)}.json")
    title = item.get("title")
    return {"title": title} if title else None


def _fetch_wx():
    d = _get_json("https://api.open-meteo.com/v1/forecast?"
                  f"latitude={LAT}&longitude={LON}&current_weather=true"
                  "&daily=sunrise,sunset&timezone=Europe%2FBerlin&forecast_days=1")
    cur = d.get("current_weather", {})
    daily = d.get("daily", {})
    return {
        "temp": cur.get("temperature"),
        "wind": cur.get("windspeed", 0),
        "sunrise": (daily.get("sunrise") or ["T??:??"])[0][-5:],
        "sunset": (daily.get("sunset") or ["T??:??"])[0][-5:],
    }


_FEEDS = {
    "iss": _Feed(600, _fetch_iss),
    "astros": _Feed(6 * 3600, _fetch_astros),
    "history": _Feed(12 * 3600, _fetch_onthisday),
    "wire": _Feed(1800, _fetch_wire),
    "wx": _Feed(1800, _fetch_wx),
}


def _region(lat, lon):
    """Very coarse 'where is that over' lookup — flavor, not navigation."""
    if lat < -60:
        return "THE SOUTHERN OCEAN"
    if -170 <= lon <= -100:
        return "THE PACIFIC"
    if -100 < lon <= -30:
        return "THE AMERICAS"
    if -30 < lon <= 20:
        return "EUROPE" if lat > 35 else ("AFRICA" if lat > -5 else "THE SOUTH ATLANTIC")
    if 20 < lon <= 60:
        return "THE STEPPES" if lat > 30 else "THE INDIAN OCEAN"
    if 60 < lon <= 150:
        return "ASIA" if lat > 20 else "THE INDIAN OCEAN"
    return "THE PACIFIC"


def _moon_phase():
    """Local computation — works offline."""
    days = (datetime.now() - datetime(2000, 1, 6, 18, 14)).total_seconds() / 86400.0
    frac = (days % 29.530588) / 29.530588
    names = ["NEW", "WAXING CRESCENT", "FIRST QUARTER", "WAXING GIBBOUS",
             "FULL", "WANING GIBBOUS", "LAST QUARTER", "WANING CRESCENT"]
    return names[int((frac * 8 + 0.5) % 8)]


def _live_candidates(name):
    """Render every fresh feed into themed message candidates."""
    out = []
    iss = _FEEDS["iss"].get()
    astros = _FEEDS["astros"].get()
    if iss:
        region = _region(iss["lat"], iss["lon"])
        out += [f"STATION PASS: {region}. LOOK UP, {name}.",
                f"THE GREAT AIRSHIP RIDES OVER {region} TONIGHT."]
        if astros and astros["n"]:
            out += [f"{astros['n']} SOULS IN ORBIT OVER {region} RIGHT NOW.",
                    f"THE SKY HAS {astros['n']} TENANTS, {name}."]
    hist = _FEEDS["history"].get()
    if hist and hist.get("events"):
        year, text = random.choice(hist["events"])
        out += [f"MEMORY BANKS // {year}: {_clip(text, 70).upper()}",
                f"ARCHIVE, {year}: {_clip(text, 74).upper()}"]
    wire = _FEEDS["wire"].get()
    if wire:
        out += [f"THE WIRE // {_clip(wire['title'], 72).upper()}",
                f"TELEGRAPH INTERCEPT // {_clip(wire['title'], 62).upper()}"]
    wx = _FEEDS["wx"].get()
    if wx and wx.get("temp") is not None:
        t = round(wx["temp"])
        out += [f"{t}°C ON THE STREETS OF THE SPRAWL.",
                f"BAROMETER READS {t} DEGREES. STOKE ACCORDINGLY."]
        if wx.get("wind", 0) >= 25:
            out.append(f"WIND {round(wx['wind'])} KM/H — MIND YOUR GOGGLES, {name}.")
        hour = datetime.now().hour
        if hour < 12:
            out.append(f"SUNRISE WAS {wx['sunrise']}. FIRST LIGHT ON THE BRASS.")
        else:
            out.append(f"SUNSET AT {wx['sunset']}. NEON AFTER THAT, {name}.")
    out.append(f"{_moon_phase()} MOON TONIGHT, {name}.")
    # open reminders nag their way into every world's ticker
    try:
        from backend.reminders import ReminderService, stage_for
        import time as _time
        for r in ReminderService.instance().active()[:3]:
            stage = stage_for(_time.time() - r["ts"])
            if stage in ("FINAL CALL", "OVERDUE"):
                out.append(f"DOCKET // {stage}: {_clip(r['text'], 60).upper()}")
    except Exception:
        pass
    return out


class SystemProtocol:
    """Fresh, themed, personal status messages. Thread-safe singleton pool."""

    _lock = threading.Lock()
    _history = None  # loaded lazily, shared across instances

    def __init__(self, name=USER_NAME):
        self.name = name

    # -- history persistence -------------------------------------------------
    @classmethod
    def _load_history(cls):
        if cls._history is None:
            try:
                with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                    cls._history = list(json.load(f))[-500:]
            except Exception:
                cls._history = []
        return cls._history

    @classmethod
    def _save_history(cls):
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(cls._history[-500:], f)
        except Exception:
            pass  # history is a nicety — never crash the display over it

    # -- pool building --------------------------------------------------------
    def _pool(self, now=None):
        now = now or datetime.now()
        bucket = _bucket(now.hour)
        raw = []
        for theme in (CYBERPUNK, STEAMPUNK):
            raw.extend(theme.get(bucket, []))
            raw.extend(theme["any"])
        fields = {
            "name": self.name,
            "weekday": now.strftime("%A").upper(),
            "doy": now.timetuple().tm_yday,
            "week": int(now.strftime("%W")) or 1,
        }
        pool = [t.format(**fields) for t in raw]
        pool.extend(t.format(**fields) for t in DATED)
        return pool

    # -- public API ------------------------------------------------------------
    def next_message(self, now=None):
        """A random themed message not shown recently. Roughly half the
        time (when feeds are warm) it carries live data — ISS position,
        today-in-history, the wire, weather, moon phase — spoken in the
        same voices as the local pool."""
        live = _live_candidates(self.name)
        with SystemProtocol._lock:
            history = self._load_history()
            pool = self._pool(now)
            fresh = [m for m in pool if m not in history]
            live_fresh = [m for m in live if m not in history]
            if not fresh:
                # pool exhausted for this bucket — forget the oldest half
                del history[: max(1, len(history) // 2)]
                fresh = [m for m in pool if m not in history] or pool
                live_fresh = [m for m in live if m not in history]
            if live_fresh and random.random() < 0.65:
                msg = random.choice(live_fresh)
            else:
                msg = random.choice(fresh)
            history.append(msg)
            # keep history bounded relative to what exists
            cap = max(60, int(len(pool) * 4))
            if len(history) > cap:
                del history[: len(history) - cap]
            self._save_history()
            return msg

    def next_messages(self, n=3, now=None):
        return [self.next_message(now) for _ in range(n)]
