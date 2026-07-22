// ============================================================
// KEA — Mini bartop-arcade desk chassis
// Raspberry Pi 3 + ELEGOO 3.5" TFT (480x320) + 3 buttons +
// KY-040 encoder + toggle + SG90 pan-tilt camera on top.
//
// Render one part at a time (set `part`), export STL, print.
// All dimensions in mm. Tune the CALIBRATE block after
// measuring your actual Pi+display stack.
// ============================================================

part = "shell_right"; // "shell" | "shell_left" | "shell_right" | "bottom" | "door"
                // | "wedge" | "camstand" | "camplate" | "assembly"
                // RECOMMENDED PRINT: shell_left + shell_right, each lying on
                // its cut face -> every feature prints as a vertical wall,
                // NO supports needed anywhere. Align the halves with short
                // pieces of 1.75 mm filament in the dowel holes and glue.

$fn = 48;

teardrop = true;  // true for the sideways split print: round holes get a
                  // 45-degree point on the side that faces UP in that
                  // orientation (+x), so their crowns print without support.
                  // Set false if you print the shell upright in one piece.

// cylinder that hulls into a 45-degree teardrop point along +/-x.
// dir must point toward "print up": +1 for holes in the right half,
// -1 for holes in the left half (it lies on the bed the other way).
module tear_cyl(d, h, center=false, dir=1) {
  if (teardrop)
    hull() {
      cylinder(d=d, h=h, center=center);
      translate([dir*d*0.71, 0, 0]) cylinder(d=0.6, h=h, center=center);
    }
  else
    cylinder(d=d, h=h, center=center);
}

// ---------- Main body ----------
// Trimmed to the minimum the fixed-size display + control row need — the
// breadboard is gone, so nothing lives under the slope any more. The
// display (56 x 85.5) sets the width and slope-length floors; depth,
// marquee and deck were carrying slack and got pulled in.
W        = 104;   // exterior width (56 stack + control row + walls)
D        = 118;   // exterior depth (was 130; back overhang pulled in)
cut_x    = 19;    // split-print plane: near the left side, between the
                  // toggle (ends ~17.2) and the blue button (starts ~20.8),
                  // clear of the screen opening and camera slot
wall     = 3;     // CASE THICKNESS: one knob for every wall, the deck, the
                  // screen panel and the top. Everything derives from it
                  // (ledge, nubs, camstand pegs, socket depths). Keep it
                  // 2.5-4: above ~4 the 12 mm button/encoder bushings get
                  // too short to catch their nuts through the deck.
front_h  = 30;    // front panel height (was 35)
deck_y   = 42;    // control deck end (depth) (was 48)
deck_z   = 48;    // control deck end (height) (was 52)
tilt     = 25;    // screen tilt back from vertical (deg)
slen     = 94;    // screen panel length along slope (85.5 display + shelf)
marq     = 18;    // marquee height above screen panel (was 24)

sy = deck_y + slen*sin(tilt);      // top of slope, depth  (~99.6)
sz = deck_z + slen*cos(tilt);      // top of slope, height (~125.7)
H  = sz + marq;                    // total height         (~149.7)
deck_a   = atan2(deck_z-front_h, deck_y);          // deck angle (~19.5 deg)
deck_len = sqrt(deck_y*deck_y + (deck_z-front_h)*(deck_z-front_h)); // ~50.9

// ---------- CALIBRATE: measure your hardware ----------
scr_vis   = [51, 75];    // PORTRAIT screen cutout (active area 48.96 x 73.44 + margin)
disp_pcb  = [56, 85.5];  // display module = full Pi 3B+ footprint, portrait
// (stack thickness no longer matters: the cradle's shelf carries the
//  stack and the WEDGE part self-adjusts to any thickness 20-30 mm)
// Power inlet: slot in the side wall aligned with the Pi's micro-USB jack
// (stock PSU plugs in directly — no adapters). Dry-fit the Pi+display stack
// and measure these before printing:
pwr_side  = -1;          // 1 = right wall (x=W), -1 = left wall (x=0)
pwr_depth = 20;          // panel inner face -> jack axis (measure at dry-fit)
pwr_z     = 82;          // along-slope position of jack center — near the TOP
                         //   of the slope (jack ~10.6 mm from the Pi corner;
                         //   use ~18 instead if the power edge sits low)

// ---------- Small parts ----------
btn_d     = 12.4;        // 12 mm THREADED panel-mount pushbutton (nut behind,
                         // like the encoder/toggle) — no perfboard, no glue
enc_d     = 7.5;         // KY-040 shaft bushing hole
tog_d     = 6.4;         // mini toggle hole
cam_holes = [21, 12.5];  // Pi camera v1 hole pattern, 2 mm holes

