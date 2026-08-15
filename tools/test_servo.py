#!/usr/bin/env python3
"""
test_servo.py — bring a servo up safely, one step at a time.

Follows hardware/SERVO_WIRING.md. Nothing here moves a servo unless you
ask it to, and nothing can drive one past its configured limits.

    python3 tools/test_servo.py --detect              # read only, moves nothing
    python3 tools/test_servo.py --show                # current calibration
    python3 tools/test_servo.py --channel 0 --calibrate   # SET left/centre/right
    python3 tools/test_servo.py --channel 0 --centre
    python3 tools/test_servo.py --channel 0 --sweep 60
    python3 tools/test_servo.py --channel 0 --go left

CALIBRATION IS THE POINT

--calibrate walks the servo by hand and lets you *mark* each position
where it actually is, then saves to ~/.kea_servos.json. Centre is stored
as its own number rather than computed as the midpoint, because a horn
mounts on splines and lands wherever the teeth allow: "monitor facing
you" is rarely halfway between the two stops.

THE ONE RULE WHILE TESTING

If a servo buzzes without moving, it is stalled: kill it now (Ctrl-C,
then pull the batteries) and check the mechanism. A stalled servo draws
its full stall current continuously, gets hot, and will flatten a 4×AA
pack in minutes. Every exit path here relaxes the channel, including
Ctrl-C.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from backend import servo                                   # noqa: E402

SPAN_MAX = 180.0


def detect():
    print("\nPCA9685")
    print(f"  address        {hex(servo.ADDR)}   (KEA_PCA9685_ADDR)")
    print(f"  i2c bus        {servo.BUS_N}          (KEA_I2C_BUS)")
    if servo.available():
        print("  status         FOUND — the board is answering")
    else:
        print(f"  status         NOT FOUND — {servo.error()}")
        print("\n  Checks, in order:")
        print("    1. sudo raspi-config -> Interface Options -> I2C -> Yes")
        print("    2. sudo apt install -y python3-smbus i2c-tools")
        print("    3. i2cdetect -y 1        (expect 40 in the grid)")
        print("    4. VCC on Pi pin 17 (3.3 V) — a board with no VCC is")
        print("       invisible on the bus. NEVER pin 2 or 4, those are 5 V.")
        print("    5. SDA on pin 3, SCL on pin 5")
    print("\nConfigured channels")
    for sv in servo.all_servos():
        state = "calibrated" if sv.calibrated else "NOT CALIBRATED"
        print(f"  {sv.name:<8} channel {sv.channel}   "
              f"{sv.lo:.0f}-{sv.hi:.0f} deg, centre {sv.centre_deg:.0f}   "
              f"{state} ({sv.source})")
    if not all(sv.calibrated for sv in servo.all_servos()):
        print("\n  Measure left / centre / right and save them:")
        print("      python3 tools/test_servo.py --channel 0 --calibrate")
    print()
    return 0 if servo.available() else 1


KEYS = """
  STEP 1 — find the middle          STEP 2 — set how far it swings
    a / d   -5 / +5 deg               [ / ]   narrow / widen by 10 deg
    j / l   -1 / +1 deg               , / .   narrow / widen by 2 deg
    2       mark this as {1:<11}   p       preview: {0} then {2}

  Fine-tune one end only (makes the travel asymmetric):  1 = {0}   3 = {2}
    s   save and quit        q   quit WITHOUT saving
