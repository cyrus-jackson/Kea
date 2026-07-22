# Kea Chassis — Mini Bartop Arcade

Desk cabinet for the Kea smart display: 3.5" TFT **in portrait**, reclined 25°, arcade control deck (3 buttons + KY-040 knob + toggle), and a **fixed camera on top** (set-once friction tilt, no servos). Replaces the RPI-35CASE-B case that didn't fit the wiring.

Footprint **104 × 118 mm**, height **151 mm** (~200 mm with camera raised). Trimmed down from the earlier 110×130×167: the breadboard is gone (every control is panel-mounted and wired straight to the header), so nothing lives under the slope, and the depth/marquee/deck slack was pulled in. The display's fixed 56×85.5 footprint sets the width and slope-length floors. Everything fits a 220×220×250 print bed.

## Parts to print (`kea_chassis.scad`)

Set `part = "..."` in the file, render (F6), export STL.

| Part | What it is | Orientation / notes |
|---|---|---|
| `shell` | One-piece cabinet body | Print upright (open bottom down). Enable normal supports — the deck and top plate are interior ceilings. ~10 h, 3 walls, 15% infill |
| `bottom` | Press-fit floor plate (plain now — no breadboard corral) | Flat, no supports |
| `door` | Vented back door, finger-scallop pull | Face down |
| `camstand` | Fixed camera fork, bolts to the top plate | Base down |
| `camplate` | Camera plate with hinge tabs (M3 friction tilt) | Flat |
| `wedge` | Gravity wedge — clamps the stack; center cutout passes the GPIO jumpers | On its flat face |

PETG recommended (PLA fine indoors). **Nothing to measure anymore**: the stack cradle's shelf and the self-adjusting wedge accommodate any Pi+display thickness from ~20 to ~30 mm.

## Printing the shell — recommended: two halves, zero supports

Set `part = "shell_left"`, export, then `"shell_right"`. **Lay each half on its flat cut face** in Cura. Because every feature of the cabinet (walls, deck, screen panel, cradle shelf and guides, top) runs straight across the width, a half lying on its cut plane prints everything as vertical walls — Cura should show **no red at all**, supports off. Each half is only 55 mm tall and both fit on one bed.

Joining: cut four ~11 mm pieces of 1.75 mm filament, push them into the dowel holes on one cut face (front wall, back wall ×2, top), dry-fit, then glue (superglue for PLA, superglue or epoxy for PETG) and clamp with tape. The cut plane sits 19 mm from the left edge — through the blank strip between the toggle and the blue button — so the seam misses the screen opening, every deck hole, and the camera slot; from the front it reads as a subtle edge line, easily hidden with filler or a marker.

Round holes printed sideways would overhang at their crowns, so with `teardrop = true` (the default) every button/encoder/toggle hole and the camstand sockets get a 45° teardrop point on their print-up side — it prints clean and hides under the mounted part. Set `teardrop = false` if you print upright.

**Case thickness** is one knob: `wall` (default 3 mm) drives every wall, the deck, the screen panel and the top; the ledge, nubs, socket depths and camstand pegs all follow it automatically. Stay within 2.5–4 mm — beyond ~4 the KY-040's threaded bushing gets too short to catch its nut through the deck, and remember to re-check `pwr_depth` from the new inner face if you change it.

One-piece upright printing (`part = "shell"`) still works if you prefer: set `teardrop = false`, supports needed only under the deck, the top plate, and the cradle shelf/flanges.

There are **no screw posts or bosses anywhere**. The bottom-plate ledge is a 1.8 mm micro-bridge and the friction nubs print from the bed; neither needs support in either orientation. Print the **door outer-face down** (lip and ribs up) and the **camstand base-down** (pegs are only 3.5 mm; brim if they worry you). All other parts print flat with no supports.

## How it goes together

