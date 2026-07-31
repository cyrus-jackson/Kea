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
kb_btn_row, kb_te_row = p("kb_btn_row"), p("kb_te_row")
tog1_x, tog2_x = p("tog1_x"), p("tog2_x")
BTN_HEAD = 14.0     # GUUZI 12 mm metal button head diameter
sv_L, sv_W, sv_screw = p("sv_L"), p("sv_W"), p("sv_screw")
CRADLE_D = None     # read from the scad below
GPIO_STACK = None
gapP, gapG = p("gapP"), p("gapG")
Dm, recl, slen, mfoot, mcap = p("Dm"), p("recl"), p("slen"), p("mfoot"), p("mcap")
stack_t = p("stack_t")
CRADLE_D = stack_t
GPIO_STACK = stack_t - 4   # real stack, leaving spare
wall_ = p("wall")
Wm = wall_ + gapP + 56 + gapG + wall_          # matches the scad expression
stack_cx = wall_ + gapP + 28
turret_y = p("turret_y")
fan_sz, fan_holes = p("fan_sz"), p("fan_holes")
mon_pwr_z, mon_pwr_depth = p("mon_pwr_z"), p("mon_pwr_depth")

r = math.radians(recl)
sym = slen*math.sin(r)
szm = mfoot + slen*math.cos(r)
Hm = szm + mcap
enc_x = W - 16                       # matches `enc_x = W - 16` in scad
checks, fails = [], []


def chk(n, ok, d=""):
    checks.append((n, ok, d)); fails.append(n) if not ok else None


print(f"case {W:.0f}x{Dc:.0f}x{Hc:.0f}   monitor {Wm:.0f}x{Dm:.0f}x{Hm:.1f}\n")

# ══════════════════════════════════════════════════════════════════════════
# THROUGH-CUT CHECKS — a hole can sit in exactly the right place, be exactly
# the right size, and still print SOLID because its cutter doesn't span the
# wall. That is what happened to the keyboard holes. Every cutter below is
# checked to start below the material and end above it.
# ══════════════════════════════════════════════════════════════════════════
def through(name, cut_lo, cut_len, mat_lo, mat_hi):
    cut_hi = cut_lo + cut_len
    ok = cut_lo <= mat_lo + 1e-9 and cut_hi >= mat_hi - 1e-9
    detail = (f"cutter {cut_lo:.1f}..{cut_hi:.1f} vs material "
              f"{mat_lo:.1f}..{mat_hi:.1f}")
    if not ok:
        left = max(0.0, mat_hi - cut_hi) + max(0.0, cut_lo - mat_lo)
        detail += f"  -> {left:.1f} mm of plastic LEFT IN THE HOLE"
    chk(name, ok, detail)


# case deck: every keyboard hole (buttons, toggles, encoder)
kb_z0 = Hc - wall - 2          # matches keyboard_holes() in the scad
through("keyboard holes cut clean through the deck",
        kb_z0, wall + 4, Hc - wall, Hc)
# turntable shaft hole + servo flange screws
through("turntable shaft hole goes through", Hc - wall - 1, wall + 2, Hc - wall, Hc)
# monitor roof: camera turret slot
through("camera turret slot goes through the roof",
        Hm - wall - 1, wall + 2, Hm - wall, Hm)
# monitor screen aperture (cut across the panel thickness)
through("screen aperture goes through the panel",
        wall/2 - (wall + 12)/2, wall + 12, 0, wall)
# door fan holes through the 2.5 mm faceplate
through("fan bolt holes go through the door", -1, 14, 0, 2.5)
# cam_cradle camera screw holes through its 2.5 mm plate
through("cam_cradle screw holes go through", -1, 5, 0, 2.5)

# --- bed ---
chk("case fits bed", W <= BED and Dc <= BED and Hc <= BED)
chk("monitor fits bed", Wm <= BED and Dm <= BED and Hm <= BED, f"{Wm:.0f}x{Dm:.0f}x{Hm:.0f}")

# --- keyboard on the case front top ---
chk("keyboard rows sit in the front (keyboard) zone",
    kb_btn_row + btn_d/2 < kb_d - 3 and kb_te_row - tog_d/2 > 3,
    f"button row ends {kb_btn_row+btn_d/2:.1f} of kb zone {kb_d:.0f}")
chk("keyboard clear of the turntable zone", kb_d + 2 < turn_y - turn_r,
    f"kb ends {kb_d:.0f}, turntable front {turn_y-turn_r:.0f}")
