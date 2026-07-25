"""
console_state.py
----------------
THE CONSOLE — the one screen that adjusts the machine itself.

A service panel from the back of a rack: brushed steel, engraved plate,
a warning stripe, two big calibrated dials with travelling needles, and
a status lamp. Everything else in Kea shows you the world; this shows
you Kea.

    DIAL 1  BRIGHTNESS   10-100 %   panel backlight
    DIAL 2  DWELL         3-120 s   how long each screen is held before
                                    auto-pilot moves on

Controls:
    encoder turn    move the selected dial up / down
    encoder press   next dial (wraps; press on the last returns to Nexus)
    toggle          fine mode — single steps instead of coarse jumps
    UP/DOWN keys    same as the encoder, for desk testing
"""

import math

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from backend import settings

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


# ── Palette: brushed steel, engraved ink, warning amber ─────────────────────
STEEL_HI   = (126, 132, 140)
STEEL      = (92, 98, 106)
STEEL_LO   = (58, 63, 70)
PANEL      = (44, 48, 54)
PANEL_DARK = (30, 33, 38)
ENGRAVE    = (206, 212, 220)
ENGRAVE_LO = (140, 148, 158)
AMBER      = (240, 176, 64)
AMBER_LIT  = (255, 214, 130)
GREEN_LAMP = (120, 226, 140)
RED_STRIPE = (176, 62, 48)
SHADOW     = (18, 20, 24)

DIALS = [
    ("brightness", "BRIGHTNESS", "%", "PANEL BACKLIGHT"),
    ("dwell", "DWELL", "s", "AUTO-PILOT HOLD"),
]


