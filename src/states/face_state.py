"""
face_state.py
-------------
KEA'S FACE — the living, expressive companion state.

A dedicated monitor station and diagnostic companion for Kea:
- Plays the 8-frame sequential animation loops (CRT Face Lens & Full-Body Droid).
- Reacts in real-time to machine state (docket backlog, focus sessions, core thermals).
- Responds to physical controls with astromech chirps and animated expressions.

Controls:
    ENCODER turn    Cycle expressions / mood override (AUTO, SERENE, HAPPY, ALERT, SLEEP, GLITCH)
    ENCODER press   Poke Kea — triggers a curious/startled chirp and joyful hop
    GREEN           Praise Kea — bright happy chirp, logs praise in lifebook
    RED             Boop / Palette Shift — cycles visor glow color (Cyan, Amber, Magenta, Acid)
    TOGGLE          Auto Mood (tracks real system state vs manual lock)
    SPACE / TAB     Toggle between CRT Face and Droid Mascot
"""

import math
import os
import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from ui import palette as pal
from backend import vitals, lifebook, voice
from backend.reminders import ReminderService

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FACE_DIR = os.path.join(ROOT, "assets", "sprites", "face")
DROID_DIR = os.path.join(ROOT, "assets", "sprites", "droid")

# Mood definitions: name -> (label, accent_color, chirp, frame_speed)
MOODS = [
    ("auto",   "AUTO LINK", pal.CYAN,    "blip",      0.14),
    ("serene", "SERENE",    pal.CYAN,    "wake",      0.16),
    ("happy",  "DELIGHTED", pal.ACID,    "happy",     0.09),
    ("alert",  "WARNING",   pal.BLOOD,   "alarm",     0.08),
    ("sleepy", "DROWSY",    pal.INK_DIM, "question",  0.22),
    ("glitch", "FEVERISH",  pal.MAGENTA, "worried",   0.06),
]

VISOR_COLORS = [
    ("CYAN", pal.CYAN),
    ("ACID", pal.ACID),
    ("AMBER", pal.AMBER),
    ("MAGENTA", pal.MAGENTA),
    ("ICE", pal.ICE),
]


