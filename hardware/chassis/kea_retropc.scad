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

part = "case";  // "case" | "case_floor" | "turntable"
                // | "monitor_left" | "monitor_right" | "monitor" (preview)
                // | "monitor_door" | "wedge" | "cam_cradle" | "assembly"
                //
                // The monitor splits VERTICALLY into two halves and is BOLTED
                // together through ears at the seam — no latches, no glue.
                // Put the Pi into one half, close the other over it, drop in
                // 3 M3 bolts. Undo them to open.
                // Print orientations:
                //   case          UPSIDE DOWN (top face on the bed) — crisp
                //                 keyboard face, open bottom needs no support.
                //   monitor_left/ each lying on its flat CUT FACE, so every
                //   monitor_right feature prints as a vertical wall: no
                //                 supports anywhere.
                //   others        flat, as they sit.

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
sv_W = 13.5;        // SG92R is 13 mm wide (was 12.8 — too tight)
sv_body_h = 22.8;   // body height below the flanges
sv_screw = 28;      // flange screw-hole spacing (M2)
sv_flange_L = 32.5; // TIP-TO-TIP across the mounting tabs — the servo is
                    // T-shaped, so this, not sv_L, is what must clear
sv_guide_h  = 12;   // how far the guide ribs hang below the deck

// ---------- Monitor ----------
// The stack is NOT centred: the GPIO side needs a wide channel for the
// sideways header, but the power side only needs enough room for the plug
// to reach the Pi's jack through the wall. So the cassette is pushed up
// against the power-side wall and the monitor is that much narrower.
gapP = 8;     // power side. NOT flush any more: the Pi's 3.5 mm headphone
              // jack shares this edge with the micro-USB and stands proud of
              // the board, so it needs clearance — and a plug needs more.
              // Flush (0) crushed it against the wall.
gapG = 17;    // GPIO-side gap: header pins + dupont shells
Wm   = wall + gapP + 56 + gapG + wall;   // = 86 (was 100)
// Stack thickness reality check: Pi PCB + GPIO header + the Winkel-Adapter
// + the display and its socket comes out far thicker than the 33 mm this was
// built around — it printed too tight to assemble. Give the channel real room.
stack_t = 46;   // depth of the cradle channel (measure yours; add ~4 spare)
Dm   = 86;      // monitor depth (was 72 — too tight for the stack)
// Everything that must line up with the display — cradle, screen aperture,
// bezel, hood — hangs off this, not off Wm/2.
stack_cx = wall + gapP + 28;
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
// Screen aperture. The old 51x75 centred on the panel mid-point sat ~2.5 mm
// low relative to where the display actually rests on the cradle shelf, and
// was only ~1 mm bigger than the active area — so the top of the picture was
// hidden behind the frame. Bigger, and centred on the STACK, not the panel.
scr_cut = [54, 80];
scr_cy  = 6.5 + 85.5/2;   // shelf top + half the display = true screen centre

// ---------- Monitor split: two halves you bolt together ----------
// Back to the vertical half-split (much easier to print than a lid), and
// joined with plain BOLT HOLES rather than latches or glue: each half grows
// a small ear at the seam, the ears sit side by side, and one bolt passes
// straight through both. Put the Pi in one half, close the other over it,
// drop the bolts in. Undo them to open.
// Seam sits in the GPIO-side margin, just outside the bezel (which now spans
// stack_cx +/- 34.5, i.e. 3.5..72.5) and inside the body edge.
mcut_x   = 75;      // GPIO margin, just outside the bezel (ends 73)
ear_len  = 11;      // right ear must stay inside Wm: 75+11 = 86 < 87
ear_w    = 10;      // ear width
ear_p    = 7;       // how far it stands off the surface
join_d   = 3.4;     // clearance hole — M3 bolt straight through both ears
// Two on the roof, one high on the back wall — all clear of the back door,
// the camera turret and the screen.
roof_ears = [24, 58];    // y positions on the roof
back_ear_z = 100;        // z on the back wall, above the door (door tops ~91)

