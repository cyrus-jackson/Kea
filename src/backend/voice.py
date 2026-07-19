"""
voice.py — Kea's voice.

Not speech: chirps. Every utterance is synthesised from scratch at
startup (no sound files anywhere) as a short sequence of pitch-swept
tones with vibrato and a soft envelope — the astromech recipe.

    from backend import voice
    voice.say("happy")

Design rules, all of which matter on a desk companion:
  * never blocks the render loop — synthesis happens on a worker
    thread, playback is fire-and-forget
  * never crashes the app — no audio device, no numpy, no mixer, no
    problem; every call becomes a silent no-op
  * never chatters — a global floor between utterances plus a
    per-phrase cooldown, so Kea stays charming rather than annoying

Off switches, in order of bluntness:
    KEA_VOICE=0        no voice at all
    KEA_VOICE_VOL=0.4  master volume (default 0.55)
    voice.toggle_mute()  runtime, bound to M and to the deck toggle
"""

import math
import os
import random
import threading
import time

RATE = 22050          # default; replaced by the mixer's real rate at build
_CHANNELS = 2
_ENABLED = os.getenv("KEA_VOICE", "1").strip().lower() not in {"0", "false", "off"}
try:
    _VOLUME = max(0.0, min(1.0, float(os.getenv("KEA_VOICE_VOL", "0.55"))))
except ValueError:
    _VOLUME = 0.55

_muted = False
_ready = False
_pending = None
_sounds = {}
_last_any = 0.0
_last_of = {}
_lock = threading.Lock()

MIN_GAP = 0.35        # seconds between any two utterances
COOLDOWN = 2.5        # seconds before the same phrase may repeat

try:
    import numpy as _np
except Exception:
    _np = None


# ══════════════════════════════════════════════════════════════════════════
# Synthesis
# ══════════════════════════════════════════════════════════════════════════
def _tone(f0, f1, dur, wave="sine", vib=0.0, vib_hz=0.0, vol=1.0):
    """One pitch-swept tone with a soft attack/release. Returns a list or
    numpy array of floats in [-1, 1]."""
    n = max(1, int(RATE * dur))
    atk = max(1, int(n * 0.12))
    rel = max(1, int(n * 0.28))

    if _np is not None:
        t = _np.arange(n) / RATE
        ratio = max(1e-6, f1 / f0)
        freq = f0 * (ratio ** (t / dur))
        if vib:
            freq = freq * (1.0 + vib * _np.sin(2 * _np.pi * vib_hz * t))
        phase = 2 * _np.pi * _np.cumsum(freq) / RATE
        if wave == "square":
            w = _np.sign(_np.sin(phase))
        elif wave == "tri":
            w = 2.0 * _np.arcsin(_np.clip(_np.sin(phase), -1, 1)) / _np.pi
        elif wave == "saw":
            w = 2.0 * ((phase / (2 * _np.pi)) % 1.0) - 1.0
        else:
            w = _np.sin(phase)
        env = _np.ones(n)
        env[:atk] = _np.linspace(0.0, 1.0, atk)
        env[n - rel:] = _np.linspace(1.0, 0.0, rel) ** 1.5
        return w * env * vol

    # pure-python fallback (no numpy): same maths, slower
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        ratio = max(1e-6, f1 / f0)
        freq = f0 * (ratio ** (t / dur))
        if vib:
            freq *= 1.0 + vib * math.sin(2 * math.pi * vib_hz * t)
        phase += 2 * math.pi * freq / RATE
        if wave == "square":
            w = 1.0 if math.sin(phase) >= 0 else -1.0
        elif wave == "tri":
            w = 2.0 * math.asin(max(-1.0, min(1.0, math.sin(phase)))) / math.pi
        elif wave == "saw":
            w = 2.0 * ((phase / (2 * math.pi)) % 1.0) - 1.0
        else:
            w = math.sin(phase)
        if i < atk:
            e = i / atk
        elif i > n - rel:
            e = ((n - i) / rel) ** 1.5
        else:
            e = 1.0
        out.append(w * e * vol)
    return out


def _rest(dur):
    n = max(1, int(RATE * dur))
    return _np.zeros(n) if _np is not None else [0.0] * n


def _phrase(parts):
    """Concatenate tones/rests into one waveform."""
    if _np is not None:
        return _np.concatenate(parts) if parts else _np.zeros(1)
    out = []
    for p in parts:
        out.extend(p)
    return out or [0.0]


