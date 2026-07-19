"""
orrery_state.py
---------------
THE ORRERY — clockpunk celestial machine, and Kea's first true-3D scene.

A brass wireframe solar system floats in the dark: six planets on
their orbit rings, each on a brass arm from the sun hub, with Earth's
moon, Jupiter's Galilean pair and Saturn's ring. The camera circles
the machine slowly with a breathing tilt, so every frame is a slightly
new perspective — nothing side-on, nothing static.

It is also a real instrument: planet positions are computed from mean
orbital elements for TODAY's date (heliocentric longitudes, J2000
epoch), so the machine shows the actual current arrangement of the
solar system. The engraved plaque names whichever planet currently
swings nearest the viewer, with the day of its own year.

Deliberately no ticker on this screen — the machine speaks for itself.
"""

import pygame
import random
import math
import datetime

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


# ── Palette: brass on midnight indigo ───────────────────────────────────────
BG_TOP    = (8, 8, 20)
BG_BOT    = (16, 12, 26)
BRASS     = (196, 156, 80)
BRASS_DIM = (110, 88, 46)
IVORY     = (235, 225, 200)
TEXT_DIM  = (140, 126, 100)
SUN_CORE  = (255, 214, 120)
SUN_GLOW  = (200, 140, 50)

# name, mean longitude at J2000 (deg), period (days), orbit radius
# (normalized for the machine, not to scale), display size, color
PLANETS = [
    ("MERCURY", 252.25, 87.97,   0.26, 2.4, (176, 168, 160)),
    ("VENUS",   181.98, 224.70,  0.38, 3.4, (232, 196, 130)),
    ("EARTH",   100.47, 365.26,  0.51, 3.6, (110, 165, 225)),
    ("MARS",    355.43, 686.98,  0.63, 3.0, (216, 112, 82)),
    ("JUPITER",  34.40, 4332.59, 0.79, 5.4, (226, 178, 128)),
    ("SATURN",   49.94, 10759.2, 0.97, 4.8, (234, 206, 148)),
]
J2000 = datetime.datetime(2000, 1, 1, 12, 0)
ROMAN = ["I", "II", "III", "IV", "V", "VI"]


