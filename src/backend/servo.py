"""
servo.py — the PCA9685, driven directly.

Two servos today: channel 0 rotates the monitor, channel 1 raises the
semaphore arm. Fourteen channels spare.

    from backend import servo
    servo.monitor().move_to(90)      # degrees, clamped to real limits
    servo.flag().raise_()            # the arm goes up
    servo.relax_all()                # stop holding, stop drawing current

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
`tools/test_servo.py --jog` and set them in the environment; see
hardware/SERVO_WIRING.md stage 5.

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


def _spec(env, default_ch, default_lo, default_hi):
    """Parse 'channel:min:max' from the environment.

    Limits live in the environment rather than in code because they are a
    property of *your* chassis, not of the software — the angle at which
    the monitor bracket fouls its case is something only the assembled
    machine knows.
    """
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
                 invert=False):
        self.channel = channel
        self.lo = lo
        self.hi = hi
        self.name = name
        self.relax_when_idle = relax
        self.invert = invert
        self.angle = None            # unknown until first commanded
        self._target = None
        self._last_cmd = 0.0
        self._relaxed = True

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

    def centre(self):
        return self.move_to((self.lo + self.hi) / 2.0)

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
                f"{self.lo:.0f}-{self.hi:.0f}deg at {self.angle}>")


# ── Kea's two ───────────────────────────────────────────────────────────────
_MON_CH, _MON_LO, _MON_HI = _spec("KEA_SERVO_MONITOR", 0, 30.0, 150.0)
_FLAG_CH, _FLAG_LO, _FLAG_HI = _spec("KEA_SERVO_FLAG", 1, 10.0, 100.0)

_monitor = None
_flag = None


def monitor():
    """Rotates the monitor. Relaxes when idle — the bracket holds itself."""
    global _monitor
    if _monitor is None:
        _monitor = Servo(_MON_CH, _MON_LO, _MON_HI, "monitor", relax=True)
    return _monitor


def flag():
    """The semaphore arm: up when something is overdue, down when clear."""
    global _flag
    if _flag is None:
        _flag = Servo(_FLAG_CH, _FLAG_LO, _FLAG_HI, "flag", relax=True)
    return _flag


def raise_flag():
    return flag().move_to(_FLAG_HI)


def lower_flag():
    return flag().move_to(_FLAG_LO)


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
