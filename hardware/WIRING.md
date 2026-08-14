# Kea — wiring sheet

**Generated from the code.** Every pin below is read out of
`src/hardware_input.py` and `src/backend/settings.py` by
`tools/gen_wiring.py`. Re-run it after changing any pin:

```bash
python3 tools/gen_wiring.py
```

> ⚠️ **Power off the Pi before wiring anything.** Get GND right first — a
> switch leg on 5 V instead of GND can kill a GPIO.

---

## 1. The connections

| Signal | BCM | Header pin | Note |
|---|---|---|---|
| Button — Blue (Cycle worlds) | 21 | **40** | switch to GND |
| Button — Red (Pomodoro) | 20 | **38** | switch to GND |
| Button — Green (Annunciator) | 26 | **37** | switch to GND |
| Encoder CLK | 5 | **29** | KY-040 `CLK` |
| Encoder DT | 6 | **31** | KY-040 `DT` |
| Encoder SW | 16 | **36** | KY-040 `SW` (shaft press) |
| Encoder **+** | 12 | **32** | see §3 — the code drives this HIGH |
| Toggle (centre leg) | 19 | **35** | one outer leg to GND, third unused |
| Ground (common) | — | **30, 34, 39** | every switch's other leg |

Every input uses the Pi's **internal pull-up**, so each switch simply
shorts its pin to ground. No resistors. The pin idles HIGH and reads LOW
when pressed.

### Per device

**12 mm buttons (×3 wired):** 2 solder pins, no polarity. One pin → its
GPIO, the other → any ground. That's it.

**KY-040 encoder:** `CLK`→29, `DT`→31, `SW`→36, `GND`→ground, `+`→32.

**Toggle (SPDT, 3 legs):** **centre** leg → pin 35, **one** outer leg →
ground, third leg unused. Which outer leg you pick only decides which
physical direction means "on"; if it ends up backwards, run Kea with
`KEA_TOGGLE_INVERT=1` rather than rewiring.

---

## 2. What's left over — read this before you wire

Your parts and the software don't match yet:

| You have | Code supports | Gap |
|---|---|---|
| 5 buttons | **3** | 2 buttons have no pin and no function |
| 2 toggles | **1** | 2nd toggle has no pin and no function |
| 3 servos (SG92R) | **none** | no servo code exists yet |
| PCA9685 | **none** | not driven by any code yet |

**Only ONE spare pin remains on the exposed block** (27–40): pin **33**
(BCM 13). Pins 27/28 are reserved for HAT EEPROM — don't use them.

So the 4th button can go on pin 33, but the 5th button, the 2nd toggle
and the PCA9685 all need pins *underneath* the display — which is exactly
what your **GPIO Winkel-Adapter (157081)** is for. Which of those lower
pins are free depends on your display's overlay, so **verify before
wiring** rather than trusting a guess:

```bash
gpio readall          # or: pinctrl get      (shows what each pin is doing)
dtoverlay -h <your-overlay>
```

Ask me to add the extra buttons/toggle to the code and I'll assign pins
and wire up the events — right now those parts would do nothing.

---

## 3. The `+` pin on the encoder (important)

The code **drives BCM 12 (pin 32) HIGH as a stand-in 3.3 V rail** and
expects the KY-040's `+` to be wired there:

```python
GPIO.setup(ENC_VCC, GPIO.OUT)
GPIO.output(ENC_VCC, GPIO.HIGH)
```

Why: pins 27–40 carry no 3.3 V, and the KY-040 has 10 kΩ pull-ups from
CLK/DT up to `+`. Left floating, grounding one data line drags the others
to ~0.9 V — inside the Pi's undefined band — which shows up as **a phantom
button press on every detent**. The board's pull-ups draw well under 1 mA,
so a GPIO can supply them.

- **Wire `+` → pin 32.** Don't leave it floating.
- Prefer real 3.3 V? Use pin 1 or 17 via the extender and run Kea with
  `KEA_ENCODER_VCC=-1` so it stops driving pin 32.
- **3.3 V only — never 5 V.** Through those pull-ups, 5 V would go
  straight into GPIO 5/6 and damage the Pi.

---

## 4. Servo power — do not take it from the header

When you get to the servos: **signal** comes from the Pi, **current** does
not.

```
4×AA ──► LM2596S (set to 5.0 V FIRST) ──► PCA9685 V+
Pi 3.3 V + SDA/SCL ─────────────────────► PCA9685 VCC/SDA/SCL
Battery GND ────────┬───────────────────► PCA9685 GND
Pi GND ─────────────┘   ← the two grounds MUST be joined
```

- Set the buck to **5.0 V with its voltmeter before** connecting servos —
  its trimmer reaches 24 V.
- PCA9685 talks I²C: **SDA = BCM 2 (pin 3), SCL = BCM 3 (pin 5)** — both
  under the display, so you need the extender.
- Never power servos from a Pi 5 V pin: the sag resets the board.

---

## 5. Check before powering on

1. **No leg on a 5 V pin** (2 or 4). Confirm each switch goes GPIO → GND.
2. **Continuity**: press each button, check its GPIO pin shorts to GND.
   Released, it must be open.
3. **Encoder `+` on pin 32**, not 5 V.
4. Boot, then run the tester before Kea:

```bash
python3 tools/test_encoder.py
```

Turn the knob a click at a time: exactly one `CW`/`CCW` per detent, and
`CLK=1 DT=1` at rest. Press the shaft: a lone `PRESS`. Flip the toggle:
`TOGGLE -> ON/OFF`.

Then check the buttons — Kea prints a line for each press:

```bash
python3 src/main.py     # press each button, watch stdout
```

---

## 6. Known software issue (not a wiring fault)

The encoder currently posts its events **from its polling thread**.
`pygame.event.post()` can fail silently off the main thread, so the dial
may decode perfectly in `test_encoder.py` and still do nothing in Kea.
The fix (queue in the thread, post on the main thread) was written and
then lost when `master` was reset. If turning the knob does nothing while
the tester looks perfect, that's this — ask me to re-apply it.

Also: if you haven't wired the encoder or toggle yet, start Kea with
`KEA_ENCODER=0` / `KEA_TOGGLE=0` so floating pins don't fire phantom
events.