module join_ears(side) {          // side = -1 left half, +1 right half
  x0 = (side < 0) ? mcut_x - ear_len : mcut_x;
  for (y = roof_ears)             // sitting on the roof
    translate([x0, y - ear_w/2, Hm - 1]) cube([ear_len, ear_w, ear_p + 1]);
  translate([x0, Dm - 1, back_ear_z - ear_w/2])   // on the back wall
    cube([ear_len, ear_p + 1, ear_w]);
}
module join_holes() {             // one bolt through both ears, along x
  for (y = roof_ears)
    translate([mcut_x - ear_len - 2, y, Hm + ear_p/2])
      rotate([0, 90, 0]) cylinder(d = join_d, h = 2*ear_len + 4);
  translate([mcut_x - ear_len - 2, Dm + ear_p/2, back_ear_z])
    rotate([0, 90, 0]) cylinder(d = join_d, h = 2*ear_len + 4);
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
// The 3.5 mm audio jack sits on the SAME edge as the micro-USB, roughly
// 43 mm along it, and sticks out past the board — so it gets its own
// aperture in the same wall. Measure yours at dry-fit and set mon_aud_z.
mon_aud_z     = 37; // along the slope (power jack is at mon_pwr_z)
mon_aud_d     = 11; // clear enough for a 3.5 mm plug body, not just the jack

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

// NOTE: every cutter must START BELOW the material and END ABOVE it. These
// used to begin at Hc-1 — 1 mm below the TOP face — so they only removed the
// top 1 mm of the 3 mm deck and printed with 2 mm of plastic in the bottom of
// every hole. Start at Hc-wall-2 and run past the surface.
module keyboard_holes() {
  z0 = Hc - wall - 2;
  h  = wall + 4;
  for (tx=[tog1_x, tog2_x]) translate([tx, kb_te_row, z0]) cylinder(d=tog_d, h=h);
  translate([enc_x, kb_te_row, z0]) cylinder(d=enc_d, h=h);
  for (bx=[W/2-2*btn_dx, W/2-btn_dx, W/2, W/2+btn_dx, W/2+2*btn_dx])
    translate([bx, kb_btn_row, z0]) cylinder(d=btn_d, h=h);
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
// The SG92R is T-shaped: its mounting flanges stick out past the body on
// both ends (32.5 mm tip-to-tip vs a 23 mm body). The old collar was a
// closed rectangle sized to the BODY, so the flanges could never pass
// through it — the servo physically could not be fitted without cutting
// the case open. Now it's two ribs that only pinch the narrow (y) faces
// and leave the x direction wide open, so the servo goes straight up from
// the open bottom and its flanges land flat against the deck underside.
module servo_collar() {
  for (sy = [-1, 1])
    translate([W/2 - sv_flange_L/2,
               turn_y + sy*(sv_W/2 + 0.3) - (sy < 0 ? 2 : 0),
               Hc - wall - sv_guide_h])
      cube([sv_flange_L, 2, sv_guide_h]);
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
// Feet live on the BOTTOM PLATE, not the shell: the shell's underside is an
// open cavity there, so pads placed on it would print in mid-air. The plate
// is the surface that actually meets the desk.
module case_feet() {
  for (x=[20, W-20], y=[20, Dc-20])
    translate([x, y, -2.6]) cylinder(d=14, h=2.6);
}
// Bottom plate. Mount the boards to it FIRST (outside the case), then slot it
// in. Cable-tie pairs strap the three boards laid out left-to-right across the
// back — they don't overlap and all sit below whatever hangs from the top:
//   battery 62x56.5  @ x~6-68    (left)
//   PCA9685 25x62.5  @ x~73-99   (centre)
//   LM2596  36x66    @ x~104-140 (right)
module case_floor() {
  difference() {
    union() {
      translate([wall+0.75, wall+0.75, 0]) cube([W-2*wall-1.5, Dc-2*wall-1.5, wall]);
      case_feet();                    // rubber-pad bosses, on the real underside
    }
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
      // Bezel + hood, trimmed to the body width. With the cassette flush to
      // the power wall the frame would otherwise hang off that edge; this
      // just squares it off there (asymmetric bezel, thin on the power side).
      intersection() {
        screen_frame() mon_bezel();
        translate([0.8, -60, -20]) cube([Wm - 1.6, Dm + 120, Hm + 60]);
      }
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
  // headphone jack, same wall, further down the same board edge
  translate([mon_pwr_side>0 ? Wm-wall-2 : -2, mon_pwr_depth, mfoot + mon_aud_z])
    rotate([0,90,0])
      hull() for (dz=[-2,2]) translate([dz,0,0]) cylinder(d=mon_aud_d, h=wall+4);
}
// Low side-wall intake louvers so the fan pulls fresh air across the Pi.
module mon_intake_vents() {
  for (s=[-1,1], k=[0:3])
    translate([s>0 ? Wm-wall-1 : -1, 14 + k*7, mfoot+8])
      cube([wall+2, 2.2, 22]);
}
// Bezel + hood follow scr_cy so they frame the aperture where it actually
// is. The frame's inner edge is held OUTSIDE the aperture, so it can never
// creep over the picture; the hood is a slim brow well clear of the glass.
module mon_bezel() {
  bw=7; bz=1.0; ow=scr_cut[0]+2*bw; oh=scr_cut[1]+2*bw;   // bz was 2.5:
                    // a flatter frame so it doesn't shadow the picture
  translate([stack_cx,0,scr_cy]) rotate([-90,0,0]) linear_extrude(bz)
    difference() {
      offset(r=4) offset(delta=-4) square([ow,oh],center=true);
      offset(r=2) offset(delta=-2) square([scr_cut[0]+4, scr_cut[1]+4],center=true);
    }
  hz = scr_cy + scr_cut[1]/2 + bw + 3;
  if (hz + 5 < slen)                       // only if it clears the panel top
    translate([stack_cx,0,hz]) rotate([-90,0,0]) linear_extrude(9)
      offset(r=3) offset(delta=-3) square([scr_cut[0]+2*bw, 8], center=true);
}
// One clean straight-through opening, and the panel is THINNED around it so
// the picture isn't looking out of a deep well. `face_t` is what's left of
// the wall right around the aperture; the full `wall` remains everywhere
// else, so the panel keeps its stiffness.
face_t   = 1.4;    // frame thickness at the screen (was the full 3 mm wall)
face_pad = 5;      // how far the thinned area extends past the aperture
                   // (kept small so the relief stays on the panel)
module mon_screen_cut() {
  translate([stack_cx, wall/2, scr_cy])
    cube([scr_cut[0], wall + 12, scr_cut[1]], center=true);
  // relieve the back of the panel around the opening: removes wall-face_t
  // of depth, so the display sits closer to the front surface
  translate([stack_cx, face_t + (wall - face_t)/2 + 0.01, scr_cy])
    cube([scr_cut[0] + 2*face_pad, wall - face_t, scr_cut[1] + 2*face_pad],
         center=true);
}
module mon_cradle() {
  gx0=stack_cx-28-3.5; gx1=stack_cx+28+0.5;
  cd=stack_t;                               // cradle depth — Pi+display+GPIO adapter
  gh_short = 14;
  translate([wall,wall,2.5]) cube([Wm-2*wall,cd,4]);   // shelf
  // Side guides. Where the stack is flush to the wall there is no room for a
  // rib and none is needed — the wall face locates it. The GPIO side's guide
  // stays short so the sideways header has an open channel.
  if (gx0 >= wall + 0.5)
    translate([gx0,wall,4]) cube([3, cd, gpio_side<0 ? gh_short : 58]);
  if (gx1 + 3 <= Wm - wall - 0.5)
    translate([gx1,wall,4]) cube([3, cd, gpio_side>0 ? gh_short : 58]);
  // back flanges (the wedge bears on these) — split for the ribbon path
  translate([max(gx0, wall), wall+cd-3, 8]) cube([21,3,42]);
  translate([min(gx1+3-21, Wm-wall-21), wall+cd-3, 8]) cube([21,3,42]);
}
// Door stops 6 mm short of the seam, so the cut plane doesn't slice through
// the opening edge and leave a knife-edge on the left half. Its top also
// stops below the back seam-bolt ear (z 95..105) — the ear needs solid wall
// under it, and at the old height it overhung the opening.
door_x0 = 12;
door_w  = mcut_x - 6 - door_x0;
door_z0 = 16;
door_h  = 66;
module mon_back_door_cut() {
  translate([door_x0, Dm-wall-1, door_z0]) cube([door_w, wall+2, door_h]);
}
// Press-fit door. The lip drops into the opening with 0.3 mm clearance a
// side, and crush ribs on ALL FOUR edges stand 0.5 mm proud so it goes in
// with 0.2 mm interference per side and grips — the old version only had
// ribs top and bottom, so it could rattle sideways.
door_lip_t = 2.6;      // lip thickness (opening is `wall` = 3 deep)
door_rib   = 0.5;      // crush height
fan_cy     = -12;      // fan centre in the door's own frame
module monitor_door() {
  ow = door_w; doh = door_h;
  fh = doh + 12;                       // faceplate: 6 mm flange all round
  lw = ow - 0.6; lh = doh - 0.6;       // lip, 0.3 mm clearance per side
  difference() {
    union() {
      translate([-ow/2-6, -fh/2, 0]) cube([ow+12, fh, 2.5]);          // faceplate
      translate([-lw/2, -lh/2, -door_lip_t]) cube([lw, lh, door_lip_t]);
      // crush ribs — two per edge, all four edges
      for (x = [-lw/2+8, lw/2-20]) {
        translate([x, -lh/2-door_rib, -door_lip_t]) cube([12, door_rib, door_lip_t]);
        translate([x,  lh/2,          -door_lip_t]) cube([12, door_rib, door_lip_t]);
      }
      for (y = [-lh/2+8, lh/2-20]) {
        translate([-lw/2-door_rib, y, -door_lip_t]) cube([door_rib, 12, door_lip_t]);
        translate([ lw/2,          y, -door_lip_t]) cube([door_rib, 12, door_lip_t]);
      }
      // fan screw bosses on the inside face (self-tap M2.5)
      for (x=[-1,1], y=[-1,1])
        translate([x*fan_holes/2, fan_cy + y*fan_holes/2, 2.5]) cylinder(d=6, h=4);
    }
    // fan aperture with a spoked grille (fan blows onto the Pi)
    translate([0, fan_cy, -3]) {
      difference() {
        cylinder(d=fan_sz-3, h=9);
        for (a=[0:60:300]) rotate([0,0,a]) translate([-1.4,-fan_sz/2,-1]) cube([2.8, fan_sz, 11]);
      }
      for (x=[-1,1], y=[-1,1])
        translate([x*fan_holes/2, y*fan_holes/2, -1]) cylinder(d=fan_screw, h=14);
    }
    // exhaust slots above the fan, then a finger scallop clear of them
    for (i=[-2:2]) translate([i*9-1.5, 12, -3]) cube([3, 18, 9]);
    translate([0, fh/2, -3]) cylinder(d=12, h=9);
  }
}
module mon_bottom_open() { translate([wall,wall,-1]) cube([Wm-2*wall, Dm-2*wall, mfoot+1]); }
module mon_foot_bolts() {
  for (a=[0:90:270]) rotate([0,0,a]) translate([turn_bolt/2 + (Wm/2-turn_bolt/2)*0, 0, -1]) {}
  // bolt holes matching the turntable bolt circle, centered under the monitor
  translate([Wm/2, Dm/2, 0])
    for (a=[0:90:270]) rotate([0,0,a]) translate([turn_bolt/2,0,-1]) cylinder(d=2.6, h=mfoot+2);
}
// Roof opening for the turret. Only a camera ribbon (~16 x 0.3) and the
// servo leads pass through, so it's a tight slot rather than the big
// 22 x 16 hole it used to be — much less of the roof is left open.
turret_slot = [17, 6];
module turret_mount() {
  translate([stack_cx - turret_slot[0]/2, turret_y - turret_slot[1]/2, Hm-wall-1])
    cube([turret_slot[0], turret_slot[1], wall+2]);
  for (s=[-1,1]) translate([stack_cx+s*turret_holes/2, turret_y+10, Hm-wall-1])
    cylinder(d=2.6, h=wall+2);
}
module wedge() {
  difference() {
    union() { rotate([90,0,90]) linear_extrude(56) polygon([[0,0],[1.5,0],[13,58],[0,58]]);
      translate([0,0,52]) cube([56,11,6]); }
    translate([16,-1,8]) cube([24,13,40]);
  }
}
// Plate the Pi camera screws to, which in turn bolts to the pan-tilt kit.
// Grown to 32 x 30 and the ribbon notch pulled back, because at 28 x 26 the
// notch cut straight through the two lower screw holes and the kit holes.
cc_plate = [32, 30];
cc_notch = [16, 5];     // ribbon relief at the bottom edge
module cam_cradle() {
  difference() {
    translate([-cc_plate[0]/2, -cc_plate[1]/2, 0]) cube([cc_plate[0], cc_plate[1], 2.5]);
    // camera screw holes (fixed 21 x 12.5 pattern)
    for (x=[-1,1], y=[-1,1])
      translate([x*cam_holes[0]/2, y*cam_holes[1]/2, -1]) cylinder(d=2.2, h=5);
    // ribbon notch — stops short of the lower screw holes
    translate([-cc_notch[0]/2, -cc_plate[1]/2 - 0.5, -1])
      cube([cc_notch[0], cc_notch[1] + 0.5, 5]);
    // bolts up to the pan-tilt kit's top plate, in the clear top corners
    for (x=[-1,1]) translate([x*12, 11, -1]) cylinder(d=2.4, h=5);
  }
}

// ============================================================
// RENDER
// ============================================================
if (part=="case") case();
if (part=="case_floor") case_floor();
if (part=="turntable")  turntable();
// The monitor prints as two halves, each lying on its flat cut face (no
// supports). Bolt them together through the ears.
if (part=="monitor") monitor();      // whole, for preview
if (part=="monitor_left")
  difference() {
    union() {
      intersection() { monitor(); translate([-1,-1,-1]) cube([mcut_x+1, Dm+2, Hm+2]); }
      join_ears(-1);
    }
    join_holes();
  }
if (part=="monitor_right")
  difference() {
    union() {
      intersection() { monitor(); translate([mcut_x,-1,-1]) cube([Wm-mcut_x+1, Dm+2, Hm+2]); }
      join_ears(1);
    }
    join_holes();
  }
if (part=="monitor_door") monitor_door();
if (part=="wedge")      wedge();
if (part=="cam_cradle") cam_cradle();
if (part=="assembly") {
  color("Gainsboro") case();
  color("gray") translate([0,0,0]) case_floor();
  color("tan") translate([W/2, turn_y, Hc]) turntable();
  color("Gainsboro") translate([W/2-Wm/2, turn_y-Dm/2, Hc+4]) monitor();
}