class FaceState(State):
    """The living companion face: 8-frame animations, live vitals, and expressive mood."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.font_title = pygame.font.Font(None, s(24))
        self.font_mood = pygame.font.Font(None, s(32))
        self.font_stat = pygame.font.Font(None, s(18))
        self.font_small = pygame.font.Font(None, s(14))

        self.reminders = ReminderService.instance()

        # Load 8-frame animation assets
        self.face_frames = self._load_frames(FACE_DIR, 8)
        self.droid_frames = self._load_frames(DROID_DIR, 8)

        self.model = "face"          # "face" or "droid"
        self.mood_idx = 0            # 0 = auto
        self.color_idx = 0
        self.auto_mood = True

        # Animation playback
        self.frame_idx = 0
        self.frame_timer = 0.0
        self.poke_timer = 0.0
        self.t = 0.0

        self.praise_flash = 0.0
        self.status_msg = ""
        self.status_timer = 0.0

        self._bg = self._build_bg()

    def _load_frames(self, directory, count):
        frames = []
        for i in range(count):
            p = os.path.join(directory, f"frame_{i}.png")
            if os.path.exists(p):
                try:
                    surf = pygame.image.load(p).convert_alpha()
                    frames.append(surf)
                except Exception:
                    pass
        return frames

    def _build_bg(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(pal.VOID)

        # Blueprint / terminal grid
        g = pal.grid((SCREEN_WIDTH, SCREEN_HEIGHT), colour=pal.GRID, step=s(24))
        surf.blit(g, (0, 0))

        # Top diagnostic bar
        pygame.draw.line(surf, pal.EDGE, (s(12), s(38)), (SCREEN_WIDTH - s(12), s(38)), 1)
        # Center bezel framing
        bezel_rect = pygame.Rect(s(24), s(48), SCREEN_WIDTH - s(48), s(330))
        pal.bevel(surf, bezel_rect, colour=pal.EDGE, cut=s(8))

        return surf

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def enter(self):
        self.t = 0.0
        self.frame_idx = 0
        self.frame_timer = 0.0
        self.poke_timer = 0.0
        self.status_msg = "COMPANION LINK ONLINE"
        self.status_timer = 2.5
        voice.say("wake")

    # ── Mood Evaluation ───────────────────────────────────────────────────
    def _effective_mood(self):
        """Evaluate real-time mood from system state if in Auto mode."""
        if not self.auto_mood and self.mood_idx > 0:
            return MOODS[self.mood_idx]

        # 1. Overdue reminders -> Alert
        try:
            if self.reminders.overdue():
                return MOODS[3]       # alert / warning
        except Exception:
            pass

        # 2. Hot thermal level -> Glitch
        therm = vitals.thermal_level()
        if therm in ("hot", "warn"):
            return MOODS[5]           # feverish

        # 3. Focus mode running -> Delighted / Focused
        try:
            pom = self.manager.states.get("pomodoro")
            if pom and getattr(pom, "running", False):
                return MOODS[2]       # happy / productive
        except Exception:
            pass

        # 4. Small hours (01:00 - 06:00) -> Sleepy
        import datetime
        hr = datetime.datetime.now().hour
        if 1 <= hr < 6:
            return MOODS[4]           # sleepy

        # 5. Baseline serene
        return MOODS[1]               # serene

    # ── Controls ───────────────────────────────────────────────────────────
    def move_cursor(self, delta):
        """Rotary encoder: cycles expression moods."""
        self.mood_idx = (self.mood_idx + delta) % len(MOODS)
        self.auto_mood = (self.mood_idx == 0)
        mood = self._effective_mood()
        self.status_msg = f"MOOD: {mood[1]}"
        self.status_timer = 2.0
        voice.say("blip")
        return True

    def activate(self):
        """Encoder press: Poke Kea!"""
        self.poke_timer = 1.0
        self.frame_idx = 6 if self.model == "droid" else 5     # jump / smile
        lifebook.bump("face_pokes")
        voice.say("curious")
        self.status_msg = "POKED! *CHIRP*"
        self.status_timer = 2.0
        return True

    def on_green_button(self):
        """GREEN button: Praise / pet Kea."""
        self.praise_flash = 1.2
        self.frame_idx = 6 if self.model == "droid" else 5
        count = lifebook.bump("face_praise")
        voice.say("happy")
        self.status_msg = f"PRAISED! (x{count})"
        self.status_timer = 2.5
        return True

    def on_red_button(self):
        """RED button: Boop / Shift Visor Tint."""
        self.color_idx = (self.color_idx + 1) % len(VISOR_COLORS)
        cname, _ = VISOR_COLORS[self.color_idx]
        self.status_msg = f"VISOR TINT: {cname}"
        self.status_timer = 2.0
        voice.say("blip")
        return True

    def on_toggle(self, on):
        """Toggle switch: Auto Mood vs Manual."""
        self.auto_mood = on
        if on:
            self.mood_idx = 0
            self.status_msg = "AUTO MOOD: ENGAGED"
        else:
            if self.mood_idx == 0:
                self.mood_idx = 1
            self.status_msg = f"MANUAL MOOD: {MOODS[self.mood_idx][1]}"
        self.status_timer = 2.0

    def toggle_label(self):
        return "AUTO MOOD" if self.auto_mood else "MANUAL"

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_TAB):
                    self.model = "droid" if self.model == "face" else "face"
                    self.status_msg = f"MODEL: {self.model.upper()}"
                    self.status_timer = 2.0
                    voice.say("blip")
                elif event.key == pygame.K_g:
                    self.on_green_button()
                elif event.key == pygame.K_r:
                    self.on_red_button()
                elif event.key == pygame.K_p:
                    self.activate()

    # ── Update ─────────────────────────────────────────────────────────────
    def update(self, dt):
        self.t += dt
        if self.status_timer > 0:
            self.status_timer -= dt
        if self.praise_flash > 0:
            self.praise_flash -= dt
        if self.poke_timer > 0:
            self.poke_timer -= dt

        # Frame animation speed based on current mood
        mood = self._effective_mood()
        frame_dur = mood[4]

        self.frame_timer += dt
        if self.frame_timer >= frame_dur:
            self.frame_timer = 0.0
            frames = self.face_frames if self.model == "face" else self.droid_frames
            if frames:
                self.frame_idx = (self.frame_idx + 1) % len(frames)

    # ── Draw ────────────────────────────────────────────────────────────────
    def draw(self, surface):
        surface.blit(self._bg, (0, 0))

        mood = self._effective_mood()
        m_name, m_label, m_col, _, _ = mood
        _, visor_col = VISOR_COLORS[self.color_idx]

        # Top Header
        title = self.font_title.render("K E A  //  C O M P A N I O N", True, pal.INK)
        surface.blit(title, (s(16), s(10)))

        # Header Vitals (right-aligned)
        t_c = vitals.core_temp_c()
        t_str = f"{round(t_c)}°C" if t_c is not None else "--"
        up_str = vitals.uptime_str()
        vit_txt = self.font_stat.render(f"CORE {t_str} · UP {up_str}", True, pal.INK_DIM)
        surface.blit(vit_txt, (SCREEN_WIDTH - vit_txt.get_width() - s(16), s(14)))

        # Center Screen Bezel & Halo
        center_x = SCREEN_WIDTH // 2
        center_y = s(195)
        halo_col = m_col if self.praise_flash <= 0 else pal.GOLD
        h = pal.halo(s(70), halo_col, alpha=50 if self.praise_flash <= 0 else 100)
        surface.blit(h, (center_x - h.get_width() // 2, center_y - h.get_height() // 2))

        # Animated Sprite Frame
        frames = self.face_frames if self.model == "face" else self.droid_frames
        if frames and 0 <= self.frame_idx < len(frames):
            frame = frames[self.frame_idx]
            # Scale frame nicely into the central monitor
            if self.model == "face":
                target_w, target_h = s(200), s(200)
            else:
                target_w, target_h = s(100), s(220)

            scaled_frame = pygame.transform.smoothscale(frame, (target_w, target_h))
            surface.blit(scaled_frame, (center_x - target_w // 2, center_y - target_h // 2))

        # CRT Scanlines over the center screen
        scan = pal.scanlines((SCREEN_WIDTH - s(48), s(330)), alpha=24, step=s(3))
        surface.blit(scan, (s(24), s(48)))

        # Mood & Status readout inside the viewport
        pal.blit_glow(surface, self.font_mood, m_label, halo_col,
                      (center_x - self.font_mood.size(m_label)[0] // 2, s(58)),
                      radius=s(2), strength=100)

        # Bottom HUD stats (above reserved strip)
        hud_y = s(385)
        model_str = f"MODEL [{self.model.upper()}] · [SPACE]"
        m_txt = self.font_small.render(model_str, True, pal.INK_DIM)
        surface.blit(m_txt, (s(16), hud_y))

        # Interactive status or action hint
        if self.status_timer > 0:
            msg_surf = self.font_small.render(self.status_msg, True, pal.AMBER)
        else:
            msg_surf = self.font_small.render("GRN: PRAISE  ·  RED: TINT  ·  DIAL: MOOD",
                                               True, pal.INK_FAINT)
        surface.blit(msg_surf, ((SCREEN_WIDTH - msg_surf.get_width()) // 2, hud_y))

        # Praise Counter
        praise_cnt = lifebook.get("face_praise", 0)
        p_txt = self.font_small.render(f"PRAISE {praise_cnt}", True, pal.ICE)
        surface.blit(p_txt, (SCREEN_WIDTH - p_txt.get_width() - s(16), hud_y))

    def draw_pomodoro(self, surface, time_left, mode):
        """Draw unique Pomodoro badge for Face state."""
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = pal.MAGENTA if mode == "work" else pal.ACID
        txt = self.font_stat.render(f"FOCUS {mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(16), s(52)))
        box = rect.inflate(s(8), s(4))
        pygame.draw.rect(surface, pal.PANEL, box, border_radius=s(3))
        pygame.draw.rect(surface, c, box, 1, border_radius=s(3))
        surface.blit(txt, rect)
