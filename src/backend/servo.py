"""
servo.py — the PCA9685, driven directly.

Two servos today: channel 0 rotates the monitor, channel 1 raises the
semaphore arm. Fourteen channels spare.

    from backend import servo
    servo.monitor().go("centre")     # to the calibrated centre
    servo.monitor().go("left")       # to the calibrated left stop
    servo.flag().go("up")            # the arm goes up
    servo.relax_all()                # stop holding, stop drawing current

CALIBRATION

Left, centre and right are *measured*, not computed, and live in
~/.kea_servos.json. Capture them by hand:

    python3 tools/test_servo.py --calibrate --channel 0

**Centre is not the midpoint.** A servo horn mounts on splines, so it
lands at whatever angle the teeth allow — "monitor facing you" might be
92 deg in a 35-148 deg range. Anything that computes centre as
(lo + hi) / 2 will be wrong by however far the horn happened to sit,
which is why the centre is stored as its own number.

NO DEPENDENCY STACK

This talks to the chip's registers over I²C rather than pulling in
Blinka and CircuitPython, which is a large install on a Pi 3B+ for what
amounts to twelve register writes. `python3-smbus` is one apt package and
already present on Raspberry Pi OS. Off a Pi there is a synthetic
backend, so the smoke test and desk development still work — the same
approach backend/camera.py takes.

THE TWO THINGS THAT PROTECT THE HARDWARE

**Travel limits.** Every channel has a min and max angle and every
command is clamped to them. A servo driven into its mechanical end stop
does not stop — it stalls, drawing full stall current continuously,
heating up and flattening a 4×AA pack in minutes. The limits are the
difference between a servo that lasts and one that cooks. Find them with
`tools/test_servo.py --calibrate`, which measures them and saves them;
see hardware/SERVO_WIRING.md stage 5.

**Idle relax.** A servo holding position still draws current, and a
cheap one hunts audibly around its target forever. After RELAX_AFTER
seconds of not being asked to move, the PWM pulse is cut entirely: the
servo goes limp, silent, and draws essentially nothing. For a monitor
that holds its own angle by friction and a flag that rests on a stop,
that is exactly right. Set relax=False on a channel that must actively
hold a load.

WIRING

See hardware/SERVO_WIRING.md. The short version: VCC to Pi 3.3 V (never
5 V — the I²C pull-ups go to VCC and GPIO 2/3 are 3.3 V-only), V+ to the
battery, and the grounds joined.
"""

import json
import os
import threading
import time

# ── PCA9685 registers ───────────────────────────────────────────────────────
MODE1 = 0x00
MODE2 = 0x01
PRESCALE = 0xFE
LED0_ON_L = 0x06
ALL_LED_ON_L = 0xFA

MODE1_RESTART = 0x80
MODE1_AI = 0x20          # auto-increment, so we can write 4 bytes at once
MODE1_SLEEP = 0x10
MODE1_ALLCALL = 0x01
MODE2_OUTDRV = 0x04      # totem-pole output

OSC_HZ = 25_000_000.0    # the chip's internal oscillator
FREQ = 50                # servos want 50 Hz — a 20 ms frame

# SG92R pulse widths. 500-2400 us is the usual full span for this class of
# micro servo; the *angle* limits below are what actually keep it safe, so
# these stay wide and the clamping happens in degrees.
PULSE_MIN_US = 500
PULSE_MAX_US = 2400
SPAN_DEG = 180.0

RELAX_AFTER = 1.2        # seconds of stillness before the pulse is cut
STEP_DEG = 3.0           # per tick when moving smoothly
TICK = 0.02

ADDR = int(os.getenv("KEA_PCA9685_ADDR", "0x40"), 0)
BUS_N = int(os.getenv("KEA_I2C_BUS", "1"))

# Where the measured positions live. Written by tools/test_servo.py
# --calibrate; a property of this chassis, so it does not belong in code.
CALIB_PATH = os.path.join(os.path.expanduser("~"), ".kea_servos.json")


def load_calibration():
    """Everything measured so far. Never raises — no file is normal."""
    try:
        with open(CALIB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:                             # noqa: BLE001
        return {}


def save_calibration(name, channel, positions):
    """Merge one servo's measured positions into the file.

    Merged rather than overwritten so calibrating the monitor never wipes
    the flag — the two are done in separate sittings, hours apart, and
    losing the first one to the second would be a nasty surprise.
    """
    data = load_calibration()
    entry = dict(data.get(name, {}))
    entry["channel"] = channel
    entry.update({k: round(float(v), 1) for k, v in positions.items()
                  if v is not None})
    data[name] = entry
    tmp = CALIB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, CALIB_PATH)                   # atomic: no half-written file
    return data[name]


