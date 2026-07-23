#!/usr/bin/env python3
"""check_retropc.py — fit checks for kea_retropc.scad (no OpenSCAD needed)."""
import math
import os
import re
import sys

BED = 220
STACK_W, STACK_L = 56.0, 85.5
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "kea_retropc.scad"), encoding="utf-8").read()


def p(n):
    m = re.search(rf"^{n}\s*=\s*(-?[\d.]+)\s*;", src, re.M)
    if not m:
        raise SystemExit(f"missing {n}")
    return float(m.group(1))


W, Dc, Hc, wall = p("W"), p("Dc"), p("Hc"), p("wall")
kb_d, turn_y, turn_r, turn_bolt = p("kb_d"), p("turn_y"), p("turn_r"), p("turn_bolt")
btn_d, enc_d, tog_d, btn_dx = p("btn_d"), p("enc_d"), p("tog_d"), p("btn_dx")
kb_btn_row, kb_te_row, tog_x = p("kb_btn_row"), p("kb_te_row"), p("tog_x")
cut_x = p("cut_x")
sv_L, sv_W, sv_screw = p("sv_L"), p("sv_W"), p("sv_screw")
CRADLE_D = 37       # mon_cradle depth (must match scad); STACK+adapter+wedge
GPIO_STACK = 33     # assumed Pi+display+GPIO-adapter thickness
Wm, Dm, recl, slen, mfoot, mcap = p("Wm"), p("Dm"), p("recl"), p("slen"), p("mfoot"), p("mcap")
turret_y = p("turret_y")
fan_sz, fan_holes = p("fan_sz"), p("fan_holes")
mon_pwr_z, mon_pwr_depth = p("mon_pwr_z"), p("mon_pwr_depth")
spk_d = p("spk_d")

r = math.radians(recl)
sym = slen*math.sin(r)
szm = mfoot + slen*math.cos(r)
Hm = szm + mcap
enc_x = W - 24
checks, fails = [], []


def chk(n, ok, d=""):
    checks.append((n, ok, d)); fails.append(n) if not ok else None


print(f"case {W:.0f}x{Dc:.0f}x{Hc:.0f}   monitor {Wm:.0f}x{Dm:.0f}x{Hm:.1f}\n")

# --- bed ---
chk("case fits bed", W <= BED and Dc <= BED and Hc <= BED)
chk("case halves fit bed", Dc+2 <= BED and Hc+6 <= BED)
chk("monitor fits bed", Wm <= BED and Dm <= BED and Hm <= BED, f"{Wm:.0f}x{Dm:.0f}x{Hm:.0f}")

# --- keyboard on the case front top ---
chk("keyboard rows sit in the front (keyboard) zone",
    kb_btn_row + btn_d/2 < kb_d - 3 and kb_te_row - tog_d/2 > 3,
    f"button row ends {kb_btn_row+btn_d/2:.1f} of kb zone {kb_d:.0f}")
chk("keyboard clear of the turntable zone", kb_d + 2 < turn_y - turn_r,
    f"kb ends {kb_d:.0f}, turntable front {turn_y-turn_r:.0f}")
chk("controls inside the case walls",
    tog_x-tog_d/2 > wall and enc_x+enc_d/2 < W-wall and (W/2+btn_dx)+btn_d/2 < W-wall)
chk("buttons don't overlap", btn_dx > btn_d+1.5)

# --- turntable / servo ---
chk("turntable seat fits on the case top", turn_y + turn_r < Dc - wall and turn_y - turn_r > kb_d,
    f"turntable spans {turn_y-turn_r:.0f}..{turn_y+turn_r:.0f} of depth {Dc:.0f}")
chk("SG92R hangs under the top: cavity deep enough + flange holes on the disc",
    Hc - wall >= 25 and sv_screw + 3 < 2*turn_r
    and sv_L + 4 < 2*(turn_r+0.6) and sv_W + 4 < 2*(turn_r+0.6),
    f"cavity {Hc-wall:.0f} (need >=25), flange span {sv_screw:.0f} vs disc {2*turn_r:.0f}")
chk("monitor foot bolt circle fits on the turntable", turn_bolt/2 + 3 < turn_r,
    f"bolt r={turn_bolt/2:.0f}, turntable r={turn_r:.0f}")
chk("monitor foot bolt circle fits under the monitor", turn_bolt + 6 < min(Wm, Dm),
    f"bolt circle {turn_bolt:.0f} vs monitor {min(Wm,Dm):.0f}")

# --- monitor houses the display ---
chk("monitor slope carries the display", slen >= 6.5+STACK_L+2)
chk("screen cutout inside the slope", slen/2-37.5 > 2 and slen/2+37.5 < slen-2)
gx0=(Wm-56)/2-3.5; gx1=(Wm+56)/2+0.5
chk("cradle guides straddle the stack", gx0 >= wall and gx1+3 <= Wm-wall)
thick = GPIO_STACK
back_y = (6.5+STACK_L)*math.sin(r) + thick*math.cos(r)
chk("seated stack (with GPIO adapter) clears the monitor back", back_y < Dm-wall,
    f"stack back {back_y:.1f} vs inner {Dm-wall:.0f}")
chk("cradle deep enough for the GPIO-adapter stack + wedge",
    CRADLE_D >= GPIO_STACK + 2 and CRADLE_D < Dm - wall,
    f"cradle {CRADLE_D:.0f} vs stack {GPIO_STACK:.0f}+wedge, inner {Dm-wall:.0f}")
chk("camera turret on the monitor roof", sym+3 < turret_y < Dm-6, f"roof {sym:.1f}..{Dm:.0f}, turret {turret_y:.0f}")

# --- fan on the monitor back door ---
door_w = Wm - 24
door_h = Hm - mfoot - 16
chk("fan aperture + bolt circle fit the back door",
    fan_sz + 8 < door_w and fan_sz + 8 < door_h,
    f"fan {fan_sz:.0f} (+bolts {fan_holes:.0f}) vs door {door_w:.0f}x{door_h:.0f}")

# --- power inlet now on the monitor side wall (not the case) ---
chk("case has NO power slot (moved to the monitor)",
    "case_power_slot" not in src, "power now enters at the Pi in the monitor")
chk("monitor power slot lands inside the side wall",
    6 < mon_pwr_depth < Dm - 6 and 6 < mfoot + mon_pwr_z < Hm - 6,
    f"slot depth {mon_pwr_depth:.0f}/{Dm:.0f}, z {mfoot+mon_pwr_z:.0f}/{Hm:.0f}")

# --- speaker mount fits the case front ---
chk("speaker + mount ring fit the case front wall",
    spk_d + 5 < Hc - 2 and spk_d + 5 < W - 2*wall,
    f"ring {spk_d+5:.0f} vs front {Hc:.0f}x{W:.0f}")

# --- total height sane on a desk ---
chk("total height reasonable", Hc + 4 + Hm < 210, f"{Hc+4+Hm:.0f} mm tall overall")

# --- case seam ---
chk("case cut plane between toggle and first button",
    tog_x+tog_d/2+0.7 < cut_x < (W/2-btn_dx)-btn_d/2-0.7,
    f"cut {cut_x:.0f}, toggle ends {tog_x+tog_d/2:.1f}, button {(W/2-btn_dx)-btn_d/2:.1f}")

for n, ok, d in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {n}" + (f"  ({d})" if d and not ok else ""))
if fails:
    print(f"\n{len(fails)} problem(s).")
    sys.exit(1)
print(f"\nall {len(checks)} checks passed — safe to slice.")
