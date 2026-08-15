# Kea — wiring sheet (with the GPIO extender)

Written for the build with the **BerryBase GPIO Winkel-Adapter (157081)**
fitted, so the whole 40-pin header is reachable — including 3.3 V, 5 V and
I²C, which the display would otherwise cover.

**Pin numbers come from the code.** Regenerate this table any time you
change a pin:

```bash
python3 tools/gen_wiring.py
```

> ⚠️ **Power the Pi off before touching anything.** Wire the ground rail
> first. A switch leg on 5 V instead of GND can destroy a GPIO.

---

## 0. Check the pin is free before you wire to it

```bash
python3 tools/pinmap.py            # the whole header
python3 tools/pinmap.py --power    # just 3.3 V / 5 V / GND
```

GPIO assignments are parsed from `src/hardware_input.py`, so the map
cannot drift from the code. **Power and ground users are a table inside
`tools/pinmap.py` — if you wire something to a power pin, add it there**,
because nothing else records it.

That gap is not hypothetical: SERVO_WIRING.md first said to put the
PCA9685's `VCC` on pin 1, which already had the encoder's `+` on it.

---

## 1. Fit the extender — and prove it's the right way round

**Why this matters:** a 2×20 socket seats perfectly well rotated 180° —
nothing physically stops it. Worked through, a reversed extender puts the
Pi's **5 V onto the extender's ground net** (a dead short across the
supply) and **5 V onto a GPIO** at the same time. That trips or cooks the
PSU and can destroy the Pi. Verify *before* power, not after.

### Step 1 — find pin 1 on both boards (unpowered)

Pin 1 is marked, always, in at least one of these ways:

- **A square solder pad** on the underside — every other pin is round.
  This is the most reliable tell; flip the board and look.
- Silkscreen: a **`1`**, a small **triangle**, or a **dot** by that corner.
- On the Pi, pin 1 is at the end of the header **nearest the micro-SD
  card**, on the inner row. Pins 1 and 2 are the pair furthest from the
  USB ports.

Sanity anchor: **pin 1 = 3.3 V, pin 2 = 5 V**, and they sit side by side
at the same end. If your extender labels any pin `3V3` or `5V`, that end
*is* the pin-1 end.

### Step 2 — seat it and eyeball it

1. Pi **off and unplugged**.
2. Push the extender on so pin 1 meets pin 1.
3. Look along both ends: **no pin should stick out uncovered**, and the
   socket must not be shifted by one column or sitting on one row only.
   An offset seat is as damaging as a reversed one.

### Step 2a — you have TWO breakouts: top and right

This extender brings the 40 pins out **twice** — a vertical header on top
and a horizontal one on the right:

- **Top (vertical)** — the display stacks onto this. Straight pass-through,
  same numbering as the Pi.
- **Right (horizontal)** — this is where your jumper wires go.

⚠️ **Don't assume the right-hand header is numbered like the top one.**
Right-angle breakouts frequently come out **mirrored** (the rows swap as
the pins fold over), so "pin 1" can be at the opposite corner or the
opposite row from what you'd guess. Getting this wrong is the same class
of mistake as fitting the extender backwards.

**Work out its numbering from the grounds — it's a unique fingerprint.**
With the meter on continuity and one probe on the USB shell, walk the
horizontal header and note every position that beeps. Compare:

| Grounds land on | Your header is |
|---|---|
| 6, 9, 14, 20, 25, 30, 34, 39 | **correct** — number it like the Pi |
| 5, 10, 13, 19, 26, 29, 33, 40 | **rows swapped** — odd/even are flipped |
| 1, 8, 12, 15, 22, 28, 31, 36 | **end reversed** — count from the other end |
| 2, 7, 11, 16, 21, 27, 32, 35 | **rotated 180°** |

All four patterns are different, so the beeps tell you exactly which
layout you have — no guessing. Work out where pin 1 really is, mark that
corner with a dab of paint or a marker, and wire from there.

### Step 3 — continuity test, still unpowered (the safe proof)

You don't need to probe under the extender: **the metal shell of the USB
or Ethernet port is connected to the Pi's ground.** Use it as a reference.

With a multimeter on continuity (beep):

| Probe A | Probe B | Expect |
|---|---|---|
| USB port metal shell | extender pin **6** (and 9, 14, 20, 25, 30, 34, 39) | **beeps** — these are grounds |
| USB port metal shell | extender pin **1** | **silent** — pin 1 is 3.3 V, not ground |
| USB port metal shell | extender pin **2** | **silent** — pin 2 is 5 V |

If pin 1 or 2 beeps to ground, or the ground pins *don't* beep, the
extender is reversed or offset. **Stop and re-seat it.**

