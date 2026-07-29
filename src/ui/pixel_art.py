"""
pixel_art.py — chunky sprites, drawn from text.

A sprite is a list of equal-length strings plus a palette mapping each
character to a colour. '.' (or any char missing from the palette) is
transparent. Rendering blows each cell up into a square "pixel", so the
art stays crisp at any size and reads properly on a 480x320 panel.

    from ui.pixel_art import SPRITES, draw

    draw(surface, SPRITES["kea"], x, y, px=4)

Everything is cached per (pixel size, tint, alpha), so a sprite costs one
surface blit per frame no matter how many cells it has — which matters on
a Pi 3. Animations are just a list of sprites plus a frame time.

Adding art: write the rows, add a palette, drop it in SPRITES. Nothing
else needs to change.
"""

import pygame

# ── palettes ────────────────────────────────────────────────────────────────
DROID = {
    "o": (26, 24, 30),        # outline
    "b": (196, 202, 212),     # brushed body
    "s": (128, 136, 150),     # shade
    "e": (120, 226, 255),     # visor glow
    "d": (28, 90, 120),       # visor dark
    "a": (240, 176, 64),      # amber accent
    "r": (214, 74, 58),       # red lamp
}
FRUIT = {
    "o": (54, 18, 16),
    "r": (206, 62, 48),
    "R": (166, 42, 32),
    "h": (240, 138, 120),
    "g": (86, 150, 62),
    "G": (58, 110, 44),
}
SKY = {
    "o": (30, 34, 44),
    "y": (246, 198, 84),      # sun
    "Y": (255, 232, 150),
    "w": (226, 232, 240),     # cloud
    "W": (172, 182, 198),
    "b": (108, 174, 226),     # rain
    "i": (206, 232, 246),     # snow / ice
    "a": (246, 210, 96),      # bolt
    "m": (210, 214, 226),     # moon
}
FLORA = {
    "o": (28, 44, 26),
    "g": (104, 176, 84),
    "G": (66, 128, 56),
    "l": (150, 210, 120),
    "f": (232, 122, 168),     # flower
    "y": (244, 206, 100),
    "d": (92, 70, 48),        # soil
}

# ── art ─────────────────────────────────────────────────────────────────────
_KEA = [
    "....oooo....",
    "..oobbbboo..",
    ".obbbbbbbbo.",
    ".obdddddddo.",
    ".obdeeeeedo.",
    ".obdeddedeo.",
    ".obdeeeeedo.",
    ".obdddddddo.",
    ".obbbbbbbbo.",
    "..obbaabbo..",
    "...obbbbo...",
    "..obbbbbbo..",
    ".obbo..obbo.",
    ".oo......oo.",
]
_KEA_BLINK = [
    "....oooo....",
    "..oobbbboo..",
    ".obbbbbbbbo.",
    ".obdddddddo.",
    ".obdddddddo.",
    ".obdeeeeedo.",
    ".obdddddddo.",
    ".obdddddddo.",
    ".obbbbbbbbo.",
    "..obbaabbo..",
    "...obbbbo...",
    "..obbbbbbo..",
    ".obbo..obbo.",
    ".oo......oo.",
]
_KEA_HAPPY = [
    "....oooo....",
    "..oobbbboo..",
    ".obbbbbbbbo.",
    ".obdddddddo.",
    ".obdeddedeo.",
    ".obdeddedeo.",
    ".obdeeeeedo.",
    ".obdddddddo.",
    ".obbbbbbbbo.",
    "..obbaabbo..",
    "...obbbbo...",
    "..obbbbbbo..",
    ".obbo..obbo.",
    ".oo......oo.",
]
_KEA_SLEEP = [
    "............",
    "....oooo....",
    "..oobbbboo..",
    ".obbbbbbbbo.",
    ".obdddddddo.",
    ".obdddddddo.",
    ".obddeeeddo.",
    ".obdddddddo.",
    ".obbbbbbbbo.",
    "..obbssbbo..",
    "...obbbbo...",
    "..obbbbbbo..",
    ".obbo..obbo.",
    ".oo......oo.",
]
_KEA_ALERT = [
    ".....rr.....",
    "....oooo....",
    "..oobbbboo..",
    ".obbbbbbbbo.",
    ".obdddddddo.",
    ".obdeddedeo.",
    ".obdeeeeedo.",
    ".obddeeeddo.",
    ".obbbbbbbbo.",
    "..obbaabbo..",
    "...obbbbo...",
    "..obbbbbbo..",
    ".obbo..obbo.",
    ".oo......oo.",
]

