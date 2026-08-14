#!/usr/bin/env python3
"""
check_free_pins.py — which header pins are ACTUALLY free on this Pi?

The GPIO extender makes pins 1-26 reachable, but the display driver still
owns the ones it uses. This asks the running Pi what each pin is doing
instead of guessing from a datasheet, and cross-references the pins Kea
already claims.

Run it ON THE PI:

    python3 tools/check_free_pins.py

Anything reported as ALT0..ALT5 is being used by a peripheral (SPI for the
display, I2C, UART...). "INPUT" with nothing attached is fair game.
"""

import os
import re
import shutil
import subprocess
import sys

BCM2PIN = {
    2: 3, 3: 5, 4: 7, 14: 8, 15: 10, 17: 11, 18: 12, 27: 13, 22: 15, 23: 16,
    24: 18, 10: 19, 9: 21, 25: 22, 11: 23, 8: 24, 7: 26, 0: 27, 1: 28,
    5: 29, 6: 31, 12: 32, 13: 33, 19: 35, 16: 36, 26: 37, 20: 38, 21: 40,
}
PIN2BCM = {v: k for k, v in BCM2PIN.items()}
POWER = {1: "3V3", 17: "3V3", 2: "5V", 4: "5V"}
GND = {6, 9, 14, 20, 25, 30, 34, 39}
RESERVED = {27: "HAT EEPROM (ID_SD)", 28: "HAT EEPROM (ID_SC)"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def kea_pins():
    """Pins Kea's own code claims, read from the source."""
    used = {}
    try:
        hw = open(os.path.join(ROOT, "src", "hardware_input.py"),
                  encoding="utf-8").read()
    except OSError:
        return used
    blk = re.search(r"BUTTON_CONFIG\s*=\s*\{(.*?)\}", hw, re.S)
    if blk:
        for bcm, desc in re.findall(r"(\d+)\s*:\s*\([A-Z_]+,\s*\"([^\"]+)\"\)",
                                    blk.group(1)):
            used[int(bcm)] = desc
    m = re.search(r"ENC_CLK,\s*ENC_DT,\s*ENC_SW\s*=\s*(\d+),\s*(\d+),\s*(\d+)", hw)
    if m:
        for bcm, nm in zip(m.groups(), ("Encoder CLK", "Encoder DT", "Encoder SW")):
            used[int(bcm)] = nm
    m = re.search(r"^TOGGLE_PIN\s*=\s*(\d+)", hw, re.M)
    if m:
        used[int(m.group(1))] = "Toggle"
    m = re.search(r'ENC_VCC\s*=\s*int\(os\.getenv\([^,]+,\s*"(-?\d+)"\)\)', hw)
    if m and int(m.group(1)) >= 0:
        used[int(m.group(1))] = "Encoder + (driven HIGH)"
    return used


def pin_functions():
    """{bcm: function} from raspi-gpio / pinctrl. None if unavailable."""
    for cmd in (["pinctrl", "get"], ["raspi-gpio", "get"]):
        if not shutil.which(cmd[0]):
            continue
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=10).stdout
        except Exception:
            continue
        funcs = {}
        for line in out.splitlines():
            m = re.match(r"\s*(\d+)\s*:?\s*(\w+)", line)
            if not m:
                continue
            bcm = int(m.group(1))
            fm = re.search(r"func\s+(\w+)|\b(a[0-5]|ALT[0-5]|INPUT|OUTPUT|ip|op)\b",
                           line, re.I)
            funcs[bcm] = (fm.group(0) if fm else m.group(2)).upper()
        if funcs:
            return funcs
    return None


def overlays():
    for p in ("/boot/firmware/config.txt", "/boot/config.txt"):
        if os.path.exists(p):
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                return []
            return [l.strip() for l in txt.splitlines()
                    if re.match(r"\s*dt(overlay|param)=", l) and
                    not l.strip().startswith("#")]
    return []


def main():
    ov = overlays()
    print("=== display / peripheral overlays in config.txt ===")
    print("\n".join("  " + o for o in ov) if ov else "  (none found)")
    print()

    funcs = pin_functions()
    if funcs is None:
        print("!! Could not read pin functions (need `pinctrl` or `raspi-gpio`,")
        print("   and this must run ON the Pi). Install with:")
        print("     sudo apt install raspi-gpio")
        print("   Falling back to Kea's own usage only.\n")

    mine = kea_pins()
    print(f"{'Pin':>4} {'BCM':>4}  {'Function':<10} Verdict")
    print("-" * 62)
    free = []
    for pin in range(1, 41):
        if pin in POWER:
            print(f"{pin:>4} {'—':>4}  {POWER[pin]:<10} power — now reachable")
            continue
        if pin in GND:
            print(f"{pin:>4} {'—':>4}  {'GND':<10} ground")
            continue
        bcm = PIN2BCM.get(pin)
        if bcm is None:
            continue
        fn = (funcs or {}).get(bcm, "?")
        if pin in RESERVED:
            verdict = f"RESERVED — {RESERVED[pin]}"
        elif bcm in mine:
            verdict = f"USED BY KEA — {mine[bcm]}"
        elif fn.startswith(("ALT", "A")) and fn not in ("A", ""):
            verdict = "IN USE by a peripheral (display/I2C/UART) — do not use"
        elif fn in ("INPUT", "IP", "OUTPUT", "OP", "?"):
            verdict = "looks free"
            free.append((pin, bcm))
        else:
            verdict = fn
        print(f"{pin:>4} {bcm:>4}  {fn:<10} {verdict}")

    print("\n=== candidates for your extra 2 buttons + 2nd toggle ===")
    if free:
        for pin, bcm in free:
            note = ""
            if bcm in (2, 3):
                note = "  (I2C — save these for the PCA9685)"
            elif bcm in (14, 15):
                note = "  (UART — only if the serial console is disabled)"
            print(f"  pin {pin:>2}  BCM {bcm:>2}{note}")
    else:
        print("  (run on the Pi with raspi-gpio installed to get this list)")
    print("\nDouble-check any candidate by toggling it and watching for display")
    print("glitches before you commit to soldering.")


if __name__ == "__main__":
    sys.exit(main())
