#!/usr/bin/env python3
"""
find_stop.py — look up the VVS stop id for a place, and see what serves it.

Configuring a departure board normally means digging through API docs for
an opaque id like "de:08111:6118". This does it for you:

    python3 tools/find_stop.py "Vaihingen"
    python3 tools/find_stop.py "Hauptbahnhof (tief)" --departures

The first form lists matching stops with their ids. The second also
fetches what is actually leaving in the next while, so you can see the
exact line names and destination spellings to filter on — the strings
Kea needs are the ones the network itself uses, not the ones on the map.

Copy the result into KEA_VVS_ROUTES, e.g.

    KEA_VVS_ROUTES='de:08111:6118|Hbf|U6,U7|Flughafen|7'
                    stop id     label lines  towards  walk minutes
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from backend import vvs                                   # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", help="stop name, e.g. 'Hauptbahnhof'")
    ap.add_argument("--departures", "-d", action="store_true",
                    help="also show what is leaving the best match")
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args()

    stops, err = vvs.find_stop(args.query)
    if err:
        print(f"lookup failed: {err}")
        print("(no network? the VVS endpoint is https://www3.vvs.de)")
        return 1
    if not stops:
        print(f"nothing matched {args.query!r}")
        return 1

    print(f"\nmatches for {args.query!r}:\n")
    for sid, name, kind, quality in stops:
        print(f"  {sid:<22} {name:<44} {kind:<9} {quality}")

    if not args.departures:
        print("\nre-run with --departures to see the lines and destinations")
        return 0

    best = stops[0]
    route = vvs.Route(best[0], label=best[1])
    deps, err = vvs.departures(route, limit=args.limit)
    print(f"\nleaving {best[1]}:\n")
    if err:
        print(f"  departures failed: {err}")
        return 1
    if not deps:
        print("  nothing scheduled right now")
        return 0

    now = vvs._now()
    for d in deps:
        delay = f"+{d.delay_min}" if d.delay_min > 0 else "  "
        flag = " CANCELLED" if d.cancelled else ""
        print(f"  {d.estimated:%H:%M} {delay:>3}  {d.product:<4} "
              f"{d.line:<5} -> {d.towards:<30} "
              f"in {d.in_min(now):4.0f} min  {d.platform}{flag}")

    lines = sorted({d.line for d in deps})
    dests = sorted({d.towards for d in deps})
    print(f"\n  lines here:        {', '.join(lines)}")
    print(f"  destinations:      {', '.join(dests)}")
    print(f"\n  example config:")
    print(f"    KEA_VVS_ROUTES='{best[0]}|{best[1][:12]}|"
          f"{','.join(lines[:2])}|{dests[0][:14]}|5'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