Run this on **whichever header you'll actually wire to** — for this build
that's the horizontal one on the right (see Step 2a).

> Quick logic: grounds sit at pins 6/9/14/20/25/30/34/39. Rotated 180°,
> those positions would land on 35/32/27/21/16/11/7/2 — which are *not*
> grounds. So the beep pattern alone tells you the orientation.

### Step 4 — power test, nothing else connected

Extender on, **display and all wiring off**. Power up and measure with the
black probe on a ground pin (6) and red on:

- **pin 1 → 3.3 V** (3.2–3.4)
- **pin 2 → 5 V** (4.9–5.2)

Anything near 0 V, or reversed, means it's wrong — pull the power.

### Step 5 — functional check

Fit the display and boot. **If the display works, the extender is
correctly oriented** — its SPI lines would be scrambled otherwise. That's
a solid free check even without a multimeter.

Then, before wiring anything, confirm the Pi still sees its own pins:

```bash
python3 tools/check_free_pins.py
```

### No multimeter?

Do Steps 1, 2 and 5 — pin-1 markings, a careful look for offset, then the
display test. A reversed extender essentially always breaks the display,
so a working screen is strong evidence. **Don't wire anything else until
the display has come up once with the extender fitted.**

For the horizontal header's numbering without a meter, use a **known
ground and a single LED with a resistor**, or safest of all: wire *one*
button first, to what you believe is pin 40 and a ground, then run
`python3 tools/test_controls.py` and press it. If "Blue (Cycle)" prints,
your numbering is right and you can wire the rest with confidence. One
wrong guess on a plain switch costs nothing — it just won't respond.

> A multimeter that does continuity is about €10 and removes all of this
> doubt. For a build with a Pi in it, it pays for itself the first time.

> Whatever you do, if anything gets warm or you smell hot plastic, pull
> the power immediately.

---

## 2. The connections

| # | Signal | BCM | **Pin** | Wire to |
|---|---|---|---|---|
| 1 | Button — Blue (cycle worlds) | 21 | **40** | other leg → GND |
| 2 | Button — Red (Pomodoro) | 20 | **38** | other leg → GND |
| 3 | Button — Green (annunciator) | 26 | **37** | other leg → GND |
| 4 | Button — Home (to Nexus) | 13 | **33** | other leg → GND |
| 5 | Button — Camera (capture) | 4 | **7** | other leg → GND |
| 6 | Encoder `CLK` | 5 | **29** | KY-040 CLK |
| 7 | Encoder `DT` | 6 | **31** | KY-040 DT |
| 8 | Encoder `SW` | 16 | **36** | KY-040 SW |
| 9 | Encoder `+` | — | **1** or **17** | **3.3 V — never 5 V** |
| 10 | Encoder `GND` | — | 30 / 34 / 39 | ground rail |
| 11 | Toggle A — centre leg | 19 | **35** | one outer leg → GND |
| 12 | Toggle B — centre leg | 27 | **13** | one outer leg → GND |
| — | Ground rail | — | **30, 34, 39** | every switch's other leg |
| — | Fan `+` / `−` | — | **4** (5 V) / GND | 30 mm fan |

Every input uses the Pi's **internal pull-up**: the pin idles HIGH and
reads LOW when the switch shorts it to ground. No resistors anywhere.

### Order of work

1. **Ground rail first.** Run one wire from pin 39 to a screw terminal or
   splice, and take every switch's ground from there. One rail, one wire
   back to the Pi.
2. **Buttons.** 2 solder pins each, no polarity: one → its GPIO, other →
   the rail.
3. **Toggles (SPDT, 3 legs).** **Centre** leg → its GPIO, **one** outer
   leg → the rail, third leg unused. Which outer leg you pick only sets
   which direction means "on" — if it ends up backwards, fix it in
   software with `KEA_TOGGLE_INVERT=1` / `KEA_TOGGLE2_INVERT=1`.
4. **Encoder.** CLK/DT/SW to 29/31/36, GND to the rail, and **`+` to
   3.3 V (pin 1 or 17)**.
5. **Fan.** 5 V (pin 4) and GND. It runs whenever the Pi is on.

---

## 3. Why `+` goes to 3.3 V now

The KY-040 has 10 kΩ pull-ups from CLK and DT up to its `+` pin. Leave `+`
unconnected and grounding one data line drags the others to about 1 V —
inside the Pi's undefined input band — which shows up as **a phantom press
on every detent**. That was the fault you hit.

Before the extender there was no 3.3 V on the exposed pins, so the code
drove GPIO 12 HIGH as a substitute. **That workaround is now off by
default** (`ENC_VCC = -1`): with the extender you have a real rail, which
is stiffer and costs no pins.

