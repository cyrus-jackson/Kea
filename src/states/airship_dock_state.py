import pygame
import random
import math

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State

# ══════════════════════════════════════════════════════════════════════════════
# PALETTE
# ══════════════════════════════════════════════════════════════════════════════
SKY_TOP      = (  6,   3,  18)
SKY_BOT      = ( 22,  10,  42)
DOCK_FAR     = ( 18,  10,  36)
DOCK_MID     = ( 30,  16,  54)
DOCK_NEAR    = ( 44,  26,  70)
BRASS        = (184, 115,  51)
BRASS_LIT    = (232, 200, 122)
BRASS_DARK   = ( 90,  55,  18)
NEON_PINK    = (255,  50, 170)
NEON_CYAN    = ( 50, 210, 255)
NEON_AMBER   = (255, 165,  30)
NEON_PURPLE  = (160,  50, 255)
NEON_GREEN   = ( 50, 255, 140)
WHITE        = (255, 255, 255)

NEON_COLORS  = [NEON_PINK, NEON_CYAN, NEON_AMBER, NEON_PURPLE, NEON_GREEN]

# Dock Y positions as fractions of screen height (back → front)
DOCK_Y_FRACS = [0.52, 0.62, 0.72]


class AirshipDockState(State):
    """
    Neon Airship Dock — steampunk × cyberpunk ambient screen.
    Victorian brass airships drift into a neon-lit docking bay
    at three parallax depths. Searchlights sweep the night sky,
    gas lanterns flicker, and neon signs buzz on the gantries.

    Target: 480×320 @ 30 fps on Raspberry Pi.
    """

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.w = SCREEN_WIDTH
        self.h = SCREEN_HEIGHT

        # ── Fonts (needed before spawning cached text surfaces) ───────────
        self.ticker_font = pygame.font.Font(None, 14)
        self.sign_font = pygame.font.Font(None, 11)

        # ── Pre-rendered static surfaces ───────────────────────────────────
        self.sky_surf    = self._build_sky()
        self.dock_surfs  = [self._build_dock_layer(i) for i in range(3)]

        # ── Dynamic objects ────────────────────────────────────────────────
        self.airships     = self._spawn_airships()
        self.lanterns     = self._spawn_lanterns()
        self.neon_signs   = self._spawn_neon_signs()
        self.searchlights = self._spawn_searchlights()
        self.sparks        = []          # occasional welding sparks on dock

        # ── Global time & scroll ───────────────────────────────────────────
        self.t          = 0.0
        self.fog_scroll = 0.0
        self.spark_timer = random.uniform(2.0, 5.0)

        # ── Ticker ─────────────────────────────────────────────────────────
        self.ticker_msg = (
            "MERIDIAN AIR DOCK  //  GATE 7 OPEN  //  WIND: 12 KN NW  //"
            "  BAROMETER: FALLING  //  ALL ZEPPELINS REPORT TO BAY 3  //"
            "  AETHER PRESSURE: NOMINAL  //  NEXT DEPARTURE: 04:22  //"
        )
        self.ticker_surf = self.ticker_font.render(self.ticker_msg, True, NEON_AMBER)
        self.ticker_w = self.ticker_surf.get_width()
        self.ticker_x = float(self.w)

        # ── Cached / reused surfaces ────────────────────────────────────────
        self.beam_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.fog_surf  = self._build_fog_strip()
        self.glow_surf = pygame.Surface((22, 22), pygame.SRCALPHA)

    # ══════════════════════════════════════════════════════════════════════════
    # BUILD STATIC SURFACES
    # ══════════════════════════════════════════════════════════════════════════

    def _build_sky(self):
        surf = pygame.Surface((self.w, self.h))

        # Vertical gradient: dark top → deep purple base
        for y in range(self.h):
            t = y / self.h
            r = int(SKY_TOP[0] + (SKY_BOT[0] - SKY_TOP[0]) * t)
            g = int(SKY_TOP[1] + (SKY_BOT[1] - SKY_TOP[1]) * t)
            b = int(SKY_TOP[2] + (SKY_BOT[2] - SKY_TOP[2]) * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (self.w, y))

        # Stars — small handful of 2px ones, rest single pixels
        for _ in range(110):
            sx  = random.randint(0, self.w - 1)
            sy  = random.randint(0, int(self.h * 0.65))
            br  = random.randint(110, 240)
            sz  = 2 if random.random() < 0.12 else 1
            pygame.draw.rect(surf, (br, br, min(255, br + 20)), (sx, sy, sz, sz))

        # Nebula wisps (soft translucent ellipses on temp SRCALPHA surface)
        neb = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        nebula_palette = [
            (90, 20, 130, 22), (20, 55, 130, 18),
            (130, 20, 80, 18), (60, 10, 100, 15),
        ]
        for _ in range(5):
            nc  = random.choice(nebula_palette)
            nw  = random.randint(70, 160)
            nh  = random.randint(18, 48)
            nx  = random.randint(-20, self.w + 20)
            ny  = random.randint(0, int(self.h * 0.55))
            pygame.draw.ellipse(neb, nc, (nx - nw//2, ny - nh//2, nw, nh))
        surf.blit(neb, (0, 0))

        # Gas giant / ringed planet
        gx = random.randint(55, self.w - 55)
        gy = random.randint(18, 72)
        gr = random.randint(18, 32)
        planet_col = random.choice([
            (160, 100, 60), (70, 130, 200), (150, 90, 200), (80, 170, 130)
        ])
        # Dark inner shadow half
        shadow_col = tuple(max(0, c - 50) for c in planet_col)
        pygame.draw.ellipse(surf, planet_col, (gx-gr, gy-gr, gr*2, gr*2))
        pygame.draw.ellipse(surf, shadow_col, (gx, gy-gr, gr, gr*2))
        # Ring (ellipse outline wider than planet)
        ring_col = tuple(max(0, c - 70) for c in planet_col)
        pygame.draw.ellipse(surf, ring_col,
                            (gx - gr*2 + 2, gy - 5, gr*4 - 4, 10), 1)

        return surf

    def _build_dock_layer(self, idx):
        """
        Three dock layers back→front. Each grows darker, taller, and
        more detailed as idx increases.
        """
        surf  = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        col   = [DOCK_FAR, DOCK_MID, DOCK_NEAR][idx]
        dok_y = int(self.h * DOCK_Y_FRACS[idx])

        # ── Catwalk floor ──────────────────────────────────────────────────
        floor_h = 4 + idx * 4
        pygame.draw.rect(surf, col, (0, dok_y, self.w, floor_h))
        # Slightly lighter top edge
        hi = tuple(min(255, c + 18) for c in col)
        pygame.draw.line(surf, hi, (0, dok_y), (self.w, dok_y))

        # ── Vertical support columns ───────────────────────────────────────
        n_cols  = 5 + idx * 3
        col_w   = 2 + idx * 2
        spacing = self.w / (n_cols - 1)
        for i in range(n_cols):
            cx      = int(i * spacing)
            top_var = random.randint(8, 28 + idx * 10)
            pygame.draw.rect(
                surf, col, (cx - col_w//2, dok_y - top_var, col_w, top_var))

        # ── Horizontal gantry cross-beams ──────────────────────────────────
        n_beams = 1 + idx
        for j in range(n_beams):
            by = dok_y - 6 - j * 12
            pygame.draw.line(surf, col, (0, by), (self.w, by),
                             1 + idx)
            # Bolt dots along beam
            for bx in range(10, self.w - 10, 20):
                pygame.draw.rect(surf, hi, (bx, by - 1, 2, 2))

        # ── Mooring posts (taller, capped with brass) ──────────────────────
        n_posts   = 3 + idx
        post_w    = 2 + idx
        post_h    = 10 + idx * 6
        for i in range(n_posts):
            px = int((i + 0.5) * self.w / n_posts)
            pygame.draw.rect(
                surf, col, (px - post_w//2, dok_y - post_h, post_w, post_h))
            cap_col = BRASS_DARK if idx < 2 else BRASS
            pygame.draw.rect(
                surf, cap_col, (px - post_w - 1, dok_y - post_h - 2,
                                post_w * 2 + 2, 3))

        # ── Pipe bundles (only mid + near layers) ─────────────────────────
        if idx >= 1:
            py_base = dok_y + floor_h + 2
            for p in range(idx + 1):
                py = py_base + p * 3
                pygame.draw.line(surf, col, (0, py), (self.w, py),
                                 1)

        # ── Foreground railing (nearest layer only) ────────────────────────
        if idx == 2:
            ry = dok_y + 2
            pygame.draw.line(surf, BRASS_DARK, (0, ry), (self.w, ry))
            for rx in range(0, self.w, 7):
                pygame.draw.line(surf, BRASS_DARK,
                                 (rx, ry), (rx, dok_y + floor_h))

        return surf

    def _build_fog_strip(self):
        """Scrolling fog band at dock level — pre-rendered, double-wide."""
        surf = pygame.Surface((self.w * 2, 44), pygame.SRCALPHA)
        for x in range(0, self.w * 2, 28):
            w = random.randint(40, 110)
            h = random.randint(12, 34)
            a = random.randint(25, 65)
            pygame.draw.ellipse(surf, (80, 40, 120, a), (x, 6, w, h))
        return surf

    # ══════════════════════════════════════════════════════════════════════════
    # SPAWN DYNAMIC OBJECTS
    # ══════════════════════════════════════════════════════════════════════════

    def _spawn_airships(self):
        """
        Five ships across three depth layers.
        Scale, speed, and y-range all grow toward the foreground.
        """
        ships = []
        # (layer, count, scale, speed_min, speed_max, y_lo_frac, y_hi_frac)
        configs = [
            (0, 2, 0.32,  6, 12, 0.12, 0.40),
            (1, 2, 0.60, 12, 20, 0.20, 0.48),
            (2, 1, 1.00, 18, 28, 0.28, 0.56),
        ]
        for layer, count, scale, spd_lo, spd_hi, y_lo, y_hi in configs:
            for _ in range(count):
                d = random.choice([-1, 1])
                ships.append({
                    'x':          random.uniform(0, self.w),
                    'y':          random.uniform(
                                      self.h * y_lo,
                                      self.h * y_hi),
                    'speed':      random.uniform(spd_lo, spd_hi) * d,
                    'layer':      layer,
                    'scale':      scale,
                    'bob_phase':  random.uniform(0, math.tau),
                    'bob_speed':  random.uniform(0.35, 0.85),
                    'bob_amp':    random.uniform(1.5, 3.5) * scale,
                    'neon_col':   random.choice(NEON_COLORS),
                    'neon_phase': random.uniform(0, math.tau),
                    'env_col':    random.choice([
                                      (42, 24, 68), (32, 18, 56), (52, 30, 74)
                                  ]),
                    'fin_col':    random.choice([
                                      BRASS_DARK, (58, 32, 78), (28, 48, 80)
                                  ]),
                })
        return ships

    def _spawn_lanterns(self):
        lanterns = []
        dok_y = int(self.h * DOCK_Y_FRACS[2])
        for i in range(14):
            lanterns.append({
                'x':       int((i + 0.5) * self.w / 14),
                'y':       dok_y - random.randint(8, 16),
                'phase':   random.uniform(0, math.tau),
                'speed':   random.uniform(1.5, 3.5),
                'base_br': random.uniform(0.55, 0.95),
            })
        return lanterns

    def _spawn_neon_signs(self):
        candidates = [
            "MERIDIAN DOCK", "GATE 7", "NO MOORING",
            "COAL & AETHER", "BAY 3 OPEN", "LIFT  ▲",
            "CUSTOMS", "QUARANTINE", "DANGER: VOLTAGE",
        ]
        signs = []
        used_x = []
        dok_y  = int(self.h * DOCK_Y_FRACS[1])
        for text in random.sample(candidates, 5):
            col = random.choice(NEON_COLORS)
            for _ in range(40):           # find non-overlapping x
                sx = random.randint(8, self.w - 85)
                if all(abs(sx - ux) > 68 for ux in used_x):
                    used_x.append(sx)
                    break
            base_surf = self.sign_font.render(text, True, col)
            signs.append({
                'text':    text,
                'x':       sx,
                'y':       random.randint(dok_y - 20, dok_y + 4),
                'col':     col,
                'phase':   random.uniform(0, math.tau),
                'flicker': random.uniform(2.2, 8.5),
                'surf':    base_surf,
            })
        return signs

    def _spawn_searchlights(self):
        return [
            {
                'base_x': self.w * frac,
                'base_y': int(self.h * DOCK_Y_FRACS[2]) - 2,
                'angle':  random.uniform(-0.4, 0.4),
                'speed':  random.uniform(0.18, 0.38) * random.choice([-1, 1]),
                'sweep':  random.uniform(0.55, 1.05),
                'length': random.randint(140, 210),
                'col':    random.choice(NEON_COLORS),
            }
            for frac in (0.14, 0.86)
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # UPDATE
    # ══════════════════════════════════════════════════════════════════════════

    def update(self, dt):
        self.t += dt

        # Fog parallax scroll
        self.fog_scroll = (self.fog_scroll + dt * 10.0) % self.w

        # Ticker scroll
        self.ticker_x -= 55.0 * dt
        if self.ticker_x < -self.ticker_w:
            self.ticker_x = float(self.w)

        # Airships drift + bob
        for ship in self.airships:
            ship['x']          += ship['speed'] * dt
            ship['bob_phase']  += ship['bob_speed'] * dt
            ship['neon_phase'] += 3.2 * dt
            # Wrap
            if ship['x'] > self.w + 130:
                ship['x'] = -130.0
            elif ship['x'] < -130:
                ship['x'] = self.w + 130.0

        # Searchlights sweep
        for sl in self.searchlights:
            sl['angle'] += sl['speed'] * dt
            if abs(sl['angle']) > sl['sweep']:
                sl['speed'] *= -1

        # Occasional welding sparks
        self.spark_timer -= dt
        if self.spark_timer <= 0:
            self.spark_timer = random.uniform(2.5, 6.0)
            dok_y = int(SCREEN_HEIGHT * DOCK_Y_FRACS[2])
            dok_y = int(self.h * DOCK_Y_FRACS[2])
            sx    = random.randint(20, self.w - 20)
            for _ in range(random.randint(4, 10)):
                self.sparks.append({
                    'x':  float(sx),
                    'y':  float(dok_y - random.randint(2, 8)),
                    'vx': random.uniform(-30, 30),
                    'vy': random.uniform(-60, -10),
                    'life': 0.0,
                    'max_life': random.uniform(0.25, 0.6),
                    'col': random.choice([BRASS_LIT, NEON_AMBER, (255, 220, 80)]),
                })

        # Update sparks
        live = []
        for sp in self.sparks:
            sp['x']   += sp['vx'] * dt
            sp['y']   += sp['vy'] * dt
            sp['vy']  += 120 * dt          # gravity
            sp['life'] += dt
            if sp['life'] < sp['max_life']:
                live.append(sp)
        self.sparks = live

    # ══════════════════════════════════════════════════════════════════════════
    # DRAW HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _draw_airship(self, surface, x, y, scale, neon_col, env_col,
                      fin_col, neon_phase, facing_right):
        """
        Draw one airship centred on (x, y).

        Structure (back→front draw order):
          fins → envelope → rope rigging → gondola → propeller
        """
        ix = int(x)
        iy = int(y)

        ew = max(4, int(62 * scale))        # envelope width
        eh = max(3, int(21 * scale))        # envelope height
        ex = ix - ew // 2
        ey = iy - eh // 2

        # ── Tail fins ─────────────────────────────────────────────────────
        fd  = int(9 * scale)                # fin depth
        ftx = ex if facing_right else ex + ew
        fsd = 1 if facing_right else -1     # which direction fins extend

        def draw_fin(tip_y):
            pts = [(ftx, ey + eh // 2), (ftx - fd * fsd, tip_y),
                   (ftx - (fd // 2) * fsd, ey + eh // 2)]
            if len(set(pts)) >= 3:
                pygame.draw.polygon(surface, fin_col, pts)

        draw_fin(ey - int(6 * scale))
        draw_fin(ey + eh + int(6 * scale))

        # ── Envelope ──────────────────────────────────────────────────────
        pygame.draw.ellipse(surface, env_col, (ex, ey, ew, eh))
        # Highlight stripe
        hi = tuple(min(255, c + 35) for c in env_col)
        pygame.draw.ellipse(surface, hi,
                            (ex + ew//4, ey + 2,
                             max(2, ew//2), max(2, eh//4)))
        # Brass ribbing bands (vertical lines on envelope)
        if scale > 0.45:
            n_ribs = max(2, int(4 * scale))
            for i in range(1, n_ribs):
                rx = ex + int(i * ew / n_ribs)
                # Clip to ellipse bounds roughly
                if ex < rx < ex + ew:
                    t_  = (rx - ex) / ew         # 0..1
                    h_  = max(1, int(eh * math.sin(math.pi * t_) * 0.9))
                    cy  = ey + eh // 2
                    pygame.draw.line(surface, BRASS_DARK,
                                     (rx, cy - h_//2), (rx, cy + h_//2), 1)
        # Outline
        pygame.draw.ellipse(surface, BRASS_DARK, (ex, ey, ew, eh),
                            max(1, int(scale)))

        # ── Suspension ropes ──────────────────────────────────────────────
        gw  = max(3, int(26 * scale))
        gh  = max(2, int(11 * scale))
        gx  = ix - gw // 2
        gy  = iy + eh // 2 + max(2, int(4 * scale))
        pygame.draw.line(surface, BRASS_DARK,
                         (ex + ew//3,     ey + eh), (gx,      gy))
        pygame.draw.line(surface, BRASS_DARK,
                         (ex + 2*ew//3,   ey + eh), (gx + gw, gy))

        # ── Gondola body ──────────────────────────────────────────────────
        r_px = max(1, int(2 * scale))
        pygame.draw.rect(surface, BRASS_DARK, (gx, gy, gw, gh), 0, r_px)

        # Neon trim on gondola (drawn on small SRCALPHA surface)
        if gw > 2 and gh > 2:
            na    = int(145 + 90 * math.sin(neon_phase))
            ns    = pygame.Surface((gw, gh), pygame.SRCALPHA)
            pygame.draw.rect(ns, neon_col + (na,), (0, 0, gw, gh), 1, r_px)
            surface.blit(ns, (gx, gy))

        # Gondola portholes
        if scale > 0.5:
            n_win = max(1, int(3 * scale))
            for i in range(n_win):
                wx = gx + int((i + 0.5) * gw / n_win) - 1
                wy = gy + gh // 2 - 1
                wc = tuple(min(255, c + 80) for c in neon_col)
                pygame.draw.rect(surface, wc, (wx, wy, 2, 2))

        # ── Propeller ─────────────────────────────────────────────────────
        if scale > 0.38:
            px = (ex + ew + int(2 * scale)) if facing_right \
                 else (ex        - int(2 * scale))
            py = ey + eh // 2
            pr = max(2, int(5 * scale))
            pygame.draw.circle(surface, BRASS, (px, py), pr, 1)
            rot = self.t * 4.0 * (1 if facing_right else -1)
            for angle in (rot, rot + math.pi/2):
                bx = px + int(math.cos(angle) * pr)
                by = py + int(math.sin(angle) * pr)
                bx2= px - int(math.cos(angle) * pr)
                by2= py - int(math.sin(angle) * pr)
                pygame.draw.line(surface, BRASS, (bx, by), (bx2, by2), 1)

    def _draw_searchlights(self, surface):
        self.beam_surf.fill((0, 0, 0, 0))
        for sl in self.searchlights:
            bx  = int(sl['base_x'])
            by  = int(sl['base_y'])
            # Angle: 0 = right, so subtract pi/2 to point upward + sweep
            ang = -math.pi / 2 + sl['angle']
            L   = sl['length']
            hw  = 0.055               # half-angle of beam cone (radians)

            tip   = (int(bx + math.cos(ang)       * L),
                     int(by + math.sin(ang)       * L))
            left  = (int(bx + math.cos(ang - hw)  * L),
                     int(by + math.sin(ang - hw)  * L))
            right = (int(bx + math.cos(ang + hw)  * L),
                     int(by + math.sin(ang + hw)  * L))

            r, g, b = sl['col']
            # Wide soft cone
            pygame.draw.polygon(
                self.beam_surf, (r, g, b, 22),
                [(bx, by), left, tip, right])
            # Bright centre ray
            pygame.draw.line(
                self.beam_surf, (r, g, b, 55), (bx, by), tip, 1)
            # Source glow
            pygame.draw.circle(self.beam_surf, (r, g, b, 90), (bx, by), 5)

        surface.blit(self.beam_surf, (0, 0))

    def _draw_lanterns(self, surface):
        for lan in self.lanterns:
            br = lan['base_br'] + 0.28 * math.sin(
                self.t * lan['speed'] + lan['phase'])
            br = max(0.0, min(1.0, br))
            r  = int(255 * br)
            g  = int(175 * br)
            b  = int(35  * br)
            # Warm glow halo
            self.glow_surf.fill((0, 0, 0, 0))
            pygame.draw.circle(
                self.glow_surf, (r, g, b, int(55 * br)), (11, 11), 11)
            surface.blit(self.glow_surf, (lan['x'] - 11, lan['y'] - 11))
            # Bright core pixel
            pygame.draw.rect(surface, (r, g, b),
                             (lan['x'] - 1, lan['y'] - 1, 2, 2))

    def _draw_neon_signs(self, surface):
        for sign in self.neon_signs:
            flicker = math.sin(self.t * sign['flicker'] + sign['phase'])
            alpha   = max(55, min(255, int(175 + 65 * flicker)))
            txt = sign['surf']
            txt.set_alpha(alpha)
            tw, th  = txt.get_size()
            # Dim box outline
            box = pygame.Surface((tw + 6, th + 4), pygame.SRCALPHA)
            pygame.draw.rect(
                box, sign['col'] + (max(18, alpha // 5),),
                (0, 0, tw + 6, th + 4), 1, 2)
            surface.blit(box, (sign['x'] - 3, sign['y'] - 2))
            surface.blit(txt, (sign['x'],     sign['y']))

    def _draw_sparks(self, surface):
        for sp in self.sparks:
            prog  = sp['life'] / sp['max_life']
            alpha = int(255 * (1.0 - prog))
            r, g, b = sp['col']
            # Fade out
            r = int(r * (1 - prog * 0.5))
            g = int(g * (1 - prog * 0.5))
            b = int(b * (1 - prog * 0.5))
            pygame.draw.rect(surface, (r, g, b),
                             (int(sp['x']), int(sp['y']), 1, 1))

    # ══════════════════════════════════════════════════════════════════════════
    # DRAW  (main entry point)
    # ══════════════════════════════════════════════════════════════════════════

    def draw(self, surface):
        # 1. Sky + planet
        surface.blit(self.sky_surf, (0, 0))

        # 2. Searchlight beams (behind all architecture, atmospheric)
        self._draw_searchlights(surface)

        # 3. Back→front: dock layer then ships on that layer
        for idx in range(3):
            surface.blit(self.dock_surfs[idx], (0, 0))

            for ship in self.airships:
                if ship['layer'] != idx:
                    continue
                bob_y = ship['y'] + ship['bob_amp'] * math.sin(
                    ship['bob_phase'])
                self._draw_airship(
                    surface,
                    ship['x'], bob_y,
                    ship['scale'],
                    ship['neon_col'],
                    ship['env_col'],
                    ship['fin_col'],
                    ship['neon_phase'],
                    facing_right=(ship['speed'] > 0),
                )

        # 4. Gas lanterns on foreground catwalk
        self._draw_lanterns(surface)

        # 5. Neon signs on gantries
        self._draw_neon_signs(surface)

        # 6. Sparks (welding / electrical arcs on dock)
        self._draw_sparks(surface)

        # 7. Fog drifting along dock level
        fog_y = int(self.h * DOCK_Y_FRACS[2]) - 10
        fx    = -int(self.fog_scroll)
        surface.blit(self.fog_surf, (fx,                 fog_y))
        surface.blit(self.fog_surf, (fx + self.w,  fog_y))

        # 8. Bottom ticker bar
        bar_y = self.h - 16
        pygame.draw.rect(surface, (8, 3, 22),
                 (0, bar_y, self.w, 16))
        pygame.draw.line(surface, NEON_PINK,
                 (0, bar_y), (self.w, bar_y), 1)
        txt = self.ticker_surf
        tx  = int(self.ticker_x)
        surface.blit(txt, (tx, bar_y + 2))
        surface.blit(txt, (tx + txt.get_width() + 20, bar_y + 2))
