# Kea Chassis — Mini Bartop Arcade

Desk cabinet for the Kea smart display: 3.5" TFT **in portrait**, reclined 35°, arcade control deck (3 buttons + KY-040 knob + toggle), and a **fixed camera on top** (set-once friction tilt, no servos). Replaces the RPI-35CASE-B case that didn't fit the wiring.

Footprint **110 × 130 mm**, height **158 mm** (~210 mm with camera raised). Everything fits a 220×220×250 print bed.

## Parts to print (`kea_chassis.scad`)

Set `part = "..."` in the file, render (F6), export STL.

| Part | What it is | Orientation / notes |
|---|---|---|
| `shell` | One-piece cabinet body | Print upright (open bottom down). Enable normal supports — the deck and top plate are interior ceilings. ~10 h, 3 walls, 15% infill |
| `bottom` | Screw-in floor plate | Flat, no supports |
| `door` | Vented back door with cable hole | Face down |
| `camstand` | Fixed camera fork, bolts to the top plate | Base down |
| `camplate` | Camera plate with hinge tabs (M3 friction tilt) | Flat |
| `sled` | Pi sled — slides into rails behind the screen, locks with 1 screw | Flat, pads up |

PETG recommended (PLA fine indoors). **Before printing the shell**, mate the display on the Pi and measure `stack_h`: panel inner face → back of the Pi PCB with the LCD glass touching the panel (default 26 mm) — it sets the length of the four tray bosses.

## Printing the shell — recommended: two halves, zero supports

Set `part = "shell_left"`, export, then `"shell_right"`. **Lay each half on its flat cut face** in Cura. Because every feature of the cabinet (walls, deck, screen panel, rails, top) runs straight across the width, a half lying on its cut plane prints everything as vertical walls — Cura should show **no red at all**, supports off. Each half is only 55 mm tall and both fit on one bed.

Joining: cut four ~11 mm pieces of 1.75 mm filament, push them into the dowel holes on one cut face (front wall, back wall ×2, top), dry-fit, then glue (superglue for PLA, superglue or epoxy for PETG) and clamp with tape. The seam runs down the middle of the bezel and deck — a swipe of filler or a black marker hides it. The middle button hole spans the seam; run a 12 mm drill or file through after gluing to true it up.

One-piece upright printing (`part = "shell"`) still works if you prefer: supports needed only under the deck, the top plate, and the sled rails (sand the rail channel smooth after removing them — test-glide the empty sled before loading the Pi).

There are **no screw posts or bosses anywhere**. The bottom-plate ledge is a 1.8 mm micro-bridge and the friction nubs print from the bed; neither needs support in either orientation. Print the **door outer-face down** (lip and ribs up) and the **camstand base-down** (pegs are only 3.5 mm; brim if they worry you). All other parts print flat with no supports.

## How it goes together

