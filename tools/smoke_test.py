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
from states.alert_state import AlertState                  # noqa: E402
from states.alerts_state import AlertsState                # noqa: E402
from states.face_state import FaceState                    # noqa: E402
from states.cyberdeck_state import CyberdeckState          # noqa: E402
from states.drift_state import (DriftState, CIRCUIT, WORLD_NAMES,   # noqa: E402
                                ARRIVALS, PASSAGES, station_for,
                                schedule)

STATES = [AmbientState, ClimateState, TelegraphState, GreetingsState,
          ConservatoryState, OrbitalState, BiolabState, AbyssalState,
          AerodromeState, OrreryState, StarportState, DocketState, LogbookState,
          NexusState, PomodoroState, NotificationState, ConsoleState,
          CameraState, TransitState, AlertState, AlertsState, FaceState, CyberdeckState]

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
    "TransitState": "transit", "AlertState": "dispatch", "AlertsState": "alerts",
    "FaceState": "face",
    "CyberdeckState": "cyberdeck",
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

# Every screen must have usable dynamic range on a dim panel.
#
# Thresholds are measured, not guessed: across all twenty screens the
# dimmest legitimate one (the orrery, a brass wireframe in space) sits at
# 1.10% bright pixels and p99.9 luminance 225. A floor of 0.5% / 170
# clears every real screen with room to spare while still catching a
# whole screen that has gone dark.
#
# What this CANNOT catch is one label going invisible — see the palette
# check below, which can.
try:
    import pygame.surfarray as _sa                                  # noqa: E402
except (ImportError, ModuleNotFoundError):
    _sa = None

MIN_BRIGHT_PCT = 0.5
MIN_P999_LUM = 170

_thin = []
if _sa is not None:
    for _name, _st in sorted(built.items()):
        try:
            surface.fill((0, 0, 0))
            _st.enter()
            for _ in range(6):
                _st.update(1 / 30)
            _st.draw(surface)
            _px = _sa.array3d(surface).astype("float64")
            _lum = (0.299 * _px[:, :, 0] ** 2 + 0.587 * _px[:, :, 1] ** 2
                    + 0.114 * _px[:, :, 2] ** 2) ** 0.5
            _bright = float((_lum > 120).mean()) * 100.0
            _flat = sorted(_lum.flatten())
            _p999 = float(_flat[int(len(_flat) * 0.999)])
            if _bright < MIN_BRIGHT_PCT or _p999 < MIN_P999_LUM:
                _thin.append(f"{_name}: {_bright:.2f}% bright, p99.9 {_p999:.0f}")
                print(f"[FAIL] contrast -> {_name}: {_bright:.2f}% bright, "
                      f"p99.9 {_p999:.0f}")
        except Exception as _e:                                     # noqa: BLE001
            _thin.append(f"{_name}: could not measure ({_e})")
    if _thin:
        failures.extend(_thin)
    else:
        print(f"[PASS] all {len(built)} screens have readable dynamic range")
else:
    print("[SKIP] dynamic range check (numpy not installed)")

# NOTE ON WHAT IS *NOT* TESTED HERE
#
# The bug this retheme actually produced was one label going invisible:
# the Docket drew its title in PAPER, which meant "the light thing you
# write on" before the neon palette and "a dark card" after it, so the
# title rendered dark-on-dark and vanished. The frame check above cannot
# see that — the screen still had a bright green disc and plenty of
# light — and it was found by rendering the screen and looking at it.
#
# Two static checks for it were tried and both removed. Comparing every
# text colour against every background in the file flags the transit
# badge, which correctly draws dark text on a bright neon pill. Flagging
# any constant used as both a filled surface and as text flags twelve
# cases, of which roughly zero are bugs — filling a badge with BRASS_LIT
# and also writing with it on a dark panel is simply normal.
#
# A static check cannot know what is behind a glyph, and a noisy test
# gets ignored, which is worse than no test. So: new screens get looked
# at, and pal.readable() is there to check a pair when you are unsure.

