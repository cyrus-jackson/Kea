// ============================================================
// KEA — "MiniToo" vintage-TV / retro-PC chassis
//
// A rounded, chunky little RETRO COMPUTER in the spirit of the Divoom
// MiniToo, dressed with vintage-machine cues:
//   * a monitor HOOD/BROW jutting over the screen
//   * the screen sunk in a CHAMFERED CRT RECESS (tube-face look)
//   * a near-flat KEYBOARD DECK at the base, tilted up toward you,
//     carrying the buttons + knob + toggle as "keys"
//   * VENT LOUVERS across the roof, a pixel-grid SPEAKER GRILLE and a
//     recessed NAMEPLATE + power LED on the front, and little FEET
//   * a small retro camera pod perched on top
//
// Same guts as the arcade chassis (Pi 3B+ + ELEGOO 3.5" portrait,
// friction cradle + gravity wedge, panel-mount controls, screwless
// press-fit door/floor) wrapped in a different, rounder shell.
//
// Render one part at a time (set `part`), export STL, print.
// All dimensions in mm. Run check_minitoo.py after any edit.
// ============================================================

part = "shell";   // "shell" | "shell_left" | "shell_right" | "bottom"
                  // | "door" | "wedge" | "camera_pod" | "assembly"

$fn = 64;

// ---------- Body ----------
W        = 100;   // width
D        = 92;    // depth  (CRTs are deep — the leaning screen needs it,
                  //         and it leans into the vintage-TV look)
wall     = 3;     // shell thickness (drives everything)
r_edge   = 11;    // radius of the vertical edges (plan rounding)
r_side   = 12;    // rounding of the front/deck/top edges (side profile)
cut_x    = 22;    // split-print plane, in the gap between toggle and buttons

// ---------- Front geometry ----------
front_h  = 30;    // vertical speaker face height at the very front
deck_y   = 46;    // depth where the keyboard deck ends / screen begins
deck_z   = 44;    // height at that point
recline  = 10;    // screen reclined back from vertical (deg) — upright-ish
slen     = 94;    // screen panel length up the slope (85.5 display + shelf)
top_cap  = 8;     // little brow above the screen before the flat roof

sy = deck_y + slen*sin(recline);              // screen top, depth
sz = deck_z + slen*cos(recline);              // screen top, height
H  = sz + top_cap;                            // total height
deck_a   = atan2(deck_z - front_h, deck_y);   // keyboard deck angle (~16°)
deck_len = sqrt(deck_y*deck_y + (deck_z-front_h)*(deck_z-front_h));

// ---------- Display (fixed hardware — do not scale) ----------
scr_cut  = [51, 75];     // portrait screen cutout (active 48.96 x 73.44)
stack    = [56, 85.5];   // display+Pi footprint, portrait

// ---------- Controls (12 mm threaded panel-mount, nut behind) ----------
btn_d    = 12.4;  // 12 mm pushbutton
enc_d    = 7.5;   // KY-040 bushing
tog_d    = 6.4;   // mini toggle
btn_dx   = 16;    // spacing between the three buttons
btn_row  = 32;    // buttons: distance up the deck
te_row   = 15;    // encoder + toggle: distance up the deck (front row)
tog_x    = 13;            // toggle center x (left)
enc_x    = W - 13;        // encoder center x (right)

// ---------- Back door opening ----------
door_z0  = 12;
door_top = H - 10;

// ---------- Power inlet ----------
pwr_side = -1;    // -1 left wall, 1 right wall
pwr_z    = 78;    // height of the jack (calibrate at dry-fit)
pwr_depth= 24;    // from the front toward the back

// ---------- Camera pod ----------
cam_r    = 14;
cam_holes= [21, 12.5];    // Pi camera v1 hole pattern
cam_y    = (sy + D)/2;    // pod sits on the flat roof behind the screen

// ============================================================
// 2D PROFILES  (rounded via offset(delta=-k) then offset(r=k))
// ============================================================
// Side profile in (depth, height): flat back, flat bottom, a low
// front wall, a rising keyboard deck, then the reclined screen and
// a short brow up to the flat roof.
side_pts = [[0, 0], [D, 0], [D, H], [sy, H],
            [sy, sz], [deck_y, deck_z], [0, front_h]];

