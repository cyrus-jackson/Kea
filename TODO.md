# Kea — TODO

Living list. Newest context at the top of each item so it's easy to pick
back up cold.

---

## 🔧 On hold — one wire: KY-040 `+` pin

**Do this:** run a jumper from the KY-040's **`+` pin** to **Pi pin 32 (BCM 12)**.
Then re-run `python3 tools/test_encoder.py`.

**Why:** the encoder's rotation already works perfectly (clean detents, correct
direction). But `+` is currently unconnected, so the board's onboard 10 kΩ
pull-ups for DT and SW hang off a dead rail. Grounding DT during a turn drags
that rail down, which drags SW to ~0.78–0.94 V — under the Pi's 0.8 V
"guaranteed LOW" line — so **every detent fakes a button press**. CLK is
unaffected because that board's CLK pull-up isn't populated, which is exactly
why SW tracked DT but ignored CLK in testing.

The software side is already done: both `main.py` and `test_encoder.py` set
BCM 12 as an output and drive it HIGH as a 3.3 V rail at startup. Nothing to
change in code — it's purely the one jumper.

**Expected after the fix:** no phantom PRESS lines, and the glitch count should
drop too (SW's coupling was loading DT).

Alternatives if GPIO 12 is ever needed elsewhere:
- `KEA_ENCODER_VCC=13` → use pin 33 instead
- `KEA_ENCODER_VCC=-1` and desolder R1/R2/R3 from the KY-040
- Real 3.3 V from pin 1/17 via a stacking header — **3.3 V only, never 5 V**

While it's unwired, `KEA_ENCODER=0` stops floating pins firing phantom events.

**Also unverified:** the toggle read `TG=0` for the whole test but was never
flipped, so its two positions are still unconfirmed. Flip it during the next
test run — if the direction feels backwards once it's nutted into the deck,
set `KEA_TOGGLE_INVERT=1` rather than unsoldering.

---

## 🖨️ Printing

- [ ] Print remaining chassis parts and assemble
- [ ] After printing: measure and set `pwr_depth` / `pwr_z` so the power slot
      lands on the Pi's jack (run `python3 hardware/chassis/check_geometry.py`
      after any parameter change — 18 checks, must exit 0)

---

## 🎥 Camera — Cyrus is doing this one

Left deliberately untouched. The mount, ribbon routing and top slot are all
built and waiting for it.

---

## 💡 Ideas not yet started

- [ ] **Kea's face** — an expressive lens driven by real machine state
      (calm when the docket is clear, narrowed when overdue, drowsy at night,
      delighted at a milestone, uncomfortable when the core is hot). The voice
      already fires on all these events, so the face plugs into the same hooks.
      This is the missing centrepiece for the BB-8 feel.
- [ ] **Moods with memory** — persistent mood derived from history rather than
      the current instant: sulky after days of ignored reminders, proud after a
      focus streak. Colours the face, the chirps, and the protocol's tone.
- [ ] **Boot as an appliance** — systemd unit so the Pi comes up straight into
      Kea kiosk-style, plus a short splash while pygame initialises.
- [ ] **Night dim** — the TFT runs at full brightness at 3am for nobody. Dim
      after a quiet hour, wake on button press.
