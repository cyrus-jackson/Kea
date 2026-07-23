#!/usr/bin/env python3
"""
check_terminal.py — fit checks for kea_terminal.scad (no OpenSCAD needed).
    python3 hardware/chassis/check_terminal.py
Exit 0 = safe to slice.
"""
import math
import os
import re
import sys

BED_X, BED_Y, BED_Z = 220, 220, 250
STACK_W, STACK_L = 56.0, 85.5

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "kea_terminal.scad"), encoding="utf-8").read()


def p(name):
    m = re.search(rf"^{name}\s*=\s*(-?[\d.]+)\s*;", src, re.M)
    if not m:
        raise SystemExit(f"cannot find parameter {name}")
    return float(m.group(1))


W, Db, wall = p("W"), p("Db"), p("wall")
base_h, mon_y0 = p("base_h"), p("mon_y0")
recline, slen, top_cap = p("recline"), p("slen"), p("top_cap")
cut_x = p("cut_x")
btn_d, enc_d, tog_d, btn_dx = p("btn_d"), p("enc_d"), p("tog_d"), p("btn_dx")
btn_row, te_row, tog_x = p("btn_row"), p("te_row"), p("tog_x")
turret_y = p("turret_y")

r = math.radians(recline)
sy = mon_y0 + slen*math.sin(r)
sz = base_h + slen*math.cos(r)
H = sz + top_cap
door_z0 = base_h + 4                    # matches scad
door_top = H - 8                        # matches scad
enc_x = W - 13

checks, fails = [], []


def chk(n, ok, d=""):
    checks.append((n, ok, d))
    if not ok:
        fails.append(n)


print(f"params:  W={W:.0f} Db={Db:.0f} base_h={base_h:.0f} recline={recline:.0f}")
print(f"derived: sy={sy:.1f} sz={sz:.1f} H={H:.1f}\n")

chk("body fits bed", W <= BED_X and Db <= BED_Y and H <= BED_Z, f"{W:.0f}x{Db:.0f}x{H:.0f}")
chk("split halves fit bed", Db+2 <= BED_X and H+2 <= BED_Y and (W-cut_x) <= BED_Z)

# display on the monitor slope
chk("slope carries the display", slen >= 6.5+STACK_L+2, f"slope {slen:.0f}")
chk("screen cutout inside the slope", slen/2-37.5 > 2 and slen/2+37.5 < slen-2)
gx0 = (W-56)/2 - 3.5; gx1 = (W+56)/2 + 0.5
chk("cradle guides straddle the stack", gx0 >= wall and gx1+3 <= W-wall
    and gx0+3 <= (W-STACK_W)/2+0.6 and gx1 >= (W+STACK_W)/2-0.6,
    f"guides {gx0:.1f}/{gx1:.1f}")

# control shelf (base top, depth 0..mon_y0)
chk("control rows fit on the base shelf",
    btn_row+btn_d/2 < mon_y0-2 and te_row-tog_d/2 > 3,
    f"button row ends {btn_row+btn_d/2:.1f} of shelf {mon_y0:.0f}")
chk("controls inside the side walls",
    tog_x-tog_d/2 > wall and enc_x+enc_d/2 < W-wall and (W/2+btn_dx)+btn_d/2 < W-wall)
chk("buttons don't overlap", btn_dx > btn_d+1.5)

# leaning stack clears the monitor back wall
thick = 25.0
back_y = mon_y0 + (6.5+STACK_L)*math.sin(r) + thick*math.cos(r)
chk("seated stack clears the back wall", back_y < Db-wall,
    f"stack back y={back_y:.1f} vs {Db-wall:.1f}")

# speaker grille fits the base front face
chk("speaker grille fits the base front", base_h/2-3 - 9 > wall and base_h/2-3 + 9 < base_h-2,
    f"grille band on base_h {base_h:.0f}")

# camera turret sits on the flat roof
chk("camera turret on the flat roof, behind the screen",
    sy+3 < turret_y < Db-6, f"roof {sy:.1f}..{Db:.0f}, turret y={turret_y:.0f}")

# back door
chk("back door clears the seated stack top",
    door_top >= base_h + (6.5+STACK_L)*math.cos(r) - 2,
    f"door top {door_top:.1f}, stack top {base_h+(6.5+STACK_L)*math.cos(r):.1f}")
chk("door opening starts above the base shelf", door_z0 > base_h,
    f"door_z0 {door_z0:.0f} vs base_h {base_h:.0f}")
chk("door faceplate fits the back wall",
    (door_z0+door_top)/2 + (door_top-door_z0+12)/2 <= H)

# seam
blue_x = W/2 - btn_dx
chk("cut plane between toggle and first button",
    tog_x+tog_d/2+0.7 < cut_x < blue_x-btn_d/2-0.7,
    f"cut {cut_x:.0f}, toggle ends {tog_x+tog_d/2:.1f}, button {blue_x-btn_d/2:.1f}")

for n, ok, d in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {n}" + (f"  ({d})" if d and not ok else ""))
if fails:
    print(f"\n{len(fails)} problem(s).")
    sys.exit(1)
print(f"\nall {len(checks)} checks passed — safe to slice.")