"""


def _getch():
    """One keypress, raw if the terminal allows it."""
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            return sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:                                       # noqa: BLE001
        return (input("  key: ").strip().lower() or " ")[0]


def show_calibration():
    cal = servo.load_calibration()
    print(f"\n  {servo.CALIB_PATH}")
    if not cal:
        print("    nothing measured yet — run --calibrate\n")
    for sv in servo.all_servos():
        print(f"\n  {sv.name}  (channel {sv.channel})   source: {sv.source}")
        for lab in sv.labels:
            v = sv.positions.get(lab)
            mark = f"{v:6.1f} deg" if v is not None else "  not set"
            star = "  <- stored, not computed" if lab == sv.labels[1] else ""
            print(f"    {lab:<8} {mark}{star}")
        print(f"    limits   {sv.lo:.1f} - {sv.hi:.1f} deg"
              f"   {'CALIBRATED' if sv.calibrated else 'incomplete'}")
        env = "KEA_SERVO_" + sv.name.upper()
        if os.getenv(env):
            print(f"    WARNING  {env}={os.getenv(env)} is set and OVERRIDES")
            print(f"             the saved calibration. unset it to use what")
            print(f"             you measured.")
    print()
    return 0


def calibrate(sv):
    """Walk the servo by hand and mark left / centre / right."""
    env = "KEA_SERVO_" + sv.name.upper()
    if os.getenv(env):
        # Refuse to save quietly into a situation where the result is
        # ignored. Env beats the file everywhere in Kea; that is fine as a
        # rule, but silently losing a calibration to it is not.
        print(f"\n  {env} is set to {os.getenv(env)!r}.")
        print("  It overrides the calibration file, so anything measured here")
        print("  would be ignored. Unset it first:")
        print(f"      unset {env}")
        print("  ...and remove it from the service file if it lives there.\n")
        return 1

    lo_guard, hi_guard = 5.0, 175.0        # explore freely, stop short of the ends
    left_lab, mid_lab, right_lab = sv.labels
    print(f"\n  Calibrating {sv.name} on channel {sv.channel}")
    print(f"\n  Find the MIDDLE first — where it should sit at rest — and mark")
    print(f"  it with 2. Then widen the swing until the extremes are where you")
    print(f"  want; {left_lab} and {right_lab} are derived from the centre, so")
    print(f"  widening moves both at once.")
    print("\n  Stop the moment you feel resistance — a servo held against a")
    print("  stop is drawing stall current.")
    print(KEYS.format(*sv.labels))

    pos = sv.centre_deg
    span = sv.span or 0.0
    have_centre = False
    sv.write(pos)
    try:
        while True:
            if have_centre:
                l, _c, r = servo.derive(sv.centre_deg, span)
                state = (f"centre {sv.centre_deg:5.1f}   span {span:5.1f}"
                         f"   -> {left_lab} {l:.0f} / {right_lab} {r:.0f}")
            else:
                state = f"{pos:6.1f} deg    centre not marked yet"
            print(f"\r  {state}        ", end="", flush=True)
            sv.update()                    # idle-relax still applies here
            k = _getch()

            if k == "q":
                print("\n  quit — nothing saved")
                return 1
            if k == "s":
                break

            if k == "2":
                sv.set_position(mid_lab, pos)
                have_centre = True
                print(f"\r  centre marked at {pos:.1f} deg" + " " * 34)
                continue

            if have_centre and k in "[],.":
                span = max(0.0, min(2 * min(sv.centre_deg, SPAN_MAX - sv.centre_deg),
                                    span + {"[": -10, "]": 10, ",": -2, ".": 2}[k]))
                sv.set_span(span)
                l, _c, r = servo.derive(sv.centre_deg, span)
                sv.write(r if k in "]." else l)
                continue

            if k == "p" and have_centre:
                print(f"\r  preview: {left_lab} ... " + " " * 40, end="", flush=True)
                sv.go(left_lab, speed=4.0)
                time.sleep(0.4)
                sv.go(right_lab, speed=4.0)
                time.sleep(0.4)
                sv.centre(speed=4.0)
                pos = sv.centre_deg
                continue

            if k in "13" and have_centre:
                lab = left_lab if k == "1" else right_lab
                sv.set_position(lab, pos)
                span = sv.span
                print(f"\r  {lab} pinned at {pos:.1f} deg (now asymmetric)"
                      + " " * 18)
                continue

            step = {"a": -5, "d": 5, "j": -1, "l": 1}.get(k, 0)
            if not step:
                continue
            pos = max(lo_guard, min(hi_guard, pos + step))
            sv.write(pos)
    finally:
        sv.relax()

    if not have_centre:
        print("\n  not saved — the centre was never marked.\n")
        return 1
    if sv.span <= 0:
        print("\n  not saved — the swing is zero. Widen it with ] or .\n")
        return 1

    entry = sv.save()
    print(f"\n  saved to {servo.CALIB_PATH}")
    for lab in sv.labels:
        print(f"    {lab:<8} {entry[lab]:6.1f} deg")
    print(f"    limits   {min(entry[l] for l in sv.labels):.1f} - "
          f"{max(entry[l] for l in sv.labels):.1f} deg")
    print("\n  Verify it:")
    print(f"      python3 tools/test_servo.py --channel {sv.channel} "
          f"--go {sv.labels[1]}\n")
    return 0


def _pick(channel):
    for sv in servo.all_servos():
        if sv.channel == channel:
            return sv
    print(f"channel {channel} is not one of Kea's configured servos; "
          f"using wide-open limits for the test only")
    return servo.Servo(channel, 20.0, 160.0, f"ch{channel}")


def centre(sv):
    mid = sv.centre_deg
    print(f"  {sv.name}: moving to the measured centre ({mid:.0f} deg)...")
    sv.move_to(mid)
    time.sleep(0.6)
    print("  done — the servo should now go limp and silent (that is correct)")
    sv.relax()


def go_named(sv, where):
    if where not in sv.positions:
        print(f"  {sv.name} has no position {where!r}. "
              f"Known: {', '.join(sorted(sv.positions))}")
        print("  Run --calibrate to measure them.")
        return 2
    print(f"  {sv.name}: -> {where} ({sv.positions[where]:.0f} deg)")
    sv.go(where)
    time.sleep(0.5)
    sv.relax()
    return 0


def sweep(sv, span):
    mid = sv.centre_deg
    half = min(span / 2.0, (sv.hi - sv.lo) / 2.0)
    print(f"  {sv.name}: centring, then sweeping +/-{half:.0f} deg "
          f"within {sv.lo:.0f}-{sv.hi:.0f}")
    sv.move_to(mid)
    time.sleep(0.4)
    for target in (mid - half, mid + half, mid):
        print(f"    -> {target:.0f} deg")
        sv.move_to(target, speed=2.0)
        time.sleep(0.5)
    sv.relax()
    print("  done")


def jog(sv):
    """Find where it really binds, by hand, in small steps."""
    print(f"\n  {sv.name} on channel {sv.channel}")
    print("  Nudge until you FEEL resistance, then back off a few degrees.")
    print("  Record both ends and put them in KEA_SERVO_MONITOR / _FLAG.\n")
    print("    a / d   -5 / +5 deg        j / l   -1 / +1 deg")
    print("    c       centre             q       quit (relaxes)\n")
    print("  Limits are still enforced. To explore past them, widen the")
    print("  env var first — deliberately, not by accident.\n")

    pos = (sv.lo + sv.hi) / 2.0
    sv.write(pos)
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                print(f"\r  {pos:6.1f} deg   ", end="", flush=True)
                k = sys.stdin.read(1).lower()
                if k == "q":
                    break
                step = {"a": -5, "d": 5, "j": -1, "l": 1}.get(k, 0)
                if k == "c":
                    pos = (sv.lo + sv.hi) / 2.0
                elif step:
                    pos = sv.clamp(pos + step)
                else:
                    continue
                sv.write(pos)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:                                       # noqa: BLE001
        print("  (no raw terminal — falling back to typed input)")
        while True:
            raw = input("  angle, or blank to quit: ").strip()
            if not raw:
                break
            try:
                pos = sv.clamp(float(raw))
            except ValueError:
                continue
            sv.write(pos)
            print(f"    at {pos:.1f} deg")
    print(f"\n  finished at {pos:.1f} deg — relaxing")
    sv.relax()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detect", action="store_true",
                    help="read the board and report; moves nothing")
    ap.add_argument("--channel", type=int, help="which channel to drive")
    ap.add_argument("--centre", "--center", action="store_true",
                    dest="centre", help="move to the middle of its limits")
    ap.add_argument("--sweep", type=float, metavar="DEG",
                    help="sweep this many degrees total, slowly")
    ap.add_argument("--jog", action="store_true",
                    help="nudge by hand, without saving anything")
    ap.add_argument("--calibrate", action="store_true",
                    help="measure and SAVE left / centre / right")
    ap.add_argument("--show", action="store_true",
                    help="print the saved calibration")
    ap.add_argument("--go", metavar="NAME",
                    help="move to a saved position (left/centre/right)")
    args = ap.parse_args()

    if args.show:
        return show_calibration()
    if args.detect or args.channel is None:
        return detect()

    if not servo.available():
        print(f"\nNo PCA9685: {servo.error()}")
        print("Run with --detect for the checklist. Refusing to pretend "
              "a servo moved.\n")
        return 1

    sv = _pick(args.channel)
    try:
        if args.calibrate:
            return calibrate(sv)
        elif args.go:
            return go_named(sv, args.go)
        elif args.centre:
            centre(sv)
        elif args.sweep:
            sweep(sv, args.sweep)
        elif args.jog:
            jog(sv)
        else:
            print("nothing to do — pass --calibrate, --centre, --sweep, "
                  "--go or --jog")
            return 2
    except KeyboardInterrupt:
        # The important exit path: a stalled servo must not be left driven.
        print("\n  interrupted — relaxing the channel")
    finally:
        sv.relax()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
