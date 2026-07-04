"""
telegraph_state.py
------------------
Steampunk Punch-Tape Telegraph — Ambient Screen for Raspberry Pi.

Portrait-first redesign: brass header plate with rising steam, ITA2
punch-tape machine band with visible spools and a reading head, and the
decoded transmission typed letter-by-letter onto an aged TELEGRAM card
with a wax seal. All static layers are pre-rendered; the per-frame cost
is blits + the moving tape.
"""

import pygame
import random
import math
import datetime

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from current_affairs import CurrentAffairs

# ── ITA2 / Baudot-Murray 5-bit codes (authentic) ────────────────────────────
ITA2 = {
    'A': [1,1,0,0,0], 'B': [1,0,0,1,1], 'C': [0,1,1,1,0],
    'D': [1,0,0,1,0], 'E': [1,0,0,0,0], 'F': [1,0,1,1,0],
    'G': [0,1,0,1,1], 'H': [0,0,1,0,1], 'I': [0,1,1,0,0],
    'J': [1,1,0,1,0], 'K': [1,1,1,1,0], 'L': [0,1,0,0,1],
    'M': [0,0,1,1,1], 'N': [0,0,1,1,0], 'O': [0,0,0,1,1],
    'P': [0,1,1,0,1], 'Q': [1,1,1,0,1], 'R': [0,1,0,1,0],
    'S': [1,0,1,0,0], 'T': [0,0,0,0,1], 'U': [1,1,1,0,0],
    'V': [0,1,1,1,1], 'W': [1,1,0,0,1], 'X': [1,0,1,1,1],
    'Y': [1,0,1,0,1], 'Z': [1,0,0,0,1],
    '0': [0,1,1,0,1], '1': [1,1,1,0,1], '2': [1,1,0,0,1],
    '3': [1,0,0,0,0], '4': [0,1,0,1,0], '5': [0,0,0,0,1],
    '6': [1,0,1,0,1], '7': [1,1,1,0,0], '8': [0,1,1,0,0],
    '9': [0,0,0,1,1],
    ' ': [0,0,1,0,0], '.': [0,1,1,0,1], ',': [0,0,0,1,1],
    '-': [0,0,0,0,0], ':': [1,1,1,0,0], '?': [1,1,0,0,1],
    "'": [0,0,0,1,0], '/': [1,0,1,1,0], '(': [1,1,1,1,0],
    ')': [1,1,0,1,0],
}


def char_to_bits(ch):
    return ITA2.get(ch.upper(), [random.randint(0, 1) for _ in range(5)])


# ── Palette ──────────────────────────────────────────────────────────────────
BG_TOP       = ( 24,  14,   7)
BG_BOTTOM    = ( 12,   7,   3)
PANEL_DARK   = ( 30,  18,   6)
BRASS        = (150, 112,  48)
BRASS_BRIGHT = (214, 172,  84)
BRASS_DARK   = ( 84,  58,  16)
AMBER        = (226, 148,  30)
AMBER_DIM    = (146,  94,  16)
COPPER       = (184, 115,  51)
TAPE_PAPER   = (218, 196, 148)
TAPE_PAPER2  = (198, 176, 128)
HOLE_DARK    = ( 28,  15,   4)
LAMP_OFF     = ( 60,  22,  10)
LAMP_ON      = (255, 168,  40)
RIVET        = (180, 140,  60)
RED_NEEDLE   = (210,  65,  15)
CARD_PAPER   = (231, 214, 172)
CARD_PAPER2  = (214, 195, 150)
CARD_EDGE    = (120,  96,  60)
INK          = ( 62,  42,  24)
INK_FAINT    = (128, 104,  70)
SEAL_WAX     = (146,  32,  22)

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    """Scale a design-space (320x480) value to the actual resolution."""
    return max(1, int(v * SCALE))