// ============================================================
// Helper frames
// ============================================================
module screen_frame() {                 // local: x=width, z=up-slope, +y=into cabinet
  translate([0, deck_y, deck_z]) rotate([-tilt, 0, 0]) children();
}
module deck_frame() {                   // local: x=width, y=up-deck, +z=out of deck
  translate([0, 0, front_h]) rotate([deck_a, 0, 0]) children();
}

// ============================================================
// SHELL
// ============================================================
profile = [[0,0],[D,0],[D,H],[sy,H],[sy,sz],[deck_y,deck_z],[0,front_h]];

// ---------- Back door opening ----------
// The opening now reaches HIGH up the back wall so the Pi+display's top
// edge clears the rail as you angle the stack in from behind. Raising it
// meant the door's old protruding pull-tab no longer fit under the ceiling,
// so the door uses a finger scallop instead (see module door).
door_z0  = 12;    // opening floor (sits just above the bottom-plate ledge)
door_top = H - 7; // opening ceiling — as high as the faceplate (opening +
                  // 6 mm margin) can go and still fit under the roof
door_dz  = H - 4; // seam dowel, tucked in the thin rail above the opening

module shell() {
  difference() {
    union() {
      // walls
      difference() {
        rotate([90,0,90]) linear_extrude(W) polygon(profile);
        translate([wall,0,0]) rotate([90,0,90])
          linear_extrude(W-2*wall) offset(delta=-wall) polygon(profile);
      }
      bottom_ledge();
      bottom_nubs();
      screen_frame() stack_cradle();
    }
    // open bottom (bottom plate snaps in between the nubs and the ledge)
    translate([wall, wall, -1]) cube([W-2*wall, D-2*wall, wall+2]);
    // back door opening — nearly the whole back wall, raised high (door_top)
    // so the stack's top edge clears the rail while you angle it in
    translate([10, D-wall-1, door_z0]) cube([W-20, wall+2, door_top-door_z0]);
    // screen cutout
    screen_frame() translate([W/2, 1.5, slen/2])
      cube([scr_vis[0], wall+6, scr_vis[1]], center=true);
    // control deck holes
    deck_frame() deck_holes();
    // camera stand peg sockets (press-fit, no screws)
    camstand_sockets();
    // camera ribbon slot — positioned relative to the camstand center so
    // it stays aligned with the stand's own pass-through at ANY tilt
    translate([W/2-12.5, (sy+D)/2 - 10.9, H-wall-1]) cube([25, 4.1, wall+2]);
    // marquee label
    translate([W/2, sy+1.2, sz+marq/2]) rotate([90,0,0])
      linear_extrude(1.4) text("K E A", size=11, font="DejaVu Sans:style=Bold",
                               halign="center", valign="center");
    // power inlet slot (side wall)
    power_slot();
    // alignment dowel holes on the center cut plane (2.0 mm: a short
    // piece of 1.75 mm filament is the dowel). Harmless in a one-piece
    // print — they're buried inside the walls.
    dowel_holes();
  }
}

module dowel_holes() {
  for (p = [[1.5, 15],                 // front wall
            [D-1.5, 6],                // back wall, below the door opening
            [D-1.5, door_dz],          // back wall, in the rail above the door
            [(sy+D)/2, H-1.5]])        // top plate
    translate([cut_x-6, p[0], p[1]])
      rotate([0, 90, 0]) cylinder(d=2.0, h=12);
}

// Oversized slot so the micro-USB plug body passes through the 3 mm wall;
// elongated along the slope and in depth for alignment tolerance.
module power_slot() {
  screen_frame()
    translate([pwr_side > 0 ? W - 19 : -6, pwr_depth, pwr_z])
      rotate([0, 90, 0])
        hull() for (dz = [-4, 4], dy = [-2.5, 2.5])
          translate([dz, dy, 0]) cylinder(d=13, h=25);   // long enough to
                                                          // notch the rail too
}

module camstand_sockets() {
  py = (sy+D)/2;                            // stand center, depth
  for (s = [-1,1]) translate([W/2 + s*10, py, H-wall-1])
    tear_cyl(d=5.5, h=wall+2);              // sockets for the stand's pegs
}

