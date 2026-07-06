"""
abyssal_state.py
----------------
ABYSSAL STATION — oceanpunk deep-sea observation post.

The whole screen is a pressure-window view into the abyss: god rays
fade out far above, a school of fish drifts through on wandering paths,
kelp sways in the current, marine snow sinks forever. Sonar rings pulse
outward; an anglerfish with a glowing lure prowls the deep; and every
few minutes a leviathan slides past in the murk while the HUD flashes
SONAR CONTACT. Brass-verdigris HUD with a live depth readout, and the
System Protocol dispatch engraved on the lower plaque.

Background, rays and HUD are pre-rendered; per-frame work is small
polygons, lines and dots.
"""

import pygame
import random
import math

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from current_affairs import CurrentAffairs

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


# ── Palette ──────────────────────────────────────────────────────────────────
SEA_TOP     = (  8,  34,  46)
SEA_BOTTOM  = (  2,   6,  12)
RAY_COLOR   = ( 60, 130, 140)
BRASS       = (110,  96,  52)
BRASS_DARK  = ( 58,  50,  26)
VERDIGRIS   = (104, 160, 138)
HUD_BG      = ( 16,  20,  16)
TEXT_PALE   = (196, 214, 196)
GLOW_CYAN   = (110, 230, 220)
LURE_WARM   = (255, 205,  96)
FISH_COL    = ( 92, 140, 150)
FISH_BELLY  = (140, 190, 190)
KELP_COL    = ( 24,  72,  54)
KELP_LIT    = ( 40, 104,  72)
LEVIATHAN   = ( 10,  22,  32)
SNOW        = (120, 150, 155)


