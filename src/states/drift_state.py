"""
drift_state.py
--------------
DRIFT — the rounds.

Kea keeps a circuit of eight stations and walks it. That is the whole
idea: the ambient worlds are not places you navigate *to* — there is
nothing to do in them — they are what the machine does when you leave
it alone. So they came off the Nexus rail, where they cost nine cards
and forced a scroll, and became one destination: this one.

The circuit follows the sun, and it is an arc, not a shuffle:

    THE GLASSHOUSE    first light, wet soil          dawn - 30m
    THE ORRERY        brass, the day being wound     dawn + 2.5h
    ORBITAL CONTROL   high noon upstairs             solar noon - 1h
    BAY 94            dust and two setting suns      solar noon + 2h
    THE AERODROME     golden hour, last departure    sunset - 1.5h
    NEON SPRAWL       the city takes over            sunset + 25m
    THE BIO-VAT LAB   everyone's gone, vats awake    22:30
    ABYSSAL STATION   the small hours, deepest point 01:00

Garden to clockwork to orbit to desert to dusk to city to lab to the
deep, and back up into the garden at dawn. Those are *real* solar times,
computed locally (backend/sun.py) — so the glasshouse opens at 07:43 in
December and 04:50 in June, and golden hour at the aerodrome is actually
golden hour. The whole circuit breathes with the year.

Leave Kea alone at dawn and it is in the glasshouse; leave it alone at
3am and it is at the bottom of the ocean. It resumes wherever the sun
says it should be, so the rounds carry on whether or not anyone is
watching.

Passages are not cuts, and deliberately not dissolves either: these
scenes all carry big header text, and cross-fading two of them gives
you ABYSSAL STATION printed through BIO-VAT LAB, which reads as a
broadcast fault rather than a journey. Instead the outgoing station is
held as a still and slid away to reveal the next one already running
underneath — a lit seam travelling with its edge, like a window panning
across. Every pixel belongs to exactly one world at any instant, so
nothing is ever unreadable, and it costs one extra render per passage
rather than two live scenes per frame.

A field note rides in underneath naming where you came from and where
you are, so consecutive worlds read as one round rather than eight
unrelated screensavers.

    ENCODER turn    walk the circuit by hand
    ENCODER press   leave the rounds, back to Nexus
    TOGGLE          HOLD — stay at this station, stop advancing
"""

import datetime
import os
import random

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


# ── the circuit ─────────────────────────────────────────────────────────────
# (state name, board label, anchor, accent)
#
# An anchor says when a station takes over, and the daylight half of the
# round is pinned to the actual sun rather than to the clock:
#
#   ("sunrise", h)  h hours from real first light
#   ("noon",    h)  from real solar noon
#   ("sunset",  h)  from real sunset
#   ("clock",   h)  a plain wall-clock hour
#
# This is the difference between a circuit that *claims* to follow the sun
# and one that does. Fixed hours put "golden hour" at 17:00 in December,
# by which time it has been dark in Stuttgart for half an hour. The night
# stations stay on the clock, because nothing about 22:30 in a lab is
# astronomical.
CIRCUIT = [
    ("conservatory", "THE GLASSHOUSE",  ("sunrise", -0.5), (110, 190,  90)),
    ("orrery",       "THE ORRERY",      ("sunrise",  2.5), (196, 156,  80)),
    ("orbital",      "ORBITAL CONTROL", ("noon",    -1.0), ( 92, 240, 150)),
    ("starport",     "BAY 94",          ("noon",     2.0), (130, 200, 255)),
    ("aerodrome",    "THE AERODROME",   ("sunset",  -1.5), (216, 150,  70)),
    ("ambient",      "NEON SPRAWL",     ("sunset",   0.4), (255,  70, 170)),
    ("biolab",       "THE BIO-VAT LAB", ("clock",   22.5), (120, 230, 100)),
    ("abyssal",      "ABYSSAL STATION", ("clock",    1.0), (110, 220, 210)),
]

WORLD_NAMES = [c[0] for c in CIRCUIT]

# Used when the sun cannot be computed at all — a polar latitude, or a
# clock so wrong the maths degenerates. The old fixed schedule: never
# beautiful, always valid.
FALLBACK = [5.0, 8.0, 11.0, 14.0, 17.0, 20.0, 22.5, 1.0]

