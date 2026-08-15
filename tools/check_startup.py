#!/usr/bin/env python3
"""
check_startup.py — will everything actually come back after a reboot?

Checks each piece that has to survive a power cycle: the display target,
the autoscreen service (and whether it really launches Kea, not just an
empty screen session), the offload timer, the Bluetooth speaker service,
and — the one people miss — user-lingering, without which *no* --user
unit runs until you log in over SSH.

    python3 tools/check_startup.py
"""

import getpass
import os
import re
import subprocess
import sys

FIXES = []
USER = getpass.getuser()


def run(cmd, timeout=20):
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


print("=" * 64)
print("KEA STARTUP CHECK — what happens after a reboot")
print("=" * 64)

# ── 1. desktop ─────────────────────────────────────────────────────────────
print("\n1. Boot target (Kea draws onto X)")
rc, out = run(["systemctl", "get-default"])
print(f"  {out}")
if "graphical" in out:
    ok("boots to the desktop")
else:
    bad("boots to console — Kea has no X to draw on",
        "sudo systemctl set-default graphical.target")

# ── 2. autoscreen ──────────────────────────────────────────────────────────
print("\n2. autoscreen.service (system unit)")
rc, out = run(["systemctl", "is-enabled", "autoscreen.service"])
if rc == 0 and "enabled" in out:
    ok("enabled — will start at boot")
else:
    bad(f"NOT enabled (is-enabled says: {out})",
        "sudo systemctl enable autoscreen.service")
rc, out = run(["systemctl", "is-active", "autoscreen.service"])
print(f"  currently: {out}")

# does it actually run Kea, or just make an empty screen?
rc, unit = run(["systemctl", "cat", "autoscreen.service"])
if rc == 0:
    launches = re.search(r"main\.py", unit)
    if launches:
        ok("its ExecStart does launch main.py")
    else:
        bad("it creates a screen session but NEVER STARTS KEA in it — "
            "after a reboot you'd get an empty session",
            "Add an ExecStartPost that types the command into the session:\n"
            "    sudo systemctl edit --full autoscreen.service\n"
            "  then add, after the existing ExecStart line:\n"
            "    ExecStartPost=/bin/bash -c 'sleep 8; /usr/bin/screen -S main "
            "-X stuff \"cd /home/%s/Kea && python3 src/main.py\\n\"'\n"
            "  then: sudo systemctl daemon-reload" % USER)
    envs = re.findall(r"^Environment=(\S+)", unit, re.M)
    if envs:
        print(f"  env set: {[e.split('=')[0] for e in envs]}")

# ── 3. THE classic gotcha: user units need lingering ───────────────────────
print("\n3. User-service lingering")
rc, out = run(["loginctl", "show-user", USER, "-p", "Linger"])
if "Linger=yes" in out:
    ok(f"lingering ON for '{USER}' — --user units start at boot")
else:
    bad(f"lingering is OFF for '{USER}' — NO --user unit runs until you log "
        "in over SSH. Your offload timer and BT speaker would be dead after "
        "an unattended reboot.",
        f"sudo loginctl enable-linger {USER}")

# ── 4. user units ──────────────────────────────────────────────────────────
print("\n4. User units")
for unit, what in (("kea-offload.timer", "hourly image upload"),
                   ("kea-bt-speaker.service", "Bluetooth speaker")):
    rc, out = run(["systemctl", "--user", "is-enabled", unit])
    if rc == 0 and "enabled" in out:
        ok(f"{unit} enabled ({what})")
    elif "No such file" in out or rc == 127:
        note(f"{unit} not installed ({what}) — skip if you don't want it")
    else:
        bad(f"{unit} not enabled ({what})",
            f"systemctl --user enable --now {unit}")

# ── 5. is the upload going where you think? ────────────────────────────────
print("\n5. Where uploads actually go")
rc, unit = run(["systemctl", "--user", "cat", "kea-offload.service"])
remote = None
if rc == 0:
    m = re.search(r"KEA_RCLONE_REMOTE=(\S+)", unit)
    remote = m.group(1) if m else None
    print(f"  service sets KEA_RCLONE_REMOTE={remote or '(unset -> default b2)'}")
shell_remote = os.getenv("KEA_RCLONE_REMOTE")
print(f"  your shell has KEA_RCLONE_REMOTE={shell_remote or '(unset)'}")
eff = remote or shell_remote or "b2"
rc, cfg = run(["rclone", "config", "show", eff], 30)
enc = "type = crypt" in cfg
if enc:
    ok(f"'{eff}' is an encrypted (crypt) remote")
else:
    rc2, allr = run(["rclone", "listremotes"], 30)
    has_enc = any("enc" in r for r in allr.split())
    bad(f"'{eff}' is NOT encrypted — images upload in the clear"
        + (" even though you have an encrypted remote configured" if has_enc else ""),
        "point the timer at the encrypted remote:\n"
        "    systemctl --user edit --full kea-offload.service\n"
        "  set:  Environment=KEA_RCLONE_REMOTE=b2_enc\n"
        "        Environment=KEA_RCLONE_PATH=\n"
        "  then: systemctl --user daemon-reload\n"
        "  (already-uploaded plaintext files stay plaintext — delete them\n"
        "   from the bucket and re-upload if that matters)")

# ── 6. the honest test ─────────────────────────────────────────────────────
print("\n" + "=" * 64)
if FIXES:
    print("FIX THESE:\n")
    for i, f in enumerate(FIXES, 1):
        print(f"  {i}. {f}\n")
else:
    print("Everything is set to start on boot.")
print("Then prove it the only way that counts:\n")
print("    sudo reboot")
print("\nand after it comes back, WITHOUT logging in first, check from SSH:")
print("    systemctl is-active autoscreen.service")
print("    systemctl --user list-timers kea-offload.timer")
print("    screen -ls                 # a 'main' session should exist")
print("    pgrep -af 'python.*main.py'   # Kea itself should be running")
sys.exit(1 if FIXES else 0)
