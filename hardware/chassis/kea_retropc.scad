// ============================================================
// KEA — retro DESKTOP PC (horizontal case + swivel monitor)
//
// The classic 90s setup, shrunk:
//   * a low horizontal CASE on the desk, with a FLAT KEYBOARD built
//     into its front top (5 buttons + 2 toggles + encoder) and "KEA"
//     on the front. Houses the swivel servo, the PCA9685, the LM2596
//     buck and the 4xAA pack (sound is a Bluetooth speaker).
//   * a MONITOR sitting on a TURNTABLE on the case's back top. The
//     monitor holds the Pi + ELEGOO screen (they bolt together, so
//     they live here), behind a hooded, recessed CRT screen, with a
//     pan/tilt camera on its roof.
//   * a MOTORIZED SWIVEL: an MG90S in the case turns the turntable
//     (and the monitor) left/right, limited to +/-90 deg so the
//     internal cable just flexes (no slip ring needed).
//
// Print each `part`, export STL, run check_retropc.py after edits.
// Servos want their OWN 5 V — never the Pi header.
// ============================================================

part = "monitor";  // "case" | "case_floor" | "turntable" | "monitor"
                // | "monitor_lid" | "monitor_door" | "wedge" | "cam_cradle"
                // | "assembly"
                //
                // The only split is the monitor's LID — and it isn't glued,
                // it LATCHES on, so the Pi drops straight in from the top.
                // Print orientations:
                //   case        UPSIDE DOWN (top face on the bed) — crisp
                //               keyboard face, open bottom needs no support.
                //   monitor     ON ITS BACK — the screen face lies flat.
                //   monitor_lid the model already drops it to z=0: print it
                //               as it comes, latch arms pointing up.
                //   others      flat, as they sit.

$fn = 64;

// ---------- Case (the horizontal computer) ----------
W    = 150;   // width
Dc   = 150;   // depth
Hc   = 48;    // height (low desktop profile)
wall = 3;
r_c  = 6;     // case edge rounding

// keyboard zone = front top of the case (depth 0..kb_d)
kb_d = 60;
// turntable zone = back top, centered here:
turn_y = 105;
turn_r = 38;      // turntable radius
turn_bolt = 26;   // bolt circle for the monitor foot

// ---------- Controls on the flat keyboard ----------
btn_d = 12.4;
enc_d = 7.5;
tog_d = 6.4;
kb_btn_row = 38;
kb_te_row = 20;   // depths on the keyboard
tog1_x = 16;      // two toggles, front row left — spread apart
tog2_x = 48;
enc_x = W - 16;   // encoder, front row far right
btn_dx = 22;      // spacing of the FIVE buttons (back row), centred on W/2

// ---------- Swivel servo (SG92R micro servo, in the case, shaft up) ----------
// Body 23 x 13 x 27 mm. It hangs UNDER the case top: flanges screw to the
// top's underside, output shaft + horn poke up through the top into the
// turntable. Body dangles in the cavity, guided by a collar.
sv_L = 23.2;
sv_W = 13.5;      // SG92R is 13 mm wide (was 12.8 — too tight)
sv_body_h = 22.8; // body height below the flanges
sv_screw = 28;    // flange screw-hole spacing (M2)

// ---------- Monitor ----------
Wm   = 100;   // monitor width
Dm   = 72;    // monitor depth (was 66 — deeper for the Pi+display+GPIO-adapter
              // stack; the cradle/wedge now take a thicker stack)
recl = 8;     // slight fixed recline (pan is motorized, tilt is fixed)
slen = 94;    // screen slope length (85.5 display + shelf)
mcap = 8;
mfoot= 6;     // monitor foot thickness (bolts to the turntable)
// The GPIO Winkel-Adapter breaks the header out sideways, so ONE side of the
// stack (the GPIO edge, vertical in portrait) needs a clear channel for the
// horizontal pins + wires. That side's cradle guide is kept short and the
// stack is NOT clamped to the wall there.
gpio_side = 1;   // -1 = left, +1 = right
sym = slen*sin(recl);
szm = mfoot + slen*cos(recl);
Hm  = szm + mcap;             // monitor height (above its foot)
scr_cut = [51,75];

