import pygame
import math
import json
import threading
import urllib.request
from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from ui.glow_text import GlowText


class GreetingsState(State):
    """System-style animated greetings screen with typewriter reveal."""

    TYPE_SPEED = 26.0
    HOLD_TIME = 1.0
    FADE_TIME = 0.55
    FUN_DISPLAY_TIME = 7.0
    FETCH_INTERVAL = 300.0

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.title_font = pygame.font.Font(None, 26)
        self.greeting_font = pygame.font.Font(None, 30)
        self.meta_font = pygame.font.Font(None, 16)

        self.target_greeting = "DEXTER, LOADING SOMETHING FUN..."
        self.visible_text = ""
        self.next_greeting = None

        self.phase = "typing"
        self.phase_timer = 0.0
        self.reveal_progress = 0.0
        self.cursor_timer = 0.0
        self.cursor_on = True
        self.global_time = 0.0

        # Similar cadence to CurrentAffairs / useless facts style
        self.fun_messages = [
            "DEXTER, LOADING SOMETHING FUN...",
            "DEX, PREPARING A FRESH LITTLE SURPRISE...",
        ]
        self.fun_index = 0
        self.fun_timer = 0.0
        self.fetch_timer = self.FETCH_INTERVAL
        self.is_fetching = False
        self.lock = threading.Lock()

        self.greeting_glow = GlowText(
            self.greeting_font,
            "",
            (255, 255, 255),
            (120, 215, 255),
            4,
            max_width=min(300, SCREEN_WIDTH - 56),
        )

        self._frame_surface = self._build_frame_surface()
        self._set_greeting(self.fun_messages[0])

    def _build_frame_surface(self):
        """Pre-render static UI frame for lower per-frame work."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        panel_w = min(340, SCREEN_WIDTH - 24)
        panel_h = 220
        self.panel_rect = pygame.Rect(
            (SCREEN_WIDTH - panel_w) // 2,
            (SCREEN_HEIGHT - panel_h) // 2 - 10,
            panel_w,
            panel_h,
        )

        pygame.draw.rect(surf, (14, 24, 38, 220), self.panel_rect, border_radius=8)
        pygame.draw.rect(surf, (95, 165, 210), self.panel_rect, 2, border_radius=8)

        header_rect = pygame.Rect(self.panel_rect.x, self.panel_rect.y, self.panel_rect.width, 34)
        pygame.draw.rect(surf, (22, 42, 62, 230), header_rect, border_top_left_radius=8, border_top_right_radius=8)
        pygame.draw.line(surf, (125, 195, 235), (header_rect.x, header_rect.bottom), (header_rect.right, header_rect.bottom), 1)

        for x in range(self.panel_rect.left + 12, self.panel_rect.right - 8, 16):
            pygame.draw.circle(surf, (68, 120, 160), (x, self.panel_rect.bottom - 12), 1)

        return surf

    def _set_greeting(self, text):
        self.target_greeting = text
        self.visible_text = ""
        self.reveal_progress = 0.0
        self.phase_timer = 0.0
        self.phase = "typing"

        self.greeting_glow.update_text("")

    def _fetch_json(self, url):
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())

    def _normalize_line(self, line, max_len=120):
        text = " ".join(str(line).strip().split())
        if not text:
            return ""
        if len(text) > max_len:
            text = text[: max_len - 3].rstrip() + "..."
        return text.upper()

    def _fetch_fun_messages(self):
        """Fetch fun greetings from public APIs without blocking the render loop."""
        try:
            new_messages = []

            # Advice Slip API
            try:
                advice_data = self._fetch_json("https://api.adviceslip.com/advice")
                advice = advice_data.get("slip", {}).get("advice", "")
                advice_line = self._normalize_line(f"DEXTER, {advice}")
                if advice_line:
                    new_messages.append(advice_line)
            except Exception:
                pass

            # Affirmations API
            try:
                affirmation_data = self._fetch_json("https://www.affirmations.dev/")
                affirmation = affirmation_data.get("affirmation", "")
                affirmation_line = self._normalize_line(f"DEXTER, {affirmation}")
                if affirmation_line:
                    new_messages.append(affirmation_line)
            except Exception:
                pass

            # Fallback: keep defaults if all APIs fail
            if new_messages:
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
                    next_text = self.next_greeting
                    self.next_greeting = None
                    self._set_greeting(next_text)
                else:
                    self.phase = "hold"
                    self.phase_timer = 0.0

    def draw(self, surface):
        # Dark UI background + subtle scanlines
        surface.fill((6, 11, 20))
        for y in range(0, SCREEN_HEIGHT, 4):
            pygame.draw.line(surface, (10, 18, 30), (0, y), (SCREEN_WIDTH, y))

        # Soft pulse behind the panel
        pulse = 0.5 + 0.5 * math.sin(self.global_time * 2.0)
        halo = pygame.Surface((self.panel_rect.width + 20, self.panel_rect.height + 20), pygame.SRCALPHA)
        pygame.draw.rect(
            halo,
            (40, 110, 160, int(45 + 35 * pulse)),
            halo.get_rect(),
            border_radius=14,
        )
        surface.blit(halo, (self.panel_rect.x - 10, self.panel_rect.y - 10))

        surface.blit(self._frame_surface, (0, 0))

        title = self.title_font.render("GREETING PROTOCOL", True, (190, 230, 255))
        surface.blit(title, (self.panel_rect.x + 10, self.panel_rect.y + 8))

        greet_surf = self.greeting_glow.get_surface()
        gx = self.panel_rect.centerx - greet_surf.get_width() // 2
        gy = self.panel_rect.centery - greet_surf.get_height() // 2 + 4

        if self.phase == "fade":
            fade_ratio = min(1.0, self.phase_timer / self.FADE_TIME)
            alpha = int(255 * (1.0 - fade_ratio))
            faded = greet_surf.copy()
            faded.set_alpha(alpha)
            surface.blit(faded, (gx, gy))
        else:
            surface.blit(greet_surf, (gx, gy))

        if self.phase == "typing" and self.cursor_on:
            cursor_x = gx + greet_surf.get_width() + 3
            cursor_y = gy + 6
            pygame.draw.rect(surface, (180, 230, 255), (cursor_x, cursor_y, 8, 20))

        scanline_y = self.panel_rect.bottom + 24
        meta = self.meta_font.render("DEXTER / DEX", True, (120, 175, 215))
        surface.blit(meta, (self.panel_rect.x + 10, scanline_y))

    def draw_pomodoro(self, surface, time_left, mode):
        """Bottom-left Pomodoro badge so greeting content remains unobstructed."""
        mins = int(time_left) // 60
        secs = int(time_left) % 60
        time_str = f"{mins:02d}:{secs:02d}"

        font = self.meta_font
        label = font.render(time_str, True, (255, 255, 255))
        pad = 8
        bg_rect = label.get_rect(bottomleft=(6, SCREEN_HEIGHT - 6))
        bg_rect.inflate_ip(pad * 2, pad)

        color = (145, 30, 30, 180) if mode == 'work' else (35, 130, 75, 180)
        bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg.fill(color)
        surface.blit(bg, bg_rect.topleft)
        surface.blit(label, label.get_rect(center=bg_rect.center))