class TelegraphState(State):
    """Steampunk punch-tape telegraph, portrait layout."""

    BASE_SPEED = 72.0  # px/s in design space

    def __init__(self, state_manager):
        super().__init__(state_manager)

        self.current_affairs = CurrentAffairs()
        self._message = ""

        # ── Geometry (scaled design space) ───────────────────────────────
        self.SLOT_W       = s(20)
        self.TAPE_H       = s(72)
        self.tape_y       = s(96)
        self.head_x       = SCREEN_WIDTH // 2
        self.SPROCKET_R   = s(2)
        self.DATA_R       = s(4)
        self.DATA_ROWS    = [s(16), s(26), s(36), s(46), s(56)]
        self.SPROCKET_TOP = s(8)
        self.SPROCKET_BOT = s(64)
        self.LEAD_SLOTS   = 6
        self.TRAIL_SLOTS  = 6

        # Telegram card
        self.card_rect = pygame.Rect(s(16), s(218), SCREEN_WIDTH - s(32), s(208))

        # ── Animation state ───────────────────────────────────────────────
        self.tape_x      = 0.0
        self.scroll_spd  = self.BASE_SPEED * SCALE
        self.slots       = []
        self.decoded     = []
        self._last_slot_idx = -1
        self.gear_angle  = 0.0
        self.spool_angle = 0.0
        self.clack_flash = 0.0
        self.gauge_a     = -55.0
        self.gauge_tgt   = 20.0
        self.steam       = []          # puffs: [x, y, r, alpha, drift]
        self.steam_timer = 0.0

        # ── Fonts ──────────────────────────────────────────────────────────
        pygame.font.init()
        self.font_title   = pygame.font.Font(None, s(30))
        self.font_sub     = pygame.font.Font(None, s(17))
        self.font_card_hd = pygame.font.Font(None, s(19))
        self.font_label   = pygame.font.Font(None, s(15))
        try:
            self.font_decoded = pygame.font.SysFont("monospace", s(17), bold=True)
        except Exception:
            self.font_decoded = pygame.font.Font(None, s(20))

        # ── Pre-rendered static layers ─────────────────────────────────────
        self._bg_surf    = self._build_background()
        self._frame_surf = self._build_frame_surface()
        self._grain_surf = self._build_grain_surface()
        self._card_surf  = self._build_card_surface()
        self._steam_area = pygame.Surface((s(90), s(80)), pygame.SRCALPHA)

        self._dispatch_no = random.randint(1000, 9999)
        self._chars_sent  = 0

        self._encode_message(self.current_affairs.get_current_message())

    # ══════════════════════════════════════════════════════════════════════
    # Construction helpers
    # ══════════════════════════════════════════════════════════════════════
    def _encode_message(self, message):
        self._message = message
        self.slots = []
        lead = self.LEAD_SLOTS + int(self.head_x / self.SLOT_W)
        for _ in range(lead):
            self.slots.append((' ', [0, 0, 0, 0, 0]))
        for ch in message:
            self.slots.append((ch, char_to_bits(ch)))
        for _ in range(self.TRAIL_SLOTS + int(self.head_x / self.SLOT_W) + 2):
            self.slots.append((' ', [0, 0, 0, 0, 0]))
        self.tape_x = 0.0
        self._last_slot_idx = -1
        self.decoded = []
        self.clack_flash = 0.0

    def _build_background(self):
        """Warm vertical gradient + wood streaks + vignette + scanlines."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            t = y / max(1, SCREEN_HEIGHT - 1)
            c = [int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)]
            pygame.draw.line(surf, c, (0, y), (SCREEN_WIDTH, y))
        # faint vertical wood streaks
        rng = random.Random(7)
        for _ in range(26):
            x = rng.randint(0, SCREEN_WIDTH - 1)
            shade = rng.randint(-8, 8)
            col = (max(0, 20 + shade), max(0, 12 + shade // 2), max(0, 6))
            pygame.draw.line(surf, col, (x, 0), (x, SCREEN_HEIGHT), 1)
        # scanlines (pre-rendered once — the old version rebuilt these per frame)
        for y in range(0, SCREEN_HEIGHT, 3):
            r, g, b = surf.get_at((0, y))[:3]
            pygame.draw.line(surf, (max(0, r - 6), max(0, g - 4), max(0, b - 3)),
                             (0, y), (SCREEN_WIDTH, y))
        return surf

    def _build_frame_surface(self):
        """Header plate, machine panels, rivets — all static brass work."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ty, th = self.tape_y, self.TAPE_H

        # ── Header plate ────────────────────────────────────────────────
        plate = pygame.Rect(s(10), s(8), SCREEN_WIDTH - s(20), s(54))
        pygame.draw.rect(surf, PANEL_DARK, plate, border_radius=s(6))
        pygame.draw.rect(surf, BRASS, plate, 2, border_radius=s(6))
        pygame.draw.rect(surf, BRASS_DARK, plate.inflate(-s(8), -s(8)), 1, border_radius=s(4))
        for rx, ry in [(plate.left + s(8), plate.top + s(8)),
                       (plate.right - s(8), plate.top + s(8)),
                       (plate.left + s(8), plate.bottom - s(8)),
                       (plate.right - s(8), plate.bottom - s(8))]:
            pygame.draw.circle(surf, RIVET, (rx, ry), s(3))
            pygame.draw.circle(surf, BRASS_DARK, (rx, ry), s(3), 1)

        # ── Machine panels above/below the tape ─────────────────────────
        for py in (ty - s(22), ty + th):
            pygame.draw.rect(surf, PANEL_DARK, (0, py, SCREEN_WIDTH, s(22)))
            pygame.draw.line(surf, BRASS, (0, py), (SCREEN_WIDTH, py), 2)
            pygame.draw.line(surf, BRASS_DARK, (0, py + s(22)), (SCREEN_WIDTH, py + s(22)), 2)
            for rx in range(s(12), SCREEN_WIDTH, s(30)):
                pygame.draw.circle(surf, RIVET, (rx, py + s(11)), s(3))
                pygame.draw.circle(surf, BRASS_DARK, (rx, py + s(11)), s(1)),
        return surf

    def _build_grain_surface(self):
        w, h = 64, self.TAPE_H
        surf = pygame.Surface((w, h))
        surf.fill(TAPE_PAPER)
        for _ in range(300):
            gx, gy = random.randint(0, w - 1), random.randint(0, h - 1)
            shade = random.randint(195, 230)
            surf.set_at((gx, gy), (shade, shade - 18, shade - 48))
        # edge shading baked in
        for d in range(1, 6):
            a = 90 - d * 15
            pygame.draw.line(surf, (170 - a // 3, 150 - a // 3, 110 - a // 3), (0, d), (w, d))
            pygame.draw.line(surf, (170 - a // 3, 150 - a // 3, 110 - a // 3), (0, h - d), (w, h - d))
        return surf

    def _build_card_surface(self):
        """Aged TELEGRAM card: deckled edges, header, rules, wax seal."""
        r = self.card_rect
        surf = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        rng = random.Random(3)

        # drop shadow
        pygame.draw.rect(surf, (0, 0, 0, 110), (s(5), s(6), r.w - s(6), r.h - s(6)),
                         border_radius=s(3))
        card = pygame.Rect(0, 0, r.w - s(6), r.h - s(7))
        pygame.draw.rect(surf, CARD_PAPER, card, border_radius=s(2))

        # paper mottling
        for _ in range(260):
            px = rng.randint(2, card.w - 3)
            py = rng.randint(2, card.h - 3)
            surf.set_at((px, py), CARD_PAPER2)
        # coffee-ring stain, upper right
        pygame.draw.circle(surf, (206, 184, 138), (card.w - s(34), s(38)), s(16), 2)

        # deckled (rough) edges
        for x in range(0, card.w, 3):
            if rng.random() < 0.5:
                surf.set_at((x, rng.randint(0, 1)), (0, 0, 0, 0))
            if rng.random() < 0.5:
                surf.set_at((x, card.h - 1 - rng.randint(0, 1)), (0, 0, 0, 0))
        pygame.draw.rect(surf, CARD_EDGE, card, 1, border_radius=s(2))

        # header
        hd = self.font_card_hd.render("— THE KEA TELEGRAPH CO. —", True, INK)
        surf.blit(hd, ((card.w - hd.get_width()) // 2, s(10)))
        sub = self.font_label.render("RECEIVED DISPATCH  ·  READ BY LAMPLIGHT", True, INK_FAINT)
        surf.blit(sub, ((card.w - sub.get_width()) // 2, s(28)))
        pygame.draw.line(surf, INK_FAINT, (s(14), s(44)), (card.w - s(14), s(44)), 1)
        pygame.draw.line(surf, INK_FAINT, (s(14), s(47)), (card.w - s(14), s(47)), 1)

        # faint writing guide lines
        line_h = self.font_decoded.get_linesize() + s(4)
        y = s(60) + line_h - s(2)
        while y < card.h - s(40):
            pygame.draw.line(surf, (204, 186, 144), (s(14), y), (card.w - s(14), y), 1)
            y += line_h

        # footer rule + wax seal
        pygame.draw.line(surf, INK_FAINT, (s(14), card.h - s(30)), (card.w - s(14), card.h - s(30)), 1)
        ft = self.font_label.render("DO NOT FOLD", True, INK_FAINT)
        surf.blit(ft, (s(16), card.h - s(24)))
        sx, sy_ = card.w - s(30), card.h - s(26)
        pygame.draw.circle(surf, SEAL_WAX, (sx, sy_), s(14))
        pygame.draw.circle(surf, (100, 20, 14), (sx, sy_), s(14), 2)
        pygame.draw.circle(surf, (196, 60, 40), (sx - s(4), sy_ - s(4)), s(3))
        kk = self.font_label.render("K", True, (228, 190, 160))
        surf.blit(kk, kk.get_rect(center=(sx, sy_)))
        return surf

    # ══════════════════════════════════════════════════════════════════════
    # Drawing helpers
    # ══════════════════════════════════════════════════════════════════════
    def _draw_gear(self, surface, cx, cy, radius, teeth, angle, color):
        inner_r = radius * 0.72
        pts = []
        n = teeth * 4
        for i in range(n):
            a = angle + (i / n) * math.tau
            r = radius if i % 4 in (1, 2) else inner_r
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        shadow = tuple(max(0, c - 60) for c in color)
        if len(pts) >= 3:
            pygame.draw.polygon(surface, color, pts)
            pygame.draw.polygon(surface, shadow, pts, 1)
        pygame.draw.circle(surface, shadow, (int(cx), int(cy)), max(2, int(radius * 0.22)))

    def _draw_spool(self, surface, cx, cy, radius, angle):
        color = (95, 65, 18)
        shadow = tuple(max(0, c - 50) for c in color)
        pygame.draw.circle(surface, color, (int(cx), int(cy)), int(radius))
        pygame.draw.circle(surface, shadow, (int(cx), int(cy)), int(radius), 2)
        hub_r = int(radius * 0.32)
        pygame.draw.circle(surface, shadow, (int(cx), int(cy)), hub_r)
        spoke = tuple(min(255, c + 40) for c in color)
        for k in range(6):
            a = angle + k * math.tau / 6
            pygame.draw.line(surface, spoke,
                             (int(cx + hub_r * math.cos(a)), int(cy + hub_r * math.sin(a))),
                             (int(cx + radius * 0.85 * math.cos(a)),
                              int(cy + radius * 0.85 * math.sin(a))), 2)

    def _draw_gauge(self, surface, cx, cy, radius):
        pygame.draw.circle(surface, BRASS_DARK, (int(cx), int(cy)), radius + s(3))
        pygame.draw.circle(surface, BRASS, (int(cx), int(cy)), radius + s(3), 2)
        pygame.draw.circle(surface, (22, 12, 4), (int(cx), int(cy)), radius)
        for i in range(11):
            a = math.radians(-210 + i * 24)
            r1, r2 = radius - s(4), radius - (s(8) if i % 5 == 0 else s(6))
            pygame.draw.line(surface, BRASS,
                             (int(cx + r1 * math.cos(a)), int(cy + r1 * math.sin(a))),
                             (int(cx + r2 * math.cos(a)), int(cy + r2 * math.sin(a))), 1)
        na = math.radians(self.gauge_a)
        pygame.draw.line(surface, RED_NEEDLE, (int(cx), int(cy)),
                         (int(cx + (radius - s(6)) * math.cos(na)),
                          int(cy + (radius - s(6)) * math.sin(na))), 2)
        pygame.draw.circle(surface, BRASS_BRIGHT, (int(cx), int(cy)), s(3))

    def _draw_reading_head(self, surface):
        ty, th, hx = self.tape_y, self.TAPE_H, self.head_x
        hw = s(18)
        if self.clack_flash > 0.05:
            glow = pygame.Surface((hw * 2 + s(30), th + s(30)), pygame.SRCALPHA)
            glow.fill((255, 170, 40, int(self.clack_flash * 70)))
            surface.blit(glow, (hx - hw - s(15), ty - s(15)))
        body = (hx - hw, ty - s(9), hw * 2, th + s(18))
        pygame.draw.rect(surface, BRASS_BRIGHT, body, border_radius=s(4))
        pygame.draw.rect(surface, BRASS_DARK, body, 2, border_radius=s(4))
        win = LAMP_ON if self.clack_flash > 0.05 else LAMP_OFF
        pygame.draw.rect(surface, win, (hx - s(4), ty + s(4), s(8), th - s(8)))
        pygame.draw.rect(surface, BRASS_DARK, (hx - s(4), ty + s(4), s(8), th - s(8)), 1)
        for gy in (ty - s(9), ty + th):
            pygame.draw.rect(surface, COPPER, (hx - hw - s(5), gy, hw * 2 + s(10), s(9)),
                             border_radius=s(2))

    def _draw_morse_key(self, surface, cx, cy):
        pygame.draw.rect(surface, BRASS_DARK, (int(cx - s(24)), int(cy + s(6)), s(48), s(8)),
                         border_radius=2)
        pygame.draw.rect(surface, BRASS, (int(cx - s(2)), int(cy - s(2)), s(4), s(10)))
        tilt = -s(3) if self.clack_flash > 0.1 else 0
        pts = [(cx - s(19), cy + tilt + 2), (cx + s(19), cy - tilt + 2),
               (cx + s(19), cy - tilt + s(5)), (cx - s(19), cy + tilt + s(5))]
        pygame.draw.polygon(surface, BRASS, [(int(x), int(y)) for x, y in pts])
        cpt = LAMP_ON if self.clack_flash > 0.1 else LAMP_OFF
        pygame.draw.circle(surface, cpt, (int(cx + s(17)), int(cy + 2 + tilt)), s(2))
        pygame.draw.ellipse(surface, COPPER, (int(cx - s(12)), int(cy - s(7) + tilt), s(10), s(7)))

    # ══════════════════════════════════════════════════════════════════════
    # State interface
    # ══════════════════════════════════════════════════════════════════════
    def update(self, dt):
        self.tape_x += self.scroll_spd * dt
        ratio = self.scroll_spd / (self.BASE_SPEED * SCALE)
        self.gear_angle += ratio * dt * 1.4
        self.spool_angle += ratio * dt * 0.7

        self.gauge_a += (self.gauge_tgt - self.gauge_a) * min(1.0, dt * 1.2)
        if abs(self.gauge_a - self.gauge_tgt) < 2.0:
            self.gauge_tgt = random.uniform(-50.0, 28.0)

        # steam puffs from behind the header plate
        self.steam_timer -= dt
        if self.steam_timer <= 0:
            self.steam_timer = random.uniform(0.5, 1.1)
            self.steam.append([s(66), s(76), s(3), 150, random.uniform(-4, 4) * SCALE])
        for p in self.steam:
            p[1] -= s(14) * dt          # rise
            p[0] += p[4] * dt           # drift
            p[2] += s(5) * dt           # grow
            p[3] -= 65 * dt             # fade
        self.steam = [p for p in self.steam if p[3] > 4]

        # decode the slot under the head
        raw_idx = int((self.tape_x + self.head_x) / self.SLOT_W)
        slot_idx = max(0, min(raw_idx, len(self.slots) - 1))
        if slot_idx != self._last_slot_idx and slot_idx < len(self.slots):
            self._last_slot_idx = slot_idx
            ch, bits = self.slots[slot_idx]
            if any(bits):
                self.clack_flash = 1.0
                if ch.isprintable():
                    self.decoded.append(ch)
                    self._chars_sent += 1
                    if len(self.decoded) > 300:
                        self.decoded.pop(0)
        if self.clack_flash > 0:
            self.clack_flash = max(0.0, self.clack_flash - dt * 9.0)

        # loop tape / next message
        if self.tape_x >= len(self.slots) * self.SLOT_W:
            self.current_affairs.update(dt)
            self._dispatch_no += 1
            self._encode_message(self.current_affairs.get_current_message())
        else:
            self.current_affairs.update(dt)

    # ──────────────────────────────────────────────────────────────────────
    def draw(self, surface):
        ty, th = self.tape_y, self.TAPE_H
        surface.blit(self._bg_surf, (0, 0))

        # steam (behind the header plate)
        self._steam_area.fill((0, 0, 0, 0))
        for p in self.steam:
            pygame.draw.circle(self._steam_area, (225, 218, 205, int(p[3])),
                               (int(p[0]), int(p[1])), int(p[2]))
        surface.blit(self._steam_area, (s(10), s(0)))

        # tape band
        gw = self._grain_surf.get_width()
        for gx in range(0, SCREEN_WIDTH, gw):
            surface.blit(self._grain_surf, (gx, ty))

        # punch holes
        first_slot = max(0, int(self.tape_x / self.SLOT_W) - 1)
        last_slot = min(len(self.slots), first_slot + int(SCREEN_WIDTH / self.SLOT_W) + 4)
        for i in range(first_slot, last_slot):
            ch, bits = self.slots[i]
            sx = int(i * self.SLOT_W - self.tape_x) + self.SLOT_W // 2
            for sy_ in (ty + self.SPROCKET_TOP, ty + self.SPROCKET_BOT):
                pygame.draw.circle(surface, HOLE_DARK, (sx, sy_), self.SPROCKET_R)
            for row, bit in enumerate(bits):
                if bit:
                    hy = ty + self.DATA_ROWS[row]
                    pygame.draw.circle(surface, HOLE_DARK, (sx, hy), self.DATA_R)
                    pygame.draw.circle(surface, (15, 6, 1), (sx, hy), max(1, self.DATA_R - 2))

        # spools in front of the band edges — the tape feeds out of them
        spool_cy = ty + th // 2
        self._draw_spool(surface, s(4), spool_cy, s(30), -self.spool_angle)
        self._draw_spool(surface, SCREEN_WIDTH - s(4), spool_cy, s(30), self.spool_angle)

        self._draw_reading_head(surface)
        surface.blit(self._frame_surf, (0, 0))

        # gears on the machine panels
        pm_top, pm_bot = ty - s(11), ty + th + s(11)
        for gx, gy, gr, gt, gd in [
                (s(26), pm_top, s(13), 9, 1.0), (s(52), pm_top, s(8), 7, -1.67),
                (SCREEN_WIDTH - s(26), pm_top, s(13), 9, -1.0),
                (SCREEN_WIDTH - s(52), pm_top, s(8), 7, 1.67),
                (s(26), pm_bot, s(13), 9, -1.0),
                (SCREEN_WIDTH - s(26), pm_bot, s(13), 9, 1.0)]:
            col = BRASS if gr >= s(13) else BRASS_DARK
            self._draw_gear(surface, gx, gy, gr, gt, self.gear_angle * gd, col)

        # header plate text
        title = self.font_title.render("TELEGRAPH DISPATCH", True, AMBER)
        surface.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, s(16)))
        now = datetime.datetime.now().strftime("%H:%M  ·  %a %d %b")
        meta = self.font_sub.render(f"DISPATCH #{self._dispatch_no:04d}  ·  {now}", True, AMBER_DIM)
        surface.blit(meta, ((SCREEN_WIDTH - meta.get_width()) // 2, s(40)))

        # receiving lamp on the top machine panel
        lamp = LAMP_ON if self.clack_flash > 0.05 else LAMP_OFF
        pygame.draw.circle(surface, lamp, (self.head_x, ty - s(11)), s(5))
        pygame.draw.circle(surface, BRASS_DARK, (self.head_x, ty - s(11)), s(5), 1)

        # ── telegram card + decoded text ────────────────────────────────
        surface.blit(self._card_surf, self.card_rect.topleft)
        self._draw_decoded(surface)

        # bottom hardware row
        self._draw_morse_key(surface, s(44), SCREEN_HEIGHT - s(28))
        self._draw_gauge(surface, SCREEN_WIDTH - s(44), SCREEN_HEIGHT - s(30), s(20))
        stats = self.font_label.render(
            f"TX {self._chars_sent:05d}  ·  {int(self.scroll_spd / SCALE)} BD", True, BRASS_DARK)
        surface.blit(stats, ((SCREEN_WIDTH - stats.get_width()) // 2, SCREEN_HEIGHT - s(32)))

    def _draw_decoded(self, surface):
        if not self.decoded:
            return
        r = self.card_rect
        text_x = r.x + s(14)
        text_w = r.w - s(34)
        line_h = self.font_decoded.get_linesize() + s(4)
        max_lines = (r.h - s(100)) // line_h

        lines, current = [], ""
        for ch in "".join(self.decoded):
            if self.font_decoded.size(current + ch)[0] < text_w:
                current += ch
            else:
                lines.append(current)
                current = ch
        if current:
            lines.append(current)
        lines = lines[-max_lines:]

        y = r.y + s(58)
        last_w = 0
        for line in lines:
            ink = self.font_decoded.render(line, True, INK)
            surface.blit(ink, (text_x, y))
            last_w = ink.get_width()
            y += line_h
        # blinking ink cursor
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            cy = y - line_h
            pygame.draw.rect(surface, INK,
                             (text_x + last_w + s(3), cy + s(2), s(7), line_h - s(8)))

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        time_str = f"T-{mins:02d}:{secs:02d}"
        c = (150, 20, 20) if mode == 'work' else (20, 120, 20)
        overlay = self.font_sub.render(time_str, True, c)
        bg_rect = overlay.get_rect(midtop=(surface.get_width() // 2, s(66)))
        bg_rect.inflate_ip(s(10), s(6))
        box = pygame.Surface((bg_rect.width, bg_rect.height))
        box.fill((230, 220, 200))
        pygame.draw.rect(box, (100, 90, 80), box.get_rect(), 1)
        surface.blit(box, bg_rect.topleft)
        surface.blit(overlay, overlay.get_rect(center=bg_rect.center))