// ---------- Removable monitor LID (how the Pi gets in) ----------
// The back door alone was hopeless: its opening ended up shorter than the
// 85.5 mm stack, so the Pi could never pass through it. Instead the monitor's
// top lifts off and the whole stack is lowered straight down into the cradle.
// The seam sits above the screen aperture and above the back door, so it
// crosses only blank bezel. A register rim keeps the lid located; two
// external cantilever latches on the side walls hold it down — press them
// outward with a thumb to release, no tools, no screws.
lid_z      = 93;    // horizontal split height (aperture top ~89.7, door top ~91)
lid_rim    = 6;     // how far the register rim stands into the lid
lid_gap    = 0.3;   // rim-to-lid clearance
latch_w    = 12;    // latch arm width
latch_drop = 22;    // how far the arm hangs below the seam (window at 13..18,
                    // so the tip continues past it and gives a thumb pad)
latch_p    = 2.6;   // how far the arm stands proud of the wall
latch_win  = 5;     // window height in the arm
catch_p    = 1.8;   // how far the catch bump sticks out

// Rim on the BODY: a thin shell standing above the seam that the lid slips
// over, so it can't slide about.
module lid_register() {
  intersection() {
    difference() {
      mon_body(inset = wall + lid_gap);
      mon_body(inset = wall + lid_gap + 1.6);
    }
    translate([-1, -1, lid_z]) cube([Wm + 2, Dm + 2, lid_rim]);
  }
}
// Catch bumps on the BODY's outer side walls, with a lead-in ramp on top.
module lid_catches() {
  for (sx = [-1, 1]) {
    x = (sx < 0) ? wall : Wm - wall;      // sit on the outer wall face
    translate([sx < 0 ? -0.4 : Wm - catch_p + 0.4, Dm/2 - 4, lid_z - 13])
      cube([catch_p, 8, latch_win]);
    // ramp so the latch rides on during closing
    translate([sx < 0 ? -0.4 : Wm - catch_p + 0.4, Dm/2 - 4, lid_z - 13 + latch_win])
      rotate([0, sx < 0 ? -90 : 90, 0])
        linear_extrude(catch_p)
          polygon([[0, 0], [0, sx < 0 ? catch_p : -catch_p], [5, 0]]);
  }
}
// Cantilever latch arms on the LID, each with a window that snaps the catch.
module lid_latches() {
  for (sx = [-1, 1])
    difference() {
      translate([sx < 0 ? -latch_p : Wm - 0.6, Dm/2 - latch_w/2, lid_z - latch_drop])
        cube([latch_p + 0.6, latch_w, latch_drop + 4]);
      // the window the catch clicks into
      translate([sx < 0 ? -latch_p - 1 : Wm - 1.6, Dm/2 - 4.4, lid_z - 13 - 0.3])
        cube([latch_p + 3, 8.8, latch_win + 0.6]);
      // thumb bevel at the tip, so it's obvious where to push
      translate([sx < 0 ? -latch_p - 1 : Wm - 1.6, Dm/2 - latch_w/2 - 1,
                 lid_z - latch_drop - 1])
        rotate([0, sx < 0 ? 20 : -20, 0]) cube([latch_p + 3, latch_w + 2, 3]);
    }
}

// ---------- Camera turret (Adafruit Mini Pan-Tilt) ----------
turret_y = 46;      // on the monitor roof, toward the back
turret_holes = 18;

// ---------- Pi cooling fan (in the monitor, on the back door) ----------
fan_sz    = 30;     // fan body edge (30x30x7 typical) — set to your fan
fan_holes = 24;     // screw-hole spacing (24 for 30 mm, 20 for 25 mm)
fan_screw = 2.6;    // M2.5 self-tapping into the door bosses


// ---------- Power inlet: runs to the Pi IN THE MONITOR (not the case) ----------
mon_pwr_side  = -1; // -1 left wall, 1 right wall of the monitor
mon_pwr_z     = 80; // high up the side wall — the Pi's power edge sits near the
                    // TOP of the slope, like the original chassis (calibrate)
mon_pwr_depth = 30; // from the screen face toward the back

// ============================================================
// CASE
// ============================================================
side_c = [[0,0],[Dc,0],[Dc,Hc],[0,Hc]];
module rc_side(inset=0) offset(r=r_c) offset(delta=-r_c-inset) polygon(side_c);
module rc_plan(inset=0) offset(r=r_c) offset(delta=-r_c-inset) square([W,Dc]);
module case_body(inset=0) intersection() {
  rotate([90,0,90]) linear_extrude(W) rc_side(inset);
  linear_extrude(Hc+1) rc_plan(inset);
}

