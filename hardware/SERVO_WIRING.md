# Kea — servo wiring (PCA9685 + 2× SG92R + 4×AA)

Two servos: **channel 0 = monitor rotation**, **channel 1 = semaphore arm**.
Fourteen channels spare for later.

Read this whole page before stripping a wire. The order of the bring-up
section matters — it is arranged so that every mistake you can make is
caught at a stage where it is still harmless.

---

## The one thing to understand first

**The PCA9685 has two completely separate power domains.** This is the
whole reason the board is safe, and the whole reason it can be made
unsafe:

| Rail | Feeds | Comes from |
|---|---|---|
| `VCC` | the PCA9685 chip's logic, and the I²C pull-up resistors | **Pi 3.3 V** |
| `V+` | the servo header power pins, the protection diode, the 100 µF cap | **battery** |

`V+` does **not** connect to the chip, to `VCC`, or to any signal pin. It
is a dumb power rail that runs to the servo plugs and nothing else.

So the Pi never sees battery voltage. It sees 3.3 V on `VCC`, 3.3 V logic
on SDA/SCL, and a shared ground. **That is the entire answer to "will
this burn my Pi".**

---

## The three rules

**1. `VCC` goes to Pi 3.3 V — pin 1. Never 5 V.**

This is the one that actually kills Pis, and it is not obvious. The board
has pull-up resistors on SDA and SCL **to whatever `VCC` is**. Put 5 V on
`VCC` and those resistors pull the I²C lines toward 5 V — straight onto
GPIO 2 and GPIO 3, which are 3.3 V-only pins with no protection. The chip
runs happily on 3.3 V (its spec is 3.0–5.5 V), so there is nothing to
gain and a Pi to lose.

<details>
<summary><b>"But every tutorial wires VCC to 5 V — doesn't the board need it?"</b></summary>

No. Your board's own datasheet settles it:

> Die Versorgung der Lasten (z. B. Servos, LEDs) erfolgt über den
> separaten **V+** Anschluss mit **3,3 V bis 5 V**. Die IC-Spannung
> (**VCC**) wird getrennt mit **3,0 V bis 5,5 V** versorgt.

BerryBase rates `VCC` at **3.0–5.5 V**. 3.3 V is in spec, not a
workaround. The 5 V advice is Arduino heritage — on a 5 V
microcontroller you would match logic levels — carried over to Pi
tutorials because it usually works, not because it is needed.

**Why it is the risky choice here.** I²C is open-drain: devices only
pull the line *low*, and the HIGH level comes entirely from pull-up
resistors. This board's pull-ups go to `VCC`; the Pi has its own 1.8 kΩ
pull-ups to 3.3 V on GPIO 2/3. Put 5 V on `VCC` and the two fight:

```
(5 / 10k + 3.3 / 1.8k) / (1/10k + 1/1.8k)  ≈  3.56 V idle
```

About 0.26 V over the rail, forward-biasing the GPIO protection diodes
and pushing current back into the Pi's 3.3 V supply. Usually survivable,
still out of spec, and worse if the board is ever powered while the Pi
is off.

**The one real tradeoff.** The PWM output high level equals `VCC`, so at
3.3 V the servos get 3.3 V pulses rather than 5 V. SG92R-class servos
trigger well below that and are fine. If a servo ever behaves
erratically while the wiring is otherwise proven, this is the thing to
revisit — the fix is a proper bidirectional level shifter on SDA/SCL
plus 5 V on `VCC`, not simply moving the `VCC` wire.

Current is a non-issue: the chip draws about 10 mA.

</details>

**2. Never connect the battery to any Pi 5 V pin.**

The Pi's 5 V pins are an *output* from its own regulator. Feeding them
from a battery makes two supplies fight. The battery's only job is `V+`.

**3. The grounds must be joined.**

Battery − and Pi GND must be the same net or the servos get a PWM signal
with no reference and will twitch, buzz, or ignore you. On this board
that happens automatically — the `GND` on the power terminal and the
`GND` on the header are the same net internally — but it is the step
people forget, so check it exists.

---

## Connections