// The bottom plate is fully screwless: it pushes in from below past six
// friction nubs and stops against a perimeter ledge, sitting recessed
// ~0.8 mm. Nubs print from the bed; the ledge is a tiny 1.8 mm bridge.
module bottom_ledge() {
  lt = 1.5;   // ledge thickness
  lp = 1.8;   // ledge protrusion into the interior
  translate([wall, wall, wall+0.8]) cube([W-2*wall, lp, lt]);
  translate([wall, D-wall-lp, wall+0.8]) cube([W-2*wall, lp, lt]);
  translate([wall, wall, wall+0.8]) cube([lp, D-2*wall, lt]);
  translate([W-wall-lp, wall, wall+0.8]) cube([lp, D-2*wall, lt]);
}
module bottom_nubs() {
  np = 1.15;  // protrusion (squeezes the plate edges for friction)
  for (x = [W*0.3, W*0.7]) {
    translate([x-3, wall, 0]) cube([6, np, 1.4]);
    translate([x-3, D-wall-np, 0]) cube([6, np, 1.4]);
  }
  translate([wall, D/2-3, 0]) cube([np, 6, 1.4]);
  translate([W-wall-np, D/2-3, 0]) cube([np, 6, 1.4]);
}

// ============================================================
// STACK CRADLE — the fix for "the Pi has nowhere to sit".
// The display+Pi stack leans against the screen panel like a
// picture in a frame: its bottom edge RESTS on a solid shelf,
// two side guides center it, and the printed WEDGE part slides
// down the slope behind the Pi until it jams snug against the
// back flanges. Gravity keeps it tight. Works for ANY stack
// thickness from ~20 to ~30 mm — nothing to measure.
// ============================================================
module stack_cradle() {
  gx0 = (W-56)/2 - 3.5;    // left guide, just outside the 56 mm stack
  gx1 = (W+56)/2 + 0.5;    // right guide
  // shelf under the stack's bottom edge (rooted in both side walls)
  translate([wall, wall, 2.5]) cube([W - 2*wall, 30, 4]);
  // side guides: vertical ribs just outside the stack width
  translate([gx0, wall, 4]) cube([3, 30, 66]);
  translate([gx1, wall, 4]) cube([3, 30, 66]);
  // back flanges: the fixed plane the wedge bears against — kept SHORT
  // (bottom half only) so the channel is wide open for insertion.
  // Gap in the middle keeps the CSI ribbon path clear.
  translate([gx0, wall + 29, 8]) cube([21.5, 3, 44]);
  translate([gx1 + 3 - 21.5, wall + 29, 8]) cube([21.5, 3, 44]);
}

// ============================================================
// WEDGE: drop it thin-end-first between the Pi's back and the
// cradle flanges, nudge it down the slope until snug. Covers a
// 2-9.5 mm gap, so any Pi+display stack clamps tight. Pull it
// up to release the stack. Print lying on its flat face.
// ============================================================
module wedge() {
  difference() {
    union() {
      rotate([90, 0, 90]) linear_extrude(58)
        polygon([[0, 0], [1.5, 0], [9.5, 62], [0, 62]]);
      // grip tab on the thick end
      translate([0, 0, 56]) cube([58, 11, 6]);
    }
    // wire pass-through: GPIO jumpers from the Pi's exposed pins run
    // through here. The cutout sits over the cradle's center gap, so
    // the wedge still bears on both flanges at its solid side rails.
    translate([17, -1, 8]) cube([24, 13, 44]);
  }
}

module deck_holes() {
  // 3 buttons: blue / red / green (GPIO 21 / 20 / 26), centered, 25 mm apart
  for (bx = [W/2-25, W/2, W/2+25])
    translate([bx, 32, 0]) tear_cyl(d=btn_d, h=24, center=true);
  // KY-040 rotary encoder (right), mini toggle (left)
  translate([W-14, 16, 0]) tear_cyl(d=enc_d, h=24, center=true);
  translate([14, 16, 0]) tear_cyl(d=tog_d, h=24, center=true, dir=-1);  // left half
}

// ============================================================
// BOTTOM PLATE (screwless: pushes in from below past the friction
// nubs until it stops against the ledge; finger hole to pull it out).
// Plain floor now — the breadboard and its corral are gone; every
// control is panel-mounted and wired straight to the Pi header.
// ============================================================
module bottom_plate() {
  difference() {
    translate([wall+0.75, wall+0.75, 0])
      cube([W-2*wall-1.5, D-2*wall-1.5, wall]);
    translate([W/2, D-25, -1]) cylinder(d=14, h=wall+2);  // finger hole
  }
}