- **Wire `+` → pin 1 or 17.** Nothing else to configure.
- Want the old behaviour? `KEA_ENCODER_VCC=12` and wire `+` → pin 32.
- **3.3 V only, never 5 V.** Through those pull-ups, 5 V feeds straight
  into GPIO 5/6 and damages the Pi.

---

## 4. Confirm the two "under the display" pins first

Buttons 1–4, the encoder and toggle A use pins 27–40, which the display
never touches. **Button 5 (pin 7) and toggle B (pin 13) sit in the display's
half of the header** — usually free on an SPI panel, but that depends on
your overlay. Check before soldering those two:

```bash
sudo apt install raspi-gpio      # once
python3 tools/check_free_pins.py
```

Anything reported **ALT0–ALT5** belongs to a peripheral (SPI/I²C/UART) —
don't use it. If either pin is taken, pick a free one from the script's
list and set it at launch instead of editing code:

```bash
KEA_BTN_CAMERA=22 KEA_TOGGLE2_PIN=23 python3 src/main.py
```

Overridable: `KEA_BTN_BLUE`, `KEA_BTN_RED`, `KEA_BTN_GREEN`,
`KEA_BTN_HOME`, `KEA_BTN_CAMERA`, `KEA_ENC_CLK`, `KEA_ENC_DT`,
`KEA_ENC_SW`, `KEA_TOGGLE_PIN`, `KEA_TOGGLE2_PIN`.

Two to avoid for switches: BCM 2/3 (pins 3/5) have fixed 1.8 kΩ pull-ups —
keep them for the PCA9685. BCM 14/15 (pins 8/10) are the serial console.

---

## 5. Test before running Kea

With the Pi on:

```bash
python3 tools/test_controls.py
```

Press every button, flip both toggles, turn the knob a click at a time and
press it. Each event prints once. **Ctrl-C prints a summary listing
anything MISSING** — that's your fix-list.

What good looks like:

- every button prints its own line, once per press
- both toggles print `ON` / `OFF` as they flip
- exactly one `CW` or `CCW` per detent — **no `PRESS` while turning**
- `PRESS` only when you actually push the shaft
- glitch count near zero

A `PRESS` on every detent means `+` isn't powered — recheck pin 1/17.

Then:

```bash
python3 src/main.py
```

---

## 6. What each control does

| Control | Action |
|---|---|
| Button 1 (Blue) | cycle worlds |
| Button 2 (Red) | Pomodoro |
| Button 3 (Green) | annunciator / stamp DONE |
| Button 4 | jump home to Nexus |
| Button 5 | open the Camera screen (GREEN is then the shutter) |
| Encoder turn | browse on Nexus, adjust on Console, tune elsewhere |
| Encoder press | select / next dial / home |
| Toggle A | per-screen role — each screen defines its own |
| Toggle B | global voice mute (`KEA_TOGGLE2_ROLE=autopilot` to change) |

Not wired yet? `KEA_ENCODER=0`, `KEA_TOGGLE=0`, `KEA_TOGGLE2=0` stop
floating pins firing phantom events.

---

## 7. Later: servos + PCA9685

No servo code exists yet, but the wiring is decided. **Signal** comes from
the Pi; **current** never does.

```
Pi pin 17 3.3 V ────────────────────────► PCA9685 VCC   ← NEVER 5 V
          (pin 1 is the encoder's `+`; 1 and 17 are the same rail)
Pi pin 3  SDA (BCM 2) ──────────────────► PCA9685 SDA
Pi pin 5  SCL (BCM 3) ──────────────────► PCA9685 SCL
Pi pin 9  GND ──────────┬───────────────► PCA9685 GND
4×AA +  ────────────────┼───────────────► PCA9685 V+
4×AA −  ────────────────┘   ← the two grounds MUST be joined
```

**Full procedure, with the staged bring-up: [SERVO_WIRING.md](SERVO_WIRING.md).**

- `VCC` to **3.3 V (pin 17)**, never 5 V. The board's I²C pull-ups go to `VCC`, so
  5 V there puts 5 V on GPIO 2/3, which are 3.3 V-only. This is the one
  that actually kills Pis.
- `V+` is a separate rail feeding only the servo plugs. It never touches
  the chip or the Pi, which is why battery voltage cannot reach the Pi.
- **The LM2596 is not used here.** It needs Vin ≥ Vout + 1.5 V, so 5 V out
  needs 6.5 V in and four AAs give 6.4 V at best — dropout from the first
  minute. It becomes the right part again with a 6×AA pack or a wall
  supply. Servos run direct off the 4×AA pack.
- Enable I²C once: `sudo raspi-config` → Interface Options → I2C.
- Verify the board answers: `i2cdetect -y 1` should show `40`.
- Never run servos off a Pi 5 V pin — the sag resets the board.
