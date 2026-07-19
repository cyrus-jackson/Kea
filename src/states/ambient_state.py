"""
ambient_state.py
----------------
NEON SPRAWL — the cyberpunk ambient city.

A procedural night city that regenerates itself with a fresh color
scheme every couple of minutes: layered silhouettes over a glowing
horizon, a giant banded moon drifting on a slow orbit, sweeping
searchlights, flickering holo-billboards, blinking rooftop beacons,
street + sky traffic, and the whole scene reflected in dark water.

Design notes (Raspberry Pi friendly):
- Everything static for a given city generation is pre-rendered once
  (sky gradient, stars, planets, moon sprite, building layers).
- The per-frame path is blits + a handful of primitive draws. The old
  version allocated several full-screen alpha surfaces every frame.
"""

import pygame
import random
import math

from config import SCREEN_WIDTH, SCREEN_HEIGHT, WHITE
from states.base_state import State
from ui.glow_text import GlowText
from current_affairs import CurrentAffairs
from backend import world_weather

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ── Curated night palettes: one is picked per city generation ───────────────
SCHEMES = [
    {   # classic neon night
        "sky_top": (6, 5, 20),   "sky_bot": (36, 14, 56),
        "horizon": (255, 64, 158), "far": (58, 30, 82),
        "windows": [(255, 190, 60), (0, 225, 255)],
    },
    {   # teal dusk / orange sodium lamps
        "sky_top": (4, 12, 22),  "sky_bot": (16, 52, 62),
        "horizon": (255, 140, 40), "far": (30, 66, 74),
        "windows": [(255, 170, 50), (170, 255, 230)],
    },
    {   # violet storm
        "sky_top": (10, 4, 26),  "sky_bot": (52, 18, 84),
        "horizon": (170, 80, 255), "far": (70, 38, 104),
        "windows": [(230, 160, 255), (0, 235, 255)],
    },
    {   # blood-red skyline
        "sky_top": (14, 4, 10),  "sky_bot": (58, 12, 28),
        "horizon": (255, 70, 70), "far": (86, 28, 44),
        "windows": [(255, 120, 90), (255, 220, 130)],
    },
]

NEAR_BLACK = (8, 6, 14)

# (width_divisor, skyline height fraction, window w, window h, lit_thresh)
# lit_thresh: windows light up when randint(1,10) >= thresh (higher = sparser)
LAYER_SPECS = [
    (10, 0.33, 2, 4, 8),
    (9,  0.40, 3, 5, 9),
    (8,  0.41, 4, 6, 9),
    (7,  0.50, 5, 7, 9),
    (6,  0.52, 6, 8, 10),
    (5,  0.58, 7, 9, 10),
]