class OrreryState(State):
    """Clockwork solar system in live 3D with real planetary longitudes."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.font_title = pygame.font.Font(None, s(24))
        self.font_label = pygame.font.Font(None, s(15))
        self.font_plaque = pygame.font.Font(None, s(19))

        self.time_alive = 0.0
        self.cx = SCREEN_WIDTH // 2
        self.cy = int(SCREEN_HEIGHT * 0.44)
        self.f = 245 * SCALE          # focal length
        self.dist = 2.35              # camera distance (orbit radii <= 1)

        # precomputed unit circle for orbit rings
        self.ring_pts = [(math.cos(a), math.sin(a))
                         for a in [i * math.tau / 56 for i in range(57)]]

        # 3D starfield on a far sphere
        rng = random.Random(9)
        self.stars = []
        for _ in range(46):
            th, ph = rng.uniform(0, math.tau), rng.uniform(0.15, math.pi - 0.15)
            r = rng.uniform(5.0, 8.0)
            self.stars.append((r * math.sin(ph) * math.cos(th),
                               r * math.sin(ph) * math.sin(th),
                               r * math.cos(ph) * 0.6,
                               rng.uniform(0, math.tau)))

        self._bg = self._build_bg()
        self._front_name = "EARTH"

    # ══════════════════════════════════════════════════════════════════════
    def _build_bg(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / max(1, SCREEN_HEIGHT - 1)
            pygame.draw.line(surf, lerp_color(BG_TOP, BG_BOT, t),
                             (0, y), (SCREEN_WIDTH, y))
        # renaissance corner filigree: nested brass arcs
        r0 = s(26)
        for cx, cy, a0 in [(0, 0, 0), (SCREEN_WIDTH, 0, math.pi / 2),
                           (SCREEN_WIDTH, SCREEN_HEIGHT, math.pi),
                           (0, SCREEN_HEIGHT, 3 * math.pi / 2)]:
            for rr in (r0, r0 - s(7), r0 - s(14)):
                rect = pygame.Rect(cx - rr, cy - rr, rr * 2, rr * 2)
                pygame.draw.arc(surf, BRASS_DIM, rect, a0, a0 + math.pi / 2, 1)
        title = self.font_title.render("THE ORRERY", True, BRASS)
        surf.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, s(10)))
        sub = self.font_label.render("CLOCKWORK HELIOCENTRIC  ·  LIVE", True, TEXT_DIM)
        surf.blit(sub, ((SCREEN_WIDTH - sub.get_width()) // 2, s(28)))
        return surf

    # ══════════════════════════════════════════════════════════════════════
    def _camera(self):
        """Slowly circling viewpoint with a breathing tilt."""
        yaw = self.time_alive * 0.10
        pitch = math.radians(58 + math.sin(self.time_alive * 0.23) * 6)
        return (math.cos(yaw), math.sin(yaw),
                math.cos(pitch), math.sin(pitch))

    def _project(self, x, y, z, cam):
        cy_, sy_, cp, sp = cam
        x1 = x * cy_ - y * sy_
        y1 = x * sy_ + y * cy_
        z2 = y1 * sp + z * cp
        depth = y1 * cp - z * sp + self.dist
        if depth < 0.35:
            return None
        k = self.f / depth
        return (self.cx + x1 * k, self.cy - z2 * k, depth)

    def _planet_angles(self):
        """Actual mean heliocentric longitudes for now."""
        days = (datetime.datetime.utcnow() - J2000).total_seconds() / 86400.0
        out = []
        for name, L0, period, radius, size, color in PLANETS:
            ang = math.radians((L0 + 360.0 * days / period) % 360.0)
            out.append((name, ang, period, radius, size, color,
                        (days % period)))
        return out

    # ══════════════════════════════════════════════════════════════════════
    def update(self, dt):
        self.time_alive += dt

    def draw(self, surface):
        surface.blit(self._bg, (0, 0))
        t = self.time_alive
        cam = self._camera()

        # ── stars (projected, twinkling) ─────────────────────────────────
        for sx_, sy_, sz_, ph in self.stars:
            p = self._project(sx_, sy_, sz_, cam)
            if p is None:
                continue
            b = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 1.6 + ph))
            c = int(110 + 110 * b)
            surface.fill((c, c, min(255, c + 24)),
                         (int(p[0]), int(p[1]), 1 + (b > 0.8), 1 + (b > 0.8)))

        planets = self._planet_angles()

        # ── orbit rings (brass, dimmer with distance) ────────────────────
        for name, ang, period, radius, size, color, pday in planets:
            pts = []
            for ux, uy in self.ring_pts:
                p = self._project(ux * radius, uy * radius, 0, cam)
                if p:
                    pts.append((p[0], p[1]))
            if len(pts) > 2:
                pygame.draw.lines(surface, BRASS_DIM, False, pts, 1)

        # ── depth-sorted machine parts: sun, arms, planets, moons ────────
        drawables = []
        sun_p = self._project(0, 0, 0, cam)
        if sun_p:
            drawables.append((sun_p[2], "sun", sun_p, None))

        nearest = None
        for name, ang, period, radius, size, color, pday in planets:
            wx, wy = radius * math.cos(ang), radius * math.sin(ang)
            p = self._project(wx, wy, 0, cam)
            if p is None:
                continue
            drawables.append((p[2], "planet", p, (name, size, color, wx, wy)))
            if nearest is None or p[2] < nearest[0]:
                nearest = (p[2], name, period, pday)
            # moons: Earth 1, Jupiter 2 (visual orbits, brisk)
            n_moons = 1 if name == "EARTH" else (2 if name == "JUPITER" else 0)
            for mi in range(n_moons):
                ma = t * (1.2 + mi * 0.5) + mi * 2.2 + ang
                mp = self._project(wx + 0.055 * math.cos(ma),
                                   wy + 0.055 * math.sin(ma), 0.012, cam)
                if mp:
                    drawables.append((mp[2], "moon", mp, None))

        drawables.sort(key=lambda d: -d[0])          # farthest first

        for depth, kind, p, extra in drawables:
            k = 2.5 / depth                          # perspective size factor
            if kind == "sun":
                pulse = 0.5 + 0.5 * math.sin(t * 1.1)
                for gr, ga in ((11, 0.35), (7, 0.7)):
                    pygame.draw.circle(surface,
                                       lerp_color(BG_TOP, SUN_GLOW, ga * (0.7 + 0.3 * pulse)),
                                       (int(p[0]), int(p[1])), int(s(gr) * k))
                pygame.draw.circle(surface, SUN_CORE, (int(p[0]), int(p[1])),
                                   max(2, int(s(5) * k)))
            elif kind == "moon":
                pygame.draw.circle(surface, IVORY, (int(p[0]), int(p[1])),
                                   max(1, int(s(1.6) * k)))
            else:
                name, size, color, wx, wy = extra
                # brass arm from the hub to the planet
                if sun_p:
                    arm = lerp_color(BRASS, BG_TOP, min(0.75, (depth - 1.5) / 2.4))
                    pygame.draw.line(surface, arm, (int(sun_p[0]), int(sun_p[1])),
                                     (int(p[0]), int(p[1])), 1 + (depth < 2.4))
                pr = max(2, int(s(size) * k))
                shaded = lerp_color(color, BG_TOP, min(0.6, (depth - 1.6) / 2.8))
                pygame.draw.circle(surface, shaded, (int(p[0]), int(p[1])), pr)
                pygame.draw.circle(surface, lerp_color(shaded, IVORY, 0.5),
                                   (int(p[0] - pr * 0.3), int(p[1] - pr * 0.3)),
                                   max(1, pr // 3))
                if name == "SATURN":                 # the ring
                    ring = pygame.Rect(0, 0, int(pr * 3.4), int(pr * 1.3))
                    ring.center = (int(p[0]), int(p[1]))
                    pygame.draw.ellipse(surface, lerp_color(BRASS, shaded, 0.4),
                                        ring, 1)

        # ── engraved plaque: date + the planet nearest the viewer ────────
        if nearest:
            _, name, period, pday = nearest
            self._front_name = name
        idx = [pl[0] for pl in PLANETS].index(self._front_name)
        plaque = pygame.Rect(s(38), SCREEN_HEIGHT - s(52), SCREEN_WIDTH - s(76), s(38))
        pygame.draw.rect(surface, (24, 20, 16), plaque, border_radius=s(5))
        pygame.draw.rect(surface, BRASS_DIM, plaque, 1, border_radius=s(5))
        pygame.draw.rect(surface, BRASS_DIM, plaque.inflate(-s(6), -s(6)), 1,
                         border_radius=s(3))
        if nearest:
            line1 = f"{ROMAN[idx]}  ·  {self._front_name}  ·  DAY {int(nearest[3]) + 1} OF {int(nearest[2])}"
        else:
            line1 = self._front_name
        l1 = self.font_plaque.render(line1, True, IVORY)
        surface.blit(l1, (plaque.centerx - l1.get_width() // 2, plaque.y + s(6)))
        date_str = datetime.datetime.now().strftime("%d %B %Y").upper()
        l2 = self.font_label.render(date_str, True, TEXT_DIM)
        surface.blit(l2, (plaque.centerx - l2.get_width() // 2, plaque.y + s(22)))

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = (216, 112, 82) if mode == "work" else (140, 200, 140)
        txt = self.font_label.render(f"{mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(10), s(10)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, (24, 20, 16), box, border_radius=s(4))
        pygame.draw.rect(surface, BRASS_DIM, box, 1, border_radius=s(4))
        surface.blit(txt, rect)
