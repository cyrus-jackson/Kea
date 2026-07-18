"""
aerodrome_state.py
------------------
AERODROME — dieselpunk airship terminal at golden hour.

Art-deco sunburst sky over a stepped ziggurat skyline. A zeppelin
drones across behind the towers with blinking navigation lights and a
spinning prop; a lattice radio mast broadcasts expanding rings into
the dusk; sepia clouds drift. The System Protocol dispatch is towed
across the sky on a banner behind a little biplane — the message IS
the aircraft.

Sky, sunburst, skyline and the deco frame are pre-rendered; per-frame
work is the aircraft, rings, clouds and a few flickering windows.
"""

import pygame
import random
import math
import datetime

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from current_affairs import CurrentAffairs
from backend import world_weather

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


# ── Dieselpunk palette: sepia, amber, olive, brass ──────────────────────────
SKY_TOP     = ( 38,  30,  40)
SKY_MID     = ( 96,  58,  44)
SKY_HORIZON = (214, 124,  50)
SUN_COL     = (244, 186,  96)
RAY_COL     = (232, 156,  66)
CLOUD_COL   = (150,  96,  64)
SKYLINE     = ( 26,  19,  13)
SKYLINE_FAR = ( 52,  36,  26)
WINDOW_WARM = (255, 190,  90)
DECO_GOLD   = (198, 152,  72)
DECO_DARK   = ( 90,  66,  30)
FRAME_BG    = ( 22,  17,  12)
HULL        = ( 92,  76,  60)
HULL_LIT    = (140, 116,  88)
BANNER_BG   = (230, 212, 168)
BANNER_INK  = ( 62,  44,  26)
TEXT_PALE   = (226, 204, 160)
TEXT_DIM    = (150, 124,  90)


