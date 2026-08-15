"""
vvs.py — real-time departures from the Stuttgart network.

Kea already has two screens built around departure boards that do not
depart from anywhere: the Aerodrome tows banners across the sky, and
Bay 94 lands a freighter on a loop. This turns the same idiom onto real
trams and trains, so the board is telling you something.

The endpoint is VVS's EFA departure monitor, which speaks JSON if asked
politely:

    https://www3.vvs.de/vvs/widget/XML_DM_REQUEST?outputFormat=rapidJSON&...

No API key, no account, no pip install — plain urllib and json, the same
as backend/weather_api.py. That matters on a Pi that has to survive a
reimage.

    from backend import vvs
    vvs.fetch(my_route, callback)      # threaded, never blocks the loop

WHAT IT IS FOR

Not "the next tram is in 4 minutes" — a phone does that better. The
useful question at a desk is *do I need to stand up*. So a Route carries
`walk_min`, the time to your stop, and every departure knows whether you
can still make it. `catchable()` is the honest answer; `leave_in()` is
the number worth putting in big type.

Everything here degrades rather than raises: no network, a reshaped API,
a stop that stops existing — you get a Departure list that is empty and
an `error` string to put on the screen, because a transit board that
lies is worse than one that admits it is blind.
"""

import datetime
import json
import os
import threading
import urllib.parse
import urllib.request

try:
    from zoneinfo import ZoneInfo
except Exception:                       # pragma: no cover
    ZoneInfo = None

ENDPOINT = "https://www3.vvs.de/vvs/widget/XML_DM_REQUEST"
STOPFINDER = "https://www3.vvs.de/vvs/widget/XML_STOPFINDER_REQUEST"
TIMEOUT = 8
TZ = "Europe/Berlin"

# The API's product classes, mapped to something a small screen can show.
PRODUCT = {
    0: "ZUG", 1: "S", 2: "U", 3: "U", 4: "TRAM",
    5: "BUS", 6: "BUS", 7: "BUS", 8: "SEIL", 9: "SCHIFF",
    10: "RUF", 11: "SONST", 13: "RE", 14: "IC", 15: "IC", 16: "ICE",
}


class Route:
    """One thing you actually catch.

    stop_id   global VVS id, e.g. "de:08111:6118" (use tools/find_stop.py)
    lines     which lines count, e.g. {"U6", "U7"}; empty = all of them
    towards   substring match on the destination, so you get one
              direction rather than both platforms
    walk_min  minutes from your desk to the platform
    """

    def __init__(self, stop_id, label=None, lines=None, towards=None,
                 walk_min=5):
        self.stop_id = stop_id
        self.label = label or stop_id
        self.lines = {l.upper() for l in (lines or [])}
        self.towards = (towards or "").lower()
        self.walk_min = walk_min

    def wants(self, dep):
        if self.lines and dep.line.upper() not in self.lines:
            return False
        if self.towards and self.towards not in dep.towards.lower():
            return False
        return True

    def __repr__(self):
        return f"<Route {self.label} {sorted(self.lines) or 'all'}>"


class Departure:
    """One tram, with the two numbers that matter."""

    def __init__(self, line, towards, planned, estimated, product,
                 platform="", cancelled=False, walk_min=0):
        self.line = line
        self.towards = towards
        self.planned = planned          # aware datetime, local
        self.estimated = estimated      # aware datetime, local
        self.product = product
        self.platform = platform
        self.cancelled = cancelled
        self.walk_min = walk_min

    @property
    def delay_min(self):
        return int(round((self.estimated - self.planned).total_seconds() / 60.0))

    def in_min(self, now=None):
        """Minutes until it goes."""
        now = now or _now()
        return (self.estimated - now).total_seconds() / 60.0

    def leave_in(self, now=None):
        """Minutes until you have to stand up. This is the number that
        belongs in big type — negative means it has already gone as far
        as you are concerned, even though the tram is still coming."""
        return self.in_min(now) - self.walk_min

    def catchable(self, now=None):
        return (not self.cancelled) and self.leave_in(now) >= 0

    def __repr__(self):
        d = f" +{self.delay_min}" if self.delay_min else ""
        x = " CANCELLED" if self.cancelled else ""
        return (f"<{self.line} -> {self.towards} "
                f"{self.estimated:%H:%M}{d}{x}>")


def _tz():
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(TZ)
    except Exception:
        return None


def _now():
    return datetime.datetime.now(_tz())


def _parse_time(raw):
    """The API sends UTC with a trailing Z; give back local."""
    if not raw:
        return None
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    tz = _tz()
    return dt.astimezone(tz) if tz else dt


