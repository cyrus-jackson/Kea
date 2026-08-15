"""
settings.py — the knobs Kea remembers.

The live preferences, adjusted on the CONSOLE screen with the rotary
encoder and persisted to ~/.kea_settings.json so they survive a reboot:

    brightness   10-100 %   backlight (real on the Pi, simulated elsewhere)
    dwell        3-120 s    how long a screen is held before auto-pilot
                            dispatches the next one
    shoot_every  2-60 s     interval between frames in the camera's
                            AUTO SHOOT mode
    idle_mins    1-60 min   how long Kea sits untouched before it goes
                            back to walking the drift circuit
    aim          -60..60    degrees to swing the monitor either side of
                            its calibrated centre

Nothing here raises: a missing backlight, an unwritable home directory
or a corrupt file all degrade to sane defaults.

    from backend import settings
    settings.get("brightness")        -> int
    settings.adjust("brightness", +1) -> new value (steps, clamped, saved)
"""

import json
import os
import threading

PATH = os.path.join(os.path.expanduser("~"), ".kea_settings.json")

# name -> [default, min, max, step]
SPEC = {
    "brightness": [80, 10, 100, 5],
    "dwell": [15, 3, 120, 1],
    # seconds between frames when the camera's AUTO SHOOT toggle is on
    "shoot_every": [6, 2, 60, 1],
    # minutes untouched before Kea resumes the drift rounds
    "idle_mins": [5, 1, 60, 1],
    # monitor aim, as degrees either side of the calibrated centre. An
    # offset rather than an absolute angle, so it survives recalibration.
    "aim": [0, -60, 60, 5],
}

# Where the Pi exposes the panel backlight. The official DSI panel and most
# DPI/SPI TFT overlays land in one of these; first writable one wins.
BACKLIGHT_PATHS = [
    "/sys/class/backlight/rpi_backlight/brightness",
    "/sys/class/backlight/10-0045/brightness",
    "/sys/class/backlight/soc:backlight/brightness",
]

_lock = threading.Lock()
_values = {k: v[0] for k, v in SPEC.items()}
_loaded = False


def _load():
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in SPEC:
            if k in data:
                _values[k] = _clamp(k, int(data[k]))
    except Exception:
        pass                      # first run, or unreadable: keep defaults


def _save():
    try:
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(_values, f)
    except Exception:
        pass                      # read-only home: run with defaults, no fuss


def _clamp(name, v):
    _d, lo, hi, _s = SPEC[name]
    return max(lo, min(hi, int(v)))


def get(name):
    _load()
    with _lock:
        return _values.get(name, SPEC[name][0])


def fraction(name):
    """0.0-1.0 position of a setting inside its range (for drawing bars)."""
    _d, lo, hi, _s = SPEC[name]
    return (get(name) - lo) / float(hi - lo) if hi > lo else 0.0


def set_value(name, v):
    if name not in SPEC:
        return None
    _load()
    with _lock:
        _values[name] = _clamp(name, v)
        out = _values[name]
        _save()
    if name == "brightness":
        apply_brightness(out)
    return out


def adjust(name, direction):
    """Nudge a setting by one step. `direction` is +1 / -1."""
    if name not in SPEC:
        return None
    step = SPEC[name][3]
    return set_value(name, get(name) + step * (1 if direction > 0 else -1))


# ── backlight ───────────────────────────────────────────────────────────────
_backlight_path = None
_backlight_max = 255


def _find_backlight():
    global _backlight_path, _backlight_max
    if _backlight_path is not None:
        return _backlight_path
    for p in BACKLIGHT_PATHS:
        if os.path.exists(p) and os.access(p, os.W_OK):
            _backlight_path = p
            try:
                with open(os.path.join(os.path.dirname(p), "max_brightness")) as f:
                    _backlight_max = max(1, int(f.read().strip()))
            except Exception:
                _backlight_max = 255
            return p
    _backlight_path = ""          # looked, found nothing — don't look again
    return ""


def has_backlight():
    return bool(_find_backlight())


def apply_brightness(percent=None):
    """Push the brightness to the panel. No panel: silently do nothing
    (main.py then dims in software — see dim_alpha)."""
    pct = get("brightness") if percent is None else percent
    if _pwm is not None:                      # GPIO-PWM backlight
        try:
            _pwm.ChangeDutyCycle(max(1, min(100, pct)))
            return True
        except Exception:
            pass
    p = _find_backlight()
    if not p:
        return False
    try:
        raw = max(1, int(_backlight_max * max(1, min(100, pct)) / 100.0))
        with open(p, "w") as f:
            f.write(str(raw))
        return True
    except Exception:
        return False


# ── software dimming (for panels with no backlight device) ──────────────────
# Most SPI TFTs — the ELEGOO 3.5" included — tie their LED line straight to
# 3V3, so /sys/class/backlight is empty and brightness can't be set in
# hardware. We then dim by veiling the frame in black. It doesn't save power,
# but it does what you actually want at night: a less glaring screen.
# 100 % = no veil; the floor keeps the screen readable at the lowest setting.
MAX_VEIL = 165          # alpha at 10 % brightness


def dim_alpha():
    """0-255 black-veil alpha for the current brightness. 0 = don't draw."""
    if has_backlight() or pwm_active():
        return 0            # real hardware dimming is doing the work
    pct = get("brightness")
    if pct >= 100:
        return 0
    _d, lo, hi, _s = SPEC["brightness"]
    t = (pct - lo) / float(hi - lo)          # 0 at min, 1 at max
    return int(MAX_VEIL * (1.0 - t))


# ── optional: PWM the backlight on a GPIO (if your panel's LED pin is free) ──
# Set KEA_BACKLIGHT_PIN=<BCM> if you wire the display's LED pin to a GPIO
# (through a transistor for anything but a tiny panel). Then brightness is
# real, and the software veil switches itself off.
try:
    BACKLIGHT_PIN = int(os.getenv("KEA_BACKLIGHT_PIN", "-1"))
except ValueError:
    BACKLIGHT_PIN = -1

_pwm = None


def pwm_active():
    return _pwm is not None


def _pwm_init():
    global _pwm
    if BACKLIGHT_PIN < 0 or _pwm is not None:
        return
    try:
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BACKLIGHT_PIN, GPIO.OUT)
        _pwm = GPIO.PWM(BACKLIGHT_PIN, 1000)     # 1 kHz: no visible flicker
        _pwm.start(get("brightness"))
    except Exception:
        _pwm = None


def init():
    """Call once at startup so the saved brightness takes effect."""
    _load()
    _pwm_init()
    apply_brightness()