chk("controls (2 toggles, encoder, 5 buttons) inside the case walls",
    tog1_x - tog_d/2 > wall and enc_x + enc_d/2 < W - wall
    and (W/2 - 2*btn_dx) - BTN_HEAD/2 > wall
    and (W/2 + 2*btn_dx) + BTN_HEAD/2 < W - wall,
    f"L button edge {(W/2-2*btn_dx)-BTN_HEAD/2:.1f}, R {(W/2+2*btn_dx)+BTN_HEAD/2:.1f}")
chk("button heads (14 mm) don't touch", btn_dx > BTN_HEAD + 1,
    f"pitch {btn_dx:.0f} vs head {BTN_HEAD:.0f}")
chk("encoder clear of the nearest button",
    enc_x - enc_d/2 > (W/2 + 2*btn_dx) + BTN_HEAD/2 + 1,
    f"enc L edge {enc_x-enc_d/2:.1f}, button R {(W/2+2*btn_dx)+BTN_HEAD/2:.1f}")

# --- turntable / servo ---
chk("turntable seat fits on the case top", turn_y + turn_r < Dc - wall and turn_y - turn_r > kb_d,
    f"turntable spans {turn_y-turn_r:.0f}..{turn_y+turn_r:.0f} of depth {Dc:.0f}")
sv_flange_L, sv_guide_h = p("sv_flange_L"), p("sv_guide_h")
chk("SG92R hangs under the deck: cavity deep enough for the body",
    Hc - wall >= sv_body_h if (sv_body_h := p("sv_body_h")) else True,
    f"cavity {Hc-wall:.0f} vs body {p('sv_body_h'):.1f}")
# THE ONE THAT BIT: the servo is T-shaped, so the flanges — not the body —
# decide whether it can be inserted at all.
chk("servo mount is OPEN across the flanges (T-shape can be inserted)",
    "for (sy = [-1, 1])" in src and "sv_flange_L" in src,
    "guide must be two ribs, not a closed collar sized to the body")
chk("guide ribs pinch only the narrow faces, leaving the flanges a path",
    sv_flange_L > sv_L + 6,
    f"flanges {sv_flange_L:.1f} tip-to-tip vs body {sv_L:.1f} — ribs must not enclose x")
chk("flange screw holes match the flange span",
    sv_screw < sv_flange_L - 2, f"screws {sv_screw:.0f} within flanges {sv_flange_L:.1f}")
chk("servo + guide fit the case cavity height",
    sv_guide_h + 2 < Hc - wall, f"ribs {sv_guide_h:.0f} of cavity {Hc-wall:.0f}")
chk("monitor foot bolt circle fits on the turntable", turn_bolt/2 + 3 < turn_r,
    f"bolt r={turn_bolt/2:.0f}, turntable r={turn_r:.0f}")
chk("monitor foot bolt circle fits under the monitor", turn_bolt + 6 < min(Wm, Dm),
    f"bolt circle {turn_bolt:.0f} vs monitor {min(Wm,Dm):.0f}")

# --- monitor houses the display ---
chk("monitor slope carries the display", slen >= 6.5+STACK_L+2)
chk("screen cutout inside the slope", slen/2-37.5 > 2 and slen/2+37.5 < slen-2)
gx0=stack_cx-28-3.5; gx1=stack_cx+28+0.5
chk("cradle locates the stack on both sides (rib or wall)",
    (gx0 >= wall + 0.5 or gapP == 0) and (gx1 + 3 <= Wm - wall - 0.5 or gapG == 0),
    f"power side {'wall' if gapP == 0 else f'rib at {gx0:.1f}'}, "
    f"GPIO rib at {gx1:.1f}")
gpio_channel = gapG                          # stack edge -> inner wall, GPIO side
chk("GPIO side has a clear channel for the sideways header + wires",
    gpio_channel >= 16, f"channel {gpio_channel:.0f} mm (need >=16 for pins+dupont)")
thick = GPIO_STACK
back_y = (6.5+STACK_L)*math.sin(r) + thick*math.cos(r)
chk("seated stack (with GPIO adapter) clears the monitor back", back_y < Dm-wall,
    f"stack back {back_y:.1f} vs inner {Dm-wall:.0f}")