def _get(url, params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{q}",
                                 headers={"User-Agent": "Kea/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def departures(route, limit=12):
    """Fetch synchronously. Returns (list[Departure], error_or_None).

    Callers on the render thread must use fetch() instead — this blocks.
    """
    try:
        data = _get(ENDPOINT, {
            "outputFormat": "rapidJSON",
            "name_dm": route.stop_id,
            "type_dm": "any",
            "mode": "direct",
            "useRealtime": "1",
            "limit": str(limit),
        })
    except Exception as exc:                       # noqa: BLE001
        return [], f"{type(exc).__name__}"

    events = data.get("stopEvents")
    if not isinstance(events, list):
        # A valid response with no stopEvents is normal at night; a
        # response with no such *key* means the shape changed.
        if "stopEvents" in data:
            return [], None
        return [], "unexpected response"

    out = []
    for ev in events:
        try:
            tr = ev.get("transportation") or {}
            planned = _parse_time(ev.get("departureTimePlanned"))
            if planned is None:
                continue
            est = _parse_time(ev.get("departureTimeEstimated")) or planned
            dest = (tr.get("destination") or {}).get("name", "")
            loc = ev.get("location") or {}
            props = loc.get("properties") or {}
            status = ev.get("realtimeStatus") or []
            dep = Departure(
                line=tr.get("disassembledName") or tr.get("number") or "?",
                towards=dest,
                planned=planned,
                estimated=est,
                product=PRODUCT.get((tr.get("product") or {}).get("class"), ""),
                platform=props.get("platformName", "") or "",
                cancelled=("TRIP_CANCELLED" in status
                           or "STOP_CANCELLED" in status),
                walk_min=route.walk_min,
            )
        except Exception:                          # noqa: BLE001
            continue                               # one bad row, not a dead board
        if route.wants(dep):
            out.append(dep)

    out.sort(key=lambda d: d.estimated)
    return out, None


def disruptions(route_or_data, limit=12):
    """Any high-priority service messages attached to the stop.

    VVS puts lift outages and diversions in every stop event, repeated;
    this pulls the distinct high-priority titles out.
    """
    route = route_or_data
    try:
        data = _get(ENDPOINT, {
            "outputFormat": "rapidJSON", "name_dm": route.stop_id,
            "type_dm": "any", "mode": "direct", "useRealtime": "1",
            "limit": str(limit),
        })
    except Exception:                              # noqa: BLE001
        return []
    seen, out = set(), []
    for ev in data.get("stopEvents", []) or []:
        for info in ev.get("infos", []) or []:
            if info.get("priority") != "high":
                continue
            for link in info.get("infoLinks", []) or []:
                t = (link.get("subtitle") or link.get("title") or "").strip()
                if t and t not in seen:
                    seen.add(t)
                    out.append(t)
    return out


def fetch(routes, callback, limit=12):
    """Fetch every route on a worker thread; callback gets a dict.

    Never raises, never blocks the render loop — see UI_GUIDELINES §7.
    The callback receives:
        {"routes": [(Route, [Departure], error), ...], "error": str|None}
    """
    if isinstance(routes, Route):
        routes = [routes]

    def _work():
        rows, first_err = [], None
        for r in routes:
            deps, err = departures(r, limit=limit)
            if err and first_err is None:
                first_err = err
            rows.append((r, deps, err))
        try:
            callback({"routes": rows, "error": first_err,
                      "fetched": _now()})
        except Exception:                          # noqa: BLE001
            pass                                   # a bad callback is not our problem

    threading.Thread(target=_work, daemon=True).start()


def routes_from_env(raw=None):
    """Parse KEA_VVS_ROUTES into Route objects.

        stop_id | label | lines | towards | walk_min

    separated by ';', e.g.

        de:08111:6118|Hbf|U6,U7|Flughafen|7 ; de:08111:1234|Home|42||5

    Only the stop id is required. Empty `lines` means every line at the
    stop; empty `towards` means both directions. Anything unparseable is
    skipped rather than crashing the screen — a typo in an env var should
    cost you one route, not the whole board.
    """
    raw = os.getenv("KEA_VVS_ROUTES", "") if raw is None else raw
    out = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [p.strip() for p in chunk.split("|")]
        stop = parts[0]
        if not stop:
            continue
        label = parts[1] if len(parts) > 1 and parts[1] else stop
        lines = [l for l in (parts[2].split(",") if len(parts) > 2 else []) if l]
        towards = parts[3] if len(parts) > 3 else ""
        try:
            walk = int(parts[4]) if len(parts) > 4 and parts[4] else 5
        except ValueError:
            walk = 5
        out.append(Route(stop, label=label, lines=lines,
                         towards=towards, walk_min=max(0, walk)))
    return out


def find_stop(query, limit=8):
    """Resolve a stop name to (global_id, name) pairs. Blocking —
    this is for tools/find_stop.py, not for the render loop."""
    try:
        data = _get(STOPFINDER, {
            "outputFormat": "rapidJSON",
            "name_sf": query,
            "type_sf": "any",
        })
    except Exception as exc:                       # noqa: BLE001
        return [], f"{type(exc).__name__}"
    out = []
    for loc in (data.get("locations") or [])[:limit]:
        if loc.get("type") not in ("stop", "street", "locality", "poi"):
            continue
        out.append((loc.get("id", ""), loc.get("name", ""),
                    loc.get("type", ""), loc.get("matchQuality", 0)))
    return out, None