class AbyssalState(State):
    """Oceanpunk deep-sea window with fish, kelp, sonar and a leviathan."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.current_affairs = CurrentAffairs()
        self.font_title = pygame.font.Font(None, s(24))
        self.font_label = pygame.font.Font(None, s(15))
        self.font_tick  = pygame.font.Font(None, s(17))
        try:
            self.font_depth = pygame.font.SysFont("monospace", s(18), bold=True)
        except Exception:
            self.font_depth = pygame.font.Font(None, s(20))

        self.hud_top = pygame.Rect(0, 0, SCREEN_WIDTH, s(44))
        self.hud_bot = pygame.Rect(0, SCREEN_HEIGHT - s(40), SCREEN_WIDTH, s(40))
        self.sea_rect = pygame.Rect(0, self.hud_top.bottom, SCREEN_WIDTH,
                                    self.hud_bot.y - self.hud_top.bottom)

        self.time_alive = 0.0

        # fish school: slots around a wandering leader
        self.fish = []
        for i in range(11):
            self.fish.append({
                "x": random.uniform(0, SCREEN_WIDTH),
                "y": random.uniform(self.sea_rect.y + s(30), self.sea_rect.bottom - s(80)),
                "vx": 0.0, "vy": 0.0,
                "slot_a": random.uniform(0, math.tau),
                "slot_r": random.uniform(s(10), s(46)),
                "wig": random.uniform(0, math.tau),
                "size": random.uniform(0.8, 1.3),
            })
        self.leader_phase = random.uniform(0, math.tau)

        # kelp fronds anchored to the sea floor
        self.kelp = []
        for _ in range(5):
            self.kelp.append({
                "x": random.uniform(s(14), SCREEN_WIDTH - s(14)),
                "h": random.uniform(60, 130) * SCALE,
                "segs": 7,
                "phase": random.uniform(0, math.tau),
                "speed": random.uniform(0.5, 0.9),
                "amp": random.uniform(3, 7) * SCALE,
                "lit": random.random() < 0.4,
            })

        # marine snow + plankton glimmers
        self.snow = [[random.uniform(0, SCREEN_WIDTH),
                      random.uniform(self.sea_rect.y, self.sea_rect.bottom),
                      random.uniform(6, 16) * SCALE,
                      random.uniform(0, math.tau)] for _ in range(22)]
        self.plankton = [[random.randint(0, SCREEN_WIDTH - 1),
                          random.randint(self.sea_rect.y, self.sea_rect.bottom - 1),
                          random.uniform(0, math.tau)] for _ in range(12)]

        # sonar rings
        self.rings = []
        self.ring_timer = 2.0

        # anglerfish + leviathan events
        self.angler = None
        self.angler_timer = random.uniform(20.0, 45.0)
        self.leviathan = None
        self.leviathan_timer = random.uniform(35.0, 90.0)

        # ticker
        self.tick_text = self.current_affairs.get_current_message()
        self._tick_surf = self.font_tick.render(self.tick_text, True, VERDIGRIS)
        self.tick_scroll = 0.0
        self.tick_hold = 2.0

        self._depth_str = ""
        self._depth_surf = None

        self._bg_surf = self._build_background()
        self._hud_surf = self._build_hud()

    # ══════════════════════════════════════════════════════════════════════
    # Pre-rendered layers
    # ══════════════════════════════════════════════════════════════════════
    def _build_background(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / max(1, SCREEN_HEIGHT - 1)
            pygame.draw.line(surf, lerp_color(SEA_TOP, SEA_BOTTOM, t ** 0.8),
                             (0, y), (SCREEN_WIDTH, y))
        # god rays from the distant surface
        ray = pygame.Surface((SCREEN_WIDTH, self.sea_rect.h // 2), pygame.SRCALPHA)
        for x0, w in [(s(40), s(30)), (s(120), s(20)), (s(210), s(36)), (s(280), s(16))]:
            pygame.draw.polygon(ray, (*RAY_COLOR, 16),
                                [(x0, 0), (x0 + w, 0),
                                 (x0 + w - s(46), ray.get_height()),
                                 (x0 - s(46), ray.get_height())])
        surf.blit(ray, (0, self.sea_rect.y))
        # sea floor
        floor_y = self.hud_bot.y - s(10)
        pygame.draw.rect(surf, (6, 12, 12), (0, floor_y, SCREEN_WIDTH, s(12)))
        rng = random.Random(4)
        for _ in range(26):                     # rocks and silt
            rx = rng.randint(0, SCREEN_WIDTH - 1)
            rr = rng.randint(1, s(4))
            pygame.draw.circle(surf, (10, 18, 18), (rx, floor_y + rng.randint(0, s(6))), rr)
        return surf

    def _build_hud(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for rect in (self.hud_top, self.hud_bot):
            pygame.draw.rect(surf, HUD_BG, rect)
            edge_y = rect.bottom - 2 if rect.y == 0 else rect.y
            pygame.draw.line(surf, BRASS, (0, edge_y), (SCREEN_WIDTH, edge_y), 2)
            pygame.draw.line(surf, BRASS_DARK,
                             (0, edge_y + (2 if rect.y == 0 else -2)),
                             (SCREEN_WIDTH, edge_y + (2 if rect.y == 0 else -2)), 1)
            for rx in range(s(10), SCREEN_WIDTH, s(28)):     # rivets
                ry = rect.y + s(5) if rect.y == 0 else rect.bottom - s(5)
                pygame.draw.circle(surf, BRASS, (rx, ry), s(2))
        title = self.font_title.render("ABYSSAL STATION", True, TEXT_PALE)
        surf.blit(title, (s(10), s(11)))
        lbl = self.font_label.render("DEPTH", True, VERDIGRIS)
        surf.blit(lbl, (SCREEN_WIDTH - s(86), s(6)))
        # porthole corner brackets on the window
        for cx, cy, dx, dy in [(2, self.sea_rect.y + 2, 1, 1),
                               (SCREEN_WIDTH - 3, self.sea_rect.y + 2, -1, 1),
                               (2, self.hud_bot.y - 3, 1, -1),
                               (SCREEN_WIDTH - 3, self.hud_bot.y - 3, -1, -1)]:
            pygame.draw.line(surf, BRASS, (cx, cy), (cx + dx * s(14), cy), 2)
            pygame.draw.line(surf, BRASS, (cx, cy), (cx, cy + dy * s(14)), 2)
        return surf

    # ══════════════════════════════════════════════════════════════════════
    # Update
    # ══════════════════════════════════════════════════════════════════════
    def update(self, dt):
        self.time_alive += dt
        t = self.time_alive

        # wandering leader for the school
        lx = SCREEN_WIDTH / 2 + math.sin(t * 0.13 + self.leader_phase) * SCREEN_WIDTH * 0.36
        ly = (self.sea_rect.centery - s(20)
              + math.sin(t * 0.09 + self.leader_phase * 2) * self.sea_rect.h * 0.22)
        for f in self.fish:
            f["slot_a"] += dt * 0.25
            tx = lx + math.cos(f["slot_a"]) * f["slot_r"]
            ty = ly + math.sin(f["slot_a"] * 1.3) * f["slot_r"] * 0.5
            f["vx"] += ((tx - f["x"]) * 0.8 - f["vx"]) * min(1, dt * 2.0)
            f["vy"] += ((ty - f["y"]) * 0.8 - f["vy"]) * min(1, dt * 2.0)
            f["x"] += f["vx"] * dt
            f["y"] += f["vy"] * dt

        # marine snow sinks
        for p in self.snow:
            p[1] += p[2] * dt
            p[0] += math.sin(t * 0.8 + p[3]) * 4 * dt
            if p[1] > self.hud_bot.y - s(6):
                p[0] = random.uniform(0, SCREEN_WIDTH)
                p[1] = self.sea_rect.y + s(4)

        # sonar rings
        self.ring_timer -= dt
        if self.ring_timer <= 0:
            self.ring_timer = random.uniform(5.0, 8.0)
            self.rings.append([SCREEN_WIDTH // 2, self.sea_rect.centery, s(4)])
        for ring in self.rings:
            ring[2] += s(64) * dt
        self.rings = [r for r in self.rings if r[2] < SCREEN_WIDTH * 0.8]

        # anglerfish event
        if self.angler is None:
            self.angler_timer -= dt
            if self.angler_timer <= 0:
                d = random.choice([1, -1])
                self.angler = {
                    "x": -s(30) if d > 0 else SCREEN_WIDTH + s(30),
                    "y": random.uniform(self.hud_bot.y - s(90), self.hud_bot.y - s(40)),
                    "vx": d * random.uniform(9, 15) * SCALE,
                    "phase": random.uniform(0, math.tau),
                }
        else:
            self.angler["x"] += self.angler["vx"] * dt
            if not -s(40) < self.angler["x"] < SCREEN_WIDTH + s(40):
                self.angler = None
                self.angler_timer = random.uniform(40.0, 90.0)

        # leviathan event
        if self.leviathan is None:
            self.leviathan_timer -= dt
            if self.leviathan_timer <= 0:
                d = random.choice([1, -1])
                self.leviathan = {
                    "x": -s(200) if d > 0 else SCREEN_WIDTH + s(200),
                    "y": self.sea_rect.y + self.sea_rect.h * random.uniform(0.30, 0.55),
                    "vx": d * random.uniform(18, 26) * SCALE,
                    "phase": random.uniform(0, math.tau),
                }
        else:
            self.leviathan["x"] += self.leviathan["vx"] * dt
            if not -s(220) < self.leviathan["x"] < SCREEN_WIDTH + s(220):
                self.leviathan = None
                self.leviathan_timer = random.uniform(120.0, 240.0)

        # ticker
        if self.current_affairs.update(dt):
            self.tick_text = self.current_affairs.get_current_message()
            self._tick_surf = self.font_tick.render(self.tick_text, True, VERDIGRIS)
            self.tick_scroll = 0.0
            self.tick_hold = 2.0
        if self._tick_surf.get_width() > SCREEN_WIDTH - s(20):
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
        surface.blit(self._bg_surf, (0, 0))
        t = self.time_alive

        # sonar rings (dim, behind everything that swims)
        for rx, ry, rr in self.rings:
            fade = 1.0 - rr / (SCREEN_WIDTH * 0.8)
            pygame.draw.circle(surface, lerp_color(SEA_BOTTOM, GLOW_CYAN, 0.4 * fade),
                               (rx, ry), int(rr), 1)

        if self.leviathan:
            self._draw_leviathan(surface, t)

        # plankton glimmer
        for px, py, ph in self.plankton:
            b = 0.5 + 0.5 * math.sin(t * 1.7 + ph)
            if b > 0.55:
                surface.fill(lerp_color(SEA_BOTTOM, GLOW_CYAN, b),
                             (px, py, 1, 1))

        # fish school
        for f in self.fish:
            self._draw_fish(surface, f, t)

        if self.angler:
            self._draw_angler(surface, t)

        # kelp (foreground)
        floor_y = self.hud_bot.y - s(8)
        for k in self.kelp:
            col = KELP_LIT if k["lit"] else KELP_COL
            px, py = k["x"], floor_y
            for seg in range(k["segs"]):
                sway = math.sin(t * k["speed"] + k["phase"] + seg * 0.55) * k["amp"]
                sway *= (seg + 1) / k["segs"]
                nx = k["x"] + sway
                ny = floor_y - (seg + 1) * k["h"] / k["segs"]
                w = max(1, s(4) - seg // 2)
                pygame.draw.line(surface, col, (px, py), (nx, ny), w)
                if seg % 2 == 1:                    # little side leaves
                    la = -math.pi / 2 + (0.9 if seg % 4 == 1 else -0.9)
                    pygame.draw.line(surface, col, (nx, ny),
                                     (nx + math.cos(la) * s(7), ny + math.sin(la) * s(7)), 1)
                px, py = nx, ny

        # marine snow (nearest layer)
        for p in self.snow:
            surface.fill(SNOW, (int(p[0]), int(p[1]), 1, 1))

        # ── HUD ──────────────────────────────────────────────────────────
        surface.blit(self._hud_surf, (0, 0))

        depth = 3742 + math.sin(t * 0.05) * 9 + math.sin(t * 0.013) * 14
        depth_str = f"{depth:7.1f} M"
        if depth_str != self._depth_str:
            self._depth_str = depth_str
            self._depth_surf = self.font_depth.render(depth_str, True, GLOW_CYAN)
        surface.blit(self._depth_surf,
                     (SCREEN_WIDTH - self._depth_surf.get_width() - s(8), s(18)))

        # sonar contact alert while the leviathan is passing
        if self.leviathan and (int(t * 2) % 2 == 0):
            alert = self.font_label.render("· SONAR CONTACT ·", True, LURE_WARM)
            surface.blit(alert, ((SCREEN_WIDTH - alert.get_width()) // 2,
                                 self.hud_top.bottom + s(4)))

        # dispatch plaque (marquee when long)
        ty = self.hud_bot.y + (self.hud_bot.h - self._tick_surf.get_height()) // 2
        if self._tick_surf.get_width() <= SCREEN_WIDTH - s(20):
            surface.blit(self._tick_surf,
                         ((SCREEN_WIDTH - self._tick_surf.get_width()) // 2, ty))
        else:
            prev_clip = surface.get_clip()
            surface.set_clip(pygame.Rect(s(8), self.hud_bot.y, SCREEN_WIDTH - s(16), self.hud_bot.h))
            x0 = s(8) - int(self.tick_scroll)
            surface.blit(self._tick_surf, (x0, ty))
            surface.blit(self._tick_surf, (x0 + self._tick_surf.get_width() + s(40), ty))
            surface.set_clip(prev_clip)

    def _draw_fish(self, surface, f, t):
        size = s(6) * f["size"]
        ang = math.atan2(f["vy"], f["vx"]) if abs(f["vx"]) + abs(f["vy"]) > 1 else 0.0
        wig = math.sin(t * 6 + f["wig"]) * 0.25
        nose = (f["x"] + math.cos(ang) * size, f["y"] + math.sin(ang) * size)
        top = (f["x"] + math.cos(ang + 2.4 + wig) * size * 0.7,
               f["y"] + math.sin(ang + 2.4 + wig) * size * 0.7)
        bot = (f["x"] + math.cos(ang - 2.4 + wig) * size * 0.7,
               f["y"] + math.sin(ang - 2.4 + wig) * size * 0.7)
        pygame.draw.polygon(surface, FISH_COL, [nose, top, bot])
        tail = (f["x"] - math.cos(ang) * size * (1.1 + wig),
                f["y"] - math.sin(ang) * size * (1.1 + wig))
        pygame.draw.line(surface, FISH_BELLY, (f["x"], f["y"]), tail, 1)

    def _draw_angler(self, surface, t):
        a = self.angler
        d = 1 if a["vx"] > 0 else -1
        bob = math.sin(t * 1.2 + a["phase"]) * s(3)
        x, y = a["x"], a["y"] + bob
        # barely-visible body
        body = lerp_color(SEA_BOTTOM, (40, 46, 52), 0.8)
        pygame.draw.ellipse(surface, body, (x - s(12), y - s(7), s(24), s(14)))
        pygame.draw.polygon(surface, body,
                            [(x - d * s(11), y), (x - d * s(19), y - s(5)),
                             (x - d * s(19), y + s(5))])
        # jaw glint
        pygame.draw.line(surface, (70, 80, 84),
                         (x + d * s(4), y + s(3)), (x + d * s(10), y + s(1)), 1)
        # glowing lure on its stalk
        lx = x + d * s(14)
        ly = y - s(9) + math.sin(t * 2.1 + a["phase"]) * s(2)
        pygame.draw.line(surface, body, (x + d * s(4), y - s(6)), (lx, ly), 1)
        pulse = 0.6 + 0.4 * math.sin(t * 3.0 + a["phase"])
        pygame.draw.circle(surface, lerp_color(SEA_BOTTOM, LURE_WARM, 0.5 * pulse),
                           (int(lx), int(ly)), s(5))
        pygame.draw.circle(surface, lerp_color((80, 60, 30), LURE_WARM, pulse),
                           (int(lx), int(ly)), s(2))

    def _draw_leviathan(self, surface, t):
        lv = self.leviathan
        d = 1 if lv["vx"] > 0 else -1
        x, y = lv["x"], lv["y"] + math.sin(t * 0.4 + lv["phase"]) * s(6)
        # segmented body, biggest in the middle
        for i, (off, ry) in enumerate([(0, 26), (-40, 22), (-76, 16), (-104, 10)]):
            pygame.draw.ellipse(surface, LEVIATHAN,
                                (x + d * off * SCALE - s(30), y - s(ry),
                                 s(64), s(ry * 2)))
        # tail fluke, slowly beating
        beat = math.sin(t * 1.1 + lv["phase"]) * s(10)
        tx = x - d * s(128)
        pygame.draw.polygon(surface, LEVIATHAN,
                            [(tx, y), (tx - d * s(22), y - s(16) + beat),
                             (tx - d * s(22), y + s(16) + beat)])
        # a single pale eye
        pygame.draw.circle(surface, (60, 80, 88),
                           (int(x + d * s(20)), int(y - s(6))), s(2))

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = LURE_WARM if mode == "work" else GLOW_CYAN
        txt = self.font_tick.render(f"{mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(10), self.hud_top.bottom + s(6)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, HUD_BG, box, border_radius=s(4))
        pygame.draw.rect(surface, BRASS, box, 1, border_radius=s(4))
        surface.blit(txt, rect)