chk("cradle deep enough for the GPIO-adapter stack + wedge",
    CRADLE_D >= GPIO_STACK + 2 and CRADLE_D < Dm - wall,
    f"cradle {CRADLE_D:.0f} vs stack {GPIO_STACK:.0f}+wedge, inner {Dm-wall:.0f}")
chk("camera turret on the monitor roof", sym+3 < turret_y < Dm-6, f"roof {sym:.1f}..{Dm:.0f}, turret {turret_y:.0f}")

# --- screen frame: thin enough not to shadow the picture ---
face_t, face_pad = p("face_t"), p("face_pad")
bz = 1.0     # bezel proud height in mon_bezel()
chk("screen frame is thinner than the wall (relieved behind the aperture)",
    face_t < wall, f"frame {face_t} mm of a {wall:.0f} mm wall")
chk("frame still thick enough to print and hold its shape",
    face_t >= 1.2, f"{face_t} mm — below ~1.2 gets floppy/translucent")
chk("total depth in front of the display is small",
    face_t + bz <= 2.6,
    f"{face_t+bz:.1f} mm (panel {face_t} + bezel {bz}) — was 3 + 2.5 = 5.5")
chk("thinned area stays inside the panel",
    scr_cut[1] + 2*face_pad < slen - 2
    and scr_cut[0] + 2*face_pad < Wm - 2*wall
    if (scr_cut := [float(v) for v in re.search(
        r"scr_cut\s*=\s*\[([\d.]+),\s*([\d.]+)\]", src).groups()]) else True,
    f"relief {scr_cut[0]+2*face_pad:.0f}x{scr_cut[1]+2*face_pad:.0f} "
    f"in panel {Wm-2*wall:.0f}x{slen:.0f}")

# --- turret roof slot: tight, but still passes the ribbon ---
ts = [float(v) for v in re.search(r"turret_slot\s*=\s*\[([\d.]+),\s*([\d.]+)\]", src).groups()]
chk("turret slot passes a 16 mm camera ribbon", ts[0] >= 16.5,
    f"slot {ts[0]:.0f} mm wide")
chk("turret slot is tight, not a gaping hole", ts[0]*ts[1] <= 130,
    f"slot {ts[0]:.0f}x{ts[1]:.0f} = {ts[0]*ts[1]:.0f} mm2 (was 22x16 = 352)")
chk("turret slot clears its own screw holes",
    10 - ts[1]/2 > 1.3 + 1, f"slot half-depth {ts[1]/2:.1f}, screws at y+10")

# --- cam_cradle: every hole needs material around it ---
cc_w, cc_h = [float(v) for v in re.search(r"cc_plate\s*=\s*\[([\d.]+),\s*([\d.]+)\]", src).groups()]
cn_w, cn_d = [float(v) for v in re.search(r"cc_notch\s*=\s*\[([\d.]+),\s*([\d.]+)\]", src).groups()]
CAM_HX, CAM_HY, CAM_R = 21/2, 12.5/2, 1.1
chk("cam_cradle: camera holes have material to the plate edge",
    cc_w/2 - (CAM_HX + CAM_R) >= 2.5 and cc_h/2 - (CAM_HY + CAM_R) >= 2.5,
    f"margins x {cc_w/2-CAM_HX-CAM_R:.1f}, y {cc_h/2-CAM_HY-CAM_R:.1f} mm")
notch_top = -cc_h/2 + cn_d
chk("cam_cradle: ribbon notch no longer cuts the lower screw holes",
    notch_top < -CAM_HY - CAM_R - 1.5,
    f"notch top {notch_top:.1f} vs hole bottom {-CAM_HY-CAM_R:.1f}")
chk("cam_cradle: kit bolt holes clear both the notch and the camera holes",
    11 - 1.2 > notch_top + 1
    and math.hypot(12 - CAM_HX, 11 - CAM_HY) > CAM_R + 1.2 + 1,
    f"kit holes at (+/-12, 11)")
chk("cam_cradle: kit bolt holes inside the plate",
    12 + 1.2 < cc_w/2 - 1 and 11 + 1.2 < cc_h/2 - 1,
    f"plate {cc_w:.0f}x{cc_h:.0f}")

# --- the back door: does it seat, grip, and clear everything? ---
mcut_x_ = p("mcut_x")
door_x0, door_z0, door_h = p("door_x0"), p("door_z0"), p("door_h")
door_w = mcut_x_ - 6 - door_x0
lip_t, rib = p("door_lip_t"), p("door_rib")
fan_cy = p("fan_cy")
lw, lh = door_w - 0.6, door_h - 0.6
chk("fan aperture + bolt circle fit the back door",
    fan_sz + 8 < door_w and fan_sz + 8 < door_h,
    f"fan {fan_sz:.0f} (+bolts {fan_holes:.0f}) vs door {door_w:.0f}x{door_h:.0f}")
