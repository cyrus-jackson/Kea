"""
nexus_state.py
--------------
NEXUS — the default home state and the brain of Kea.

Integrates everything: big clock + date, the System Protocol greeting,
live Stuttgart weather, and a rail of instrument cards.

The rail carries INSTRUMENTS ONLY — the nine screens you actually press
for a reason. It used to carry all sixteen, five across, which is four
rows you have to scroll through, and nine of those cards were ambient
worlds: beautiful, but there is nothing to *do* in a city or a fish
tank, so nobody navigates to them. Those eight now live behind one card
(DRIFT) and mostly arrive on their own — see states/drift_state.py.

DAY PHASES still drive the NOW / NEXT transit board, and they are now
literally the drift circuit, so the board tells you where Kea will be
when you stop touching it: the glasshouse at dawn, the abyss at 3am.
A rain override promotes WX.SYS when an umbrella is coming, and overdue
reminders promote the DOCKET over everything.

Press A (or the deck toggle) for AUTO-PILOT: Nexus hands you to the
rounds after a short dwell.

The blue hardware button still cycles states; every card prints its key.
"""

import pygame
import math
import random
import datetime

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from backend.weather_api import fetch_stuttgart_weather
from backend.reminders import ReminderService
from backend import lifebook
from system_protocol import SystemProtocol
from ui.glow_text import GlowText
from ui import pixel_art
from states.drift_state import (WORLD_NAMES, schedule as drift_schedule,
                                station_for as _station_for, hhmm)

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


# ── Palette: neutral dark chassis with every punk's accent ──────────────────
BG_TOP     = (10, 10, 18)
BG_BOT     = (16, 12, 22)
GRID       = (24, 22, 34)
BRASS      = (150, 118, 56)
NEON_CYAN  = (0, 225, 245)
NEON_PINK  = (255, 70, 170)
AMBER      = (255, 176, 44)
LEAF       = (110, 190, 90)
TOXIC      = (120, 230, 100)
PHOSPHOR   = (92, 240, 150)
SEAFOAM    = (110, 220, 210)
TEXT_PALE  = (225, 228, 235)
TEXT_DIM   = (120, 124, 140)
CARD_BG    = (18, 18, 28)
CARD_EDGE  = (52, 52, 72)

# The rounds. Kea's day phases ARE the drift circuit — one source of
# truth, so the NOW / NEXT board describes exactly where the machine will
# be when you leave it alone. The times are solar and therefore change
# daily, so this is a function rather than a table: see drift_state.py.
def phases(date=None):
    return [(start, name, label) for start, name, label, _a
            in drift_schedule(date)]

# The rail: instruments only — the things you press for a reason. It used
# to carry all sixteen screens at 5 across, which is four rows and a
# scroll. The nine ambient worlds were nine of those cards and none of
# them is a place you go: there is nothing to do in a city or a fish tank.
# They live behind DRIFT now, one card, and mostly arrive by themselves.
WORLDS = [
    # Focus is a first-class destination on the hub.  There is no dedicated
    # hardware shortcut for it: choose it the same deliberate way as every
    # other instrument.
    ("pomodoro",  "FOCUS",   "DIAL", (228, 174, 86)),
    ("drift",     "DRIFT",   "W", (150, 170, 255)),
    # ALERTS is deliberately NOT on the rail: it is reached by pressing
    # on the DOCKET. Overview then detail is the right hierarchy, and an
    # eleventh card would push the rail to three rows and reintroduce the
    # scroll the whole cut was about.
    ("docket",    "DOCKET",  "R", (200, 60, 45)),
    ("transit",   "TRANSIT", "V", (250, 186, 60)),
    ("climate",   "WX.SYS",  "8", AMBER),
    ("greetings", "PROTOCL", "9", (255, 160, 60)),
    ("telegraph", "TELEGRF", "6", BRASS),
    ("logbook",   "LOGBOOK", "L", (172, 136, 68)),
    ("camera",    "CAMERA",  "K", (176, 138, 66)),
    ("console",   "CONSOLE", "C", (240, 176, 64)),
]

