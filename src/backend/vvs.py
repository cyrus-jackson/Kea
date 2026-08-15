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
    vvs.fetch(vvs.routes_from_env(), callback)   # threaded, never blocks

TWO QUESTIONS, TWO ENDPOINTS

A stop board answers "what is leaving this platform". That is the wrong
question for a commute. "Universität to Max-Planck-Institute" cannot be
expressed as a filtered stop board at all: the only service is the 748,
which has "Ostelsheim" on the front, and the S-Bahn into town shows a
dozen different terminus names depending on the hour. Filtering on those
strings is guesswork.

So a Route can be a JOURNEY (origin -> destination, via the trip
planner) as well as a stop board, and Journey exposes the same
leave_in() / catchable() interface as Departure, so the screen does not
care which kind it is holding.

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
TRIP = "https://www3.vvs.de/vvs/widget/XML_TRIP_REQUEST2"
STOPFINDER = "https://www3.vvs.de/vvs/widget/XML_STOPFINDER_REQUEST"
TIMEOUT = 8
TZ = "Europe/Berlin"

# The API's product classes, mapped to something a small screen can show.
PRODUCT = {
    0: "ZUG", 1: "S", 2: "U", 3: "U", 4: "TRAM",
    5: "BUS", 6: "BUS", 7: "BUS", 8: "SEIL", 9: "SCHIFF",
    10: "RUF", 11: "SONST", 13: "RE", 14: "IC", 15: "IC", 16: "ICE",
    99: "WALK", 100: "WALK",
}
WALKING = {99, 100}


# The stops Kea knows about out of the box. Resolved from the live VVS
# stop finder, not guessed — see tools/find_stop.py to add your own.
STOPS = {
    "universitaet": "de:08111:6008",     # S-Bahn + bus
    "hauptbahnhof": "de:08111:6118",     # Hbf (tief), where the S-Bahn goes
    "vaihingen":    "de:08111:6002",     # Vaihingen Bahnhof
    "max-planck":   "de:08111:2589",     # Max-Planck-Institute (bus only)
}

# Kea's default board: everything Cyrus actually leaves the university for.
#
# These are JOURNEYS, not stop departures, and they have to be. Two of the
# three cannot be expressed as "departures from Universität filtered by
# destination": Max-Planck-Institute is bus-only and served by the 748,
# whose final destination is Ostelsheim, and the S-Bahn towards town shows
# a dozen different terminus names. Filtering on those strings would be
# guesswork. Asking the journey planner "how do I get from here to there"
# is the question actually being asked.
# The walk time is per route, not per person, because it is the walk to
# THAT platform: the S-Bahn into town leaves from the far end of the
# station, the bus stops are next to the door. Measured by Cyrus.
DEFAULT_ROUTES = [
    (STOPS["universitaet"], STOPS["hauptbahnhof"], "HAUPTBAHNHOF", 13),
    (STOPS["universitaet"], STOPS["vaihingen"],    "VAIHINGEN",     5),
    (STOPS["universitaet"], STOPS["max-planck"],   "MAX-PLANCK",    5),
]


class Route:
    """One thing you actually catch.

    stop_id   global VVS id, e.g. "de:08111:6118" (use tools/find_stop.py)
    lines     which lines count, e.g. {"U6", "U7"}; empty = all of them
    towards   substring match on the destination, so you get one
              direction rather than both platforms
    walk_min  minutes from your desk to the platform
    """

    def __init__(self, stop_id, label=None, lines=None, towards=None,
                 walk_min=5, to_id=None):
        self.stop_id = stop_id
        self.to_id = to_id              # set = journey mode (A -> B)
        self.label = label or stop_id
        self.lines = {l.upper() for l in (lines or [])}
        self.towards = (towards or "").lower()
        self.walk_min = walk_min

    @property
    def is_trip(self):
        """Journey mode asks 'how do I get from A to B'; stop mode asks
        'what is leaving this platform'. Different endpoints entirely."""
        return bool(self.to_id)

    def wants(self, dep):
        if self.lines and dep.line.upper() not in self.lines:
            return False
        if self.towards and self.towards not in dep.towards.lower():
            return False
        return True

    def __repr__(self):
        if self.is_trip:
            return f"<Route {self.label} {self.stop_id}->{self.to_id}>"
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


class Leg:
    """One vehicle (or one walk) inside a journey."""

    def __init__(self, line, product, frm, to, dep, arr, platform=""):
        self.line = line
        self.product = product
        self.frm = frm
        self.to = to
        self.dep = dep
        self.arr = arr
        self.platform = platform

    @property
    def walking(self):
        return self.product == "WALK"

    def __repr__(self):
        return f"<{self.line} {self.frm}->{self.to} {self.dep:%H:%M}>"


