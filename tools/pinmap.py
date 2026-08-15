#!/usr/bin/env python3
"""
pinmap.py — what is on every pin of the 40-pin header, right now.

    python3 tools/pinmap.py              # the whole header
    python3 tools/pinmap.py --free       # only what is still available
    python3 tools/pinmap.py --power      # only the power and ground pins

WHY THIS EXISTS

I recommended Pi pin 1 for the PCA9685's VCC without checking that the
rotary encoder's `+` was already there — it is, per hardware/WIRING.md
step 4. Nothing in the repo could have told me otherwise: the GPIO
assignments live in src/hardware_input.py, the power-pin assignments live
in prose in a markdown file, and the display's pins live in the Pi's
config.txt. Three places, none of them a map.

So this builds the map. GPIO assignments are read from the actual source
(so they cannot drift from the code), power-pin consumers come from a
table here, and the display's pins are marked from what the SPI overlay
takes. Run it before suggesting a pin. That is the whole point.

Runs anywhere — it reads source, not hardware. For what the *live* Pi
thinks is in use, run tools/check_free_pins.py on the Pi itself; the two
answer different questions and both are worth having.
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── the physical header ─────────────────────────────────────────────────────
# (physical pin -> BCM number, or a power/ground label)
HEADER = {
    1: "3V3", 2: "5V", 3: 2, 4: "5V", 5: 3, 6: "GND",
    7: 4, 8: 14, 9: "GND", 10: 15, 11: 17, 12: 18,
    13: 27, 14: "GND", 15: 22, 16: 23, 17: "3V3", 18: 24,
    19: 10, 20: "GND", 21: 9, 22: 25, 23: 11, 24: 8,
    25: "GND", 26: 7, 27: "ID_SD", 28: "ID_SC", 29: 5, 30: "GND",
    31: 6, 32: 12, 33: 13, 34: "GND", 35: 19, 36: 16,
    37: 26, 38: 20, 39: "GND", 40: 21,
}
BCM_TO_PIN = {v: k for k, v in HEADER.items() if isinstance(v, int)}

# ── things that are not GPIO assignments and so cannot be parsed ────────────
# Power and ground consumers, documented in hardware/WIRING.md. If you wire
# something to a power pin, add it HERE or the next person gets my mistake.
POWER_USERS = {
    1: "Encoder `+` (KY-040 pull-up rail) — WIRING.md §3",
    17: "PCA9685 VCC — SERVO_WIRING.md  (pin 1 was already taken)",
    9: "PCA9685 GND — SERVO_WIRING.md",
    4: "Fan 5 V — WIRING.md §2 step 5",
    39: "Ground rail for all switches — WIRING.md §2 step 1",
}

# The 3.5" SPI panel. SPI0 is certain; the control pins vary by overlay,
# so they are flagged rather than asserted — confirm with check_free_pins.py
# on the Pi before using any of them.
DISPLAY_CERTAIN = {
    9:  "display SPI0 MISO",
    10: "display SPI0 MOSI",
    11: "display SPI0 SCLK",
    8:  "display SPI0 CE0",
    7:  "display SPI0 CE1",
}
DISPLAY_LIKELY = {
    25: "display DC/RS on most 3.5in overlays",
    17: "touch IRQ on some 3.5in overlays",
    18: "backlight on some 3.5in overlays",
    24: "reset on some 3.5in overlays",
}

# Reserved by function
FUNCTION = {
    2: "I2C SDA — PCA9685",
    3: "I2C SCL — PCA9685",
    14: "UART TX (free if serial console disabled)",
    15: "UART RX (free if serial console disabled)",
}


def parse_assignments():
    """Read the GPIO assignments straight out of hardware_input.py.

    Parsed rather than duplicated, so this map cannot drift away from the
    code the way a hand-maintained table would.
    """
    path = os.path.join(ROOT, "src", "hardware_input.py")
    src = open(path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(
            r"^([A-Z_0-9]+)\s*=\s*_pin\(\s*[\"']([^\"']+)[\"']\s*,\s*(-?\d+)",
            src, re.M):
        name, env, bcm = m.group(1), m.group(2), int(m.group(3))
        if bcm >= 0:
            out[bcm] = (name, env)
    return out


def build():
    """pin -> (status, description). status: free / used / power / reserved."""
    gpio = parse_assignments()
    rows = {}
    for pin, what in HEADER.items():
        if isinstance(what, str):                       # power / ground / ID
            desc = POWER_USERS.get(pin, "")
            rows[pin] = (("power-used" if desc else "power"),
                         what, desc or "available")
            continue
        bcm = what
        if bcm in gpio:
            name, env = gpio[bcm]
            rows[pin] = ("used", f"BCM {bcm}", f"{name}  ({env})")
        elif bcm in DISPLAY_CERTAIN:
            rows[pin] = ("reserved", f"BCM {bcm}", DISPLAY_CERTAIN[bcm])
        elif bcm in FUNCTION:
            rows[pin] = ("reserved", f"BCM {bcm}", FUNCTION[bcm])
        elif bcm in DISPLAY_LIKELY:
            rows[pin] = ("check", f"BCM {bcm}", DISPLAY_LIKELY[bcm])
        else:
            rows[pin] = ("free", f"BCM {bcm}", "available")
    return rows


MARK = {"free": "  ", "used": "**", "reserved": "XX", "check": "??",
        "power": "  ", "power-used": "**"}


def show(rows, only=None):
    print("\n  Kea — 40-pin header\n")
    print("     **used   XX reserved   ?? verify on the Pi   (blank) free\n")
    print(f"  {'':>3} {'':2} {'':<10} {'':<34}   {'':2} {'':<10} {''}")
    for left in range(1, 41, 2):
        right = left + 1
        out = []
        for pin in (left, right):
            st, label, desc = rows[pin]
            if only and st not in only:
                out.append(f"  {'':>2} {'':2} {'':<9} {'':<30}")
                continue
            out.append(f"  {pin:>2} {MARK[st]} {label:<9} {desc[:30]:<30}")
        print(f"{out[0]} |{out[1]}")

    free = [p for p, (st, _l, _d) in rows.items() if st == "free"]
    check = [p for p, (st, _l, _d) in rows.items() if st == "check"]
    print(f"\n  free GPIO pins:      {', '.join(map(str, sorted(free))) or 'none'}")
    print(f"  verify before using: {', '.join(map(str, sorted(check)))}")


def show_power(rows):
    print("\n  Power and ground pins\n")
    for pin in sorted(p for p in HEADER if isinstance(HEADER[p], str)):
        st, label, desc = rows[pin]
        flag = "OCCUPIED" if st == "power-used" else "free"
        print(f"    pin {pin:>2}  {label:<6} {flag:<9} {desc}")
    print("""
  Pins 1 and 17 are the SAME 3.3 V rail — two access points to one
  regulator output, not two supplies. Same for the 5 V pins 2 and 4, and
  for all eight grounds. So "pin 1 is taken" only means that hole is
  full; use the other one.

  Budget: keep the total draw on 3.3 V modest (tens of mA). The encoder's
  pull-ups are well under 1 mA and the PCA9685 is about 10 mA, so both on
  the same rail is not close to a problem.
""")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--free", action="store_true", help="only unused pins")
    ap.add_argument("--power", action="store_true", help="only power/ground")
    args = ap.parse_args()

    rows = build()
    if args.power:
        show_power(rows)
    elif args.free:
        show(rows, only={"free"})
    else:
        show(rows)
        show_power(rows)
    print("  GPIO assignments parsed from src/hardware_input.py — they cannot")
    print("  drift from the code. Power-pin users come from the table in this")
    print("  file: if you wire something to a power pin, add it there.\n")
    print("  On the Pi, cross-check the display's pins with:")
    print("      python3 tools/check_free_pins.py\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
