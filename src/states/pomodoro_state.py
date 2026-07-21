"""
pomodoro_state.py
-----------------
THE HOURGLASS — focus as a physical mechanism.

Brass frame, blown glass, and sand that actually falls in real time:
the level in the upper bulb *is* the time remaining, the mound growing
in the lower bulb is the time spent. A stream runs between them while
the timer is going and stops dead the moment you pause. When a session
ends the whole instrument flips over and the sand starts again — amber
for work, cool green for rest.

Three brass studs on the base track the cycle to the long rest.

Controls (unchanged): RED resets the session, GREEN starts/pauses.
"""

import pygame
import math
import random

from config import SCREEN_WIDTH, SCREEN_HEIGHT, WHITE
from states.base_state import State
from hardware_input import BUTTON_POMODORO_EVENT, BUTTON_NOTIFICATION_EVENT

WORK_TIME = 20 * 60
BREAK_TIME = 6 * 60
LONG_BREAK_TIME = 15 * 60
TRANSITION_TIME = 1.4          # long enough for the flip to read
CYCLE = 3                      # work sessions per long rest

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


# ── Palette ─────────────────────────────────────────────────────────────────
BG_TOP     = (22, 18, 16)
BG_BOT     = (12, 10, 10)
BRASS      = (176, 138, 66)
BRASS_LIT  = (226, 190, 116)
BRASS_DARK = (92, 70, 30)
GLASS      = (196, 214, 220)
TEXT_PALE  = (238, 228, 208)
TEXT_DIM   = (140, 124, 100)

SAND_WORK  = (228, 174, 86)
SAND_REST  = (126, 214, 174)


