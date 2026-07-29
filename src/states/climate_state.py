import pygame
import random
import math
from states.base_state import State
from backend.weather_api import fetch_stuttgart_weather
from ui.glow_text import GlowText
from ui import pixel_art
from config import SCREEN_WIDTH, SCREEN_HEIGHT
from current_affairs import CurrentAffairs

# --- Cyberpunk palette ---
SKY_TOP = (8, 6, 24)
SKY_BOTTOM = (46, 12, 62)
HORIZON_GLOW = (255, 60, 160)
NEON_CYAN = (0, 235, 255)
NEON_MAGENTA = (255, 60, 180)
NEON_AMBER = (255, 176, 40)
DIM_PURPLE = (26, 12, 44)
SKYLINE = (16, 8, 30)
WINDOW_COLORS = [(0, 235, 255), (255, 60, 180), (255, 176, 40)]

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    """Scale a design-space (320x480) value to the actual resolution."""
    return max(1, int(v * SCALE))


class ClimateState(State):
    def __init__(self, manager):
        super().__init__(manager)
        self.current_affairs = CurrentAffairs()
        self.weather_data = None
        self.loading = True
        self.fahrenheit = False

        pygame.font.init()
        self.font_header = pygame.font.Font(None, s(22))
        self.font_big = pygame.font.Font(None, s(96))
        self.font_status = pygame.font.Font(None, s(24))
        self.font_col = pygame.font.Font(None, s(18))

        self.header_text = GlowText(self.font_header, "STUTTGART // WX.SYS",
                                    NEON_CYAN, (0, 90, 110), glow_radius=2)
        self.temp_text = None      # built when data arrives
        self.status_text = None
        self.loading_text = GlowText(self.font_status, "SYNCING SATELLITE LINK",
                                     NEON_CYAN, (0, 90, 110), glow_radius=2)

        # Pre-rendered static layers (build once — keep the Pi at 30 fps)
        self.bg_surface = self._build_background()
        self.scanlines = self._build_scanlines()
        self.sun_surface = self._build_synthwave_sun(s(72))
        self.forecast_panel = None  # built when data arrives

        # Night sky stars: (x, y, phase, size)
        self.stars = [(random.randint(0, SCREEN_WIDTH),
                       random.randint(0, int(SCREEN_HEIGHT * 0.45)),
                       random.uniform(0, math.tau),
                       random.choice([1, 1, 2]))
                      for _ in range(26)]

        self.animation_timer = 0.0
        self.glitch_timer = 0.0
        self.glitch_active = 0.0
        self.particles = []

    # ------------------------------------------------------------------
    # Static layer builders
    # ------------------------------------------------------------------
    def _build_background(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        horizon = int(SCREEN_HEIGHT * 0.70)
        # vertical gradient sky
        for y in range(horizon):
            t = y / max(1, horizon - 1)
            c = [int(SKY_TOP[i] + (SKY_BOTTOM[i] - SKY_TOP[i]) * t) for i in range(3)]
            pygame.draw.line(surf, c, (0, y), (SCREEN_WIDTH, y))
        # below horizon: near-black ground for the skyline + forecast panel
        pygame.draw.rect(surf, DIM_PURPLE, (0, horizon, SCREEN_WIDTH, SCREEN_HEIGHT - horizon))
        # glowing horizon line (stacked translucent strips)
        for w, a in [(4, 40), (2, 90), (1, 255)]:
            line = pygame.Surface((SCREEN_WIDTH, w * 2), pygame.SRCALPHA)
            line.fill((HORIZON_GLOW[0], HORIZON_GLOW[1], HORIZON_GLOW[2], a))
            surf.blit(line, (0, horizon - w))
        self._draw_skyline(surf, horizon)
        self._draw_brackets(surf)
        return surf

    def _draw_skyline(self, surf, horizon):
        rng = random.Random(9)  # fixed seed -> stable skyline
        x = 0
        while x < SCREEN_WIDTH:
            w = rng.randint(s(14), s(34))
            h = rng.randint(s(20), s(78))
            rect = pygame.Rect(x, horizon - h, w, h)
            pygame.draw.rect(surf, SKYLINE, rect)
            # a few lit windows
            for _ in range(rng.randint(1, 4)):
                wx = rect.x + rng.randint(2, max(3, w - 4))
                wy = rect.y + rng.randint(3, max(4, h - 5))
                if 0 <= wx < SCREEN_WIDTH and 0 <= wy < SCREEN_HEIGHT:
                    surf.set_at((wx, wy), rng.choice(WINDOW_COLORS))
            # antenna on some towers
            if rng.random() < 0.3:
                ax = min(rect.centerx, SCREEN_WIDTH - 1)
                pygame.draw.line(surf, SKYLINE, (ax, rect.y), (ax, rect.y - s(10)))
                if rect.y - s(10) >= 0:
                    surf.set_at((ax, rect.y - s(10)), NEON_MAGENTA)
            x += w + rng.randint(2, s(8))

    def _draw_brackets(self, surf):
        m, l, t = s(6), s(16), 2
        for cx, cy, dx, dy in [(m, m, 1, 1), (SCREEN_WIDTH - m, m, -1, 1),
                               (m, SCREEN_HEIGHT - m, 1, -1),
                               (SCREEN_WIDTH - m, SCREEN_HEIGHT - m, -1, -1)]:
            pygame.draw.line(surf, NEON_CYAN, (cx, cy), (cx + dx * l, cy), t)
            pygame.draw.line(surf, NEON_CYAN, (cx, cy), (cx, cy + dy * l), t)

    def _build_scanlines(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for y in range(0, SCREEN_HEIGHT, 3):
            pygame.draw.line(surf, (0, 0, 0, 38), (0, y), (SCREEN_WIDTH, y))
        return surf

    def _build_synthwave_sun(self, radius):
        """Retro sun: amber->magenta gradient disc with slice cuts low down."""
        size = radius * 2
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for y in range(size):
            t = y / max(1, size - 1)
            c = [int(NEON_AMBER[i] + (NEON_MAGENTA[i] - NEON_AMBER[i]) * t) for i in range(3)]
            half = int(math.sqrt(max(0, radius * radius - (y - radius) ** 2)))
            if half > 0:
                pygame.draw.line(surf, c, (radius - half, y), (radius + half, y))
        # transparent slice cuts, widening toward the bottom
        gap, y = 2, int(size * 0.55)
        while y < size:
            surf.fill((0, 0, 0, 0), (0, y, size, gap))
            y += gap + s(7)
            gap += 1
        return surf

    def _build_forecast_panel(self, columns):
        """Neon bar gauges for the hourly forecast, pre-rendered once."""
        panel_h = int(SCREEN_HEIGHT * 0.24)
        surf = pygame.Surface((SCREEN_WIDTH, panel_h), pygame.SRCALPHA)
        surf.fill((10, 6, 22, 200))
        pygame.draw.line(surf, NEON_CYAN, (0, 0), (SCREEN_WIDTH, 0), 1)
        if not columns:
            return surf
        col_w = SCREEN_WIDTH // len(columns)
        bar_max = panel_h - s(62)
        for i, col in enumerate(columns):
            cx = i * col_w + col_w // 2
            precip = max(0, min(100, int(col.get("precip") or 0)))
            # bar color: cyan (dry) -> magenta (wet)
            t = precip / 100.0
            bc = [int(NEON_CYAN[j] + (NEON_MAGENTA[j] - NEON_CYAN[j]) * t) for j in range(3)]
            bh = max(2, int(bar_max * t))
            bar = pygame.Rect(cx - s(5), s(24) + (bar_max - bh), s(10), bh)
            glow = pygame.Surface((bar.width + s(6), bar.height + s(6)), pygame.SRCALPHA)
            glow.fill((bc[0], bc[1], bc[2], 60))
            surf.blit(glow, (bar.x - s(3), bar.y - s(3)))
            pygame.draw.rect(surf, bc, bar)
            pygame.draw.rect(surf, (90, 60, 120), (cx - s(5), s(24), s(10), bar_max), 1)
            hour = self.font_col.render(col["hour"], True, (170, 160, 200))
            surf.blit(hour, hour.get_rect(center=(cx, s(12))))
            temp = self.font_col.render(f"{round(col['temp'])}°", True, (240, 240, 255))
            surf.blit(temp, temp.get_rect(center=(cx, panel_h - s(24))))
            pr = self.font_col.render(f"{precip}%", True, bc)
            surf.blit(pr, pr.get_rect(center=(cx, panel_h - s(9))))
        return surf

    # ------------------------------------------------------------------
    # State lifecycle
    # ------------------------------------------------------------------
    def enter(self):
        self.loading = True
        self.particles = []
        fetch_stuttgart_weather(self._on_weather_fetched)

    def _on_weather_fetched(self, data):
        self.weather_data = data
        self.loading = False
        if data.get("error"):
            self.status_text = GlowText(self.font_status, "LINK ERROR // RETRYING SOON",
                                        NEON_MAGENTA, (110, 20, 70), glow_radius=2)
            return

        temp = data.get("temp", "?")
        rain_chance = data.get("rain_chance", 0)
        umbrella = "UMBRELLA: YES" if data.get("needs_umbrella") else "UMBRELLA: NO"
        try:
            _t = float(temp)
            if getattr(self, "fahrenheit", False):
                _t = _t * 9 / 5 + 32
            temp_str = f"{round(_t)}°"
        except (TypeError, ValueError):
            temp_str = "--°"

        self.temp_text = GlowText(self.font_big, temp_str,
                                  (245, 240, 255), NEON_CYAN, glow_radius=3)
        self.status_text = GlowText(self.font_status,
                                    f"RAIN {rain_chance}%  //  {umbrella}",
                                    NEON_AMBER, (120, 70, 10), glow_radius=2)
        self.forecast_panel = self._build_forecast_panel(data.get("forecast_columns", []))

        status = f"RAIN {rain_chance}%" if rain_chance > 20 else "CLEAR"
        message = f"STUTTGART WEATHER UPDATE: {temp}C, {status}."
        if hasattr(self.current_affairs, 'add_important_message'):
            self.current_affairs.add_important_message(message)

        self._init_particles()

    def _init_particles(self):
        self.particles = []
        if self.weather_data and self.weather_data.get("needs_umbrella"):
            for _ in range(46):
                self.particles.append([
                    random.randint(0, SCREEN_WIDTH),
                    random.randint(0, SCREEN_HEIGHT),
                    random.uniform(240, 420),          # speed
                    random.randint(s(8), s(18)),       # length
                    NEON_MAGENTA if random.random() < 0.12 else NEON_CYAN,
                ])

    def on_toggle(self, on):
        """Toggle: read temperatures in Fahrenheit."""
        self.fahrenheit = on
        if self.weather_data and not self.weather_data.get("error"):
            self._on_weather_fetched(self.weather_data)   # re-render readouts

    def toggle_label(self):
        return "DEG F"

    def update(self, dt):
        self.animation_timer += dt

        # occasional glitch on the big temperature readout
        self.glitch_timer -= dt
        if self.glitch_timer <= 0:
            self.glitch_active = 0.12
            self.glitch_timer = random.uniform(2.5, 6.0)
        if self.glitch_active > 0:
            self.glitch_active -= dt

        if self.weather_data and not self.loading and not self.weather_data.get("error"):
            if self.weather_data.get("needs_umbrella"):
                for p in self.particles:
                    p[1] += p[2] * dt
                    p[0] += 60 * dt
                    if p[1] > SCREEN_HEIGHT:
                        p[1] = -p[3]
                        p[0] = random.randint(-50, SCREEN_WIDTH)

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------
    def draw(self, surface):
        surface.blit(self.bg_surface, (0, 0))

        if self.loading:
            self._draw_loading(surface)
            surface.blit(self.scanlines, (0, 0))
            return

        data = self.weather_data or {}
        if not data.get("error"):
            if data.get("is_day"):
                self._draw_sun(surface)
            else:
                self._draw_night(surface)

            if data.get("needs_umbrella"):
                for p in self.particles:
                    pygame.draw.line(surface, p[4], (int(p[0]), int(p[1])),
                                     (int(p[0] + 4), int(p[1] + p[3])), 1)

            # pixel-art sky icon beside the temperature, picked from the
            # live conditions (rain / snow / storm / cloud / sun / moon)
            icon = pixel_art.weather_sprite(
                data.get("description") or data.get("status")
                or ("night" if not data.get("is_day") else "clear"))
            ipx = max(2, int(3 * SCALE))
            iw, ih = icon.size(ipx)
            pixel_art.draw(surface, icon, s(14), int(SCREEN_HEIGHT * 0.17), ipx)

            if self.temp_text:
                tw = self.temp_text.get_surface()
                tx = (SCREEN_WIDTH - tw.get_width()) // 2
                ty = int(SCREEN_HEIGHT * 0.16)
                if self.glitch_active > 0:
                    surface.blit(tw, (tx + s(3), ty))
                    surface.blit(tw, (tx - s(3), ty + 2))
                else:
                    surface.blit(tw, (tx, ty))

            if self.forecast_panel:
                surface.blit(self.forecast_panel,
                             (0, SCREEN_HEIGHT - self.forecast_panel.get_height()))

        # header + status
        self.header_text.draw(surface, (s(12), s(10)))
        if self.status_text:
            st = self.status_text.get_surface()
            surface.blit(st, ((SCREEN_WIDTH - st.get_width()) // 2,
                              int(SCREEN_HEIGHT * 0.42)))

        surface.blit(self.scanlines, (0, 0))

    def _draw_loading(self, surface):
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        r = s(24)
        pygame.draw.circle(surface, (40, 30, 70), (cx, cy), r, 2)
        a0 = self.animation_timer * 5
        pygame.draw.arc(surface, NEON_CYAN, (cx - r, cy - r, r * 2, r * 2), a0, a0 + 1.8, 3)
        dots = "." * (int(self.animation_timer * 2) % 4)
        self.loading_text.update_text(f"SYNCING SATELLITE LINK{dots}")
        lt = self.loading_text.get_surface()
        surface.blit(lt, ((SCREEN_WIDTH - lt.get_width()) // 2, cy + r + s(14)))
        self.header_text.draw(surface, (s(12), s(10)))

    def _draw_sun(self, surface):
        bob = math.sin(self.animation_timer * 0.6) * s(3)
        x = (SCREEN_WIDTH - self.sun_surface.get_width()) // 2
        y = int(SCREEN_HEIGHT * 0.30 + bob) - self.sun_surface.get_height() // 2
        surface.blit(self.sun_surface, (x, y))

    def _draw_night(self, surface):
        # twinkling stars
        for sx, sy, phase, size in self.stars:
            a = 0.5 + 0.5 * math.sin(self.animation_timer * 1.4 + phase)
            c = int(120 + 120 * a)
            pygame.draw.circle(surface, (c, c, min(255, c + 30)), (sx, sy), size)
        # neon crescent moon
        cx, cy = int(SCREEN_WIDTH * 0.72), int(SCREEN_HEIGHT * 0.30)
        r = s(26)
        pygame.draw.circle(surface, (210, 230, 255), (cx, cy), r)
        pygame.draw.circle(surface, (60, 70, 120), (cx - s(9), cy - s(4)), r - s(4))
        pygame.draw.circle(surface, NEON_CYAN, (cx, cy), r, 1)
