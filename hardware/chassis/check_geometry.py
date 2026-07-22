#!/usr/bin/env python3
"""
check_geometry.py — sanity-checks kea_chassis.scad before you print.

Parses the parameters straight out of the .scad (so it tracks your
edits, e.g. changing `tilt`), recomputes the derived geometry with the
same formulas, and verifies fit/printability constraints. Run it after
any parameter change:

    python3 hardware/chassis/check_geometry.py

Exit code 0 = safe to slice.
"""

import math
import re
import sys
import os

BED_X, BED_Y, BED_Z = 220, 220, 250          # printer volume
STACK_W, STACK_L = 56.0, 85.5                # display+Pi footprint (portrait)

scad_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "kea_chassis.scad")
src = open(scad_path, encoding="utf-8").read()


def param(name):
    m = re.search(rf"^{name}\s*=\s*(-?[\d.]+)\s*;", src, re.M)
    if not m:
        raise SystemExit(f"cannot find parameter {name} in scad")
    return float(m.group(1))


W, D = param("W"), param("D")
wall = param("wall")
front_h = param("front_h")
deck_y, deck_z = param("deck_y"), param("deck_z")
tilt, slen, marq = param("tilt"), param("slen"), param("marq")
cut_x = param("cut_x")
enc_d, tog_d = param("enc_d"), param("tog_d")
pwr_side, pwr_depth, pwr_z = param("pwr_side"), param("pwr_depth"), param("pwr_z")

sy = deck_y + slen * math.sin(math.radians(tilt))
sz = deck_z + slen * math.cos(math.radians(tilt))
H = sz + marq

checks, failures = [], []


def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    if not ok:
        failures.append(name)


print(f"parameters: tilt={tilt}°  slen={slen}  wall={wall}  W={W} D={D}")
print(f"derived:    sy={sy:.1f}  sz={sz:.1f}  H={H:.1f}\n")

# ── bed fit ──────────────────────────────────────────────────────────────
check("shell halves fit bed (split print, lying on cut face)",
      D + 2 <= BED_X and H + 2 <= BED_Y and (W - cut_x) <= BED_Z,
      f"footprint {D:.0f}x{H:.0f}, tallest half {W - cut_x:.1f}")
check("one-piece shell fits bed (upright)",
      W <= BED_X and D <= BED_Y and H <= BED_Z, f"{W:.0f}x{D:.0f}x{H:.0f}")
door_z0 = param("door_z0")
door_top = H - 7                                 # matches `door_top = H - 7` in scad
door_open_h = door_top - door_z0
door_face_h = door_open_h + 12
door_dz = H - 4                                  # matches `door_dz = H - 4` in scad
check("door fits bed", 102 <= BED_X and door_face_h + 2 <= BED_Y,
      f"faceplate {door_face_h:.0f} tall")

# ── the screen slope must carry the whole stack ──────────────────────────
check("slope long enough for the stack + shelf",
      slen >= 6.5 + STACK_L + 2,
      f"slope {slen}, needs {6.5 + STACK_L + 2:.1f}")
gx0 = (W - 56) / 2 - 3.5                          # left guide (tracks W in scad)
gx1 = (W + 56) / 2 + 0.5                          # right guide
check("cradle guides sit just outside the stack, inside the walls",
      gx0 >= wall and gx0 + 3 <= (W - STACK_W) / 2 + 0.6
      and gx1 >= (W + STACK_W) / 2 - 0.6 and gx1 + 3 <= W - wall,
      f"guides x={gx0:.1f}/{gx1:.1f}, stack x={(W-STACK_W)/2:.1f}-{(W+STACK_W)/2:.1f}")