module rounded_side(inset = 0)
  offset(r = r_side) offset(delta = -r_side - inset) polygon(side_pts);

module rounded_plan(inset = 0)
  offset(r = r_edge) offset(delta = -r_edge - inset) square([W, D]);

// Solid body = intersection of the two extruded rounded profiles.
// Side rounds the front/deck/top edges; plan rounds the 4 vertical
// edges; the floor stays flat for printing and standing.
module body(inset = 0) {
  intersection() {
    rotate([90, 0, 90]) linear_extrude(W) rounded_side(inset);
    linear_extrude(H + 1) rounded_plan(inset);
  }
}

// ============================================================
// Frames for placing features
//   screen_frame: x=width, y=into body, z=up the screen slope
//   deck_frame:   x=width, y=up the deck, z=out of the deck (normal)
// ============================================================
module screen_frame() { translate([0, deck_y, deck_z]) rotate([-recline, 0, 0]) children(); }
module deck_frame()   { translate([0, 0, front_h]) rotate([deck_a, 0, 0]) children(); }

// ============================================================
// SHELL
// ============================================================
module shell() {
  difference() {
    union() {
      difference() {
        body();                 // outer
        body(inset = wall);     // hollow — wall on every face
      }
      screen_frame() screen_bezel();     // raised CRT bezel + hood
      screen_frame() cradle();           // display cradle inside
      floor_ledge();
      floor_nubs();
      feet();                            // little raised feet
    }
    // --- openings ---
    screen_frame() screen_cut();         // chamfered CRT recess
    deck_frame()   control_holes();
    speaker_grille();
    front_badge();                       // recessed nameplate + power LED
    vent_louvers();                      // retro cooling slots on the roof
    back_door_cut();
    bottom_open();
    power_slot();
    camera_sockets();                    // holes the pod's pegs press into
    camera_ribbon_slot();
    dowel_holes();
  }
}

// Raised rounded frame around the screen — the CRT bezel, plus a little
// hood/brow jutting over the top like an old monitor.
module screen_bezel() {
  bw = 8; bz = 3.0;
  ow = scr_cut[0] + 2*bw; oh = scr_cut[1] + 2*bw;
  translate([W/2, 0, slen/2]) rotate([-90, 0, 0])
    linear_extrude(bz)
      difference() {
        offset(r=6) offset(delta=-6) square([ow, oh], center=true);
        offset(r=3) offset(delta=-3) square([scr_cut[0]+5, scr_cut[1]+5], center=true);
      }
  screen_hood();
}
module screen_hood() {
  bw = 8;
  hz = slen/2 + scr_cut[1]/2 + bw;          // just above the bezel top
  translate([W/2, 0, hz]) rotate([-90, 0, 0])
    linear_extrude(10)                       // juts ~10 mm toward the viewer
      offset(r=4) offset(delta=-4)
        square([scr_cut[0] + 2*bw + 4, 9], center=true);
}
// Chamfered CRT recess: the opening flares out toward the viewer, then a
// straight through-hole — the flat panel sits back like a tube face.
module screen_cut() {
  hull() {
    translate([W/2, -0.2, slen/2]) cube([scr_cut[0]+5, 0.1, scr_cut[1]+5], center=true);
    translate([W/2, 3.0, slen/2])  cube([scr_cut[0], 0.1, scr_cut[1]], center=true);
  }
  translate([W/2, 3, slen/2]) cube([scr_cut[0], wall+8, scr_cut[1]], center=true);
}

// Buttons/knob/toggle as keys on the tilted deck.
module control_holes() {
  translate([tog_x, te_row, 0]) cylinder(d=tog_d, h=24, center=true);
  translate([enc_x, te_row, 0]) cylinder(d=enc_d, h=24, center=true);
  for (bx = [W/2 - btn_dx, W/2, W/2 + btn_dx])
    translate([bx, btn_row, 0]) cylinder(d=btn_d, h=24, center=true);
}

