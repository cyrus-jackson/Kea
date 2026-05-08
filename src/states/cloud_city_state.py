import math
import random
import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State


class CloudCityState(State):
    """Layered floating steampunk city in the clouds.

    Rendering intent: keep the draw path mostly "blit + primitives" and avoid
    per-frame allocations where practical.
    """

    def __init__(self, state_manager):
        super().__init__(state_manager)

        self.w = SCREEN_WIDTH
        self.h = SCREEN_HEIGHT

        # --- Time / motion ---
        self.t = 0.0
        self.scroll_x = 0.0

        # Slow day/night cycle (sunset -> night -> sunset)
        self.cycle_seconds = 90.0

        # --- Cached sky gradients ---
        self.sunset_sky = self._make_vertical_gradient(
            (160, 120, 70),  # warm sepia
            (70, 140, 150),  # teal haze
            self.w,
            self.h,
        )
        self.night_sky = self._make_vertical_gradient(
            (18, 22, 40),  # deep blue
            (20, 70, 90),  # teal night
            self.w,
            self.h,
        )
        self.flash_overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.overlay_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.particle_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)

        # Sun / flare
        self.sun_pos = (int(self.w * 0.78), int(self.h * 0.18))
        self.flare_surf = self._make_flare_surface(80)

        # --- Distant floating islands (static surface) ---
        self.islands_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.islands = self._generate_islands(self.islands_surf)

        # --- Cloud layers ---
        self.cloud_layers = self._generate_cloud_layers()

        # --- Parallax city layers (static; windows are separate for day/night) ---
        self.city_layers = self._generate_city_layers()

        # --- Dynamic traffic: airships + personal flyers ---
        self.airships = [self._spawn_airship(big=True) for _ in range(4)]
        self.airships += [self._spawn_airship(big=False) for _ in range(8)]

        self.flyers = [self._spawn_flyer() for _ in range(12)]

        # Birds / mechanical pigeons
        self.birds = [self._spawn_bird() for _ in range(6)]

        # --- Particles ---
        self.steam_puffs = []
        self.sparks = []
        self.steam_accum = 0.0
        self.spark_accum = 0.0
        self.max_steam = 60
        self.max_sparks = 40

        # --- Aether storms (lightning) ---
        self.lightning_timer = random.uniform(10.0, 22.0)
        self.lightning_flash = 0.0
        self.lightning_points = None

        # --- Foreground: gears + chains + flags + clock tower ---
        self.fg_gear_base = self._make_gear_surface(radius=38, teeth=14, color=(140, 105, 55))
        self.fg_gear_cache = {}
        self.fg_gear_angle = 0.0
        self.fg_gear_pos = (int(self.w * 0.18), int(self.h * 0.82))

        self.fg_gear2_base = self._make_gear_surface(radius=22, teeth=10, color=(120, 90, 50))
        self.fg_gear2_cache = {}
        self.fg_gear2_angle = 0.0
        self.fg_gear2_pos = (int(self.w * 0.34), int(self.h * 0.90))

        self.chain_phase = 0.0

    # ----- Lifecycle -----

    def enter(self):
        # Reset lightning to avoid immediate flash on entry
        self.lightning_timer = random.uniform(8.0, 18.0)
        self.lightning_flash = 0.0
        self.lightning_points = None

    def update(self, dt):
        self.t += dt
        self.scroll_x += dt * 14.0

        # Foreground motion
        self.fg_gear_angle = (self.fg_gear_angle + dt * 18.0) % 360.0
        self.fg_gear2_angle = (self.fg_gear2_angle - dt * 26.0) % 360.0
        self.chain_phase += dt * 1.1

        # Traffic
        for ship in self.airships:
            ship["x"] += ship["vx"] * dt
            ship["bob"] += dt * ship["bob_speed"]
            if ship["x"] > self.w + ship["w"]:
                ship["x"] = -ship["w"] - random.uniform(0, self.w * 0.3)
                ship["y"] = random.uniform(self.h * 0.12, self.h * 0.62)

        for flyer in self.flyers:
            flyer["x"] += flyer["vx"] * dt
            flyer["y"] += math.sin(self.t * flyer["wiggle"] + flyer["seed"]) * dt * 4.0
            if flyer["x"] > self.w + 30:
                flyer["x"] = -random.uniform(10, 120)
                flyer["y"] = random.uniform(self.h * 0.16, self.h * 0.62)

        for bird in self.birds:
            bird["x"] += bird["vx"] * dt
            bird["phase"] += dt * bird["flap"]
            if bird["x"] > self.w + 40:
                bird.update(self._spawn_bird())

        # Particles
        self._update_particles(dt)

        # Lightning (aether storm)
        self.lightning_timer -= dt
        if self.lightning_timer <= 0.0:
            self.lightning_timer = random.uniform(9.0, 22.0)
            self.lightning_flash = 1.0
            self.lightning_points = self._generate_lightning_points()

        if self.lightning_flash > 0.0:
            self.lightning_flash = max(0.0, self.lightning_flash - dt * 3.2)

    def draw(self, surface):
        night = self._night_factor()

        # Clear per-frame alpha overlays
        self.overlay_surf.fill((0, 0, 0, 0))
        self.particle_surf.fill((0, 0, 0, 0))

        # Sky base + blend to night
        surface.blit(self.sunset_sky, (0, 0))
        if night > 0.001:
            self.night_sky.set_alpha(int(255 * min(1.0, night)))
            surface.blit(self.night_sky, (0, 0))

        # Sun + lens flare (subtle at night)
        self._draw_sun_and_flare(surface, night)

        # Distant islands
        islands_x = int(-self.scroll_x * 0.08) % self.w
        self._blit_tiled(surface, self.islands_surf, -islands_x, 0)

        # Clouds (slow)
        for layer in self.cloud_layers:
            cx = int(-self.scroll_x * layer["speed"]) % layer["surf"].get_width()
            layer_surf = layer["surf"]
            # fade a bit at night
            layer_surf.set_alpha(int(layer["alpha"] * (0.75 + 0.25 * (1.0 - night))))
            self._blit_tiled(surface, layer_surf, -cx, layer["y"])

        # City layers back-to-front
        for i, layer in enumerate(self.city_layers):
            ox = int(-self.scroll_x * layer["parallax"]) % layer["w"]
            self._blit_tiled(surface, layer["buildings"], -ox, layer["y"])

            # Windows glow increases at night
            base_alpha = 30 + int(200 * night)
            flicker = int(18 * math.sin(self.t * 3.2 + (i * 1.7)))
            layer["windows"].set_alpha(max(0, min(255, base_alpha + flicker)))
            self._blit_tiled(surface, layer["windows"], -ox, layer["y"])

            # Rooftop gears (subtle)
            gear_alpha = 40 + int(80 * (1.0 - night))
            layer["gears"].set_alpha(gear_alpha)
            self._blit_tiled(surface, layer["gears"], -ox, layer["y"])

            # Put larger traffic between middle layers for depth
            if i == 1:
                self._draw_airships(surface, night)

        # Flyers in front of city
        self._draw_flyers(surface, night)

        # Steam + sparks
        self._draw_particles(surface, night)

        # Birds
        self._draw_birds(surface, night)

        # Foreground clock tower + mechanics
        self._draw_clock_tower(surface, night)
        self._draw_foreground_mechanics(surface, night)

        # Lightning flash + bolt
        if self.lightning_flash > 0.0 and self.lightning_points:
            self.flash_overlay.fill((255, 255, 255, int(140 * self.lightning_flash)))
            surface.blit(self.flash_overlay, (0, 0))
            pygame.draw.lines(surface, (230, 250, 255), False, self.lightning_points, 2)

    # ----- Sky helpers -----

    def _night_factor(self):
        cycle_pos = (self.t % self.cycle_seconds) / self.cycle_seconds
        # 0 at sunset, 1 at deep night (halfway), back to 0
        return 0.5 - 0.5 * math.cos(cycle_pos * math.tau)

    def _draw_sun_and_flare(self, surface, night):
        day_strength = 1.0 - night
        sx, sy = self.sun_pos

        # Sun disk
        sun_c = (235, 205, 140)
        pygame.draw.circle(surface, sun_c, (sx, sy), 18)
        pygame.draw.circle(surface, (255, 230, 180), (sx - 4, sy - 5), 8)

        # Flare
        alpha = int(95 * day_strength)
        if alpha > 0:
            self.flare_surf.set_alpha(alpha)
            surface.blit(self.flare_surf, (sx - 40, sy - 40))

    def _make_vertical_gradient(self, top_rgb, bottom_rgb, width, height):
        surf = pygame.Surface((width, height))
        tr, tg, tb = top_rgb
        br, bg, bb = bottom_rgb
        for y in range(height):
            t = y / max(1, height - 1)
            r = int(tr + (br - tr) * t)
            g = int(tg + (bg - tg) * t)
            b = int(tb + (bb - tb) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (width, y))
        return surf

    def _make_flare_surface(self, size):
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = size // 2
        cy = size // 2
        # Simple concentric glow
        for r in range(size // 2, 0, -1):
            a = int(110 * (r / (size / 2)) ** 2)
            pygame.draw.circle(surf, (255, 230, 180, a), (cx, cy), r)
        return surf

    # ----- Islands / clouds -----

    def _generate_islands(self, surf):
        islands = []
        for _ in range(6):
            x = random.randint(0, self.w)
            y = random.randint(int(self.h * 0.06), int(self.h * 0.38))
            rx = random.randint(22, 60)
            ry = random.randint(10, 22)
            islands.append((x, y, rx, ry))

            # Soft island body
            body = (70, 80, 85, 55)
            pygame.draw.ellipse(surf, body, (x - rx, y - ry, rx * 2, ry * 2))
            # Under-shadow
            pygame.draw.ellipse(surf, (0, 0, 0, 35), (x - rx, y - 2, rx * 2, ry * 2))
        return islands

    def _generate_cloud_layers(self):
        layers = []
        # Wide cloud strips we can tile
        for i in range(3):
            surf_w = int(self.w * 1.8)
            surf_h = int(self.h * (0.14 + i * 0.03))
            y = int(self.h * (0.06 + i * 0.12))
            alpha = 80 - i * 18
            speed = 0.05 + i * 0.07
            cloud_surf = self._make_cloud_surface(surf_w, surf_h, density=18 + i * 8)
            layers.append({"surf": cloud_surf, "y": y, "alpha": alpha, "speed": speed})
        return layers

    def _make_cloud_surface(self, width, height, density=24):
        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        base = (245, 235, 220, 35)
        highlight = (255, 255, 255, 22)
        for _ in range(density):
            x = random.randint(0, width)
            y = random.randint(0, height)
            rx = random.randint(int(height * 0.2), int(height * 0.55))
            ry = random.randint(int(height * 0.12), int(height * 0.35))
            pygame.draw.ellipse(surf, base, (x - rx, y - ry, rx * 2, ry * 2))
            pygame.draw.ellipse(surf, highlight, (x - rx + 6, y - ry - 4, rx * 2, ry * 2))
        return surf

    # ----- City layers -----

    def _generate_city_layers(self):
        layers = []
        skyline_base_y = int(self.h * 0.64)
        for i in range(4):
            parallax = 0.12 + i * 0.12
            y = skyline_base_y + i * 18

            # Create a slightly wider surface so tiling seams are less obvious
            lw = int(self.w * 1.4)
            lh = self.h
            buildings = pygame.Surface((lw, lh), pygame.SRCALPHA)
            windows = pygame.Surface((lw, lh), pygame.SRCALPHA)
            gears = pygame.Surface((lw, lh), pygame.SRCALPHA)

            self._paint_buildings(buildings, windows, gears, layer=i, base_y=y)

            layers.append(
                {
                    "buildings": buildings,
                    "windows": windows,
                    "gears": gears,
                    "parallax": parallax,
                    "y": 0,
                    "w": lw,
                }
            )
        return layers

    def _paint_buildings(self, buildings_surf, windows_surf, gears_surf, layer, base_y):
        # Palette shifts with depth
        brass = (150 - layer * 12, 110 - layer * 8, 60 - layer * 6, 255)
        iron = (70 - layer * 6, 75 - layer * 5, 80 - layer * 5, 255)
        shadow = (0, 0, 0, 28 + layer * 8)

        w = buildings_surf.get_width()
        h = buildings_surf.get_height()

        x = -10
        while x < w + 10:
            bw = random.randint(32, 64) - layer * 4
            bw = max(18, bw)
            bh = random.randint(80, 180) - layer * 18
            bh = max(45, bh)

            y_top = max(0, base_y - bh - random.randint(0, 18))

            # Main block
            pygame.draw.rect(buildings_surf, brass, (x, y_top, bw, bh))
            # Side pipe column
            if random.random() < 0.55:
                px = x + random.randint(2, max(2, bw - 8))
                pygame.draw.rect(buildings_surf, iron, (px, y_top + 10, 4, bh - 18))

            # Ornate roofline + domes
            if random.random() < 0.65:
                roof_h = random.randint(6, 14)
                pygame.draw.rect(buildings_surf, iron, (x, y_top - roof_h, bw, roof_h))
                if random.random() < 0.45:
                    dome_w = random.randint(10, max(10, bw - 8))
                    dome_h = random.randint(8, 16)
                    pygame.draw.ellipse(
                        buildings_surf,
                        iron,
                        (x + (bw - dome_w) // 2, y_top - roof_h - dome_h + 2, dome_w, dome_h),
                    )

            # Shadow wash
            pygame.draw.rect(buildings_surf, shadow, (x + 3, y_top + 3, bw, bh))

            # Glowing windows
            win_color = (255, 210, 120, 220)
            win_w = 4
            win_h = 6
            for wy in range(y_top + 14, y_top + bh - 10, win_h + 6):
                for wx in range(x + 6, x + bw - 6, win_w + 6):
                    if random.random() < 0.60:
                        pygame.draw.rect(windows_surf, win_color, (wx, wy, win_w, win_h))

            # Rooftop gear
            if random.random() < 0.35:
                gx = x + random.randint(10, max(10, bw - 10))
                gy = y_top - random.randint(6, 18)
                self._stamp_small_gear(gears_surf, gx, gy, radius=6 + layer, color=(120, 95, 55, 110))

            x += bw + random.randint(6, 18)

    def _stamp_small_gear(self, surf, cx, cy, radius, color):
        # Tiny gear: circle + teeth rectangles
        pygame.draw.circle(surf, color, (cx, cy), radius)
        teeth = 8
        for i in range(teeth):
            a = (i / teeth) * math.tau
            tx = int(cx + math.cos(a) * (radius + 2))
            ty = int(cy + math.sin(a) * (radius + 2))
            pygame.draw.rect(surf, color, (tx - 1, ty - 1, 2, 2))
        pygame.draw.circle(surf, (0, 0, 0, 60), (cx, cy), max(1, radius // 3))

    # ----- Traffic -----

    def _spawn_airship(self, big):
        scale = random.uniform(0.9, 1.2) if big else random.uniform(0.45, 0.75)
        w = 120 * scale
        x = random.uniform(-self.w, self.w)
        y = random.uniform(self.h * 0.14, self.h * 0.58)
        vx = random.uniform(10.0, 22.0) * (0.75 if big else 1.15)
        return {
            "x": x,
            "y": y,
            "vx": vx,
            "scale": scale,
            "w": w,
            "bob": random.uniform(0, math.tau),
            "bob_speed": random.uniform(0.6, 1.4),
            "seed": random.uniform(0, 9999),
        }

    def _spawn_flyer(self):
        return {
            "x": random.uniform(-self.w, self.w),
            "y": random.uniform(self.h * 0.18, self.h * 0.62),
            "vx": random.uniform(18.0, 42.0),
            "wiggle": random.uniform(3.0, 6.0),
            "seed": random.uniform(0, 9999),
        }

    def _draw_airships(self, surface, night):
        for ship in self.airships:
            x = ship["x"]
            y = ship["y"] + math.sin(ship["bob"]) * 3.0
            self._draw_airship(surface, x, y, ship["scale"], night)

    def _draw_airship(self, surface, x, y, scale, night):
        # Brass hull with teal shadow
        hull = (160, 120, 65)
        hull_dark = (85, 110, 120)
        gondola = (60, 50, 40)
        lamp = (255, 210, 120)

        w = int(90 * scale)
        h = int(18 * scale)
        rx = w // 2
        ry = h // 2

        cx = int(x)
        cy = int(y)

        pygame.draw.ellipse(surface, hull, (cx - rx, cy - ry, w, h))
        pygame.draw.ellipse(surface, hull_dark, (cx - rx, cy - ry + int(0.35 * ry), w, h))

        # Tail fin
        pygame.draw.polygon(
            surface,
            hull_dark,
            [
                (cx + rx - int(8 * scale), cy),
                (cx + rx + int(10 * scale), cy - int(6 * scale)),
                (cx + rx + int(10 * scale), cy + int(6 * scale)),
            ],
        )

        # Gondola
        gw = int(26 * scale)
        gh = int(8 * scale)
        pygame.draw.rect(surface, gondola, (cx - gw // 2, cy + ry - int(2 * scale), gw, gh), border_radius=3)

        # Propeller
        px = cx - rx + int(10 * scale)
        pygame.draw.line(surface, (30, 30, 30), (px, cy), (px - int(10 * scale), cy), 1)
        pygame.draw.line(surface, (30, 30, 30), (px - int(5 * scale), cy - int(4 * scale)), (px - int(5 * scale), cy + int(4 * scale)), 1)

        # Lamps (brighter at night)
        if night > 0.15:
            pygame.draw.circle(surface, lamp, (cx - int(10 * scale), cy + int(2 * scale)), max(1, int(2 * scale)))

    def _draw_flyers(self, surface, night):
        c = (190, 170, 130) if night < 0.6 else (140, 190, 200)
        for f in self.flyers:
            x = int(f["x"])
            y = int(f["y"])
            pygame.draw.line(surface, c, (x, y), (x - 6, y + 2), 1)
            pygame.draw.line(surface, c, (x, y), (x - 6, y - 2), 1)
            if night > 0.4 and random.random() < 0.06:
                pygame.draw.circle(surface, (255, 220, 140), (x, y), 1)

    # ----- Birds -----

    def _spawn_bird(self):
        return {
            "x": random.uniform(-40, self.w),
            "y": random.uniform(self.h * 0.08, self.h * 0.32),
            "vx": random.uniform(14.0, 24.0),
            "flap": random.uniform(3.0, 5.0),
            "phase": random.uniform(0, math.tau),
        }

    def _draw_birds(self, surface, night):
        c = (40, 40, 40) if night < 0.5 else (160, 200, 210)
        for b in self.birds:
            x = int(b["x"])
            y = int(b["y"])
            flap = 2 + int(1.5 * math.sin(b["phase"]))
            pygame.draw.line(surface, c, (x, y), (x - 5, y - flap), 1)
            pygame.draw.line(surface, c, (x, y), (x + 5, y - flap), 1)

    # ----- Particles -----

    def _update_particles(self, dt):
        # Rising steam puffs from rooftops
        self.steam_accum += dt
        while self.steam_accum >= 0.12:
            self.steam_accum -= 0.12
            if len(self.steam_puffs) < self.max_steam:
                self._spawn_steam()

        # Occasional sparks
        self.spark_accum += dt
        while self.spark_accum >= 0.25:
            self.spark_accum -= 0.25
            if len(self.sparks) < self.max_sparks and random.random() < 0.55:
                self._spawn_spark()

        # Integrate steam
        for p in self.steam_puffs:
            p["life"] -= dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] -= dt * 2.0
            p["r"] += dt * 5.5

        # Integrate sparks
        for s in self.sparks:
            s["life"] -= dt
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["vy"] += dt * 38.0

        # Cull in-place (avoid per-frame list allocations)
        if self.steam_puffs:
            write = 0
            for p in self.steam_puffs:
                if p["life"] > 0.0 and p["y"] > -30:
                    self.steam_puffs[write] = p
                    write += 1
            del self.steam_puffs[write:]
        if self.sparks:
            write = 0
            for s in self.sparks:
                if s["life"] > 0.0 and s["y"] < self.h + 30:
                    self.sparks[write] = s
                    write += 1
            del self.sparks[write:]

    def _spawn_steam(self):
        x = random.uniform(0, self.w)
        y = random.uniform(self.h * 0.46, self.h * 0.72)
        self.steam_puffs.append(
            {
                "x": x,
                "y": y,
                "vx": random.uniform(-6.0, 6.0),
                "vy": random.uniform(-16.0, -6.0),
                "r": random.uniform(3.0, 7.0),
                "life": random.uniform(1.2, 2.4),
            }
        )

    def _spawn_spark(self):
        x = random.uniform(self.w * 0.20, self.w * 0.85)
        y = random.uniform(self.h * 0.52, self.h * 0.80)
        self.sparks.append(
            {
                "x": x,
                "y": y,
                "vx": random.uniform(-18.0, 18.0),
                "vy": random.uniform(-32.0, -10.0),
                "life": random.uniform(0.25, 0.75),
            }
        )

    def _draw_particles(self, surface, night):
        steam_c = (230, 230, 235)
        for p in self.steam_puffs:
            a = int(55 * (p["life"] / 2.4))
            pygame.draw.circle(self.particle_surf, (*steam_c, a), (int(p["x"]), int(p["y"])), int(p["r"]))

        spark_c = (255, 210, 120) if night < 0.7 else (180, 240, 255)
        for s in self.sparks:
            a = int(255 * (s["life"] / 0.75))
            pygame.draw.circle(self.particle_surf, (*spark_c, a), (int(s["x"]), int(s["y"])), 1)

        surface.blit(self.particle_surf, (0, 0))

    # ----- Lightning -----

    def _generate_lightning_points(self):
        # Bolt between two cloud bands
        x0 = random.randint(int(self.w * 0.18), int(self.w * 0.82))
        y0 = random.randint(int(self.h * 0.10), int(self.h * 0.24))
        x1 = x0 + random.randint(-40, 40)
        y1 = random.randint(int(self.h * 0.32), int(self.h * 0.52))

        pts = [(x0, y0)]
        segments = 8
        for i in range(1, segments):
            t = i / segments
            x = int(x0 + (x1 - x0) * t + random.randint(-10, 10))
            y = int(y0 + (y1 - y0) * t + random.randint(-6, 12))
            pts.append((x, y))
        pts.append((x1, y1))
        return pts

    # ----- Foreground -----

    def _draw_clock_tower(self, surface, night):
        # Big central clock tower with gas lamps
        x = int(self.w * 0.58)
        y_base = int(self.h * 0.92)
        tower_w = int(self.w * 0.22)
        tower_h = int(self.h * 0.46)
        y_top = y_base - tower_h

        brass = (150, 110, 60)
        brass_dark = (95, 75, 45)
        teal_shadow = (30, 70, 85, 60)

        pygame.draw.rect(surface, brass, (x - tower_w // 2, y_top, tower_w, tower_h), border_radius=6)
        pygame.draw.rect(surface, brass_dark, (x - tower_w // 2, y_top + 10, tower_w, 10))
        pygame.draw.rect(surface, teal_shadow, (x - tower_w // 2 + 3, y_top + 3, tower_w, tower_h))

        # Roof
        pygame.draw.polygon(
            surface,
            brass_dark,
            [(x - tower_w // 2, y_top + 8), (x + tower_w // 2, y_top + 8), (x, y_top - 26)],
        )

        # Clock face
        face_r = int(tower_w * 0.32)
        face_y = y_top + int(tower_h * 0.30)
        pygame.draw.circle(surface, (225, 210, 175), (x, face_y), face_r)
        pygame.draw.circle(surface, (80, 60, 40), (x, face_y), face_r, 2)

        # Clock ticks
        for i in range(12):
            a = i / 12.0 * math.tau
            tx0 = x + int(math.cos(a) * (face_r - 2))
            ty0 = face_y + int(math.sin(a) * (face_r - 2))
            tx1 = x + int(math.cos(a) * (face_r - 7))
            ty1 = face_y + int(math.sin(a) * (face_r - 7))
            pygame.draw.line(surface, (70, 50, 35), (tx0, ty0), (tx1, ty1), 1)

        # Hands (based on global time)
        minute = (self.t * 0.15) % math.tau
        hour = (self.t * 0.02) % math.tau
        self._draw_hand(surface, x, face_y, hour, int(face_r * 0.55), 2)
        self._draw_hand(surface, x, face_y, minute, int(face_r * 0.80), 1)
        pygame.draw.circle(surface, (70, 50, 35), (x, face_y), 2)

        # Gas lamps at night
        if night > 0.2:
            lamp_alpha = int(110 + 120 * night)
            pygame.draw.circle(self.overlay_surf, (255, 220, 150, lamp_alpha), (x - tower_w // 2 + 6, y_base - 10), 3)
            pygame.draw.circle(self.overlay_surf, (255, 220, 150, lamp_alpha), (x + tower_w // 2 - 6, y_base - 10), 3)
            surface.blit(self.overlay_surf, (0, 0))

    def _draw_hand(self, surface, cx, cy, angle, length, thickness):
        x1 = cx + int(math.cos(angle - math.pi / 2) * length)
        y1 = cy + int(math.sin(angle - math.pi / 2) * length)
        pygame.draw.line(surface, (60, 45, 30), (cx, cy), (x1, y1), thickness)

    def _draw_foreground_mechanics(self, surface, night):
        # Gears (cached rotation by quantized angle)
        g1 = self._get_rotated_gear(self.fg_gear_base, self.fg_gear_cache, self.fg_gear_angle)
        surface.blit(g1, (self.fg_gear_pos[0] - g1.get_width() // 2, self.fg_gear_pos[1] - g1.get_height() // 2))

        g2 = self._get_rotated_gear(self.fg_gear2_base, self.fg_gear2_cache, self.fg_gear2_angle)
        surface.blit(g2, (self.fg_gear2_pos[0] - g2.get_width() // 2, self.fg_gear2_pos[1] - g2.get_height() // 2))

        # Chains (swaying)
        chain_c = (60, 55, 50)
        x0 = int(self.w * 0.05)
        y0 = int(self.h * 0.02)
        x1 = int(self.w * 0.12)
        y1 = int(self.h * 0.65)
        sway = int(6 * math.sin(self.chain_phase))
        pygame.draw.line(surface, chain_c, (x0 + sway, y0), (x1 - sway, y1), 2)

        # Hanging links
        for i in range(10):
            t = i / 10
            lx = int((x0 + sway) + (x1 - sway - (x0 + sway)) * t)
            ly = int(y0 + (y1 - y0) * t)
            pygame.draw.circle(surface, (40, 40, 40), (lx, ly), 2)

        # Flags
        pole_x = int(self.w * 0.86)
        pole_y0 = int(self.h * 0.42)
        pole_y1 = int(self.h * 0.70)
        pygame.draw.line(surface, (55, 45, 35), (pole_x, pole_y0), (pole_x, pole_y1), 2)

        flap = int(6 * math.sin(self.chain_phase * 2.0))
        flag = [(pole_x, pole_y0 + 10), (pole_x + 22, pole_y0 + 16 + flap), (pole_x, pole_y0 + 22)]
        pygame.draw.polygon(surface, (140, 40, 35), flag)

        # Subtle vignette at night
        if night > 0.5:
            self.overlay_surf.fill((0, 0, 0, int(55 * (night - 0.5))))
            surface.blit(self.overlay_surf, (0, 0))

    def _make_gear_surface(self, radius, teeth, color):
        size = radius * 2 + 10
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = size // 2
        cy = size // 2

        # Teeth
        for i in range(teeth):
            a = i / teeth * math.tau
            tx = cx + int(math.cos(a) * (radius + 3))
            ty = cy + int(math.sin(a) * (radius + 3))
            pygame.draw.rect(surf, color, (tx - 3, ty - 3, 6, 6))

        # Main gear
        pygame.draw.circle(surf, color, (cx, cy), radius)
        pygame.draw.circle(surf, (0, 0, 0, 90), (cx, cy), max(2, radius // 3))
        pygame.draw.circle(surf, (0, 0, 0, 90), (cx, cy), radius, 2)
        return surf

    def _get_rotated_gear(self, base, cache, angle_degrees):
        # Quantize to reduce unique rotated surfaces
        q = int(angle_degrees // 6) * 6
        surf = cache.get(q)
        if surf is None:
            surf = pygame.transform.rotate(base, q)
            cache[q] = surf
        return surf

    # ----- Blit helper -----

    def _blit_tiled(self, target, tile_surf, x, y):
        # Blit a surface repeatedly to cover the screen width.
        tw = tile_surf.get_width()
        target.blit(tile_surf, (x, y))
        if x + tw < self.w:
            target.blit(tile_surf, (x + tw, y))
        if x > 0:
            target.blit(tile_surf, (x - tw, y))
