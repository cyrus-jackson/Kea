"""
telegraph_state.py
------------------
Steampunk Punch-Tape Telegraph  —  Ambient Screen for Raspberry Pi
Displays current-affairs headlines encoded as authentic ITA2 Baudot
punch-tape, scrolling left with a brass reading-head in the centre.
Decoded characters appear letter-by-letter below the tape.

Drop this file into your  states/  folder and wire it up the same way
as AmbientState.  It expects the same helpers to exist:

    from config import SCREEN_WIDTH, SCREEN_HEIGHT
    from states.base_state import State
    from current_affairs import CurrentAffairs

(GlowText is not required — we draw our own styled text here.)
"""

import pygame
import random
import math
import datetime

# ── project imports (same pattern as ambient_state.py) ──────────────────────
from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from current_affairs import CurrentAffairs


# ── ITA2 / Baudot-Murray 5-bit codes ────────────────────────────────────────
#  Authentic codes from the ITA-2 standard.
#  Each value is [row0, row1, row2, row3, row4]  (top → bottom on tape)
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
    """Return 5-bit ITA2 hole pattern for a character."""
    key = ch.upper()
    return ITA2.get(key, [random.randint(0, 1) for _ in range(5)])


# ── Colour palette ───────────────────────────────────────────────────────────
BG           = ( 14,   8,   2)   # near-black warm brown
PANEL_DARK   = ( 28,  16,   4)   # dark panel sections
BRASS        = (139, 106,  48)   # standard brass
BRASS_BRIGHT = (200, 160,  70)   # highlight brass
BRASS_DARK   = ( 80,  55,  15)   # shadow brass
AMBER        = (220, 140,  20)   # warm amber text
AMBER_DIM    = (140,  90,  12)   # dimmer amber
COPPER       = (184, 115,  51)   # copper accent
TAPE_PAPER   = (218, 196, 148)   # aged cream paper
TAPE_PAPER2  = (200, 178, 130)   # slightly darker cream
HOLE_DARK    = ( 30,  16,   4)   # punched hole interior
HEAD_WIN_OFF = ( 10,  35,  10)   # reading window — idle
HEAD_WIN_ON  = ( 20, 160,  50)   # reading window — active
RIVET        = (180, 140,  60)
RED_NEEDLE   = (210,  65,  15)


