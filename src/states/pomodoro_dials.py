"""
pomodoro_dials.py
-----------------
The instruments the focus timer can wear.

Every dial answers the same question — *how much of this session is
left* — but as a different physical mechanism, and one is drawn at
random each time you arrive at the Pomodoro screen. They all render
into a surface of the same size, so the state can drop any of them
into the same slot (and flip the ones that make sense to flip).

    dial = pick()                       # random instrument
    surf = dial.render(size, frac, colour, t, running)

`frac` is 1.0 at the start of a session and 0.0 when it runs out, so
every mechanism empties, burns down or unwinds in real time.

Adding another: write a class with `flips` and `render()`, then list it
in DIALS. Nothing else needs to change.
"""

import math
import random

import pygame

# shared tones (the state passes the session colour in as `col`)
BRASS = (176, 138, 66)
BRASS_LIT = (226, 190, 116)
BRASS_DARK = (92, 70, 30)
GLASS = (196, 214, 220)
SOOT = (26, 21, 18)


def _lerp(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


def _dim(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


# ════════════════════════════════════════════════════════════════════════════
class Hourglass:
    """Blown glass and falling sand — the original instrument."""

    name = "HOURGLASS"
    flips = True                       # rotating 180° is literally correct

    def render(self, size, frac, col, t, running, grains):
        w, h = size
        g = pygame.Surface(size, pygame.SRCALPHA)
        hw, nw = int(w * 0.39), max(2, int(w * 0.034))
        cx, cy = w // 2, h // 2
        bulb = int(h * 0.447)
        pad = int(h * 0.053)
        ly0, lyn, ly1 = cy - bulb, cy, cy + bulb

        def half_w(y):
            if y <= lyn:
                p = (y - ly0) / max(1, (lyn - ly0))
                return hw + (nw - hw) * (p ** 1.7)
            p = (y - lyn) / max(1, (ly1 - lyn))
            return nw + (hw - nw) * (p ** 1.7)

        # glass envelope
        pts_l = [(cx - half_w(y), y) for y in range(ly0, ly1 + 1, 2)]
        pts_r = [(cx + half_w(y), y) for y in reversed(range(ly0, ly1 + 1, 2))]
        pygame.draw.polygon(g, (*GLASS, 26), pts_l + pts_r)

        # upper sand: a body whose top edge falls with frac
        top_y = ly0 + int((lyn - ly0) * (1.0 - frac))
        if frac > 0.002:
            band = [(cx - half_w(y), y) for y in range(top_y, lyn + 1, 2)]
            band += [(cx + half_w(y), y) for y in reversed(range(top_y, lyn + 1, 2))]
            if len(band) > 2:
                pygame.draw.polygon(g, col, band)
                pygame.draw.line(g, _lerp(col, (255, 255, 255), 0.45),
                                 (cx - half_w(top_y), top_y),
                                 (cx + half_w(top_y), top_y), 2)

        # lower mound grows as the upper empties
        mound = (1.0 - frac)
        if mound > 0.002:
            mh = int((ly1 - lyn) * mound)
            base_y = ly1
            peak_y = ly1 - mh
            bw = half_w(ly1)
            pygame.draw.polygon(g, col, [
                (cx - bw, base_y), (cx + bw, base_y),
                (cx + bw * 0.35, peak_y), (cx - bw * 0.35, peak_y)])
            pygame.draw.line(g, _lerp(col, (255, 255, 255), 0.35),
                             (cx - bw * 0.35, peak_y), (cx + bw * 0.35, peak_y), 2)

        # the stream, only while it runs
        if running and 0.001 < frac < 0.999:
            for gx, gy, _sp in grains:
                pygame.draw.line(g, _lerp(col, (255, 255, 255), 0.25),
                                 (cx + gx, gy), (cx + gx, gy + 3), 1)

        # brass caps and posts
        for y in (ly0 - pad // 2, ly1 + pad // 2):
            r = pygame.Rect(cx - hw - 5, y - 5, 2 * (hw + 5), 10)
            pygame.draw.rect(g, BRASS, r, border_radius=3)
            pygame.draw.rect(g, BRASS_DARK, r, 1, border_radius=3)
        for sx in (-1, 1):
            px = cx + sx * (hw + 4)
            pygame.draw.line(g, BRASS_DARK, (px, ly0 - 2), (px, ly1 + 2), 3)
            pygame.draw.line(g, BRASS_LIT, (px - 1, ly0 - 2), (px - 1, ly1 + 2), 1)
        return g


# ════════════════════════════════════════════════════════════════════════════
class Candle:
    """A taper that burns down, drips wax and gutters in a draught."""

    name = "CANDLE"
    flips = False

    def render(self, size, frac, col, t, running, grains):
        w, h = size
        g = pygame.Surface(size, pygame.SRCALPHA)
        cx = w // 2
        base_y = int(h * 0.88)
        full = int(h * 0.62)
        body = max(int(h * 0.06), int(full * frac))
        top_y = base_y - body
        cw = int(w * 0.20)

        # holder
        dish = pygame.Rect(cx - int(w * 0.30), base_y, int(w * 0.60), int(h * 0.05))
        pygame.draw.ellipse(g, BRASS, dish)
        pygame.draw.ellipse(g, BRASS_DARK, dish, 1)
        pygame.draw.arc(g, BRASS_LIT, dish.inflate(-6, -4), math.pi, 2 * math.pi, 2)

        # wax column, warm on one side
        col_rect = pygame.Rect(cx - cw, top_y, cw * 2, body)
        pygame.draw.rect(g, (238, 230, 210), col_rect, border_radius=3)
        pygame.draw.rect(g, (208, 196, 172), pygame.Rect(cx + cw // 3, top_y,
                                                         cw - cw // 3, body),
                         border_radius=3)
        pygame.draw.rect(g, _dim(col, 0.5), col_rect, 1, border_radius=3)
        # molten rim + drips
        pygame.draw.ellipse(g, _lerp((238, 230, 210), col, 0.45),
                            pygame.Rect(cx - cw, top_y - 4, cw * 2, 9))
        rng = random.Random(7)
        for i in range(3):
            dx = rng.randint(-cw + 3, cw - 3)
            dl = int((0.25 + 0.5 * ((i + t * 0.05) % 1.0)) * min(26, body))
            if dl > 4:
                pygame.draw.line(g, (226, 216, 196), (cx + dx, top_y),
                                 (cx + dx, top_y + dl), 2)
                pygame.draw.circle(g, (238, 230, 210), (cx + dx, top_y + dl), 2)

        # wick + flame (still and dark when paused)
        wick_y = top_y - 5
        pygame.draw.line(g, SOOT, (cx, top_y), (cx, wick_y), 2)
        if running:
            flick = math.sin(t * 11) * 0.10 + math.sin(t * 23) * 0.05
            fh = int(h * 0.075 * (1.0 + flick))
            fw = int(w * 0.045 * (1.0 - flick * 0.5))
            sway = int(math.sin(t * 7) * 2)
            halo = pygame.Surface((fw * 8, fh * 4), pygame.SRCALPHA)
            pygame.draw.ellipse(halo, (*col, 42), halo.get_rect())
            g.blit(halo, (cx - fw * 4 + sway, wick_y - fh * 3))
            pygame.draw.polygon(g, _lerp(col, (255, 240, 190), 0.35), [
                (cx + sway, wick_y - fh), (cx + fw, wick_y - fh // 3),
                (cx, wick_y + 2), (cx - fw, wick_y - fh // 3)])
            pygame.draw.polygon(g, (255, 250, 226), [
                (cx + sway // 2, wick_y - fh // 2), (cx + fw // 2, wick_y - fh // 6),
                (cx, wick_y), (cx - fw // 2, wick_y - fh // 6)])
        else:
            for i in range(3):                       # a thread of smoke
                yy = wick_y - 6 - i * 7
                pygame.draw.circle(g, (90, 84, 78),
                                   (cx + int(math.sin(t * 1.5 + i) * 4), yy), 2)
        return g


# ════════════════════════════════════════════════════════════════════════════
class Orbit:
    """An orrery arm sweeping a graduated ring back to its origin."""

    name = "ORBIT"
    flips = False

    def render(self, size, frac, col, t, running, grains):
        w, h = size
        g = pygame.Surface(size, pygame.SRCALPHA)
        cx, cy = w // 2, h // 2
        R = int(min(w, h) * 0.40)

        pygame.draw.circle(g, (*GLASS, 20), (cx, cy), R + 8)
        pygame.draw.circle(g, BRASS_DARK, (cx, cy), R + 8, 2)
        for i in range(60):                       # graduations
            a = math.radians(i * 6 - 90)
            long_tick = (i % 5 == 0)
            r0 = R + (2 if long_tick else 5)
            pygame.draw.line(g, BRASS if long_tick else BRASS_DARK,
                             (cx + math.cos(a) * r0, cy + math.sin(a) * r0),
                             (cx + math.cos(a) * (R + 8), cy + math.sin(a) * (R + 8)),
                             2 if long_tick else 1)

        # remaining arc, drawn from 12 o'clock clockwise
        if frac > 0.001:
            rect = pygame.Rect(cx - R, cy - R, 2 * R, 2 * R)
            start = math.pi / 2 - 2 * math.pi * frac
            pygame.draw.arc(g, col, rect, start, math.pi / 2, max(3, R // 9))

        # the travelling body
        ang = math.pi / 2 - 2 * math.pi * frac
        px, py = cx + math.cos(ang) * R, cy - math.sin(ang) * R
        if running:
            halo = pygame.Surface((R, R), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*col, 46), (R // 2, R // 2), R // 2)
            g.blit(halo, (px - R // 2, py - R // 2))
        pygame.draw.line(g, _dim(col, 0.55), (cx, cy), (px, py), 2)
        pygame.draw.circle(g, col, (int(px), int(py)), max(4, R // 12))
        pygame.draw.circle(g, (255, 255, 255), (int(px - 1), int(py - 2)),
                           max(1, R // 34))

        # hub
        pygame.draw.circle(g, BRASS, (cx, cy), max(5, R // 9))
        pygame.draw.circle(g, BRASS_DARK, (cx, cy), max(5, R // 9), 1)
        pygame.draw.circle(g, BRASS_LIT, (cx - 2, cy - 2), max(1, R // 26))
        return g


# ════════════════════════════════════════════════════════════════════════════
class Tube:
    """A vacuum tube whose glowing charge drains down the envelope."""

    name = "TUBE"
    flips = False

    def render(self, size, frac, col, t, running, grains):
        w, h = size
        g = pygame.Surface(size, pygame.SRCALPHA)
        cx = w // 2
        tw, th = int(w * 0.34), int(h * 0.62)
        top = int(h * 0.14)
        body = pygame.Rect(cx - tw, top, tw * 2, th)

        # envelope
        pygame.draw.rect(g, (*GLASS, 26), body, border_radius=tw)
        pygame.draw.rect(g, (*GLASS, 70), body, 2, border_radius=tw)

        # charge level
        lvl_h = int((th - 12) * frac)
        if lvl_h > 2:
            lvl = pygame.Rect(body.x + 5, body.bottom - 6 - lvl_h,
                              body.w - 10, lvl_h)
            glow = pygame.Surface(lvl.size, pygame.SRCALPHA)
            for i in range(lvl.h):
                a = 120 + int(80 * (i / max(1, lvl.h)))
                pygame.draw.line(glow, (*col, a), (0, i), (lvl.w, i))
            g.blit(glow, lvl.topleft)
            # surface ripple
            ry = lvl.top + int(math.sin(t * 3) * 1.5)
            pygame.draw.line(g, _lerp(col, (255, 255, 255), 0.5),
                             (lvl.left, ry), (lvl.right, ry), 2)

        # filament: bright and buzzing when running
        fx = cx
        f_top, f_bot = top + 14, body.bottom - 14
        if running:
            pts = []
            for i in range(9):
                yy = f_top + (f_bot - f_top) * i / 8.0
                pts.append((fx + math.sin(t * 6 + i) * 4 * (i % 2), yy))
            if len(pts) > 1:
                pygame.draw.lines(g, _lerp(col, (255, 240, 200), 0.6), False, pts, 2)
            halo = pygame.Surface((tw, th), pygame.SRCALPHA)
            pygame.draw.ellipse(halo, (*col, 34), halo.get_rect())
            g.blit(halo, (cx - tw // 2, top + th // 4))
        else:
            pygame.draw.line(g, (70, 62, 54), (fx, f_top), (fx, f_bot), 2)

        # base and pins
        base = pygame.Rect(cx - tw, body.bottom - 6, tw * 2, int(h * 0.09))
        pygame.draw.rect(g, (44, 38, 32), base, border_radius=4)
        pygame.draw.rect(g, BRASS_DARK, base, 1, border_radius=4)
        for i in range(5):
            px = base.x + 6 + i * (base.w - 12) / 4.0
            pygame.draw.line(g, BRASS, (px, base.bottom),
                             (px, base.bottom + int(h * 0.035)), 3)
        return g


# ════════════════════════════════════════════════════════════════════════════
class PixelPot:
    """Pixel art: a tomato that ripens as the session burns down, with Kea
    watching from the soil line. Green at the start, deep red at the end."""

    name = "PIXEL"
    flips = False

    def render(self, size, frac, col, t, running, grains):
        from ui import pixel_art as pa

        w, h = size
        g = pygame.Surface(size, pygame.SRCALPHA)
        cx = w // 2

        # the fruit, ripening: tint from green toward the session colour
        ripe = 1.0 - frac                       # 0 at the start, 1 when done
        tint = (*_lerp((92, 158, 66), col, ripe), int(110 + 120 * ripe))
        px = max(3, int(min(w, h) * 0.055))
        spr = pa.SPRITES["tomato"]
        sw, sh = spr.size(px)
        bob = int(math.sin(t * 2.2) * 2) if running else 0
        pa.draw(g, spr, cx - sw // 2, int(h * 0.16) + bob, px, tint=tint)

        # a row of pips: one per tenth still to go
        pips = int(round(frac * 10))
        pw = max(3, px // 2)
        total = 10 * (pw * 2)
        for i in range(10):
            on = i < pips
            c = col if on else (58, 52, 48)
            gx = cx - total // 2 + i * pw * 2
            g.fill(c, (gx, int(h * 0.60), pw, pw))

        # Kea, watching the pot: awake while it runs, dozing when held
        kp = max(2, px - 1)
        kea = (pa.KEA_IDLE.at(t) if running else pa.SPRITES["kea_sleep"])
        kw, kh = kea.size(kp)
        pa.draw(g, kea, cx - kw // 2, int(h * 0.68), kp)

        # soil line under them both
        pygame.draw.rect(g, (74, 56, 38), (int(w * 0.12), int(h * 0.68) + kh,
                                           int(w * 0.76), max(3, px)))
        return g


DIALS = [Hourglass(), Candle(), Orbit(), Tube(), PixelPot()]


def pick(exclude=None):
    """A random instrument, avoiding an immediate repeat where possible."""
    pool = [d for d in DIALS if d.name != exclude] or DIALS
    return random.choice(pool)