```
                    ┌─────────────── Pi (via the GPIO extender) ─────────┐
                    │                                                     │
   pin 1   3.3 V ───┼──────────────────────────────► PCA9685  VCC        │
   pin 3   SDA  ────┼──────────────────────────────► PCA9685  SDA        │
   pin 5   SCL  ────┼──────────────────────────────► PCA9685  SCL        │
   pin 6   GND  ────┼───────────┬──────────────────► PCA9685  GND        │
                    └───────────┼───────────────────────────────────────-┘
                                │
   4×AA  +  (red) ──────────────┼──────────────────► PCA9685  V+
   4×AA  −  (black) ────────────┘

   PCA9685 channel 0 ──────────► servo: monitor rotation
   PCA9685 channel 1 ──────────► servo: semaphore arm
```

| From | To | Note |
|---|---|---|
| Pi **pin 1** (3.3 V) | PCA9685 `VCC` | **not pin 2, not pin 4** — those are 5 V |
| Pi **pin 3** (BCM 2) | PCA9685 `SDA` | |
| Pi **pin 5** (BCM 3) | PCA9685 `SCL` | |
| Pi **pin 6** (GND) | PCA9685 `GND` (header) | any GND pin works: 6, 9, 14, 20, 25, 30, 34, 39 |
| Battery **+** | PCA9685 `V+` (green terminal block) | |
| Battery **−** | PCA9685 `GND` (green terminal block) | |
| `OE` | **leave unconnected** | see below |

**`OE` (output enable) is active LOW** and has a pull-down on the board,
so leaving it unconnected means "outputs enabled". You *can* wire it to a
spare GPIO as a hardware kill switch for all sixteen channels — drive it
HIGH and every servo signal stops instantly, regardless of what the
software is doing. Worth doing later; not needed now.

### Servo plugs — check the silkscreen before pushing

Each channel is a 3-pin group. On this board the order is:

```
   PWM   (signal)   ← nearest the chip     → servo ORANGE / yellow
   V+    (power)    ← middle               → servo RED
   GND              ← outer board edge     → servo BROWN / black
```

**Verify against your board's silkscreen** — it is printed next to the
first channel. Getting this backwards puts battery voltage into the
servo's signal line, which kills the servo (not the Pi, but still).

The brown wire goes to the edge of the board. If your servo lead is
brown/red/orange, brown is ground.

---

## Why the LM2596 is not in this circuit

You have the buck converter, and it does not belong here. Its datasheet
requires **Vin ≥ Vout + 1.5 V**. For 5 V out that needs 6.5 V in. Four
alkaline AAs give 6.4 V brand new, 6.0 V nominal, and less under load —
so the regulator is in dropout from the first minute and its output
collapses exactly when a servo pulls current.

A 4-cell pack cannot usefully feed it. Keep it in the box: if you ever
move to a 6×AA holder (9 V) or a wall supply, it becomes the right part
and gives you a properly regulated 5 V for its whole discharge.

### What running direct at 6 V actually means

- **Fresh alkalines read ~6.4 V open-circuit**, which is over the SG92R's
  6 V ceiling. But that is the *no-load* reading. Alkaline cells have
  high internal resistance (~0.15–0.3 Ω each), so the moment a servo
  draws ~700 mA the pack sags 0.4–0.8 V. **The servo sees ~5.2–5.6 V
  while it is actually moving** and only sees 6.4 V sitting still doing
  nothing. Cost: a slightly warmer motor and somewhat shorter life.
- **As the pack drains**, servos keep working down to about 4.2 V, then
  get slow, weak and jittery and stop holding position. Below ~3.5 V they
  stop. Nothing is damaged at any point, and **nothing happens to the
  Pi** — it is on its own supply. A sagging `V+` with `VCC` steady at
  3.3 V is precisely the case those separate rails exist for.
- **Your board's `V+` is printed 3.3–5 V.** The parts on that rail are a
  protection diode and an electrolytic cap, both normally rated well
  above 6 V, and Adafruit's equivalent board rates `V+` to 6 V. Very
  likely fine — but it is outside what BerryBase printed, so it is your
  call knowingly made rather than a spec I am claiming you meet.

**The real enemy is stall current, not voltage.** A servo pushed against
a mechanical end stop draws its full stall current continuously, gets
hot, and flattens the pack in minutes. That is prevented in software:
`backend/servo.py` clamps every channel to travel limits and cuts the
pulse when idle. Set those limits honestly — see below.

---

