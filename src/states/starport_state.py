"""
starport_state.py
-----------------
STARPORT // BAY 94 — the dusty dock at the edge of the galaxy.

Twin suns sink over a desert starport: moisture towers and dome
settlements on the horizon, a landing pad with chasing edge lights in
the foreground. A battered little freighter lives here on a loop of
real events — it drops out of the high sky on repulsor glow, sets down
in a burst of dust, sits venting while the pad crew (you) reads the
news, then lifts and climbs away; now and then something up high tears
away in a hyperspace streak. The System Protocol dispatch is projected
beside the pad as a flickering blue HOLOGRAM, jitter and glitch
included.

An original scene in an old spirit. No ticker bar — the news floats.
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
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


# ── Palette: desert dusk ────────────────────────────────────────────────────
SKY_TOP    = (40, 22, 52)
SKY_MID    = (120, 58, 62)
SKY_LOW    = (232, 132, 66)
SUN_BIG    = (255, 216, 150)
SUN_SMALL  = (255, 246, 220)
SIL        = (30, 17, 22)          # horizon silhouettes
SAND_FAR   = (120, 72, 54)
SAND_NEAR  = (66, 42, 40)
PAD_METAL  = (52, 46, 52)
PAD_EDGE   = (86, 78, 86)
LIGHT_AMBER = (255, 190, 90)
HOLO       = (130, 200, 255)
HULL       = (120, 116, 112)
HULL_DARK  = (78, 74, 72)
ENGINE     = (150, 220, 255)
TEXT_DIM   = (168, 128, 100)


class StarportState(State):
    """Desert starport with a living freighter and holographic dispatches."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.current_affairs = CurrentAffairs()
        self.font_label = pygame.font.Font(None, s(15))
        self.font_holo = pygame.font.Font(None, s(19))

        self.horizon_y = int(SCREEN_HEIGHT * 0.40)
        self.pad_cx = int(SCREEN_WIDTH * 0.54)
        self.pad_cy = int(SCREEN_HEIGHT * 0.74)
        self.pad_rx, self.pad_ry = s(112), s(30)

        self.time_alive = 0.0

        # freighter event loop
        self.ship_state = "inbound"       # inbound | landed | depart | gone
        self.ship_t = 0.0
        self.ship_wait = 0.0
        self.dust = []                    # [x, y, vx, vy, life]
        self.vents = []                   # steam puffs while landed

        # high-sky traffic + hyperspace streaks
        self.streak = None
        self.streak_timer = random.uniform(8.0, 20.0)

        # stars (upper sky)
        rng = random.Random(11)
        self.stars = [(rng.randint(0, SCREEN_WIDTH - 1),
                       rng.randint(s(6), int(self.horizon_y * 0.6)),
                       rng.uniform(0, math.tau)) for _ in range(26)]

        # hologram text
        self.holo_text = self.current_affairs.get_current_message()
        self._holo_surf = self.font_holo.render(self.holo_text, True, HOLO)
        self.holo_scroll = 0.0
        self.holo_hold = 2.0
        self.holo_w = SCREEN_WIDTH - s(70)

        self._bg = self._build_bg()

    # ══════════════════════════════════════════════════════════════════════
    def _build_bg(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        hz = self.horizon_y
        # dusk gradient in two stages
        for y in range(SCREEN_HEIGHT):
            if y < hz * 0.6:
                c = lerp_color(SKY_TOP, SKY_MID, y / max(1, hz * 0.6))
            elif y < hz:
                c = lerp_color(SKY_MID, SKY_LOW, (y - hz * 0.6) / max(1, hz * 0.4))
            else:
                c = lerp_color(SAND_FAR, SAND_NEAR,
                               (y - hz) / max(1, SCREEN_HEIGHT - hz))
            pygame.draw.line(surf, c, (0, y), (SCREEN_WIDTH, y))

        # the twin suns, one shouldering the other
        bx, by = int(SCREEN_WIDTH * 0.64), int(hz * 0.76)
        pygame.draw.circle(surf, lerp_color(SUN_BIG, SKY_LOW, 0.35), (bx, by), s(30))
        pygame.draw.circle(surf, SUN_BIG, (bx, by), s(26))
        pygame.draw.circle(surf, SUN_SMALL, (bx - s(30), by - s(14)), s(13))

        # horizon: dome settlement (left) + moisture towers
        rng = random.Random(15)
        for dx, dr in [(s(38), s(20)), (s(62), s(13)), (s(20), s(11))]:
            pygame.draw.circle(surf, SIL, (dx, hz), dr,
                               draw_top_left=True, draw_top_right=True)
        pygame.draw.rect(surf, SIL, (0, hz - s(3), SCREEN_WIDTH, s(4)))
        for tx in (s(120), s(168), s(238), s(292)):
            th = rng.randint(s(16), s(30))
            pygame.draw.line(surf, SIL, (tx, hz), (tx, hz - th), 2)
            pygame.draw.line(surf, SIL, (tx - s(5), hz - th), (tx + s(5), hz - th), 2)
            pygame.draw.line(surf, SIL, (tx - s(3), hz - th + s(4)),
                             (tx + s(3), hz - th + s(4)), 1)

        # desert bands + scattered rocks
        for _ in range(26):
            rx0 = rng.randint(0, SCREEN_WIDTH - 1)
            ry0 = rng.randint(hz + s(8), SCREEN_HEIGHT - s(30))
            pygame.draw.ellipse(surf, lerp_color(SAND_NEAR, SIL, 0.4),
                                (rx0, ry0, rng.randint(2, s(7)), rng.randint(1, s(3))))

        # the landing pad: layered octagon-ish ellipse with plate seams
        pad = pygame.Rect(0, 0, self.pad_rx * 2, self.pad_ry * 2)
        pad.center = (self.pad_cx, self.pad_cy)
        pygame.draw.ellipse(surf, (30, 26, 32), pad.move(0, s(5)))     # shadow rim
        pygame.draw.ellipse(surf, PAD_METAL, pad)
        pygame.draw.ellipse(surf, PAD_EDGE, pad, 2)
        inner = pad.inflate(-s(34), -s(12))
        pygame.draw.ellipse(surf, PAD_EDGE, inner, 1)
        for a in range(0, 360, 45):                                    # plate seams
            r = math.radians(a)
            pygame.draw.line(surf, (40, 36, 42),
                             (self.pad_cx + math.cos(r) * inner.w // 2,
                              self.pad_cy + math.sin(r) * inner.h // 2),
                             (self.pad_cx + math.cos(r) * self.pad_rx,
                              self.pad_cy + math.sin(r) * self.pad_ry), 1)
        # holo emitter post, left of the pad
        ex = self.pad_cx - self.pad_rx - s(10)
        pygame.draw.rect(surf, PAD_EDGE, (ex - s(2), self.pad_cy - s(16), s(4), s(16)))
        pygame.draw.circle(surf, HOLO, (ex, self.pad_cy - s(18)), s(3), 1)
        self.emitter = (ex, self.pad_cy - s(18))

        # HUD line
        title = self.font_label.render("STARPORT // BAY 94", True, TEXT_DIM)
        surf.blit(title, (s(10), s(8)))
        return surf

    # ══════════════════════════════════════════════════════════════════════
    def _spawn_dust(self, n, spread):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(20, 70) * SCALE * spread
            self.dust.append([self.pad_cx, self.pad_cy - s(2),
                              math.cos(a) * v, -abs(math.sin(a)) * v * 0.45,
                              random.uniform(0.5, 1.1)])

    def update(self, dt):
        self.time_alive += dt
        t = self.time_alive

        # hologram text + marquee
        if self.current_affairs.update(dt):
            self.holo_text = self.current_affairs.get_current_message()
            self._holo_surf = self.font_holo.render(self.holo_text, True, HOLO)
            self.holo_scroll = 0.0
            self.holo_hold = 2.0
        if self._holo_surf.get_width() > self.holo_w:
            if self.holo_hold > 0:
                self.holo_hold -= dt
            else:
                self.holo_scroll += s(24) * dt
                if self.holo_scroll > self._holo_surf.get_width() + s(40):
                    self.holo_scroll = 0.0
                    self.holo_hold = 2.0

        # freighter event loop
        self.ship_t += dt
        if self.ship_state == "inbound" and self.ship_t >= 4.0:
            self.ship_state = "landed"
            self.ship_t = 0.0
            self.ship_wait = random.uniform(14.0, 30.0)
            self._spawn_dust(26, 1.0)
        elif self.ship_state == "landed":
            if random.random() < dt * 1.2:          # vent steam now and then
                side = random.choice([-1, 1])
                self.vents.append([self.pad_cx + side * s(16),
                                   self.pad_cy - s(16), side, 0.0])
            if self.ship_t >= self.ship_wait:
                self.ship_state = "depart"
                self.ship_t = 0.0
                self._spawn_dust(18, 0.7)
        elif self.ship_state == "depart" and self.ship_t >= 3.5:
            self.ship_state = "gone"
            self.ship_t = 0.0
            self.ship_wait = random.uniform(10.0, 22.0)
        elif self.ship_state == "gone" and self.ship_t >= self.ship_wait:
            self.ship_state = "inbound"
            self.ship_t = 0.0

        # dust + vents
        for d in self.dust:
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[3] += 40 * SCALE * dt
            d[4] -= dt
        self.dust = [d for d in self.dust if d[4] > 0]
        for v in self.vents:
            v[0] += v[2] * 14 * SCALE * dt
            v[1] -= 10 * SCALE * dt
            v[3] += dt
        self.vents = [v for v in self.vents if v[3] < 1.0]

        # hyperspace streaks
        if self.streak is None:
            self.streak_timer -= dt
            if self.streak_timer <= 0:
                y = random.randint(s(30), int(self.horizon_y * 0.55))
                x = random.randint(s(40), SCREEN_WIDTH - s(80))
                self.streak = [x, y, random.choice([-1, 1]), 0.0]
        else:
            self.streak[3] += dt
            if self.streak[3] > 0.5:
                self.streak = None
                self.streak_timer = random.uniform(18.0, 45.0)

    # ══════════════════════════════════════════════════════════════════════
    def _ship_pos(self):
        """Position + phase info for the freighter, per state machine."""
        if self.ship_state == "inbound":
            p = min(1.0, self.ship_t / 4.0)
            e = 1 - (1 - p) ** 2                        # ease out
            x = SCREEN_WIDTH * 0.9 - (SCREEN_WIDTH * 0.9 - self.pad_cx) * e
            y = s(60) + (self.pad_cy - s(24) - s(60)) * e
            return x, y, True
        if self.ship_state == "landed":
            return self.pad_cx, self.pad_cy - s(24), False
        if self.ship_state == "depart":
            p = min(1.0, self.ship_t / 3.5)
            e = p * p
            x = self.pad_cx + SCREEN_WIDTH * 0.5 * e
            y = (self.pad_cy - s(24)) - (self.pad_cy + s(40)) * e
            return x, y, True
        return None

    def draw(self, surface):
        surface.blit(self._bg, (0, 0))
        t = self.time_alive

        # stars, brightening as they twinkle
        for sx_, sy_, ph in self.stars:
            b = 0.5 + 0.5 * math.sin(t * 1.5 + ph)
            if b > 0.35:
                c = int(150 + 100 * b)
                surface.fill((c, c, min(255, c + 20)), (sx_, sy_, 1 + (b > 0.85), 1))

        # hyperspace streak: a line tearing open, then gone
        if self.streak:
            x, y, d, st = self.streak
            ln = int(min(1.0, st / 0.25) * s(70))
            fade = 1.0 if st < 0.3 else max(0.0, 1 - (st - 0.3) / 0.2)
            col = lerp_color(SKY_TOP, (255, 255, 255), fade)
            pygame.draw.line(surface, col, (x, y), (x + d * ln, y - ln // 5), 2)
            pygame.draw.circle(surface, col, (x + d * ln, y - ln // 5), s(2))

        # pad chase lights (over the baked pad rim)
        for i in range(14):
            a = i * math.tau / 14
            lx = self.pad_cx + math.cos(a) * (self.pad_rx - s(4))
            ly = self.pad_cy + math.sin(a) * (self.pad_ry - s(2))
            chase = ((t * 5 - i) % 14) < 2.0
            col = LIGHT_AMBER if chase else lerp_color(LIGHT_AMBER, PAD_METAL, 0.75)
            pygame.draw.circle(surface, col, (int(lx), int(ly)), s(2))

        # dust + vent steam
        for d in self.dust:
            c = lerp_color(SAND_NEAR, (200, 170, 140), d[4])
            pygame.draw.circle(surface, c, (int(d[0]), int(d[1])),
                               max(1, int(s(3) * d[4])))
        for v in self.vents:
            a = max(0.0, 1 - v[3])
            pygame.draw.circle(surface, lerp_color(PAD_METAL, (220, 220, 225), 0.5 * a),
                               (int(v[0]), int(v[1])), max(1, int(s(4) * (0.4 + v[3]))), 1)

        # the freighter
        pos = self._ship_pos()
        if pos:
            self._draw_ship(surface, *pos, t)

        # hologram dispatch
        self._draw_hologram(surface, t)

        # bottom status line
        now = datetime.datetime.now().strftime("%H:%M")
        status = {"inbound": "INBOUND FREIGHTER ON APPROACH",
                  "landed": "DOCKED · UNLOADING",
                  "depart": "DEPARTURE CLEARANCE GRANTED",
                  "gone": "PAD CLEAR · AWAITING TRAFFIC"}[self.ship_state]
        line = self.font_label.render(f"{now}  ·  {status}", True, TEXT_DIM)
        surface.blit(line, ((SCREEN_WIDTH - line.get_width()) // 2,
                            SCREEN_HEIGHT - s(18)))

    def _draw_ship(self, surface, x, y, flying, t):
        x, y = int(x), int(y)
        wob = math.sin(t * 3.1) * s(1.5) if flying else 0
        y += int(wob)
        # repulsor glow washing the ground when flying
        if flying:
            for gx in (-s(13), s(13)):
                pygame.draw.circle(surface, lerp_color(ENGINE, SKY_LOW, 0.35),
                                   (x + gx, y + s(11)), s(6))
                pygame.draw.circle(surface, (255, 255, 255), (x + gx, y + s(11)), s(3))
        # landing legs when down
        if not flying:
            for lx in (-s(17), s(1), s(19)):
                pygame.draw.line(surface, HULL_DARK, (x + lx, y + s(7)),
                                 (x + lx + s(4), y + s(17)), 2)
                pygame.draw.line(surface, HULL_DARK, (x + lx + s(1), y + s(17)),
                                 (x + lx + s(7), y + s(17)), 2)
        # hull: broad saucer body, offset cockpit pod, twin nacelles
        body = pygame.Rect(0, 0, s(62), s(19))
        body.center = (x, y)
        pygame.draw.ellipse(surface, HULL, body)
        pygame.draw.ellipse(surface, HULL_DARK, body, 1)
        # upper deck highlight + hull plating seams
        deck = pygame.Rect(0, 0, s(44), s(9))
        deck.center = (x - s(2), y - s(4))
        pygame.draw.ellipse(surface, lerp_color(HULL, (215, 210, 205), 0.35), deck)
        pygame.draw.line(surface, HULL_DARK, (x - s(23), y + s(1)),
                         (x + s(23), y + s(1)), 1)
        for sx_ in (-s(12), 0, s(12)):
            pygame.draw.line(surface, HULL_DARK, (x + sx_, y - s(6)),
                             (x + sx_, y + s(1)), 1)
        # cockpit pod on its neck, lit viewport
        pygame.draw.line(surface, HULL_DARK, (x + s(17), y - s(2)),
                         (x + s(23), y - s(6)), s(4))
        pygame.draw.circle(surface, HULL_DARK, (x + s(25), y - s(7)), s(6))
        pygame.draw.circle(surface, lerp_color(HOLO, (255, 255, 255), 0.45),
                           (x + s(26), y - s(8)), s(3))
        # nacelles
        for gx in (-s(13), s(13)):
            pygame.draw.rect(surface, HULL_DARK,
                             (x + gx - s(5), y + s(5), s(10), s(7)), border_radius=2)
            pygame.draw.line(surface, lerp_color(HULL, (0, 0, 0), 0.2),
                             (x + gx - s(3), y + s(5)), (x + gx + s(3), y + s(5)), 1)
        # mandible prongs at the bow
        for my in (-s(4), s(4)):
            pygame.draw.line(surface, HULL_DARK, (x - s(28), y + my),
                             (x - s(38), y + my * 0.6), 2)
        # blinking nav light
        if int(t * 3) % 2 == 0:
            pygame.draw.circle(surface, (235, 90, 80), (x - s(38), y), s(2))

    def _draw_hologram(self, surface, t):
        hs = self._holo_surf
        hx0 = (SCREEN_WIDTH - self.holo_w) // 2
        hy = self.pad_cy - s(76)
        jitter = int(math.sin(t * 17) * 1.2)
        flicker = 150 + int(60 * (0.5 + 0.5 * math.sin(t * 9))
                            + random.randint(-18, 12))

        # beam from the emitter up to the text
        ex, ey = self.emitter
        for dx, a in ((-1, 40), (1, 40), (0, 70)):
            pygame.draw.line(surface, lerp_color(SAND_NEAR, HOLO, a / 100),
                             (ex, ey), (hx0 + s(6) + dx * s(10), hy + s(14)), 1)

        # text plate: base line + flickering text (marquee when long)
        pygame.draw.line(surface, lerp_color(SAND_FAR, HOLO, 0.4),
                         (hx0, hy + s(18)), (hx0 + self.holo_w, hy + s(18)), 1)
        holo = hs.copy()
        holo.set_alpha(max(90, min(230, flicker)))
        prev_clip = surface.get_clip()
        surface.set_clip(pygame.Rect(hx0, hy - s(6), self.holo_w, s(24)))
        if hs.get_width() <= self.holo_w:
            bx = hx0 + (self.holo_w - hs.get_width()) // 2
            surface.blit(holo, (bx, hy + jitter))
        else:
            x0 = hx0 - int(self.holo_scroll)
            surface.blit(holo, (x0, hy + jitter))
            surface.blit(holo, (x0 + hs.get_width() + s(40), hy + jitter))
        # occasional glitch: shift a horizontal slice
        if int(t * 0.8) % 4 == 0 and (t % 1.0) < 0.12:
            sl = pygame.Rect(hx0, hy + s(4), self.holo_w, s(5))
            try:
                slice_surf = surface.subsurface(sl).copy()
                surface.blit(slice_surf, (sl.x + s(3), sl.y))
            except ValueError:
                pass
        surface.set_clip(prev_clip)

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = (235, 90, 80) if mode == "work" else ENGINE
        txt = self.font_label.render(f"{mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(10), s(8)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, (30, 20, 26), box, border_radius=s(4))
        pygame.draw.rect(surface, c, box, 1, border_radius=s(4))
        surface.blit(txt, rect)
