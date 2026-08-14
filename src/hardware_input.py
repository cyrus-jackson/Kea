"""
hardware_input.py — the control deck.

Three arcade buttons, a KY-040 rotary encoder and a mini ON-ON toggle,
all read straight off the GPIO header and turned into pygame events.

    Blue   BCM 21 (pin 40)   cycle worlds
    Red    BCM 20 (pin 38)   pomodoro
    Green  BCM 26 (pin 37)   annunciator / stamp DONE
    Encoder CLK/DT/SW  BCM 5 / 6 / 16  (pins 29 / 31 / 36)
    Toggle BCM 19 (pin 35)   auto-pilot (or mute — see KEA_TOGGLE_ROLE)

Wiring note: every input uses the Pi's internal pull-up, so each switch
just shorts its pin to ground — no resistors, and the KY-040's + pin can
be left unconnected. Nothing here needs the 5 V rail, which is why the
buttons live on pins 27-40 that the display doesn't cover.

The encoder gets its own 1 kHz polling thread. Reading quadrature at the
30 fps render rate would silently drop steps on any brisk turn; a
detent-boundary decoder on a fast thread catches every click.
"""

import os
import threading
import time

import pygame

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    print("WARNING: RPi.GPIO not found. Hardware controls will not be active.")

# ── events ──────────────────────────────────────────────────────────────────
BUTTON_AMBIENT_EVENT = pygame.USEREVENT + 1
BUTTON_POMODORO_EVENT = pygame.USEREVENT + 2
BUTTON_NOTIFICATION_EVENT = pygame.USEREVENT + 3
ENCODER_TURN_EVENT = pygame.USEREVENT + 4     # .direction = +1 / -1
ENCODER_PRESS_EVENT = pygame.USEREVENT + 5
TOGGLE_EVENT = pygame.USEREVENT + 6           # .on = True / False
BUTTON_HOME_EVENT = pygame.USEREVENT + 7      # 4th button: straight to Nexus
BUTTON_CONSOLE_EVENT = pygame.USEREVENT + 8   # 5th button: the Console screen
TOGGLE2_EVENT = pygame.USEREVENT + 9          # 2nd toggle, .on = True / False


def _pin(name, default):
    """Pin numbers are env-overridable: run tools/check_free_pins.py, then
    set e.g. KEA_BTN_MENU=22 if the default clashes on your Pi."""
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# ── pins (BCM) ──────────────────────────────────────────────────────────────
# The first three + the encoder + toggle A live on pins 27-40, which the
# display leaves exposed. The last two buttons and toggle B need the GPIO
# extender — their defaults are pins an SPI 3.5" panel usually leaves alone,
# but CONFIRM with tools/check_free_pins.py before soldering.
BTN_BLUE    = _pin("KEA_BTN_BLUE", 21)     # pin 40  — exposed
BTN_RED     = _pin("KEA_BTN_RED", 20)      # pin 38  — exposed
BTN_GREEN   = _pin("KEA_BTN_GREEN", 26)    # pin 37  — exposed
BTN_HOME    = _pin("KEA_BTN_HOME", 13)     # pin 33  — exposed, the last free one
BTN_CONSOLE = _pin("KEA_BTN_CONSOLE", 4)   # pin 7   — needs the extender

BUTTON_CONFIG = {
    BTN_BLUE:    (BUTTON_AMBIENT_EVENT, "Blue (Cycle)"),
    BTN_RED:     (BUTTON_POMODORO_EVENT, "Red (Pomodoro)"),
    BTN_GREEN:   (BUTTON_NOTIFICATION_EVENT, "Green (Annunciator)"),
    BTN_HOME:    (BUTTON_HOME_EVENT, "Home (Nexus)"),
    BTN_CONSOLE: (BUTTON_CONSOLE_EVENT, "Console (Settings)"),
}
if len(BUTTON_CONFIG) != 5:
    print("WARNING: two buttons share a pin — check your KEA_BTN_* settings; "
          f"got {sorted(BUTTON_CONFIG)}")