class ConsoleState(State):
    """Service panel: brightness and screen-cycle timing, on the encoder."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.font_title = pygame.font.Font(None, s(30))
        self.font_dial = pygame.font.Font(None, s(22))
        self.font_val = pygame.font.Font(None, s(44))
        self.font_small = pygame.font.Font(None, s(14))
        self.font_tiny = pygame.font.Font(None, s(12))

        self.sel = 0                 # which dial the encoder drives
        self.fine = False            # toggle: single-step mode
        self.t = 0.0
        self.flash = 0.0             # brief highlight after a change
        self.needle = [settings.fraction(d[0]) for d in DIALS]
        self._bg = None

    # ── lifecycle ──────────────────────────────────────────────────────────
    def enter(self):
        self.t = 0.0
        self.flash = 0.0
        self.fine = bool(getattr(self.manager, "toggle_on", False))
        # snap needles to the stored values
        self.needle = [settings.fraction(d[0]) for d in DIALS]

    # ── controls ───────────────────────────────────────────────────────────
    def move_cursor(self, direction):
        """Encoder turn: adjust the selected dial."""
        name = DIALS[self.sel][0]
        step = 1 if self.fine else None
        if step is None:
            settings.adjust(name, direction)
        else:                        # fine: move a single unit, not a step
            settings.set_value(name, settings.get(name) + (1 if direction > 0 else -1))
        self.flash = 0.5
        return True

    def activate(self):
        """Encoder press: next dial; past the last one, go home."""
        self.sel += 1
        if self.sel >= len(DIALS):
            self.sel = 0
            return False             # let main.py return us to Nexus
        self.flash = 0.4
        return True

    def on_toggle(self, on):
        self.fine = on

    def toggle_label(self):
        return "FINE STEP"

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_RIGHT):
                    self.move_cursor(1)
                elif e.key in (pygame.K_DOWN, pygame.K_LEFT):
                    self.move_cursor(-1)
                elif e.key in (pygame.K_TAB, pygame.K_RETURN):
                    self.activate()

    # ── update ─────────────────────────────────────────────────────────────
    def update(self, dt):
        self.t += dt
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt)
        # needles ease toward their targets
        for i, (name, _l, _u, _c) in enumerate(DIALS):
            target = settings.fraction(name)
            self.needle[i] += (target - self.needle[i]) * min(1.0, dt * 9.0)

    # ── drawing ────────────────────────────────────────────────────────────
    def draw(self, surface):
        if self._bg is None or self._bg.get_size() != surface.get_size():
            self._bg = self._make_bg(surface.get_size())
        surface.blit(self._bg, (0, 0))

        w, h = surface.get_size()
        top = s(74)
        gap = s(14)
        dial_h = (h - top - s(58) - gap) // 2
        for i, (name, label, unit, sub) in enumerate(DIALS):
            self._draw_dial(surface, s(14), top + i * (dial_h + gap),
                            w - s(28), dial_h, i, label, unit, sub)
        self._draw_footer(surface)

    # brushed-steel plate, engraved header, warning stripe — drawn once
    def _make_bg(self, size):
        w, h = size
        bg = pygame.Surface(size)
        bg.fill(PANEL)
        # brushed vertical grain
        for x in range(0, w, 2):
            k = 10 + int(8 * math.sin(x * 0.7) + 6 * math.sin(x * 0.13))
            pygame.draw.line(bg, (PANEL[0] + k, PANEL[1] + k, PANEL[2] + k),
                             (x, 0), (x, h))
        # header plate
        head = pygame.Rect(0, 0, w, s(62))
        pygame.draw.rect(bg, STEEL_LO, head)
        pygame.draw.rect(bg, PANEL_DARK, pygame.Rect(0, s(60), w, s(3)))
        for x in range(0, w, 3):     # grain on the plate
            k = 8 + int(7 * math.sin(x * 0.9))
            pygame.draw.line(bg, (STEEL_LO[0] + k, STEEL_LO[1] + k, STEEL_LO[2] + k),
                             (x, 0), (x, s(59)))
        # hazard stripe under the header
        stripe_y = s(63)
        sw = s(9)
        for i in range(-1, w // sw + 2):
            x = i * sw
            pygame.draw.polygon(bg, RED_STRIPE if i % 2 == 0 else PANEL_DARK,
                                [(x, stripe_y), (x + sw, stripe_y),
                                 (x + sw - s(5), stripe_y + s(6)),
                                 (x - s(5), stripe_y + s(6))])
        # engraved title
        title = self.font_title.render("CONSOLE", True, ENGRAVE)
        shade = self.font_title.render("CONSOLE", True, SHADOW)
        bg.blit(shade, (s(15) + 1, s(15) + 1))
        bg.blit(title, (s(15), s(15)))
        sub = self.font_tiny.render("SERVICE PANEL / CALIBRATION", True, ENGRAVE_LO)
        bg.blit(sub, (s(16), s(40)))
        # four corner screws
        for cx, cy in [(s(9), s(9)), (w - s(9), s(9)),
                       (s(9), h - s(9)), (w - s(9), h - s(9))]:
            pygame.draw.circle(bg, STEEL_HI, (cx, cy), s(5))
            pygame.draw.circle(bg, STEEL_LO, (cx, cy), s(5), 1)
            pygame.draw.line(bg, PANEL_DARK, (cx - s(3), cy - s(2)),
                             (cx + s(3), cy + s(2)), 1)
        return bg

    def _draw_dial(self, surf, x, y, w, h, idx, label, unit, sub):
        name = DIALS[idx][0]
        active = (idx == self.sel)
        val = settings.get(name)
        _d, lo, hi, _s = settings.SPEC[name]

        # recessed housing
        box = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surf, PANEL_DARK, box, border_radius=s(5))
        pygame.draw.rect(surf, STEEL_LO, box, 1, border_radius=s(5))
        if active:
            glow = AMBER_LIT if self.flash > 0 else AMBER
            pygame.draw.rect(surf, glow, box, s(2), border_radius=s(5))

        # label + reading
        col = AMBER_LIT if active else ENGRAVE_LO
        surf.blit(self.font_dial.render(label, True, col), (x + s(10), y + s(8)))
        surf.blit(self.font_tiny.render(sub, True, ENGRAVE_LO), (x + s(10), y + s(30)))

        vs = self.font_val.render(str(val), True, AMBER_LIT if active else ENGRAVE)
        surf.blit(vs, (x + w - vs.get_width() - s(26), y + s(10)))
        surf.blit(self.font_small.render(unit, True, ENGRAVE_LO),
                  (x + w - s(22), y + s(24)))

        # calibrated track
        ty = y + h - s(24)
        tx0, tx1 = x + s(12), x + w - s(12)
        pygame.draw.rect(surf, SHADOW, pygame.Rect(tx0, ty, tx1 - tx0, s(7)),
                         border_radius=s(3))
        frac = self.needle[idx]
        fill_w = int((tx1 - tx0) * max(0.0, min(1.0, frac)))
        if fill_w > 0:
            bar = AMBER if active else STEEL
            pygame.draw.rect(surf, bar, pygame.Rect(tx0, ty, fill_w, s(7)),
                             border_radius=s(3))
        # tick marks every 10%
        for i in range(11):
            tx = tx0 + (tx1 - tx0) * i / 10.0
            tall = (i % 5 == 0)
            pygame.draw.line(surf, ENGRAVE_LO if tall else STEEL_LO,
                             (tx, ty + s(9)), (tx, ty + s(14) if tall else ty + s(12)))
        # travelling needle
        nx = tx0 + fill_w
        ncol = AMBER_LIT if active else ENGRAVE_LO
        pygame.draw.polygon(surf, ncol,
                            [(nx, ty - s(4)), (nx - s(4), ty - s(11)),
                             (nx + s(4), ty - s(11))])
        # range end labels
        surf.blit(self.font_tiny.render(str(lo), True, ENGRAVE_LO), (tx0, ty + s(15)))
        hs = self.font_tiny.render(str(hi), True, ENGRAVE_LO)
        surf.blit(hs, (tx1 - hs.get_width(), ty + s(15)))

    def _draw_footer(self, surf):
        w, h = surf.get_size()
        y = h - s(44)
        pygame.draw.line(surf, STEEL_LO, (s(12), y), (w - s(12), y))

        # status lamp: green when the real backlight is under our control
        live = settings.has_backlight()
        lamp = GREEN_LAMP if live else STEEL
        cx, cy = s(22), y + s(17)
        if live:
            halo = pygame.Surface((s(22), s(22)), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*GREEN_LAMP, 60), (s(11), s(11)), s(11))
            surf.blit(halo, (cx - s(11), cy - s(11)))
        pygame.draw.circle(surf, lamp, (cx, cy), s(5))
        pygame.draw.circle(surf, SHADOW, (cx, cy), s(5), 1)
        surf.blit(self.font_tiny.render(
            "BACKLIGHT LIVE" if live else "BACKLIGHT N/A", True, ENGRAVE_LO),
            (cx + s(11), cy - s(6)))

        hint = "TURN: ADJUST   PRESS: NEXT DIAL" + ("   [FINE]" if self.fine else "")
        hs = self.font_tiny.render(hint, True, ENGRAVE_LO)
        surf.blit(hs, (w - hs.get_width() - s(14), cy - s(6)))