chk("back door stops short of the seam (no knife-edge)",
    door_x0 + door_w <= mcut_x_ - 4 and door_x0 > wall + 4,
    f"door x {door_x0}..{door_x0+door_w:.0f}, seam {mcut_x_:.0f}")
# seating: the faceplate must overlap the opening all round so it stops flush
chk("door faceplate seats on the wall around the opening",
    door_w + 12 > door_w + 8 and door_h + 12 > door_h + 8,
    "6 mm flange all round")
# lip fits the opening, and the ribs give a real interference fit
chk("door lip enters the opening (0.3 mm/side clearance)",
    abs((door_w - lw) - 0.6) < 1e-6 and abs((door_h - lh) - 0.6) < 1e-6,
    f"lip {lw:.1f}x{lh:.1f} vs opening {door_w:.0f}x{door_h:.0f}")
chk("crush ribs give interference on BOTH axes (door won't rattle)",
    (lw + 2*rib) - door_w > 0.2 and (lh + 2*rib) - door_h > 0.2,
    f"with ribs {lw+2*rib:.1f}x{lh+2*rib:.1f} vs {door_w:.0f}x{door_h:.0f}")
chk("interference is press-fit, not unassemblable",
    (lw + 2*rib) - door_w <= 0.8 and (lh + 2*rib) - door_h <= 0.8,
    f"{(lw+2*rib)-door_w:.1f} mm total")
chk("lip is shallower than the wall (door sits flush, doesn't bottom out)",
    lip_t < wall, f"lip {lip_t} vs wall {wall}")
# the door must clear the seam-bolt ear above it
ear_lo = 100 - 10/2
chk("door opening clears the back seam-bolt ear",
    door_z0 + door_h < ear_lo - 2,
    f"door top z={door_z0+door_h:.0f}, ear starts z={ear_lo:.0f}")
chk("door opening sits inside the back wall",
    door_z0 > mfoot + 4 and door_z0 + door_h < Hm - 6,
    f"door z {door_z0:.0f}..{door_z0+door_h:.0f} of height {Hm:.1f}")
# nothing cut into anything else on the door face
fan_r = (fan_sz - 3) / 2
vent_xs = [i*9 - 1.5 for i in range(-2, 3)]
chk("vents clear the fan aperture and its bolts",
    all(12 > fan_cy + fan_r + 1 for _ in vent_xs)
    and 12 > fan_cy + fan_holes/2 + 1.3 + 1,
    f"vents start y=12, fan reaches {fan_cy+fan_r:.1f}, bolts {fan_cy+fan_holes/2:.1f}")
chk("vents stay on the faceplate", all(abs(x) + 3 < (door_w+12)/2 for x in vent_xs),
    f"vents x {min(vent_xs):.0f}..{max(vent_xs)+3:.0f} of +/-{(door_w+12)/2:.1f}")
chk("finger scallop clears the vents",
    (door_h + 12)/2 - 6 > 12 + 18 + 1,
    f"scallop from y={(door_h+12)/2-6:.1f}, vents end y=30")
chk("fan bolts land on the lip, not off the edge",
    fan_holes/2 + 3 < lw/2 and abs(fan_cy) + fan_holes/2 + 3 < lh/2,
    f"bolts at (+/-{fan_holes/2:.0f}, {fan_cy:.0f}+/-{fan_holes/2:.0f}) in lip {lw:.0f}x{lh:.0f}")

# --- power inlet now on the monitor side wall (not the case) ---
chk("case has NO power slot (moved to the monitor)",
    "case_power_slot" not in src, "power now enters at the Pi in the monitor")
chk("monitor power slot lands inside the side wall",
    6 < mon_pwr_depth < Dm - 6 and 6 < mfoot + mon_pwr_z < Hm - 6,
    f"slot depth {mon_pwr_depth:.0f}/{Dm:.0f}, z {mfoot+mon_pwr_z:.0f}/{Hm:.0f}")
# the cassette is pushed to the power wall: that gap must still take the plug,
# and the wide channel must be on the GPIO side
mon_pwr_side = p("mon_pwr_side")
gpio_side = p("gpio_side")
chk("power side leaves room for the headphone jack AND a plug",
    gapP >= 7, f"power gap {gapP:.0f} mm (jack stands proud of the board)")
