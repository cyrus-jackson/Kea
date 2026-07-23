// ============================================================
// KEA — retro CRT-TERMINAL chassis
//
// A vintage computer terminal: a chunky BASE pedestal with a control
// shelf (buttons + knob + toggle) and a speaker grille, and a MONITOR
// block sitting on top — a deeply RECESSED screen under a jutting HOOD,
// with a pan/tilt CAMERA HEAD on the roof.
//
// The moving head is the Adafruit Mini Pan-Tilt kit (2x SG90): the roof
// has a flat pad + two screw holes for its bracket and a pass-through
// for the servo leads + camera ribbon. Servos want their own 5 V — do
// NOT run them off the Pi header.
//
// Same guts as before: Pi 3B+ + ELEGOO 3.5" portrait, friction cradle +
// gravity wedge, panel-mount controls, screwless press-fit door/floor.
//
// Render one part at a time (set `part`), export STL. Run
// check_terminal.py after any edit.
// ============================================================

part = "shell";   // "shell" | "shell_left" | "shell_right" | "bottom"
                  // | "door" | "wedge" | "cam_cradle" | "assembly"

$fn = 64;

// ---------- Body ----------
W        = 110;   // width
Db       = 95;    // depth
wall     = 3;
r_edge   = 7;     // vertical-edge rounding (crisper than the MiniToo)
r_side   = 7;     // front/deck/top edge rounding
cut_x    = 24;    // split-print plane, between toggle and first button

// ---------- Base pedestal ----------
base_h   = 46;    // height of the base
mon_y0   = 34;    // depth where the monitor front meets the base top
                  //   (control shelf is the base top in front of it: y 0..mon_y0)

// ---------- Monitor / screen ----------
recline  = 10;    // screen reclined back from vertical
slen     = 94;    // screen slope length (85.5 display + shelf)
top_cap  = 8;     // brow above the screen before the flat roof

sy = mon_y0 + slen*sin(recline);     // screen top / roof front, depth
sz = base_h + slen*cos(recline);     // screen top, height
H  = sz + top_cap;                   // total height

// ---------- Display (fixed hardware) ----------
scr_cut  = [51, 75];
stack    = [56, 85.5];

// ---------- Controls (12 mm panel-mount on the base shelf) ----------
btn_d    = 12.4;
enc_d    = 7.5;
tog_d    = 6.4;
btn_dx   = 16;
btn_row  = 24;    // buttons: depth on the shelf
te_row   = 12;    // encoder+toggle: depth on the shelf
tog_x    = 13;
enc_x    = W - 13;

// ---------- Back door (on the monitor's back wall) ----------
door_z0  = base_h + 4;
door_top = H - 8;

// ---------- Power inlet ----------
pwr_side = -1;    // -1 left, 1 right
pwr_z    = 90;    // jack height (calibrate)
pwr_depth= 26;

// ---------- Camera turret (Adafruit Mini Pan-Tilt footprint) ----------
turret_y = 72;            // where it sits on the roof
turret_holes = 18;        // screw-hole spacing of the kit bracket (measure!)

// ============================================================
// 2D profiles + rounded body (side x plan intersection)
// ============================================================
// side profile (depth, height): base box, control shelf on top of the
// base in front, reclined monitor, brow, flat roof, vertical back.
side_pts = [[0, 0], [Db, 0], [Db, H], [sy, H],
            [sy, sz], [mon_y0, base_h], [0, base_h]];

module rounded_side(inset=0)
  offset(r=r_side) offset(delta=-r_side-inset) polygon(side_pts);
module rounded_plan(inset=0)
  offset(r=r_edge) offset(delta=-r_edge-inset) square([W, Db]);

module body(inset=0) {
  intersection() {
    rotate([90,0,90]) linear_extrude(W) rounded_side(inset);
    linear_extrude(H+1) rounded_plan(inset);
  }
}

// frames
module screen_frame() { translate([0, mon_y0, base_h]) rotate([-recline,0,0]) children(); }