module case() {
  difference() {
    union() {
      difference() { case_body(); case_body(inset=wall); }
      case_floor_ledge();
      case_feet();
      servo_collar();
    }
    keyboard_holes();
    turntable_socket();
    case_back_access();
    case_bottom_open();
    // NOTE: no power inlet on the case — the PSU cable runs to the Pi in
    // the monitor (see mon_power_slot). The case only needs a small notch
    // in the back access for the servo + speaker + button leads.
    // power LED (status)
    translate([W-20, 1.5, Hc-10]) rotate([-90,0,0]) cylinder(d=3.2, h=wall+4, center=true);
    // KEA wordmark, debossed big and centered on the front face (where the
    // speaker grille used to be). No mirror — reads correctly from the front.
    translate([W/2, 1.6, Hc/2]) rotate([90,0,0])
      linear_extrude(1.6) text("KEA", size=20, halign="center", valign="center",
                               font="DejaVu Sans:style=Bold");
  }
}

module keyboard_holes() {
  for (tx=[tog1_x, tog2_x]) translate([tx, kb_te_row, Hc-1]) cylinder(d=tog_d, h=wall+4);
  translate([enc_x, kb_te_row, Hc-1]) cylinder(d=enc_d, h=wall+4);
  for (bx=[W/2-2*btn_dx, W/2-btn_dx, W/2, W/2+btn_dx, W/2+2*btn_dx])
    translate([bx, kb_btn_row, Hc-1]) cylinder(d=btn_d, h=wall+4);
}
// (Speaker grille + mount removed — Kea uses the Bluetooth speaker.)
// Case-top interface: a shallow seat the turntable disc rotates in, the
// servo output+horn hole, and 2 flange screw holes (servo mounts from the
// inside, flanges up against the top's underside).
module turntable_socket() {
  translate([W/2, turn_y, Hc-2]) cylinder(r=turn_r+0.6, h=2.4);         // disc seat
  translate([W/2, turn_y, Hc-wall-1]) cylinder(d=16, h=wall+2);         // output+horn+cable
  for (s=[-1,1]) translate([W/2+s*sv_screw/2, turn_y, Hc-wall-1])
    cylinder(d=2.4, h=wall+2);                                          // flange screws
}
// Collar hanging from the top's underside that guides the dangling servo
// body (keeps it from wobbling on its two flange screws).
module servo_collar() {
  translate([W/2, turn_y, Hc-wall-10])
    difference() {
      translate([-(sv_L/2+2), -(sv_W/2+2), 0]) cube([sv_L+4, sv_W+4, 10]);
      translate([-(sv_L/2+0.3), -(sv_W/2+0.3), -1]) cube([sv_L+0.6, sv_W+0.6, 12]);
    }
}
module case_back_access() {                     // wiring access on the back
  translate([20, Dc-wall-1, 8]) cube([W-40, wall+2, Hc-16]);
}
module case_bottom_open() { translate([wall,wall,-1]) cube([W-2*wall, Dc-2*wall, wall+2]); }
module case_floor_ledge() {
  lt=1.5; lp=1.8;
  translate([wall,wall,wall+0.8]) cube([W-2*wall, lp, lt]);
  translate([wall,Dc-wall-lp,wall+0.8]) cube([W-2*wall, lp, lt]);
  translate([wall,wall,wall+0.8]) cube([lp, Dc-2*wall, lt]);
  translate([W-wall-lp,wall,wall+0.8]) cube([lp, Dc-2*wall, lt]);
}
module case_feet() { for (x=[18,W-18], y=[18,Dc-18]) translate([x,y,-2.5]) cylinder(d=14,h=2.6); }
// Bottom plate. Mount the boards to it FIRST (outside the case), then slot it
// in. Cable-tie pairs strap the three boards laid out left-to-right across the
// back — they don't overlap and all sit below whatever hangs from the top:
//   battery 62x56.5  @ x~6-68    (left)
//   PCA9685 25x62.5  @ x~73-99   (centre)
//   LM2596  36x66    @ x~104-140 (right)
module case_floor() {
  difference() {
    translate([wall+0.75, wall+0.75, 0]) cube([W-2*wall-1.5, Dc-2*wall-1.5, wall]);
    translate([W/2, Dc-22, -1]) cylinder(d=14, h=wall+2);   // finger hole
    for (a = [[37,85,22], [86,85,9], [122,85,13]])          // [cx, cy, half-span]
      for (s = [-1,1])
        translate([a[0]+s*a[2], a[1]-8, -1]) cube([3, 16, wall+2]);
  }
}