def derive(centre, span):
    """(left, centre, right) from a centre and a total travel.

    This is the way round that matches the mechanism. You do not really
    know where the left stop is; you know where "facing me" is, and how
    far it should swing. So centre is measured and the extremes fall out
    of it, symmetrically, and widening the span moves both at once.

    Clamped to the servo's absolute range, so a span wider than the
    hardware allows truncates rather than commanding past the ends.
    """
    half = max(0.0, float(span)) / 2.0
    return (max(0.0, centre - half), float(centre),
            min(SPAN_DEG, centre + half))


def _spec(env, default_ch, default_lo, default_hi):
    """Parse 'channel:min:max' from the environment."""
    raw = os.getenv(env, "")
    ch, lo, hi = default_ch, default_lo, default_hi
    if raw:
        parts = raw.split(":")
        try:
            if len(parts) >= 1 and parts[0] != "":
                ch = int(parts[0])
            if len(parts) >= 3:
                lo, hi = float(parts[1]), float(parts[2])
        except ValueError:
            pass                      # a typo costs the default, not a crash
    if lo > hi:
        lo, hi = hi, lo
    return ch, max(0.0, lo), min(SPAN_DEG, hi)


def resolve(name, env, default_ch, default_lo, default_hi, labels):
    """Where one servo's numbers come from, and in what order.

    ENV BEATS THE CALIBRATION FILE. That is the same rule as everywhere
    else in Kea (KEA_CAM_AUTO_SECS beats the Console dial, KEA_IDLE_MINS
    beats the IDLE dial), and a consistent rule you can state in one
    sentence is worth more than a cleverer one you cannot.

    The trap it creates — you calibrate, an old env var in the service
    file silently wins, and the servo does not go where you just told it
    — is handled by tools/test_servo.py, which refuses to save quietly
    into that situation and says exactly which variable to unset.
    """
    cal = load_calibration().get(name, {})
    ch = int(cal.get("channel", default_ch))
    pos = {k: float(cal[k]) for k in labels if k in cal}

    lo = min(pos.values()) if pos else default_lo
    hi = max(pos.values()) if pos else default_hi
    centre = pos.get(labels[1], (lo + hi) / 2.0)
    source = "calibration" if pos else "default"

    if os.getenv(env):
        ch, lo, hi = _spec(env, ch, lo, hi)
        centre = max(lo, min(hi, centre))
        source = "env"
    return ch, lo, hi, centre, pos, source


class _Synthetic:
    """Off-Pi stand-in. Records what would have been sent."""

    def __init__(self):
        self.writes = []
        self.available = False
        self.error = "no I2C bus (not a Pi?)"

    def set_pwm(self, ch, on, off):
        self.writes.append((ch, on, off))

    def close(self):
        pass


class _Bus:
    """The real chip. Nothing here is clever; it is twelve register writes."""

    def __init__(self, addr=ADDR, bus_n=BUS_N):
        self.available = False
        self.error = None
        self.addr = addr
        self._bus = None
        try:
            try:
                import smbus2 as smbus          # noqa: F401
            except ImportError:
                import smbus                    # noqa: F401
            self._smbus = smbus
            self._bus = smbus.SMBus(bus_n)
            self._init_chip()
            self.available = True
        except FileNotFoundError:
            self.error = f"/dev/i2c-{bus_n} missing — enable I2C in raspi-config"
        except ImportError:
            self.error = "python3-smbus not installed (sudo apt install python3-smbus)"
        except OSError as exc:
            self.error = f"no PCA9685 at {hex(addr)} ({exc.__class__.__name__})"
        except Exception as exc:                # noqa: BLE001
            self.error = f"{type(exc).__name__}: {exc}"

    def _w(self, reg, val):
        self._bus.write_byte_data(self.addr, reg, val & 0xFF)

    def _r(self, reg):
        return self._bus.read_byte_data(self.addr, reg)

    def _init_chip(self):
        self._w(MODE1, 0x00)
        self._w(MODE2, MODE2_OUTDRV)
        time.sleep(0.005)
        self.set_freq(FREQ)

    def set_freq(self, hz):
        """The prescaler can only be written while the chip is asleep —
        that is a hardware requirement, not a nicety."""
        prescale = int(round(OSC_HZ / (4096.0 * hz)) - 1)
        prescale = max(3, min(255, prescale))
        old = self._r(MODE1)
        self._w(MODE1, (old & 0x7F) | MODE1_SLEEP)
        self._w(PRESCALE, prescale)
        self._w(MODE1, old)
        time.sleep(0.005)
        self._w(MODE1, old | MODE1_RESTART | MODE1_AI | MODE1_ALLCALL)

    def set_pwm(self, ch, on, off):
        base = LED0_ON_L + 4 * ch
        self._bus.write_i2c_block_data(self.addr, base, [
            on & 0xFF, (on >> 8) & 0x0F, off & 0xFF, (off >> 8) & 0x0F])

    def close(self):
        try:
            if self._bus is not None:
                self._bus.close()
        except Exception:                       # noqa: BLE001
            pass


