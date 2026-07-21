"""
orbital_state.py
----------------
ATOMPUNK ORBITAL CONTROL — 1950s retro-futurist mission control.

Cream, teal and atomic orange. A big phosphor radar scope tracks
satellites on baked orbit rings; the sweep decays behind itself and
satellites ping bright when it passes them. Every half minute or so a
little rocket launches across the scope. Below: blinking console lamps,
self-flipping toggle switches, a mission clock, and the current System
Protocol dispatch on a punch-card ticker.

All chrome (bezel, panels, scope background) is pre-rendered; the
per-frame path is the sweep lines, a few dots and cached text.
"""

import pygame
import random
import math
import datetime

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from current_affairs import CurrentAffairs

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ── Atomic-age palette ───────────────────────────────────────────────────────
CREAM       = (238, 228, 205)
CREAM_DARK  = (206, 192, 164)
TEAL        = ( 32,  94,  94)
TEAL_DARK   = ( 18,  60,  60)
CHASSIS     = ( 36,  30,  26)
ATOMIC_RED  = (214,  72,  48)
MUSTARD     = (224, 168,  64)
MINT        = (140, 212, 180)
CHROME      = (196, 200, 200)
INK         = ( 52,  44,  38)
PHOSPHOR    = ( 92, 255, 150)
SCOPE_BG    = (  8,  26,  14)
SCOPE_DIM   = ( 22,  60,  34)
LAMP_COLORS = [ATOMIC_RED, MINT, MUSTARD, (120, 180, 220)]