// ============================================================
// SHELL
// ============================================================
module shell() {
  difference() {
    union() {
      difference() { body(); body(inset=wall); }
      screen_frame() screen_bezel();
      screen_frame() cradle();
      floor_ledge();
      floor_nubs();
      feet();
    }
    screen_frame() screen_cut();
    shelf_controls();
    speaker_grille();
    front_badge();
    back_door_cut();
    bottom_open();
    power_slot();
    turret_mount();
    dowel_holes();
  }
}

// --- monitor: hood + recessed screen ---
module screen_bezel() {
  bw = 9; bz = 3.5;
  ow = scr_cut[0]+2*bw; oh = scr_cut[1]+2*bw;
  translate([W/2, 0, slen/2]) rotate([-90,0,0]) linear_extrude(bz)
    difference() {
      offset(r=4) offset(delta=-4) square([ow, oh], center=true);
      offset(r=2) offset(delta=-2) square([scr_cut[0]+5, scr_cut[1]+5], center=true);
    }
  screen_hood();
}
module screen_hood() {
  bw = 9; hz = slen/2 + scr_cut[1]/2 + bw;
  translate([W/2, 0, hz]) rotate([-90,0,0]) linear_extrude(12)      // deep brow
    offset(r=3) offset(delta=-3) square([scr_cut[0]+2*bw+6, 10], center=true);
}
module screen_cut() {
  hull() {
    translate([W/2, -0.2, slen/2]) cube([scr_cut[0]+6, 0.1, scr_cut[1]+6], center=true);
    translate([W/2, 4.0, slen/2])  cube([scr_cut[0], 0.1, scr_cut[1]], center=true);
  }
  translate([W/2, 4, slen/2]) cube([scr_cut[0], wall+10, scr_cut[1]], center=true);
}

// --- controls on the horizontal base shelf (y 0..mon_y0 at z=base_h) ---
module shelf_controls() {
  translate([tog_x, te_row, base_h-1]) cylinder(d=tog_d, h=wall+4);
  translate([enc_x, te_row, base_h-1]) cylinder(d=enc_d, h=wall+4);
  for (bx=[W/2-btn_dx, W/2, W/2+btn_dx])
    translate([bx, btn_row, base_h-1]) cylinder(d=btn_d, h=wall+4);
}

// --- speaker grille on the base front face ---
module speaker_grille() {
  cols=11; rows=4; pitch=6;
  gw=(cols-1)*pitch; gh=(rows-1)*pitch;
  for (i=[0:cols-1], j=[0:rows-1])
    translate([W/2 + i*pitch - gw/2, 1.5, base_h/2 - 3 + j*pitch - gh/2])
      rotate([-90,0,0]) cylinder(d=2.6, h=wall+6, center=true);
}
module front_badge() {
  translate([W-18, 1.5, base_h-8]) rotate([-90,0,0]) cylinder(d=3.2, h=wall+4, center=true); // power LED
}

// --- display cradle (in the monitor, on the screen frame) ---
module cradle() {
  gx0 = (W-56)/2 - 3.5; gx1 = (W+56)/2 + 0.5;
  translate([wall, wall, 2.5]) cube([W-2*wall, 28, 4]);
  translate([gx0, wall, 4]) cube([3, 28, 58]);
  translate([gx1, wall, 4]) cube([3, 28, 58]);
  translate([gx0, wall+25, 8]) cube([21, 3, 42]);
  translate([gx1+3-21, wall+25, 8]) cube([21, 3, 42]);
}
module wedge() {
  difference() {
    union() {
      rotate([90,0,90]) linear_extrude(56) polygon([[0,0],[1.5,0],[9.5,58],[0,58]]);
      translate([0,0,52]) cube([56,11,6]);
    }
    translate([16,-1,8]) cube([24,13,40]);
  }
}

// --- camera turret mount on the roof (Adafruit Mini Pan-Tilt) ---
module turret_mount() {
  // wire + ribbon pass-through
  translate([W/2-11, turret_y-8, H-wall-1]) cube([22, 16, wall+2]);
  // two screw holes for the kit's base bracket
  for (s=[-1,1]) translate([W/2 + s*turret_holes/2, turret_y+11, H-wall-1])
    cylinder(d=2.6, h=wall+2);
}
// Optional printed cradle to bolt the Pi camera onto the kit's top plate.
module cam_cradle() {
  difference() {
    translate([-14,-13,0]) cube([28,26,2.5]);
    for (x=[-1,1], y=[-1,1]) translate([x*21/2, y*12.5/2, -1]) cylinder(d=2.2, h=5);
    translate([-9,-13.5,-1]) cube([18,8,5]);            // ribbon notch
    for (x=[-1,1]) translate([x*10, -9, -1]) cylinder(d=2.4, h=5);  // to kit plate
  }
}