_bus = None
_bus_lock = threading.Lock()


def bus():
    """The shared board. Built once, never raises."""
    global _bus
    with _bus_lock:
        if _bus is None:
            b = _Bus()
            _bus = b if b.available else _Synthetic()
            if not b.available and b.error:
                _bus.error = b.error
        return _bus


def available():
    return bool(getattr(bus(), "available", False))


def error():
    return getattr(bus(), "error", None)


class Servo:
    """One channel, clamped to what your chassis can actually do."""

    def __init__(self, channel, lo, hi, name="servo", relax=True,
                 invert=False, centre_deg=None, positions=None,
                 labels=("left", "centre", "right"), source="default"):
        self.channel = channel
        self.lo = lo
        self.hi = hi
        self.name = name
        self.relax_when_idle = relax
        self.invert = invert
        self.labels = labels
        self.source = source          # default / calibration / env
        # Measured positions. centre is stored, never derived: a horn
        # mounts on splines and lands where the teeth allow, so the real
        # centre is rarely halfway between the ends.
        self.positions = dict(positions or {})
        self.centre_deg = (centre_deg if centre_deg is not None
                           else (lo + hi) / 2.0)
        self.positions.setdefault(labels[1], self.centre_deg)
        self.angle = None            # unknown until first commanded
        self._target = None
        self._last_cmd = 0.0
        self._relaxed = True

    @property
    def calibrated(self):
        """True once all three positions have actually been measured."""
        return all(k in self.positions for k in self.labels)

    # ── the guard rail ─────────────────────────────────────────────────
    def clamp(self, deg):
        """Every command goes through here. This is the whole safety story:
        a servo cannot be asked to go somewhere it physically cannot."""
        return max(self.lo, min(self.hi, float(deg)))

    def _ticks(self, deg):
        if self.invert:
            deg = SPAN_DEG - deg
        us = PULSE_MIN_US + (PULSE_MAX_US - PULSE_MIN_US) * (deg / SPAN_DEG)
        # 4096 steps across a 1/FREQ second frame
        return int(round(us * 4096.0 * FREQ / 1_000_000.0))

    # ── commands ───────────────────────────────────────────────────────
    def write(self, deg):
        """Send one position immediately. Clamped."""
        deg = self.clamp(deg)
        try:
            bus().set_pwm(self.channel, 0, self._ticks(deg))
        except Exception:                       # noqa: BLE001
            return self.angle                   # a dead bus is not a crash
        self.angle = deg
        self._last_cmd = time.time()
        self._relaxed = False
        return deg

    def move_to(self, deg, speed=STEP_DEG):
        """Walk to a position rather than jumping.

        A jump makes the servo slam at full speed, which on a monitor
        bracket is both alarming and hard on the gears — and the current
        spike is the worst thing you can do to an alkaline pack.
        """
        deg = self.clamp(deg)
        if self.angle is None:
            return self.write(deg)
        while abs(self.angle - deg) > 0.5:
            step = min(speed, abs(deg - self.angle))
            self.write(self.angle + (step if deg > self.angle else -step))
            time.sleep(TICK)
        return self.write(deg)

    def go(self, where, speed=STEP_DEG):
        """Move to a named position: "left" / "centre" / "right"
        (or "down" / "rest" / "up" on the flag)."""
        if where not in self.positions:
            raise KeyError(f"{self.name} has no position {where!r}; "
                           f"known: {sorted(self.positions)}")
        return self.move_to(self.positions[where], speed=speed)

    def centre(self, speed=STEP_DEG):
        """The measured centre, not the midpoint of the range."""
        return self.move_to(self.centre_deg, speed=speed)

    def set_span(self, span):
        """Set total travel about the measured centre, deriving both ends.

        Fine-tuning one end afterwards with set_position() is allowed and
        simply makes the travel asymmetric — some mechanisms are.
        """
        left, centre, right = derive(self.centre_deg, span)
        self.positions[self.labels[0]] = left
        self.positions[self.labels[2]] = right
        self.lo, self.hi = left, right
        return left, right

    @property
    def span(self):
        """Total travel between the two extremes, in degrees."""
        a = self.positions.get(self.labels[0])
        b = self.positions.get(self.labels[2])
        return abs(b - a) if (a is not None and b is not None) else 0.0

    def set_position(self, where, deg):
        """Record a measured position and widen the limits to include it.

        Calibration is the one time the limits are allowed to grow: they
        exist to stop *later* commands exceeding what you measured, not
        to stop you measuring it.

        Marking the centre re-derives both extremes around the new centre,
        keeping the span you already chose — moving the middle should
        carry the ends with it, not leave them stranded.
        """
        deg = max(0.0, min(SPAN_DEG, float(deg)))
        if where == self.labels[1]:
            old_span = self.span
            self.centre_deg = deg
            self.positions[where] = deg
            if old_span > 0:
                self.set_span(old_span)
                return deg
        self.positions[where] = deg
        self.lo = min(self.lo, deg)
        self.hi = max(self.hi, deg)
        return deg

    def save(self):
        """Persist to ~/.kea_servos.json.

        Both the derived extremes and the span are written: the extremes
        so loading needs no maths, the span so a later session can widen
        the travel without re-finding the centre.
        """
        out = {k: self.positions.get(k) for k in self.labels}
        out["span"] = round(self.span, 1)
        return save_calibration(self.name, self.channel, out)

    def relax(self):
        """Cut the pulse. The servo goes limp and stops drawing current.

        Bit 4 of the OFF_H register is the chip's 'full off' flag, which
        stops the output entirely rather than sending a 0-width pulse.
        """
        try:
            base = LED0_ON_L + 4 * self.channel
            b = bus()
            if hasattr(b, "_bus") and b._bus is not None:
                b._bus.write_i2c_block_data(b.addr, base, [0, 0, 0, 0x10])
            else:
                b.set_pwm(self.channel, 0, 0)
        except Exception:                       # noqa: BLE001
            pass
        self._relaxed = True

    def update(self, now=None):
        """Call periodically. Relaxes the channel once it has been still
        long enough. Safe to call every frame."""
        if not self.relax_when_idle or self._relaxed:
            return
        now = now or time.time()
        if now - self._last_cmd >= RELAX_AFTER:
            self.relax()

    def __repr__(self):
        return (f"<Servo {self.name} ch{self.channel} "
                f"{self.lo:.0f}-{self.hi:.0f}deg centre {self.centre_deg:.0f} "
                f"[{self.source}] at {self.angle}>")


