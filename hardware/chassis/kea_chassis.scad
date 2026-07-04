// ============================================================
// KEA — Mini bartop-arcade desk chassis
// Raspberry Pi 3 + ELEGOO 3.5" TFT (480x320) + 3 buttons +
// KY-040 encoder + toggle + SG90 pan-tilt camera on top.
//
// Render one part at a time (set `part`), export STL, print.
// All dimensions in mm. Tune the CALIBRATE block after
// measuring your actual Pi+display stack.
// ============================================================

part = "shell"; // "shell" | "bottom" | "door" | "sled" | "camstand" | "camplate" | "assembly"

$fn = 48;

// ---------- Main body ----------
W        = 110;   // exterior width
D        = 130;   // exterior depth
wall     = 3;     // wall thickness
front_h  = 35;    // front panel height
deck_y   = 48;    // control deck end (depth)
deck_z   = 52;    // control deck end (height)
tilt     = 25;    // screen tilt back from vertical (deg)
slen     = 100;   // screen panel length along slope (portrait display)
marq     = 24;    // marquee height above screen panel

sy = deck_y + slen*sin(tilt);      // top of slope, depth  (~99.6)
sz = deck_z + slen*cos(tilt);      // top of slope, height (~125.7)
H  = sz + marq;                    // total height         (~149.7)
deck_a   = atan2(deck_z-front_h, deck_y);          // deck angle (~19.5 deg)
deck_len = sqrt(deck_y*deck_y + (deck_z-front_h)*(deck_z-front_h)); // ~50.9

// ---------- CALIBRATE: measure your hardware ----------
scr_vis   = [51, 75];    // PORTRAIT screen cutout (active area 48.96 x 73.44 + margin)
disp_pcb  = [56, 85.5];  // display module = full Pi 3B+ footprint, portrait
stack_h   = 27;          // panel inner face -> BACK of the Pi PCB with the
                         // display MATED on the GPIO socket and the LCD glass
                         // touching the panel. Sets the rail depth.
                         // NOTE: 10 is likely too small — the mated stack is
                         // usually ~24-27 (glass + display PCB + socket + Pi).
                         // Measure the assembled sandwich, not just the Pi.
// Power inlet: slot in the side wall aligned with the Pi's micro-USB jack
// (stock PSU plugs in directly — no adapters). Dry-fit the Pi+display stack
// and measure these before printing:
pwr_side  = -1;          // 1 = right wall (x=W), -1 = left wall (x=0)
pwr_depth = 20;          // panel inner face -> jack axis (measure at dry-fit)
pwr_z     = 82;          // along-slope position of jack center — near the TOP
                         //   of the slope (jack ~10.6 mm from the Pi corner;
                         //   use ~18 instead if the power edge sits low)

// ---------- Small parts ----------
btn_d     = 12.4;        // 12 mm pushbutton hole
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