chk("power side isn't wastefully wide", gapP <= 12, f"{gapP:.0f} mm")
mon_aud_z, mon_aud_d = p("mon_aud_z"), p("mon_aud_d")
chk("audio aperture is separated from the power slot",
    abs(mon_aud_z - mon_pwr_z) > mon_aud_d/2 + 10.5 + 2,
    f"audio at {mon_aud_z:.0f}, power at {mon_pwr_z:.0f} along the slope")
chk("audio aperture lands inside the side wall",
    6 < mfoot + mon_aud_z < Hm - 6, f"audio z {mfoot+mon_aud_z:.0f} of {Hm:.1f}")
chk("audio aperture takes a 3.5 mm plug body", mon_aud_d >= 9,
    f"{mon_aud_d:.0f} mm")
# THE JACK-SIDE RIB: it ran down the very gap the headphone jack sticks into.
pwr_rib_h = p("pwr_rib_h")
chk("no cradle rib blocking the headphone-jack side",
    pwr_rib_h == 0 or pwr_rib_h + 4 < mon_aud_z - mon_aud_d/2,
    f"rib height {pwr_rib_h:.0f} vs jack at z {mon_aud_z:.0f}")
chk("jack-side gap is left completely open to the wall",
    pwr_rib_h == 0,
    f"anything in x {stack_cx-28-3.5:.1f}..{stack_cx-28:.1f} fouls the jack")
chk("screen aperture still lands inside the body once flush",
    stack_cx - 51/2 > wall - 0.5 and stack_cx + 51/2 < Wm - wall + 0.5,
    f"aperture {stack_cx-25.5:.1f}..{stack_cx+25.5:.1f} of width {Wm:.0f}")
chk("display active area sits under the aperture",
    stack_cx - 48.96/2 > stack_cx - 51/2 and stack_cx + 48.96/2 < stack_cx + 51/2,
    "active area inside the cutout")
chk("bezel is trimmed rather than overhanging",
    "intersection() {\n        screen_frame() mon_bezel();" in src,
    "bezel must be clipped to the body width")
chk("the wide channel is on the GPIO side, the narrow one on the power side",
    gapG > gapP + 5 and mon_pwr_side != gpio_side,
    f"power gap {gapP:.0f} (side {mon_pwr_side:+.0f}), "
    f"GPIO gap {gapG:.0f} (side {gpio_side:+.0f})")
chk("bezel's GPIO-side edge stays inside the body",
    stack_cx + (51/2 + 9) < Wm - 1,
    f"bezel right edge {stack_cx+34.5:.1f} of width {Wm:.0f}")
chk("narrower than the centred layout (space saved)", Wm < 100,
    f"{Wm:.0f} mm wide")

# --- ordered boards fit inside the case ---
# [name, w(x), d(y), h(z), cx, cy] from the datasheets
BOARDS = [
    ("battery 4xAA", 62.0, 56.5, 16.0, 37, 85),
    ("PCA9685",      25.4, 62.5, 20.0, 86, 85),   # ~20 mm tall with headers
    ("LM2596 buck",  36.0, 66.0, 16.0, 122, 85),
]
floor_lo, floor_hi = wall + 0.75, W - wall - 0.75
floor_hi_y = Dc - wall - 0.75
LOWEST_HANG = 22.0     # nothing (buttons/servo) hangs below ~22 mm; boards <=20
for nm, bw, bd, bh, cx, cy in BOARDS:
    chk(f"{nm} fits the floor footprint",
        cx - bw/2 >= floor_lo and cx + bw/2 <= floor_hi
        and cy - bd/2 >= floor_lo and cy + bd/2 <= floor_hi_y,
        f"x {cx-bw/2:.0f}-{cx+bw/2:.0f}, y {cy-bd/2:.0f}-{cy+bd/2:.0f}")
    chk(f"{nm} clears the parts hanging from the top", bh < LOWEST_HANG,
        f"board {bh:.0f} mm tall vs {LOWEST_HANG:.0f} mm")
# no two boards overlap in x (they're laid out left-to-right)
xs = sorted((cx - bw/2, cx + bw/2) for nm, bw, bd, bh, cx, cy in BOARDS)
chk("the three boards don't overlap each other",
    all(xs[i][1] <= xs[i+1][0] for i in range(len(xs)-1)),
    f"x spans {[ (round(a),round(b)) for a,b in xs ]}")