// Pixel-grid speaker grille on the low vertical front face (lower band).
module speaker_grille() {
  cols = 9; rows = 3; pitch = 6;
  gw = (cols-1)*pitch; gh = (rows-1)*pitch;
  for (i = [0:cols-1], j = [0:rows-1])
    translate([W/2 + i*pitch - gw/2, 1.5, front_h/2 - 7 + j*pitch - gh/2])
      rotate([-90,0,0]) cylinder(d=2.6, h=wall+6, center=true);
}

// Recessed nameplate + power-LED on the upper part of the front face.
module front_badge() {
  translate([W/2, 1.2, 22]) rotate([90,0,0]) linear_extrude(1.2)          // plate recess
    offset(r=2.5) offset(delta=-2.5) square([46, 12], center=true);
  translate([W/2, 1.6, 22]) rotate([90,0,0]) mirror([1,0,0]) linear_extrude(1.6)
    text("K E A", size=6, halign="center", valign="center",
         font="DejaVu Sans:style=Bold");                                  // debossed name
  translate([W-16, 1.5, 8]) rotate([-90,0,0]) cylinder(d=3.2, h=wall+4, center=true); // LED
}

// Retro cooling louvers on the flat roof — two banks of front-to-back
// slots flanking the camera pod, like the vents on an old beige box.
module vent_louvers() {
  y0 = sy + 5; y1 = D - 6;
  for (s = [-1, 1], k = [0:3])
    translate([W/2 + s*(20 + k*5) - 1.1, y0, H-wall-1])
      cube([2.2, y1 - y0, wall+2]);
}

// Four little feet, raising the body off the desk like a real box.
module feet() {
  for (x = [16, W-16], yy = [16, D-16])
    translate([x, yy, -2.5]) cylinder(d=12, h=2.6);
}

// ============================================================
// DISPLAY CRADLE — shelf carries the stack's bottom edge, guides
// center it, short back flanges give the wedge a bearing face.
// ============================================================
module cradle() {
  gx0 = (W-56)/2 - 3.5;
  gx1 = (W+56)/2 + 0.5;
  translate([wall, wall, 2.5]) cube([W - 2*wall, 28, 4]);   // shelf
  translate([gx0, wall, 4]) cube([3, 28, 58]);              // guides
  translate([gx1, wall, 4]) cube([3, 28, 58]);
  translate([gx0,      wall+25, 8]) cube([21, 3, 42]);      // back flanges
  translate([gx1+3-21, wall+25, 8]) cube([21, 3, 42]);
}

// ============================================================
// WEDGE — drop behind the Pi, nudge down until snug. Prints flat.
// ============================================================
module wedge() {
  difference() {
    union() {
      rotate([90, 0, 90]) linear_extrude(56)
        polygon([[0, 0], [1.5, 0], [9.5, 58], [0, 58]]);
      translate([0, 0, 52]) cube([56, 11, 6]);   // grip tab
    }
    translate([16, -1, 8]) cube([24, 13, 40]);   // wire pass-through
  }
}

// ============================================================
// BACK DOOR
// ============================================================
module back_door_cut() {
  translate([12, D-wall-1, door_z0]) cube([W-24, wall+2, door_top-door_z0]);
}
module door() {
  ow = W-24; doh = door_top - door_z0;
  fh = doh + 12; lh = doh - 0.6;
  difference() {
    union() {
      translate([-ow/2 - 6, -fh/2, 0]) cube([ow+12, fh, 2.5]);         // face
      translate([-ow/2 + 0.3, -lh/2, -2.5]) cube([ow-0.6, lh, 2.6]);   // lip
      for (rx = [-ow/2+8, ow/2-20])                                    // crush ribs
        for (ry = [-lh/2-0.2, lh/2-0.3])
          translate([rx, ry, -2.5]) cube([12, 0.5, 2.6]);
    }
    for (i = [-3:3])                                                   // vents
      translate([i*11 - 1.5, -22, -3]) cube([3, 44, 9]);
    translate([0, fh/2, -3]) cylinder(d=13, h=9);                      // finger scallop
  }
}