1. **Display/Pi — the cradle**: the back door is almost the entire back wall (90×132 opening, now raised high up the back so the stack's top edge clears the rail as you angle it in). Mate the display on the Pi's GPIO socket, then through the open back, lean the stack against the screen panel *glass-first* — like standing a picture in a frame. The cradle flanges only cover the bottom half of the channel, so the top is wide open: rest the stack's bottom edge in, tip it flat, and slide it down until it lands on the shelf. Its bottom edge sits on the **shelf** (a full-width ledge just below the cutout), the two **side guides** center it, and gravity holds it against the panel. Then take the **wedge** part, drop it thin-end-first into the gap between the Pi's back and the cradle's flanges, and nudge it down the slope until snug — it self-adjusts to any stack thickness, so there is nothing to measure and no screws. To remove: pull the wedge up by its tab and lift the stack out. Everything mounts **rotated 90° (portrait)**, GPIO-socket edge vertical; the power jack faces the left wall near the top of the slope (step 5), above where the guides end.
2. **Controls — all panel-mount, no perfboard**: each control fastens with its own threaded body and nut through the deck, then wires straight to the Pi header. Drop the three **12 mm threaded pushbuttons** into the deck holes (blue 27 mm, red 52 mm, green 77 mm from the left) and tighten the back nut; the KY-040 encoder nuts into the right hole, the toggle into the left. Nothing to glue.
3. **Camera stand**: press the fork's two chamfered pegs into the top-plate sockets (drop of glue if ever loose). Screw the camera to the plate (M2), hang the plate between the fork arms on an M3×35 bolt with a nyloc nut — tighten until the tilt holds under friction, aim it at your face once, done. (Both SG90s stay in the drawer; if you ever want motion, only the stand part needs redesigning — the shell doesn't change.)
4. **Ribbon routing**: the camera's ribbon connector is on the *back* of its PCB at the bottom — the plate has a notch there. Fold the ribbon down through the notch, through the matching slot in the stand base and top plate, then down the hollow marquee to the Pi's CSI port. Insert the ribbon into the camera *before* screwing it to the plate.
5. **Charger**: the stock PSU cable plugs **straight into the Pi through a slot in the side wall** — no adapters or extensions. Dry-fit the Pi+display stack first and set `pwr_side` / `pwr_depth` / `pwr_z` in the `.scad` so the slot lands on the jack (it's oversized ~21×18 mm for tolerance). Orient the display so the Pi's power edge sits on your preferred side, jack toward the bottom.
6. **Close up — no screws**: the door press-fits into its opening (the crush ribs on its lip squash on first insertion for a snug hold; pop it out by the finger scallop on the top edge). The bottom plate pushes in from below past six friction nubs until it stops on the ledge — the finger hole gets it back out. Rubber feet on. The small hole in the door is a spare cable exit (e.g. aux servo power later).

## Wiring (matches `src/hardware_input.py`)

The ELEGOO 3.5" occupies header pins 1–26. Pins 27–40 stay exposed — that's why the buttons already use BCM 20/21/26.

| Signal | BCM | Pin | Notes |
|---|---|---|---|
| Blue btn (cycle) | 21 | 40 | existing, to GND |
| Red btn (pomodoro) | 20 | 38 | existing, to GND |
| Green btn (notification) | 26 | 37 | existing, to GND |
| Encoder CLK / DT / SW | 5 / 6 / 16 | 29 / 31 / 36 | KY-040 data lines |
| Encoder **+** | 12 | 32 | driven HIGH as a 3.3 V rail for the board's pull-ups (see below) |
| Encoder GND | — | 30/34/39 | to a common ground |
| Toggle (3-pin ON-ON) | 19 | 35 | **centre** pin to GPIO 19, **one** outer leg to GND, third leg unused |
| GND | — | 30/34/39 | common ground |
| (spare) | 13 | 33 | hardware-PWM pin, free for a servo later |

**Deck behaviour.** The dial browses the world rail on Nexus (press to enter) and tunes straight through the worlds anywhere else (press returns home). The toggle drives auto-pilot by default — set `KEA_TOGGLE_ROLE=mute` to make it a voice mute switch instead, or `none` to ignore it.

**The toggle is a plain SPDT** — three legs, no electronics, so none of the KY-040's pull-up complications apply. Centre leg (the common pole) to GPIO 19; one outer leg to any ground; leave the third empty. Flipped toward the grounded leg the pin reads LOW = ON; flipped the other way the common floats and the Pi's internal pull-up holds it HIGH = OFF. It doesn't matter *which* outer leg you ground — that only decides which physical direction means "on". If it ends up backwards once the switch is nutted into the deck, set `KEA_TOGGLE_INVERT=1` rather than unsoldering.

Ground is common across the whole header. With the breadboard gone, join the button, encoder and toggle grounds together at one point — a small screw terminal block, a wire nut, or a soldered splice — and run a single lead to any header ground pin (30/34/39).

Nothing here touches the 5 V rail, so no stacking header is needed for the buttons: each switch simply shorts its pin to ground and the Pi's internal pull-ups supply the rest. If you haven't wired the encoder or toggle yet, set `KEA_ENCODER=0` / `KEA_TOGGLE=0` — floating inputs can otherwise read as random presses.

### The KY-040 `+` pin — test before you trust it

Pins 27–40 (everything the display leaves exposed) carry **no 3.3 V and no 5 V**, only ground. So the KY-040's `+` pin has nowhere convenient to go, and it starts unconnected.

That is usually fine, but not always. The breakout board has 10 kΩ pull-ups from CLK and DT up to `+`. With `+` floating, grounding one data line drags the other down through those two resistors — roughly 3.3 V × 20 kΩ/70 kΩ ≈ **0.94 V**, which lands in the Pi's undefined input band (0.8–1.3 V). When that happens the second channel reads as noise and rotation decodes erratically or not at all.

The tell-tale is subtle: **everything looks fine at rest** (nothing is grounded, so the rail floats up and all lines read HIGH) and only misbehaves while turning. The classic symptom is a phantom PRESS on every detent, because grounding DT sags SW to ~0.8–0.95 V through the resistor pair.

**The fix needs no extra parts: drive `+` from a spare GPIO.** Those pull-ups draw under 1 mA in total and a Pi GPIO sources up to 16 mA, so wire the KY-040's `+` to **BCM 12 (pin 32)** — conveniently right beside the encoder's other pins. Kea and `test_encoder.py` both set that pin as an output and drive it HIGH at startup, giving a solid 3.3 V rail from the exposed header. Change it with `KEA_ENCODER_VCC=13`, or `-1` to leave `+` unpowered.

Alternatives if you'd rather not spend a GPIO: **desolder R1/R2/R3** from the KY-040 so the Pi's internal pull-ups work alone, or run `+` to real 3.3 V (pin 1 or 17) via a stacking header. **3.3 V only, never 5 V** — through those pull-ups, 5 V would go straight into GPIO 5/6 and damage the Pi.

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