# ══════════════════════════════════════════════════════════════════════════
# The vocabulary — Kea's whole emotional range
# ══════════════════════════════════════════════════════════════════════════
def _vocabulary():
    v = {}

    # waking up: a rising three-note flourish, pleased to be here
    v["wake"] = _phrase([
        _tone(320, 520, 0.10, "sine", 0.03, 22),
        _rest(0.03),
        _tone(520, 700, 0.09, "sine", 0.04, 26),
        _rest(0.02),
        _tone(700, 980, 0.16, "sine", 0.05, 18, vol=0.9),
    ])

    # soft acknowledgment — used when you change worlds
    v["blip"] = _phrase([
        _tone(620, 760, 0.06, "sine", 0.0, 0, vol=0.55),
    ])

    # something arrived: curious, questioning, rising
    v["curious"] = _phrase([
        _tone(480, 640, 0.08, "tri", 0.05, 24),
        _rest(0.025),
        _tone(600, 900, 0.13, "tri", 0.07, 30, vol=0.95),
        _rest(0.02),
        _tone(880, 1020, 0.09, "sine", 0.05, 26, vol=0.8),
    ])

    # you finished something: bright and delighted
    v["happy"] = _phrase([
        _tone(660, 880, 0.07, "sine", 0.0, 0),
        _rest(0.02),
        _tone(880, 1180, 0.14, "sine", 0.04, 20, vol=0.95),
    ])

    # a milestone: triumphant little fanfare
    v["proud"] = _phrase([
        _tone(520, 620, 0.08, "tri"),
        _rest(0.02),
        _tone(660, 780, 0.08, "tri"),
        _rest(0.02),
        _tone(800, 980, 0.10, "tri"),
        _rest(0.03),
        _tone(1040, 1240, 0.22, "sine", 0.06, 16, vol=0.95),
    ])

    # something's overdue: worried, wobbling, falling away
    v["worried"] = _phrase([
        _tone(620, 470, 0.16, "tri", 0.10, 15),
        _rest(0.03),
        _tone(500, 360, 0.20, "tri", 0.12, 12, vol=0.9),
    ])

    # disappointed sigh — long ignored, low and slow
    v["sad"] = _phrase([
        _tone(430, 250, 0.42, "sine", 0.06, 7, vol=0.75),
    ])

    # urgent: stuttered alarm, deliberately unpleasant
    v["alarm"] = _phrase([
        _tone(900, 900, 0.07, "square", 0.0, 0, vol=0.65),
        _rest(0.045),
        _tone(900, 900, 0.07, "square", 0.0, 0, vol=0.65),
        _rest(0.045),
        _tone(1050, 780, 0.16, "square", 0.10, 22, vol=0.6),
    ])

    # settling into work: determined, climbing
    v["focus_start"] = _phrase([
        _tone(380, 500, 0.11, "tri", 0.03, 14),
        _rest(0.02),
        _tone(520, 700, 0.17, "tri", 0.04, 16, vol=0.9),
    ])

    # session over: satisfied two-note chime
    v["focus_done"] = _phrase([
        _tone(880, 880, 0.11, "sine", 0.02, 12),
        _rest(0.04),
        _tone(660, 660, 0.26, "sine", 0.03, 9, vol=0.85),
    ])

    # late at night: a slow sleepy hum
    v["sleepy"] = _phrase([
        _tone(300, 240, 0.34, "sine", 0.05, 5, vol=0.6),
        _rest(0.05),
        _tone(250, 190, 0.40, "sine", 0.04, 4, vol=0.5),
    ])

    # a small questioning noise, when it wants something
    v["question"] = _phrase([
        _tone(540, 760, 0.13, "tri", 0.06, 20, vol=0.8),
    ])

    return v


# ══════════════════════════════════════════════════════════════════════════
# Playback
# ══════════════════════════════════════════════════════════════════════════
def _to_sound(wave):
    import pygame
    if _np is not None:
        arr = _np.clip(_np.asarray(wave, dtype=_np.float32), -1.0, 1.0)
        pcm = (arr * 26000).astype(_np.int16)
        if _CHANNELS >= 2:
            pcm = _np.column_stack((pcm, pcm))
        return pygame.sndarray.make_sound(_np.ascontiguousarray(pcm))
    # no numpy: build a raw buffer by hand
    import array
    buf = array.array("h")
    for x in wave:
        val = int(max(-1.0, min(1.0, x)) * 26000)
        for _ in range(max(1, _CHANNELS)):
            buf.append(val)
    return pygame.mixer.Sound(buffer=buf.tobytes())


def _build():
    """Synthesise the whole vocabulary. Runs on a worker thread."""
    global _ready, RATE, _CHANNELS
    try:
        import pygame
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=RATE, size=-16, channels=2, buffer=1024)
        info = pygame.mixer.get_init()
        if info:
            # main.py pre-inits the mixer; synthesise at ITS rate or every
            # chirp plays at the wrong pitch
            RATE, _CHANNELS = info[0], abs(info[2])
        vocab = _vocabulary()
        made = {}
        for name, wave in vocab.items():
            try:
                snd = _to_sound(wave)
                snd.set_volume(_VOLUME)
                made[name] = snd
            except Exception:
                pass
        with _lock:
            _sounds.update(made)
            _ready = bool(made)
        if _ready and _pending:
            say(_pending, force=True)     # the greeting that was waiting
    except Exception:
        _ready = False        # no audio device: stay silent, stay alive


def init():
    """Kick off synthesis in the background. Safe to call more than once."""
    if not _ENABLED or _ready:
        return
    threading.Thread(target=_build, daemon=True).start()


def say(name, force=False):
    """Utter a phrase. Never blocks, never raises, never chatters."""
    global _last_any
    if not _ENABLED or _muted or not _ready:
        return False
    now = time.time()
    with _lock:
        snd = _sounds.get(name)
        if snd is None:
            return False
        if not force:
            if now - _last_any < MIN_GAP:
                return False
            if now - _last_of.get(name, 0.0) < COOLDOWN:
                return False
        _last_any = now
        _last_of[name] = now
    try:
        snd.play()
        return True
    except Exception:
        return False


def say_any(*names):
    """Pick one of several phrases — keeps repeated events from feeling
    mechanical."""
    return say(random.choice(names))


def say_when_ready(name):
    """For the boot greeting: speak now if the voice is built, otherwise
    the moment it is."""
    global _pending
    if _ready:
        return say(name, force=True)
    _pending = name
    return False


# ── mute control ────────────────────────────────────────────────────────────
def set_muted(flag):
    global _muted
    _muted = bool(flag)
    return _muted


def toggle_mute():
    global _muted
    _muted = not _muted
    if not _muted:
        say("blip", force=True)      # confirm we're back
    return _muted


def is_muted():
    return _muted or not _ENABLED


def is_ready():
    return _ready


def phrase_names():
    return sorted(_vocabulary().keys())