_TOMATO = [
    ".....gg.....",
    "..g.gGg.g...",
    "...gggg.....",
    "..oorroorr..",
    ".orrrrrrrro.",
    "orhrrrrrrrro",
    "orhrrrrrrrro",
    "orrrrrrrrRro",
    "orrrrrrrRRro",
    ".orrrrrrRro.",
    "..oRRRRRRo..",
    "....oooo....",
]

_SUN = [
    "...o....o...",
    "....o..o....",
    "..oooyyooo..",
    "...oyYYyo...",
    "ooyYYYYYYyoo",
    "..yYYYYYYy..",
    "..yYYYYYYy..",
    "ooyYYYYYYyoo",
    "...oyYYyo...",
    "..oooyyooo..",
    "....o..o....",
    "...o....o...",
]
_CLOUD = [
    "............",
    "....oooo....",
    "..oowwwwoo..",
    ".owwwwwwwwo.",
    "owwwwwwwwwwo",
    "owwwwwwwwwwo",
    "oWWwwwwwwWWo",
    ".oWWWWWWWWo.",
    "..oooooooo..",
    "............",
    "............",
    "............",
]
_RAIN = [
    "....oooo....",
    "..oowwwwoo..",
    ".owwwwwwwwo.",
    "owwwwwwwwwwo",
    "oWWwwwwwwWWo",
    ".oWWWWWWWWo.",
    "..oooooooo..",
    "..b..b..b...",
    "..b..b..b...",
    ".b..b..b....",
    ".b..b..b....",
    "............",
]
_SNOW = [
    "....oooo....",
    "..oowwwwoo..",
    ".owwwwwwwwo.",
    "owwwwwwwwwwo",
    "oWWwwwwwwWWo",
    ".oWWWWWWWWo.",
    "..oooooooo..",
    "...i..i..i..",
    "..iii.iii...",
    "...i..i..i..",
    "..i..i..i...",
    "............",
]
_STORM = [
    "....oooo....",
    "..oowwwwoo..",
    ".owwwwwwwwo.",
    "owwwwwwwwwwo",
    "oWWwwwwwwWWo",
    ".oWWWWWWWWo.",
    "..oooooooo..",
    ".....aa.....",
    "....aa......",
    "...aaaa.....",
    "....aa......",
    "...aa.......",
]
_MOON = [
    "....oooo....",
    "..oommmmoo..",
    ".ommmmmmoo..",
    "ommmmmmo....",
    "ommmmmo.....",
    "ommmmmo.....",
    "ommmmmo.....",
    "ommmmmmo....",
    ".ommmmmmoo..",
    "..oommmmoo..",
    "....oooo....",
    "............",
]

_SPROUT = [
    "............",
    "............",
    "............",
    "............",
    "............",
    "......l.....",
    "...g..g..g..",
    "....ggGg....",
    ".....Gg.....",
    "...dddddd...",
    "..dddddddd..",
    "..dddddddd..",
]
_PLANT = [
    "............",
    "....l..l....",
    "...glg.glg..",
    "....gGgGg...",
    "..l..gGg..l.",
    "..glg.Gg.glg",
    "...g..Gg..g.",
    ".....gGg....",
    "......G.....",
    "...dddddd...",
    "..dddddddd..",
    "..dddddddd..",
]
_BLOOM = [
    "....f..f....",
    "...fyf.fyf..",
    "....f.gf....",
    "..l..gGg..l.",
    ".glg..Gg.glg",
    "..g...Gg..g.",
    "....l.Gg.l..",
    "...glgGgglg.",
    "......G.....",
    "...dddddd...",
    "..dddddddd..",
    "..dddddddd..",
]


