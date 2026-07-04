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
        """A random themed message not shown recently."""
        with SystemProtocol._lock:
            history = self._load_history()
            pool = self._pool(now)
            fresh = [m for m in pool if m not in history]
            if not fresh:
                # pool exhausted for this bucket — forget the oldest half
                del history[: max(1, len(history) // 2)]
                fresh = [m for m in pool if m not in history] or pool
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
