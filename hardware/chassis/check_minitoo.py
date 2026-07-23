#!/usr/bin/env python3
"""
check_minitoo.py — fit checks for kea_minitoo.scad (no OpenSCAD needed).

Parses the parameters out of the .scad and verifies the geometry that
actually has to fit: the fixed-size display, the reclined screen face,
the keyboard-deck control row, stack depth clearance and bed fit.

    python3 hardware/chassis/check_minitoo.py

Exit 0 = safe to slice.
"""
import math
import os
import re
import sys

BED_X, BED_Y, BED_Z = 220, 220, 250
STACK_W, STACK_L = 56.0, 85.5

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "kea_minitoo.scad"), encoding="utf-8").read()


def p(name):
    m = re.search(rf"^{name}\s*=\s*(-?[\d.]+)\s*;", src, re.M)
    if not m:
        raise SystemExit(f"cannot find parameter {name}")
    return float(m.group(1))


W, D, wall = p("W"), p("D"), p("wall")
front_h, deck_y, deck_z = p("front_h"), p("deck_y"), p("deck_z")
recline, slen, top_cap = p("recline"), p("slen"), p("top_cap")
cut_x = p("cut_x")
btn_d, enc_d, tog_d, btn_dx = p("btn_d"), p("enc_d"), p("tog_d"), p("btn_dx")
btn_row, te_row, tog_x = p("btn_row"), p("te_row"), p("tog_x")
door_z0 = p("door_z0")

r = math.radians(recline)
sy = deck_y + slen * math.sin(r)
sz = deck_z + slen * math.cos(r)
H = sz + top_cap
door_top = H - 10                                # matches `door_top = H - 10` in scad
deck_a = math.degrees(math.atan2(deck_z - front_h, deck_y))
deck_len = math.hypot(deck_y, deck_z - front_h)
enc_x = W - 13
cam_y = (sy + D) / 2

checks, fails = [], []


def chk(name, ok, detail=""):
    checks.append((name, ok, detail))
    if not ok:
        fails.append(name)


print(f"params:  W={W:.0f} D={D:.0f} recline={recline:.0f} slen={slen:.0f}")
print(f"derived: sy={sy:.1f} sz={sz:.1f} H={H:.1f} "
      f"deck_a={deck_a:.1f}° deck_len={deck_len:.1f}\n")

# ── bed ──
chk("one-piece body fits bed", W <= BED_X and D <= BED_Y and H <= BED_Z,
    f"{W:.0f}x{D:.0f}x{H:.0f}")
chk("split halves fit bed (lying on cut face)",
    D + 2 <= BED_X and H + 2 <= BED_Y and (W - cut_x) <= BED_Z,
    f"tallest half {W-cut_x:.0f}")

# ── display on the screen slope ──
chk("slope long enough for display + shelf",
    slen >= 6.5 + STACK_L + 2, f"slope {slen:.0f}, needs {6.5+STACK_L+2:.1f}")
chk("screen cutout inside the slope",
    slen/2 - 75/2 > 2 and slen/2 + 75/2 < slen - 2,
    f"screen spans {slen/2-37.5:.1f}..{slen/2+37.5:.1f} of {slen:.0f}")
gx0 = (W - 56)/2 - 3.5
gx1 = (W + 56)/2 + 0.5
chk("cradle guides straddle the 56 mm stack, inside the walls",
    gx0 >= wall and gx1 + 3 <= W - wall
    and gx0 + 3 <= (W-STACK_W)/2 + 0.6 and gx1 >= (W+STACK_W)/2 - 0.6,
    f"guides x={gx0:.1f}/{gx1:.1f}")

# ── keyboard deck ──
chk("control rows fit on the deck length",
    btn_row + btn_d/2 < deck_len - 2 and te_row - tog_d/2 > 3,
    f"button row ends {btn_row+btn_d/2:.1f} of deck {deck_len:.1f}")
chk("deck angle is keyboard-like (8–24°)", 8 <= deck_a <= 24, f"{deck_a:.1f}°")
chk("controls stay inside the side walls",
    tog_x - tog_d/2 > wall and enc_x + enc_d/2 < W - wall
    and (W/2 + btn_dx) + btn_d/2 < W - wall,
    f"toggle L {tog_x-tog_d/2:.1f}, encoder R {enc_x+enc_d/2:.1f}")
chk("buttons don't overlap each other", btn_dx > btn_d + 1.5,
    f"pitch {btn_dx:.0f} vs button {btn_d:.1f}")

# ── seated stack clears the back wall ──
# top-back corner of a ~25 mm-thick stack leaning on the reclined slope
thick = 25.0
face_top = 6.5 + STACK_L                       # display top along the slope
back_y = deck_y + face_top*math.sin(r) + thick*math.cos(r)
chk("seated stack clears the back wall", back_y < D - wall,
    f"stack back y={back_y:.1f}, inner back {D-wall:.1f}")

# ── flat roof carries the camera pod ──
chk("flat roof deep enough for the camera pod",
    D - sy >= 12 and sy + 2 < cam_y < D - 2,
    f"roof spans {sy:.1f}..{D:.0f} ({D-sy:.1f} deep), pod y={cam_y:.1f}")

# ── back door ──
chk("back door opening clears the seated stack top",
    door_top >= deck_z + face_top*math.cos(r) - 2,
    f"door top {door_top:.1f}, stack top z={deck_z+face_top*math.cos(r):.1f}")
chk("door faceplate fits the back wall",
    (door_z0 + door_top)/2 + (door_top - door_z0 + 12)/2 <= H,
    f"faceplate top {(door_z0+door_top)/2+(door_top-door_z0+12)/2:.1f}, H {H:.1f}")

# ── seam: in the gap between the toggle and the leftmost button ──
blue_x = W/2 - btn_dx
chk("cut plane sits between toggle and the nearest button",
    tog_x + tog_d/2 + 0.7 < cut_x < blue_x - btn_d/2 - 0.7,
    f"cut {cut_x:.0f}, toggle ends {tog_x+tog_d/2:.1f}, button starts {blue_x-btn_d/2:.1f}")

for name, ok, detail in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" +
          (f"  ({detail})" if detail and not ok else ""))
if fails:
    print(f"\n{len(fails)} problem(s) — fix before printing.")
    sys.exit(1)
print(f"\nall {len(checks)} checks passed — safe to slice.")