# ── engine ──────────────────────────────────────────────────────────────────
class Sprite:
    """Text rows + palette -> a cached, scalable pygame surface."""

    def __init__(self, rows, palette, name=""):
        self.rows = rows
        self.palette = palette
        self.name = name
        self.h = len(rows)
        self.w = max((len(r) for r in rows), default=0)
        self._cache = {}

    def surface(self, px=3, tint=None, alpha=255, flip=False):
        key = (px, tint, alpha, flip)
        got = self._cache.get(key)
        if got is not None:
            return got
        surf = pygame.Surface((self.w * px, self.h * px), pygame.SRCALPHA)
        for y, row in enumerate(self.rows):
            for x, ch in enumerate(row):
                col = self.palette.get(ch)
                if col is None:
                    continue
                if tint is not None:                 # blend toward a tint
                    t = tint[3] / 255.0 if len(tint) > 3 else 0.5
                    col = tuple(int(col[i] + (tint[i] - col[i]) * t) for i in range(3))
                surf.fill(col, (x * px, y * px, px, px))
        if alpha < 255:
            surf.set_alpha(alpha)
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        if len(self._cache) < 48:                    # bounded: never leaks
            self._cache[key] = surf
        return surf

    def size(self, px=3):
        return (self.w * px, self.h * px)


class Anim:
    """A few sprites shown in turn. `at(t)` picks the frame for a time."""

    def __init__(self, frames, frame_time=0.25):
        self.frames = frames
        self.frame_time = frame_time

    def at(self, t):
        if not self.frames:
            return None
        return self.frames[int(t / self.frame_time) % len(self.frames)]


def draw(surface, sprite, x, y, px=3, tint=None, alpha=255, flip=False,
         center=False):
    """Blit a sprite. Returns the rect it occupied."""
    if sprite is None:
        return pygame.Rect(x, y, 0, 0)
    s = sprite.surface(px, tint, alpha, flip)
    rect = s.get_rect(center=(x, y)) if center else s.get_rect(topleft=(x, y))
    surface.blit(s, rect)
    return rect


# ── library ─────────────────────────────────────────────────────────────────
SPRITES = {
    "kea":        Sprite(_KEA, DROID, "kea"),
    "kea_blink":  Sprite(_KEA_BLINK, DROID, "kea_blink"),
    "kea_happy":  Sprite(_KEA_HAPPY, DROID, "kea_happy"),
    "kea_sleep":  Sprite(_KEA_SLEEP, DROID, "kea_sleep"),
    "kea_alert":  Sprite(_KEA_ALERT, DROID, "kea_alert"),
    "tomato":     Sprite(_TOMATO, FRUIT, "tomato"),
    "sun":        Sprite(_SUN, SKY, "sun"),
    "cloud":      Sprite(_CLOUD, SKY, "cloud"),
    "rain":       Sprite(_RAIN, SKY, "rain"),
    "snow":       Sprite(_SNOW, SKY, "snow"),
    "storm":      Sprite(_STORM, SKY, "storm"),
    "moon":       Sprite(_MOON, SKY, "moon"),
    "sprout":     Sprite(_SPROUT, FLORA, "sprout"),
    "plant":      Sprite(_PLANT, FLORA, "plant"),
    "bloom":      Sprite(_BLOOM, FLORA, "bloom"),
}

# Kea idling: mostly open-eyed with an occasional blink.
KEA_IDLE = Anim([SPRITES["kea"]] * 7 + [SPRITES["kea_blink"]], 0.28)
GROWTH = [SPRITES["sprout"], SPRITES["plant"], SPRITES["bloom"]]


def weather_sprite(code):
    """Map a loose description ('light rain', 'Clear') to a sprite."""
    s = (code or "").lower()
    if any(k in s for k in ("thunder", "storm")):
        return SPRITES["storm"]
    if any(k in s for k in ("snow", "sleet", "ice")):
        return SPRITES["snow"]
    if any(k in s for k in ("rain", "drizzle", "shower")):
        return SPRITES["rain"]
    if any(k in s for k in ("cloud", "overcast", "fog", "mist")):
        return SPRITES["cloud"]
    if "night" in s or "moon" in s:
        return SPRITES["moon"]
    return SPRITES["sun"]


def mood_sprite(mood):
    """Kea's face for a mood name."""
    return {
        "happy": SPRITES["kea_happy"],
        "proud": SPRITES["kea_happy"],
        "sleepy": SPRITES["kea_sleep"],
        "sad": SPRITES["kea_sleep"],
        "worried": SPRITES["kea_alert"],
        "alarm": SPRITES["kea_alert"],
    }.get(mood, SPRITES["kea"])
