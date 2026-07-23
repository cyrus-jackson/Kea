# Kea Retro-PC — parts to order (`kea_retropc.scad`)

> **Reviewed `hardware/parts/proposal/` (2026-07):** Fan (SLCA-FAN) ✅,
> PCA9685 (157066) ✅. **Raspberry Pi 400 GPIO adapter ❌ — Pi-400-only, won't
> fit a Pi 3B+; replace with a 2×20 tall stacking header.** **Power decision:**
> Pi on its own 5 V micro-USB adapter; **servos run off 4×AA alkaline → LM2596S
> buck (set to 5.0 V) → PCA9685 V+** (the buck caps the ~6.4 V fresh alkaline
> under the PCA9685's 6 V limit). REG5V5A **not used**. Still to add: stacking
> header, LM2596S buck, servos (SG90s in hand).


Everything below is what the chassis is designed around. The **Fit** column
is the dimension the SCAD assumes — if the part you find differs, change the
matching parameter at the top of `kea_retropc.scad` and re-run
`python3 check_retropc.py` before printing.

## Where things sit (quick map)

- **Pi 3B+ + ELEGOO 3.5"** — stacked together, inside the **monitor**, leaning
  on the screen (cradle + wedge hold them). Power and camera enter here.
- **MG90S swivel servo** — stands **upright in the case**, dead-center under the
  turntable (`servo_boss` pocket at x=W/2, y=`turn_y`=105). Its shaft points up
  through the case-top hole into the turntable hub; the horn screws to the
  turntable underside. Limited to ±90° so the cable to the monitor just flexes.
- **Speaker + amp + PSU/buck** — in the **case** (lots of empty room there now
  that the Pi lives in the monitor).
- **Fan** — on the **monitor back door**, blowing onto the Pi.
- **Pan/tilt camera** — on the **monitor roof** pad.

## Electronics

| Part | Qty | Fit / spec assumed | Notes |
|---|---|---|---|
| Raspberry Pi 3B+ | 1 | 85 × 56 mm | have it |
| ELEGOO 3.5" TFT (480×320) | 1 | portrait, sits on the GPIO header | have it |
| 12 mm threaded panel-mount pushbutton | 3 | 12 mm hole + nut (`btn_d`) | on the keyboard |
| KY-040 rotary encoder | 1 | 7 mm bushing (`enc_d`) | keyboard, right |
| Mini SPDT ON-ON toggle | 1 | 6 mm thread (`tog_d`) | keyboard, left |
| **MG90S** metal-gear servo | 1 | 23.2 × 12.8 × 22.8 mm body (`sv_*`) | monitor swivel — needs metal gears for the torque |
| Adafruit Mini Pan-Tilt kit (2× SG90) | 1 | bracket screw spacing `turret_holes`=18 mm (measure!) | camera head |
| Pi Camera (v1/v2) | 1 | 25 × 24 mm, 21×12.5 hole pattern | your own project |
| 30 cm camera ribbon | 1 | — | the 15 cm one won't reach up the swivel |
| **30 mm 5 V fan** (30×30×7) | 1 | body `fan_sz`=30, holes `fan_holes`=24 mm | Pi cooling; 25 mm also fine (set `fan_sz`=25, `fan_holes`=20) |
| Speaker, 8 Ω 2–3 W, round | 1 | ~36 mm (match `spk_d`) | press-fits into the mount behind the case grille |
| PAM8403 mini amp | 1 | class-D, runs on 5 V | Pi 3.5 mm out → amp IN → speaker; amp power from a Pi **5 V** + GND pin |
| 3.5 mm audio cable → bare wires | 1 | 3-pole TRS is fine | taps the Pi's headphone jack to the amp input (tip=L, sleeve=GND) |

## Power (chosen: Pi on its adapter, servos on the battery)

Two independent sources, joined only at **ground**.

| Part | Qty | Spec | Notes |
|---|---|---|---|
| Pi PSU | 1 | 5 V / 2.5–3 A micro-USB | powers the **Pi only**, via the monitor side-wall slot |
| 4×AA holder with switch | 1 | **4× alkaline (~6 V, free)** | powers the **servos only**, through the buck ↓ |
| **LM2596S buck + voltmeter** | 1 | in 4–24 V, out set to **5.0 V**, ~2 A (3 A w/ heatsink) | **set to 5.0 V first**, then wire to PCA9685 **V+/GND**. It caps the 6.4 V fresh alkaline under the PCA9685 6 V limit |
| 470–1000 µF cap | 1 | ≥10 V | optional, across V+ (PCA9685 has 100 µF onboard) |

**Not used:** the **REG5V5A** (it needs 9 V+ in; a 6 V pack can't feed it).

Wiring: **Pi adapter → Pi.**   **4×AA (switch) → LM2596S → PCA9685 V+ / GND.**
Set the LM2596S output to **5.0–5.2 V with the trimmer/voltmeter *before*
connecting the servos** (the trimmer can reach 24 V). PCA9685 logic (VCC + SDA +
SCL) comes from the Pi via the stacking header. **Tie the battery/buck GND to the
Pi GND** — shared ground is mandatory or the servo signals won't work.

Notes: LM2596S is ~2 A continuous (heatsink for 3 A); **alkalines sag hard under
1–2 A**, so runtime under active motion is modest and, once the pack drops below
~6.5 V, the buck can't hold 5 V and the servos weaken — swap batteries then.
`servo.py` should **stop the PWM when idle** (servo relaxes, draw ≈ 0), and the
monitor should be **balanced over the swivel** so that servo isn't holding weight.

**Servos are plastic-gear (SG90):** great for the light pan/tilt camera. For the
**monitor swivel** they're marginal (they turn the whole monitor), so add a
**turntable/lazy-susan or 608 bearing** under the turntable to take the weight
off the servo gears, and balance the monitor over the axis. Upgrade that one
servo to metal gear (MG90S/MG996R) only if it still strains.

## Driving the servos (recommended: PCA9685)

The display already occupies most of the 40-pin header, so free GPIOs are
scarce and software PWM jitters. Best path:

| Part | Qty | Spec | Notes |
|---|---|---|---|
| **PCA9685** 16-ch PWM driver | 1 | 62.5×25.4 mm, I²C | **have it (157066).** All 3 servos plug in; **only uses SDA/GPIO2 + SCL/GPIO3**; **V+ takes the 5 V from the LM2596S**; onboard 100 µF cap |
| 2×20 stacking header (extra-tall) | 1 | ≥11 mm pins | **must add** — reach the header pins (I²C + button/encoder/toggle) under the display. NOT the Pi 400 adapter (that's Pi-400-only) |
| MG90S servo (swivel) | 1 | metal gear | monitor swivel — **add** |
| Adafruit Mini Pan-Tilt (2× SG90) | 1 | — | camera head — **add** |

Wiring in one line: **servo power + ground → external 5 V (via the PCA9685 V+),
servo signal → PCA9685, PCA9685 → Pi over I²C, and tie the servo-supply ground
to the Pi ground.** Direct-GPIO is possible instead (BCM 12/13 are hardware-PWM
pins) but you'd burn 3 scarce pins and fight jitter — the PCA9685 avoids both.

## Fasteners & bits

| Part | Qty | For |
|---|---|---|
| M2.5 × 10 self-tapping screws | 4 | fan → door bosses |
| M2 × 5 screws | 4 | Pi camera → `cam_cradle` |
| M2.5 × 6 screws | 4 | monitor foot → turntable (bolt circle `turn_bolt`=26 mm) |
| Servo horn screws | — | come with the MG90S; horn → turntable |
| 1.75 mm filament | ~30 cm | seam dowels (cut into ~11 mm pins) |
| Stick-on rubber feet | 4 | under the case |
| Heatsinks for the Pi | 1 set | optional, pairs with the fan |
| Screw terminal block / wire nuts | a few | joining the grounds |
| Dupont jumper wires | ~20 | buttons, encoder, servos |

## Before you print the whole thing

The **motorized swivel** is the only unproven bit. Print just `case`,
`case_floor`, `turntable`, and dry-fit the **MG90S** first: confirm the horn
couples to the turntable, it seats in the socket, and it turns the empty
turntable smoothly. Then adjust `turn_r`, `servo_*`, or `turn_bolt` as needed
before committing to the monitor print.
