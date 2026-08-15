#!/usr/bin/env python3
"""
smoke_test.py — headless check that every screen still works.

Constructs each state, runs it, draws a frame and its pomodoro overlay,
then verifies that every Nexus card and every Day Phase points at a
state that is actually registered in main.py. Catches broken worlds and
dead links without a display attached.

    python3 tools/smoke_test.py

Exit code 0 = all good.
"""

import os
import re
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("KEA_SCREEN_WIDTH", "320")
os.environ.setdefault("KEA_SCREEN_HEIGHT", "480")
os.environ.setdefault("KEA_FEEDS", "0")          # no network during tests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame                                     # noqa: E402
pygame.init()
pygame.display.set_mode((320, 480))
surface = pygame.display.get_surface()

from states.ambient_state import AmbientState              # noqa: E402
from states.climate_state import ClimateState              # noqa: E402
from states.telegraph_state import TelegraphState          # noqa: E402
from states.greetings_state import GreetingsState          # noqa: E402
from states.conservatory_state import ConservatoryState    # noqa: E402
from states.orbital_state import OrbitalState              # noqa: E402
from states.biolab_state import BiolabState                # noqa: E402
from states.abyssal_state import AbyssalState              # noqa: E402
from states.aerodrome_state import AerodromeState          # noqa: E402
from states.orrery_state import OrreryState                # noqa: E402
from states.starport_state import StarportState            # noqa: E402
from states.docket_state import DocketState                # noqa: E402
from states.nexus_state import NexusState, phases, WORLDS  # noqa: E402
from states.logbook_state import LogbookState                # noqa: E402
from states.pomodoro_state import PomodoroState            # noqa: E402
from states.notification_state import NotificationState    # noqa: E402
from states.console_state import ConsoleState              # noqa: E402
from states.camera_state import CameraState                # noqa: E402
from states.transit_state import TransitState              # noqa: E402
from states.drift_state import (DriftState, CIRCUIT, WORLD_NAMES,   # noqa: E402
                                ARRIVALS, PASSAGES, station_for,
                                schedule)

STATES = [AmbientState, ClimateState, TelegraphState, GreetingsState,
          ConservatoryState, OrbitalState, BiolabState, AbyssalState,
          AerodromeState, OrreryState, StarportState, DocketState, LogbookState,
          NexusState, PomodoroState, NotificationState, ConsoleState,
          CameraState, TransitState]

failures = []


class FakeManager:
    current_state_name = "smoke"
    toggle_on = False

    def __init__(self):
        self.states = {}

    def change_state(self, name):
        pass


built = {}          # name -> instance, so drift can borrow real worlds
NAME_OF = {
    "AmbientState": "ambient", "ClimateState": "climate",
    "TelegraphState": "telegraph", "GreetingsState": "greetings",
    "ConservatoryState": "conservatory", "OrbitalState": "orbital",
    "BiolabState": "biolab", "AbyssalState": "abyssal",
    "AerodromeState": "aerodrome", "OrreryState": "orrery",
    "StarportState": "starport", "DocketState": "docket",
    "LogbookState": "logbook", "NexusState": "nexus",
    "PomodoroState": "pomodoro", "NotificationState": "notification",
    "ConsoleState": "console", "CameraState": "camera",
    "TransitState": "transit",
}

for cls in STATES:
    try:
        st = cls(FakeManager())
        built[NAME_OF.get(cls.__name__, cls.__name__)] = st
        st.enter()                                 # states may rely on it
        for _ in range(20):
            st.update(1 / 30)
        st.draw(surface)
        st.draw_pomodoro(surface, 754, "work")
        st.draw_pomodoro(surface, 120, "break")
        print(f"[PASS] {cls.__name__}")
    except Exception as exc:                       # noqa: BLE001
        failures.append(f"{cls.__name__}: {type(exc).__name__}: {exc}")
        print(f"[FAIL] {cls.__name__}: {exc}")

# ── DRIFT: the rounds, hosting the borrowed worlds ─────────────────────────
try:
    dm = FakeManager()
    dm.states = built
    drift = DriftState(dm)
    drift.enter()
    for _ in range(20):
        drift.update(1 / 30)
    drift.draw(surface)
    drift.draw_pomodoro(surface, 754, "work")
    # walk the entire circuit, forwards then back, drawing each passage
    for step in (1, -1):
        for _ in range(len(CIRCUIT)):
            drift.move_cursor(step)
            for _ in range(4):
                drift.update(1 / 30)
                drift.draw(surface)
    drift.exit()
    print("[PASS] DriftState (walked all "
          f"{len(CIRCUIT)} stations both ways)")
except Exception as exc:                           # noqa: BLE001
    failures.append(f"DriftState: {type(exc).__name__}: {exc}")
    print(f"[FAIL] DriftState: {exc}")

# the circuit's story data must be complete — a missing arrival line would
# only show up as a KeyError hours into a drift nobody is watching
for _n, _l, _h, _a in CIRCUIT:
    if _n not in ARRIVALS or not ARRIVALS[_n]:
        failures.append(f"station '{_n}' has no arrival field notes")
        print(f"[FAIL] arrivals -> {_n}")
for a, b in PASSAGES:
    if a not in WORLD_NAMES or b not in WORLD_NAMES:
        failures.append(f"passage ({a} -> {b}) names a station not on the circuit")
        print(f"[FAIL] passage -> {a} -> {b}")

# every hour of the day must land on exactly one station
_covered = {station_for(float(h)) for h in range(24)}
if len(_covered) != len(CIRCUIT):
    missing = [CIRCUIT[i][0] for i in range(len(CIRCUIT)) if i not in _covered]
    failures.append(f"stations never reached by the clock: {missing}")
    print(f"[FAIL] hours -> {missing}")
else:
    print(f"[PASS] all 24 hours map onto all {len(CIRCUIT)} stations")

# every Nexus card + day phase must point at a state registered in main.py
main_src = open(os.path.join(ROOT, "src", "main.py"), encoding="utf-8").read()
registered = set(re.findall(r"add_state\(\s*['\"]([a-z_]+)['\"]", main_src))
print(f"\nregistered states in main.py: {len(registered)}")

for name in sorted({w[0] for w in WORLDS}):
    if name not in registered:
        failures.append(f"Nexus card '{name}' is not registered in main.py")
        print(f"[FAIL] card -> {name}")
PHASES = phases()
for name in sorted({p[1] for p in PHASES}):
    if name not in registered:
        failures.append(f"Day phase '{name}' is not registered in main.py")
        print(f"[FAIL] phase -> {name}")
for name in WORLD_NAMES:
    if name not in registered:
        failures.append(f"Drift station '{name}' is not registered in main.py")
        print(f"[FAIL] station -> {name}")

# the rail has to fit on one screen without scrolling — that was the whole
# point of the cut, and it silently regresses the moment a card is added
_cols, _rows = 5, -(-len(WORLDS) // 5)
if _rows > 2:
    failures.append(f"Nexus rail is {_rows} rows ({len(WORLDS)} cards) — it scrolls again")
    print(f"[FAIL] rail -> {_rows} rows")
else:
    print(f"[PASS] rail is {len(WORLDS)} cards in {_rows} rows")

if not failures:
    print(f"[PASS] all {len(WORLDS)} cards and {len(PHASES)} phases route correctly")
    print(f"\nall good — {len(STATES)} states healthy.")
    sys.exit(0)

print(f"\n{len(failures)} problem(s):")
for f in failures:
    print("  -", f)
sys.exit(1)