// ============================================================
// TURNTABLE — rides in the case seat, driven by the servo horn;
// the monitor foot bolts to its top. Cable passes through the center.
// ============================================================
module turntable() {
  difference() {
    union() {
      cylinder(r=turn_r, h=4);
      cylinder(r=turn_r-3, h=6);                 // raised hub
    }
    translate([0,0,-1]) cylinder(d=18, h=3);     // pocket for the servo horn (underside)
    translate([0,0,-3]) cylinder(d=6.5, h=14);   // central cable hole (through)
    // servo-horn screw holes (screw the horn up into the disc)
    for (a=[0:90:270]) rotate([0,0,a]) translate([7,0,1]) cylinder(d=2.0, h=8);
    // monitor-foot bolt holes
    for (a=[0:90:270]) rotate([0,0,a]) translate([turn_bolt/2,0,-1]) cylinder(d=2.6, h=10);
  }
}

// ============================================================
// MONITOR — Pi + ELEGOO live here. Foot bolts to the turntable.
// ============================================================
side_m = [[0,0],[Dm,0],[Dm,Hm],[sym,Hm],[sym,szm],[0,mfoot]];
module rm_side(inset=0) offset(r=6) offset(delta=-6-inset) polygon(side_m);
module rm_plan(inset=0) offset(r=8) offset(delta=-8-inset) square([Wm,Dm]);
module mon_body(inset=0) intersection() {
  rotate([90,0,90]) linear_extrude(Wm) rm_side(inset);
  linear_extrude(Hm+1) rm_plan(inset);
}
module screen_frame() translate([0, 0, mfoot]) rotate([-recl,0,0]) children();

module monitor() {
  difference() {
    union() {
      difference() { mon_body(); mon_body(inset=wall); }
      screen_frame() mon_bezel();
      screen_frame() mon_cradle();
      // foot bolt bosses
      for (a=[0:90:270]) rotate([0,0,a]) translate([Wm/2,Dm/2,0]) {}
    }
    screen_frame() mon_screen_cut();
    mon_back_door_cut();
    mon_bottom_open();
    mon_foot_bolts();
    turret_mount();
    mon_power_slot();     // PSU cable enters here, straight to the Pi
    mon_intake_vents();   // fresh-air intake for the fan
  }
}