ENC_CLK = _pin("KEA_ENC_CLK", 5)           # pin 29
ENC_DT = _pin("KEA_ENC_DT", 6)             # pin 31
ENC_SW = _pin("KEA_ENC_SW", 16)            # pin 36
TOGGLE_PIN = _pin("KEA_TOGGLE_PIN", 19)    # pin 35 — exposed
TOGGLE2_PIN = _pin("KEA_TOGGLE2_PIN", 27)  # pin 13 — needs the extender

# The KY-040's + pin powers its onboard 10k pull-ups, and MUST be supplied:
# left floating, grounding one data line drags the others to ~1 V — inside
# the Pi's undefined band — which reads as a phantom press on every detent.
#
# With the GPIO extender fitted, wire + to REAL 3.3 V (pin 1 or 17). That's
# stiffer than a GPIO and costs no pins, so it's the default: -1 means "the
# code doesn't drive any pin; you supplied + from the 3.3 V rail".
# No extender? Set KEA_ENCODER_VCC=12 and wire + to pin 32 instead — the
# code will then drive that pin HIGH as a stand-in rail.
try:
    ENC_VCC = int(os.getenv("KEA_ENCODER_VCC", "-1"))
except ValueError:
    ENC_VCC = -1

# What toggle A does when a screen doesn't claim it: "autopilot"|"mute"|"none"
TOGGLE_ROLE = os.getenv("KEA_TOGGLE_ROLE", "autopilot").strip().lower()
# Toggle B is global and screens never claim it. Default: mute Kea's voice.
TOGGLE2_ROLE = os.getenv("KEA_TOGGLE2_ROLE", "mute").strip().lower()
TOGGLE2_INVERT = os.getenv("KEA_TOGGLE2_INVERT", "0").strip().lower() in {"1", "true", "on"}
TOGGLE2_ENABLED = os.getenv("KEA_TOGGLE2", "1").strip().lower() not in {"0", "false", "off"}
# Which way is "on". Set 1 if the switch ends up backwards once it's
# nutted into the deck — cheaper than unsoldering the ground leg.
TOGGLE_INVERT = os.getenv("KEA_TOGGLE_INVERT", "0").strip().lower() in {"1", "true", "on"}
# Set 0 if you haven't wired the encoder/toggle yet (floating pins are noisy)
ENC_ENABLED = os.getenv("KEA_ENCODER", "1").strip().lower() not in {"0", "false", "off"}
TOGGLE_ENABLED = os.getenv("KEA_TOGGLE", "1").strip().lower() not in {"0", "false", "off"}

# Quadrature: index by (previous << 2) | current, where state = CLK<<1 | DT.
# Non-zero entries are valid single-step transitions; 0 means no movement
# or an illegal jump (contact bounce), which we simply ignore.
_QUAD = (0, -1, 1, 0,
         1, 0, 0, -1,
         -1, 0, 0, 1,
         0, 1, -1, 0)
_REST = 0b11              # both lines high = sitting in a detent


def _post(event_type, **kw):
    try:
        pygame.event.post(pygame.event.Event(event_type, **kw))
    except Exception:
        pass              # queue full or display gone: never take the app down