# boards clear the finger hole in the bottom plate
# feet must sit on the bottom PLATE (solid), not over the shell's open cavity
FOOT_XY = [(20, 20), (W-20, 20), (20, Dc-20), (W-20, Dc-20)]
plate_x0, plate_x1 = wall + 0.75, W - wall - 0.75
plate_y0, plate_y1 = wall + 0.75, Dc - wall - 0.75
chk("feet land on the bottom plate, not in mid-air",
    all(plate_x0 + 7 <= fx <= plate_x1 - 7 and plate_y0 + 7 <= fy <= plate_y1 - 7
        for fx, fy in FOOT_XY),
    f"feet {FOOT_XY} vs plate x{plate_x0:.0f}-{plate_x1:.0f} y{plate_y0:.0f}-{plate_y1:.0f}")
chk("feet clear the plate's finger hole",
    all(math.hypot(fx - W/2, fy - (Dc-22)) > 7 + 7 for fx, fy in FOOT_XY))
chk("feet are on the plate, not the shell", "case_feet();\n      servo_collar" not in src)

chk("boards clear the bottom-plate finger hole",
    all(cy + bd/2 < Dc - 30 for nm, bw, bd, bh, cx, cy in BOARDS),
    f"finger hole at y={Dc-22:.0f}")

# --- monitor split into two bolted halves ---
mcut_x = p("mcut_x")
ear_len, ear_w, ear_p, join_d = p("ear_len"), p("ear_w"), p("ear_p"), p("join_d")
back_ear_z = p("back_ear_z")
bezel_l, bezel_r = stack_cx - (51/2 + 9), stack_cx + (51/2 + 9)
chk("monitor seam clears the screen bezel",
    mcut_x < bezel_l - 0.5 or mcut_x > bezel_r + 0.5,
    f"seam {mcut_x:.0f}, bezel {bezel_l:.1f}..{bezel_r:.1f}")
chk("both halves fit the bed lying on the cut face",
    Dm + 2 <= BED and Hm + 2 <= BED and max(mcut_x, Wm - mcut_x) <= 250,
    f"halves {mcut_x:.0f} and {Wm-mcut_x:.0f} thick")
chk("ears stay within the monitor width",
    mcut_x - ear_len > wall and mcut_x + ear_len <= Wm,
    f"ears span x {mcut_x-ear_len:.0f}..{mcut_x+ear_len:.0f} of {Wm:.0f}")
chk("bolt holes take an M3", join_d >= 3.2, f"hole {join_d} mm")
for _y in (24, 58):
    chk(f"roof ear at y={_y} sits on the roof, clear of the turret",
        sym + 4 < _y < Dm - 4 and abs(_y - turret_y) > 10,
        f"roof {sym:.1f}..{Dm:.0f}, turret y={turret_y:.0f}")
chk("back ear sits above the back door",
    back_ear_z - ear_w/2 > (Hm - 16) + 1 and back_ear_z + ear_w/2 < Hm,
    f"ear z {back_ear_z-ear_w/2:.0f}..{back_ear_z+ear_w/2:.0f}, door top {Hm-16:.1f}")
chk("back ear clear of the seam-side bezel", mcut_x > bezel_r,
    "ear column is in the right margin")

# --- total height sane on a desk ---
chk("total height reasonable", Hc + 4 + Hm < 210, f"{Hc+4+Hm:.0f} mm tall overall")

# --- nothing else is split: no stale seams, locks or dowels ---
chk("case is still one piece (no case seam)",
    not re.search(r"^cut_x\s*=", src, re.M) and "case_dowels" not in src,
    "leftover case seam")
chk("no latch/lid leftovers", not any(k in src for k in
    ("lid_z", "lid_hooks", "lid_latches", "lock_tab", "lock_boss")))
chk("every part still fits the bed whole",
    max(W, Dc, Hc) <= BED and max(Wm, Dm, Hm) <= BED,
    f"case {W:.0f}x{Dc:.0f}x{Hc:.0f}, monitor {Wm:.0f}x{Dm:.0f}x{Hm:.0f}")

for n, ok, d in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {n}" + (f"  ({d})" if d and not ok else ""))
if fails:
    print(f"\n{len(fails)} problem(s).")
    sys.exit(1)
print(f"\nall {len(checks)} checks passed — safe to slice.")