// PSU plugs into the Pi through a slot in the monitor's side wall.
// The monitor swivels +/-90, so leave a service loop in the cable.
module mon_power_slot() {
  translate([mon_pwr_side>0 ? Wm-wall-2 : -2, mon_pwr_depth, mfoot + mon_pwr_z])
    rotate([0,90,0])
      hull() for (dz=[-4,4], dy=[-2.5,2.5]) translate([dz,dy,0]) cylinder(d=13, h=wall+4);
}
// Low side-wall intake louvers so the fan pulls fresh air across the Pi.
module mon_intake_vents() {
  for (s=[-1,1], k=[0:3])
    translate([s>0 ? Wm-wall-1 : -1, 14 + k*7, mfoot+8])
      cube([wall+2, 2.2, 22]);
}
module mon_bezel() {
  bw=9; bz=3.5; ow=scr_cut[0]+2*bw; oh=scr_cut[1]+2*bw;
  translate([Wm/2,0,slen/2]) rotate([-90,0,0]) linear_extrude(bz)
    difference() {
      offset(r=4) offset(delta=-4) square([ow,oh],center=true);
      offset(r=2) offset(delta=-2) square([scr_cut[0]+5, scr_cut[1]+5],center=true);
    }
  bw2=9; hz=slen/2+scr_cut[1]/2+bw2;
  translate([Wm/2,0,hz]) rotate([-90,0,0]) linear_extrude(12)
    offset(r=3) offset(delta=-3) square([scr_cut[0]+2*bw2+6, 10], center=true);
}
module mon_screen_cut() {
  hull() {
    translate([Wm/2,-0.2,slen/2]) cube([scr_cut[0]+6,0.1,scr_cut[1]+6],center=true);
    translate([Wm/2,4,slen/2]) cube([scr_cut[0],0.1,scr_cut[1]],center=true);
  }
  translate([Wm/2,4,slen/2]) cube([scr_cut[0], wall+10, scr_cut[1]], center=true);
}
module mon_cradle() {
  gx0=(Wm-56)/2-3.5; gx1=(Wm+56)/2+0.5;
  cd=37;                                    // cradle depth — Pi+display+GPIO adapter
  translate([wall,wall,2.5]) cube([Wm-2*wall,cd,4]);   // shelf
  // Side guides: full on the non-GPIO side; SHORT (base only) on the GPIO
  // side so the sideways header + wires have an open channel to the wall.
  gh_short = 14;
  translate([gx0,wall,4]) cube([3, cd, gpio_side<0 ? gh_short : 58]);
  translate([gx1,wall,4]) cube([3, cd, gpio_side>0 ? gh_short : 58]);
  // back flanges (the wedge bears on these) — split for the ribbon path
  translate([gx0,wall+cd-3,8]) cube([21,3,42]);
  translate([gx1+3-21,wall+cd-3,8]) cube([21,3,42]);
}
module mon_back_door_cut() {
  translate([12, Dm-wall-1, mfoot+6]) cube([Wm-24, wall+2, Hm-mfoot-16]);
}
module monitor_door() {
  ow=Wm-24; doh=Hm-mfoot-16; fh=doh+12; lh=doh-0.6;
  difference() {
    union() {
      translate([-ow/2-6,-fh/2,0]) cube([ow+12, fh, 2.5]);
      translate([-ow/2+0.3,-lh/2,-2.5]) cube([ow-0.6, lh, 2.6]);
      // fan screw bosses on the inside face (self-tap M2.5)
      for (x=[-1,1], y=[-1,1])
        translate([x*fan_holes/2, y*fan_holes/2 - fh*0.12, 2.5]) cylinder(d=6, h=4);
    }
    // --- fan aperture with a spoked grille (fan blows onto the Pi) ---
    translate([0, -fh*0.12, -3]) {
      difference() {
        cylinder(d=fan_sz-3, h=9);
        for (a=[0:60:300]) rotate([0,0,a]) translate([-1.4,-fan_sz/2,-1]) cube([2.8, fan_sz, 11]);
      }
      for (x=[-1,1], y=[-1,1]) translate([x*fan_holes/2, y*fan_holes/2, -1]) cylinder(d=fan_screw, h=14);
    }
    // a couple of exhaust slots up top + finger scallop
    for (i=[-2:2]) translate([i*11-1.5, fh*0.30, -3]) cube([3, 16, 9]);
    translate([0,fh/2,-3]) cylinder(d=12,h=9);
  }
}
module mon_bottom_open() { translate([wall,wall,-1]) cube([Wm-2*wall, Dm-2*wall, mfoot+1]); }
module mon_foot_bolts() {
  for (a=[0:90:270]) rotate([0,0,a]) translate([turn_bolt/2 + (Wm/2-turn_bolt/2)*0, 0, -1]) {}
  // bolt holes matching the turntable bolt circle, centered under the monitor
  translate([Wm/2, Dm/2, 0])
    for (a=[0:90:270]) rotate([0,0,a]) translate([turn_bolt/2,0,-1]) cylinder(d=2.6, h=mfoot+2);
}
module turret_mount() {
  translate([Wm/2-11, turret_y-8, Hm-wall-1]) cube([22,16,wall+2]);
  for (s=[-1,1]) translate([Wm/2+s*turret_holes/2, turret_y+10, Hm-wall-1]) cylinder(d=2.6,h=wall+2);
}
module wedge() {
  difference() {
    union() { rotate([90,0,90]) linear_extrude(56) polygon([[0,0],[1.5,0],[13,58],[0,58]]);
      translate([0,0,52]) cube([56,11,6]); }
    translate([16,-1,8]) cube([24,13,40]);
  }
}
module cam_cradle() {
  difference() {
    translate([-14,-13,0]) cube([28,26,2.5]);
    for (x=[-1,1],y=[-1,1]) translate([x*21/2,y*12.5/2,-1]) cylinder(d=2.2,h=5);
    translate([-9,-13.5,-1]) cube([18,8,5]);
  }
}

// ============================================================
// RENDER
// ============================================================
if (part=="case") case();
if (part=="case_floor") case_floor();
if (part=="turntable")  turntable();
// The monitor prints in two pieces so the Pi can be lowered in from above:
// the body (open top) and the lid that latches onto it.
if (part=="monitor") {
  intersection() { monitor(); translate([-1,-1,-1]) cube([Wm+2, Dm+2, lid_z+1]); }
  lid_register();
  lid_catches();
}
if (part=="monitor_lid") {
  translate([0, 0, -lid_z]) {          // sit the lid flat for printing
    intersection() { monitor(); translate([-1,-1,lid_z]) cube([Wm+2, Dm+2, Hm-lid_z+2]); }
    lid_latches();
  }
}
if (part=="monitor_whole") monitor();   // reference / preview only
if (part=="monitor_door") monitor_door();
if (part=="wedge")      wedge();
if (part=="cam_cradle") cam_cradle();
if (part=="assembly") {
  color("Gainsboro") case();
  color("gray") translate([0,0,0]) case_floor();
  color("tan") translate([W/2, turn_y, Hc]) turntable();
  color("Gainsboro") translate([W/2-Wm/2, turn_y-Dm/2, Hc+4]) monitor();
  color("Silver")    translate([W/2-Wm/2, turn_y-Dm/2, Hc+4]) lid_latches();
}