# Screens that stay OFF the cycle: reachable from this hub (and by their
# key / dedicated button), but never landed on by the blue button, the
# encoder dial or auto-pilot.
#   console — settings shouldn't interrupt you at random
#   camera  — entering it powers up the sensor (~1 s) and exiting stops it
#             again, so cycling through would spin the camera all day. It
#             has button 5 (pin 7) to itself.
#   worlds  — the eight ambient scenes are still registered (drift borrows
#             the instances) but they are no longer destinations. You reach
#             them through DRIFT or by leaving Kea alone.
NO_CYCLE = {"console", "camera"} | set(WORLD_NAMES)

# The dial/button cycle: every world except those.
def cycle_worlds():
    return [w for w in WORLDS if w[0] not in NO_CYCLE]


def station_index_now():
    """Which of the eight stations the rounds are at right now — the DRIFT
    card lights that dot, so the hub shows where Kea would go."""
    return _station_for(datetime.datetime.now())


AUTO_DWELL = 15.0     # fallback; the live value is the CONSOLE's "dwell" dial


def _dwell():
    """Seconds before auto-pilot dispatches — tunable on the Console."""
    try:
        from backend import settings
        return float(settings.get("dwell"))
    except Exception:
        return AUTO_DWELL


def phase_for(when=None):
    """Index of the phase that owns a moment. Delegates to the circuit."""
    return _station_for(when)