# ── Kea's two ───────────────────────────────────────────────────────────────
# The flag's three positions are the same idea under different names: a
# semaphore arm has down / rest / up rather than left / centre / right.
MONITOR_LABELS = ("left", "centre", "right")
FLAG_LABELS = ("down", "rest", "up")

_monitor = None
_flag = None


def monitor():
    """Rotates the monitor. Relaxes when idle — the bracket holds itself."""
    global _monitor
    if _monitor is None:
        ch, lo, hi, c, pos, src = resolve(
            "monitor", "KEA_SERVO_MONITOR", 0, 30.0, 150.0, MONITOR_LABELS)
        _monitor = Servo(ch, lo, hi, "monitor", relax=True, centre_deg=c,
                         positions=pos, labels=MONITOR_LABELS, source=src)
    return _monitor


def flag():
    """The semaphore arm: up when something is overdue, down when clear."""
    global _flag
    if _flag is None:
        ch, lo, hi, c, pos, src = resolve(
            "flag", "KEA_SERVO_FLAG", 1, 10.0, 100.0, FLAG_LABELS)
        _flag = Servo(ch, lo, hi, "flag", relax=True, centre_deg=c,
                      positions=pos, labels=FLAG_LABELS, source=src)
    return _flag


def reload():
    """Drop the cached servos so a fresh calibration takes effect."""
    global _monitor, _flag
    _monitor = _flag = None


def raise_flag():
    f = flag()
    return f.go("up") if "up" in f.positions else f.move_to(f.hi)


def lower_flag():
    f = flag()
    return f.go("down") if "down" in f.positions else f.move_to(f.lo)


def all_servos():
    return [monitor(), flag()]


def update(now=None):
    """Tick every servo's idle timer. Cheap; call it from the main loop."""
    for sv in all_servos():
        sv.update(now)


def relax_all():
    """Everything limp. Call on shutdown — leaving a servo powered and
    holding is how a pack is flat by morning."""
    for sv in all_servos():
        sv.relax()


def shutdown():
    relax_all()
    try:
        bus().close()
    except Exception:                           # noqa: BLE001
        pass
