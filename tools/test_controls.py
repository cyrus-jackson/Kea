#!/usr/bin/env python3
"""
test_controls.py — prove every control is wired correctly, before Kea.

Covers the whole deck: 5 buttons, 2 toggles and the KY-040 (turn + press).
It reads the pin assignments from src/hardware_input.py, so it always
tests what the software will actually use.

    python3 tools/test_controls.py            # interactive checklist
    python3 tools/test_controls.py --monitor  # raw live levels, no checklist

Ctrl-C to quit. A summary prints on exit showing what was never seen —
that's your list of things still to fix.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

try:
    import RPi.GPIO as GPIO
except ImportError:
    sys.exit("RPi.GPIO not found — run this ON THE PI "
             "(sudo apt install python3-rpi.gpio)")

import hardware_input as hw          # noqa: E402  (pin numbers live here)

BCM2PIN = {2: 3, 3: 5, 4: 7, 14: 8, 15: 10, 17: 11, 18: 12, 27: 13, 22: 15,
           23: 16, 24: 18, 10: 19, 9: 21, 25: 22, 11: 23, 8: 24, 7: 26,
           5: 29, 6: 31, 12: 32, 13: 33, 19: 35, 16: 36, 26: 37, 20: 38, 21: 40}


def phys(bcm):
    return BCM2PIN.get(bcm, "?")


BUTTONS = [(pin, desc) for pin, (_e, desc) in hw.BUTTON_CONFIG.items()]
TOGGLES = [(hw.TOGGLE_PIN, "Toggle A"), (hw.TOGGLE2_PIN, "Toggle B")]
TOGGLES = [(p, n) for p, n in TOGGLES if p >= 0]
ENC = [(hw.ENC_CLK, "CLK"), (hw.ENC_DT, "DT"), (hw.ENC_SW, "SW")]

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
for pin, _ in BUTTONS + TOGGLES + ENC:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
if getattr(hw, "ENC_VCC", -1) >= 0:
    GPIO.setup(hw.ENC_VCC, GPIO.OUT)
    GPIO.output(hw.ENC_VCC, GPIO.HIGH)

print(__doc__)
print("Pins under test (BCM -> physical):")
for pin, desc in BUTTONS:
    print(f"   button   {desc:<22} BCM {pin:<3} pin {phys(pin)}")
for pin, name in TOGGLES:
    print(f"   toggle   {name:<22} BCM {pin:<3} pin {phys(pin)}")
for pin, name in ENC:
    print(f"   encoder  {name:<22} BCM {pin:<3} pin {phys(pin)}")
if getattr(hw, "ENC_VCC", -1) >= 0:
    print(f"   encoder  {'+ (driven HIGH)':<22} BCM {hw.ENC_VCC:<3} "
          f"pin {phys(hw.ENC_VCC)}")
print()

# ── idle sanity: everything should read HIGH untouched ──────────────────────
time.sleep(0.2)
stuck = []
for pin, desc in BUTTONS + TOGGLES:
    if all(GPIO.input(pin) == GPIO.LOW for _ in range(20)):
        stuck.append((pin, desc))
if stuck:
    print("[WARN] these read LOW while untouched — likely shorted to GND,")
    print("       or a toggle simply sitting in its ON position:")
    for pin, desc in stuck:
        print(f"         {desc} (BCM {pin}, pin {phys(pin)})")
    print()
else:
    print("[OK]   every button/toggle idles HIGH.\n")

_QUAD = (0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0)
REST = 0b11

seen = {desc: 0 for _, desc in BUTTONS}
seen.update({n: 0 for _, n in TOGGLES})
seen["encoder CW"] = seen["encoder CCW"] = seen["encoder PRESS"] = 0

prev = {pin: GPIO.HIGH for pin, _ in BUTTONS + TOGGLES}
state = (GPIO.input(hw.ENC_CLK) << 1) | GPIO.input(hw.ENC_DT)
accum = 0
sw_prev = GPIO.HIGH
sw_changed = 0.0
glitches = 0
last_print = 0.0
monitor = "--monitor" in sys.argv

print("Now: press each button, flip each toggle, turn and press the knob.")
print("Every event prints once. Ctrl-C for the summary.\n")

try:
    while True:
        # buttons
        for pin, desc in BUTTONS:
            cur = GPIO.input(pin)
            if cur == GPIO.LOW and prev[pin] == GPIO.HIGH:
                seen[desc] += 1
                print(f"  BUTTON  {desc}   (BCM {pin}, pin {phys(pin)})")
            prev[pin] = cur

        # toggles
        for pin, name in TOGGLES:
            cur = GPIO.input(pin)
            if cur != prev[pin]:
                prev[pin] = cur
                seen[name] += 1
                print(f"  TOGGLE  {name} -> {'ON (to GND)' if cur == 0 else 'OFF'}"
                      f"   (BCM {pin}, pin {phys(pin)})")

        # encoder rotation
        clk, dt = GPIO.input(hw.ENC_CLK), GPIO.input(hw.ENC_DT)
        ns = (clk << 1) | dt
        if ns != state:
            step = _QUAD[(state << 2) | ns]
            if step == 0:
                glitches += 1
            accum += step
            state = ns
            if state == REST and abs(accum) >= 2:
                d = "CW" if accum > 0 else "CCW"
                seen[f"encoder {d}"] += 1
                print(f"  ENCODER {d}")
                accum = 0
            elif state == REST:
                accum = 0

        # encoder press
        sw = GPIO.input(hw.ENC_SW)
        now = time.time()
        if sw != sw_prev and now - sw_changed > 0.05:
            sw_changed = now
            if sw == GPIO.LOW:
                seen["encoder PRESS"] += 1
                print("  ENCODER PRESS")
            sw_prev = sw

        if monitor and now - last_print > 0.5:
            last_print = now
            lv = " ".join(f"{d[:6]}={GPIO.input(p)}" for p, d in BUTTONS)
            sys.stdout.write(f"\r  {lv}  CLK={clk} DT={dt} SW={sw}   ")
            sys.stdout.flush()
        time.sleep(0.001)

except KeyboardInterrupt:
    print("\n\n" + "=" * 58)
    print("SUMMARY")
    print("=" * 58)
    ok = [k for k, v in seen.items() if v]
    missing = [k for k, v in seen.items() if not v]
    for k in ok:
        print(f"  [OK]      {k:<24} {seen[k]}x")
    for k in missing:
        print(f"  [MISSING] {k:<24} never seen")
    if glitches:
        print(f"\n  encoder illegal transitions: {glitches}")
        if glitches > sum(seen[f'encoder {d}'] for d in ('CW', 'CCW')):
            print("  More glitches than detents — the KY-040's '+' pin is")
            print("  probably unpowered. Wire it to 3.3 V (pin 1/17) and run")
            print("  Kea with KEA_ENCODER_VCC=-1, or to pin 32 as-is.")
    if missing:
        print("\n  Anything MISSING is either not wired, on a different pin,")
        print("  or on a pin the display already owns. Check with:")
        print("      python3 tools/check_free_pins.py")
    else:
        print("\n  Every control responded. The deck is wired correctly.")
    GPIO.cleanup()