# How long a station is held before the rounds move on. Long by design:
# these scenes have slow events in them (the leviathan, the recultured
# batch, the freighter landing) and cutting away every 15 s means you
# never see one finish.
try:
    HOLD = max(10.0, float(os.getenv("KEA_DRIFT_HOLD", "90")))
except ValueError:
    HOLD = 90.0

PASSAGE = 1.25       # seconds of passage
NOTE_HOLD = 4.5      # how long the field note stays readable
NOTE_FADE = 0.9

INK = (232, 234, 240)
INK_DIM = (128, 132, 146)
SHADOW = (8, 8, 12)

_sched_cache = {}


def schedule(date=None):
    """[(start_hour, name, label, accent)] for one day, in circuit order.

    Solar anchors drift through the year, and on a short enough day they
    can cross: "golden hour" falls before "early afternoon" once daylight
    drops under about seven hours. Stuttgart only gets to 8.3 h at the
    solstice, so it never quite happens here — but if it did, a naive
    implementation would silently drop a station for the day.

    So the computed moments are sorted and handed back out *in circuit
    order*. The narrative sequence — garden, clockwork, orbit, desert,
    dusk, city, lab, deep — is preserved by construction no matter what
    the sun is doing, and every station always gets its slot.
    """
    date = date or datetime.date.today()
    if date in _sched_cache:
        return _sched_cache[date]

    sr = nn = ss = None
    try:
        from backend import sun
        h = sun.hours(date)
        if h:
            sr, nn, ss = h
    except Exception:
        pass                     # no sun module, or polar: fall back below

    raw = []
    for i, (_n, _l, (kind, off), _a) in enumerate(CIRCUIT):
        if kind == "clock":
            raw.append(off % 24.0)
        elif sr is None:
            raw.append(FALLBACK[i])
        else:
            raw.append(({"sunrise": sr, "noon": nn, "sunset": ss}[kind]
                        + off) % 24.0)

    # measure every start from the first station, so the day's frame
    # begins at dawn and the small hours land at the end where they belong
    base = raw[0]
    offsets = sorted((r - base) % 24.0 for r in raw)
    out = [((base + o) % 24.0, CIRCUIT[i][0], CIRCUIT[i][1], CIRCUIT[i][3])
           for i, o in enumerate(offsets)]

    if len(_sched_cache) > 4:
        _sched_cache.clear()
    _sched_cache[date] = out
    return out


def station_for(when=None):
    """Index of the station that owns a given moment."""
    when = when or datetime.datetime.now()
    if isinstance(when, (int, float)):          # a bare hour still works
        hour, date = float(when), datetime.date.today()
    elif isinstance(when, datetime.datetime):
        hour, date = when.hour + when.minute / 60.0, when.date()
    else:                                        # a date: assume midday
        hour, date = 12.0, when

    sched = schedule(date)
    idx, best = len(sched) - 1, -1.0
    for i, (start, _n, _l, _a) in enumerate(sched):
        if start <= hour and start > best:
            idx, best = i, start
    if best < 0:
        return len(sched) - 1        # before the first start: last night's
    return idx