class TelegraphState(State):
    """
    Steampunk punch-tape telegraph ambient display.

    Architecture mirrors AmbientState:
        __init__  → build all surfaces & encode first message
        update    → advance scroll, gear angles, weather-equivalent
        draw      → render tape, gears, decoded ticker, gauges
    """

    # ── Tape geometry constants ──────────────────────────────────────────────
    TAPE_H        = 88    # px — height of the paper tape band
    SLOT_W        = 20    # px — width per character column on tape
    LEAD_SLOTS    = 6     # blank lead-in columns before message
    TRAIL_SLOTS   = 6     # blank trail-out columns after message
    SPROCKET_R    = 3     # px radius of sprocket (feed) holes
    DATA_R        = 5     # px radius of data holes
    # Row y-offsets *within the tape surface* (0 = tape top)
    SPROCKET_TOP  = 10
    DATA_ROWS     = [22, 33, 44, 55, 66]   # 5 data rows
    SPROCKET_BOT  = 78

    # ── Speed & animation ────────────────────────────────────────────────────
    BASE_SPEED    = 72.0  # px / second  (tune to taste)

    def __init__(self, state_manager):
        super().__init__(state_manager)

        # ── Current-affairs feed ─────────────────────────────────────────────
        self.current_affairs = CurrentAffairs()
        self._message = ""

        # ── Tape scroll state ────────────────────────────────────────────────
        self.tape_x      = 0.0   # how many px we have scrolled so far
        self.scroll_spd  = self.BASE_SPEED

        # ── Encoded tape: list of (char, [5 bits]) ───────────────────────────
        self.slots: list[tuple[str, list[int]]] = []

        # ── Decoded ticker (bottom half) ─────────────────────────────────────
        self.decoded: list[str] = []     # characters successfully "read"
        self._last_slot_idx = -1         # which slot index was last decoded

        # ── Animation angles ─────────────────────────────────────────────────
        self.gear_angle   = 0.0          # main corner-gear rotation (radians)
        self.spool_angle  = 0.0          # spool rotation (radians)

        # ── Reading-head flash (green pulse when a hole passes) ──────────────
        self.clack_flash  = 0.0          # 0.0 → 1.0

        # ── Gauge (purely decorative) ────────────────────────────────────────
        self.gauge_a      = -55.0        # current needle angle (degrees)
        self.gauge_tgt    = 20.0         # target needle angle

        # ── Fonts ────────────────────────────────────────────────────────────
        pygame.font.init()
        self.font_title   = pygame.font.Font(None, 28)
        self.font_sub     = pygame.font.Font(None, 18)
        self.font_decoded = pygame.font.Font(None, 34)
        self.font_label   = pygame.font.Font(None, 16)
        try:
            self.font_mono = pygame.font.SysFont("monospace", 18)
        except Exception:
            self.font_mono = pygame.font.Font(None, 18)

        # ── Derived positions ─────────────────────────────────────────────────
        self.tape_y   = SCREEN_HEIGHT // 2 - self.TAPE_H // 2
        self.head_x   = SCREEN_WIDTH  // 2   # reading head fixed at centre

        # ── Pre-build static frame overlay (brass bars, rivets) ──────────────
        self._frame_surf = self._build_frame_surface()

        # ── Tape paper grain: reuse a small tiled surface ────────────────────
        self._grain_surf  = self._build_grain_surface()

        # ── Dispatch counter ─────────────────────────────────────────────────
        self._dispatch_no  = random.randint(1000, 9999)
        self._chars_sent   = 0

        # ── Kick off first message ────────────────────────────────────────────
        self._encode_message(self.current_affairs.get_current_message())

    # ═════════════════════════════════════════════════════════════════════════
    # Construction helpers
    # ═════════════════════════════════════════════════════════════════════════

    def _encode_message(self, message: str):
        """Convert a text message into a list of punch-tape slots."""
        self._message = message
        self.slots = []

        # Lead-in blanks (all sprockets, no data holes → looks like unprinted tape)
        for _ in range(self.LEAD_SLOTS + int(self.head_x / self.SLOT_W)):
            self.slots.append((' ', [0, 0, 0, 0, 0]))

        for ch in message:
            self.slots.append((ch, char_to_bits(ch)))

        # Trail-out blanks
        for _ in range(self.TRAIL_SLOTS + int(self.head_x / self.SLOT_W) + 2):
            self.slots.append((' ', [0, 0, 0, 0, 0]))

        self.tape_x       = 0.0
        self._last_slot_idx = -1
        self.decoded      = []
        self.clack_flash  = 0.0

    def _build_frame_surface(self) -> pygame.Surface:
        """Pre-render the brass frame bars, rivets, and edge lines (static)."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ty, th = self.tape_y, self.TAPE_H

        # ── Top panel (above tape) ────────────────────────────────────────────
        pygame.draw.rect(surf, PANEL_DARK, (0, ty - 24, SCREEN_WIDTH, 24))
        pygame.draw.line(surf, BRASS,       (0, ty - 24), (SCREEN_WIDTH, ty - 24), 2)
        pygame.draw.line(surf, BRASS_DARK,  (0, ty),      (SCREEN_WIDTH, ty),      2)

        # ── Bottom panel (below tape) ─────────────────────────────────────────
        pygame.draw.rect(surf, PANEL_DARK, (0, ty + th, SCREEN_WIDTH, 24))
        pygame.draw.line(surf, BRASS,       (0, ty + th),      (SCREEN_WIDTH, ty + th),      2)
        pygame.draw.line(surf, BRASS_DARK,  (0, ty + th + 24), (SCREEN_WIDTH, ty + th + 24), 2)

        # ── Rivets ────────────────────────────────────────────────────────────
        for panel_y, row_y in [(-12, ty - 12), (12, ty + th + 12)]:
            for rx in range(14, SCREEN_WIDTH, 26):
                ry = ty + panel_y if panel_y < 0 else row_y
                pygame.draw.circle(surf, RIVET,      (rx, ry), 4)
                pygame.draw.circle(surf, BRASS_DARK, (rx, ry), 2)

        # ── Vertical side bars ────────────────────────────────────────────────
        pygame.draw.rect(surf, PANEL_DARK,  (0, 0,               18, SCREEN_HEIGHT))
        pygame.draw.rect(surf, PANEL_DARK,  (SCREEN_WIDTH - 18, 0, 18, SCREEN_HEIGHT))
        pygame.draw.line(surf, BRASS,        (18, 0),               (18, SCREEN_HEIGHT), 1)
        pygame.draw.line(surf, BRASS, (SCREEN_WIDTH - 18, 0), (SCREEN_WIDTH - 18, SCREEN_HEIGHT), 1)

        return surf

    def _build_grain_surface(self) -> pygame.Surface:
        """Build a small tileable paper-grain texture for the tape."""
        w, h = 64, self.TAPE_H
        surf = pygame.Surface((w, h))
        surf.fill(TAPE_PAPER)
        for _ in range(300):
            gx = random.randint(0, w - 1)
            gy = random.randint(0, h - 1)
            shade = random.randint(195, 230)
            surf.set_at((gx, gy), (shade, shade - 18, shade - 48))
        return surf

    # ═════════════════════════════════════════════════════════════════════════
    # Drawing helpers
    # ═════════════════════════════════════════════════════════════════════════

    def _draw_gear(self, surface, cx: float, cy: float,
                   radius: float, teeth: int, angle: float,
                   color: tuple, inner_ratio: float = 0.72):
        """Draw a single gear with spokes and hub."""
        inner_r = radius * inner_ratio
        pts = []
        n = teeth * 4
        for i in range(n):
            a = angle + (i / n) * math.tau
            r = radius if i % 4 in (1, 2) else inner_r
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))

        if len(pts) >= 3:
            pygame.draw.polygon(surface, color, pts)
            shadow = (max(0, color[0] - 60), max(0, color[1] - 60), max(0, color[2] - 60))
            pygame.draw.polygon(surface, shadow, pts, 1)

        # Hub disc
        hub_r = max(3, int(radius * 0.22))
        pygame.draw.circle(surface, shadow, (int(cx), int(cy)), hub_r)

        # Spokes
        spoke_color = (
            min(255, color[0] + 30),
            min(255, color[1] + 20),
            max(0,   color[2] - 10),
        )
        for k in range(4):
            a = angle + k * math.pi / 2
            x1 = cx + inner_r * 0.28 * math.cos(a)
            y1 = cy + inner_r * 0.28 * math.sin(a)
            x2 = cx + inner_r * 0.82 * math.cos(a)
            y2 = cy + inner_r * 0.82 * math.sin(a)
            pygame.draw.line(surface, spoke_color,
                             (int(x1), int(y1)), (int(x2), int(y2)), 1)

    def _draw_spool(self, surface, cx: float, cy: float,
                    radius: float, angle: float, color: tuple):
        """Draw a tape spool with flanges and spokes."""
        # Outer flange
        pygame.draw.circle(surface, color, (int(cx), int(cy)), int(radius))
        shadow = (max(0, color[0] - 50), max(0, color[1] - 50), max(0, color[2] - 50))
        pygame.draw.circle(surface, shadow, (int(cx), int(cy)), int(radius), 2)

        # Hub
        hub_r = int(radius * 0.32)
        pygame.draw.circle(surface, shadow, (int(cx), int(cy)), hub_r)

        # Spokes
        spoke = (min(255, color[0] + 40), min(255, color[1] + 30), min(255, color[2] + 5))
        for k in range(6):
            a = angle + k * math.tau / 6
            x1 = cx + hub_r * math.cos(a)
            y1 = cy + hub_r * math.sin(a)
            x2 = cx + radius * 0.85 * math.cos(a)
            y2 = cy + radius * 0.85 * math.sin(a)
            pygame.draw.line(surface, spoke,
                             (int(x1), int(y1)), (int(x2), int(y2)), 2)

    def _draw_gauge(self, surface, cx: float, cy: float, radius: int):
        """Small decorative brass steam-pressure gauge."""
        # Outer bezel
        pygame.draw.circle(surface, BRASS_DARK, (int(cx), int(cy)), radius + 4)
        pygame.draw.circle(surface, BRASS,       (int(cx), int(cy)), radius + 4, 3)
        # Face
        pygame.draw.circle(surface, (22, 12, 4), (int(cx), int(cy)), radius)

        # Scale arc ticks  (-210° → +30°,  i.e. 240° sweep)
        for i in range(11):
            a = math.radians(-210 + i * 24)
            r1 = radius - 5
            r2 = radius - 10 if i % 5 == 0 else radius - 8
            x1, y1 = cx + r1 * math.cos(a), cy + r1 * math.sin(a)
            x2, y2 = cx + r2 * math.cos(a), cy + r2 * math.sin(a)
            pygame.draw.line(surface, BRASS,
                             (int(x1), int(y1)), (int(x2), int(y2)), 1)

        # Danger zone ticks (red zone: 0 → +30°)
        for i in range(5):
            a = math.radians(i * 6)
            r1 = radius - 5
            pygame.draw.line(surface, (180, 40, 10),
                             (int(cx + r1 * math.cos(a)), int(cy + r1 * math.sin(a))),
                             (int(cx + (radius - 3) * math.cos(a)),
                              int(cy + (radius - 3) * math.sin(a))), 1)

        # Needle
        na = math.radians(self.gauge_a)
        nx = cx + (radius - 8) * math.cos(na)
        ny = cy + (radius - 8) * math.sin(na)
        pygame.draw.line(surface, RED_NEEDLE,
                         (int(cx), int(cy)), (int(nx), int(ny)), 2)
        pygame.draw.circle(surface, BRASS_BRIGHT, (int(cx), int(cy)), 4)

        # Label
        lbl = self.font_label.render("PSI", True, BRASS)
        surface.blit(lbl, (int(cx) - lbl.get_width() // 2, int(cy) + radius // 2 + 2))

    def _draw_reading_head(self, surface):
        """Draw the central brass reading-head assembly."""
        ty, th = self.tape_y, self.TAPE_H
        hx = self.head_x
        hw = 22   # head half-width

        # Glowing halo when flash active
        if self.clack_flash > 0.05:
            alpha = int(self.clack_flash * 80)
            glow = pygame.Surface((hw * 2 + 40, th + 40), pygame.SRCALPHA)
            glow.fill((30, 200, 60, alpha))
            surface.blit(glow, (hx - hw - 20, ty - 20))

        # Body plate
        body_rect = (hx - hw, ty - 10, hw * 2, th + 20)
        pygame.draw.rect(surface, BRASS_BRIGHT, body_rect, border_radius=5)
        pygame.draw.rect(surface, BRASS_DARK,   body_rect, 2, border_radius=5)

        # Bolt heads on body
        for by in (ty - 4, ty + th + 4):
            pygame.draw.circle(surface, BRASS_DARK,  (hx - hw + 6, by), 3)
            pygame.draw.circle(surface, BRASS_DARK,  (hx + hw - 6, by), 3)

        # Reading window slot (coloured LED-style)
        win_col = HEAD_WIN_ON if self.clack_flash > 0.05 else HEAD_WIN_OFF
        pygame.draw.rect(surface, win_col,
                         (hx - 5, ty + 4, 10, th - 8))
        # Window frame
        pygame.draw.rect(surface, BRASS_DARK,
                         (hx - 5, ty + 4, 10, th - 8), 1)

        # Top / bottom guide brackets
        for gy in (ty - 10, ty + th):
            pygame.draw.rect(surface, COPPER,
                             (hx - hw - 6, gy, hw * 2 + 12, 10),
                             border_radius=2)
            pygame.draw.rect(surface, BRASS_DARK,
                             (hx - hw - 6, gy, hw * 2 + 12, 10), 1,
                             border_radius=2)

    # ═════════════════════════════════════════════════════════════════════════
    # State interface
    # ═════════════════════════════════════════════════════════════════════════

    def update(self, dt: float):
        # ── Scroll tape ───────────────────────────────────────────────────────
        self.tape_x += self.scroll_spd * dt

        # ── Gear & spool rotation ─────────────────────────────────────────────
        ratio = self.scroll_spd / self.BASE_SPEED
        self.gear_angle  += ratio * dt * 1.4
        self.spool_angle += ratio * dt * 0.7

        # ── Gauge needle wander ───────────────────────────────────────────────
        self.gauge_a += (self.gauge_tgt - self.gauge_a) * min(1.0, dt * 1.2)
        if abs(self.gauge_a - self.gauge_tgt) < 2.0:
            self.gauge_tgt = random.uniform(-50.0, 28.0)

        # ── Decode character under head ───────────────────────────────────────
        #  The slot currently centred under head_x
        raw_idx = int((self.tape_x + self.head_x) / self.SLOT_W)
        slot_idx = max(0, min(raw_idx, len(self.slots) - 1))

        if slot_idx != self._last_slot_idx and slot_idx < len(self.slots):
            self._last_slot_idx = slot_idx
            ch, bits = self.slots[slot_idx]
            if any(bits):          # non-blank column
                self.clack_flash = 1.0
                if ch.strip():     # printable character
                    self.decoded.append(ch)
                    self._chars_sent += 1
                    if len(self.decoded) > 55:
                        self.decoded.pop(0)

        # ── Decay clack flash ─────────────────────────────────────────────────
        if self.clack_flash > 0:
            self.clack_flash = max(0.0, self.clack_flash - dt * 9.0)

        # ── Loop tape / fetch new message ─────────────────────────────────────
        tape_len_px = len(self.slots) * self.SLOT_W
        if self.tape_x >= tape_len_px:
            changed = self.current_affairs.update(dt) if hasattr(self, 'current_affairs') else False
            msg = self.current_affairs.get_current_message()
            self._dispatch_no += 1
            self._encode_message(msg)
        else:
            if hasattr(self, 'current_affairs'):
                self.current_affairs.update(dt)

    # ─────────────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface):
        ty, th = self.tape_y, self.TAPE_H

        # ── 1. Background ─────────────────────────────────────────────────────
        surface.fill(BG)

        # Subtle horizontal scan-lines texture
        scan_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for sy in range(0, SCREEN_HEIGHT, 3):
            scan_surf.fill((0, 0, 0, 18), rect=(0, sy, SCREEN_WIDTH, 1))
        surface.blit(scan_surf, (0, 0))

        # ── 2. Tape spools ────────────────────────────────────────────────────
        spool_cy = ty + th // 2
        spool_col = (95, 65, 18)

        # left spool (feed)
        self._draw_spool(surface,  52, spool_cy, 36, -self.spool_angle, spool_col)
        # right spool (take-up)
        self._draw_spool(surface, SCREEN_WIDTH - 52, spool_cy,
                         36,  self.spool_angle, spool_col)

        # Tape ribbon connecting spool to tape band (two thin lines)
        for side_x, sign in [(52, 1), (SCREEN_WIDTH - 52, -1)]:
            pygame.draw.line(surface, TAPE_PAPER2,
                             (side_x + sign * 18, spool_cy - 4),
                             (side_x + sign * 18, spool_cy + 4), 1)

        # ── 3. Paper tape band ────────────────────────────────────────────────
        # Tiled grain
        gw = self._grain_surf.get_width()
        for gx in range(0, SCREEN_WIDTH, gw):
            surface.blit(self._grain_surf, (gx, ty))

        # Tape edge highlight lines
        pygame.draw.line(surface, TAPE_PAPER2,         (0, ty),       (SCREEN_WIDTH, ty),      1)
        pygame.draw.line(surface, (160, 140, 100), (0, ty + th),   (SCREEN_WIDTH, ty + th),  1)

        # ── 4. Punch holes ────────────────────────────────────────────────────
        first_slot = max(0, int(self.tape_x / self.SLOT_W) - 1)
        last_slot  = min(len(self.slots), first_slot + int(SCREEN_WIDTH / self.SLOT_W) + 4)

        for i in range(first_slot, last_slot):
            ch, bits = self.slots[i]
            sx = int(i * self.SLOT_W - self.tape_x) + self.SLOT_W // 2  # centre-x on screen

            # ── Sprocket holes (every slot, top & bottom) ─────────────────────
            for sy in (ty + self.SPROCKET_TOP, ty + self.SPROCKET_BOT):
                pygame.draw.circle(surface, HOLE_DARK, (sx, sy), self.SPROCKET_R)

            # ── Data holes ────────────────────────────────────────────────────
            for row, bit in enumerate(bits):
                if bit:
                    hy = ty + self.DATA_ROWS[row]
                    pygame.draw.circle(surface, HOLE_DARK, (sx, hy), self.DATA_R)
                    # Inner deep shadow for depth
                    pygame.draw.circle(surface, (15, 6, 1), (sx, hy), self.DATA_R - 2)

        # ── 5. Tape edge shadows ──────────────────────────────────────────────
        for depth in range(1, 7):
            alpha = 35 - depth * 5
            s = pygame.Surface((SCREEN_WIDTH, 1), pygame.SRCALPHA)
            s.fill((0, 0, 0, alpha))
            surface.blit(s, (0, ty + depth))
            surface.blit(s, (0, ty + th - depth))

        # ── 6. Reading head ───────────────────────────────────────────────────
        self._draw_reading_head(surface)

        # ── 7. Static brass frame ─────────────────────────────────────────────
        surface.blit(self._frame_surf, (0, 0))

        # ── 8. Corner gears ───────────────────────────────────────────────────
        panel_mid_top = ty - 12     # vertical centre of top panel
        panel_mid_bot = ty + th + 12

        gear_positions = [
            (32,               panel_mid_top, 16, 9,  1.0),   # TL large
            (62,               panel_mid_top, 10, 7, -1.67),  # TL small
            (SCREEN_WIDTH-32,  panel_mid_top, 16, 9, -1.0),   # TR large
            (SCREEN_WIDTH-62,  panel_mid_top, 10, 7,  1.67),  # TR small
            (32,               panel_mid_bot, 16, 9, -1.0),   # BL large
            (62,               panel_mid_bot, 10, 7,  1.67),  # BL small
            (SCREEN_WIDTH-32,  panel_mid_bot, 16, 9,  1.0),   # BR large
            (SCREEN_WIDTH-62,  panel_mid_bot, 10, 7, -1.67),  # BR small
        ]
        for gx, gy, gr, gt, gd in gear_positions:
            col = BRASS if gr == 16 else BRASS_DARK
            self._draw_gear(surface, gx, gy, gr, gt,
                            self.gear_angle * gd, col)

        # ── 9. Header text ────────────────────────────────────────────────────
        title_str = "✦  AETHERIC  TELEGRAPH  DISPATCH  ✦"
        title_surf = self.font_title.render(title_str, True, AMBER)
        surface.blit(title_surf, (SCREEN_WIDTH // 2 - title_surf.get_width() // 2, 6))

        now_str = datetime.datetime.now().strftime("TRANSMISSION  ·  %H:%M:%S  ·  %a %d %b")
        ts_surf = self.font_sub.render(now_str, True, AMBER_DIM)
        surface.blit(ts_surf, (SCREEN_WIDTH // 2 - ts_surf.get_width() // 2, 32))

        # Dispatch number (top-left corner)
        dn_surf = self.font_sub.render(f"DISPATCH  #{self._dispatch_no:04d}", True, BRASS)
        surface.blit(dn_surf, (26, 8))

        # Characters sent counter (top-left)
        cs_surf = self.font_label.render(f"CHARS TX: {self._chars_sent:06d}", True, BRASS_DARK)
        surface.blit(cs_surf, (26, 26))

        # ── 10. RECEIVING indicator LED (top-right) ──────────────────────────
        led_col = (20, 230, 60) if self.clack_flash > 0.05 else (10, 80, 25)
        pygame.draw.circle(surface, led_col, (SCREEN_WIDTH - 30, 14), 6)
        pygame.draw.circle(surface, (5, 35, 10), (SCREEN_WIDTH - 30, 14), 6, 1)
        recv_lbl = self.font_label.render("RECEIVING", True, led_col)
        surface.blit(recv_lbl, (SCREEN_WIDTH - 30 - recv_lbl.get_width() - 8, 10))

        # Transmission speed
        spd_lbl = self.font_label.render(f"{int(self.scroll_spd)} BD", True, BRASS_DARK)
        surface.blit(spd_lbl, (SCREEN_WIDTH - spd_lbl.get_width() - 24, 26))

        # ── 11. Decoded text ticker ───────────────────────────────────────────
        decoded_y = ty + th + 34

        decoded_label = self.font_sub.render("◄  DECODED  TRANSMISSION  ►", True, BRASS_DARK)
        surface.blit(decoded_label,
                     (SCREEN_WIDTH // 2 - decoded_label.get_width() // 2, decoded_y - 18))

        # Build decoded string — last N chars to fit screen
        decoded_str = "".join(self.decoded)
        # Trim to screen width
        while True:
            ds = self.font_decoded.render(decoded_str, True, AMBER)
            if ds.get_width() <= SCREEN_WIDTH - 40 or len(decoded_str) == 0:
                break
            decoded_str = decoded_str[1:]

        ds = self.font_decoded.render(decoded_str, True, AMBER)
        surface.blit(ds, (SCREEN_WIDTH // 2 - ds.get_width() // 2, decoded_y))

        # Blinking cursor after last char
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            cur_x = SCREEN_WIDTH // 2 - ds.get_width() // 2 + ds.get_width() + 3
            pygame.draw.rect(surface, AMBER, (cur_x, decoded_y + 4, 10, 22))

        # ── 12. Decorative gauge (bottom-right) ──────────────────────────────
        self._draw_gauge(surface, SCREEN_WIDTH - 60, SCREEN_HEIGHT - 50, 36)

        # ── 13. Morse key decoration (bottom-left) ────────────────────────────
        self._draw_morse_key(surface, 55, SCREEN_HEIGHT - 48)

        # ── 14. Bottom status bar ─────────────────────────────────────────────
        msg_preview = self._message[:50] + ("…" if len(self._message) > 50 else "")
        bar_surf = self.font_label.render(f"SOURCE:  {msg_preview}", True, BRASS_DARK)
        surface.blit(bar_surf, (26, SCREEN_HEIGHT - 14))

    # ─────────────────────────────────────────────────────────────────────────

    def _draw_morse_key(self, surface, cx: float, cy: float):
        """Draw a tiny decorative telegraph Morse key."""
        col = BRASS_DARK
        bcol = BRASS

        # Base plate
        pygame.draw.rect(surface, col, (int(cx - 28), int(cy + 8), 56, 10), border_radius=2)
        # Pivot post
        pygame.draw.rect(surface, bcol, (int(cx - 2), int(cy - 2), 4, 12))
        # Lever arm  (tilts when flash active)
        tilt = -4 if self.clack_flash > 0.1 else 0
        pts = [
            (cx - 22, cy + tilt + 2),
            (cx + 22, cy - tilt + 2),
            (cx + 22, cy - tilt + 6),
            (cx - 22, cy + tilt + 6),
        ]
        pygame.draw.polygon(surface, bcol, [(int(x), int(y)) for x, y in pts])
        # Contact point
        cpt_col = (20, 200, 50) if self.clack_flash > 0.1 else (10, 60, 20)
        pygame.draw.circle(surface, cpt_col, (int(cx + 20), int(cy + 2 + tilt)), 3)
        # Knob
        pygame.draw.ellipse(surface, COPPER, (int(cx - 14), int(cy - 8 + tilt), 12, 8))