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
| Button 1 — Blue (Cycle worlds) | 21 | **40** | switch to GND |
| Button 2 — Red (Pomodoro) | 20 | **38** | switch to GND |
| Button 3 — Green (Annunciator) | 26 | **37** | switch to GND |
| Button 4 — Home (jump to Nexus) | 13 | **33** | switch to GND |
| Button 5 — Console (settings) | 4 | **7** | switch to GND — **needs extender** |
| Encoder CLK | 5 | **29** | KY-040 `CLK` |
| Encoder DT | 6 | **31** | KY-040 `DT` |
| Encoder SW | 16 | **36** | KY-040 `SW` (shaft press) |
| Encoder **+** | 12 | **32** | see §3 — better: real 3.3 V on pin 1/17 |
| Toggle A (centre leg) | 19 | **35** | per-screen role; outer leg to GND |
| Toggle B (centre leg) | 27 | **13** | global mute; **needs extender** |
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

## 2. Parts vs code

All 8 inputs are now wired up in software:

| You have | Code supports | Status |
|---|---|---|
| 5 buttons | **5** | ✅ all wired (Home + Console added) |
| 2 toggles | **2** | ✅ A = per-screen, B = global mute |
| 1 encoder | **1** | ✅ turn + press |
| 3 servos (SG92R) | **none** | ⛔ no servo code yet |
| PCA9685 | **none** | ⛔ not driven yet |

The exposed block (27–40) is now full: buttons 1–4, the encoder and
toggle A use it all. **Button 5 (pin 7) and toggle B (pin 13) sit under
the display**, so they need the extender — and their defaults are only
*likely* free. Confirm both before soldering (§2a).

Every pin is env-overridable, so you never have to edit code:

```bash
KEA_BTN_CONSOLE=22 KEA_TOGGLE2_PIN=23 python3 src/main.py
```

Full list: `KEA_BTN_BLUE`, `KEA_BTN_RED`, `KEA_BTN_GREEN`, `KEA_BTN_HOME`,
`KEA_BTN_CONSOLE`, `KEA_ENC_CLK`, `KEA_ENC_DT`, `KEA_ENC_SW`,
`KEA_TOGGLE_PIN`, `KEA_TOGGLE2_PIN`.

### 2a. With the stacking extender: what you actually gain

Reaching pins 1–26 does **not** mean they're free — the display driver
still owns the ones it uses. Find out on your own Pi rather than trusting
a datasheet:

```bash
sudo apt install raspi-gpio      # once
python3 tools/check_free_pins.py
```

It reads your `config.txt` overlays, asks the running Pi what every pin is
doing, cross-references the pins Kea already claims, and prints the
candidates. Anything reported **ALT0–ALT5** belongs to a peripheral — SPI
for the display, I²C, UART — and is off-limits.

**The real win isn't GPIOs, it's power.** The extender finally gives you:

| Now reachable | Pins | Why it matters |
|---|---|---|
| **3.3 V** | 1, 17 | proper supply for the KY-040's `+` — retires the GPIO-12 hack (see §3) |
| **5 V** | 2, 4 | the 30 mm fan, and the amp if you ever go wired |
| **I²C** SDA/SCL | 3, 5 | the PCA9685 — needs exactly these two |

On a typical SPI 3.5" panel the display claims **SPI0** (pins 19, 21, 23,
24, 26) plus a few control lines (often 11, 18, 22, and sometimes 12), and
leaves BCM 4 (pin 7), 27 (pin 13), 22 (pin 15), 23 (pin 16) free — which
would be plenty for the extra buttons and toggle. **Confirm with the
script before soldering**; the exact set depends on your overlay.

Two to treat carefully: BCM 2/3 (pins 3/5) have fixed 1.8 kΩ pull-ups —
fine for I²C, poor for buttons. BCM 14/15 (pins 8/10) are the serial
console unless you've disabled it.

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

- **Now that you have the extender, the better fix is real 3.3 V:** wire
  `+` → **pin 1 or 17** and run Kea with `KEA_ENCODER_VCC=-1` so it stops
  driving pin 32. A real rail is stiffer than a GPIO and frees BCM 12.
- Without the extender: wire `+` → pin 32. Don't leave it floating.
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
python3 tools/test_controls.py      # all 8 inputs, with a summary
```

Press every button, flip both toggles, turn and press the knob. Each
event prints once. Ctrl-C gives a summary listing anything **MISSING** —
that's your fix-list. `--monitor` shows raw live pin levels instead.

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
| Toggle A | per-screen role (each screen defines its own) |
| Toggle B | global voice mute (`KEA_TOGGLE2_ROLE=autopilot` to change) |

If a toggle ends up backwards once nutted into the deck, use
`KEA_TOGGLE_INVERT=1` / `KEA_TOGGLE2_INVERT=1` rather than rewiring.

Note: if you haven't wired the encoder or toggle yet, start Kea with
`KEA_ENCODER=0` / `KEA_TOGGLE=0` so floating pins don't fire phantom
events.
