"""
palette.py — Kea's colours, in one place.

THE LOOK

Dystopian, cyberpunk, a bit Star Wars cockpit, a bit roguelike terminal,
pixel art throughout. Saturated neon on near-black, hard edges, glowing
type, nothing pastel and nothing corporate. Kea is a machine salvaged
from somewhere worse than here, and it should look like it.

WHY THIS FILE EXISTS

Every screen used to declare its own colours at the top — around two
hundred hardcoded tuples across twenty-one files. That is how a theme
drifts: each new screen picks "a nice amber" slightly different from the
last nice amber, and after a dozen screens there is no house style left,
just twelve opinions. The Console and the Board had wandered all the way
into grey office enamel.

So: pull from here. If a colour is not in this file it probably should
not be on the screen, and if you need a new one, add it here with a name
so the next screen can reuse it.

    from ui import palette as pal
    surf.fill(pal.VOID)
    txt = pal.glow_text(font, "READY", pal.CYAN)
    surf.blit(txt, (x, y))

THE ONE RULE THAT OVERRIDES TASTE

The 3.5" panel is dim and low contrast. Neon on black looks spectacular
on a monitor and can be unreadable on the real thing. Body text must
stay well clear of the background in luminance — `contrast()` measures
it and `readable()` is the check. Atmosphere never wins over being able
to read the screen; see docs/UI_GUIDELINES.md §6.
"""

import math

import pygame

# ── the void ────────────────────────────────────────────────────────────────
# Never pure black: a hint of blue reads as depth, and pure black on an
# LCD shows the backlight bleed instead of hiding it.
VOID = (8, 8, 14)
VOID_HI = (14, 15, 24)
PANEL = (18, 19, 30)
PANEL_HI = (28, 30, 46)
GRID = (26, 28, 44)
EDGE = (52, 56, 84)

# ── the neons ───────────────────────────────────────────────────────────────
# Saturated, bright enough to survive the panel, distinct from each other
# at a glance even for the colour-blind (they differ in luminance too).
CYAN = (0, 232, 255)        # the default accent — terminals, chrome, ice
MAGENTA = (255, 58, 168)    # danger, hot, the sprawl at night
PURPLE = (168, 92, 255)     # arcane, secondary
ACID = (140, 255, 80)       # go, alive, growth, "system nominal"
AMBER = (255, 176, 44)      # attention, brass, warm machinery
BLOOD = (255, 62, 72)       # stop, overdue, cancelled
ICE = (150, 230, 255)       # pale cyan, for large calm areas
GOLD = (255, 214, 120)      # highlight on amber
LIME = (198, 255, 140)      # highlight on acid
HOT = (255, 140, 210)       # highlight on magenta

# ── type ────────────────────────────────────────────────────────────────────
INK = (232, 240, 255)       # body text: cool white, never pure white
INK_DIM = (128, 140, 172)   # secondary — still readable, barely
INK_FAINT = (78, 88, 116)   # decoration only; never put words here
SHADOW = (4, 4, 8)

# Rotation for anything that needs "the next distinct colour", e.g. cards,
# tags, chart series. Ordered so neighbours never collide.
CYCLE = [CYAN, MAGENTA, ACID, AMBER, PURPLE, ICE, BLOOD, LIME]

# Semantic aliases. Use these for meaning, the raw names for decoration —
# then a change of heart about "what colour is danger" happens once.
OK = ACID
WARN = AMBER
DANGER = BLOOD
IDLE = INK_DIM
ACCENT = CYAN


def cycle(i):
    """The i-th distinct accent, wrapping."""
    return CYCLE[i % len(CYCLE)]


# ── mixing ──────────────────────────────────────────────────────────────────
def mix(a, b, t):
    """Blend two colours. t=0 is a, t=1 is b."""
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def dim(colour, t=0.5):
    """Toward the void — for inactive states."""
    return mix(colour, VOID, t)


def lift(colour, t=0.35):
    """Toward white — for the hot centre of a glowing thing."""
    return mix(colour, (255, 255, 255), t)


def luminance(colour):
    """Perceived brightness, 0-255. Weighted for how the eye actually
    works, which is why pure blue text disappears and pure green shouts."""
    r, g, b = colour[:3]
    return math.sqrt(0.299 * r * r + 0.587 * g * g + 0.114 * b * b)


def contrast(fg, bg):
    """Luminance gap between two colours, 0-255."""
    return abs(luminance(fg) - luminance(bg))


# Below this, text on the real panel turns to mush. Measured against the
# ELEGOO 3.5", which is dimmer and flatter than any desktop monitor.
MIN_CONTRAST = 60
MIN_CONTRAST_SMALL = 85     # under ~14 px you need more


def readable(fg, bg, small=False):
    """Is this combination safe on the panel? Used by the smoke test."""
    return contrast(fg, bg) >= (MIN_CONTRAST_SMALL if small else MIN_CONTRAST)


# ── glow ────────────────────────────────────────────────────────────────────
# The bloom is the whole look: neon without glow is just bright text.
#
# Everything here is CACHED. A blur per frame would cost more than the
# rest of the screen put together on a Pi 3B+, and the results never
# change for the same inputs — see docs/UI_GUIDELINES.md §4.
_glow_cache = {}
_halo_cache = {}
_CACHE_MAX = 220


