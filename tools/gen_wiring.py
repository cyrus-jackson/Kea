#!/usr/bin/env python3
"""
gen_wiring.py — build the wiring sheet FROM THE CODE.

Parses the pin assignments straight out of src/hardware_input.py (and the
backlight pin out of src/backend/settings.py) so the wiring document can
never drift from what the software actually drives.

    python3 tools/gen_wiring.py            # print
    python3 tools/gen_wiring.py > WIRING.md

Re-run it after changing any pin.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW = open(os.path.join(ROOT, "src", "hardware_input.py"), encoding="utf-8").read()
ST = open(os.path.join(ROOT, "src", "backend", "settings.py"), encoding="utf-8").read()

# ── BCM -> physical pin on the 40-way header ────────────────────────────────
BCM2PIN = {
    2: 3, 3: 5, 4: 7, 14: 8, 15: 10, 17: 11, 18: 12, 27: 13, 22: 15, 23: 16,
    24: 18, 10: 19, 9: 21, 25: 22, 11: 23, 8: 24, 7: 26, 0: 27, 1: 28,
    5: 29, 6: 31, 12: 32, 13: 33, 19: 35, 16: 36, 26: 37, 20: 38, 21: 40,
}
GROUND_PINS = [6, 9, 14, 20, 25, 30, 34, 39]
# The ELEGOO 3.5" sits on pins 1-26; only 27-40 stay reachable without a
# stacking header / GPIO extender.
EXPOSED = lambda pin: pin >= 27


def pin_of(bcm):
    return BCM2PIN.get(bcm, "?")


def grab_int(src, name, default=None):
    m = re.search(rf"^{name}\s*=\s*(-?\d+)", src, re.M)
    if m:
        return int(m.group(1))
    m = re.search(rf'{name}\s*=\s*int\(os\.getenv\([^,]+,\s*"(-?\d+)"\)\)', src)
    return int(m.group(1)) if m else default


rows = []           # (signal, bcm, note)

# buttons
block = re.search(r"BUTTON_CONFIG\s*=\s*\{(.*?)\}", HW, re.S).group(1)
for bcm, desc in re.findall(r"(\d+)\s*:\s*\([A-Z_]+,\s*\"([^\"]+)\"\)", block):
    rows.append((f"Button — {desc}", int(bcm), "switch to GND (internal pull-up)"))

# encoder
clk, dt, sw = (int(v) for v in
               re.search(r"ENC_CLK,\s*ENC_DT,\s*ENC_SW\s*=\s*(\d+),\s*(\d+),\s*(\d+)",
                         HW).groups())
rows.append(("Encoder CLK", clk, "KY-040 CLK"))
rows.append(("Encoder DT", dt, "KY-040 DT"))
rows.append(("Encoder SW", sw, "KY-040 SW (shaft press)"))

enc_vcc = grab_int(HW, "ENC_VCC", -1)
if enc_vcc >= 0:
    rows.append(("Encoder + (VCC)", enc_vcc,
                 "DRIVEN HIGH BY THE CODE as a 3.3 V rail — wire KY-040 '+' here"))

# toggle
tog = grab_int(HW, "TOGGLE_PIN")
rows.append(("Toggle (centre pin)", tog, "one outer leg to GND, third unused"))

# optional backlight
bl = grab_int(ST, "BACKLIGHT_PIN", -1)

out = []
w = max(len(r[0]) for r in rows) + 2
out.append("| Signal | BCM | Header pin | Reachable? | Note |")
out.append("|---|---|---|---|---|")
for sig, bcm, note in rows:
    pin = pin_of(bcm)
    reach = "yes" if EXPOSED(pin) else "**needs extender**"
    out.append(f"| {sig} | {bcm} | **{pin}** | {reach} | {note} |")
gnd = ", ".join(str(p) for p in GROUND_PINS if EXPOSED(p))
out.append(f"| Ground (common) | — | {gnd} | yes | every switch's other leg |")

print("\n".join(out))
print()
used = {pin_of(b) for _, b, _ in rows}
free = [p for p in sorted(set(BCM2PIN.values()))
        if EXPOSED(p) and p not in used and p not in GROUND_PINS]
print(f"Pins used on the exposed block (27-40): {sorted(used)}")
print(f"Still free there: {free}   (27 & 28 are reserved for HAT EEPROM)")
if bl >= 0:
    print(f"Backlight PWM enabled on BCM {bl} (pin {pin_of(bl)})")
else:
    print("Backlight PWM: disabled (KEA_BACKLIGHT_PIN unset) — software dimming")
