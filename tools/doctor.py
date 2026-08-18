#!/usr/bin/env python3
"""
doctor.py — is Kea healthy? One command, one answer.

    python3 tools/doctor.py              # everything passive, ~15 s
    python3 tools/doctor.py -v           # ...with the full output of each check
    python3 tools/doctor.py --slow       # also the network/offload round-trip
    python3 tools/doctor.py --interactive  # also press every button, move servos
    python3 tools/doctor.py --only servo,display

WHY THIS EXISTS

There were nine separate check tools and no way to ask "is the machine
alright". You had to remember all nine, know which ones were slow, and
read nine different output formats to find the one line that mattered.

DELEGATES, NEVER DUPLICATES

Each existing tool is run as a subprocess and its exit code becomes the
verdict. Nothing is reimplemented here, so a check cannot drift from the
tool that owns it — fix check_display.py and this gets the fix for free.
The only checks written inline are the ones no tool owned: the I²C
servo board, system health, and configuration sanity.

PASSIVE BY DEFAULT

Nothing moves and nothing is asked of you unless you pass --interactive.
You should be able to run this over SSH on a machine you cannot see,
which means it must not sit waiting for a button press that will never
come, and must not swing a monitor at a wall.

FOUR VERDICTS, AND THE DIFFERENCE MATTERS

    PASS   working
    WARN   working, but something will bite later
    FAIL   broken, with the fix printed
    SKIP   cannot be checked here (not a Pi, no hardware attached)

SKIP is not a soft FAIL. Running this on a laptop should not produce a
wall of red for hardware that was never meant to be there.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
GLYPH = {PASS: "ok  ", WARN: "warn", FAIL: "FAIL", SKIP: "--  "}

results = []          # (group, name, status, detail, fix)


def record(group, name, status, detail="", fix=""):
    results.append((group, name, status, detail, fix))
    return status


def sh(cmd, timeout=25):
    """Run a command, never raise. Returns (rc, output)."""
    try:
        p = subprocess.run(cmd, shell=isinstance(cmd, str), timeout=timeout,
                           capture_output=True, text=True, cwd=ROOT)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except FileNotFoundError:
        return 127, "command not found"
    except Exception as exc:                                # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


def on_pi():
    try:
        with open("/proc/device-tree/model", encoding="utf-8") as f:
            return "raspberry pi" in f.read().lower()
    except OSError:
        return False


# ── delegated checks ────────────────────────────────────────────────────────
def delegated(group, name, script, args=(), timeout=60, pi_only=False,
              verbose=False):
    """Run one of the existing tools and take its exit code as the verdict."""
    if pi_only and not on_pi():
        return record(group, name, SKIP, "not running on a Pi")
    path = os.path.join(ROOT, "tools", script)
    if not os.path.exists(path):
        return record(group, name, FAIL, f"{script} is missing")
    rc, out = sh([sys.executable, path, *args], timeout=timeout)
    if verbose:
        print(f"\n----- {script} {' '.join(args)}\n{out.rstrip()}\n-----")
    last = [l for l in out.strip().splitlines() if l.strip()]
    detail = last[-1].strip()[:64] if last else ""
    if rc == 0:
        return record(group, name, PASS, detail)
    if rc == 124:
        return record(group, name, WARN, "timed out",
                      f"run it alone: python3 tools/{script}")
    return record(group, name, FAIL, detail,
                  f"python3 tools/{script} {' '.join(args)}")


# ── checks nothing else owns ────────────────────────────────────────────────
def check_python():
    v = sys.version_info
    record("code", "python", PASS if v >= (3, 7) else FAIL,
           f"{v.major}.{v.minor}.{v.micro}",
           "Kea needs Python 3.7+")
    try:
        import pygame                                       # noqa: F401
        record("code", "pygame", PASS, pygame.version.ver)
    except ImportError:
        record("code", "pygame", FAIL, "not installed",
               "sudo apt install -y python3-pygame")


def check_servos():
    try:
        from backend import servo
    except Exception as exc:                                # noqa: BLE001
        return record("servo", "driver", FAIL, f"import failed: {exc}")

    if servo.available():
        record("servo", "PCA9685", PASS, f"answering at {hex(servo.ADDR)}")
    elif on_pi():
        record("servo", "PCA9685", FAIL, servo.error() or "not found",
               "python3 tools/test_servo.py --detect")
    else:
        record("servo", "PCA9685", SKIP, "no I2C bus (not a Pi)")

    for sv in servo.all_servos():
        if sv.calibrated:
            record("servo", f"{sv.name} calibration", PASS,
                   f"{sv.lo:.0f}-{sv.hi:.0f} deg, centre {sv.centre_deg:.0f} "
                   f"({sv.source})")
        else:
            record("servo", f"{sv.name} calibration", WARN,
                   f"not measured — using {sv.source}s",
                   f"python3 tools/test_servo.py --channel {sv.channel} "
                   f"--calibrate")
        env = "KEA_SERVO_" + sv.name.upper()
        if os.getenv(env) and sv.calibrated:
            record("servo", f"{sv.name} override", WARN,
                   f"{env} is shadowing the saved calibration",
                   f"unset {env}")


def check_controls():
    """Can the GPIO pins be claimed at all? Pressing them needs --interactive."""
    if not on_pi():
        return record("controls", "GPIO", SKIP, "not running on a Pi")
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        return record("controls", "GPIO", FAIL, "RPi.GPIO not installed",
                      "sudo apt install -y python3-rpi.gpio")
    try:
        from hardware_input import (BTN_BLUE, BTN_RED, BTN_GREEN, BTN_HOME,
                                    BTN_CAMERA, ENC_CLK, ENC_DT, ENC_SW,
                                    TOGGLE_PIN, TOGGLE2_PIN)
    except Exception as exc:                                # noqa: BLE001
        return record("controls", "pin config", FAIL, str(exc))

    pins = {"blue": BTN_BLUE, "red": BTN_RED, "green": BTN_GREEN,
            "home": BTN_HOME, "camera": BTN_CAMERA, "enc clk": ENC_CLK,
            "enc dt": ENC_DT, "enc sw": ENC_SW, "toggle A": TOGGLE_PIN,
            "toggle B": TOGGLE2_PIN}
    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        stuck = []
        for name, bcm in pins.items():
            if bcm is None or bcm < 0:
                continue
            GPIO.setup(bcm, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            # Pulled up and not pressed should read HIGH. A pin stuck LOW
            # with nothing touching it means a short to ground or a switch
            # wired closed — worth knowing without pressing anything.
            if GPIO.input(bcm) == GPIO.LOW:
                stuck.append(f"{name}(BCM {bcm})")
        if stuck:
            record("controls", "idle levels", WARN,
                   f"reading LOW at rest: {', '.join(stuck)}",
                   "a held button, a switch wired closed, or a short to GND")
        else:
            record("controls", "idle levels", PASS,
                   f"all {len(pins)} inputs high at rest")
    except Exception as exc:                                # noqa: BLE001
        record("controls", "GPIO", FAIL, f"{type(exc).__name__}: {exc}")
    finally:
        try:
            GPIO.cleanup()
        except Exception:                                   # noqa: BLE001
            pass


def check_watcher():
    """The wireless camera node's listener, and whether it has been heard."""
    try:
        from backend import watcher
    except Exception as exc:                                # noqa: BLE001
        return record("watcher", "module", FAIL, str(exc)[:50])
    w = watcher.instance()
    if not w.enabled:
        return record("watcher", "listener", SKIP,
                      "KEA_WATCHER_TOKEN not set — disabled",
                      "see hardware/WATCHER.md to enable")
    record("watcher", "listener", PASS if w.start() else FAIL,
           f"port {watcher.PORT}" if w.start() else (w.error or "failed"),
           "another process may hold the port")
    online, rows = w.summary()
    if not rows:
        return record("watcher", "nodes", WARN, "none has ever reported",
                      "flash firmware/watcher/watcher.ino and check the token")
    for name, age, count, batt in rows:
        b = f", battery {batt} V" if batt else ""
        if age < 3600:
            record("watcher", name, PASS, f"seen {age / 60:.0f} min ago, "
                                          f"{count} frames{b}")
        else:
            record("watcher", name, WARN,
                   f"silent for {age / 3600:.1f} h{b}",
                   "flat cell, out of wifi range, or it never woke")