module shell() {
  difference() {
    union() {
      // walls
      difference() {
        rotate([90,0,90]) linear_extrude(W) polygon(profile);
        translate([wall,0,0]) rotate([90,0,90])
          linear_extrude(W-2*wall) offset(delta=-wall) polygon(profile);
      }
      corner_posts();
      door_bosses();
      screen_frame() slope_rails();
    }
    // open bottom (bottom plate screws onto corner posts)
    translate([wall, wall, -1]) cube([W-2*wall, D-2*wall, wall+2]);
    // back door opening
    translate([15, D-wall-1, 15]) cube([W-30, wall+2, 100]);
    // screen cutout
    screen_frame() translate([W/2, 1.5, slen/2])
      cube([scr_vis[0], wall+6, scr_vis[1]], center=true);
    // control deck holes
    deck_frame() deck_holes();
    // camera stand mounting holes (M3 from inside, up through the top)
    camstand_holes();
    // camera ribbon slot
    translate([W/2-12.5, sy+1.5, H-wall-1]) cube([25, 4, wall+2]);
    // marquee label
    translate([W/2, sy+1.2, sz+marq/2]) rotate([90,0,0])
      linear_extrude(1.4) text("K E A", size=11, font="DejaVu Sans:style=Bold",
                               halign="center", valign="center");
    // power inlet slot (side wall)
    power_slot();
    // screw pilots
    corner_post_pilots();
    door_boss_pilots();
  }
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

module camstand_holes() {
  py = (sy+D)/2;                            // stand center, depth
  for (s = [-1,1]) translate([W/2 + s*10, py, H-wall-1])
    cylinder(d=3.4, h=wall+2);              // M3 clearance through the top
}

module corner_posts() {
  for (p = [[8,8],[W-8,8],[8,D-8],[W-8,D-8]])
    translate([p[0], p[1], wall]) cylinder(d=10, h=12);
}
module corner_post_pilots() {
  for (p = [[8,8],[W-8,8],[8,D-8],[W-8,D-8]])
    translate([p[0], p[1], wall-1]) cylinder(d=2.6, h=11);
}

module door_bosses() {
  for (p = [[17,17],[W-17,17],[17,113],[W-17,113]])
    translate([p[0], D-13, p[1]]) rotate([-90,0,0]) cylinder(d=8, h=13);
}
module door_boss_pilots() {
  for (p = [[17,17],[W-17,17],[17,113],[W-17,113]])
    translate([p[0], D-9, p[1]]) rotate([-90,0,0]) cylinder(d=2.6, h=10);
}

// Two rails run down the inside of the screen panel; the Pi sled slides
// in from the bottom of the slope like a drawer, edges captured under the
// rail lips. NO screws: friction pads on the lips pinch the sled over the
// last ~10 mm of travel, and the top stops set its final position.
// Sled back face sits at wall+stack_h+6 (Pi back + 3 mm pads + 3 mm plate).
module slope_rails() {
  for (s = [0, 1]) {
    xw = s ? W-10 : 7;                        // web x-start (3 wide)
    xl = s ? W-16 : 7;                        // lip x-start (9 wide)
    translate([xw, wall, 0]) cube([3, stack_h + 9.3, slen]);          // web
    translate([xl, wall + stack_h + 6.3, 0]) cube([9, 3, slen]);      // lip
    translate([xl, wall + stack_h + 3, slen-5]) cube([9, 3.4, 5]);    // top stop
    // friction pad: 0.45 proud of the lip -> pinches the seated sled
    translate([xl+1.5, wall + stack_h + 5.85, 55]) cube([6, 0.6, 10]);
  }
}

// ============================================================
// PI SLED: 89 x 100 plate with a screwless pocket. The Pi 3B+
// drops between the locating walls onto the 4 pads, display mated
// on top; once the sled is in the rails the panel sandwiches the
// stack — nothing else needed. Walls are open where connectors
// overhang the PCB (power/HDMI edge, USB/Eth + SD short edges).
// Print flat, pads up. Central opening = airflow + CSI access.
// ============================================================
module pi_sled() {
  difference() {
    union() {
      cube([89, 100, 3]);
      for (x = [-1,1], y = [-1,1])            // 3 mm rest pads (no pilots)
        translate([44.5 + x*24.5, 55 + y*29, 3]) cylinder(d=6, h=3);
      // pocket walls, 7 mm tall (capture the Pi PCB sitting on the pads)
      translate([72.8, 12, 3]) cube([2, 86, 7]);       // GPIO edge: full wall
      translate([14.2, 12, 3]) cube([2, 8, 7]);        // power edge: end stubs
      translate([14.2, 90, 3]) cube([2, 8, 7]);        //   (ports stay clear)
      for (sx = [14.2, 63], sy = [10, 98])             // short-edge segments,
        translate([sx, sy, 3]) cube([11.8, 2, 7]);     //   center open (USB/SD)
    }
    translate([24.5, 33, -1]) cube([40, 44, 9]);       // airflow / access
    // notch for the power plug body (aligned with wall slot + rail notch)
    translate([pwr_side > 0 ? 73 : -1, pwr_z - 6, -1]) cube([17, 22, 12]);
  }
}

module deck_holes() {
  // 3 buttons: blue / red / green (GPIO 21 / 20 / 26)
  for (bx = [30, 55, 80])
    translate([bx, 32, 0]) cylinder(d=btn_d, h=24, center=true);
  // KY-040 rotary encoder (right), mini toggle (left)
  translate([94, 16, 0]) cylinder(d=enc_d, h=24, center=true);
  translate([16, 16, 0]) cylinder(d=tog_d, h=24, center=true);
}

// ============================================================
// BOTTOM PLATE (slides in from below, screws into corner posts)
// ============================================================
module bottom_plate() {
  difference() {
    translate([wall+0.3, wall+0.3, 0]) cube([W-2*wall-0.6, D-2*wall-0.6, wall]);
    for (p = [[8,8],[W-8,8],[8,D-8],[W-8,D-8]]) {
      translate([p[0], p[1], -1]) cylinder(d=3.4, h=wall+2);
      translate([p[0], p[1], -0.01]) cylinder(d1=6.5, d2=3.4, h=1.8); // countersink
    }
  }
}

// ============================================================
// BACK DOOR (vented, with power-cable hole)
// ============================================================
module door() {
  difference() {
    union() {
      translate([-46, -56, 0]) cube([92, 112, 2.5]);   // face plate
      translate([-30, -40, -2]) cube([60, 80, 2.5]);   // registration lip
    }
    for (p = [[-38,-48],[38,-48],[-38,48],[38,48]])    // screws into door bosses
      translate([p[0], p[1], -3]) cylinder(d=3.4, h=8);
    for (i = [-2:2])                                    // vents
      translate([i*12-1.5, -20, -3]) cube([3, 45, 9]);
    // spare cable hole (e.g. aux 5 V for servos later) — power enters
    // through the side-wall slot instead, no extra parts needed
    translate([0, -42, -3]) cylinder(d=12, h=9);
  }
}

// ============================================================
// CAMERA STAND (no servos): fixed fork bolted to the top plate;
// the camera plate hangs between the arms on an M3 bolt + nyloc
// nut — a manual friction tilt, set the angle once by hand.
// (If you ever add a servo back, only this part changes.)
// ============================================================
module camstand() {
  difference() {
    union() {
      translate([-19, -13, 0]) cube([38, 26, 6]);      // base, bolts to top
      for (s = [-1, 1])                                 // fork arms, 28 mm apart
        translate([s*16-2, -6, 0]) cube([4, 12, 32]);
    }
    for (s = [-1, 1])                                   // blind M3 pilots (from below)
      translate([s*10, 0, -1]) cylinder(d=2.6, h=6);
    // ribbon pass-through: the base sits over the top-plate slot, so the
    // same 25 x 4 slot continues through the base (in front of the arms)
    translate([-12.5, -10.9, -1]) cube([25, 4.1, 8]);
    // M3 tilt axle through both arms
    translate([0, 0, 26]) rotate([0, 90, 0]) cylinder(d=3.2, h=50, center=true);
  }
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
if (part == "bottom")   bottom_plate();
if (part == "door")     door();
if (part == "sled")     pi_sled();
if (part == "camstand") camstand();
if (part == "camplate") camera_plate();
if (part == "assembly") {
  color("SteelBlue", 0.85) shell();
  color("gray") bottom_plate();
  color("dimgray") translate([W/2, D+0.5, 65]) rotate([-90,0,0]) door();
  color("orange") translate([W/2, (sy+D)/2, H]) camstand();
  color("tomato") screen_frame() translate([10.5, wall+stack_h+6, -5])
    rotate([90,0,0]) pi_sled();
  color("orange") translate([W/2, (sy+D)/2-9.5, H+20]) rotate([90,0,0]) camera_plate();
}
