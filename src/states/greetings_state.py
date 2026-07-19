"""
greetings_state.py
------------------
SYSTEM PROTOCOL — the transmission terminal.

Every message is classified by source and the terminal re-dresses
itself per channel: accent color, procedural icon, channel tag, and a
live audio-style waveform that gets excited while a message types in.
Drifting particles in the accent color float through the background,
an RX timestamp and signal bars sell the "incoming transmission"
fiction, and the UPLINKS chips show which live feeds are warm.

Cold-start fix: the boot batch is fetched before the feeds have warmed
up, so the terminal watches the uplinks and pulls a fresh batch the
moment the first feed comes alive.
"""

import random
import math
import threading
import datetime

import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from system_protocol import SystemProtocol, _FEEDS, FEEDS_ENABLED
from ui.glow_text import GlowText

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


BG_TOP = (5, 9, 18)
BG_BOT = (10, 8, 20)
PANEL_BG = (13, 20, 32)
TEXT_DIM = (108, 130, 155)

CHANNELS = {
    "docket":   ("DISPATCH DOCKET", (200, 60, 45)),
    "orbital":  ("ORBITAL RELAY",  (92, 240, 150)),
    "archive":  ("ARCHIVE",        (216, 168, 88)),
    "wire":     ("THE WIRE",       (0, 225, 245)),
    "met":      ("MET STATION",    (255, 176, 44)),
    "lunar":    ("LUNAR WATCH",    (198, 205, 235)),
    "protocol": ("LOCAL PROTOCOL", (255, 160, 60)),
}


def classify(text):
    t = text.upper()
    if "DOCKET //" in t:
        return "docket"
    if any(k in t for k in ("STATION PASS", "SOULS IN ORBIT", "AIRSHIP RIDES",
                            "SKY HAS", "TENANTS")):
        return "orbital"
    if "MEMORY BANKS //" in t or t.startswith("ARCHIVE,"):
        return "archive"
    if "THE WIRE //" in t or "TELEGRAPH INTERCEPT //" in t:
        return "wire"
    if any(k in t for k in ("°C", "BAROMETER", "WIND ", "SUNSET AT",
                            "SUNRISE WAS", "GOGGLES")):
        return "met"
    if "MOON TONIGHT" in t:
        return "lunar"
    return "protocol"


