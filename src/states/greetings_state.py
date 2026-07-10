"""
greetings_state.py
------------------
SYSTEM PROTOCOL — the message terminal.

Now that the protocol carries live feeds, the panel dresses itself for
whatever is coming through: each message is classified by source and
the terminal switches channel — accent color, a small procedural icon
and a channel tag (ORBITAL RELAY, ARCHIVE, THE WIRE, MET STATION,
LUNAR WATCH, or LOCAL PROTOCOL for the personal greetings). An UPLINKS
row at the bottom shows which feeds are warm. Typewriter reveal kept.
"""

import random
import math
import threading

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


BG = (6, 11, 20)
PANEL_BG = (14, 24, 38)
TEXT_DIM = (110, 140, 165)

# channel -> (label, accent)
CHANNELS = {
    "orbital":  ("ORBITAL RELAY",  (92, 240, 150)),
    "archive":  ("ARCHIVE",        (216, 168, 88)),
    "wire":     ("THE WIRE",       (0, 225, 245)),
    "met":      ("MET STATION",    (255, 176, 44)),
    "lunar":    ("LUNAR WATCH",    (198, 205, 235)),
    "protocol": ("LOCAL PROTOCOL", (255, 160, 60)),
}


def classify(text):
    t = text.upper()
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
    """System Protocol terminal with per-channel styling."""

    TYPE_SPEED = 26.0
    HOLD_TIME = 1.0
    FADE_TIME = 0.55
    FUN_DISPLAY_TIME = 120.0
    FETCH_INTERVAL = 300.0

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.protocol = SystemProtocol()

        self.title_font = pygame.font.Font(None, s(24))
        self.greeting_font = pygame.font.Font(None, s(28))
        self.meta_font = pygame.font.Font(None, s(15))

        self.target_greeting = ""
        self.visible_text = ""
        self.next_greeting = None
        self.channel = "protocol"

        self.phase = "typing"
        self.phase_timer = 0.0
        self.reveal_progress = 0.0
        self.cursor_timer = 0.0
        self.cursor_on = True
        self.global_time = 0.0

        self.fun_messages = self.protocol.next_messages(2)
        self.fun_index = 0
        self.fun_timer = 0.0
        self.fetch_timer = self.FETCH_INTERVAL
        self.is_fetching = False
        self.lock = threading.Lock()

        panel_w = min(s(300), SCREEN_WIDTH - s(24))
        panel_h = s(230)
        self.panel_rect = pygame.Rect((SCREEN_WIDTH - panel_w) // 2,
                                      (SCREEN_HEIGHT - panel_h) // 2 - s(16),
                                      panel_w, panel_h)

        self.greeting_glow = None       # built per channel
        self._bg_surface = self._build_bg()
        self._set_greeting(self.fun_messages[0])

    # ══════════════════════════════════════════════════════════════════════
    def _build_bg(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(BG)
        for y in range(0, SCREEN_HEIGHT, 4):
            pygame.draw.line(surf, (10, 18, 30), (0, y), (SCREEN_WIDTH, y))
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
        accent = self._accent()
        self.greeting_glow = GlowText(
            self.greeting_font, "", (255, 255, 255),
            lerp_color(accent, (0, 0, 0), 0.25), 4,
            max_width=self.panel_rect.w - s(40),
        )

    def _fetch_fun_messages(self):
        """Refill the rotation from the protocol engine (live feeds mix in)."""
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
        """Small procedural channel icon in the accent color."""
        accent = self._accent()
        dim = lerp_color(accent, PANEL_BG, 0.35)
        ch = self.channel
        if ch == "orbital":
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
        else:  # protocol: terminal prompt
            pygame.draw.line(surface, accent, (cx - r + 2, cy - r // 2),
                             (cx - 2, cy), 2)
            pygame.draw.line(surface, accent, (cx - 2, cy),
                             (cx - r + 2, cy + r // 2), 2)
            pygame.draw.line(surface, accent, (cx + 2, cy + r // 2),
                             (cx + r - 2, cy + r // 2), 2)

    def draw(self, surface):
        surface.blit(self._bg_surface, (0, 0))
        accent = self._accent()
        label = CHANNELS[self.channel][0]
        pr = self.panel_rect

        # pulsing halo in the channel color
        pulse = 0.5 + 0.5 * math.sin(self.global_time * 2.0)
        halo = pygame.Surface((pr.w + s(20), pr.h + s(20)), pygame.SRCALPHA)
        pygame.draw.rect(halo, (*lerp_color(accent, (0, 0, 0), 0.55),
                                int(40 + 35 * pulse)),
                         halo.get_rect(), border_radius=s(14))
        surface.blit(halo, (pr.x - s(10), pr.y - s(10)))

        # panel + header
        pygame.draw.rect(surface, PANEL_BG, pr, border_radius=s(8))
        pygame.draw.rect(surface, accent, pr, 2, border_radius=s(8))
        header = pygame.Rect(pr.x, pr.y, pr.w, s(30))
        pygame.draw.rect(surface, lerp_color(PANEL_BG, accent, 0.12), header,
                         border_top_left_radius=s(8), border_top_right_radius=s(8))
        pygame.draw.line(surface, accent, (pr.x, header.bottom),
                         (pr.right, header.bottom), 1)
        title = self.title_font.render("SYSTEM PROTOCOL", True, (210, 230, 245))
        surface.blit(title, (pr.x + s(10), pr.y + s(7)))
        tag = self.meta_font.render(label, True, accent)
        surface.blit(tag, (pr.right - tag.get_width() - s(10), pr.y + s(10)))

        # channel icon
        self._draw_icon(surface, pr.centerx, header.bottom + s(24), s(11))

        # message with typewriter + fade
        gs = self.greeting_glow.get_surface()
        gx = pr.centerx - gs.get_width() // 2
        gy = pr.centery - gs.get_height() // 2 + s(20)
        if self.phase == "fade":
            faded = gs.copy()
            faded.set_alpha(int(255 * (1 - min(1.0, self.phase_timer / self.FADE_TIME))))
            surface.blit(faded, (gx, gy))
        else:
            surface.blit(gs, (gx, gy))
        if self.phase == "typing" and self.cursor_on:
            pygame.draw.rect(surface, accent,
                             (gx + gs.get_width() + s(3), gy + s(6), s(7), s(18)))

        # bottom rivet dots (kept from the old design)
        for x in range(pr.left + s(12), pr.right - s(8), s(16)):
            pygame.draw.circle(surface, lerp_color(accent, PANEL_BG, 0.5),
                               (x, pr.bottom - s(10)), 1)

        # ── UPLINKS row: which feeds are warm ────────────────────────────
        uy = pr.bottom + s(24)
        feeds = [("ORB", "iss"), ("ARC", "history"), ("WIRE", "wire"),
                 ("MET", "wx"), ("LUN", None)]           # moon is always local
        total_w = len(feeds) * s(52)
        ux = (SCREEN_WIDTH - total_w) // 2
        lbl = self.meta_font.render("UPLINKS", True, TEXT_DIM)
        surface.blit(lbl, ((SCREEN_WIDTH - lbl.get_width()) // 2, uy - s(16)))
        for i, (name, key) in enumerate(feeds):
            x = ux + i * s(52) + s(26)
            warm = True if key is None else (FEEDS_ENABLED and
                                             _FEEDS[key].value is not None)
            col = (92, 240, 150) if warm else (60, 70, 85)
            pygame.draw.circle(surface, col, (x - s(16), uy + s(4)), s(3))
            if warm and int(self.global_time * 2) % 2 == 0:
                pygame.draw.circle(surface, col, (x - s(16), uy + s(4)), s(5), 1)
            nm = self.meta_font.render(name, True, col if warm else TEXT_DIM)
            surface.blit(nm, (x - s(9), uy - s(2)))

        meta = self.meta_font.render(f"KEA // {self.protocol.name}", True, TEXT_DIM)
        surface.blit(meta, (pr.x + s(2), pr.y - s(18)))

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        time_str = f"{mins:02d}:{secs:02d}"
        font = self.meta_font
        label = font.render(time_str, True, (255, 255, 255))
        bg_rect = label.get_rect(bottomleft=(s(8), SCREEN_HEIGHT - s(8)))
        bg_rect.inflate_ip(s(10), s(6))
        pygame.draw.rect(surface, PANEL_BG, bg_rect, border_radius=s(4))
        pygame.draw.rect(surface, (95, 165, 210), bg_rect, 1, border_radius=s(4))
        surface.blit(label, label.get_rect(center=bg_rect.center))