class NexusState(State):
    """Home hub: clock, protocol greeting, weather, world rail, day phases."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.protocol = SystemProtocol()

        try:
            self.font_clock = pygame.font.SysFont("monospace", s(54), bold=True)
        except Exception:
            self.font_clock = pygame.font.Font(None, s(60))
        self.font_date  = pygame.font.Font(None, s(19))
        self.font_label = pygame.font.Font(None, s(15))
        self.font_board = pygame.font.Font(None, s(20))
        self.font_greet = pygame.font.Font(None, s(20))

        # single-line greeting; long lines marquee instead of truncating
        self.greeting = GlowText(self.font_greet, self.protocol.next_message(),
                                 (255, 200, 120), (255, 120, 20), glow_radius=2)
        self.greet_timer = 0.0
        self.greet_scroll = 0.0
        self.greet_hold = 2.0

        # weather + reminders
        self.weather = None
        self.weather_timer = 1e9           # force fetch on enter
        self.reminders = ReminderService.instance()
        self.time_alive = 0.0

        # auto-pilot
        self.auto_pilot = False
        self.dwell = 0.0

        # encoder cursor: -1 until the knob is touched, so the rail stays
        # clean until you actually reach for it
        self.cursor = -1
        self.cursor_seen = 0.0

        # cached clock
        self._clock_str = ""
        self._clock_surf = None

        # layout: 5 across — nine instruments, two rows, no scrolling
        self.cols = 5
        self.rail_y = s(200)
        self.card_w = (SCREEN_WIDTH - s(16) - s(5) * (self.cols - 1)) // self.cols
        self.card_h = s(56)

        self._drift_station = station_index_now()
        self._bg = self._build_background()
        self._cards = [self._build_card(w) for w in WORLDS]

    # ══════════════════════════════════════════════════════════════════════
    # Pre-rendered layers
    # ══════════════════════════════════════════════════════════════════════
    def _build_background(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / max(1, SCREEN_HEIGHT - 1)
            pygame.draw.line(surf, lerp_color(BG_TOP, BG_BOT, t), (0, y), (SCREEN_WIDTH, y))
        for gx in range(0, SCREEN_WIDTH, s(24)):        # faint blueprint grid
            pygame.draw.line(surf, GRID, (gx, 0), (gx, SCREEN_HEIGHT))
        for gy in range(0, SCREEN_HEIGHT, s(24)):
            pygame.draw.line(surf, GRID, (0, gy), (SCREEN_WIDTH, gy))
        # brass corner brackets — a nod to every machine in the collection
        m, l = s(6), s(16)
        for cx, cy, dx, dy in [(m, m, 1, 1), (SCREEN_WIDTH - m, m, -1, 1),
                               (m, SCREEN_HEIGHT - m, 1, -1),
                               (SCREEN_WIDTH - m, SCREEN_HEIGHT - m, -1, -1)]:
            pygame.draw.line(surf, BRASS, (cx, cy), (cx + dx * l, cy), 2)
            pygame.draw.line(surf, BRASS, (cx, cy), (cx, cy + dy * l), 2)
        # section rules: framing the world rail
        for yy in (s(192), s(390)):
            pygame.draw.line(surf, CARD_EDGE, (s(10), yy), (SCREEN_WIDTH - s(10), yy))
        title = self.font_label.render("K E A  //  N E X U S", True, TEXT_DIM)
        surf.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, s(6)))
        return surf

    def _build_card(self, world):
        """A world card with a tiny procedural icon of that punk."""
        state, label, key, accent = world
        card = pygame.Surface((self.card_w, self.card_h), pygame.SRCALPHA)
        pygame.draw.rect(card, CARD_BG, card.get_rect(), border_radius=s(5))
        pygame.draw.rect(card, CARD_EDGE, card.get_rect(), 1, border_radius=s(5))
        cx, cy = self.card_w // 2, s(17)
        dim = lerp_color(accent, CARD_BG, 0.35)

        if state == "ambient":            # three towers + a moon
            for i, (bx, bh) in enumerate([(-10, 14), (0, 22), (10, 17)]):
                pygame.draw.rect(card, dim, (cx + s(bx) - s(3), cy + s(14) - s(bh),
                                             s(6), s(bh)))
            pygame.draw.circle(card, accent, (cx + s(11), cy - s(9)), s(4))
        elif state == "transit":          # a split-flap cell mid-flip
            pygame.draw.rect(card, dim, (cx - s(11), cy - s(8), s(22), s(16)),
                             border_radius=s(2))
            pygame.draw.rect(card, accent, (cx - s(11), cy - s(8), s(22), s(16)),
                             1, border_radius=s(2))
            pygame.draw.line(card, CARD_BG, (cx - s(11), cy), (cx + s(11), cy), 1)
            pygame.draw.rect(card, accent, (cx - s(11), cy, s(22), s(4)))
        elif state == "drift":            # the circuit: eight stops, one lit
            import math as _m
            pygame.draw.circle(card, dim, (cx, cy), s(11), 1)
            live = station_index_now()
            for i in range(8):
                a = -_m.pi / 2 + i * _m.pi / 4
                px, py = cx + int(s(11) * _m.cos(a)), cy + int(s(11) * _m.sin(a))
                if i == live:
                    pygame.draw.circle(card, accent, (px, py), s(3))
                else:
                    pygame.draw.circle(card, dim, (px, py), s(2))
        elif state == "orbital":          # scope + sweep
            pygame.draw.circle(card, dim, (cx, cy), s(13), 1)
            pygame.draw.circle(card, dim, (cx, cy), s(7), 1)
            pygame.draw.line(card, accent, (cx, cy),
                             (cx + s(11), cy - s(7)), 2)
            pygame.draw.circle(card, accent, (cx - s(5), cy + s(4)), s(1))
        elif state == "biolab":           # vat + bubbles
            pygame.draw.rect(card, dim, (cx - s(7), cy - s(11), s(14), s(24)),
                             1, border_radius=s(4))
            pygame.draw.circle(card, accent, (cx, cy + s(3)), s(4))
            for by in (-4, -8):
                pygame.draw.circle(card, dim, (cx + s(4), cy + s(by)), s(1), 1)
        elif state == "telegraph":        # gear
            for k in range(8):
                a = k * math.tau / 8
                pygame.draw.line(card, dim,
                                 (cx + math.cos(a) * s(9), cy + math.sin(a) * s(9)),
                                 (cx + math.cos(a) * s(13), cy + math.sin(a) * s(13)), 3)
            pygame.draw.circle(card, accent, (cx, cy), s(9), 2)
            pygame.draw.circle(card, dim, (cx, cy), s(3))
        elif state == "conservatory":     # stem + leaves
            pygame.draw.line(card, accent, (cx, cy + s(13)), (cx - s(2), cy - s(11)), 2)
            for ly, d in ((2, 1), (-3, -1), (-8, 1)):
                pygame.draw.circle(card, dim, (cx + d * s(6), cy + s(ly)), s(3))
        elif state == "climate":          # synthwave sun
            pygame.draw.circle(card, accent, (cx, cy - s(2)), s(9))
            for i in range(3):
                pygame.draw.line(card, CARD_BG, (cx - s(10), cy + s(1) + i * s(3)),
                                 (cx + s(10), cy + s(1) + i * s(3)), 2)
            pygame.draw.line(card, dim, (cx - s(13), cy + s(11)),
                             (cx + s(13), cy + s(11)), 1)
        elif state == "aerodrome":        # zeppelin
            hullr = pygame.Rect(0, 0, s(24), s(10))
            hullr.center = (cx, cy - s(2))
            pygame.draw.ellipse(card, dim, hullr)
            pygame.draw.ellipse(card, accent, hullr, 1)
            pygame.draw.polygon(card, dim, [(cx - s(12), cy - s(2)),
                                            (cx - s(17), cy - s(7)),
                                            (cx - s(15), cy - s(1))])
            pygame.draw.rect(card, accent, (cx - s(3), cy + s(4), s(6), s(3)))
        elif state == "starport":         # twin suns over the horizon
            pygame.draw.circle(card, accent, (cx + s(3), cy - s(2)), s(7))
            pygame.draw.circle(card, dim, (cx - s(7), cy - s(6)), s(4))
            pygame.draw.line(card, dim, (cx - s(13), cy + s(7)),
                             (cx + s(13), cy + s(7)), 2)
            pygame.draw.line(card, accent, (cx - s(6), cy + s(11)),
                             (cx + s(6), cy + s(11)), 1)
        elif state == "pomodoro":         # hourglass
            pygame.draw.polygon(card, dim, [(cx - s(8), cy - s(10)),
                                            (cx + s(8), cy - s(10)),
                                            (cx, cy)])
            pygame.draw.polygon(card, accent, [(cx, cy),
                                               (cx + s(8), cy + s(10)),
                                               (cx - s(8), cy + s(10))])
            for by in (cy - s(12), cy + s(10)):
                pygame.draw.rect(card, dim, (cx - s(10), by, s(20), s(2)))
        elif state == "logbook":          # open ledger
            pygame.draw.rect(card, dim, (cx - s(11), cy - s(8), s(22), s(17)), 1)
            pygame.draw.line(card, accent, (cx, cy - s(8)), (cx, cy + s(9)), 1)
            for ly in (cy - s(4), cy, cy + s(4)):
                pygame.draw.line(card, dim, (cx - s(8), ly), (cx - s(2), ly), 1)
                pygame.draw.line(card, dim, (cx + s(2), ly), (cx + s(8), ly), 1)
        elif state == "docket":           # filed card + stamp
            pygame.draw.rect(card, dim, (cx - s(9), cy - s(9), s(18), s(20)), 1,
                             border_radius=s(2))
            pygame.draw.line(card, dim, (cx - s(6), cy - s(4)), (cx + s(6), cy - s(4)), 1)
            pygame.draw.circle(card, accent, (cx + s(3), cy + s(4)), s(4), 1)
        elif state == "orrery":           # tilted orbit + planet on its arm
            r = pygame.Rect(0, 0, s(26), s(12))
            r.center = (cx, cy)
            pygame.draw.ellipse(card, dim, r, 1)
            pygame.draw.circle(card, accent, (cx, cy), s(2))
            pygame.draw.line(card, dim, (cx, cy), (cx + s(10), cy + s(4)), 1)
            pygame.draw.circle(card, accent, (cx + s(10), cy + s(4)), s(3))
        elif state == "abyssal":          # waves + fish
            for wy in (-4, 2):
                pts = [(cx - s(13) + i * s(4),
                        cy + s(wy) + (s(2) if i % 2 else 0)) for i in range(8)]
                pygame.draw.lines(card, dim, False, pts, 1)
            pygame.draw.polygon(card, accent,
                                [(cx + s(6), cy + s(9)), (cx - s(2), cy + s(6)),
                                 (cx - s(2), cy + s(12))])

        lab = self.font_label.render(label, True, TEXT_PALE)
        card.blit(lab, ((self.card_w - lab.get_width()) // 2, self.card_h - s(24)))
        keyt = self.font_label.render(f"[{key}]", True, TEXT_DIM)
        card.blit(keyt, ((self.card_w - keyt.get_width()) // 2, self.card_h - s(13)))
        return card

    # ══════════════════════════════════════════════════════════════════════
    # State interface
    # ══════════════════════════════════════════════════════════════════════
    def enter(self):
        self.dwell = 0.0
        if self.weather_timer > 1800:      # refresh at most every 30 min
            self.weather_timer = 0.0
            fetch_stuttgart_weather(self._on_weather)

    def _on_weather(self, data):
        self.weather = data

    def on_toggle(self, on):
        """Toggle: the auto-pilot lever."""
        self.auto_pilot = on
        self.dwell = 0.0

    def toggle_label(self):
        return "AUTO-PILOT"

    def _card_rect(self, index):
        """The on-screen bounds of a rail card, shared by drawing and taps."""
        row, col = divmod(index, self.cols)
        row_n = min(self.cols, len(WORLDS) - row * self.cols)
        gap = s(5)
        x0 = (SCREEN_WIDTH - row_n * self.card_w - (row_n - 1) * gap) // 2
        return pygame.Rect(x0 + col * (self.card_w + gap),
                           self.rail_y + row * (self.card_h + s(8)),
                           self.card_w, self.card_h)

    def move_cursor(self, delta):
        """Encoder turned: walk the world rail."""
        from backend import voice
        if self.cursor < 0:
            # First turn honours its direction.  Previously a left turn
            # inexplicably selected the first card, making wrap-around feel
            # broken.
            self.cursor = 0 if delta > 0 else len(WORLDS) - 1
        else:
            self.cursor = (self.cursor + delta) % len(WORLDS)
        self.cursor_seen = self.time_alive
        self.dwell = 0.0                         # you're driving now
        voice.say("blip")
        return WORLDS[self.cursor][0]

    def activate(self):
        """Encoder pressed: enter the highlighted world."""
        if 0 <= self.cursor < len(WORLDS):
            self.manager.change_state(WORLDS[self.cursor][0])
            return True
        return False

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_a:
                self.auto_pilot = not self.auto_pilot
                self.dwell = 0.0
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                for i in range(len(WORLDS)):
                    if self._card_rect(i).collidepoint(event.pos):
                        self.cursor = i
                        self.cursor_seen = self.time_alive
                        self.activate()
                        break

    def _recommended(self, now):
        """(state_name, label, until_str, next_label) for right now.

        The times come from the live solar schedule, so NEXT shows the
        real moment the rounds move on — 20:40 tonight, 16:29 in
        December — not a rounded-off fixed hour.
        """
        sched = drift_schedule(now.date())
        idx = _station_for(now)
        cur = sched[idx]
        nxt = sched[(idx + 1) % len(sched)]
        # docket override beats everything: overdue reminders demand the board
        if self.reminders.overdue():
            return "docket", f"DOCKET  ·  {len(self.reminders.overdue())} OVERDUE", \
                   "WHEN DONE", cur[2]
        # rain override: if an umbrella is coming, weather takes the NOW slot
        if self.weather and not self.weather.get("error") and \
           self.weather.get("needs_umbrella") and cur[1] != "climate":
            return "climate", "WX.SYS  ·  RAIN OVERRIDE", "AFTER RAIN", cur[2]
        return cur[1], cur[2], hhmm(nxt[0]), nxt[2]

    def update(self, dt):
        self.time_alive += dt
        # the DRIFT card's lit dot follows the rounds; rebuilt only when the
        # station actually changes, so it costs nothing per frame
        st = station_index_now()
        if st != self._drift_station:
            self._drift_station = st
            for i, wd in enumerate(WORLDS):
                if wd[0] == "drift":
                    self._cards[i] = self._build_card(wd)
        self.weather_timer += dt
        self.greet_timer += dt
        self.reminders.update(dt)          # keep the docket feed warm
        if self.greet_timer >= 90.0:       # fresh protocol line every 90 s
            self.greet_timer = 0.0
            self.greeting.update_text(self.protocol.next_message())
            self.greet_scroll = 0.0
            self.greet_hold = 2.0

        # marquee for greetings wider than the screen
        gw = self.greeting.get_surface().get_width()
        if gw > SCREEN_WIDTH - s(24):
            if self.greet_hold > 0:
                self.greet_hold -= dt
            else:
                self.greet_scroll += s(26) * dt
                if self.greet_scroll > gw + s(40):
                    self.greet_scroll = 0.0
                    self.greet_hold = 2.0

        if self.auto_pilot:
            self.dwell += dt
            if self.dwell >= _dwell():
                self.dwell = 0.0
                target = self._recommended(datetime.datetime.now())[0]
                # an ambient station means "start the rounds"; drift resumes
                # at the right hour by itself. Overrides (docket / rain) are
                # real screens and still go straight there.
                if target in WORLD_NAMES:
                    target = "drift"
                if self.manager.current_state_name != target:
                    self.manager.change_state(target)

    # ══════════════════════════════════════════════════════════════════════
    # Draw
    # ══════════════════════════════════════════════════════════════════════
    def draw(self, surface):
        surface.blit(self._bg, (0, 0))
        now = datetime.datetime.now()
        t = self.time_alive

        # ── clock + date ─────────────────────────────────────────────────
        clock_str = now.strftime("%H:%M")
        if clock_str != self._clock_str:
            self._clock_str = clock_str
            self._clock_surf = self.font_clock.render(clock_str, True, TEXT_PALE)
        surface.blit(self._clock_surf,
                     ((SCREEN_WIDTH - self._clock_surf.get_width()) // 2, s(26)))
        # blinking colon seconds hint
        if now.second % 2 == 0:
            pygame.draw.circle(surface, NEON_CYAN,
                               (SCREEN_WIDTH // 2 + self._clock_surf.get_width() // 2 + s(8),
                                s(26) + self._clock_surf.get_height() // 2), s(2))
        date_str = now.strftime("%A  ·  %d %B  ·  DAY %j").upper()
        ds = self.font_date.render(date_str, True, TEXT_DIM)
        surface.blit(ds, ((SCREEN_WIDTH - ds.get_width()) // 2, s(82)))

        # docket badge: open reminders, red when something is overdue
        n_open = self.reminders.count()
        if n_open:
            urgent = bool(self.reminders.overdue())
            bcol = (200, 60, 45) if urgent else AMBER
            btxt = self.font_label.render(f"DOCKET {n_open}", True, (245, 240, 230))
            brect = pygame.Rect(s(10), s(26), btxt.get_width() + s(12), s(17))
            if not urgent or int(t * 2) % 2 == 0:
                pygame.draw.rect(surface, bcol, brect, border_radius=s(4))
                surface.blit(btxt, (brect.x + s(6), brect.y + s(3)))

        # ── protocol greeting (marquee when long) ────────────────────────
        gs = self.greeting.get_surface()
        gy = s(102)
        if gs.get_width() <= SCREEN_WIDTH - s(24):
            surface.blit(gs, ((SCREEN_WIDTH - gs.get_width()) // 2, gy))
        else:
            prev_clip = surface.get_clip()
            surface.set_clip(pygame.Rect(s(12), gy, SCREEN_WIDTH - s(24),
                                         gs.get_height()))
            x0 = s(12) - int(self.greet_scroll)
            surface.blit(gs, (x0, gy))
            surface.blit(gs, (x0 + gs.get_width() + s(40), gy))
            surface.set_clip(prev_clip)

        # ── weather chip ─────────────────────────────────────────────────
        wy = s(142)
        if self.weather is None:
            wtxt = self.font_board.render("SYNCING WEATHER LINK...", True, TEXT_DIM)
            surface.blit(wtxt, ((SCREEN_WIDTH - wtxt.get_width()) // 2, wy))
        elif self.weather.get("error"):
            wtxt = self.font_board.render("WEATHER LINK ERROR", True, NEON_PINK)
            surface.blit(wtxt, ((SCREEN_WIDTH - wtxt.get_width()) // 2, wy))
        else:
            temp = self.weather.get("temp", "?")
            rain = self.weather.get("rain_chance", 0)
            umb = "UMBRELLA" if self.weather.get("needs_umbrella") else "DRY RUN"
            col = AMBER if not self.weather.get("needs_umbrella") else NEON_CYAN
            wtxt = self.font_board.render(
                f"STUTTGART  {temp}°C   RAIN {rain}%   {umb}", True, col)
            surface.blit(wtxt, ((SCREEN_WIDTH - wtxt.get_width()) // 2, wy))
            # rain probability bar
            bar_w = int(SCREEN_WIDTH * 0.6)
            bx = (SCREEN_WIDTH - bar_w) // 2
            pygame.draw.rect(surface, CARD_EDGE, (bx, wy + s(22), bar_w, s(4)), 1)
            fill = int(bar_w * min(100, rain) / 100)
            if fill > 2:
                pygame.draw.rect(surface, col, (bx + 1, wy + s(23), fill - 2, s(4) - 2))

        # ── instrument rail ──────────────────────────────────────────────
        rec_state = self._recommended(now)[0]
        if rec_state in WORLD_NAMES:
            rec_state = "drift"        # the rounds are the recommendation
        for i, (world, card) in enumerate(zip(WORLDS, self._cards)):
            card_rect = self._card_rect(i)
            x, y = card_rect.topleft
            surface.blit(card, (x, y))
            if world[0] == rec_state:      # pulse ring on the recommended world
                pulse = 0.5 + 0.5 * math.sin(t * 3.0)
                pygame.draw.rect(surface, lerp_color(CARD_EDGE, world[3], pulse),
                                 (x - 1, y - 1, self.card_w + 2, self.card_h + 2),
                                 2, border_radius=s(6))
            if i == self.cursor:           # the encoder's selection
                sel = pygame.Rect(x - s(3), y - s(3),
                                  self.card_w + s(6), self.card_h + s(6))
                pygame.draw.rect(surface, TEXT_PALE, sel, 2, border_radius=s(7))
                for cxp, cyp in ((sel.left, sel.top), (sel.right, sel.top),
                                 (sel.left, sel.bottom), (sel.right, sel.bottom)):
                    pygame.draw.circle(surface, world[3], (cxp, cyp), s(2))

        # Kea itself, sitting on the hub: alert when something is overdue,
        # dozing on auto-pilot, otherwise idling with the odd blink.
        try:
            overdue = bool(self.reminders.overdue())
        except Exception:
            overdue = False
        face = (pixel_art.SPRITES["kea_alert"] if overdue
                else pixel_art.SPRITES["kea_sleep"] if self.auto_pilot
                else pixel_art.KEA_IDLE.at(self.time_alive))
        fp = max(2, int(2 * SCALE))
        fw, fh = face.size(fp)
        pixel_art.draw(surface, face, SCREEN_WIDTH - fw - s(12), s(380) - fh, fp)

        # ── NOW / NEXT transit board ─────────────────────────────────────
        by = s(398)
        _, now_label, until, next_label = self._recommended(now)
        n1 = self.font_board.render(f"NOW   {now_label}", True, TEXT_PALE)
        n2 = self.font_board.render(f"NEXT  {next_label}  ·  {until}", True, TEXT_DIM)
        surface.blit(n1, (s(14), by))
        surface.blit(n2, (s(14), by + s(20)))

        # auto-pilot status + dispatch countdown
        if self.auto_pilot:
            remain = max(0, int(_dwell() - self.dwell) + 1)
            ap = self.font_board.render(f"AUTO {remain:02d}s", True, PHOSPHOR)
        else:
            ap = self.font_board.render("AUTO OFF · [A]", True, TEXT_DIM)
        surface.blit(ap, (SCREEN_WIDTH - ap.get_width() - s(14), by))
        # rotate between the control hint and the machine's life story
        if 0 <= self.cursor < len(WORLDS) and t - self.cursor_seen < 6.0:
            hint_str = f"PRESS DIAL TO ENTER {WORLDS[self.cursor][1]}"
        elif int(t / 8) % 2 == 0:
            hint_str = "DIAL BROWSES  ·  PRESS ENTERS"
        else:
            hint_str = (f"GEN {lifebook.get('conservatory_gen', 1):02d} · "
                        f"BATCH {lifebook.get('biolab_batch', 1):02d} · "
                        f"{lifebook.get('pomodoros', 0)} FOCUS · "
                        f"{lifebook.get('chars_tx', 0)} TX · "
                        f"BOOT {lifebook.get('boots', 0)}")
        hint = self.font_label.render(hint_str, True, TEXT_DIM)
        surface.blit(hint, ((SCREEN_WIDTH - hint.get_width()) // 2, by + s(40)))

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = NEON_PINK if mode == "work" else PHOSPHOR
        txt = self.font_board.render(f"{mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(12), s(24)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, CARD_BG, box, border_radius=s(4))
        pygame.draw.rect(surface, c, box, 1, border_radius=s(4))
        surface.blit(txt, rect)
