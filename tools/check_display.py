#!/usr/bin/env python3
"""
check_display.py — the TFT shows only a console cursor. Why?

Run ON THE PI after the desktop stops appearing:

    python3 tools/check_display.py

Kea draws through SDL onto X (DISPLAY=:0), so if the desktop isn't
running there is nothing for it to draw on. This works out whether the
boot target changed, whether X is up, and whether the SPI panel is still
being fed.
"""

import glob
import os
import re
import shutil
import subprocess
import sys

FIXES = []


def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except FileNotFoundError:
        return 127, "not found"
    except Exception as e:
        return 1, str(e)


def ok(m):
    print(f"  [OK]   {m}")


def bad(m, fix=None):
    print(f"  [BAD]  {m}")
    if fix:
        FIXES.append(fix)


def note(m):
    print(f"  [note] {m}")


print("=" * 62)
print("KEA DISPLAY DIAGNOSTIC")
print("=" * 62)

# ── 1. boot target: the usual casualty of a raspi-config visit ─────────────
print("\n1. Boot target")
rc, out = run(["systemctl", "get-default"])
print(f"  default target: {out}")
if "graphical" in out:
    ok("set to boot into the desktop")
else:
    bad("booting to CONSOLE, not the desktop — this alone explains a bare '_'",
        "sudo systemctl set-default graphical.target\n"
        "    ...or: sudo raspi-config -> System Options -> Boot / Auto Login\n"
        "           -> Desktop Autologin (B4),  then reboot")

# ── 2. is a display server actually running? ───────────────────────────────
print("\n2. Display server")
found = None
for proc in ("Xorg", "X", "labwc", "wayfire", "lightdm"):
    rc, out = run(["pgrep", "-x", proc])
    if rc == 0:
        found = proc
        break
if found:
    ok(f"{found} is running")
else:
    bad("no X / Wayland / display manager process found",
        "sudo systemctl start lightdm      # or fix the boot target above")

# ── 3. framebuffers — the SPI panel is usually fb1 ─────────────────────────
print("\n3. Framebuffers")
fbs = sorted(glob.glob("/dev/fb*"))
print(f"  present: {fbs or 'NONE'}")
for fb in fbs:
    n = os.path.basename(fb).replace("fb", "")
    try:
        name = open(f"/sys/class/graphics/fb{n}/name").read().strip()
        size = open(f"/sys/class/graphics/fb{n}/virtual_size").read().strip()
        print(f"    {fb}: {name}  ({size})")
    except OSError:
        pass
if not fbs:
    bad("no framebuffer at all", "check the display overlay in config.txt")
elif len(fbs) == 1:
    note("only one framebuffer — if your TFT is an SPI panel it usually adds")
    note("fb1; a single fb0 can mean the panel overlay didn't load")

# ── 4. is anything copying the desktop onto the SPI panel? ─────────────────
print("\n4. fbcp (copies fb0 -> fb1 for SPI panels)")
rc, _ = run(["pgrep", "-x", "fbcp"])
if rc == 0:
    ok("fbcp is running")
else:
    if shutil.which("fbcp"):
        note("fbcp installed but not running")
        note("only needed if your panel is driven by fbtft, not DPI/KMS")
    else:
        note("fbcp not installed (fine if the panel is a KMS/DPI overlay)")

# ── 5. what raspi-config did to config.txt ─────────────────────────────────
print("\n5. config.txt")
cfg_path = next((p for p in ("/boot/firmware/config.txt", "/boot/config.txt")
                 if os.path.exists(p)), None)
if cfg_path:
    print(f"  file: {cfg_path}")
    try:
        lines = [l.strip() for l in open(cfg_path, errors="ignore")
                 if l.strip() and not l.strip().startswith("#")]
    except OSError:
        lines = []
    interesting = [l for l in lines if re.search(
        r"dtoverlay|start_x|gpu_mem|camera_auto_detect|dtparam=spi|hdmi|vc4", l)]
    for l in interesting:
        print(f"    {l}")
    if any("start_x=1" in l for l in lines):
        bad("start_x=1 is back — legacy camera on again",
            "sudo raspi-config -> Interface Options -> Legacy Camera -> No")
    kms = [l for l in lines if "vc4-kms-v3d" in l]
    fkms = [l for l in lines if "vc4-fkms-v3d" in l]
    tft = [l for l in lines if re.search(r"tft|ili9|piscreen|waveshare|mpi\d", l, re.I)]
    if kms and tft:
        bad("full KMS (vc4-kms-v3d) alongside an fbtft SPI panel — these fight,"
            " and fbcp won't work under KMS",
            f"in {cfg_path}, use vc4-fkms-v3d instead of vc4-kms-v3d, or drop\n"
            "    the vc4 line entirely while you use the SPI panel; then reboot")
    elif tft:
        ok(f"SPI panel overlay present: {tft[0]}")
    # did raspi-config leave a backup we can diff?
    for b in (cfg_path + ".bak", "/boot/config.txt.bak"):
        if os.path.exists(b):
            note(f"backup exists: {b}   (diff it: diff {b} {cfg_path})")
            break
else:
    bad("config.txt not found")

# ── 6. can SDL open a screen at all? ───────────────────────────────────────
print("\n6. Can Kea's toolkit open a display?")
for drv, desc in (("x11", "the desktop"), ("kmsdrm", "direct KMS/DRM"),
                  ("fbcon", "the raw framebuffer")):
    env = dict(os.environ, SDL_VIDEODRIVER=drv)
    code = ("import pygame,sys;pygame.init();"
            "pygame.display.set_mode((64,64));sys.exit(0)")
    rc, out = 1, ""
    try:
        r = subprocess.run([sys.executable, "-c", code], env=env,
                           capture_output=True, text=True, timeout=20)
        rc, out = r.returncode, (r.stderr or "").strip().splitlines()[-1:] or [""]
        out = out[0]
    except Exception as e:
        out = str(e)
    print(f"  {drv:<8} ({desc}): {'WORKS' if rc == 0 else 'no — ' + out[:56]}")
    if rc == 0 and drv != "x11":
        FIXES.append(
            f"Kea can run WITHOUT the desktop using this driver:\n"
            f"    SDL_VIDEODRIVER={drv} python3 src/main.py\n"
            "    (add it to autoscreen.service if you'd rather not run X at all)")
        break

print("\n" + "=" * 62)
if FIXES:
    print("TRY THESE, IN ORDER:\n")
    for i, f in enumerate(FIXES, 1):
        print(f"  {i}. {f}\n")
    sys.exit(1)
print("Nothing obviously wrong — if the panel is still blank, reboot once and")
print("re-run. Note the console cursor means the panel itself is alive.")
sys.exit(0)