# Every character the screens draw must exist in the font we draw it with.
# pygame renders a missing codepoint as a featureless box, which looks like
# a layout bug and is invisible to any test that only checks positions —
# an arrow in the transit board shipped exactly that way.
_probe = pygame.font.Font(None, 24)


def _renders(ch):
    if _sa is not None:
        return (_sa.array3d(_probe.render(ch, True, (255, 255, 255))).sum()
                != _sa.array3d(_probe.render("\uffff", True, (255, 255, 255))).sum())
    try:
        r_ch = _probe.render(ch, True, (255, 255, 255))
        r_miss = _probe.render("\uffff", True, (255, 255, 255))
        return r_ch.get_buffer().raw != r_miss.get_buffer().raw
    except Exception:
        return True


_lit = re.compile(r'"([^"\n]*)"|\'([^\'\n]*)\'')
_missing = {}
for _fn in sorted(os.listdir(os.path.join(ROOT, "src", "states"))):
    if not _fn.endswith("_state.py"):
        continue
    for _ln in open(os.path.join(ROOT, "src", "states", _fn), encoding="utf-8"):
        _st = _ln.strip()
        if _st.startswith("#") or _st.startswith('"""') or "render(" not in _ln:
            continue
        for _g in _lit.findall(_ln):
            for _s2 in _g:
                for _c in _s2:
                    if ord(_c) > 127 and not _renders(_c):
                        _missing.setdefault(_fn, set()).add(_c)
if _missing:
    for _fn, _cs in _missing.items():
        failures.append(f"{_fn} draws glyphs the font lacks: {sorted(_cs)}")
        print(f"[FAIL] glyphs -> {_fn}: {sorted(_cs)}")
else:
    print("[PASS] every drawn glyph exists in the font")

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

# The rail has to fit on one screen without scrolling — that was the whole
# point of the cut, and it silently regresses the moment a card is added.
#
# This used to assert "no more than two rows", which passed for the wrong
# reason: two rows was a proxy for fitting, never the requirement itself.
# The proxy then blocked a third row that fits perfectly well. Measure the
# thing we actually care about — the last card's bottom edge against the
# section rule underneath it — and let the row count fall out of that.
_rail = built.get("nexus")
if _rail is None:
    failures.append("could not build NexusState to measure the rail")
    print("[FAIL] rail -> no NexusState instance")
else:
    from config import SCREEN_HEIGHT                    # noqa: E402
    _SCALE = SCREEN_HEIGHT / 480.0
    _s = lambda v: max(1, int(v * _SCALE))               # noqa: E731
    _bottom = _rail.rail_bottom()
    _rule = _s(390)                    # section rule above the NOW/NEXT board
    _rows = -(-len(WORLDS) // _rail.cols)
    if _bottom > _rule:
        failures.append(f"Nexus rail runs to y={_bottom}, past the section rule "
                        f"at y={_rule} — {len(WORLDS)} cards no longer fit")
        print(f"[FAIL] rail -> bottom {_bottom} > rule {_rule}")
    else:
        # Every card must also miss the pixel face in the bottom-right —
        # its INFLATED tap area, not just the sprite, because the face is
        # tested for a hit before the cards are and would silently swallow
        # a press meant for a card. Asking _face_rect() rather than
        # rebuilding the coordinates means this tests the real layout.
        _face = _rail._face_rect().inflate(_s(8), _s(8))
        _hit = [WORLDS[i][1] for i in range(len(WORLDS))
                if _rail._card_rect(i).colliderect(_face)]
        if _hit:
            failures.append(f"rail cards overlap Kea's face sprite: {', '.join(_hit)}")
            print(f"[FAIL] rail -> {len(_hit)} cards over the face")
        else:
            print(f"[PASS] rail is {len(WORLDS)} cards in {_rows} rows, "
                  f"bottom y={_bottom} clears the rule at y={_rule} "
                  f"and misses the face")

if not failures:
    print(f"[PASS] all {len(WORLDS)} cards and {len(PHASES)} phases route correctly")
    print(f"\nall good — {len(STATES)} states healthy.")
    sys.exit(0)

print(f"\n{len(failures)} problem(s):")
for f in failures:
    print("  -", f)
sys.exit(1)