class AerodromeState(State):
    """Dieselpunk aerodrome with zeppelin and banner-towing biplane."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.current_affairs = CurrentAffairs()
        self.font_title  = pygame.font.Font(None, s(24))
        self.font_label  = pygame.font.Font(None, s(15))
        self.font_banner = pygame.font.Font(None, s(18))

        self.horizon_y = int(SCREEN_HEIGHT * 0.66)
        self.frame_h = s(36)

        self.time_alive = 0.0

        # zeppelin
        self.zep = None
        self.zep_timer = 2.0

        # banner plane
        self.plane = None
        self.plane_timer = 4.0
        self._banner_surf = None

        # radio broadcast rings from the mast tip
        self.mast_tip = (int(SCREEN_WIDTH * 0.78), 0)   # y set in _build_sky
        self.rings = []
        self.ring_timer = 1.0

        # flickering windows (chosen at build time)
        self.flicker_windows = []

        # drifting sepia clouds: [x, y, speed, sprite]
        self.clouds = []
        for i in range(3):
            cw, ch = s(84 + 26 * i), s(22 + 8 * i)
            sprite = pygame.Surface((int(cw * 1.5), ch * 2), pygame.SRCALPHA)
            for dx, dy, rw in [(cw * 0.25, ch * 0.5, cw), (0, ch * 0.85, cw * 0.55),
                               (cw * 0.55, ch * 0.85, cw * 0.55)]:
                pygame.draw.ellipse(sprite, (*CLOUD_COL, 90),
                                    (int(dx), int(dy), int(rw), ch))
            self.clouds.append([random.uniform(0, SCREEN_WIDTH),
                                s(60 + 46 * i), (5 - i * 1.5) * SCALE, sprite])

        self._bg = self._build_sky()
        self._frame = self._build_frame()

    # ══════════════════════════════════════════════════════════════════════
    # Pre-rendered layers
    # ══════════════════════════════════════════════════════════════════════
    def _build_sky(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        hz = self.horizon_y
        # dusk gradient in two stages
        for y in range(SCREEN_HEIGHT):
            if y < hz * 0.55:
                t = y / max(1, hz * 0.55)
                c = lerp_color(SKY_TOP, SKY_MID, t)
            else:
                t = (y - hz * 0.55) / max(1, hz - hz * 0.55)
                c = lerp_color(SKY_MID, SKY_HORIZON, min(1.0, t))
            pygame.draw.line(surf, c, (0, y), (SCREEN_WIDTH, y))

        # deco sunburst: alternating light wedges radiating from the sun
        sun_x, sun_y = SCREEN_WIDTH // 2, hz
        ray_surf = pygame.Surface((SCREEN_WIDTH, hz), pygame.SRCALPHA)
        n_rays = 12
        for k in range(n_rays):
            if k % 2:
                continue
            a0 = math.pi + k * math.pi / n_rays
            a1 = math.pi + (k + 1) * math.pi / n_rays
            length = SCREEN_WIDTH * 1.6
            pygame.draw.polygon(ray_surf, (*RAY_COL, 16),
                                [(sun_x, sun_y),
                                 (sun_x + math.cos(a0) * length, sun_y + math.sin(a0) * length),
                                 (sun_x + math.cos(a1) * length, sun_y + math.sin(a1) * length)])
        surf.blit(ray_surf, (0, 0))

        # setting deco sun: semicircle with concentric outline rings
        pygame.draw.circle(surf, SUN_COL, (sun_x, sun_y), s(44),
                           draw_top_left=True, draw_top_right=True)
        for rr in (s(52), s(62), s(74)):
            pygame.draw.circle(surf, lerp_color(SUN_COL, SKY_HORIZON, 0.5),
                               (sun_x, sun_y), rr, 1,
                               draw_top_left=True, draw_top_right=True)

        # early stars up top
        rng = random.Random(6)
        for _ in range(22):
            x = rng.randint(0, SCREEN_WIDTH - 1)
            y = rng.randint(0, int(hz * 0.4))
            surf.set_at((x, y), (200, 180, 170))

        # ── art-deco skyline: stepped ziggurat towers ────────────────────
        ground = SCREEN_HEIGHT - self.frame_h
        rng = random.Random(17)
        # far layer
        x = -s(10)
        while x < SCREEN_WIDTH:
            w = rng.randint(s(30), s(52))
            h = rng.randint(s(60), s(120))
            self._ziggurat(surf, x, ground, w, h, SKYLINE_FAR, rng, windows=False)
            x += w - rng.randint(s(4), s(12))
        # near layer with windows
        x = -s(16)
        while x < SCREEN_WIDTH:
            w = rng.randint(s(38), s(64))
            h = rng.randint(s(90), s(170))
            self._ziggurat(surf, x, ground, w, h, SKYLINE, rng, windows=True)
            x += w + rng.randint(s(2), s(10))

        # radio mast on the tallest right-side rooftop
        mx = self.mast_tip[0]
        mast_base = ground - s(150)
        mast_top = mast_base - s(56)
        self.mast_tip = (mx, mast_top)
        for i in range(4):                       # lattice
            yy = mast_base - i * s(14)
            ww = s(10) - i * s(2)
            pygame.draw.line(surf, SKYLINE, (mx - ww, yy), (mx + ww, yy - s(14)), 1)
            pygame.draw.line(surf, SKYLINE, (mx + ww, yy), (mx - ww, yy - s(14)), 1)
        pygame.draw.line(surf, SKYLINE, (mx - s(10), mast_base), (mx, mast_top), 2)
        pygame.draw.line(surf, SKYLINE, (mx + s(10), mast_base), (mx, mast_top), 2)
        return surf

    def _ziggurat(self, surf, x, ground, w, h, color, rng, windows):
        """Stepped art-deco tower with a spire, optionally lit windows."""
        steps = rng.randint(2, 4)
        for i in range(steps):
            inset = int(w * 0.14 * i)
            step_h = int(h * (1 - i * 0.22))
            rect = pygame.Rect(x + inset, ground - step_h, w - inset * 2, step_h)
            if rect.w > 2:
                pygame.draw.rect(surf, color, rect)
        # spire
        top_y = ground - h
        pygame.draw.line(surf, color, (x + w // 2, top_y), (x + w // 2, top_y - s(12)), 2)
        if windows and rng.random() < 0.9:
            for _ in range(rng.randint(3, 8)):
                wx = x + rng.randint(3, max(4, w - 5))
                wy = ground - rng.randint(s(10), max(s(12), h - s(14)))
                if 0 <= wx < SCREEN_WIDTH - 1:
                    surf.fill(WINDOW_WARM, (wx, wy, 2, s(3)))
                    if rng.random() < 0.25:      # some windows flicker at runtime
                        self.flicker_windows.append(
                            (wx, wy, random.uniform(0, math.tau)))

    def _build_frame(self):
        """Bottom art-deco terminal plate."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        fy = SCREEN_HEIGHT - self.frame_h
        pygame.draw.rect(surf, FRAME_BG, (0, fy, SCREEN_WIDTH, self.frame_h))
        pygame.draw.line(surf, DECO_GOLD, (0, fy), (SCREEN_WIDTH, fy), 2)
        pygame.draw.line(surf, DECO_DARK, (0, fy + 3), (SCREEN_WIDTH, fy + 3), 1)
        # deco fan corners
        for cx, d in ((s(16), 1), (SCREEN_WIDTH - s(16), -1)):
            for k in range(4):
                a = math.pi + k * math.pi / 6 * d if d > 0 else -k * math.pi / 6
                pygame.draw.line(surf, DECO_GOLD, (cx, SCREEN_HEIGHT - s(4)),
                                 (cx + math.cos(a) * s(12) * -d,
                                  SCREEN_HEIGHT - s(4) + math.sin(a) * s(12)), 1)
        title = self.font_title.render("A E R O D R O M E", True, DECO_GOLD)
        surf.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, fy + s(8)))
        return surf

    # ══════════════════════════════════════════════════════════════════════
    # Aircraft
    # ══════════════════════════════════════════════════════════════════════
    def _spawn_zeppelin(self):
        d = random.choice([1, -1])
        self.zep = {
            "x": -s(180) if d > 0 else SCREEN_WIDTH + s(180),
            "y": random.uniform(s(80), int(self.horizon_y * 0.55)),
            "vx": d * random.uniform(9, 14) * SCALE,
            "phase": random.uniform(0, math.tau),
        }

    def _spawn_plane(self):
        msg = self.current_affairs.get_current_message()
        text = self.font_banner.render(msg, True, BANNER_INK)
        banner = pygame.Surface((text.get_width() + s(16), s(22)), pygame.SRCALPHA)
        pygame.draw.rect(banner, BANNER_BG, banner.get_rect(), border_radius=s(3))
        pygame.draw.rect(banner, lerp_color(BANNER_BG, BANNER_INK, 0.4),
                         banner.get_rect(), 1, border_radius=s(3))
        banner.blit(text, (s(8), (banner.get_height() - text.get_height()) // 2))
        # trailing edge swallowtail
        hh = banner.get_height()
        pygame.draw.polygon(banner, (0, 0, 0, 0),
                            [(banner.get_width(), 0), (banner.get_width(), hh),
                             (banner.get_width() - s(6), hh // 2)])
        self._banner_surf = banner
        d = random.choice([1, -1])
        total = SCREEN_WIDTH + banner.get_width() + s(120)
        self.plane = {
            "x": -banner.get_width() - s(80) if d > 0 else SCREEN_WIDTH + s(80),
            "y": random.uniform(int(self.horizon_y * 0.30), int(self.horizon_y * 0.72)),
            "vx": d * total / random.uniform(14.0, 18.0),
            "phase": random.uniform(0, math.tau),
        }

    # ══════════════════════════════════════════════════════════════════════
    def update(self, dt):
        self.time_alive += dt
        self.current_affairs.update(dt)

        wind_mult = 1.0 + world_weather.conditions()["wind"] / 25.0
        for c in self.clouds:
            c[0] += c[2] * wind_mult * dt
            if c[0] > SCREEN_WIDTH + s(20):
                c[0] = -c[3].get_width()

        # radio rings
        self.ring_timer -= dt
        if self.ring_timer <= 0:
            self.ring_timer = 3.2
            self.rings.append(s(4))
        self.rings = [r + s(26) * dt for r in self.rings]
        self.rings = [r for r in self.rings if r < s(64)]

        # zeppelin — grounded when the real Stuttgart wind is up
        wx = world_weather.conditions()
        if self.zep is None:
            self.zep_timer -= dt
            if self.zep_timer <= 0 and wx["wind"] < 32:
                self._spawn_zeppelin()
        else:
            self.zep["x"] += self.zep["vx"] * dt
            if not -s(200) < self.zep["x"] < SCREEN_WIDTH + s(200):
                self.zep = None
                self.zep_timer = random.uniform(18.0, 45.0)

        # banner plane
        if self.plane is None:
            self.plane_timer -= dt
            if self.plane_timer <= 0:
                self._spawn_plane()
        else:
            self.plane["x"] += self.plane["vx"] * dt
            bw = self._banner_surf.get_width() if self._banner_surf else 0
            if not -bw - s(120) < self.plane["x"] < SCREEN_WIDTH + bw + s(120):
                self.plane = None
                self.plane_timer = random.uniform(6.0, 16.0)

    # ══════════════════════════════════════════════════════════════════════
    def draw(self, surface):
        t = self.time_alive
        surface.blit(self._bg, (0, 0))

        # clouds
        for cx, cy, _spd, sprite in self.clouds:
            surface.blit(sprite, (int(cx), int(cy)))

        # radio broadcast rings
        mx, my = self.mast_tip
        for r in self.rings:
            fade = 1.0 - r / s(64)
            pygame.draw.circle(surface, lerp_color(SKY_MID, DECO_GOLD, 0.7 * fade),
                               (mx, my), int(r), 1)
        # mast beacon
        if int(t * 1.4) % 2 == 0:
            pygame.draw.circle(surface, (235, 80, 60), (mx, my), s(2))

        # zeppelin (behind nothing — it owns the sky)
        if self.zep:
            self._draw_zeppelin(surface, t)

        # banner plane in the foreground sky
        if self.plane:
            self._draw_plane(surface, t)

        # flickering windows over the baked skyline
        for wx, wy, ph in self.flicker_windows:
            b = 0.5 + 0.5 * math.sin(t * 1.7 + ph)
            if b > 0.35:
                surface.fill(lerp_color(SKYLINE, WINDOW_WARM, b), (wx, wy, 2, s(3)))

        # terminal frame + clock line
        surface.blit(self._frame, (0, 0))
        now = datetime.datetime.now()
        info = self.font_label.render(now.strftime("%H:%M"), True, TEXT_DIM)
        surface.blit(info, (SCREEN_WIDTH - info.get_width() - s(10),
                            SCREEN_HEIGHT - self.frame_h + s(12)))
        day = self.font_label.render(f"DAY {now.timetuple().tm_yday}", True, TEXT_DIM)
        surface.blit(day, (s(10), SCREEN_HEIGHT - self.frame_h + s(12)))

    def _draw_zeppelin(self, surface, t):
        z = self.zep
        d = 1 if z["vx"] > 0 else -1
        x = z["x"]
        y = z["y"] + math.sin(t * 0.5 + z["phase"]) * s(4)
        L, R = s(150), s(28)                     # hull length / radius
        hull = pygame.Rect(0, 0, L, R * 2)
        hull.center = (int(x), int(y))
        pygame.draw.ellipse(surface, HULL, hull)
        # lit top from the sunset
        lit = pygame.Rect(0, 0, int(L * 0.86), R)
        lit.center = (int(x), int(y - R * 0.45))
        pygame.draw.ellipse(surface, HULL_LIT, lit)
        # panel seams
        for k in (-0.3, 0.0, 0.3):
            sx = int(x + k * L * 0.8)
            pygame.draw.line(surface, lerp_color(HULL, (0, 0, 0), 0.25),
                             (sx, int(y - R * 0.86)), (sx, int(y + R * 0.86)), 1)
        # tail fins
        tx = int(x - d * L * 0.46)
        pygame.draw.polygon(surface, HULL,
                            [(tx, int(y)), (tx - d * s(20), int(y - s(20))),
                             (tx - d * s(12), int(y))])
        pygame.draw.polygon(surface, lerp_color(HULL, (0, 0, 0), 0.2),
                            [(tx, int(y)), (tx - d * s(20), int(y + s(18))),
                             (tx - d * s(12), int(y))])
        # gondola with warm windows
        gw, gh = s(34), s(9)
        grect = pygame.Rect(0, 0, gw, gh)
        grect.center = (int(x), int(y + R + s(2)))
        pygame.draw.rect(surface, SKYLINE, grect, border_radius=s(3))
        for k in range(3):
            surface.fill(WINDOW_WARM, (grect.x + s(5) + k * s(10), grect.y + s(3), s(4), s(3)))
        # spinning props (two engine pods)
        for pk in (-0.22, 0.22):
            px = int(x + pk * L)
            py = int(y + R * 0.9)
            a = t * 14 + pk
            pygame.draw.line(surface, lerp_color(HULL_LIT, (255, 255, 255), 0.3),
                             (px - math.cos(a) * s(6), py - math.sin(a) * s(6)),
                             (px + math.cos(a) * s(6), py + math.sin(a) * s(6)), 1)
        # nav lights: red left, green right (blink alternately)
        nose = (int(x + d * L * 0.5), int(y))
        if int(t * 2) % 2 == 0:
            pygame.draw.circle(surface, (230, 70, 60), (tx, int(y - s(6))), s(2))
        else:
            pygame.draw.circle(surface, (90, 220, 110), nose, s(2))

    def _draw_plane(self, surface, t):
        p = self.plane
        d = 1 if p["vx"] > 0 else -1
        bob = math.sin(t * 1.6 + p["phase"]) * s(3)
        x, y = p["x"], p["y"] + bob
        # banner trails behind the plane
        banner = self._banner_surf
        if banner:
            bx = x - d * (banner.get_width() + s(26)) if d > 0 else x + s(26)
            bwave = math.sin(t * 2.2 + p["phase"]) * s(2)
            surface.blit(banner, (int(bx if d > 0 else x + s(26)), int(y - s(10) + bwave)))
            # tow rope
            rope_x0 = int(x - d * s(10))
            rope_x1 = int(bx + (banner.get_width() if d > 0 else 0))
            pygame.draw.line(surface, lerp_color(BANNER_INK, SKY_MID, 0.4),
                             (rope_x0, int(y)), (rope_x1, int(y - s(2) + bwave)), 1)
        # little biplane
        body = pygame.Rect(0, 0, s(22), s(6))
        body.center = (int(x), int(y))
        pygame.draw.ellipse(surface, SKYLINE, body)
        for wy in (-s(6), s(3)):                  # biplane double wings
            pygame.draw.rect(surface, DECO_GOLD,
                             (int(x - s(5)), int(y + wy), s(10), s(2)))
        pygame.draw.line(surface, DECO_DARK, (int(x - s(3)), int(y - s(5))),
                         (int(x - s(3)), int(y + s(4))), 1)
        # tail + spinning prop
        pygame.draw.rect(surface, SKYLINE, (int(x - d * s(12)), int(y - s(4)), s(3), s(5)))
        a = t * 18
        px = int(x + d * s(12))
        pygame.draw.line(surface, (230, 220, 200),
                         (px, int(y - math.sin(a) * s(5))),
                         (px, int(y + math.sin(a) * s(5))), 1)

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = (230, 90, 60) if mode == "work" else (140, 200, 110)
        txt = self.font_label.render(f"{mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(10), s(10)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, FRAME_BG, box, border_radius=s(4))
        pygame.draw.rect(surface, DECO_GOLD, box, 1, border_radius=s(4))
        surface.blit(txt, rect)