// ============================================================
// FLOOR: press-fit bottom plate (nubs + ledge, screwless)
// ============================================================
module bottom_open() { translate([wall, wall, -1]) cube([W-2*wall, D-2*wall, wall+2]); }
module floor_ledge() {
  lt = 1.5; lp = 1.8;
  translate([wall, wall, wall+0.8])       cube([W-2*wall, lp, lt]);
  translate([wall, D-wall-lp, wall+0.8])  cube([W-2*wall, lp, lt]);
  translate([wall, wall, wall+0.8])       cube([lp, D-2*wall, lt]);
  translate([W-wall-lp, wall, wall+0.8])  cube([lp, D-2*wall, lt]);
}
module floor_nubs() {
  np = 1.15;
  for (x = [W*0.3, W*0.7]) {
    translate([x-3, wall, 0]) cube([6, np, 1.4]);
    translate([x-3, D-wall-np, 0]) cube([6, np, 1.4]);
  }
  translate([wall, D/2-3, 0]) cube([np, 6, 1.4]);
  translate([W-wall-np, D/2-3, 0]) cube([np, 6, 1.4]);
}
module bottom_plate() {
  difference() {
    translate([wall+0.75, wall+0.75, 0]) cube([W-2*wall-1.5, D-2*wall-1.5, wall]);
    translate([W/2, D-22, -1]) cylinder(d=14, h=wall+2);   // finger hole
  }
}

// ============================================================
// POWER inlet slot in the side wall
// ============================================================
module power_slot() {
  translate([pwr_side > 0 ? W-wall-2 : -2, pwr_depth, pwr_z])
    rotate([0, 90, 0])
      hull() for (dz=[-4,4], dy=[-2.5,2.5])
        translate([dz, dy, 0]) cylinder(d=13, h=wall+4);
}

// ============================================================
// SEAM dowels for the split print
// ============================================================
module dowel_holes() {
  for (p = [[3, 12], [3, H-16], [D-3, 12], [D-3, H-16]])
    translate([cut_x-6, p[0], p[1]]) rotate([0,90,0]) cylinder(d=2.0, h=12);
}

// ============================================================
// CAMERA POD — rounded retro-webcam blob, press-fits into the roof.
// (Camera electronics are the user's own project — this just holds it.)
// ============================================================
module camera_sockets() {
  for (s=[-1,1]) translate([W/2 + s*9, cam_y, H-wall-1]) cylinder(d=5.5, h=wall+2);
}
module camera_ribbon_slot() {
  translate([W/2-12.5, cam_y - 2, H-wall-1]) cube([25, 4.1, wall+2]);
}
module camera_pod() {
  union() {
    difference() {
      hull() {
        for (s=[-1,1]) translate([s*10, 0, 6]) sphere(r=cam_r*0.55);
        translate([0, 4, 6]) sphere(r=cam_r*0.6);
      }
      translate([0, -cam_r, 8]) rotate([-90,0,0]) cylinder(d=9, h=cam_r);  // lens bore
      translate([-13, -8, -1]) cube([26, 16, 7]);                          // PCB pocket
      for (x=[-1,1], y=[-1,1])
        translate([x*cam_holes[0]/2, y*cam_holes[1]/2, -1]) cylinder(d=2.2, h=9);
    }
    for (s=[-1,1]) translate([s*9, 0, -(wall+0.4)]) {                       // pegs
      cylinder(d=5.7, h=wall+0.5);
      translate([0,0,-0.9]) cylinder(d1=4.6, d2=5.7, h=1);
    }
  }
}

// ============================================================
// RENDER
// ============================================================
if (part == "shell")   shell();
if (part == "shell_left")
  intersection() { shell(); translate([-1,-1,-3]) cube([cut_x+1, D+2, H+4]); }
if (part == "shell_right")
  intersection() { shell(); translate([cut_x,-1,-3]) cube([W-cut_x+1, D+2, H+4]); }
if (part == "bottom")     bottom_plate();
if (part == "door")       door();
if (part == "wedge")      wedge();
if (part == "camera_pod") camera_pod();
if (part == "assembly") {
  color("Gainsboro") shell();
  color("gray")      bottom_plate();
  color("dimgray")   translate([W/2, D+0.5, (door_z0+door_top)/2]) rotate([-90,0,0]) door();
  color("orange")    translate([W/2, cam_y, H]) camera_pod();
}