// ============================================================
// BACK DOOR (screwless press-fit: full-size lip with crush ribs
// wedges into the opening; pull tab at the bottom to pop it out)
// ============================================================
module door() {
  doh = door_top - door_z0;        // opening height (tracks the shell)
  fh  = doh + 12;                  // faceplate height (6 mm margin top+bottom)
  lh  = doh - 0.6;                 // lip height (0.3 mm clearance each end)
  difference() {
    union() {
      translate([-51, -fh/2, 0]) cube([102, fh, 2.5]);          // face plate
      translate([-44.7, -lh/2, -2.5]) cube([89.4, lh, 2.6]);    // press-fit lip
      // crush ribs: 0.5 proud, they squash on first insertion
      for (ry = [-(doh/2-20), (doh/2-32)]) {
        translate([-45.2, ry, -2.5]) cube([0.5, 12, 2.6]);
        translate([44.7, ry, -2.5]) cube([0.5, 12, 2.6]);
      }
      for (rx = [-30, 18]) {
        translate([rx, -lh/2-0.2, -2.5]) cube([12, 0.5, 2.6]);
        translate([rx,  lh/2-0.3, -2.5]) cube([12, 0.5, 2.6]);
      }
    }
    for (i = [-2:2])                                    // vents
      translate([i*12-1.5, -28, -3]) cube([3, 56, 9]);
    // spare cable hole (e.g. aux 5 V for servos later) — power enters
    // through the side-wall slot instead, no extra parts needed
    translate([0, -54, -3]) cylinder(d=12, h=9);
    // finger scallop bitten out of the top edge — replaces the old pull
    // tab, which no longer fit once the opening rose near the ceiling
    translate([0, fh/2, -3]) cylinder(d=13, h=9);
  }
}

// ============================================================
// CAMERA STAND (no servos, no screws): fork with two chamfered
// pegs that press into the top-plate sockets. The camera plate
// hangs between the arms on an M3 bolt + nyloc nut — a manual
// friction tilt, set the angle once by hand.
// (If you ever add a servo back, only this part changes.)
// ============================================================
module camstand() {
  union() {
    difference() {
      union() {
        translate([-19, -13, 0]) cube([38, 26, 6]);    // base, press-fits to top
        for (s = [-1, 1])                               // fork arms, 28 mm apart
          translate([s*16-2, -6, 0]) cube([4, 12, 32]);
      }
      camstand_cuts();
    }
    // press-fit pegs (chamfered tips) into the top-plate sockets;
    // length follows the wall parameter automatically
    for (s = [-1, 1]) translate([s*10, 0, -(wall+0.4)]) {
      cylinder(d=5.7, h=wall+0.5);
      translate([0, 0, -0.9]) cylinder(d1=4.6, d2=5.7, h=1);
    }
  }
}

module camstand_cuts() {
  // ribbon pass-through: the base sits over the top-plate slot, so the
  // same 25 x 4 slot continues through the base (in front of the arms)
  translate([-12.5, -10.9, -1]) cube([25, 4.1, 8]);
  // M3 tilt axle through both arms
  translate([0, 0, 26]) rotate([0, 90, 0]) cylinder(d=3.2, h=50, center=true);
}

module camera_plate() {
  difference() {
    union() {
      translate([-13.5, -12.5, 0]) cube([27, 25, 2.5]);
      for (s = [-1, 1])                                 // hinge tabs, fit inside fork
        translate([s > 0 ? 10.5 : -13.5, 6.5, 0]) cube([3, 6, 10]);
    }
    for (x = [-1,1], y = [-1,1])                        // Pi camera holes
      translate([x*cam_holes[0]/2, y*cam_holes[1]/2, -1]) cylinder(d=2.2, h=5);
    // notch at the bottom edge: the camera's ribbon connector sits on the
    // BACK of its PCB at the bottom — ribbon folds down through here
    translate([-9, -13.5, -1]) cube([18, 8, 5]);
    // M3 axle through the tabs
    translate([0, 9.5, 6]) rotate([0, 90, 0]) cylinder(d=3.2, h=40, center=true);
  }
}

// ============================================================
// RENDER
// ============================================================
if (part == "shell")    shell();
if (part == "shell_left")                       // print lying on the cut face
  intersection() { shell(); translate([-1, -1, -1]) cube([cut_x+1, D+2, H+2]); }
if (part == "shell_right")
  intersection() { shell(); translate([cut_x, -1, -1]) cube([W-cut_x+1, D+2, H+2]); }
if (part == "bottom")   bottom_plate();
if (part == "door")     door();
if (part == "wedge")    wedge();
if (part == "camstand") camstand();
if (part == "camplate") camera_plate();
if (part == "assembly") {
  color("SteelBlue", 0.85) shell();
  color("gray") bottom_plate();
  color("dimgray") translate([W/2, D+0.5, (door_z0+door_top)/2]) rotate([-90,0,0]) door();
  color("orange") translate([W/2, (sy+D)/2, H]) camstand();
  color("tomato") screen_frame() translate([26, wall+19.5, 6]) wedge();
  color("orange") translate([W/2, (sy+D)/2-9.5, H+20]) rotate([90,0,0]) camera_plate();
}
