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

# ── pins (BCM) ──────────────────────────────────────────────────────────────
BUTTON_CONFIG = {
    21: (BUTTON_AMBIENT_EVENT, "Blue (Cycle)"),
    20: (BUTTON_POMODORO_EVENT, "Red (Pomodoro)"),
    26: (BUTTON_NOTIFICATION_EVENT, "Green (Annunciator)"),
}
ENC_CLK, ENC_DT, ENC_SW = 5, 6, 16
TOGGLE_PIN = 19

# The KY-040's + pin powers its onboard 10k pull-ups. Pins 27-40 carry no
# 3.3 V rail, and leaving + floating makes those pull-ups couple the data
# lines to each other through it (ground DT and SW sags to ~1.1 V, inside
# the Pi's undefined band, so it reads as a phantom button press).
# The pull-ups draw well under 1 mA total, so a spare GPIO driven HIGH is
# a perfectly good 3.3 V supply — GPIO12 (pin 32) sits right next to the
# encoder's pins. Set KEA_ENCODER_VCC=-1 if you power + some other way.
try:
    ENC_VCC = int(os.getenv("KEA_ENCODER_VCC", "12"))
except ValueError:
    ENC_VCC = 12

# What the physical toggle does: "autopilot" | "mute" | "none"
TOGGLE_ROLE = os.getenv("KEA_TOGGLE_ROLE", "autopilot").strip().lower()
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
        self._enc_thread = None
        self._stop = threading.Event()

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
                        _post(ENCODER_TURN_EVENT,
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
                        _post(ENCODER_PRESS_EVENT)
                    sw_prev = sw
            except Exception:
                pass
            time.sleep(0.001)

    # ══════════════════════════════════════════════════════════════════════
    def update(self):
        """Poll buttons and the toggle. Called once per frame."""
        if not HAS_GPIO:
            return

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
                print(f"Toggle -> {'ON' if self.toggle_on else 'OFF'}")
                _post(TOGGLE_EVENT, on=self.toggle_on)

    def cleanup(self):
        self._stop.set()
        if self._enc_thread is not None:
            self._enc_thread.join(timeout=0.5)
        if HAS_GPIO:
            GPIO.cleanup()
