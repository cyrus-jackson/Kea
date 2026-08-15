#!/usr/bin/env python3
"""
test_vvs.py — the departure parser, checked offline.

The fixture is a real response from the VVS endpoint, trimmed. Testing
against it rather than against the live API means this never flakes at
3am when nothing is running, never depends on the network, and still
breaks loudly if VVS reshapes the JSON — because the fixture stops
matching what tools/check_vvs.py sees from the real thing.

    python3 tests/test_vvs.py        # exit 0 = good
"""

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from backend import vvs                                    # noqa: E402

RAW = json.load(open(os.path.join(ROOT, "tests", "fixtures", "vvs_hbf.json"),
                     encoding="utf-8"))
TRIP = json.load(open(os.path.join(ROOT, "tests", "fixtures", "vvs_trip.json"),
                      encoding="utf-8"))
NOW = datetime.datetime(2026, 8, 15, 14, 30, tzinfo=vvs._tz())

fails = []


def check(what, got, want):
    ok = got == want
    print(f"  [{'PASS' if ok else 'FAIL'}] {what}: {got!r}")
    if not ok:
        fails.append(f"{what}: got {got!r}, wanted {want!r}")


def main():
    vvs._get = lambda url, params: RAW
    vvs._now = lambda: NOW

    print("parsing")
    deps, err = vvs.departures(vvs.Route("de:08111:6118", walk_min=5))
    check("no error on a good response", err, None)
    check("5 rows parsed, malformed one skipped", len(deps), 5)
    check("sorted by departure",
          [d.estimated for d in deps] == sorted(d.estimated for d in deps), True)

    print("\nrealtime")
    u6 = [d for d in deps if d.line == "U6"][0]
    u12 = [d for d in deps if d.line == "U12"][0]
    check("delay read from estimated vs planned", u6.delay_min, 1)
    check("TRIP_CANCELLED honoured", u12.cancelled, True)
    check("a cancelled tram is never catchable", u12.catchable(), False)
    check("product class 3 -> U", u6.product, "U")
    check("product class 5 -> BUS",
          [d for d in deps if d.line == "42"][0].product, "BUS")

    print("\nfiltering")
    check("by line",
          [d.line for d in vvs.departures(vvs.Route("x", lines=["U6"]))[0]],
          ["U6", "U6"])
    check("by direction, case-insensitive",
          [d.line for d in vvs.departures(vvs.Route("x", towards="mönchfeld"))[0]],
          ["U7"])
    check("line and direction together",
          len(vvs.departures(vvs.Route("x", lines=["U6", "U7"],
                                       towards="Flughafen"))[0]), 2)

    print("\nwalk time — the point of the whole thing")
    near = vvs.departures(vvs.Route("x", lines=["U6"], walk_min=5))[0][0]
    check("6 min away, 5 min walk -> leave in ~1 min",
          round(near.leave_in()), 1)
    check("catchable with a 5 min walk", near.catchable(), True)
    far = vvs.departures(vvs.Route("x", lines=["U6"], walk_min=10))[0][0]
    check("same tram, 10 min walk -> already gone", far.catchable(), False)

    print("\ndegrading honestly")

    def boom(u, p):
        raise OSError("Network is unreachable")
    vvs._get = boom
    check("no network -> empty list, named error",
          vvs.departures(vvs.Route("x")), ([], "OSError"))
    vvs._get = lambda u, p: {"version": "11", "locations": []}
    check("reshaped API is reported, not silently empty",
          vvs.departures(vvs.Route("x"))[1], "unexpected response")
    vvs._get = lambda u, p: {"stopEvents": []}
    check("nothing running is NOT an error",
          vvs.departures(vvs.Route("x")), ([], None))

    # ── journeys (A -> B) ──────────────────────────────────────────────
    print("\njourneys")
    vvs._get = lambda url, params: TRIP
    r = vvs.Route("de:08111:6008", to_id="de:08111:2589",
                  label="MAX-PLANCK", walk_min=5)
    js, err = vvs.trips(r)
    check("route knows it is a journey", r.is_trip, True)
    check("no error on a good trip response", err, None)
    check("3 journeys parsed, the legless one dropped", len(js), 3)
    check("direct bus is 0 changes", js[0].changes, 0)
    check("duration from first departure to last arrival",
          js[0].duration_min, 4)
    check("destination is where YOU are going, not the bus terminus",
          js[0].towards, "Max-Planck-Institute")

    multi = js[1]
    check("3 legs, one of them a walk",
          [l.walking for l in multi.legs], [False, True, False])
    check("a walking leg is not an interchange", multi.changes, 1)
    check("'board' names the vehicle, never the walk", multi.line, "S1")
    check("realtime estimate wins over planned",
          multi.planned.strftime("%H:%M"),
          vvs._parse_time("2026-08-15T13:32:00Z").strftime("%H:%M"))
    check("cancelled trip flagged", js[2].cancelled, True)
    check("cancelled journey is never catchable", js[2].catchable(), False)

    print("\njourneys and departures are interchangeable to the screen")
    for name in ("leave_in", "catchable", "in_min"):
        check(f"Journey has {name}()", hasattr(js[0], name), True)
    check("leave_in subtracts the walk here too",
          round(js[1].leave_in()), round(js[1].in_min()) - 5)

    print("\nroute config")
    os.environ.pop("KEA_VVS_ROUTES", None)
    d = vvs.routes_from_env()
    check("unset gives Kea's three defaults", [x.label for x in d],
          ["HAUPTBAHNHOF", "VAIHINGEN", "MAX-PLANCK"])
    check("all three are journeys", all(x.is_trip for x in d), True)
    check("all three start at Universität",
          {x.stop_id for x in d}, {vvs.STOPS["universitaet"]})
    check("empty string means an empty board", vvs.routes_from_env(""), [])
    mixed = vvs.routes_from_env("a>b|J|9 ; c|S|U6|Flug|4")
    check("journey and stop forms can be mixed",
          [x.is_trip for x in mixed], [True, False])
    check("journey walk time parsed from field 3", mixed[0].walk_min, 9)
    check("stop walk time parsed from field 5", mixed[1].walk_min, 4)
    check("garbage entries are skipped, not fatal",
          len(vvs.routes_from_env(">;|||;x>y|OK")), 1)

    print()
    if fails:
        print(f"{len(fails)} failure(s):")
        for f in fails:
            print("  -", f)
        return 1
    print("all good — the departure parser is honest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
