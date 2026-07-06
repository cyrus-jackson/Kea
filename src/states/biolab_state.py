"""
biolab_state.py
---------------
BIO-VAT LAB — biopunk specimen wing.

Four glass vats glow in a dark lab, each holding a procedurally
generated organism: a pulsing lobed body with swaying tentacles and
eyes that blink. Every couple of minutes the batch is "recultured" and
new mutations appear — no two organisms are ever alike. An EKG monitor
traces a heartbeat tied to the specimens' pulse, and the System
Protocol dispatch scrolls through the specimen log.

Vat glass, pedestals and panels are pre-rendered; per-frame work is
the organisms (a handful of circles and lines each), bubbles and the
EKG polyline.
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
LAB_BG      = ( 10,  14,  12)
PANEL       = ( 24,  32,  28)
PANEL_EDGE  = ( 52,  70,  60)
HAZARD_Y    = (212, 180,  40)
HAZARD_K    = ( 26,  24,  16)
TEXT_PALE   = (196, 220, 200)
TEXT_DIM    = (110, 140, 120)
MONITOR_BG  = (  8,  18,  10)
EKG_GREEN   = (110, 255, 120)
GLASS_EDGE  = (120, 170, 150)
FLUIDS      = [(60, 220, 90), (150, 90, 235), (60, 190, 220), (220, 120, 170)]


class BiolabState(State):
    """Biopunk vat lab with procedural mutating specimens."""

    RECULTURE_INTERVAL = 100.0     # seconds between new mutations

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.current_affairs = CurrentAffairs()

        self.font_title = pygame.font.Font(None, s(26))
        self.font_label = pygame.font.Font(None, s(15))
        self.font_tick  = pygame.font.Font(None, s(17))

        # vat layout: 2 x 2 grid
        self.vats = []
        vw, vh = s(136), s(120)
        x0 = (SCREEN_WIDTH - vw * 2 - s(12)) // 2
        y0 = s(66)
        for row in range(2):
            for col in range(2):
                rect = pygame.Rect(x0 + col * (vw + s(12)),
                                   y0 + row * (vh + s(14)), vw, vh)
                self.vats.append({"rect": rect, "specimen": None,
                                  "fluid": None, "bubbles": [], "id": row * 2 + col})

        self.monitor_rect = pygame.Rect(s(12), y0 + 2 * vh + s(26),
                                        SCREEN_WIDTH - s(24), s(58))
        self.tick_slot = pygame.Rect(s(12), SCREEN_HEIGHT - s(30),
                                     SCREEN_WIDTH - s(24), s(20))

        self.time_alive = 0.0
        self.batch = 1
        self.reculture_timer = 0.0
        self._reculture()

        # EKG trace: one value per column of the monitor
        self.ekg_w = self.monitor_rect.w - s(12)
        self.ekg = [0.0] * self.ekg_w
        self.ekg_pos = 0
        self.ekg_time = 0.0

        # ticker
        self.tick_text = self.current_affairs.get_current_message()
        self._tick_surf = self.font_tick.render(self.tick_text, True, HAZARD_Y)
        self.tick_scroll = 0.0
        self.tick_hold = 2.0

        self._frame_surf = self._build_frame()

    # ══════════════════════════════════════════════════════════════════════
    # Specimen generation — every batch is a new mutation
    # ══════════════════════════════════════════════════════════════════════
    def _make_specimen(self, fluid):
        bright = lerp_color(fluid, (255, 255, 255), 0.35)
        dark = lerp_color(fluid, (0, 0, 0), 0.45)
        return {
            "body_r": random.uniform(10, 16) * SCALE,
            "lobes": [(random.uniform(0, math.tau),          # angle
                       random.uniform(0.4, 0.95),            # dist (x body_r)
                       random.uniform(0.35, 0.7))            # radius (x body_r)
                      for _ in range(random.randint(4, 7))],
            "tentacles": [{
                "angle": math.pi / 2 + random.uniform(-1.2, 1.2),
                "len": random.uniform(14, 26) * SCALE,
                "phase": random.uniform(0, math.tau),
                "speed": random.uniform(1.2, 2.4),
                "amp": random.uniform(2.0, 5.0) * SCALE,
            } for _ in range(random.randint(2, 4))],
            "eyes": [{
                "angle": random.uniform(-1.2, 1.2) - math.pi / 2,
                "dist": random.uniform(0.2, 0.6),
                "r": random.uniform(2.2, 4.0) * SCALE,
                "blink": random.uniform(0, math.tau),
            } for _ in range(random.randint(1, 3))],
            "pulse": random.uniform(0.8, 1.5),
            "bob": random.uniform(0, math.tau),
            "bright": bright,
            "dark": dark,
        }

    def _reculture(self):
        fluids = random.sample(FLUIDS, len(FLUIDS))
        for i, vat in enumerate(self.vats):
            vat["fluid"] = fluids[i % len(fluids)]
            vat["specimen"] = self._make_specimen(vat["fluid"])
            r = vat["rect"]
            vat["bubbles"] = [[random.uniform(r.x + 8, r.right - 8),
                               random.uniform(r.y + 20, r.bottom - 6),
                               random.uniform(8, 18) * SCALE,
                               random.randint(1, s(2))]
                              for _ in range(4)]

    # ══════════════════════════════════════════════════════════════════════
    # Pre-rendered chrome
    # ══════════════════════════════════════════════════════════════════════
    def _hazard_strip(self, surf, rect):
        step = s(12)
        prev = surf.get_clip()
        surf.set_clip(rect)
        for x in range(rect.x - step * 2, rect.right + step, step):
            pygame.draw.polygon(surf, HAZARD_Y,
                                [(x, rect.bottom), (x + step // 2, rect.bottom),
                                 (x + step // 2 + rect.h, rect.y), (x + rect.h, rect.y)])
        surf.set_clip(prev)

    def _build_frame(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(LAB_BG)
        rng = random.Random(8)
        for _ in range(240):                    # grimy floor/wall speckle
            x, y = rng.randint(0, SCREEN_WIDTH - 1), rng.randint(0, SCREEN_HEIGHT - 1)
            surf.set_at((x, y), (16, 22, 18))

        # header: hazard stripes + title plate
        strip = pygame.Rect(s(8), s(8), SCREEN_WIDTH - s(16), s(48))
        pygame.draw.rect(surf, HAZARD_K, strip, border_radius=s(6))
        self._hazard_strip(surf, pygame.Rect(strip.x, strip.y, strip.w, s(6)))
        self._hazard_strip(surf, pygame.Rect(strip.x, strip.bottom - s(6), strip.w, s(6)))
        title = self.font_title.render("BIO-VAT LAB", True, TEXT_PALE)
        surf.blit(title, (strip.centerx - title.get_width() // 2, strip.y + s(10)))
        sub = self.font_label.render("SPECIMEN WING  ·  AUTHORIZED PERSONNEL", True, TEXT_DIM)
        surf.blit(sub, (strip.centerx - sub.get_width() // 2, strip.y + s(30)))
        # biohazard trefoil
        bx, by = strip.x + s(22), strip.centery
        for k in range(3):
            a = -math.pi / 2 + k * math.tau / 3
            pygame.draw.circle(surf, HAZARD_Y,
                               (int(bx + math.cos(a) * s(5)), int(by + math.sin(a) * s(5))),
                               s(5), 2)
        pygame.draw.circle(surf, HAZARD_K, (bx, by), s(3))
        pygame.draw.circle(surf, HAZARD_Y, (bx, by), s(2), 1)

        # vat glass + pedestals + labels
        for vat in self.vats:
            r = vat["rect"]
            # pedestal with pipes
            ped = pygame.Rect(r.x - s(4), r.bottom, r.w + s(8), s(10))
            pygame.draw.rect(surf, PANEL, ped, border_radius=s(3))
            pygame.draw.rect(surf, PANEL_EDGE, ped, 1, border_radius=s(3))
            pygame.draw.line(surf, PANEL_EDGE, (r.centerx, ped.bottom),
                             (r.centerx, ped.bottom + s(4)), s(3))
            # glass
            pygame.draw.rect(surf, GLASS_EDGE, r, 2, border_radius=s(10))
            pygame.draw.line(surf, (200, 235, 220),
                             (r.x + s(8), r.y + s(6)), (r.x + s(8), r.bottom - s(10)), 1)
            # cap
            cap = pygame.Rect(r.x + s(10), r.y - s(6), r.w - s(20), s(8))
            pygame.draw.rect(surf, PANEL, cap, border_radius=s(3))
            pygame.draw.rect(surf, PANEL_EDGE, cap, 1, border_radius=s(3))
            # label plate (on the pedestal so the fluid never covers it)
            lbl = self.font_label.render(f"SPX-{vat['id'] + 7:02d}", True, TEXT_PALE)
            surf.blit(lbl, (r.x + s(4), ped.y - s(1)))

        # monitor housing
        m = self.monitor_rect
        pygame.draw.rect(surf, PANEL, m.inflate(s(8), s(8)), border_radius=s(6))
        pygame.draw.rect(surf, PANEL_EDGE, m.inflate(s(8), s(8)), 1, border_radius=s(6))
        pygame.draw.rect(surf, MONITOR_BG, m, border_radius=s(3))
        lbl = self.font_label.render("VITALS", True, TEXT_DIM)
        surf.blit(lbl, (m.x + s(5), m.y + s(3)))

        # ticker slot
        pygame.draw.rect(surf, PANEL, self.tick_slot.inflate(s(6), s(6)), border_radius=s(4))
        pygame.draw.rect(surf, HAZARD_K, self.tick_slot, border_radius=s(3))
        lbl = self.font_label.render("SPECIMEN LOG", True, TEXT_DIM)
        surf.blit(lbl, (self.tick_slot.x + s(2), self.tick_slot.y - s(16)))
        return surf

    # ══════════════════════════════════════════════════════════════════════
    # Update
    # ══════════════════════════════════════════════════════════════════════
    def update(self, dt):
        self.time_alive += dt

        self.reculture_timer += dt
        if self.reculture_timer >= self.RECULTURE_INTERVAL:
            self.reculture_timer = 0.0
            self.batch += 1
            self._reculture()

        # bubbles rise
        for vat in self.vats:
            r = vat["rect"]
            for b in vat["bubbles"]:
                b[1] -= b[2] * dt
                b[0] += math.sin(self.time_alive * 2 + b[2]) * 3 * dt
                if b[1] < r.y + s(14):
                    b[0] = random.uniform(r.x + 8, r.right - 8)
                    b[1] = r.bottom - s(8)

        # EKG: advance the write head, one heartbeat every ~1.1s
        self.ekg_time += dt
        cols = max(1, int(dt * 90))
        for _ in range(cols):
            t = (self.ekg_time * 0.9) % 1.0
            v = 0.0
            if 0.10 < t < 0.16:
                v = -0.25
            elif 0.16 <= t < 0.22:
                v = 1.0 - abs(t - 0.19) / 0.03
            elif 0.30 < t < 0.42:
                v = 0.22 * math.sin((t - 0.30) / 0.12 * math.pi)
            v += random.uniform(-0.04, 0.04)
            self.ekg[self.ekg_pos] = v
            self.ekg_pos = (self.ekg_pos + 1) % self.ekg_w

        # ticker
        if self.current_affairs.update(dt):
            self.tick_text = self.current_affairs.get_current_message()
            self._tick_surf = self.font_tick.render(self.tick_text, True, HAZARD_Y)
            self.tick_scroll = 0.0
            self.tick_hold = 2.0
        if self._tick_surf.get_width() > self.tick_slot.w - s(8):
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
        surface.blit(self._frame_surf, (0, 0))
        t = self.time_alive

        for vat in self.vats:
            self._draw_vat(surface, vat, t)

        # EKG monitor
        m = self.monitor_rect
        base_y = m.centery + s(6)
        amp = m.h * 0.36
        pts = []
        for i in range(self.ekg_w):
            gap = (i - self.ekg_pos) % self.ekg_w
            if gap < s(10):            # erase gap in front of the write head
                if len(pts) > 1:
                    pygame.draw.lines(surface, EKG_GREEN, False, pts, 1)
                pts = []
                continue
            pts.append((m.x + s(6) + i, base_y - self.ekg[i] * amp))
        if len(pts) > 1:
            pygame.draw.lines(surface, EKG_GREEN, False, pts, 1)
        bpm = self.font_label.render(f"BATCH {self.batch:02d}  ·  54 BPM", True, TEXT_DIM)
        surface.blit(bpm, (m.right - bpm.get_width() - s(6), m.y + s(3)))

        # ticker
        slot = self.tick_slot
        ty = slot.y + (slot.h - self._tick_surf.get_height()) // 2
        if self._tick_surf.get_width() <= slot.w - s(8):
            surface.blit(self._tick_surf,
                         (slot.x + (slot.w - self._tick_surf.get_width()) // 2, ty))
        else:
            prev_clip = surface.get_clip()
            surface.set_clip(slot.inflate(-s(6), 0))
            x0 = slot.x + s(4) - int(self.tick_scroll)
            surface.blit(self._tick_surf, (x0, ty))
            surface.blit(self._tick_surf, (x0 + self._tick_surf.get_width() + s(40), ty))
            surface.set_clip(prev_clip)

    def _draw_vat(self, surface, vat, t):
        r = vat["rect"]
        fluid = vat["fluid"]
        sp = vat["specimen"]

        # fluid (pulses gently), leaving an air gap at the top
        pulse = 0.5 + 0.5 * math.sin(t * sp["pulse"])
        fluid_top = r.y + s(12)
        body = lerp_color(lerp_color(fluid, LAB_BG, 0.84),
                          lerp_color(fluid, LAB_BG, 0.74), pulse)
        inner = pygame.Rect(r.x + 2, fluid_top, r.w - 4, r.bottom - 2 - fluid_top)
        pygame.draw.rect(surface, body, inner,
                         border_bottom_left_radius=s(9), border_bottom_right_radius=s(9))
        pygame.draw.line(surface, lerp_color(fluid, (255, 255, 255), 0.3),
                         (inner.x, fluid_top), (inner.right - 1, fluid_top), 1)

        # organism
        cx = r.centerx
        cy = r.centery + s(6) + math.sin(t * 0.7 + sp["bob"]) * s(4)
        br = sp["body_r"] * (1.0 + 0.08 * math.sin(t * sp["pulse"] * 2))

        # tentacles first (behind the body)
        for tc in sp["tentacles"]:
            px, py = cx, cy
            for k in range(4):
                sway = math.sin(t * tc["speed"] + tc["phase"] + k * 0.9) * tc["amp"]
                nx = px + math.cos(tc["angle"]) * tc["len"] / 4 + sway * 0.4
                ny = py + math.sin(tc["angle"]) * tc["len"] / 4
                pygame.draw.line(surface, sp["dark"], (px, py), (nx, ny), max(1, s(3) - k))
                px, py = nx, ny

        # lobed body
        for la, ld, lr in sp["lobes"]:
            wob = 1.0 + 0.1 * math.sin(t * sp["pulse"] * 2 + la)
            lx = cx + math.cos(la) * br * ld
            ly = cy + math.sin(la) * br * ld
            pygame.draw.circle(surface, sp["dark"], (int(lx), int(ly)), int(br * lr * wob))
        pygame.draw.circle(surface, sp["bright"], (int(cx), int(cy)), int(br))
        pygame.draw.circle(surface, sp["dark"], (int(cx), int(cy)), int(br), 1)

        # eyes (blink by skipping)
        for eye in sp["eyes"]:
            if math.sin(t * 0.9 + eye["blink"]) > 0.96:
                continue
            ex = cx + math.cos(eye["angle"]) * br * eye["dist"]
            ey = cy + math.sin(eye["angle"]) * br * eye["dist"]
            pygame.draw.circle(surface, (235, 240, 235), (int(ex), int(ey)), int(eye["r"]))
            look = math.sin(t * 0.5 + eye["blink"]) * eye["r"] * 0.35
            pygame.draw.circle(surface, (20, 24, 20),
                               (int(ex + look), int(ey)), max(1, int(eye["r"] * 0.45)))

        # bubbles
        bub = lerp_color(fluid, (255, 255, 255), 0.45)
        for b in vat["bubbles"]:
            pygame.draw.circle(surface, bub, (int(b[0]), int(b[1])), b[3], 1)

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = (235, 110, 80) if mode == "work" else EKG_GREEN
        txt = self.font_tick.render(f"{mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(12), s(62)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, HAZARD_K, box, border_radius=s(4))
        pygame.draw.rect(surface, c, box, 1, border_radius=s(4))
        surface.blit(txt, rect)