class AmbientState(State):
    """Procedural neon city with water reflection."""

    RESET_INTERVAL = 120.0     # seconds between city regenerations

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.city_h = int(SCREEN_HEIGHT * 0.75)
        self.water_h = SCREEN_HEIGHT - self.city_h

        # per-generation content
        self.scheme = None
        self.sky_surface = pygame.Surface((SCREEN_WIDTH, self.city_h))
        self.layer_surfaces = []
        self.roads = []
        self.beacons = []          # [x, y, phase]
        self.billboards = []       # {rect, color, phase, layer, bg}
        self.searchlights = []     # {x, y, phase, speed, spread, length}
        self.twinkles = []         # [x, y, phase]
        self.moon_sprite = None

        self.generate_city()

        # traffic (street + sky)
        self.traffic = self.gen_traffic(num_cars=16, speed=20)
        self.traffic.extend(self.gen_sky_traffic(num_cars=2, speed=10))

        # timers
        self.time_alive = 0.0
        self.reflection_timer = 0.0
        self.scene_reset_timer = 0.0

        # weather
        self.rain_intensity = 0.0
        self.wind_speed = 0.0
        self.raindrops = []
        self.water_ripples = []
        self.lightning_timer = random.uniform(5.0, 15.0)
        self.lightning_flash_alpha = 0.0

        # reusable surfaces (no per-frame allocation)
        self.city_render_surface = pygame.Surface((SCREEN_WIDTH, self.city_h))
        self.fx_surface = pygame.Surface((SCREEN_WIDTH, self.city_h), pygame.SRCALPHA)
        self.cached_flash_surf = pygame.Surface((SCREEN_WIDTH, self.city_h), pygame.SRCALPHA)
        self.cached_weather_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        self.cached_reflection_darken_surf = pygame.Surface((SCREEN_WIDTH, self.water_h), pygame.SRCALPHA)
        self.cached_reflection_darken_surf.fill((8, 14, 26, 70))
        # depth fade as an RGB multiply mask (the reflection surface has no
        # alpha channel, so an RGBA mask silently does nothing — old bug)
        self.cached_reflection_fade = pygame.Surface((SCREEN_WIDTH, max(1, self.water_h)))
        for y in range(self.water_h):
            t = y / max(1, self.water_h - 1)
            shade = int(255 * (1.0 - t ** 1.3) * 0.92 + 18)
            pygame.draw.line(self.cached_reflection_fade, (shade, shade, shade),
                             (0, y), (SCREEN_WIDTH, y))

        # ticker: single line, marquee when long — never truncates
        self.current_affairs = CurrentAffairs()
        affairs_font = pygame.font.Font(None, s(20))
        self.affairs_text = GlowText(affairs_font, self.current_affairs.get_current_message(),
                                     (255, 200, 120), (255, 120, 20), glow_radius=2)
        self.ticker_scroll = 0.0
        self.ticker_hold = 2.0
        self.ticker_band = pygame.Surface((SCREEN_WIDTH, s(46)), pygame.SRCALPHA)
        for y in range(s(46)):
            a = int(150 * (y / s(46)))
            pygame.draw.line(self.ticker_band, (0, 0, 0, a), (0, y), (SCREEN_WIDTH, y))

        # moon orbit
        self.orbital_timer = random.uniform(0, math.tau)
        self.moon_orbit = {
            "cx": SCREEN_WIDTH / 2, "cy": int(self.city_h * 0.22),
            "rx": SCREEN_WIDTH * 0.36, "ry": int(self.city_h * 0.11),
            "speed": 0.02,
        }
        self.moon_x = self.moon_orbit["cx"] + math.cos(self.orbital_timer) * self.moon_orbit["rx"]
        self.moon_y = self.moon_orbit["cy"] + math.sin(self.orbital_timer) * self.moon_orbit["ry"]

        # keep the storm switch (external callers can crank it up)
        self.set_weather(rain_intensity=0.0, wind_speed=0.0)

    # ══════════════════════════════════════════════════════════════════════
    # City generation (everything here runs once per generation)
    # ══════════════════════════════════════════════════════════════════════
    def set_weather(self, rain_intensity, wind_speed):
        self.rain_intensity = max(0.0, min(1.0, rain_intensity))
        self.wind_speed = wind_speed

    def generate_city(self):
        self.scheme = random.choice(SCHEMES)
        self.layer_surfaces.clear()
        self.roads.clear()
        self.beacons.clear()
        self.billboards.clear()
        self.searchlights.clear()
        self.twinkles.clear()

        self._build_sky()
        self._build_moon_sprite()

        n = len(LAYER_SPECS)
        for i, (wdiv, hfrac, ww, wh, lit) in enumerate(LAYER_SPECS):
            t = i / (n - 1)
            color = lerp_color(self.scheme["far"], NEAR_BLACK, t ** 0.8)
            layer = pygame.Surface((SCREEN_WIDTH, self.city_h), pygame.SRCALPHA)
            skyline_y = self.city_h - int(self.city_h * (1 - hfrac))
            self._gen_buildings(layer, i, SCREEN_WIDTH / wdiv, skyline_y,
                                color, ww, wh, lit)
            # road for this layer
            r0 = 0.70 + i * 0.05
            road_y = random.randint(int(self.city_h * r0),
                                    min(self.city_h - 8, int(self.city_h * (r0 + 0.05))))
            thickness = 2 + i
            self.roads.append({"y": road_y, "thickness": thickness, "layer": i})
            self._gen_road(layer, road_y, thickness, color)
            self.layer_surfaces.append(layer)

        # shimmer streaks on the water: [x, row, width, speed, phase, color]
        self.water_streaks = []
        streak_colors = self.scheme["windows"] + [self.scheme["horizon"]]
        for _ in range(10):
            self.water_streaks.append([
                random.randint(s(10), SCREEN_WIDTH - s(10)),
                random.randint(2, max(3, self.water_h - 4)),
                random.randint(s(8), s(34)),
                random.uniform(1.2, 2.6),
                random.uniform(0, math.tau),
                random.choice(streak_colors),
            ])

        # sweeping searchlights rise from mid-distance rooftops
        for _ in range(2):
            self.searchlights.append({
                "x": random.randint(s(30), SCREEN_WIDTH - s(30)),
                "y": random.randint(int(self.city_h * 0.42), int(self.city_h * 0.60)),
                "phase": random.uniform(0, math.tau),
                "speed": random.uniform(0.25, 0.45),
                "spread": random.uniform(0.05, 0.09),
                "length": self.city_h * random.uniform(0.7, 0.95),
            })

    def _build_sky(self):
        """Gradient + horizon glow + stars + a distant ringed planet."""
        sky = self.sky_surface
        top, bot = self.scheme["sky_top"], self.scheme["sky_bot"]
        h = self.city_h
        for y in range(h):
            sky_t = y / max(1, h - 1)
            pygame.draw.line(sky, lerp_color(top, bot, sky_t), (0, y), (SCREEN_WIDTH, y))
        # horizon glow band (strongest at the skyline, fades upward)
        hz = self.scheme["horizon"]
        for i in range(s(70)):
            a = (1 - i / s(70)) ** 2
            y = h - 1 - i
            base = sky.get_at((0, y))[:3]
            pygame.draw.line(sky, lerp_color(base, hz, 0.55 * a), (0, y), (SCREEN_WIDTH, y))

        # stars (static; a few get twinkle animation on top)
        for _ in range(random.randint(30, 48)):
            x = random.randint(0, SCREEN_WIDTH - 1)
            y = random.randint(0, int(h * 0.75))
            c = random.choice([(210, 210, 230), (200, 160, 200), (150, 200, 220)])
            sky.fill(c, (x, y, random.choice([1, 1, 2]), 1))
        self.twinkles = [[random.randint(2, SCREEN_WIDTH - 3),
                          random.randint(2, int(h * 0.6)),
                          random.uniform(0, math.tau)] for _ in range(8)]

        # one distant ringed planet, baked
        px = random.randint(s(30), SCREEN_WIDTH - s(30))
        py = random.randint(s(30), int(h * 0.35))
        pr = random.randint(s(8), s(14))
        pcol = lerp_color(self.scheme["horizon"], (120, 120, 160), 0.5)
        pygame.draw.circle(sky, lerp_color(pcol, top, 0.55), (px, py), pr)
        pygame.draw.circle(sky, lerp_color(pcol, top, 0.35), (px - pr // 3, py - pr // 3), pr // 3)
        if random.random() < 0.6:
            ring = pygame.Rect(0, 0, int(pr * 3.2), int(pr * 0.9))
            ring.center = (px, py)
            pygame.draw.ellipse(sky, lerp_color(pcol, top, 0.3), ring, 1)

    def _build_moon_sprite(self):
        """Giant banded synthwave moon, pre-rendered with its glow."""
        r = s(34)
        glow = s(12)
        size = (r + glow) * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        hz = self.scheme["horizon"]
        # halo
        for g in range(glow, 0, -2):
            pygame.draw.circle(surf, (*hz, 10), (size // 2, size // 2), r + g)
        # banded disc: pale top fading into a bright horizon-colored base
        pale = (245, 240, 248)
        hz_hot = lerp_color(hz, (255, 255, 255), 0.25)
        for y in range(-r, r):
            half = int(math.sqrt(r * r - y * y))
            band_t = (y + r) / (2 * r)
            col = lerp_color(pale, hz_hot, band_t)
            pygame.draw.line(surf, col, (size // 2 - half, size // 2 + y),
                             (size // 2 + half, size // 2 + y))
        # slice gaps in the lower half (classic synthwave)
        gap, y = 2, int(size * 0.60)
        while y < size:
            surf.fill((0, 0, 0, 0), (0, y, size, gap))
            y += gap + s(6)
            gap += 1
        # craters on the pale upper half
        rng = random.Random()
        for _ in range(4):
            cx = size // 2 + rng.randint(-r // 2, r // 2)
            cy = size // 2 - rng.randint(r // 4, int(r * 0.7))
            pygame.draw.circle(surf, lerp_color(pale, (150, 150, 170), 0.5),
                               (cx, cy), rng.randint(2, s(4)))
        self.moon_sprite = surf

    def _gen_buildings(self, surface, layer_i, b_width, b_height, b_color, win_w, win_h, lit_thresh):
        canvas_h = surface.get_height()
        num_buildings = int(SCREEN_WIDTH / b_width) + 2
        for i in range(num_buildings):
            start_x = int(b_width * i + random.randint(int(-b_width), int(b_width)))
            start_y = int(b_height + random.randint(-15, 15))
            end_x = start_x + int(b_width) + random.randint(-10, 10)
            rect_w = end_x - start_x
            if rect_w <= 0:
                continue
            pygame.draw.rect(surface, b_color, (start_x, start_y, rect_w, canvas_h - start_y))

            feature = random.choice(["Box", "Dome", "Antenna", "Platform", "Pylon", "None"])
            if feature == "Box":
                bx0 = random.randint(start_x, start_x + rect_w // 2)
                bx1 = random.randint(start_x + rect_w // 2, end_x)
                by0 = random.randint(start_y - 5, start_y - 1)
                if bx1 > bx0:
                    pygame.draw.rect(surface, b_color, (bx0, by0, bx1 - bx0, start_y - by0))
            elif feature == "Dome":
                d = random.randint(max(2, rect_w // 2), max(3, rect_w))
                pygame.draw.ellipse(surface, b_color,
                                    (start_x + rect_w // 2 - d // 2,
                                     random.randint(start_y - d, start_y - d // 2), d, d))
            elif feature in ("Antenna", "Pylon"):
                px = random.randint(start_x + 2, max(start_x + 3, end_x - 2))
                ph = random.randint(4, 10)
                pygame.draw.line(surface, b_color, (px, start_y), (px, start_y - ph))
                # rooftop beacon on the antenna tip (front layers only)
                if layer_i >= 3 and random.random() < 0.6:
                    self.beacons.append([px, start_y - ph, random.uniform(0, math.tau)])
            elif feature == "Platform":
                pygame.draw.line(surface, b_color, (start_x, start_y - 2), (end_x, start_y - 2))

            # windows
            ww = max(2, random.randint(win_w - 1, win_w + 1))
            wh = max(3, random.randint(win_h - 1, win_h + 1))
            self._gen_windows(surface, start_x, end_x, start_y, canvas_h, ww, wh, lit_thresh)

            # holo-billboard on some tall mid/front buildings
            if layer_i >= 2 and rect_w > s(26) and random.random() < 0.18 \
               and len(self.billboards) < 4:
                bw = random.randint(s(16), min(rect_w - 6, s(30)))
                bh = random.randint(s(10), s(18))
                bx = random.randint(start_x + 3, max(start_x + 4, end_x - bw - 3))
                by = random.randint(start_y + 6, start_y + s(40))
                self.billboards.append({
                    "rect": pygame.Rect(bx, by, bw, bh),
                    "color": random.choice(self.scheme["windows"] + [self.scheme["horizon"]]),
                    "bg": b_color,
                    "phase": random.uniform(0, math.tau),
                    "layer": layer_i,
                })

    def _gen_windows(self, surface, start_x, end_x, start_y, end_y, win_w, win_h, lit_thresh):
        c1, c2 = self.scheme["windows"]
        cols = int((end_x - start_x - 2) / win_w)
        rows = int((end_y - start_y - 2) / win_h)
        for iy in range(rows + 1):
            for ix in range(cols + 1):
                wx = start_x + 1 + ix * win_w
                wy = start_y + 3 + iy * win_h
                if wx + win_w - 2 >= end_x:
                    continue
                if random.randint(1, 10) >= lit_thresh:
                    color = random.choice([c1, c1, c1, c2])
                    # occasional dim window (someone's asleep)
                    if random.random() < 0.25:
                        color = lerp_color(color, NEAR_BLACK, 0.6)
                    if win_w - 2 > 0 and win_h - 3 > 0:
                        pygame.draw.rect(surface, color, (wx, wy, win_w - 2, win_h - 3))

    def _gen_road(self, surface, road_y, thickness, color):
        canvas_w, canvas_h = surface.get_size()
        pygame.draw.rect(surface, color, (0, road_y, canvas_w, thickness))
        strut_w = max(1, (thickness * 2) // 3)
        interval = strut_w * 6
        for i in range(canvas_w // max(1, interval) + 1):
            x = i * (interval + strut_w)
            pygame.draw.rect(surface, color, (x, road_y, strut_w, canvas_h - road_y))
        if random.random() < 0.5:
            rail_y = road_y - thickness // 2 - 1
            pygame.draw.line(surface, color, (0, rail_y), (canvas_w, rail_y))
            for i in range(canvas_w // 3 + 1):
                pygame.draw.rect(surface, color, (i * 3, rail_y, 1, road_y - rail_y))
        # street lamps
        lamp = self.scheme["windows"][0]
        for i in range(canvas_w // 24 + 1):
            x = random.randint(-10, 10) + i * 25
            pygame.draw.rect(surface, color, (x, road_y - 8, 1, 8))
            pygame.draw.rect(surface, color, (x, road_y - 8, 3, 2))
            pygame.draw.rect(surface, lamp, (x + 3, road_y - 6, 2, 2))

    # ══════════════════════════════════════════════════════════════════════
    # Traffic
    # ══════════════════════════════════════════════════════════════════════
    def gen_traffic(self, num_cars, speed):
        cars = []
        for _ in range(num_cars):
            road = random.choice(self.roads)
            cars.append({
                "x": random.uniform(0, SCREEN_WIDTH),
                "y": road["y"] + random.randint(0, max(0, road["thickness"] - 2)),
                "speed": speed * random.uniform(0.8, 1.2) * random.choice([1, -1]),
                "layer": road["layer"],
            })
        return cars

    def gen_sky_traffic(self, num_cars, speed):
        cars = []
        for _ in range(num_cars):
            cars.append({
                "x": random.uniform(0, SCREEN_WIDTH),
                "y": random.uniform(self.city_h * 0.1, self.city_h * 0.75),
                "speed": speed * random.uniform(1.5, 4.0) * random.choice([1, -1]),
                "layer": random.randint(0, len(LAYER_SPECS) - 1),
                "is_sky": True,
                "trail": random.randint(4, 15),
                "color": random.choice([(255, 100, 100), (100, 255, 255),
                                        (100, 255, 100), (255, 255, 255)]),
            })
        return cars

    def _respawn_car(self, car):
        if car.get("is_sky"):
            car["y"] = random.uniform(self.city_h * 0.1, self.city_h * 0.75)
            car["layer"] = random.randint(0, len(LAYER_SPECS) - 1)
            car["trail"] = random.randint(4, 15)
        else:
            road = random.choice(self.roads)
            car["y"] = road["y"] + random.randint(0, max(0, road["thickness"] - 2))
            car["layer"] = road["layer"]

    # ══════════════════════════════════════════════════════════════════════
    # Update
    # ══════════════════════════════════════════════════════════════════════
    def update(self, dt):
        self.time_alive += dt
        self.reflection_timer += dt * 3.0

        # the real sky drives the city: rain, wind, and storms are live
        self._wx_timer = getattr(self, "_wx_timer", 0.0) - dt
        if self._wx_timer <= 0:
            self._wx_timer = 30.0
            wx = world_weather.conditions()
            self.set_weather(wx["rain"], -wx["wind"] * 0.6)

        for car in self.traffic:
            car["x"] += car["speed"] * dt
            if car["x"] > SCREEN_WIDTH + 20:
                car["x"] = -20
                self._respawn_car(car)
            elif car["x"] < -20:
                car["x"] = SCREEN_WIDTH + 20
                self._respawn_car(car)

        self.scene_reset_timer += dt
        if self.scene_reset_timer >= self.RESET_INTERVAL:
            self.scene_reset_timer = 0.0
            self.generate_city()

        # moon orbit
        self.orbital_timer += dt * self.moon_orbit["speed"]
        self.moon_x = self.moon_orbit["cx"] + math.cos(self.orbital_timer) * self.moon_orbit["rx"]
        self.moon_y = self.moon_orbit["cy"] + math.sin(self.orbital_timer) * self.moon_orbit["ry"]

        # ── weather ──────────────────────────────────────────────────────
        target_drops = int(self.rain_intensity * 400)
        while len(self.raindrops) < target_drops:
            self.raindrops.append({
                "x": random.uniform(0, SCREEN_WIDTH),
                "y": random.uniform(-SCREEN_HEIGHT, 0),
                "speed": random.uniform(300, 500) + self.rain_intensity * 200,
                "length": random.uniform(10, 20) + self.rain_intensity * 10,
            })
        while len(self.raindrops) > target_drops:
            self.raindrops.pop()

        for drop in self.raindrops:
            drop["x"] += self.wind_speed * dt
            drop["y"] += drop["speed"] * dt
            if drop["y"] > SCREEN_HEIGHT:
                if random.random() < 0.45:
                    self.water_ripples.append({
                        "x": drop["x"],
                        "y": random.uniform(SCREEN_HEIGHT * 0.78, SCREEN_HEIGHT),
                        "life": 0.0,
                        "max_life": random.uniform(0.15, 0.3),
                    })
                drop["y"] = random.uniform(-50, 0)
                drop["x"] = random.uniform(0, SCREEN_WIDTH)

        for r in self.water_ripples:
            r["life"] += dt
        self.water_ripples = [r for r in self.water_ripples if r["life"] < r["max_life"]]

        if self.rain_intensity >= 0.8:
            self.lightning_timer -= dt
            if self.lightning_timer <= 0:
                self.lightning_flash_alpha = 255.0
                self.lightning_timer = random.uniform(1.0, 5.0)
        else:
            self.lightning_timer = random.uniform(5.0, 15.0)
        if self.lightning_flash_alpha > 0:
            self.lightning_flash_alpha = max(0.0, self.lightning_flash_alpha - 900 * dt)

        if self.current_affairs.update(dt):
            self.affairs_text.update_text(self.current_affairs.get_current_message())
            self.ticker_scroll = 0.0
            self.ticker_hold = 2.0
        aw = self.affairs_text.get_surface().get_width()
        if aw > SCREEN_WIDTH - s(24):
            if self.ticker_hold > 0:
                self.ticker_hold -= dt
            else:
                self.ticker_scroll += s(26) * dt
                if self.ticker_scroll > aw + s(40):
                    self.ticker_scroll = 0.0
                    self.ticker_hold = 2.0

    # ══════════════════════════════════════════════════════════════════════
    # Draw
    # ══════════════════════════════════════════════════════════════════════
    def draw(self, surface):
        city = self.city_render_surface
        t = self.time_alive

        # sky (pre-rendered) + twinkling stars + moon
        city.blit(self.sky_surface, (0, 0))
        for tx, ty, phase in self.twinkles:
            b = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 2.0 + phase))
            c = int(140 + 110 * b)
            city.fill((c, c, min(255, c + 20)), (tx, ty, 2, 2))
        ms = self.moon_sprite
        city.blit(ms, (int(self.moon_x) - ms.get_width() // 2,
                       int(self.moon_y) - ms.get_height() // 2))

        # searchlight beams sweep the sky behind the buildings
        self.fx_surface.fill((0, 0, 0, 0))
        for sl in self.searchlights:
            a = -math.pi / 2 + math.sin(t * sl["speed"] + sl["phase"]) * 0.85
            for da, alpha in ((sl["spread"], 22), (sl["spread"] * 0.45, 30)):
                p1 = (sl["x"] + math.cos(a - da) * sl["length"],
                      sl["y"] + math.sin(a - da) * sl["length"])
                p2 = (sl["x"] + math.cos(a + da) * sl["length"],
                      sl["y"] + math.sin(a + da) * sl["length"])
                pygame.draw.polygon(self.fx_surface, (*self.scheme["horizon"], alpha),
                                    [(sl["x"], sl["y"]), p1, p2])
        city.blit(self.fx_surface, (0, 0))

        # building layers, each with its billboards, beacons and traffic
        for i, layer in enumerate(self.layer_surfaces):
            city.blit(layer, (0, 0))
            for bb in self.billboards:
                if bb["layer"] == i:
                    flicker = 0.55 + 0.45 * math.sin(t * 3.1 + bb["phase"])
                    if random.random() < 0.01:      # occasional hard glitch
                        flicker *= 0.2
                    col = lerp_color(bb["bg"], bb["color"], flicker)
                    pygame.draw.rect(city, col, bb["rect"])
                    # glyph bars, like unreadable holo-adverts
                    r = bb["rect"]
                    dark = lerp_color(col, NEAR_BLACK, 0.55)
                    for gy in range(r.y + 2, r.bottom - 2, 4):
                        gw = (gy * 7 + int(bb["phase"] * 10)) % max(4, r.w - 6) + 3
                        pygame.draw.line(city, dark, (r.x + 2, gy), (r.x + 2 + gw // 2, gy))
            for car in self.traffic:
                if car.get("layer", 0) != i:
                    continue
                if car.get("is_sky"):
                    dir_mod = 1 if car["speed"] < 0 else -1
                    ex = int(car["x"])
                    sx0 = ex + int(car.get("trail", 5) * dir_mod)
                    pygame.draw.line(city, car["color"], (sx0, int(car["y"])), (ex, int(car["y"])), 1)
                    city.fill(WHITE, (ex - (1 if dir_mod > 0 else 0), int(car["y"]) - 1, 2, 2))
                else:
                    city.fill(WHITE, (int(car["x"]), int(car["y"]), 4, 2))

        # blinking rooftop beacons (in front of everything)
        for bx, by, phase in self.beacons:
            b = 0.5 + 0.5 * math.sin(t * 2.4 + phase)
            if b > 0.55:
                c = (int(255 * b), int(50 * b), int(50 * b))
                city.fill(c, (bx - 1, by - 1, 2, 2))

        # lightning
        if self.lightning_flash_alpha > 0:
            self.cached_flash_surf.fill((255, 255, 255,
                                         int(min(255, self.lightning_flash_alpha))))
            city.blit(self.cached_flash_surf, (0, 0))

        surface.blit(city, (0, 0))

        # ── water reflection ─────────────────────────────────────────────
        if self.water_h > 0:
            # mirror the WHOLE city — moon, horizon glow and beams included,
            # so the water always has something bright to show
            reflection = pygame.transform.scale(
                pygame.transform.flip(city, False, True),
                (SCREEN_WIDTH, self.water_h))
            reflection.blit(self.cached_reflection_fade, (0, 0),
                            special_flags=pygame.BLEND_MULT)
            slice_h = 6
            for y in range(0, self.water_h, slice_h):
                h = min(slice_h, self.water_h - y)
                offset_x = int(math.sin(self.reflection_timer + y * 0.13) * (2.2 + y * 0.05))
                surface.blit(reflection, (offset_x, self.city_h + y),
                             area=pygame.Rect(0, y, SCREEN_WIDTH, h))
            surface.blit(self.cached_reflection_darken_surf, (0, self.city_h))

            # neon shimmer streaks dancing on the surface
            hz = self.scheme["horizon"]
            for st in self.water_streaks:
                b = 0.5 + 0.5 * math.sin(t * st[3] + st[4])
                col = lerp_color((14, 18, 32), st[5], 0.25 + 0.6 * b)
                y = self.city_h + st[1]
                pygame.draw.line(surface, col, (st[0] - st[2] // 2, y),
                                 (st[0] + st[2] // 2, y), 1)

            # shoreline: a lit waterfront edge separating city from water
            pygame.draw.line(surface, lerp_color(hz, (255, 255, 255), 0.3),
                             (0, self.city_h), (SCREEN_WIDTH, self.city_h), 1)
            pygame.draw.line(surface, lerp_color(hz, NEAR_BLACK, 0.45),
                             (0, self.city_h + 1), (SCREEN_WIDTH, self.city_h + 1), 1)

        # ── rain overlay ─────────────────────────────────────────────────
        if self.rain_intensity > 0:
            self.cached_weather_surf.fill((0, 0, 0, 0))
            rain_color = (150, 210, 255, 150)
            wind_lag = self.wind_speed * 0.05
            for drop in self.raindrops:
                pygame.draw.line(self.cached_weather_surf, rain_color,
                                 (drop["x"], drop["y"]),
                                 (drop["x"] - wind_lag, drop["y"] - drop["length"]), 1)
            for ripple in self.water_ripples:
                prog = ripple["life"] / ripple["max_life"]
                w = 4 + 12 * prog
                rc = (150, 210, 255, int(150 * (1 - prog)))
                pygame.draw.line(self.cached_weather_surf, rc,
                                 (ripple["x"] - w / 2, ripple["y"]),
                                 (ripple["x"] + w / 2, ripple["y"]), 1)
            surface.blit(self.cached_weather_surf, (0, 0))

        # ── ticker (marquee when long) ───────────────────────────────────
        surface.blit(self.ticker_band, (0, SCREEN_HEIGHT - self.ticker_band.get_height()))
        af = self.affairs_text.get_surface()
        ay = SCREEN_HEIGHT - af.get_height() - s(12)
        if af.get_width() <= SCREEN_WIDTH - s(24):
            self.affairs_text.draw(surface, ((SCREEN_WIDTH - af.get_width()) // 2, ay))
        else:
            prev_clip = surface.get_clip()
            surface.set_clip(pygame.Rect(s(12), ay, SCREEN_WIDTH - s(24), af.get_height()))
            x0 = s(12) - int(self.ticker_scroll)
            surface.blit(af, (x0, ay))
            surface.blit(af, (x0 + af.get_width() + s(40), ay))
            surface.set_clip(prev_clip)

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        time_str = f"{mins:02d}:{secs:02d}"
        glow_c = (255, 50, 100) if mode == "work" else (50, 255, 100)
        cached = getattr(self, "_pomo_text", None)
        if not cached or cached.text != time_str or cached.glow_color != glow_c:
            font = pygame.font.Font(None, s(72))
            self._pomo_text = GlowText(font, time_str, (255, 255, 255), glow_c, 5)
        ts = self._pomo_text.get_surface()
        surface.blit(ts, ((surface.get_width() - ts.get_width()) // 2,
                          (surface.get_height() - ts.get_height()) // 2))
