"""
nexus_state.py
--------------
NEXUS — the default home state and the brain of Kea.

Integrates everything: big clock + date, the System Protocol greeting,
live Stuttgart weather, and a rail of the seven worlds as procedural
icon cards. The new idea is DAY PHASES: Nexus recommends a world for
the hour you're in (conservatory at sunrise, neon city for deep work,
weather at lunch, orbital for the afternoon, telegraph at dusk, the lab
in the evening, the abyss after midnight), shown as a NOW / NEXT
transit board — with a rain override that promotes WX.SYS when an
umbrella is coming. Press A (or wire the deck toggle to it) to enable
AUTO-PILOT: Nexus dispatches you to the recommended world after a short
dwell, so the display follows your day on its own.

The blue hardware button still cycles states; every world's key is
printed on its card.
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

# Day phases: (start_hour, state_name, board label) — the full collection
PHASES = [
    (6,  "conservatory", "CONSERVATORY"),
    (9,  "ambient",      "NEON SPRAWL"),
    (12, "climate",      "WX.SYS"),
    (13, "orbital",      "ORBITAL CTRL"),
    (15, "aerodrome",    "AERODROME"),
    (17, "telegraph",    "TELEGRAPH"),
    (19, "biolab",       "BIO-VAT LAB"),
    (21, "starport",     "STARPORT B-94"),
    (23, "abyssal",      "ABYSSAL STN"),
]

# Card rail: every screen in the machine (4 x 3)
WORLDS = [
    ("ambient",      "SPRAWL",  "1", NEON_PINK),
    ("climate",      "WX.SYS",  "8", AMBER),
    ("orbital",      "ORBITAL", "4", PHOSPHOR),
    ("biolab",       "BIO-VAT", "5", TOXIC),
    ("telegraph",    "TELEGRF", "6", BRASS),
    ("conservatory", "GARDEN",  "7", LEAF),
    ("abyssal",      "ABYSSAL", "0", SEAFOAM),
    ("aerodrome",    "AERODRM", "D", (216, 150, 70)),
    ("orrery",       "ORRERY",  "O", (196, 156, 80)),
    ("starport",     "STARPRT", "S", (130, 200, 255)),
    ("docket",       "DOCKET",  "R", (200, 60, 45)),
    ("greetings",    "PROTOCL", "9", (255, 160, 60)),
]

AUTO_DWELL = 15.0     # seconds on the hub before auto-pilot dispatches


def phase_for(hour):
    """Return (index into PHASES) for a given hour."""
    idx = len(PHASES) - 1
    for i, (start, _, _) in enumerate(PHASES):
        if hour >= start:
            idx = i
    if hour < PHASES[0][0]:
        idx = len(PHASES) - 1          # small hours belong to the abyss
    return idx


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

        # cached clock
        self._clock_str = ""
        self._clock_surf = None

        # layout: 4 x 3 rail holding the whole collection
        self.rail_y = s(200)
        self.card_w = (SCREEN_WIDTH - s(16) - s(6) * 3) // 4
        self.card_h = s(56)

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

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_a:
                self.auto_pilot = not self.auto_pilot
                self.dwell = 0.0

    def _recommended(self, now):
        """(state_name, label, until_str, next_label) for the current hour."""
        idx = phase_for(now.hour)
        nxt = PHASES[(idx + 1) % len(PHASES)]
        cur = PHASES[idx]
        # docket override beats everything: overdue reminders demand the board
        if self.reminders.overdue():
            return "docket", f"DOCKET  ·  {len(self.reminders.overdue())} OVERDUE", \
                   "WHEN DONE", cur[2]
        # rain override: if an umbrella is coming, weather takes the NOW slot
        if self.weather and not self.weather.get("error") and \
           self.weather.get("needs_umbrella") and cur[1] != "climate":
            return "climate", "WX.SYS  ·  RAIN OVERRIDE", "AFTER RAIN", cur[2]
        return cur[1], cur[2], f"{nxt[0]:02d}:00", nxt[2]

    def update(self, dt):
        self.time_alive += dt
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
            if self.dwell >= AUTO_DWELL:
                self.dwell = 0.0
                target = self._recommended(datetime.datetime.now())[0]
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

        # ── world rail (4 + 3 cards) ─────────────────────────────────────
        rec_state = self._recommended(now)[0]
        gap = s(6)
        for i, (world, card) in enumerate(zip(WORLDS, self._cards)):
            row, col = divmod(i, 4)
            row_n = min(4, len(WORLDS) - row * 4)
            x0 = (SCREEN_WIDTH - row_n * self.card_w - (row_n - 1) * gap) // 2
            x = x0 + col * (self.card_w + gap)
            y = self.rail_y + row * (self.card_h + s(8))
            surface.blit(card, (x, y))
            if world[0] == rec_state:      # pulse ring on the recommended world
                pulse = 0.5 + 0.5 * math.sin(t * 3.0)
                pygame.draw.rect(surface, lerp_color(CARD_EDGE, world[3], pulse),
                                 (x - 1, y - 1, self.card_w + 2, self.card_h + 2),
                                 2, border_radius=s(6))

        # ── NOW / NEXT transit board ─────────────────────────────────────
        by = s(398)
        _, now_label, until, next_label = self._recommended(now)
        n1 = self.font_board.render(f"NOW   {now_label}", True, TEXT_PALE)
        n2 = self.font_board.render(f"NEXT  {next_label}  ·  {until}", True, TEXT_DIM)
        surface.blit(n1, (s(14), by))
        surface.blit(n2, (s(14), by + s(20)))

        # auto-pilot status + dispatch countdown
        if self.auto_pilot:
            remain = max(0, int(AUTO_DWELL - self.dwell) + 1)
            ap = self.font_board.render(f"AUTO {remain:02d}s", True, PHOSPHOR)
        else:
            ap = self.font_board.render("AUTO OFF · [A]", True, TEXT_DIM)
        surface.blit(ap, (SCREEN_WIDTH - ap.get_width() - s(14), by))
        # rotate between the control hint and the machine's life story
        if int(t / 8) % 2 == 0:
            hint_str = "BLUE BTN CYCLES WORLDS"
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