def check_system():
    if not on_pi():
        record("system", "host", SKIP, "not running on a Pi")
    else:
        rc, out = sh("vcgencmd measure_temp", timeout=8)
        if rc == 0 and "=" in out:
            try:
                t = float(out.split("=")[1].split("'")[0])
                st = PASS if t < 70 else (WARN if t < 80 else FAIL)
                record("system", "CPU temp", st, f"{t:.1f} C",
                       "check the fan and the case vents" if st != PASS else "")
            except ValueError:
                record("system", "CPU temp", WARN, out.strip()[:40])

        rc, out = sh("vcgencmd get_throttled", timeout=8)
        if rc == 0 and "=" in out:
            raw = out.strip().split("=")[1]
            val = int(raw, 16) if raw.startswith("0x") else 0
            if val == 0:
                record("system", "power", PASS, "no throttling, ever")
            else:
                bits = []
                if val & 0x1:
                    bits.append("under-voltage NOW")
                if val & 0x4:
                    bits.append("throttled NOW")
                if val & 0x10000:
                    bits.append("under-voltage since boot")
                if val & 0x40000:
                    bits.append("throttled since boot")
                now = val & 0xF
                record("system", "power", FAIL if now else WARN,
                       f"{raw}: {', '.join(bits) or 'flagged'}",
                       "a weak PSU or cable — Kea needs a solid 5 V 2.5 A")

    total, used, free = shutil.disk_usage(ROOT)
    pct = used / total * 100
    record("system", "disk", PASS if pct < 85 else (WARN if pct < 95 else FAIL),
           f"{free / 2**30:.1f} GB free ({pct:.0f}% used)",
           "python3 tools/offload.py to clear captured frames")

    try:
        import datetime
        yr = datetime.datetime.now().year
        record("system", "clock", PASS if yr >= 2024 else FAIL,
               datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
               "no RTC and no network — the drift circuit needs the hour")
    except Exception:                                       # noqa: BLE001
        pass