class PomodoroState(State):
    """Focus timer rendered as a working hourglass."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.font_time = pygame.font.Font(None, s(64))
        self.font_mode = pygame.font.Font(None, s(24))
        self.font_small = pygame.font.Font(None, s(15))

        self.mode = 'work'
        self.time_left = WORK_TIME
        self.session_len = WORK_TIME       # correct denominator, incl. long rest
        self.running = False
        self.break_count = 0
        self.transition_timer = 0.0
        self.transition_mode = None
        self.t = 0.0

        # hourglass geometry (local to its own surface, so it can rotate)
        self.hw = s(58)
        self.nw = s(5)
        self.bulb_h = s(110)
        self.pad = s(16)
        self.g_w = 2 * (self.hw + self.pad)
        self.g_h = 2 * self.bulb_h + 2 * s(13)
        self.g_center = (SCREEN_WIDTH // 2, s(94) + self.g_h // 2)

        self.grains = []                   # falling motes: [x_off, y, speed]
        self._bg = self._build_bg()

    # ══════════════════════════════════════════════════════════════════════
    def _build_bg(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            surf.fill(lerp_color(BG_TOP, BG_BOT, y / max(1, SCREEN_HEIGHT - 1)),
                      (0, y, SCREEN_WIDTH, 1))
        # faint workbench grain
        rng = random.Random(7)
        for _ in range(160):
            x, y = rng.randint(0, SCREEN_WIDTH - 1), rng.randint(0, SCREEN_HEIGHT - 1)
            surf.set_at((x, y), (30, 25, 22))
        # corner brackets
        m, l = s(7), s(15)
        for cx, cy, dx, dy in [(m, m, 1, 1), (SCREEN_WIDTH - m, m, -1, 1),
                               (m, SCREEN_HEIGHT - m, 1, -1),
                               (SCREEN_WIDTH - m, SCREEN_HEIGHT - m, -1, -1)]:
            pygame.draw.line(surf, BRASS_DARK, (cx, cy), (cx + dx * l, cy), 2)
            pygame.draw.line(surf, BRASS_DARK, (cx, cy), (cx, cy + dy * l), 2)
        return surf

    # ══════════════════════════════════════════════════════════════════════
    # Session control (behaviour preserved)
    # ══════════════════════════════════════════════════════════════════════
    def enter(self):
        pass

    # ── the deck toggle is this screen's run lever ──────────────────────
    def on_toggle(self, on):
        """Up = running, down = held. A position switch is exactly the
        right shape for a timer's run state."""
        if on != self.running:
            self.running = on
            from backend import voice
            voice.say("focus_start" if on else "blip")

    def toggle_label(self):
        return "RUN TIMER"

    def _begin_transition(self, mode_name):
        self.transition_mode = mode_name
        self.transition_timer = TRANSITION_TIME

    def _switch_to_break(self):
        from backend import lifebook, voice
        lifebook.bump("pomodoros")          # a work session completed
        lifebook.bump_day("focus")         # and into today's bucket
        self.break_count += 1
        self.mode = 'break'
        long_rest = self.break_count % CYCLE == 0
        # a full cycle earns a small fanfare; a single session, a chime
        voice.say("proud" if long_rest else "focus_done", force=True)
        self.time_left = LONG_BREAK_TIME if long_rest else BREAK_TIME
        self.session_len = self.time_left
        self.running = True
        self._begin_transition('LONG REST' if long_rest else 'REST')
        if self.manager.current_state_name != 'pomodoro':
            self.manager.change_state('pomodoro')

    def _switch_to_work(self):
        from backend import voice
        self.mode = 'work'
        self.time_left = WORK_TIME
        self.session_len = WORK_TIME
        self.running = True
        voice.say("focus_start", force=True)
        self._begin_transition('FOCUS')
        if self.manager.current_state_name != 'pomodoro':
            self.manager.change_state('pomodoro')

    def handle_events(self, events):
        for event in events:
            if event.type == BUTTON_NOTIFICATION_EVENT:
                self.running = not self.running
            elif event.type == BUTTON_POMODORO_EVENT:
                # reset the current session to its full length
                self.time_left = self.session_len
                self.running = False
                self.transition_timer = 0.0
                self.transition_mode = None
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.running = not self.running

    def update(self, dt):
        self.t += dt

        if self.running:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                if self.mode == 'work':
                    self._switch_to_break()
                else:
                    self._switch_to_work()

        if self.transition_timer > 0:
            self.transition_timer = max(0.0, self.transition_timer - dt)

        # falling grains in the neck
        if self.running and self.transition_timer <= 0 and self.time_left > 0:
            if len(self.grains) < 7 and random.random() < dt * 26:
                self.grains.append([random.uniform(-1.6, 1.6) * SCALE, 0.0,
                                    random.uniform(90, 150) * SCALE])
            for g in self.grains:
                g[1] += g[2] * dt
            self.grains = [g for g in self.grains if g[1] < self.bulb_h]
        else:
            self.grains = []

    # ══════════════════════════════════════════════════════════════════════
    # The instrument
    # ══════════════════════════════════════════════════════════════════════
    def _hw_at(self, y, ly0, lyn, ly1):
        """Half-width of the glass at local y."""
        if y <= lyn:
            k = (y - ly0) / max(1e-6, lyn - ly0)
            return self.hw + (self.nw - self.hw) * k
        k = (y - lyn) / max(1e-6, ly1 - lyn)
        return self.nw + (self.hw - self.nw) * k

    def _render_glass(self, frac, sand):
        """Draw the hourglass into its own surface so it can be flipped."""
        g = pygame.Surface((self.g_w, self.g_h), pygame.SRCALPHA)
        cx = self.g_w // 2
        ly0 = s(13)
        lyn = ly0 + self.bulb_h
        ly1 = lyn + self.bulb_h
        hw, nw = self.hw, self.nw

        top_poly = [(cx - hw, ly0), (cx + hw, ly0), (cx + nw, lyn), (cx - nw, lyn)]
        bot_poly = [(cx - nw, lyn), (cx + nw, lyn), (cx + hw, ly1), (cx - hw, ly1)]

        # glass body: faint tint, and a soft highlight down the left wall
        # (drawn UNDER the sand so it never reads as a crack in the glass)
        for poly in (top_poly, bot_poly):
            pygame.draw.polygon(g, (*GLASS, 26), poly)
        pygame.draw.line(g, (*GLASS, 40), (cx - hw * 0.66, ly0 + s(10)),
                         (cx - nw * 1.5, lyn - s(8)), 2)
        pygame.draw.line(g, (*GLASS, 30), (cx - nw * 1.5, lyn + s(8)),
                         (cx - hw * 0.66, ly1 - s(10)), 2)

        # ── sand in the upper bulb: drains from its top surface down ────
        if frac > 0.001:
            sy = ly0 + (1.0 - frac) * (lyn - ly0)
            w_at = self._hw_at(sy, ly0, lyn, ly1)
            pygame.draw.polygon(g, sand,
                                [(cx - w_at, sy), (cx + w_at, sy),
                                 (cx + nw, lyn), (cx - nw, lyn)])
            # a lighter meniscus on the surface
            pygame.draw.line(g, lerp_color(sand, (255, 255, 255), 0.45),
                             (cx - w_at, sy), (cx + w_at, sy), 2)
            # slight funnel dimple where it drains
            if frac < 0.985:
                pygame.draw.polygon(g, lerp_color(sand, (0, 0, 0), 0.35),
                                    [(cx - s(9), sy), (cx + s(9), sy),
                                     (cx, sy + s(7))])

        # ── sand piled in the lower bulb ────────────────────────────────
        fill = (1.0 - frac) * (ly1 - lyn)
        if fill > 0.5:
            level = ly1 - fill
            w_at = self._hw_at(level, ly0, lyn, ly1)
            pygame.draw.polygon(g, sand,
                                [(cx - w_at, level), (cx + w_at, level),
                                 (cx + hw, ly1), (cx - hw, ly1)])
            # conical mound, flattening as the bulb fills
            mound_h = min(s(15), fill * 0.42)
            mound_w = max(s(8), w_at * 0.72)
            pygame.draw.polygon(g, lerp_color(sand, (255, 255, 255), 0.18),
                                [(cx - mound_w, level), (cx, level - mound_h),
                                 (cx + mound_w, level)])

        # ── the falling stream ──────────────────────────────────────────
        if self.grains:
            stream_bottom = ly1 - fill - s(6)
            jitter = math.sin(self.t * 21) * 0.9 * SCALE
            pygame.draw.line(g, lerp_color(sand, (255, 255, 255), 0.25),
                             (cx + jitter, lyn), (cx, max(lyn, stream_bottom)), 2)
            for gx, gy, _sp in self.grains:
                py = lyn + gy
                if py < ly1 - fill:
                    pygame.draw.circle(g, sand, (int(cx + gx), int(py)), max(1, s(2)))

        # ── glass outline over everything ───────────────────────────────
        for poly in (top_poly, bot_poly):
            pygame.draw.polygon(g, lerp_color(GLASS, BG_TOP, 0.35), poly, 2)

        # ── brass frame: caps and posts ─────────────────────────────────
        for cap_y in (ly0 - s(13), ly1):
            cap = pygame.Rect(cx - hw - s(11), cap_y, 2 * (hw + s(11)), s(13))
            pygame.draw.rect(g, BRASS, cap, border_radius=s(3))
            pygame.draw.rect(g, BRASS_DARK, cap, 1, border_radius=s(3))
            pygame.draw.line(g, BRASS_LIT, (cap.x + s(4), cap.y + s(3)),
                             (cap.right - s(4), cap.y + s(3)), 1)
        for px in (cx - hw - s(6), cx + hw + s(6)):
            pygame.draw.line(g, BRASS, (px, ly0 - s(2)), (px, ly1 + s(2)), s(4))
            pygame.draw.line(g, BRASS_LIT, (px - 1, ly0 - s(2)), (px - 1, ly1 + s(2)), 1)
        return g

    # ══════════════════════════════════════════════════════════════════════
    def draw(self, surface):
        surface.blit(self._bg, (0, 0))
        work = self.mode == 'work'
        sand = SAND_WORK if work else SAND_REST
        frac = max(0.0, min(1.0, self.time_left / max(1e-6, self.session_len)))

        # ── mode plate ──────────────────────────────────────────────────
        label = "FOCUS" if work else (
            "LONG REST" if self.session_len == LONG_BREAK_TIME else "REST")
        lab = self.font_mode.render(label, True, sand)
        plate = lab.get_rect(midtop=(SCREEN_WIDTH // 2, s(26))).inflate(s(26), s(10))
        pygame.draw.rect(surface, (30, 25, 20), plate, border_radius=s(4))
        pygame.draw.rect(surface, BRASS_DARK, plate, 1, border_radius=s(4))
        surface.blit(lab, lab.get_rect(midtop=(SCREEN_WIDTH // 2, s(26))))

        # ── the hourglass, flipping between sessions ────────────────────
        glass = self._render_glass(frac, sand)
        if self.transition_timer > 0:
            p = 1.0 - (self.transition_timer / TRANSITION_TIME)
            angle = 180.0 * (p * p * (3 - 2 * p))       # smoothstep flip
            glass = pygame.transform.rotozoom(glass, angle, 1.0)
        rect = glass.get_rect(center=self.g_center)
        surface.blit(glass, rect)

        # ── time readout on a brass plate ───────────────────────────────
        mins, secs = int(self.time_left) // 60, int(self.time_left) % 60
        tsurf = self.font_time.render(f"{mins:02d}:{secs:02d}", True, TEXT_PALE)
        trect = tsurf.get_rect(midtop=(SCREEN_WIDTH // 2, s(356)))
        back = trect.inflate(s(30), s(12))
        pygame.draw.rect(surface, (28, 23, 19), back, border_radius=s(5))
        pygame.draw.rect(surface, BRASS_DARK, back, 1, border_radius=s(5))
        surface.blit(tsurf, trect)
        if not self.running and self.transition_timer <= 0:
            if int(self.t * 1.6) % 2 == 0:
                hold = self.font_small.render("HELD", True, BRASS_LIT)
                surface.blit(hold, (back.right + s(6), back.centery - s(6)))

        # ── cycle studs: work sessions banked toward the long rest ──────
        done = self.break_count % CYCLE
        dot_y = s(410)
        for i in range(CYCLE):
            dx = SCREEN_WIDTH // 2 + (i - (CYCLE - 1) / 2) * s(24)
            filled = i < done
            pygame.draw.circle(surface, BRASS if filled else (44, 38, 32),
                               (int(dx), dot_y), s(6))
            pygame.draw.circle(surface, BRASS_DARK, (int(dx), dot_y), s(6), 1)
            if filled:
                pygame.draw.circle(surface, BRASS_LIT,
                                   (int(dx - s(2)), dot_y - s(2)), s(2))
        cyc = self.font_small.render(
            f"{done}/{CYCLE} TO LONG REST", True, TEXT_DIM)
        surface.blit(cyc, ((SCREEN_WIDTH - cyc.get_width()) // 2, dot_y + s(12)))

        # ── transition banner ───────────────────────────────────────────
        if self.transition_timer > 0 and self.transition_mode:
            alpha = int(220 * min(1.0, self.transition_timer / TRANSITION_TIME))
            band = pygame.Surface((SCREEN_WIDTH, s(34)), pygame.SRCALPHA)
            band.fill((*sand, min(200, alpha)))
            surface.blit(band, (0, s(212)))
            btxt = self.font_mode.render(f"— {self.transition_mode} —", True,
                                         (26, 20, 16))
            surface.blit(btxt, btxt.get_rect(center=(SCREEN_WIDTH // 2, s(229))))

        # ── footer hint ─────────────────────────────────────────────────
        hint = self.font_small.render(
            "GREEN  START / HOLD      RED  RESET", True, TEXT_DIM)
        surface.blit(hint, ((SCREEN_WIDTH - hint.get_width()) // 2,
                            SCREEN_HEIGHT - s(22)))

    # ══════════════════════════════════════════════════════════════════════
    def draw_overlay(self, surface):
        """Fallback badge for any state without its own draw_pomodoro."""
        if not self.running:
            return
        mins, secs = int(self.time_left) // 60, int(self.time_left) % 60
        txt = self.font_small.render(f"{mins:02d}:{secs:02d}", True, WHITE)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(6), s(6)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, SAND_WORK if self.mode == 'work' else SAND_REST,
                         box, border_radius=s(3))
        surface.blit(txt, rect)