class GreetingsState(State):
    """System Protocol terminal with per-channel dress and live waveform."""

    TYPE_SPEED = 26.0
    HOLD_TIME = 1.0
    FADE_TIME = 0.55
    FUN_DISPLAY_TIME = 45.0      # rotate faster — there's more to say now
    FETCH_INTERVAL = 120.0

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.protocol = SystemProtocol()

        self.title_font = pygame.font.Font(None, s(24))
        # adaptive message fonts: long transmissions drop a size instead of
        # ever being truncated
        self.msg_fonts = [(70, pygame.font.Font(None, s(28))),
                          (150, pygame.font.Font(None, s(22))),
                          (10**9, pygame.font.Font(None, s(18)))]
        self.greeting_font = self.msg_fonts[0][1]
        self.meta_font = pygame.font.Font(None, s(15))

        self.target_greeting = ""
        self.visible_text = ""
        self.next_greeting = None
        self.channel = "protocol"
        self.rx_time = ""

        self.phase = "typing"
        self.phase_timer = 0.0
        self.reveal_progress = 0.0
        self.cursor_timer = 0.0
        self.cursor_on = True
        self.global_time = 0.0

        self.fun_messages = self.protocol.next_messages(2)
        self.fun_index = 0
        self.fun_timer = 0.0
        self.fetch_timer = 0.0
        self.is_fetching = False
        self.lock = threading.Lock()
        self._warm_refresh_done = self._feeds_warm()   # cold-start watcher

        panel_w = SCREEN_WIDTH - s(28)
        panel_h = s(252)
        self.panel_rect = pygame.Rect((SCREEN_WIDTH - panel_w) // 2,
                                      (SCREEN_HEIGHT - panel_h) // 2 - s(24),
                                      panel_w, panel_h)

        # drifting particles: [x, y, speed, phase, size]
        self.motes = [[random.uniform(0, SCREEN_WIDTH),
                       random.uniform(0, SCREEN_HEIGHT),
                       random.uniform(6, 16) * SCALE,
                       random.uniform(0, math.tau),
                       random.choice([1, 1, 2])] for _ in range(16)]

        self.greeting_glow = None
        self._bg_surface = self._build_bg()
        self._set_greeting(self.fun_messages[0])

    # ══════════════════════════════════════════════════════════════════════
    def _feeds_warm(self):
        return FEEDS_ENABLED and any(f.value is not None for k, f in _FEEDS.items())

    def _build_bg(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / max(1, SCREEN_HEIGHT - 1)
            pygame.draw.line(surf, lerp_color(BG_TOP, BG_BOT, t), (0, y), (SCREEN_WIDTH, y))
        rng = random.Random(12)
        for _ in range(40):                      # faint static stars
            x, y = rng.randint(0, SCREEN_WIDTH - 1), rng.randint(0, SCREEN_HEIGHT - 1)
            c = rng.randint(24, 44)
            surf.set_at((x, y), (c, c, c + 8))
        for y in range(0, SCREEN_HEIGHT, 4):     # scanlines
            pygame.draw.line(surf, (8, 12, 22), (0, y), (SCREEN_WIDTH, y))
        return surf

    def _accent(self):
        return CHANNELS[self.channel][1]

    def _set_greeting(self, text):
        self.target_greeting = text
        self.visible_text = ""
        self.reveal_progress = 0.0
        self.phase_timer = 0.0
        self.phase = "typing"
        self.channel = classify(text)
        self.rx_time = datetime.datetime.now().strftime("%H:%M:%S")
        accent = self._accent()
        for limit, font in self.msg_fonts:      # pick a size the panel can hold
            if len(text) <= limit:
                self.greeting_font = font
                break
        self.greeting_glow = GlowText(
            self.greeting_font, "", (255, 255, 255),
            lerp_color(accent, (0, 0, 0), 0.25), 4,
            max_width=self.panel_rect.w - s(44),
        )

    def _fetch_fun_messages(self):
        try:
            new_messages = self.protocol.next_messages(3)
            with self.lock:
                self.fun_messages = new_messages
                self.fun_index = 0
                self.fun_timer = 0.0
                self.next_greeting = self.fun_messages[0]
                self.phase = "fade"
                self.phase_timer = 0.0
        finally:
            self.is_fetching = False

    def enter(self):
        with self.lock:
            self.fun_index = 0
            self.fun_timer = 0.0
            if self.fun_messages:
                self._set_greeting(self.fun_messages[0])

    # ══════════════════════════════════════════════════════════════════════
    def update(self, dt):
        self.global_time += dt
        self.phase_timer += dt
        self.cursor_timer += dt
        self.fun_timer += dt
        self.fetch_timer += dt

        # cold-start fix: as soon as the first uplink warms, pull a fresh
        # batch so live channels appear within seconds of boot
        if not self._warm_refresh_done and self._feeds_warm() and not self.is_fetching:
            self._warm_refresh_done = True
            self.fetch_timer = 0.0
            self.is_fetching = True
            threading.Thread(target=self._fetch_fun_messages, daemon=True).start()

        if self.fetch_timer >= self.FETCH_INTERVAL and not self.is_fetching:
            self.fetch_timer = 0.0
            self.is_fetching = True
            threading.Thread(target=self._fetch_fun_messages, daemon=True).start()

        if self.fun_timer >= self.FUN_DISPLAY_TIME:
            self.fun_timer = 0.0
            with self.lock:
                if self.fun_messages:
                    self.fun_index = (self.fun_index + 1) % len(self.fun_messages)
                    self.next_greeting = self.fun_messages[self.fun_index]
                    self.phase = "fade"
                    self.phase_timer = 0.0

        if self.cursor_timer >= 0.45:
            self.cursor_timer = 0.0
            self.cursor_on = not self.cursor_on

        # drifting motes
        for m in self.motes:
            m[1] -= m[2] * dt
            m[0] += math.sin(self.global_time * 0.7 + m[3]) * 6 * dt
            if m[1] < -4:
                m[0] = random.uniform(0, SCREEN_WIDTH)
                m[1] = SCREEN_HEIGHT + 4

        if self.phase == "typing":
            self.reveal_progress += self.TYPE_SPEED * dt
            new_len = min(len(self.target_greeting), int(self.reveal_progress))
            new_text = self.target_greeting[:new_len]
            if new_text != self.visible_text:
                self.visible_text = new_text
                self.greeting_glow.update_text(self.visible_text)
            if new_len >= len(self.target_greeting):
                self.phase = "hold"
                self.phase_timer = 0.0
        elif self.phase == "hold":
            if self.next_greeting and self.phase_timer >= self.HOLD_TIME:
                self.phase = "fade"
                self.phase_timer = 0.0
        elif self.phase == "fade":
            if self.phase_timer >= self.FADE_TIME:
                if self.next_greeting:
                    nxt = self.next_greeting
                    self.next_greeting = None
                    self._set_greeting(nxt)
                else:
                    self.phase = "hold"
                    self.phase_timer = 0.0

    # ══════════════════════════════════════════════════════════════════════
    def _draw_icon(self, surface, cx, cy, r):
        accent = self._accent()
        dim = lerp_color(accent, PANEL_BG, 0.35)
        ch = self.channel
        if ch == "docket":       # a filed card with a stamp mark
            pygame.draw.rect(surface, dim, (cx - r, cy - r + s(2), r * 2, r * 2 - s(4)), 1)
            pygame.draw.line(surface, accent, (cx - r + s(3), cy - s(2)),
                             (cx + r - s(3), cy - s(2)), 1)
            pygame.draw.circle(surface, accent, (cx + s(4), cy + s(4)), s(4), 1)
        elif ch == "orbital":
            pygame.draw.circle(surface, dim, (cx, cy), r, 1)
            a = self.global_time * 1.5
            pygame.draw.circle(surface, accent,
                               (int(cx + math.cos(a) * r), int(cy + math.sin(a) * r)), s(2))
            pygame.draw.circle(surface, accent, (cx, cy), s(2))
        elif ch == "archive":
            for i in range(3):
                pygame.draw.rect(surface, dim if i else accent,
                                 (cx - r, cy - r + i * (r * 2 // 3), r * 2, r // 2), 1)
        elif ch == "wire":
            pts = [(cx - r + i * (r // 2), cy + (r // 2 if i % 2 else -r // 2))
                   for i in range(5)]
            pygame.draw.lines(surface, accent, False, pts, 2)
        elif ch == "met":
            pygame.draw.circle(surface, accent, (cx, cy), r - s(2))
            for i in range(2):
                pygame.draw.line(surface, PANEL_BG, (cx - r, cy + i * s(3)),
                                 (cx + r, cy + i * s(3)), 2)
        elif ch == "lunar":
            pygame.draw.circle(surface, accent, (cx, cy), r - 1)
            pygame.draw.circle(surface, PANEL_BG, (cx - s(4), cy - s(2)), r - s(3))
        else:
            pygame.draw.line(surface, accent, (cx - r + 2, cy - r // 2), (cx - 2, cy), 2)
            pygame.draw.line(surface, accent, (cx - 2, cy), (cx - r + 2, cy + r // 2), 2)
            pygame.draw.line(surface, accent, (cx + 2, cy + r // 2), (cx + r - 2, cy + r // 2), 2)

    def draw(self, surface):
        surface.blit(self._bg_surface, (0, 0))
        accent = self._accent()
        label = CHANNELS[self.channel][0]
        pr = self.panel_rect
        t = self.global_time

        # drifting accent motes behind the panel
        for m in self.motes:
            tw = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 1.3 + m[3]))
            pygame.draw.circle(surface, lerp_color(BG_TOP, accent, 0.5 * tw),
                               (int(m[0]), int(m[1])), m[4])

        # breathing halo
        pulse = 0.5 + 0.5 * math.sin(t * 2.0)
        halo = pygame.Surface((pr.w + s(22), pr.h + s(22)), pygame.SRCALPHA)
        pygame.draw.rect(halo, (*lerp_color(accent, (0, 0, 0), 0.5),
                                int(38 + 34 * pulse)),
                         halo.get_rect(), border_radius=s(15))
        surface.blit(halo, (pr.x - s(11), pr.y - s(11)))

        # panel body, double border
        pygame.draw.rect(surface, PANEL_BG, pr, border_radius=s(9))
        pygame.draw.rect(surface, accent, pr, 2, border_radius=s(9))
        pygame.draw.rect(surface, lerp_color(accent, PANEL_BG, 0.6),
                         pr.inflate(-s(8), -s(8)), 1, border_radius=s(6))

        # header: RX lamp + title | channel tag
        header = pygame.Rect(pr.x, pr.y, pr.w, s(30))
        pygame.draw.rect(surface, lerp_color(PANEL_BG, accent, 0.12), header,
                         border_top_left_radius=s(9), border_top_right_radius=s(9))
        pygame.draw.line(surface, accent, (pr.x, header.bottom), (pr.right, header.bottom), 1)
        rx_on = (self.phase == "typing") and (int(t * 5) % 2 == 0)
        pygame.draw.circle(surface, accent if rx_on else lerp_color(accent, PANEL_BG, 0.65),
                           (pr.x + s(13), header.centery), s(4))
        title = self.title_font.render("SYSTEM PROTOCOL", True, (214, 232, 246))
        surface.blit(title, (pr.x + s(24), pr.y + s(7)))
        tag = self.meta_font.render(label, True, accent)
        surface.blit(tag, (pr.right - tag.get_width() - s(10), pr.y + s(10)))

        # RX line + signal bars
        rx = self.meta_font.render(f"RX {self.rx_time}  ·  SIGNAL LOCKED", True, TEXT_DIM)
        surface.blit(rx, (pr.x + s(12), header.bottom + s(6)))
        for i in range(4):
            bh = s(3) + int(abs(math.sin(t * 2.6 + i * 0.9)) * s(8))
            bx = pr.right - s(16) - (3 - i) * s(6)
            pygame.draw.rect(surface, lerp_color(accent, PANEL_BG, 0.25),
                             (bx, header.bottom + s(18) - bh, s(3), bh))

        # channel icon
        self._draw_icon(surface, pr.centerx, header.bottom + s(42), s(11))

        # message
        gs = self.greeting_glow.get_surface()
        gx = pr.centerx - gs.get_width() // 2
        gy = pr.y + s(96)
        if self.phase == "fade":
            faded = gs.copy()
            faded.set_alpha(int(255 * (1 - min(1.0, self.phase_timer / self.FADE_TIME))))
            surface.blit(faded, (gx, gy))
        else:
            surface.blit(gs, (gx, gy))
        if self.phase == "typing" and self.cursor_on:
            pygame.draw.rect(surface, accent,
                             (gx + gs.get_width() + s(3), gy + s(6), s(7), s(18)))

        # transmission waveform: lively while typing, calm on hold
        wave_y = pr.bottom - s(24)
        wave_x0, wave_x1 = pr.x + s(14), pr.right - s(14)
        amp = s(9) if self.phase == "typing" else s(3)
        pygame.draw.line(surface, lerp_color(accent, PANEL_BG, 0.7),
                         (wave_x0, wave_y), (wave_x1, wave_y), 1)
        pts = []
        for x in range(wave_x0, wave_x1, 3):
            u = (x - wave_x0) / max(1, wave_x1 - wave_x0)
            envelope = math.sin(u * math.pi)
            y = wave_y + math.sin(x * 0.14 + t * 9) * amp * envelope \
                + math.sin(x * 0.05 - t * 3) * amp * 0.4 * envelope
            pts.append((x, y))
        if len(pts) > 1:
            pygame.draw.lines(surface, accent, False, pts, 1)

        # ── UPLINK chips ─────────────────────────────────────────────────
        chips = [("ORB", "iss"), ("ARC", "history"), ("WIRE", "wire"),
                 ("MET", "wx"), ("LUN", None)]
        chip_w, gap = s(52), s(6)
        cx0 = (SCREEN_WIDTH - len(chips) * chip_w - (len(chips) - 1) * gap) // 2
        cy = pr.bottom + s(22)
        for i, (name, key) in enumerate(chips):
            warm = True if key is None else (FEEDS_ENABLED and
                                             _FEEDS[key].value is not None)
            rect = pygame.Rect(cx0 + i * (chip_w + gap), cy, chip_w, s(18))
            col = (92, 240, 150) if warm else (56, 66, 82)
            pygame.draw.rect(surface, lerp_color(col, BG_TOP, 0.82), rect,
                             border_radius=s(4))
            pygame.draw.rect(surface, col, rect, 1, border_radius=s(4))
            dot = col if (not warm or int(t * 2 + i) % 2 == 0) else lerp_color(col, BG_TOP, 0.4)
            pygame.draw.circle(surface, dot, (rect.x + s(9), rect.centery), s(3))
            nm = self.meta_font.render(name, True, col if warm else TEXT_DIM)
            surface.blit(nm, (rect.x + s(17), rect.y + s(4)))

        meta = self.meta_font.render(f"KEA // {self.protocol.name}", True, TEXT_DIM)
        surface.blit(meta, ((SCREEN_WIDTH - meta.get_width()) // 2,
                            SCREEN_HEIGHT - s(20)))

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        time_str = f"{mins:02d}:{secs:02d}"
        label = self.meta_font.render(time_str, True, (255, 255, 255))
        bg_rect = label.get_rect(bottomleft=(s(8), SCREEN_HEIGHT - s(8)))
        bg_rect.inflate_ip(s(10), s(6))
        pygame.draw.rect(surface, PANEL_BG, bg_rect, border_radius=s(4))
        pygame.draw.rect(surface, (95, 165, 210), bg_rect, 1, border_radius=s(4))
        surface.blit(label, label.get_rect(center=bg_rect.center))