def check_config():
    from_dir = os.path.expanduser("~")
    for label, path, needed in (
            ("settings", os.path.join(from_dir, ".kea_settings.json"), False),
            ("servo calibration", os.path.join(from_dir, ".kea_servos.json"), False),
            ("tags", os.path.join(from_dir, ".kea_tags.json"), False),
            ("lifebook", os.path.join(from_dir, ".kea_lifebook.json"), False)):
        if os.path.exists(path):
            record("config", label, PASS, f"{os.path.getsize(path)} bytes")
        else:
            record("config", label, WARN if needed else SKIP,
                   "not created yet (normal before first run)")

    try:
        from backend import vvs
        routes = vvs.routes_from_env()
        record("config", "transit routes", PASS if routes else WARN,
               f"{len(routes)} configured: "
               f"{', '.join(r.label for r in routes)[:40]}",
               "KEA_VVS_ROUTES — see hardware docs" if not routes else "")
    except Exception as exc:                                # noqa: BLE001
        record("config", "transit routes", FAIL, str(exc)[:50])


# ── interactive ─────────────────────────────────────────────────────────────
def interactive_controls():
    if not on_pi():
        return record("controls", "press test", SKIP, "not running on a Pi")
    print("\n  Press every button, turn the encoder, flip both toggles.")
    print("  Ctrl-C when you are done.\n")
    rc, out = sh([sys.executable, os.path.join(ROOT, "tools",
                                               "test_controls.py")],
                 timeout=300)
    record("controls", "press test", PASS if rc in (0, 130) else FAIL,
           "operator confirmed" if rc in (0, 130) else out.strip()[-60:])