def glow_text(font, text, colour, radius=2, strength=110, core=None):
    """Text with a coloured halo bleeding out of it.

    `core` defaults to a lifted version of `colour`, so the letter itself
    is hotter than its own glow — which is what makes it read as emitting
    light rather than as coloured text with a shadow.
    """
    key = (id(font), text, colour, radius, strength, core)
    hit = _glow_cache.get(key)
    if hit is not None:
        return hit

    core = core or lift(colour, 0.45)
    base = font.render(text, True, core)
    w, h = base.get_size()
    pad = radius * 2 + 2
    out = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)

    # Cheap bloom: the same glyph stamped around itself at low alpha.
    # A real gaussian looks marginally better and costs ~40x more.
    ghost = font.render(text, True, colour)
    steps = max(1, radius)
    for r in range(steps, 0, -1):
        a = int(strength * (1.0 - (r - 1) / float(steps)) * 0.55)
        if a <= 0:
            continue
        layer = ghost.copy()
        layer.set_alpha(a)
        for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r),
                       (-r, -r), (r, -r), (-r, r), (r, r)):
            out.blit(layer, (pad + dx, pad + dy))
    out.blit(base, (pad, pad))

    if len(_glow_cache) > _CACHE_MAX:
        _glow_cache.clear()
    _glow_cache[key] = out
    return out


def glow_pad(radius=2):
    """How much bigger a glow_text surface is than the plain text."""
    return radius * 2 + 2


def blit_glow(surface, font, text, colour, pos, radius=2, strength=110,
              core=None):
    """Draw glowing text positioned exactly where plain text would go.

    glow_text() returns a surface padded by the bloom radius, so blitting
    it at the coordinates you would have used for font.render() shifts
    the text down and right and makes it taller — which is how a title
    ends up sitting on top of its own subtitle. This compensates, so
    swapping render() for blit_glow() never moves anything.
    """
    g = glow_text(font, text, colour, radius, strength, core)
    p = glow_pad(radius)
    surface.blit(g, (pos[0] - p, pos[1] - p))
    return g


def halo(size, colour, alpha=70):
    """A soft radial pool of light, for lamps, pips and hotspots."""
    key = (size, colour, alpha)
    hit = _halo_cache.get(key)
    if hit is not None:
        return hit
    surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
    for r in range(size, 0, -1):
        a = int(alpha * (1.0 - r / float(size)) ** 1.6)
        if a > 0:
            pygame.draw.circle(surf, (*colour, a), (size, size), r)
    if len(_halo_cache) > _CACHE_MAX:
        _halo_cache.clear()
    _halo_cache[key] = surf
    return surf


def glow_rect(surface, rect, colour, width=2, radius=0, spread=3, alpha=60):
    """An outlined box that bleeds light outward. Draw it, then draw
    whatever goes inside on top."""
    for i in range(spread, 0, -1):
        a = int(alpha * (1.0 - (i - 1) / float(spread)) * 0.5)
        if a <= 0:
            continue
        layer = pygame.Surface((rect.w + i * 2, rect.h + i * 2), pygame.SRCALPHA)
        pygame.draw.rect(layer, (*colour, a), layer.get_rect(), width,
                         border_radius=radius + i)
        surface.blit(layer, (rect.x - i, rect.y - i))
    pygame.draw.rect(surface, colour, rect, width, border_radius=radius)


def scanlines(size, alpha=26, step=3):
    """A cached CRT scanline overlay. Blit last, over everything.

    Use sparingly: it costs one full-screen alpha blit per frame and it
    eats contrast, which the panel has little of to spare.
    """
    key = ("scan", size, alpha, step)
    hit = _halo_cache.get(key)
    if hit is not None:
        return hit
    surf = pygame.Surface(size, pygame.SRCALPHA)
    for y in range(0, size[1], step):
        pygame.draw.line(surf, (0, 0, 0, alpha), (0, y), (size[0], y))
    _halo_cache[key] = surf
    return surf


def grid(size, colour=GRID, step=24, glow_every=0):
    """The blueprint/holo-table grid under everything. Cached: it never
    changes, so it must never be redrawn per frame."""
    key = ("grid", size, colour, step, glow_every)
    hit = _halo_cache.get(key)
    if hit is not None:
        return hit
    surf = pygame.Surface(size, pygame.SRCALPHA)
    w, h = size
    for i, x in enumerate(range(0, w, step)):
        c = mix(colour, CYAN, 0.35) if glow_every and i % glow_every == 0 else colour
        pygame.draw.line(surf, c, (x, 0), (x, h))
    for i, y in enumerate(range(0, h, step)):
        c = mix(colour, CYAN, 0.35) if glow_every and i % glow_every == 0 else colour
        pygame.draw.line(surf, c, (0, y), (w, y))
    _halo_cache[key] = surf
    return surf


def bevel(surface, rect, colour=EDGE, cut=6):
    """A clipped-corner panel outline — the Star Wars console shape.
    Rectangles read as corporate; cut corners read as hardware."""
    c = cut
    pts = [(rect.x + c, rect.y), (rect.right - c, rect.y),
           (rect.right, rect.y + c), (rect.right, rect.bottom - c),
           (rect.right - c, rect.bottom), (rect.x + c, rect.bottom),
           (rect.x, rect.bottom - c), (rect.x, rect.y + c)]
    pygame.draw.polygon(surface, colour, pts, 1)
    return pts
