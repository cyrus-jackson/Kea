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

## 1. Fit the extender

The display mates onto the extender's pass-through header; the extender
brings the same 40 pins out sideways where you can reach them.

1. Pi off, power unplugged.
2. Extender onto the Pi's header — **pin 1 to pin 1**. Check the corner
   marking; on backwards it will short 5 V into GPIOs.
3. Display onto the extender's pass-through.
4. Power up and confirm the display still works **before** wiring anything
   else. If it doesn't, stop — the extender is seated wrong.

---

## 2. The connections

| # | Signal | BCM | **Pin** | Wire to |
|---|---|---|---|---|
| 1 | Button — Blue (cycle worlds) | 21 | **40** | other leg → GND |
| 2 | Button — Red (Pomodoro) | 20 | **38** | other leg → GND |
| 3 | Button — Green (annunciator) | 26 | **37** | other leg → GND |
| 4 | Button — Home (to Nexus) | 13 | **33** | other leg → GND |
| 5 | Button — Console (settings) | 4 | **7** | other leg → GND |
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
KEA_BTN_CONSOLE=22 KEA_TOGGLE2_PIN=23 python3 src/main.py
```

Overridable: `KEA_BTN_BLUE`, `KEA_BTN_RED`, `KEA_BTN_GREEN`,
`KEA_BTN_HOME`, `KEA_BTN_CONSOLE`, `KEA_ENC_CLK`, `KEA_ENC_DT`,
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
| Button 5 | open the Console (brightness / dwell) |
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
4×AA ──► LM2596S (set to 5.0 V FIRST) ──► PCA9685 V+
Pi pin 1  3.3 V ────────────────────────► PCA9685 VCC
Pi pin 3  SDA (BCM 2) ──────────────────► PCA9685 SDA
Pi pin 5  SCL (BCM 3) ──────────────────► PCA9685 SCL
Battery − ──────────┬───────────────────► PCA9685 GND
Pi GND ─────────────┘   ← the two grounds MUST be joined
```

- Set the buck to **5.0 V on its voltmeter before** connecting any servo —
  the trimmer reaches 24 V.
- Enable I²C once: `sudo raspi-config` → Interface Options → I2C.
- Verify the board answers: `i2cdetect -y 1` should show `40`.
- Never run servos off a Pi 5 V pin — the sag resets the board.
