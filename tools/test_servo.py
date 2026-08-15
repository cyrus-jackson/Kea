#!/usr/bin/env python3
"""
test_servo.py — bring a servo up safely, one step at a time.

Follows hardware/SERVO_WIRING.md. Nothing here moves a servo unless you
ask it to, and nothing can drive one past its configured limits.

    python3 tools/test_servo.py --detect            # read only, moves nothing
    python3 tools/test_servo.py --channel 0 --centre
    python3 tools/test_servo.py --channel 0 --sweep 60
    python3 tools/test_servo.py --channel 0 --jog   # find the real limits

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
        print("    4. VCC on Pi pin 1 (3.3 V) — a board with no VCC is")
        print("       invisible on the bus. NEVER pin 2 or 4, those are 5 V.")
        print("    5. SDA on pin 3, SCL on pin 5")
    print("\nConfigured channels")
    for sv in servo.all_servos():
        print(f"  {sv.name:<8} channel {sv.channel}   "
              f"limits {sv.lo:.0f}-{sv.hi:.0f} deg")
    print("\n  Set limits once you know them (SERVO_WIRING.md stage 5):")
    print("    KEA_SERVO_MONITOR='0:35:145'     channel:min:max")
    print("    KEA_SERVO_FLAG='1:10:100'")
    print()
    return 0 if servo.available() else 1


def _pick(channel):
    for sv in servo.all_servos():
        if sv.channel == channel:
            return sv
    print(f"channel {channel} is not one of Kea's configured servos; "
          f"using wide-open limits for the test only")
    return servo.Servo(channel, 20.0, 160.0, f"ch{channel}")


def centre(sv):
    mid = (sv.lo + sv.hi) / 2.0
    print(f"  {sv.name}: moving to centre ({mid:.0f} deg)...")
    sv.move_to(mid)
    time.sleep(0.6)
    print("  done — the servo should now go limp and silent (that is correct)")
    sv.relax()


def sweep(sv, span):
    mid = (sv.lo + sv.hi) / 2.0
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
                    help="nudge by hand to find the real travel limits")
    args = ap.parse_args()

    if args.detect or args.channel is None:
        return detect()

    if not servo.available():
        print(f"\nNo PCA9685: {servo.error()}")
        print("Run with --detect for the checklist. Refusing to pretend "
              "a servo moved.\n")
        return 1

    sv = _pick(args.channel)
    try:
        if args.centre:
            centre(sv)
        elif args.sweep:
            sweep(sv, args.sweep)
        elif args.jog:
            jog(sv)
        else:
            print("nothing to do — pass --centre, --sweep or --jog")
            return 2
    except KeyboardInterrupt:
        # The important exit path: a stalled servo must not be left driven.
        print("\n  interrupted — relaxing the channel")
    finally:
        sv.relax()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