class OrbitalState(State):
    """Atompunk radar scope + mission-control console."""

    SWEEP_SPEED = 1.1          # rad/s
    TRAIL_STEPS = 18

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.current_affairs = CurrentAffairs()

        self.font_title = pygame.font.Font(None, s(26))
        self.font_sub   = pygame.font.Font(None, s(15))
        self.font_label = pygame.font.Font(None, s(15))
        try:
            self.font_clock = pygame.font.SysFont("monospace", s(22), bold=True)
        except Exception:
            self.font_clock = pygame.font.Font(None, s(24))
        self.font_tick  = pygame.font.Font(None, s(17))

        # scope geometry
        self.cx, self.cy = SCREEN_WIDTH // 2, s(212)
        self.radius = s(122)

        # satellites: ellipse orbits around the center Earth
        self.sats = []
        for i in range(3):
            self.sats.append({
                "a": self.radius * random.uniform(0.42, 0.8),
                "b": self.radius * random.uniform(0.28, 0.58),
                "speed": random.uniform(0.15, 0.4) * random.choice([1, -1]),
                "theta": random.uniform(0, math.tau),
                "ping": 0.0,
            })

        self.sweep = 0.0
        self.time_alive = 0.0

        # rocket launch event
        self.rocket = None                 # {t, dur, x0, y0, x1, y1}
        self.rocket_timer = random.uniform(8.0, 18.0)

        # console lamps + switches
        self.lamps = [{"phase": random.uniform(0, math.tau),
                       "speed": random.uniform(0.6, 2.2),
                       "color": random.choice(LAMP_COLORS)} for _ in range(8)]
        self.switches = [random.random() < 0.5 for _ in range(3)]
        self.switch_timer = random.uniform(4.0, 9.0)

        # ticker
        self.tick_text = self.current_affairs.get_current_message()
        self._tick_surf = self.font_tick.render(self.tick_text, True, MUSTARD)
        self.tick_scroll = 0.0
        self.tick_hold = 2.0

        # cached clock text
        self._clock_str = ""
        self._clock_surf = None

        self._frame_surf = self._build_frame()
        self._scope_bg = self._build_scope_bg()

    # ══════════════════════════════════════════════════════════════════════
    # Pre-rendered chrome
    # ══════════════════════════════════════════════════════════════════════
    def _starburst(self, surf, x, y, r, color):
        for k in range(8):
            a = k * math.pi / 4
            rr = r if k % 2 == 0 else r * 0.45
            pygame.draw.line(surf, color, (x, y),
                             (x + math.cos(a) * rr, y + math.sin(a) * rr), 1)

    def _build_frame(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(CHASSIS)
        # faint chassis texture
        rng = random.Random(5)
        for _ in range(300):
            x, y = rng.randint(0, SCREEN_WIDTH - 1), rng.randint(0, SCREEN_HEIGHT - 1)
            surf.set_at((x, y), (42, 35, 30))

        # ── header plate ────────────────────────────────────────────────
        plate = pygame.Rect(s(8), s(8), SCREEN_WIDTH - s(16), s(52))
        pygame.draw.rect(surf, CREAM, plate, border_radius=s(8))
        pygame.draw.rect(surf, CREAM_DARK, plate, 2, border_radius=s(8))
        pygame.draw.line(surf, CHROME, (plate.x + s(6), plate.bottom - s(6)),
                         (plate.right - s(6), plate.bottom - s(6)), 2)
        title = self.font_title.render("ORBITAL CONTROL", True, INK)
        surf.blit(title, (plate.centerx - title.get_width() // 2 + s(12), plate.y + s(9)))
        sub = self.font_sub.render("KEA ATOMIC RESEARCH DIV.", True, TEAL)
        surf.blit(sub, (plate.centerx - sub.get_width() // 2 + s(12), plate.y + s(30)))
        self._starburst(surf, plate.right - s(20), plate.y + s(16), s(8), ATOMIC_RED)
        self._starburst(surf, plate.right - s(30), plate.y + s(34), s(5), MUSTARD)
        # atomic logo spot (electrons drawn per frame around it)
        self.logo_pos = (plate.x + s(24), plate.centery)
        pygame.draw.circle(surf, ATOMIC_RED, self.logo_pos, s(4))

        # ── scope bezel ─────────────────────────────────────────────────
        pygame.draw.circle(surf, CREAM, (self.cx, self.cy), self.radius + s(12))
        pygame.draw.circle(surf, CREAM_DARK, (self.cx, self.cy), self.radius + s(12), 2)
        pygame.draw.circle(surf, TEAL_DARK, (self.cx, self.cy), self.radius + s(4))
        for k in range(12):                      # bezel tick marks + screws
            a = k * math.tau / 12
            x1 = self.cx + math.cos(a) * (self.radius + s(5))
            y1 = self.cy + math.sin(a) * (self.radius + s(5))
            x2 = self.cx + math.cos(a) * (self.radius + s(10))
            y2 = self.cy + math.sin(a) * (self.radius + s(10))
            pygame.draw.line(surf, INK, (x1, y1), (x2, y2), 2)
        for a in (0.7, 2.4, 4.0, 5.6):
            pygame.draw.circle(surf, CHROME,
                               (int(self.cx + math.cos(a) * (self.radius + s(12))),
                                int(self.cy + math.sin(a) * (self.radius + s(12)))), s(2))

        # ── console panel ───────────────────────────────────────────────
        panel = pygame.Rect(s(8), self.cy + self.radius + s(18),
                            SCREEN_WIDTH - s(16),
                            SCREEN_HEIGHT - (self.cy + self.radius + s(26)))
        self.panel_rect = panel
        pygame.draw.rect(surf, TEAL, panel, border_radius=s(8))
        pygame.draw.rect(surf, TEAL_DARK, panel, 2, border_radius=s(8))
        # lamp bay labels
        lab = self.font_label.render("SYS", True, CREAM)
        surf.blit(lab, (panel.x + s(10), panel.y + s(6)))
        lab = self.font_label.render("MISSION CLOCK", True, CREAM)
        surf.blit(lab, (panel.x + s(10), panel.y + s(40)))
        # switch plates
        for i in range(3):
            px = panel.right - s(28) - i * s(26)
            pygame.draw.rect(surf, CREAM, (px - s(7), panel.y + s(38), s(14), s(30)),
                             border_radius=s(3))
        # ticker slot
        slot = pygame.Rect(panel.x + s(8), panel.bottom - s(26),
                           panel.w - s(16), s(18))
        self.tick_slot = slot
        pygame.draw.rect(surf, CHASSIS, slot, border_radius=s(3))
        # punch-card holes along the slot edges
        for hx in range(slot.x + s(6), slot.right - s(4), s(10)):
            pygame.draw.rect(surf, TEAL_DARK, (hx, slot.y - s(3), s(3), s(2)))
            pygame.draw.rect(surf, TEAL_DARK, (hx, slot.bottom + 1, s(3), s(2)))
        return surf

    def _build_scope_bg(self):
        size = self.radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        c = self.radius
        pygame.draw.circle(surf, SCOPE_BG, (c, c), self.radius)  # round CRT glass
        # range rings + crosshair (kept inside the disc)
        for rr in (0.33, 0.66, 0.98):
            pygame.draw.circle(surf, SCOPE_DIM, (c, c), int(self.radius * rr), 1)
        pygame.draw.line(surf, SCOPE_DIM, (c, s(2)), (c, size - s(2)), 1)
        pygame.draw.line(surf, SCOPE_DIM, (s(2), c), (size - s(2), c), 1)
        # baked orbit ellipses
        for sat in self.sats:
            rect = pygame.Rect(0, 0, int(sat["a"] * 2), int(sat["b"] * 2))
            rect.center = (c, c)
            pygame.draw.ellipse(surf, SCOPE_DIM, rect, 1)
        # Earth at center with little landmasses
        pygame.draw.circle(surf, (30, 90, 60), (c, c), s(16))
        rng = random.Random(2)
        for _ in range(5):
            bx = c + rng.randint(-s(10), s(10))
            by = c + rng.randint(-s(10), s(10))
            pygame.draw.circle(surf, (60, 140, 80), (bx, by), rng.randint(2, s(5)))
        pygame.draw.circle(surf, PHOSPHOR, (c, c), s(16), 1)
        return surf

    # ══════════════════════════════════════════════════════════════════════
    # Update
    # ══════════════════════════════════════════════════════════════════════
    def on_toggle(self, on):
        """Toggle: long-range sweep — the scope reaches further out."""
        self.SWEEP_SPEED = 2.4 if on else 1.1

    def toggle_label(self):
        return "FAST SWEEP"

    def update(self, dt):
        self.time_alive += dt
        self.sweep = (self.sweep + self.SWEEP_SPEED * dt) % math.tau

        for sat in self.sats:
            sat["theta"] += sat["speed"] * dt
            # ping when the sweep passes the satellite's bearing
            sx = math.cos(sat["theta"]) * sat["a"]
            sy = math.sin(sat["theta"]) * sat["b"]
            bearing = math.atan2(sy, sx) % math.tau
            diff = abs((bearing - self.sweep + math.pi) % math.tau - math.pi)
            if diff < 0.06:
                sat["ping"] = 1.0
            sat["ping"] = max(0.0, sat["ping"] - dt * 0.8)

        # rocket launches
        if self.rocket is None:
            self.rocket_timer -= dt
            if self.rocket_timer <= 0:
                a0 = random.uniform(0, math.tau)
                a1 = a0 + math.pi + random.uniform(-0.7, 0.7)
                r = self.radius - s(6)
                self.rocket = {
                    "t": 0.0, "dur": random.uniform(2.6, 3.6),
                    "x0": math.cos(a0) * r, "y0": math.sin(a0) * r,
                    "x1": math.cos(a1) * r, "y1": math.sin(a1) * r,
                }
        else:
            self.rocket["t"] += dt
            if self.rocket["t"] >= self.rocket["dur"]:
                self.rocket = None
                self.rocket_timer = random.uniform(16.0, 40.0)

        # console switches flip themselves now and then
        self.switch_timer -= dt
        if self.switch_timer <= 0:
            self.switch_timer = random.uniform(4.0, 9.0)
            self.switches[random.randrange(len(self.switches))] ^= True

        # ticker
        if self.current_affairs.update(dt):
            self.tick_text = self.current_affairs.get_current_message()
            self._tick_surf = self.font_tick.render(self.tick_text, True, MUSTARD)
            self.tick_scroll = 0.0
            self.tick_hold = 2.0
        if self._tick_surf.get_width() > self.tick_slot.w - s(8):
            if self.tick_hold > 0:
                self.tick_hold -= dt
            else:
                self.tick_scroll += s(24) * dt
                if self.tick_scroll > self._tick_surf.get_width() + s(40):
                    self.tick_scroll = 0.0
                    self.tick_hold = 2.0

    # ══════════════════════════════════════════════════════════════════════
    # Draw
    # ══════════════════════════════════════════════════════════════════════
    def draw(self, surface):
        surface.blit(self._frame_surf, (0, 0))
        cx, cy, r = self.cx, self.cy, self.radius

        # scope background (baked)
        surface.blit(self._scope_bg, (cx - r, cy - r))

        # sweep with phosphor decay
        for k in range(self.TRAIL_STEPS, -1, -1):
            a = self.sweep - k * 0.045
            t = k / self.TRAIL_STEPS
            col = lerp_color(PHOSPHOR, SCOPE_BG, t ** 0.6)
            pygame.draw.line(surface, col, (cx, cy),
                             (cx + math.cos(a) * (r - 2), cy + math.sin(a) * (r - 2)),
                             1 if k else 2)

        # satellites + pings
        for sat in self.sats:
            sx = cx + math.cos(sat["theta"]) * sat["a"]
            sy = cy + math.sin(sat["theta"]) * sat["b"]
            p = sat["ping"]
            col = lerp_color(SCOPE_DIM, PHOSPHOR, 0.35 + 0.65 * p)
            pygame.draw.circle(surface, col, (int(sx), int(sy)), s(3))
            if p > 0.4:
                ring_r = int(s(4) + (1.0 - p) * s(12))
                if math.hypot(sx - cx, sy - cy) + ring_r < r - 2:
                    pygame.draw.circle(surface, lerp_color(SCOPE_BG, PHOSPHOR, p),
                                       (int(sx), int(sy)), ring_r, 1)

        # rocket crossing the scope
        if self.rocket:
            rk = self.rocket
            t = rk["t"] / rk["dur"]
            x = cx + rk["x0"] + (rk["x1"] - rk["x0"]) * t
            y = cy + rk["y0"] + (rk["y1"] - rk["y0"]) * t
            if math.hypot(x - cx, y - cy) < r - s(4):
                ang = math.atan2(rk["y1"] - rk["y0"], rk["x1"] - rk["x0"])
                nose = (x + math.cos(ang) * s(6), y + math.sin(ang) * s(6))
                left = (x + math.cos(ang + 2.6) * s(4), y + math.sin(ang + 2.6) * s(4))
                right = (x + math.cos(ang - 2.6) * s(4), y + math.sin(ang - 2.6) * s(4))
                pygame.draw.polygon(surface, CREAM, [nose, left, right])
                for fk in range(3):                     # flame trail
                    fx = x - math.cos(ang) * (s(7) + fk * s(5))
                    fy = y - math.sin(ang) * (s(7) + fk * s(5))
                    if math.hypot(fx - cx, fy - cy) < r - s(4):
                        fcol = [ATOMIC_RED, MUSTARD, SCOPE_DIM][fk]
                        pygame.draw.circle(surface, fcol, (int(fx), int(fy)), max(1, s(3) - fk))

        # spinning atomic logo electrons (header)
        lx, ly = self.logo_pos
        for k in range(3):
            a = self.time_alive * 1.6 + k * math.tau / 3
            ex = lx + math.cos(a) * s(11)
            ey = ly + math.sin(a) * s(6) * math.cos(a * 0.7 + k)
            pygame.draw.circle(surface, TEAL, (int(ex), int(ey)), s(2))
        pygame.draw.circle(surface, CREAM_DARK, (lx, ly), s(13), 1)

        # ── console: lamps, clock, switches, ticker ─────────────────────
        panel = self.panel_rect
        for i, lamp in enumerate(self.lamps):
            b = 0.5 + 0.5 * math.sin(self.time_alive * lamp["speed"] + lamp["phase"])
            col = lerp_color(TEAL_DARK, lamp["color"], 0.25 + 0.75 * b)
            lx0 = panel.x + s(38) + i * s(24)
            pygame.draw.circle(surface, col, (lx0, panel.y + s(12)), s(5))
            pygame.draw.circle(surface, CHASSIS, (lx0, panel.y + s(12)), s(5), 1)

        now = datetime.datetime.now()
        clock_str = now.strftime("%H:%M:%S")
        if clock_str != self._clock_str:
            self._clock_str = clock_str
            self._clock_surf = self.font_clock.render(clock_str, True, MUSTARD)
        surface.blit(self._clock_surf, (panel.x + s(10), panel.y + s(54)))
        day = self.font_label.render(f"DAY {now.timetuple().tm_yday}", True, CREAM)
        surface.blit(day, (panel.x + s(122), panel.y + s(60)))

        for i, up in enumerate(self.switches):
            px = panel.right - s(28) - i * s(26)
            base_y = panel.y + s(53)
            tip = base_y - s(9) if up else base_y + s(9)
            pygame.draw.line(surface, INK, (px, base_y), (px, tip), s(4))
            pygame.draw.circle(surface, ATOMIC_RED if up else CHROME, (px, tip), s(3))

        # ticker (marquee when long)
        slot = self.tick_slot
        ty = slot.y + (slot.h - self._tick_surf.get_height()) // 2
        if self._tick_surf.get_width() <= slot.w - s(8):
            surface.blit(self._tick_surf,
                         (slot.x + (slot.w - self._tick_surf.get_width()) // 2, ty))
        else:
            prev_clip = surface.get_clip()
            surface.set_clip(slot.inflate(-s(6), 0))
            x0 = slot.x + s(4) - int(self.tick_scroll)
            surface.blit(self._tick_surf, (x0, ty))
            surface.blit(self._tick_surf,
                         (x0 + self._tick_surf.get_width() + s(40), ty))
            surface.set_clip(prev_clip)

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = ATOMIC_RED if mode == "work" else MINT
        txt = self.font_clock.render(f"T-{mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(midtop=(SCREEN_WIDTH // 2, s(64)))
        box = rect.inflate(s(12), s(6))
        pygame.draw.rect(surface, CREAM, box, border_radius=s(4))
        pygame.draw.rect(surface, CREAM_DARK, box, 1, border_radius=s(4))
        surface.blit(txt, rect)