1. **Display/Pi — fully screwless**: drop the Pi into the sled's pocket (locating walls, open where connectors overhang the PCB), mate the display on the GPIO socket, then slide the sled into the two rails from the bottom of the slope until it hits the top stops. Friction pads on the rail lips pinch it in place over the last ~10 mm — no lock screw. Once seated, the panel↔sled sandwich holds the whole stack captive: the Pi can't leave the pocket without sliding the sled back out. If the glass is a hair loose against the panel, a strip of foam behind the Pi takes up the slack; if the sled slides too easily, a layer of tape on its edge tightens the pinch. Everything mounts **rotated 90° (portrait)**, GPIO-socket edge vertical; the power jack faces the left wall near the top of the slope, where the wall slot, rail, and sled are all notched for the plug (step 6).
2. **Controls**: push the 12 mm buttons into the deck holes (blue 30 mm, red 55 mm, green 80 mm from left) and hot-glue from behind, or solder them to a perfboard strip glued under the deck. KY-040 panel-mounts with its own nut (right hole), toggle with its nut (left hole).
3. **Breadboard**: peel-and-stick to the bottom plate; all button/encoder/servo wiring lands here.
4. **Camera stand**: press the fork's two chamfered pegs into the top-plate sockets (drop of glue if ever loose). Screw the camera to the plate (M2), hang the plate between the fork arms on an M3×35 bolt with a nyloc nut — tighten until the tilt holds under friction, aim it at your face once, done. (Both SG90s stay in the drawer; if you ever want motion, only the stand part needs redesigning — the shell doesn't change.)
5. **Ribbon routing**: the camera's ribbon connector is on the *back* of its PCB at the bottom — the plate has a notch there. Fold the ribbon down through the notch, through the matching slot in the stand base and top plate, then down the hollow marquee to the Pi's CSI port. Insert the ribbon into the camera *before* screwing it to the plate.
6. **Charger**: the stock PSU cable plugs **straight into the Pi through a slot in the side wall** — no adapters or extensions. Dry-fit the Pi+display stack first and set `pwr_side` / `pwr_depth` / `pwr_z` in the `.scad` so the slot lands on the jack (it's oversized ~21×18 mm for tolerance). Orient the display so the Pi's power edge sits on your preferred side, jack toward the bottom.
7. **Close up — no screws**: the door press-fits into its opening (the crush ribs on its lip squash on first insertion for a snug hold; pop it out by the pull tab). The bottom plate pushes in from below past six friction nubs until it stops on the ledge — the finger hole gets it back out. Rubber feet on. The small hole in the door is a spare cable exit (e.g. aux servo power later).

## Wiring (matches `src/hardware_input.py`)

The ELEGOO 3.5" occupies header pins 1–26. Pins 27–40 stay exposed — that's why the buttons already use BCM 20/21/26.

| Signal | BCM | Pin | Notes |
|---|---|---|---|
| Blue btn (cycle) | 21 | 40 | existing, to GND |
| Red btn (pomodoro) | 20 | 38 | existing, to GND |
| Green btn (notification) | 26 | 37 | existing, to GND |
| Encoder CLK / DT / SW | 5 / 6 / 16 | 29 / 31 / 36 | leave KY-040 VCC unconnected; enable internal pull-ups (`PUD_UP`) |
| Toggle (privacy/mode) | 19 | 35 | to GND, read as input |
| GND | — | 30/34/39 | breadboard ground rail |
| (spare) | 12 / 13 | 32 / 33 | hardware-PWM pins, free for servos later |

**Power:** with no servos, everything you're wiring (buttons, encoder, toggle) needs only GPIO + ground — and grounds ARE on the exposed pins 27–40. No stacking header, no cap, no external 5 V: the 2.5 A PSU into the Pi covers the lot.

## Verified dimensions (Pi 3B+ + ELEGOO 3.5", portrait)

Pi 3B+ is identical in outline and port placement to the 3B (85×56 mm), and the ELEGOO 3.5" module covers that footprint fully. Active area **48.96 wide × 73.44 tall** in portrait → the 51×75 cutout gives ~1 mm reveal per side. The rails sit at the panel edges, clearing the 56 mm-wide stack by ~17 mm per side, and both rails and sled are notched around the power slot so nothing crosses the plug's path.

## Display orientation

Good news: the panel is **natively portrait (320×480)** — no driver rotation needed (`rotate=0`, or `180` if it's upside-down once mounted; re-run touch calibration if you change it). Run Kea with:

```bash
KEA_SCREEN_WIDTH=320 KEA_SCREEN_HEIGHT=480 KEA_FULLSCREEN=1 python src/main.py
```

This matches `config.py`'s portrait logical sizes (400×600 staging / 200×300 production). Don't flip the display module physically — its socket must stay on the Pi's GPIO edge.

## Still to buy

- **30 cm camera ribbon cable** — the 15 cm one shipped with the camera won't reach from the Pi (mid-slope) up through the top slot to the stand
- Screws: just 4× M2×5 (camera) + 1× M3×35 bolt + nyloc nut (tilt hinge) — the entire chassis is otherwise screwless (press-fits, friction nubs, snap-in plate)
- Stick-on rubber feet

## Software next steps

- Encoder: rotate = cycle states, press = select (BCM 5/6/16)
- Camera: `picamera2`; with a fixed camera, use a wide crop + face detection to know when you're at the desk (GPIO 12/13 stay free if servos return someday)