class Journey:
    """A way of getting from A to B, with the two numbers that matter.

    Same interface as Departure where it counts — leave_in(), catchable()
    — so the screen does not care which kind of thing it is holding.
    """

    def __init__(self, legs, walk_min=0, cancelled=False):
        self.legs = legs
        self.walk_min = walk_min
        self.cancelled = cancelled
        self.planned = legs[0].dep if legs else None
        self.estimated = self.planned
        self.arrival = legs[-1].arr if legs else None

    @property
    def ride(self):
        """The first leg you actually board. A journey that starts with a
        five minute walk to another platform should show the vehicle, not
        the word WALK."""
        for l in self.legs:
            if not l.walking:
                return l
        return self.legs[0] if self.legs else None

    @property
    def line(self):
        r = self.ride
        return r.line if r else "?"

    @property
    def product(self):
        r = self.ride
        return r.product if r else ""

    @property
    def platform(self):
        r = self.ride
        return r.platform if r else ""

    @property
    def towards(self):
        return self.legs[-1].to if self.legs else ""

    @property
    def changes(self):
        """Interchanges = boardings minus one. Walking legs are not
        changes; they are the walking between them."""
        return max(0, len([l for l in self.legs if not l.walking]) - 1)

    @property
    def duration_min(self):
        if not (self.planned and self.arrival):
            return 0
        return int(round((self.arrival - self.planned).total_seconds() / 60.0))

    @property
    def delay_min(self):
        return 0            # realtime is folded into estimated already

    def in_min(self, now=None):
        now = now or _now()
        return (self.estimated - now).total_seconds() / 60.0

    def leave_in(self, now=None):
        return self.in_min(now) - self.walk_min

    def catchable(self, now=None):
        return (not self.cancelled) and self.leave_in(now) >= 0

    def __repr__(self):
        return (f"<Journey {self.line} {self.planned:%H:%M}->"
                f"{self.arrival:%H:%M} {self.changes}ch>")


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


def trips(route, limit=5):
    """Journeys from route.stop_id to route.to_id.

    Returns (list[Journey], error_or_None). Blocking — use fetch().
    """
    try:
        data = _get(TRIP, {
            "outputFormat": "rapidJSON",
            "name_origin": route.stop_id,
            "type_origin": "any",
            "name_destination": route.to_id,
            "type_destination": "any",
            "calcNumberOfTrips": str(limit),
            "itdDateTimeDepArr": "dep",
            "useRealtime": "1",
            "coordListOutputFormat": "NONE",
            "genMaps": "0",
        })
    except Exception as exc:                       # noqa: BLE001
        return [], f"{type(exc).__name__}"

    journeys = data.get("journeys")
    if not isinstance(journeys, list):
        if "journeys" in data:
            return [], None                        # planner found nothing
        return [], "unexpected response"

    out = []
    for j in journeys:
        legs = []
        cancelled = False
        for raw in j.get("legs", []) or []:
            try:
                tr = raw.get("transportation") or {}
                o = raw.get("origin") or {}
                d = raw.get("destination") or {}
                dep = (_parse_time(o.get("departureTimeEstimated"))
                       or _parse_time(o.get("departureTimePlanned")))
                arr = (_parse_time(d.get("arrivalTimeEstimated"))
                       or _parse_time(d.get("arrivalTimePlanned")))
                if dep is None or arr is None:
                    continue
                cls = (tr.get("product") or {}).get("class")
                product = PRODUCT.get(cls, "")
                name = tr.get("disassembledName") or tr.get("number") or ""
                if cls in WALKING or not name:
                    product, name = "WALK", "WALK"
                legs.append(Leg(
                    line=name,
                    product=product,
                    frm=(o.get("parent") or {}).get("name") or o.get("name", ""),
                    to=(d.get("parent") or {}).get("name") or d.get("name", ""),
                    dep=dep, arr=arr,
                    platform=(o.get("properties") or {}).get("platform", "") or "",
                ))
                if "TRIP_CANCELLED" in (raw.get("realtimeStatus") or []):
                    cancelled = True
            except Exception:                      # noqa: BLE001
                continue                           # one bad leg, not a dead board
        if legs:
            out.append(Journey(legs, walk_min=route.walk_min,
                               cancelled=cancelled))

    out.sort(key=lambda j: j.estimated)
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
            if r.is_trip:
                deps, err = trips(r)
            else:
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
    """The board's routes. Defaults to Kea's three, unless you say otherwise.

    Two forms, chosen by whether the first field contains ">":

        JOURNEY   origin>destination | label | walk_min
        STOP      stop_id | label | lines | towards | walk_min

    separated by ";". For example:

        de:08111:6008>de:08111:6118|HAUPTBAHNHOF|5 ; de:08111:6118|Hbf|U6||7

    Journey form asks the planner how to get from A to B, which is the
    only way to express a route whose vehicles do not advertise your
    destination — the 748 to Max-Planck-Institute says "Ostelsheim" on
    the front. Stop form is the raw platform board.

    Set KEA_VVS_ROUTES="" to get an empty board; unset it for the
    defaults. Anything unparseable is skipped rather than crashing the
    screen: a typo should cost you one route, not the whole board.
    """
    if raw is None:
        raw = os.getenv("KEA_VVS_ROUTES")
    if raw is None:                                # unset: ship the defaults
        return [Route(frm, label=label, walk_min=walk, to_id=to)
                for frm, to, label, walk in DEFAULT_ROUTES]

    out = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [p.strip() for p in chunk.split("|")]
        stop = parts[0]
        if not stop:
            continue

        def _walk(i):
            try:
                return max(0, int(parts[i])) if len(parts) > i and parts[i] else 5
            except ValueError:
                return 5

        if ">" in stop:                            # journey form
            frm, _, to = stop.partition(">")
            frm, to = frm.strip(), to.strip()
            if not (frm and to):
                continue
            out.append(Route(frm, to_id=to,
                             label=parts[1] if len(parts) > 1 and parts[1] else to,
                             walk_min=_walk(2)))
        else:                                      # stop-board form
            lines = [l for l in (parts[2].split(",") if len(parts) > 2 else []) if l]
            out.append(Route(stop,
                             label=parts[1] if len(parts) > 1 and parts[1] else stop,
                             lines=lines,
                             towards=parts[3] if len(parts) > 3 else "",
                             walk_min=_walk(4)))
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
