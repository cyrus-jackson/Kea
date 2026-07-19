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
from states.nexus_state import NexusState, PHASES, WORLDS  # noqa: E402
from states.logbook_state import LogbookState                # noqa: E402
from states.pomodoro_state import PomodoroState            # noqa: E402
from states.notification_state import NotificationState    # noqa: E402

STATES = [AmbientState, ClimateState, TelegraphState, GreetingsState,
          ConservatoryState, OrbitalState, BiolabState, AbyssalState,
          AerodromeState, OrreryState, StarportState, DocketState, LogbookState,
          NexusState, PomodoroState, NotificationState]

failures = []


class FakeManager:
    current_state_name = "smoke"

    def change_state(self, name):
        pass


for cls in STATES:
    try:
        st = cls(FakeManager())
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

# every Nexus card + day phase must point at a state registered in main.py
main_src = open(os.path.join(ROOT, "src", "main.py"), encoding="utf-8").read()
registered = set(re.findall(r"add_state\(\s*['\"]([a-z_]+)['\"]", main_src))
print(f"\nregistered states in main.py: {len(registered)}")

for name in sorted({w[0] for w in WORLDS}):
    if name not in registered:
        failures.append(f"Nexus card '{name}' is not registered in main.py")
        print(f"[FAIL] card -> {name}")
for name in sorted({p[1] for p in PHASES}):
    if name not in registered:
        failures.append(f"Day phase '{name}' is not registered in main.py")
        print(f"[FAIL] phase -> {name}")

if not failures:
    print(f"[PASS] all {len(WORLDS)} cards and {len(PHASES)} phases route correctly")
    print(f"\nall good — {len(STATES)} states healthy.")
    sys.exit(0)

print(f"\n{len(failures)} problem(s):")
for f in failures:
    print("  -", f)
sys.exit(1)