// ============================================================
// BACK DOOR (on the monitor back wall)
// ============================================================
module back_door_cut() { translate([12, Db-wall-1, door_z0]) cube([W-24, wall+2, door_top-door_z0]); }
module door() {
  ow=W-24; doh=door_top-door_z0; fh=doh+12; lh=doh-0.6;
  difference() {
    union() {
      translate([-ow/2-6, -fh/2, 0]) cube([ow+12, fh, 2.5]);
      translate([-ow/2+0.3, -lh/2, -2.5]) cube([ow-0.6, lh, 2.6]);
      for (rx=[-ow/2+8, ow/2-20]) for (ry=[-lh/2-0.2, lh/2-0.3])
        translate([rx, ry, -2.5]) cube([12, 0.5, 2.6]);
    }
    for (i=[-3:3]) translate([i*11-1.5, -18, -3]) cube([3, 36, 9]);
    translate([0, fh/2, -3]) cylinder(d=13, h=9);
  }
}

// ============================================================
// FLOOR + feet
// ============================================================
module bottom_open() { translate([wall, wall, -1]) cube([W-2*wall, Db-2*wall, wall+2]); }
module floor_ledge() {
  lt=1.5; lp=1.8;
  translate([wall, wall, wall+0.8]) cube([W-2*wall, lp, lt]);
  translate([wall, Db-wall-lp, wall+0.8]) cube([W-2*wall, lp, lt]);
  translate([wall, wall, wall+0.8]) cube([lp, Db-2*wall, lt]);
  translate([W-wall-lp, wall, wall+0.8]) cube([lp, Db-2*wall, lt]);
}
module floor_nubs() {
  np=1.15;
  for (x=[W*0.3, W*0.7]) { translate([x-3, wall, 0]) cube([6,np,1.4]); translate([x-3, Db-wall-np, 0]) cube([6,np,1.4]); }
  translate([wall, Db/2-3, 0]) cube([np,6,1.4]); translate([W-wall-np, Db/2-3, 0]) cube([np,6,1.4]);
}
module bottom_plate() {
  difference() {
    translate([wall+0.75, wall+0.75, 0]) cube([W-2*wall-1.5, Db-2*wall-1.5, wall]);
    translate([W/2, Db-22, -1]) cylinder(d=14, h=wall+2);
  }
}
module feet() { for (x=[16, W-16], yy=[16, Db-16]) translate([x, yy, -2.5]) cylinder(d=13, h=2.6); }

// ============================================================
// POWER + seam dowels
// ============================================================
module power_slot() {
  translate([pwr_side>0 ? W-wall-2 : -2, pwr_depth, pwr_z]) rotate([0,90,0])
    hull() for (dz=[-4,4], dy=[-2.5,2.5]) translate([dz,dy,0]) cylinder(d=13, h=wall+4);
}
module dowel_holes() {
  for (p=[[3,12],[3,H-16],[Db-3,12],[Db-3,H-16]])
    translate([cut_x-6, p[0], p[1]]) rotate([0,90,0]) cylinder(d=2.0, h=12);
}

// ============================================================
// RENDER
// ============================================================
if (part=="shell") shell();
if (part=="shell_left")  intersection() { shell(); translate([-1,-1,-3]) cube([cut_x+1, Db+2, H+4]); }
if (part=="shell_right") intersection() { shell(); translate([cut_x,-1,-3]) cube([W-cut_x+1, Db+2, H+4]); }
if (part=="bottom")    bottom_plate();
if (part=="door")      door();
if (part=="wedge")     wedge();
if (part=="cam_cradle") cam_cradle();
if (part=="assembly") {
  color("Gainsboro") shell();
  color("gray")      bottom_plate();
  color("dimgray")   translate([W/2, Db+0.5, (door_z0+door_top)/2]) rotate([-90,0,0]) door();
}
