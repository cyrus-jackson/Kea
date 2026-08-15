#!/usr/bin/env python3
"""
check_camera.py — why won't the camera start?

"Camera __init__ sequence did not complete" is picamera2 failing partway
through, and it has several possible causes. This checks each one on the
running Pi and tells you which applies.

    python3 tools/check_camera.py
"""

import glob
import os
import re
import shutil
import subprocess
import sys

FIXES = []


def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except FileNotFoundError:
        return 127, "not found"
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    except Exception as e:
        return 1, str(e)


def ok(msg):
    print(f"  [OK]   {msg}")


def bad(msg, fix=None):
    print(f"  [BAD]  {msg}")
    if fix:
        FIXES.append(fix)


def warn(msg):
    print(f"  [note] {msg}")


print("=" * 62)
print("KEA CAMERA DIAGNOSTIC")
print("=" * 62)

# ── 1. OS / stack ───────────────────────────────────────────────────────────
print("\n1. System")
codename = ""
try:
    with open("/etc/os-release") as f:
        txt = f.read()
    codename = (re.search(r"VERSION_CODENAME=(\w+)", txt) or [None, "?"])[1]
    print(f"  OS: {codename}")
except OSError:
    warn("not a Pi? (/etc/os-release missing)")

# ── 2. THE usual culprit: legacy camera stack ───────────────────────────────
print("\n2. Legacy camera stack (the most common cause)")
cfg_path = None
for p in ("/boot/firmware/config.txt", "/boot/config.txt"):
    if os.path.exists(p):
        cfg_path = p
        break
cfg = ""
if cfg_path:
    try:
        cfg = open(cfg_path, encoding="utf-8", errors="ignore").read()
    except OSError:
        pass
    print(f"  config: {cfg_path}")
    live = [l.strip() for l in cfg.splitlines()
            if l.strip() and not l.strip().startswith("#")]
    if any(re.match(r"start_x\s*=\s*1", l) for l in live):
        bad("start_x=1 — the LEGACY camera stack is ON; picamera2 cannot work",
            "sudo raspi-config  ->  Interface Options  ->  Legacy Camera  ->  No"
            "\n    (then reboot)")
    else:
        ok("start_x=1 not set")
    if any(re.match(r"camera_auto_detect\s*=\s*1", l) for l in live):
        ok("camera_auto_detect=1")
    else:
        bad("camera_auto_detect=1 is missing",
            f"add 'camera_auto_detect=1' to {cfg_path}, then reboot")
    ov = [l for l in live if "dtoverlay" in l and
          any(k in l for k in ("imx", "ov5647", "ov64"))]
    if ov:
        warn(f"explicit camera overlay present: {ov}")
else:
    warn("no config.txt found")

rc, out = run(["vcgencmd", "get_camera"])
if rc == 0:
    print(f"  vcgencmd get_camera: {out.strip()}")
    if "detected=0" in out and "libcamera_detected=0" in out:
        bad("firmware sees NO camera — check the ribbon", "reseat the CSI ribbon")

# ── 3. Does libcamera itself see it? ────────────────────────────────────────
print("\n3. libcamera")
tool = None
for t in ("rpicam-hello", "libcamera-hello"):
    if shutil.which(t):
        tool = t
        break
if tool is None:
    bad("no rpicam-hello / libcamera-hello installed",
        "sudo apt install -y libcamera-apps   # or rpicam-apps on Bookworm")
else:
    rc, out = run([tool, "--list-cameras"], timeout=30)
    if "Available cameras" in out and not re.search(r"no cameras", out, re.I):
        ok(f"{tool} --list-cameras found a camera")
        for line in out.splitlines():
            if re.match(r"^\d+\s*:", line.strip()):
                print(f"         {line.strip()}")
    else:
        bad(f"{tool} reports no cameras",
            "if the ribbon is seated and legacy is off, reboot once more;\n"
            "    blue side of the ribbon faces the ETHERNET/USB ports on a Pi 3")
        print("        ", out.strip().splitlines()[-1][:100] if out.strip() else "")

# ── 4. picamera2 ────────────────────────────────────────────────────────────
print("\n4. picamera2")
try:
    import picamera2
    ok(f"picamera2 importable (version {getattr(picamera2, '__version__', '?')})")
    try:
        from picamera2 import Picamera2
        cams = Picamera2.global_camera_info()
        if cams:
            ok(f"Picamera2 sees {len(cams)} camera(s): "
               f"{[c.get('Model', '?') for c in cams]}")
        else:
            bad("Picamera2.global_camera_info() is EMPTY — nothing to open",
                "this is the direct cause of 'init sequence did not complete'")
    except Exception as e:
        bad(f"global_camera_info() failed: {str(e)[:90]}")
except ImportError:
    bad("picamera2 not installed",
        "sudo apt install -y python3-picamera2\n"
        "    (apt, NOT pip — pip builds miss the libcamera bindings)")
except Exception as e:
    bad(f"importing picamera2 raised: {str(e)[:90]}")

# ── 5. Is something else holding it? ────────────────────────────────────────
print("\n5. Is the camera already in use?")
busy = False
vids = sorted(glob.glob("/dev/video*"))
if not vids:
    warn("no /dev/video* nodes")
for dev in vids[:8]:
    rc, out = run(["fuser", dev])
    if rc == 0 and out.strip():
        busy = True
        bad(f"{dev} is held by PID(s): {out.strip()}",
            "another Kea (or a crashed one) still owns the camera:\n"
            "    pkill -f 'python.*main.py'   then start Kea again")
if not busy:
    ok("nothing else is holding a video device")

# ── 6. Can WE open it? the real test ────────────────────────────────────────
print("\n6. Opening the camera the same way Kea does")
try:
    from picamera2 import Picamera2
    cam = Picamera2()
    cfgn = cam.create_still_configuration(main={"size": (1280, 720)})
    cam.configure(cfgn)
    cam.start()
    import time
    time.sleep(0.5)
    cam.capture_file("/tmp/kea_camtest.jpg")
    cam.stop()
    cam.close()
    sz = os.path.getsize("/tmp/kea_camtest.jpg")
    ok(f"captured /tmp/kea_camtest.jpg ({sz / 1024:.0f} KB) — the camera WORKS")
    print("\n  If Kea still says NO CAMERA, it's holding a stale handle:")
    print("     restart Kea, or reboot.")
except Exception as e:
    bad(f"open/capture failed: {type(e).__name__}: {str(e)[:110]}")

# ── verdict ────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
if FIXES:
    print("DO THIS, IN ORDER:\n")
    for i, f in enumerate(FIXES, 1):
        print(f"  {i}. {f}\n")
    print("Then reboot and re-run this script.")
    sys.exit(1)
print("Everything checks out. If Kea still can't open the camera, restart it")
print("so it isn't reusing a handle from a failed attempt.")
sys.exit(0)