## Bring-up, in this order

Each stage adds one thing and proves it before the next. Do not skip
ahead; the whole point is that a mistake at stage 1 cannot hurt anything
because the battery is not in the circuit yet.

### Stage 0 — nothing connected

**Take the batteries out of the holder.** They stay out until stage 4.
The holder's push-button lead is live the moment cells are in it.

### Stage 1 — logic only, no battery, no servos

Wire the four Pi ↔ PCA9685 lines from the table above. Nothing else.

Enable I²C once, if you have not:

```bash
sudo raspi-config      # Interface Options → I2C → Yes
sudo reboot
```

Then:

```bash
sudo apt install -y python3-smbus i2c-tools
i2cdetect -y 1
```

**Expected:** `40` appears in the grid. That is the PCA9685 answering.

- Nothing at all → check SDA/SCL are on pins 3 and 5, and that `VCC` has
  3.3 V. A board with no `VCC` is invisible on the bus.
- Note whether the board's **green LED** is lit at this stage. If it is,
  that LED reports `VCC`; if it is dark until stage 4, it reports `V+`.
  Worth knowing which, because it is your at-a-glance power indicator
  from then on.

At this stage the servo rail is not connected, so even if you have
mixed up `V+` and `VCC` nothing can be damaged. **That is why this stage
exists.**

### Stage 2 — power off, wire the battery

```bash
sudo shutdown -h now
```

Wait for the green activity LED to stop, then pull the Pi's power.

Connect the battery holder's red lead to `V+` and black to `GND` on the
green terminal block. **Batteries still out.** Screw the terminals down
firmly and tug each wire — a strand of stranded wire bridging `V+` to
`GND` is a dead short across the pack.

The board has reverse-polarity protection on `V+`, which is a real safety
net. Do not use it as one: check the silkscreen.

### Stage 3 — one servo, still unpowered

Plug **one** servo into **channel 0**, brown wire to the board edge.

Never plug or unplug a servo while the rail is live.

### Stage 4 — first power-on

Put the batteries in. Power the Pi. Then:

```bash
cd ~/Kea
python3 tools/test_servo.py --detect
```

This only reads the board — it does not move anything. It confirms the
chip is present and reports what it finds.

Then move it, gently and within limits:

```bash
python3 tools/test_servo.py --channel 0 --centre
python3 tools/test_servo.py --channel 0 --sweep 60
```

**Expected:** a smooth move to centre, then a slow sweep ±30° and back,
then the servo goes quiet and limp (the pulse is cut when idle — that is
correct, not a fault).

**If the servo buzzes continuously without moving**, it is stalled
against something. Kill it immediately (Ctrl-C, then pull the batteries)
and check the mechanism before trying again. A buzzing servo is drawing
stall current and getting hot.

### Stage 5 — find the real travel limits

Before you trust either servo in the chassis, find where it actually
binds, then tell the software:

```bash
python3 tools/test_servo.py --channel 0 --jog
```

Nudge in small steps until you feel resistance, back off a few degrees,
and record that. Do the same the other way. Then set:

```bash
KEA_SERVO_MONITOR="0:35:145"      # channel : min angle : max angle
KEA_SERVO_FLAG="1:10:100"
```

Those limits are hard-clamped in software, so nothing can later command
the servo into its end stop.

### Stage 6 — second servo

Power down, plug the semaphore arm into channel 1, power up, repeat
stages 4 and 5 for channel 1.

---

## If something is wrong

| Symptom | Most likely cause |
|---|---|
| `i2cdetect` shows nothing | `VCC` not connected, or SDA/SCL swapped |
| `i2cdetect` shows `40`, servo does nothing | no battery on `V+`, or grounds not joined |
| Servo twitches randomly | grounds not joined (rule 3) |
| Servo buzzes, will not move | stalled — mechanical bind, or limits set too wide |
| Servo moves then Pi reboots | battery wired to a Pi 5 V pin — **stop, rule 2** |
| Servo weak and slow, was fine before | batteries flat; expect this well before they read 0 V |
| Board hot | short across `V+`/`GND`, or a servo stalled for a long time |

**If the Pi ever reboots when a servo moves**, that is the one symptom
that means the power domains are not actually separate. Disconnect the
battery and re-check rules 1 and 2 before anything else.