# ── ribbon slot: shell cut must align with the camstand's own slot ───────
py = (sy + D) / 2                                     # camstand center depth
m = re.search(r"ribbon slot[^\n]*\n(?:\s*//[^\n]*\n)*\s*translate\(\[W/2-12\.5,\s*([^,]+),", src)
shell_slot_expr = m.group(1).strip() if m else "?"
shell_slot_y = eval(shell_slot_expr, {"sy": sy, "D": D})   # noqa: S307 (own file)
stand_slot_y = py - 10.9
check("camera ribbon slot aligns with camstand pass-through",
      abs(shell_slot_y - stand_slot_y) < 0.6,
      f"shell slot y={shell_slot_y:.1f}, camstand slot y={stand_slot_y:.1f} "
      f"(expr: {shell_slot_expr})")
check("ribbon slot inside the flat top", sy + 1 < shell_slot_y
      and shell_slot_y + 4.1 < D - wall, f"top spans {sy:.1f}..{D - wall:.0f}")

# ── camstand sockets in the flat top, clear of the slot ──────────────────
check("camstand sockets inside the flat top",
      sy + 4 < py - 2.75 and py + 2.75 < D - wall, f"sockets at y={py:.1f}")

# ── power slot: inside the side wall, clear of guides and top ────────────
pyg = deck_y + pwr_z * math.sin(math.radians(tilt)) \
    + pwr_depth * math.cos(math.radians(tilt))
pzg = deck_z + pwr_z * math.cos(math.radians(tilt)) \
    - pwr_depth * math.sin(math.radians(tilt))
check("power slot lands inside the side wall",
      10 < pyg < D - 6 and 12 < pzg < H - 8,
      f"slot center global y={pyg:.1f} z={pzg:.1f}")
check("power slot cutter clears the cradle guides",
      19 < gx0, f"cutter reaches x=19, left guide starts x={gx0:.1f}")

# ── door: opening leaves solid rails; dowels in solid wall ───────────────
check("solid rail above door opening for the top dowel",
      door_top + 2 < door_dz and door_dz + 1 < H,
      f"opening top z={door_top:.0f}, dowel z={door_dz:.1f}, wall top {H:.1f}")
check("solid rail below door opening for the bottom dowel",
      6 + 1 < door_z0, f"dowel z=6, opening starts z={door_z0:.0f}")
check("door faceplate fits under the back-wall ceiling",
      (door_z0 + door_top) / 2 + door_face_h / 2 <= H,
      f"faceplate top z={(door_z0 + door_top) / 2 + door_face_h / 2:.1f}, "
      f"wall top {H:.1f}")
stack_top_z = deck_z + (6.5 + STACK_L) * math.cos(math.radians(tilt))
check("raised opening actually clears the seated stack top",
      door_top >= stack_top_z, f"opening top z={door_top:.1f}, "
      f"seated stack top z={stack_top_z:.1f}")
check("front dowel inside front wall", 15 < front_h - 2)
check("top dowel inside the flat top", sy + 2 < py < D - 2)

# ── marquee ──────────────────────────────────────────────────────────────
check("marquee tall enough for the label", marq >= 16)

# ── deck seam: cut plane clear of holes ──────────────────────────────────
tog_x = 14                                        # toggle center (scad)
blue_x = W / 2 - 25                               # leftmost button center (scad)
check("cut plane clear of toggle and blue button",
      tog_x + 6.4 / 2 + 0.7 < cut_x < blue_x - 12.4 / 2 - 0.7,
      f"cut at {cut_x}, toggle ends {tog_x + 3.2:.1f}, "
      f"button starts {blue_x - 6.2:.1f}")

# ── deck controls fit the (narrower) deck ────────────────────────────────
check("encoder + buttons stay inside the side walls",
      tog_x - tog_d / 2 > wall and (W - 14) + enc_d / 2 < W - wall
      and (W / 2 + 25) + 12.4 / 2 < W - wall,
      f"toggle L edge {tog_x - tog_d / 2:.1f}, encoder R edge {(W-14)+enc_d/2:.1f}")

# ── report ───────────────────────────────────────────────────────────────
for name, ok, detail in checks:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail and not ok else ""))

if failures:
    print(f"\n{len(failures)} problem(s) — fix before printing.")
    sys.exit(1)
print(f"\nall {len(checks)} checks passed — safe to slice.")