class HardwareButtons:
    """Polls the deck. Buttons and toggle on the render loop; the encoder
    on its own fast thread."""

    def __init__(self):
        self.previous_states = {}
        self.toggle_on = False
        self.toggle2_on = False
        self._enc_thread = None
        self._stop = threading.Event()
        # The encoder thread only DECODES; it queues results here and the
        # main thread posts them. pygame.event.post() can fail silently off
        # the main thread, which makes a perfectly decoded turn vanish.
        self._pending = []
        self._plock = threading.Lock()

        if not HAS_GPIO:
            return

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        for pin, (_event, _desc) in BUTTON_CONFIG.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.previous_states[pin] = GPIO.HIGH

        if TOGGLE_ENABLED:
            GPIO.setup(TOGGLE_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            # switch shorted to ground = engaged (unless inverted)
            self.toggle_on = (GPIO.input(TOGGLE_PIN) == GPIO.LOW) != TOGGLE_INVERT
            self.previous_states[TOGGLE_PIN] = GPIO.input(TOGGLE_PIN)

        if TOGGLE2_ENABLED and TOGGLE2_PIN >= 0:
            GPIO.setup(TOGGLE2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.toggle2_on = (GPIO.input(TOGGLE2_PIN) == GPIO.LOW) != TOGGLE2_INVERT
            self.previous_states[TOGGLE2_PIN] = GPIO.input(TOGGLE2_PIN)

        if ENC_ENABLED:
            if ENC_VCC >= 0:
                # stand-in 3.3 V rail for the KY-040's pull-ups
                GPIO.setup(ENC_VCC, GPIO.OUT)
                GPIO.output(ENC_VCC, GPIO.HIGH)
            for pin in (ENC_CLK, ENC_DT, ENC_SW):
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._enc_thread = threading.Thread(target=self._encoder_loop,
                                                daemon=True)
            self._enc_thread.start()

    # ══════════════════════════════════════════════════════════════════════
    def _queue(self, event_type, **kw):
        """Called from the encoder thread: record, don't post."""
        with self._plock:
            self._pending.append((event_type, kw))

    def _encoder_loop(self):
        """1 kHz quadrature decode. Emits one event per detent, in the
        direction the knob actually moved."""
        state = (GPIO.input(ENC_CLK) << 1) | GPIO.input(ENC_DT)
        accum = 0
        sw_prev = GPIO.HIGH
        sw_changed = 0.0

        while not self._stop.is_set():
            try:
                new_state = (GPIO.input(ENC_CLK) << 1) | GPIO.input(ENC_DT)
                if new_state != state:
                    accum += _QUAD[(state << 2) | new_state]
                    state = new_state
                    # a detent is complete when we settle back at rest with
                    # a consistent direction behind us
                    if state == _REST and abs(accum) >= 2:
                        self._queue(ENCODER_TURN_EVENT,
                                    direction=1 if accum > 0 else -1)
                        accum = 0
                    elif state == _REST:
                        accum = 0          # bounced without completing

                # encoder push-button, debounced
                sw = GPIO.input(ENC_SW)
                now = time.time()
                if sw != sw_prev and now - sw_changed > 0.05:
                    sw_changed = now
                    if sw == GPIO.LOW:
                        self._queue(ENCODER_PRESS_EVENT)
                    sw_prev = sw
            except Exception:
                pass
            time.sleep(0.001)

    # ══════════════════════════════════════════════════════════════════════
    def update(self):
        """Poll buttons and the toggle. Called once per frame."""
        if not HAS_GPIO:
            return

        # post whatever the encoder thread decoded, from THIS thread
        with self._plock:
            pending, self._pending = self._pending, []
        for event_type, kw in pending:
            _post(event_type, **kw)

        for pin, (event_type, desc) in BUTTON_CONFIG.items():
            current = GPIO.input(pin)
            if current == GPIO.LOW and self.previous_states[pin] == GPIO.HIGH:
                print(f"Hardware button pressed: {desc}")
                _post(event_type)
            self.previous_states[pin] = current

        if TOGGLE_ENABLED:
            current = GPIO.input(TOGGLE_PIN)
            if current != self.previous_states.get(TOGGLE_PIN):
                self.previous_states[TOGGLE_PIN] = current
                self.toggle_on = (current == GPIO.LOW) != TOGGLE_INVERT
                print(f"Toggle A -> {'ON' if self.toggle_on else 'OFF'}")
                _post(TOGGLE_EVENT, on=self.toggle_on)

        if TOGGLE2_ENABLED and TOGGLE2_PIN >= 0:
            current = GPIO.input(TOGGLE2_PIN)
            if current != self.previous_states.get(TOGGLE2_PIN):
                self.previous_states[TOGGLE2_PIN] = current
                self.toggle2_on = (current == GPIO.LOW) != TOGGLE2_INVERT
                print(f"Toggle B -> {'ON' if self.toggle2_on else 'OFF'}")
                _post(TOGGLE2_EVENT, on=self.toggle2_on)

    def cleanup(self):
        self._stop.set()
        if self._enc_thread is not None:
            self._enc_thread.join(timeout=0.5)
        if HAS_GPIO:
            GPIO.cleanup()
