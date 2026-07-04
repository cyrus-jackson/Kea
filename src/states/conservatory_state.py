"""
conservatory_state.py
---------------------
SOLARPUNK CONSERVATORY — a living ambient screen.

A rooftop glasshouse: procedural vines grow in real time (stems creep,
leaves sprout, flowers bloom) against a sky that follows the actual time
of day. Pollen motes drift by day; fireflies wander at night. A copper
SOLAR YIELD dial tracks the sun and the planter box carries the current
System Protocol dispatch.

The garden fills over ~10 minutes, is gently pruned, and regrows —
never the same twice. Growth is drawn incrementally onto a persistent
surface, so the per-frame cost stays tiny on the Pi.
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


# ── Palette ──────────────────────────────────────────────────────────────────
MULLION      = (108, 156, 132)   # weathered copper frame
MULLION_DARK = ( 62, 100,  82)
VERDIGRIS    = (148, 196, 168)
WOOD         = ( 96,  66,  40)
WOOD_DARK    = ( 66,  44,  26)
CREAM        = (240, 232, 200)
DIAL_FACE    = ( 44,  58,  46)
COPPER       = (188, 118,  58)
STEM_GREENS  = [(58, 118, 58), (74, 138, 64), (92, 158, 72)]
LEAF_GREENS  = [(88, 160, 72), (110, 182, 84), (132, 200, 96), (70, 140, 66)]
FLOWERS      = [(238, 182, 66), (228, 122, 148), (156, 124, 220),
                (242, 240, 218), (232, 150, 90)]

# Sky keyframes: hour -> (top colour, bottom colour)
SKY_KEYS = [
    (0.0,  (10, 14, 34),   (24, 30, 56)),
    (5.0,  (16, 20, 46),   (60, 44, 70)),
    (7.0,  (86, 110, 150), (238, 168, 120)),
    (12.0, (110, 170, 210),(196, 226, 214)),
    (17.0, (96, 140, 190), (240, 190, 130)),
    (20.0, (36, 40, 84),   (180, 100, 90)),
    (22.0, (12, 16, 38),   (40, 40, 70)),
    (24.0, (10, 14, 34),   (24, 30, 56)),
]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _sky_colors(hour_f):
    for i in range(len(SKY_KEYS) - 1):
        h0, top0, bot0 = SKY_KEYS[i]
        h1, top1, bot1 = SKY_KEYS[i + 1]
        if h0 <= hour_f <= h1:
            t = (hour_f - h0) / max(0.001, h1 - h0)
            return _lerp(top0, top1, t), _lerp(bot0, bot1, t)
    return SKY_KEYS[0][1], SKY_KEYS[0][2]


class ConservatoryState(State):
    """Solarpunk glasshouse with a garden that grows in real time."""

    GROW_TICK   = 0.28     # seconds between growth steps
    MAX_TIPS    = 7
    PRUNE_HOLD  = 25.0     # seconds to admire the full garden before pruning

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.current_affairs = CurrentAffairs()

        self.font_title = pygame.font.Font(None, s(24))
        self.font_label = pygame.font.Font(None, s(15))
        self.font_sign  = pygame.font.Font(None, s(17))

        # layout
        self.shelf_y = SCREEN_HEIGHT - s(86)          # top of planter box
        self.sky_rect = pygame.Rect(0, 0, SCREEN_WIDTH, self.shelf_y)

        # pre-rendered static layers
        self._frame_surf = self._build_frame()

        # dynamic sky cache (rebuilt once a minute)
        self._sky_surf = pygame.Surface(self.sky_rect.size)
        self._sky_minute = -1

        # persistent garden canvas
        self.plant_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.tips = []
        self.grow_timer = 0.0
        self.prune_timer = 0.0
        self.pruning = False
        self.generation = 1
        self._seed_garden()

        # ambience particles: [x, y, phase, speed]
        self.motes = [[random.uniform(0, SCREEN_WIDTH), random.uniform(s(40), self.shelf_y),
                       random.uniform(0, math.tau), random.uniform(4, 10) * SCALE]
                      for _ in range(14)]

        # clouds: [x, y, speed, sprite]
        self.clouds = []
        for i in range(3):
            cw, ch = s(90 + 30 * i), s(30 + 10 * i)
            sprite = pygame.Surface((int(cw * 1.5), ch * 2), pygame.SRCALPHA)
            for dx, dy, rw in [(cw * 0.25, ch * 0.5, cw), (0, ch * 0.85, cw * 0.55),
                               (cw * 0.55, ch * 0.85, cw * 0.55)]:
                pygame.draw.ellipse(sprite, (240, 242, 245, 120),
                                    (int(dx), int(dy), int(rw), ch))
            self.clouds.append([random.uniform(0, SCREEN_WIDTH), s(46 + 42 * i),
                                (6 - i * 2) * SCALE, sprite])

        self.time_alive = 0.0
        self.sign_text = self.current_affairs.get_current_message()

    # ══════════════════════════════════════════════════════════════════════
    # Static frame: greenhouse mullions, glass glare, planter box, dial face
    # ══════════════════════════════════════════════════════════════════════
    def _build_frame(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        w, sh = SCREEN_WIDTH, self.shelf_y

        # glass glare streaks (behind mullions)
        for i in range(4):
            x0 = s(30) + i * s(85)
            pts = [(x0, 0), (x0 + s(26), 0), (x0 - s(50), sh), (x0 - s(76), sh)]
            pygame.draw.polygon(surf, (255, 255, 255, 13), pts)

        # arched roof ribs
        arch_h = s(64)
        pygame.draw.arc(surf, MULLION, (-s(20), -arch_h, w + s(40), arch_h * 2), 0, math.pi, s(5))
        for fx in (w // 4, w // 2, 3 * w // 4):
            # rib from arch down — approximate arch y at fx
            rel = abs(fx - w / 2) / (w / 2 + s(20))
            ay = int(arch_h * (1 - math.sqrt(max(0.0, 1 - rel * rel)))) + s(2)
            pygame.draw.line(surf, MULLION, (fx, ay), (fx, sh), s(4))
            pygame.draw.line(surf, MULLION_DARK, (fx + s(2), ay), (fx + s(2), sh), 1)
        # horizontal glazing bars
        for gy in (s(150), s(255)):
            pygame.draw.line(surf, MULLION, (0, gy), (w, gy), s(3))
            pygame.draw.line(surf, MULLION_DARK, (0, gy + s(2)), (w, gy + s(2)), 1)
        # side posts
        pygame.draw.rect(surf, MULLION, (0, 0, s(6), sh))
        pygame.draw.rect(surf, MULLION, (w - s(6), 0, s(6), sh))
        # finial
        pygame.draw.circle(surf, VERDIGRIS, (w // 2, s(6)), s(5))

        # ── planter box / shelf ─────────────────────────────────────────
        pygame.draw.rect(surf, WOOD, (0, sh, w, SCREEN_HEIGHT - sh))
        pygame.draw.rect(surf, WOOD_DARK, (0, sh, w, s(7)))
        pygame.draw.line(surf, (130, 92, 56), (0, sh + s(7)), (w, sh + s(7)), 1)
        # plank seams
        for px in range(s(40), w, s(64)):
            pygame.draw.line(surf, WOOD_DARK, (px, sh + s(10)), (px, SCREEN_HEIGHT), 1)
        # title plaque
        plaque = pygame.Rect(w // 2 - s(88), sh + s(12), s(176), s(22))
        pygame.draw.rect(surf, WOOD_DARK, plaque, border_radius=s(4))
        pygame.draw.rect(surf, COPPER, plaque, 1, border_radius=s(4))
        t = self.font_title.render("CONSERVATORY", True, VERDIGRIS)
        surf.blit(t, t.get_rect(center=plaque.center))

        # dial face (needle drawn per-frame)
        cx, cy, r = self._dial_pos()
        pygame.draw.circle(surf, COPPER, (cx, cy), r + s(3))
        pygame.draw.circle(surf, WOOD_DARK, (cx, cy), r + s(3), 2)
        pygame.draw.circle(surf, DIAL_FACE, (cx, cy), r)
        for i in range(9):
            a = math.radians(-200 + i * 27.5)
            pygame.draw.line(surf, VERDIGRIS,
                             (cx + (r - s(4)) * math.cos(a), cy + (r - s(4)) * math.sin(a)),
                             (cx + (r - s(7)) * math.cos(a), cy + (r - s(7)) * math.sin(a)), 1)
        lbl = self.font_label.render("SOLAR YIELD", True, VERDIGRIS)
        surf.blit(lbl, (cx - lbl.get_width() // 2, cy + r + s(5)))
        return surf

    def _dial_pos(self):
        return SCREEN_WIDTH - s(46), SCREEN_HEIGHT - s(38), s(22)

    # ══════════════════════════════════════════════════════════════════════
    # Garden growth
    # ══════════════════════════════════════════════════════════════════════
    def _seed_garden(self):
        """Plant 3-4 seedlings in the planter box."""
        self.tips = []
        for _ in range(random.randint(3, 4)):
            x = random.uniform(s(30), SCREEN_WIDTH - s(30))
            self.tips.append({
                "x": x, "y": float(self.shelf_y + s(4)),
                "angle": -math.pi / 2 + random.uniform(-0.3, 0.3),
                "energy": random.randint(220, 380),
                "step": random.uniform(2.2, 3.2) * SCALE,
                "wander": random.uniform(0.8, 1.3),
                "phase": random.uniform(0, math.tau),
                "n": 0,
                "green": random.choice(STEM_GREENS),
            })

    def _grow_step(self):
        """Advance every living tip one segment on the persistent canvas."""
        new_tips = []
        for tip in self.tips:
            if tip["energy"] <= 0:
                # bloom at the spent tip
                self._draw_flower(tip["x"], tip["y"])
                continue
            tip["n"] += 1
            tip["energy"] -= 1
            # meander with an upward bias
            sway = math.sin(tip["n"] * 0.35 + tip["phase"]) * tip["wander"]
            tip["angle"] += sway * 0.22 + random.uniform(-0.08, 0.08)
            # ease back toward "up" so vines don't nosedive
            tip["angle"] += (-math.pi / 2 - tip["angle"]) * 0.03

            nx = tip["x"] + math.cos(tip["angle"]) * tip["step"]
            ny = tip["y"] + math.sin(tip["angle"]) * tip["step"]
            if nx < s(8) or nx > SCREEN_WIDTH - s(8) or ny < s(26):
                self._draw_flower(tip["x"], tip["y"])
                continue

            width = max(1, s(4) - tip["n"] // 60)
            pygame.draw.line(self.plant_surf, tip["green"],
                             (tip["x"], tip["y"]), (nx, ny), width)
            tip["x"], tip["y"] = nx, ny

            # leaves every few segments
            if tip["n"] % 6 == 0:
                self._draw_leaf(nx, ny, tip["angle"])
            # occasional branch
            if tip["n"] > 8 and random.random() < 0.045 and \
               len(self.tips) + len(new_tips) < self.MAX_TIPS:
                branch = dict(tip)
                branch["angle"] = tip["angle"] + random.choice([-1, 1]) * random.uniform(0.5, 1.0)
                branch["energy"] = int(tip["energy"] * 0.6)
                branch["step"] = tip["step"] * 0.9
                branch["phase"] = random.uniform(0, math.tau)
                branch["n"] = 0
                new_tips.append(branch)
            new_tips.append(tip)
        self.tips = new_tips

    def _draw_leaf(self, x, y, stem_angle):
        a = stem_angle + random.choice([-1, 1]) * random.uniform(0.9, 1.5)
        length = random.uniform(7, 12) * SCALE
        color = random.choice(LEAF_GREENS)
        tipx, tipy = x + math.cos(a) * length, y + math.sin(a) * length
        midx, midy = (x + tipx) / 2, (y + tipy) / 2
        perp = a + math.pi / 2
        wdt = length * 0.38
        pts = [(x, y),
               (midx + math.cos(perp) * wdt, midy + math.sin(perp) * wdt),
               (tipx, tipy),
               (midx - math.cos(perp) * wdt, midy - math.sin(perp) * wdt)]
        pygame.draw.polygon(self.plant_surf, color, [(int(px), int(py)) for px, py in pts])

    def _draw_flower(self, x, y):
        color = random.choice(FLOWERS)
        r = random.randint(s(3), s(5))
        for k in range(5):
            a = k * math.tau / 5 + random.uniform(0, 0.5)
            pygame.draw.circle(self.plant_surf, color,
                               (int(x + math.cos(a) * r), int(y + math.sin(a) * r)),
                               max(1, r - 1))
        pygame.draw.circle(self.plant_surf, (250, 220, 120), (int(x), int(y)), max(1, r - 2))

    # ══════════════════════════════════════════════════════════════════════
    # State interface
    # ══════════════════════════════════════════════════════════════════════
    def update(self, dt):
        self.time_alive += dt

        if self.current_affairs.update(dt):
            self.sign_text = self.current_affairs.get_current_message()

        # growth / pruning cycle
        if self.pruning:
            # fade the old garden out gently
            self.plant_surf.fill((255, 255, 255, 246), special_flags=pygame.BLEND_RGBA_MULT)
            self.prune_timer += dt
            if self.prune_timer > 2.6:
                self.plant_surf.fill((0, 0, 0, 0))
                self.pruning = False
                self.generation += 1
                self._seed_garden()
        elif not self.tips:
            self.prune_timer += dt
            if self.prune_timer > self.PRUNE_HOLD:
                self.pruning = True
                self.prune_timer = 0.0
        else:
            self.prune_timer = 0.0
            self.grow_timer += dt
            while self.grow_timer >= self.GROW_TICK:
                self.grow_timer -= self.GROW_TICK
                self._grow_step()

        # drifting motes / fireflies
        for m in self.motes:
            m[2] += dt
            m[0] += math.sin(m[2] * 0.7) * m[3] * dt
            m[1] -= m[3] * 0.5 * dt
            if m[1] < s(30):
                m[0] = random.uniform(0, SCREEN_WIDTH)
                m[1] = self.shelf_y - s(4)

        # clouds
        for c in self.clouds:
            c[0] += c[2] * dt
            if c[0] > SCREEN_WIDTH + s(20):
                c[0] = -c[3].get_width()

    def _rebuild_sky(self, now):
        hour_f = now.hour + now.minute / 60.0
        top, bottom = _sky_colors(hour_f)
        h = self.sky_rect.h
        for y in range(h):
            t = y / max(1, h - 1)
            pygame.draw.line(self._sky_surf, _lerp(top, bottom, t),
                             (0, y), (SCREEN_WIDTH, y))

    def _sun_frac(self, now):
        """0..1 across the sky between 06:00 and 21:00, None at night."""
        f = (now.hour * 60 + now.minute - 360) / 900.0
        return f if 0.0 <= f <= 1.0 else None

    def draw(self, surface):
        now = datetime.datetime.now()
        if now.minute != self._sky_minute:
            self._sky_minute = now.minute
            self._rebuild_sky(now)
        surface.blit(self._sky_surf, (0, 0))

        # sun or moon on its arc
        f = self._sun_frac(now)
        if f is not None:
            sx = int(s(24) + f * (SCREEN_WIDTH - s(48)))
            sy = int(s(200) - math.sin(f * math.pi) * s(150))
            pygame.draw.circle(surface, (252, 232, 160), (sx, sy), s(15))
            pygame.draw.circle(surface, (255, 246, 210), (sx, sy), s(9))
        else:
            pygame.draw.circle(surface, (226, 232, 240), (int(SCREEN_WIDTH * 0.7), s(80)), s(11))
            pygame.draw.circle(surface, (150, 158, 178), (int(SCREEN_WIDTH * 0.7) - s(4), s(76)), s(9))

        # clouds (soft translucent sprites, dimmed at night)
        for cx, cy, _spd, sprite in self.clouds:
            sprite.set_alpha(45 if f is None else 150)
            surface.blit(sprite, (int(cx), int(cy)))

        # the garden
        surface.blit(self.plant_surf, (0, 0))

        # motes by day / fireflies at night
        night = f is None
        for m in self.motes:
            tw = 0.5 + 0.5 * math.sin(m[2] * (2.2 if night else 1.1))
            if night:
                col = (140 + int(100 * tw), 220, 90)
                pygame.draw.circle(surface, col, (int(m[0]), int(m[1])), s(2))
            else:
                col = (255, 250, 200)
                if tw > 0.4:
                    pygame.draw.circle(surface, col, (int(m[0]), int(m[1])), 1)

        # glasshouse frame + planter
        surface.blit(self._frame_surf, (0, 0))

        # solar dial needle: sun elevation -> yield
        yield_pct = math.sin(f * math.pi) if f is not None else 0.0
        cx, cy, r = self._dial_pos()
        na = math.radians(-200 + 220 * yield_pct)
        pygame.draw.line(surface, (235, 120, 60), (cx, cy),
                         (cx + (r - s(5)) * math.cos(na), cy + (r - s(5)) * math.sin(na)), 2)
        pygame.draw.circle(surface, COPPER, (cx, cy), s(3))
        pct = self.font_label.render(f"{int(yield_pct * 100):3d}%", True, CREAM)
        surface.blit(pct, (cx - pct.get_width() // 2, cy + s(6)))

        # generation tag (bottom-left)
        gen = self.font_label.render(
            f"GEN {self.generation:02d}  ·  DAY {now.timetuple().tm_yday}", True, (168, 140, 100))
        surface.blit(gen, (s(10), SCREEN_HEIGHT - s(18)))

        # dispatch painted on the planter box (kept clear of the dial)
        max_w = SCREEN_WIDTH - s(120)
        text = self.sign_text
        sign = self.font_sign.render(text, True, CREAM)
        while sign.get_width() > max_w and len(text) > 4:
            text = text[:-4].rstrip() + "…"
            sign = self.font_sign.render(text, True, CREAM)
        surface.blit(sign, (s(10), self.shelf_y + s(42)))

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = (200, 90, 60) if mode == 'work' else (110, 170, 90)
        txt = self.font_sign.render(f"{mins:02d}:{secs:02d}", True, CREAM)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(10), s(10)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, WOOD_DARK, box, border_radius=s(4))
        pygame.draw.rect(surface, c, box, 1, border_radius=s(4))
        surface.blit(txt, rect)
