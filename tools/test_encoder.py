#!/usr/bin/env python3
"""
test_encoder.py — prove the KY-040 and toggle are wired correctly.

Run this on the Pi BEFORE launching Kea. It shows the raw pin levels
live, decodes detents, and warns about the one failure mode that bites
on this build (see the note about the + pin below).

    python3 tools/test_encoder.py

Turn the knob slowly one click at a time. You should see exactly one
CW or CCW per click and the REST line should read 1 1 between clicks.

Then press the knob (its shaft switch is the SW pin) and flip the
toggle. A PRESS on its own is correct; a PRESS that drags a stray CW
or CCW along with it means the board's SW pull-up is dragging the
floating + rail down — same cure as below, desolder the pull-ups.

Ctrl-C to quit.
"""

import sys
import time

try:
    import RPi.GPIO as GPIO
except ImportError:
    sys.exit("RPi.GPIO not found — run this on the Pi "
             "(sudo apt install python3-rpi.gpio)")

CLK, DT, SW, TOGGLE = 5, 6, 16, 19

_QUAD = (0, -1, 1, 0,
         1, 0, 0, -1,
         -1, 0, 0, 1,
         0, 1, -1, 0)
REST = 0b11

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
for pin in (CLK, DT, SW, TOGGLE):
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print(__doc__)
print(f"CLK=BCM{CLK} (pin 29)   DT=BCM{DT} (pin 31)   "
      f"SW=BCM{SW} (pin 36)   TOGGLE=BCM{TOGGLE} (pin 35)\n")

# ── idle sanity check: both data lines must sit HIGH when untouched ────────
time.sleep(0.2)
idle = [(GPIO.input(CLK), GPIO.input(DT)) for _ in range(50)]
stable = all(x == (1, 1) for x in idle)
if stable:
    print("[OK]   CLK and DT idle HIGH and steady — wiring looks good.\n")
else:
    lows = sum(1 for c, d in idle if c == 0 or d == 0)
    print(f"[WARN] CLK/DT are NOT resting HIGH ({lows}/50 samples low).")
    print("       Don't turn the knob during this check. If the knob was")
    print("       still and you still see this, your KY-040's onboard")
    print("       pull-ups are fighting the Pi's because the + pin is")
    print("       floating. Fix: connect + to 3.3V (pin 1 or 17), or")
    print("       desolder R1/R2 on the KY-040 board.\n")

state = (GPIO.input(CLK) << 1) | GPIO.input(DT)
accum = 0
detents = 0
sw_prev = GPIO.HIGH
tg_prev = GPIO.input(TOGGLE)
bad = 0
last_print = 0.0

# Short-detection: if SW simply mirrors DT (or CLK) while you turn, the
# two lines are the same electrical node — a shared breadboard row, a
# solder bridge, or a jumper on the wrong pad. Symptom is a PRESS on
# every detent without touching the knob.
samples = 0
sw_eq_dt = 0
sw_eq_clk = 0
warned_short = False
toggle_moved = False

try:
    while True:
        clk, dt = GPIO.input(CLK), GPIO.input(DT)
        ns = (clk << 1) | dt
        if ns != state:
            step = _QUAD[(state << 2) | ns]
            if step == 0:
                bad += 1            # illegal jump = bounce or missed sample
            accum += step
            state = ns
            if state == REST and abs(accum) >= 2:
                detents += 1
                print(f"  {'CW  ->' if accum > 0 else 'CCW <-'}   "
                      f"detent #{detents}")
                accum = 0
            elif state == REST:
                accum = 0

        sw = GPIO.input(SW)
        if sw != sw_prev:
            sw_prev = sw
            if sw == GPIO.LOW:
                print("  PRESS")

        tg = GPIO.input(TOGGLE)
        if tg != tg_prev:
            tg_prev = tg
            toggle_moved = True
            print(f"  TOGGLE -> {'ON (shorted to GND)' if tg == 0 else 'OFF'}")

        # correlate SW against the data lines while the knob is moving
        samples += 1
        if sw == dt:
            sw_eq_dt += 1
        if sw == clk:
            sw_eq_clk += 1
        if not warned_short and detents >= 3 and samples > 400:
            if sw_eq_dt / samples > 0.98:
                warned_short = True
                print("\n[FAULT] SW mirrors DT exactly — those two pins are "
                      "the same node.\n        Check that the SW jumper is on "
                      "its own breadboard row and\n        lands on the SW pad "
                      "(GPIO16 / pin 36), not DT.\n")
            elif sw_eq_clk / samples > 0.98:
                warned_short = True
                print("\n[FAULT] SW mirrors CLK exactly — those two pins are "
                      "the same node.\n        Check the SW jumper's row and "
                      "pad (GPIO16 / pin 36).\n")

        now = time.time()
        if now - last_print > 0.5:
            last_print = now
            sys.stdout.write(f"\r  live: CLK={clk} DT={dt} SW={sw} TG={tg}   "
                             f"detents={detents} glitches={bad}   ")
            sys.stdout.flush()
        time.sleep(0.001)
except KeyboardInterrupt:
    print(f"\n\n{detents} detents, {bad} illegal transitions.")
    if detents and bad > detents:
        print("More glitches than detents — see the + pin note above.")
    if samples and sw_eq_dt / samples > 0.98 and detents >= 3:
        print("SW mirrored DT for the whole run: those pins are shorted.")
    if not toggle_moved:
        print(f"Toggle never changed (stayed {'LOW/ON' if tg_prev == 0 else 'HIGH/OFF'})"
              " — flip it during the test to confirm it works.")
    GPIO.cleanup()