def interactive_servos():
    try:
        from backend import servo
    except Exception:                                       # noqa: BLE001
        return
    if not servo.available():
        return record("servo", "motion", SKIP, "no board attached")
    for sv in servo.all_servos():
        if not sv.calibrated:
            record("servo", f"{sv.name} motion", SKIP, "not calibrated yet")
            continue
        try:
            print(f"  moving {sv.name} to centre...")
            sv.centre(speed=2.0)
            time.sleep(0.5)
            sv.relax()
            record("servo", f"{sv.name} motion", PASS,
                   f"reached {sv.centre_deg:.0f} deg and relaxed")
        except Exception as exc:                            # noqa: BLE001
            record("servo", f"{sv.name} motion", FAIL, str(exc)[:50])


# ── report ──────────────────────────────────────────────────────────────────
def report():
    order, seen = [], set()
    for g, *_ in results:
        if g not in seen:
            seen.add(g)
            order.append(g)

    print("\n" + "=" * 68)
    print("  KEA — SYSTEM CHECK")
    print("=" * 68)
    for g in order:
        print(f"\n  {g.upper()}")
        for grp, name, st, detail, _fix in results:
            if grp == g:
                print(f"    [{GLYPH[st]}] {name:<22} {detail}")

    fails = [r for r in results if r[2] == FAIL]
    warns = [r for r in results if r[2] == WARN]
    skips = [r for r in results if r[2] == SKIP]
    passes = [r for r in results if r[2] == PASS]

    print("\n" + "-" * 68)
    print(f"  {len(passes)} ok   {len(warns)} warn   {len(fails)} failed   "
          f"{len(skips)} not applicable here")

    if fails or warns:
        print("\n  WHAT TO DO")
        for _g, name, st, detail, fix in results:
            if st in (FAIL, WARN) and fix:
                print(f"    {name}: {fix}")

    print()
    if fails:
        print("  NOT HEALTHY — see the failures above.\n")
        return 1
    if warns:
        print("  Working, with warnings worth clearing.\n")
        return 0
    print("  All good.\n")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print each delegated tool's full output")
    ap.add_argument("--slow", action="store_true",
                    help="also run the network/offload round-trip")
    ap.add_argument("--interactive", action="store_true",
                    help="also press buttons and move servos")
    ap.add_argument("--only", default="",
                    help="comma-separated groups: code,display,camera,"
                         "controls,servo,storage,startup,watcher,system,"
                         "config")
    args = ap.parse_args()

    want = {g.strip() for g in args.only.split(",") if g.strip()}

    def run(group):
        return not want or group in want

    t0 = time.time()
    print(f"  Kea system check — {'Raspberry Pi' if on_pi() else 'not a Pi'}"
          f", {time.strftime('%H:%M:%S')}")

    if run("code"):
        check_python()
        delegated("code", "all screens render", "smoke_test.py",
                  timeout=120, verbose=args.verbose)
    if run("display"):
        delegated("display", "panel", "check_display.py",
                  pi_only=True, verbose=args.verbose)
    if run("camera"):
        delegated("camera", "sensor", "check_camera.py",
                  pi_only=True, verbose=args.verbose)
    if run("controls"):
        check_controls()
    if run("servo"):
        check_servos()
    if run("startup"):
        delegated("startup", "services", "check_startup.py",
                  pi_only=True, verbose=args.verbose)
    if run("storage") and args.slow:
        delegated("storage", "encrypted offload", "check_offload.py",
                  timeout=180, verbose=args.verbose)
    elif run("storage"):
        record("storage", "encrypted offload", SKIP,
               "needs --slow (does a network round-trip)")
    if run("watcher"):
        check_watcher()
    if run("system"):
        check_system()
    if run("config"):
        check_config()

    if args.interactive:
        if run("servo"):
            interactive_servos()
        if run("controls"):
            interactive_controls()

    rc = report()
    print(f"  took {time.time() - t0:.1f}s\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