def hhmm(hour):
    """A float hour as HH:MM, for the transit board."""
    m = int(round(hour * 60)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


# ── field notes ─────────────────────────────────────────────────────────────
# What Kea says on arriving. Not flavour for its own sake: it is the thread
# that makes eight unrelated scenes read as one continuous round.
ARRIVALS = {
    "conservatory": [
        "first light through the panes. the vines have moved again.",
        "warm glass, wet soil. everything here grew overnight.",
        "the sprinklers just stopped. steam coming off the beds.",
    ],
    "orrery": [
        "brass and patience. the planets kept turning while i was away.",
        "the gearwork runs a half-degree fast. good enough.",
        "wound, oiled, level. the sky in miniature, behaving.",
    ],
    "orbital": [
        "the scope is warm. three contacts since the last pass.",
        "high noon upstairs. everything where the charts say.",
        "sweep, ping, log. the quiet part of the shift.",
    ],
    "starport": [
        "dust on everything. the freighter is still venting.",
        "two suns down, pad lights chasing. nobody waiting on us.",
        "heat coming off the apron in sheets.",
    ],
    "aerodrome": [
        "golden hour. the evening airship is right on the boards.",
        "banner overhead, engine note dropping. last departure.",
        "deco sun going down behind the ziggurats.",
    ],
    "ambient": [
        "the city took over while i wasn't looking.",
        "rain on the water, so the signs are in it twice.",
        "the sprawl is awake now. it does this every night.",
    ],
    "biolab": [
        "everyone has gone home. the vats are still awake.",
        "batch is holding. something in tank three moved.",
        "hum of the glass. the specimens don't sleep either.",
    ],
    "abyssal": [
        "pressure steady. nothing down here but snow and patience.",
        "the lure went past the window again.",
        "deepest part of the round. the water keeps its own hours.",
    ],
}

# The eight passages the circuit actually makes, in order. These fire far
# more often than any other pair, so they get written rather than generic.
PASSAGES = {
    ("conservatory", "orrery"):     "out of the wet warmth, into brass.",
    ("orrery", "orbital"):          "from the model to the real thing.",
    ("orbital", "starport"):        "down the gravity well, into the dust.",
    ("starport", "aerodrome"):      "one dusk traded for another, lower and warmer.",
    ("aerodrome", "ambient"):       "the sun finishes going down and the signs come on.",
    ("ambient", "biolab"):          "off the street, through the airlock. quieter here.",
    ("biolab", "abyssal"):          "glass to glass — but this window holds back an ocean.",
    ("abyssal", "conservatory"):    "up out of the dark. the glasshouse has the sun already.",
}


class DriftState(State):
    """Hosts the ambient worlds and walks between them.

    It does not own the scenes — it borrows the instances already
    registered on the manager, so nothing is built twice and drift costs
    no extra memory over the old arrangement.
    """

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()
        self.font_label = pygame.font.Font(None, s(21))
        self.font_from = pygame.font.Font(None, s(13))
        self.font_note = pygame.font.Font(None, s(15))

        self.i = 0                  # index into CIRCUIT
        self.held = 0.0             # time at this station
        self.hold_here = False      # toggle: stop advancing
        self.trans = PASSAGE + 1.0  # time since the last passage began
        self.note_t = 999.0
        self.note = ""
        self.came_from = ""
        self.snap = None            # still of the station we just left
        self._pending = None         # station a desk key asked us to open at
        self._rng = random.Random()

    # ── the borrowed scene ─────────────────────────────────────────────────
    def _world(self, idx=None):
        name = CIRCUIT[self.i if idx is None else idx][0]
        return self.manager.states.get(name)

    # ── lifecycle ──────────────────────────────────────────────────────────
    def open_at(self, name):
        """Begin the rounds at a named station instead of the hour's one.

        Called before change_state('drift') by the desk shortcuts, so the
        old per-world keys still work — they just park the rounds there
        rather than stranding you in a world with no way onward.
        """
        if name in WORLD_NAMES:
            self._pending = WORLD_NAMES.index(name)

    def enter(self):
        """Resume the rounds wherever the hour says they should be."""
        self.i = self._pending if self._pending is not None \
            else station_for(datetime.datetime.now().hour)
        self._pending = None
        self.held = 0.0
        self.hold_here = bool(getattr(self.manager, "toggle_on", False))
        self.came_from = ""
        w = self._world()
        if w:
            w.enter()
        self._arrive()
        # arriving on the rounds comes up out of black rather than cutting
        self.snap = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.snap.fill((0, 0, 0))

    def exit(self):
        w = self._world()
        if w:
            w.exit()
        self.snap = None            # don't hold a screen-sized surface idle

    def _arrive(self):
        """Set the field note for the station we just reached."""
        key = (self.came_from, CIRCUIT[self.i][0])
        if key in PASSAGES:
            self.note = PASSAGES[key]
        else:
            self.note = self._rng.choice(ARRIVALS[CIRCUIT[self.i][0]])
        self.note_t = 0.0
        self.trans = 0.0

    def _go(self, step):
        """Walk to the next station. The outgoing scene is stopped, not
        left running in the background — only one world is ever live."""
        old = self._world()
        self.came_from = CIRCUIT[self.i][0]
        if old:
            # one last frame of the station we are leaving, to fade over the
            # next one. main.py clears the canvas before every draw, so the
            # still has to be taken deliberately — but it costs a single
            # extra render per passage, not per frame.
            try:
                snap = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                old.draw(snap)
                self.snap = snap
            except Exception:
                self.snap = None
            old.exit()
        self.i = (self.i + step) % len(CIRCUIT)
        new = self._world()
        if new:
            new.enter()
            # the lever means the same thing wherever it is
            if hasattr(new, "on_toggle"):
                try:
                    new.on_toggle(bool(getattr(self.manager, "toggle_on", False)))
                except Exception:
                    pass
        self.held = 0.0
        self._arrive()

    # ── controls ───────────────────────────────────────────────────────────
    def move_cursor(self, direction):
        """Encoder: walk the circuit by hand."""
        self._go(1 if direction > 0 else -1)
        return True

    def activate(self):
        return False                # press = leave the rounds, go home

    def on_toggle(self, on):
        self.hold_here = on
        self.held = 0.0

    def toggle_label(self):
        return "HOLD STATION"

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RIGHT, pygame.K_DOWN):
                    self.move_cursor(1)
                elif e.key in (pygame.K_LEFT, pygame.K_UP):
                    self.move_cursor(-1)

    # ── update ─────────────────────────────────────────────────────────────
    def update(self, dt):
        self.trans += dt
        self.note_t += dt
        w = self._world()
        if w:
            w.update(dt)            # only the live station ticks
        if self.hold_here:
            return
        self.held += dt
        if self.held >= HOLD:
            self._go(1)

    # ── drawing ────────────────────────────────────────────────────────────
    def draw(self, surface):
        w = self._world()
        if w:
            w.draw(surface)
        else:                        # a world failed to register: don't die
            surface.fill((10, 10, 16))

        if self.snap is not None:
            if self.trans >= PASSAGE:
                self.snap = None     # passage over, release the surface
            else:
                k = self.trans / PASSAGE                  # 0 -> 1
                ease = 1.0 - (1.0 - k) ** 3               # leaves, then settles
                w_, h_ = surface.get_size()
                x = -int(w_ * ease)
                surface.blit(self.snap, (x, 0))
                # the seam: a lit edge travelling with the departing station,
                # so the move reads as deliberate rather than as a glitch
                accent = CIRCUIT[self.i][3]
                edge = x + w_
                if 0 <= edge <= w_:
                    glow = pygame.Surface((s(14), h_), pygame.SRCALPHA)
                    for gx in range(s(14)):
                        a = int(90 * (1.0 - gx / float(s(14))))
                        pygame.draw.line(glow, (*accent, a), (gx, 0), (gx, h_))
                    surface.blit(glow, (edge, 0))
                    pygame.draw.line(surface, accent, (edge - 1, 0), (edge - 1, h_), 2)

        self._draw_note(surface)

    def _draw_note(self, surface):
        """From / station / field note, stacked above the reserved strip.

        Kept clear of the bottom ~28 px, which belongs to the toggle chip
        and the Pomodoro badge — see docs/UI_GUIDELINES.md.
        """
        if self.note_t > NOTE_HOLD + NOTE_FADE:
            return
        if self.note_t < NOTE_HOLD:
            a = min(1.0, self.note_t / 0.45)          # ease in
        else:
            a = 1.0 - (self.note_t - NOTE_HOLD) / NOTE_FADE
        a = max(0.0, min(1.0, a))
        if a <= 0.01:
            return

        w, h = surface.get_size()
        _n, label, _hr, accent = CIRCUIT[self.i]
        x = s(14)
        bottom = h - s(34)                            # above the strip

        lines = []
        if self.came_from:
            prev = next((c[1] for c in CIRCUIT if c[0] == self.came_from), "")
            if prev:
                lines.append((self.font_from, f"FROM  {prev}", INK_DIM))
        lines.append((self.font_label, label, accent))
        lines.append((self.font_note, self.note, INK))

        rendered = [(f.render(t, True, c), c) for f, t, c in lines]
        total = sum(r.get_height() for r, _ in rendered) + s(3) * (len(rendered) - 1)
        y = bottom - total

        # a soft plate so the note stays legible over a bright scene
        pad = s(7)
        wide = max(r.get_width() for r, _ in rendered)
        plate = pygame.Surface((wide + pad * 2, total + pad * 2), pygame.SRCALPHA)
        plate.fill((*SHADOW, int(215 * a)))
        surface.blit(plate, (x - pad, y - pad))
        bar = pygame.Surface((s(2), total + pad * 2), pygame.SRCALPHA)
        bar.fill((*accent, int(220 * a)))
        surface.blit(bar, (x - pad, y - pad))

        for r, _c in rendered:
            r.set_alpha(int(255 * a))
            surface.blit(r, (x, y))
            y += r.get_height() + s(3)

    def draw_pomodoro(self, surface, time_left, mode):
        """Let the live station draw the timer in its own idiom."""
        w = self._world()
        if w:
            w.draw_pomodoro(surface, time_left, mode)
