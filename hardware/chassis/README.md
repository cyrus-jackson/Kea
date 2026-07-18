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
| `wedge` | Gravity wedge — clamps the stack; center cutout passes the GPIO jumpers | On its flat face |
| `riser_base` | Breadboard riser base (mortises for the towers) | Flat |
| `riser_tower` | Riser ladder tower — **print 2** | Flat |
| `riser_tray` | Riser tray with breadboard fence, slides into any rung | Flat |

PETG recommended (PLA fine indoors). **Nothing to measure anymore**: the stack cradle's shelf and the self-adjusting wedge accommodate any Pi+display thickness from ~20 to ~30 mm.

## Printing the shell — recommended: two halves, zero supports

Set `part = "shell_left"`, export, then `"shell_right"`. **Lay each half on its flat cut face** in Cura. Because every feature of the cabinet (walls, deck, screen panel, cradle shelf and guides, top) runs straight across the width, a half lying on its cut plane prints everything as vertical walls — Cura should show **no red at all**, supports off. Each half is only 55 mm tall and both fit on one bed.

Joining: cut four ~11 mm pieces of 1.75 mm filament, push them into the dowel holes on one cut face (front wall, back wall ×2, top), dry-fit, then glue (superglue for PLA, superglue or epoxy for PETG) and clamp with tape. The cut plane sits 21.5 mm from the left edge — through the blank strip between the toggle and the blue button — so the seam misses the screen opening, every deck hole, and the camera slot; from the front it reads as a subtle edge line, easily hidden with filler or a marker.

Round holes printed sideways would overhang at their crowns, so with `teardrop = true` (the default) every button/encoder/toggle hole and the camstand sockets get a 45° teardrop point on their print-up side — it prints clean and hides under the mounted part. Set `teardrop = false` if you print upright.

**Case thickness** is one knob: `wall` (default 3 mm) drives every wall, the deck, the screen panel and the top; the ledge, nubs, socket depths and camstand pegs all follow it automatically. Stay within 2.5–4 mm — beyond ~4 the KY-040's threaded bushing gets too short to catch its nut through the deck, and remember to re-check `pwr_depth` from the new inner face if you change it.

One-piece upright printing (`part = "shell"`) still works if you prefer: set `teardrop = false`, supports needed only under the deck, the top plate, and the cradle shelf/flanges.

There are **no screw posts or bosses anywhere**. The bottom-plate ledge is a 1.8 mm micro-bridge and the friction nubs print from the bed; neither needs support in either orientation. Print the **door outer-face down** (lip and ribs up) and the **camstand base-down** (pegs are only 3.5 mm; brim if they worry you). All other parts print flat with no supports.

## How it goes together

1. **Display/Pi — the cradle**: the back door is now almost the entire back wall (90×130 opening), so the stack goes in without contortions. Mate the display on the Pi's GPIO socket, then through the open back, lean the stack against the screen panel *glass-first* — like standing a picture in a frame. The cradle flanges only cover the bottom half of the channel, so the top is wide open: rest the stack's bottom edge in, tip it flat, and slide it down until it lands on the shelf. Its bottom edge sits on the **shelf** (a full-width ledge just below the cutout), the two **side guides** center it, and gravity holds it against the panel. Then take the **wedge** part, drop it thin-end-first into the gap between the Pi's back and the cradle's flanges, and nudge it down the slope until snug — it self-adjusts to any stack thickness, so there is nothing to measure and no screws. To remove: pull the wedge up by its tab and lift the stack out. Everything mounts **rotated 90° (portrait)**, GPIO-socket edge vertical; the power jack faces the left wall near the top of the slope (step 6), above where the guides end.
2. **Controls**: push the 12 mm buttons into the deck holes (blue 30 mm, red 55 mm, green 80 mm from left) and hot-glue from behind, or solder them to a perfboard strip glued under the deck. KY-040 panel-mounts with its own nut (right hole), toggle with its nut (left hole).
3. **Breadboard — the riser**: slot the two ladder towers into the base mortises, stand it on the bottom plate (anywhere — behind the corral is natural), and slide the tray into the same rung on both towers. **Six height levels, 10 mm apart** (board sits ~24–74 mm above the floor): pick whichever puts the breadboard closest to the Pi's exposed GPIO pins so the jumpers stay short, and re-rung it anytime. The tray's fence holds the 83×55 board; wires drop through the tray's center hole and the towers' floor-level pass-throughs. The Pi's jumpers reach it through the **cutout in the wedge**. (Ground-level option: the corral fence on the bottom plate is still there.)
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

Pi 3B+ is identical in outline and port placement to the 3B (85×56 mm), and the ELEGOO 3.5" module covers that footprint fully. Active area **48.96 wide × 73.44 tall** in portrait → the 51×75 cutout gives ~1 mm reveal per side. The cradle guides sit 0.5 mm outside the 56 mm stack width, the shelf carries its bottom edge, and the guides stop below the power slot so nothing crosses the plug's path.

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
