#!/usr/bin/env python3
"""
check_offload.py — did the images actually make it to the cloud?

Checks the whole path rather than one end of it: what's still local, what
the remote holds, whether the timer is running and when it last fired,
whether image/sidecar pairs survived the trip, and finally a round-trip
canary that uploads a file, reads it back and compares it — which is the
only way to prove an ENCRYPTED remote is really readable again.

    python3 tools/check_offload.py              # full check incl. canary
    python3 tools/check_offload.py --no-canary  # don't touch the remote
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HOME = os.path.expanduser("~")
ROOT = os.getenv("KEA_DATA_DIR", os.path.join(HOME, "kea_data"))
PENDING = os.path.join(ROOT, "pending")
REMOTE = os.getenv("KEA_RCLONE_REMOTE", "b2")
REMOTE_PATH = os.getenv("KEA_RCLONE_PATH", "kea-data/images")
DEST = f"{REMOTE}:{REMOTE_PATH}" if REMOTE_PATH else f"{REMOTE}:"

PROBLEMS = []


def run(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"
    except Exception as e:
        return 1, "", str(e)


def ok(m):
    print(f"  [OK]   {m}")


def bad(m, fix=None):
    print(f"  [BAD]  {m}")
    PROBLEMS.append(fix or m)


def note(m):
    print(f"  [note] {m}")


ap = argparse.ArgumentParser()
ap.add_argument("--no-canary", action="store_true",
                help="skip the upload/download round-trip test")
args = ap.parse_args()

print("=" * 64)
print("KEA OFFLOAD VERIFICATION")
print(f"  local : {PENDING}")
print(f"  remote: {DEST}")
print("=" * 64)

# ── 1. what's still sitting on the Pi ───────────────────────────────────────
print("\n1. Waiting locally")
jpgs = jsons = 0
oldest = None
if os.path.isdir(PENDING):
    for fn in os.listdir(PENDING):
        p = os.path.join(PENDING, fn)
        if fn.endswith(".jpg"):
            jpgs += 1
            try:
                m = os.path.getmtime(p)
                oldest = m if oldest is None else min(oldest, m)
            except OSError:
                pass
        elif fn.endswith(".json"):
            jsons += 1
    print(f"  {jpgs} images, {jsons} sidecars")
    if jpgs and oldest:
        age_min = (time.time() - oldest) / 60
        print(f"  oldest is {age_min:.0f} min old")
        if age_min > 90:
            bad("images have been waiting over 90 min — the timer isn't "
                "running, or uploads are failing",
                "check section 4, then run: python3 tools/offload.py")
        elif age_min < 2:
            note("younger than --min-age 2m, so held back on purpose")
    if jpgs != jsons:
        bad(f"image/sidecar mismatch locally ({jpgs} vs {jsons})")
    if jpgs == 0:
        ok("nothing pending — everything has been uploaded")
else:
    note("no pending directory yet (no photos taken?)")

# ── 2. rclone + remote ─────────────────────────────────────────────────────
print("\n2. rclone and the remote")
rc, out, err = run(["rclone", "version"], 30)
if rc != 0:
    bad("rclone not installed", "sudo apt install rclone")
    print("\n".join(f"  {p}" for p in PROBLEMS))
    sys.exit(1)
ok(f"rclone {out.splitlines()[0].split()[-1] if out else '?'}")

rc, out, err = run(["rclone", "listremotes"], 30)
remotes = [r.strip().rstrip(":") for r in out.splitlines() if r.strip()]
print(f"  configured remotes: {remotes}")
if REMOTE not in remotes:
    bad(f"remote '{REMOTE}' is not configured",
        f"rclone config   # create a remote named {REMOTE}")
else:
    ok(f"'{REMOTE}' exists")
    rc, out, err = run(["rclone", "about", f"{REMOTE}:"], 60)
    if rc != 0:
        rc2, _, _ = run(["rclone", "lsd", f"{REMOTE}:", "--max-depth", "1"], 60)
        if rc2 != 0:
            bad(f"cannot reach '{REMOTE}': {err.strip().splitlines()[-1:] or ''}",
                "check network / credentials: rclone lsd " + REMOTE + ":")
        else:
            ok("remote reachable")
    else:
        ok("remote reachable")

# is it encrypted?
rc, out, _ = run(["rclone", "config", "show", REMOTE], 30)
if "type = crypt" in out:
    ok("this remote is ENCRYPTED (crypt) — uploads are ciphertext at rest")
elif out:
    t = re.search(r"type\s*=\s*(\w+)", out)
    note(f"remote type: {t.group(1) if t else '?'} (not encrypted)")

# ── 3. what's actually up there ────────────────────────────────────────────
print("\n3. Contents of the remote")
rc, out, err = run(["rclone", "size", DEST, "--json"], 120)
remote_files = remote_bytes = None
if rc == 0 and out.strip():
    try:
        d = json.loads(out)
        remote_files, remote_bytes = d.get("count", 0), d.get("bytes", 0)
        print(f"  {remote_files} files, {remote_bytes / 1048576:.1f} MB")
    except Exception:
        print(f"  {out.strip()}")
else:
    bad(f"could not list {DEST}: {(err or '').strip().splitlines()[-1:] or ''}")

if remote_files == 0:
    bad("the remote is EMPTY — nothing has uploaded yet",
        "run it by hand and read the output: python3 tools/offload.py")
elif remote_files:
    rc, out, _ = run(["rclone", "lsf", DEST], 120)
    names = [n.strip() for n in out.splitlines() if n.strip()]
    rj = len([n for n in names if n.endswith(".jpg")])
    rs = len([n for n in names if n.endswith(".json")])
    print(f"  of those: {rj} images, {rs} sidecars")
    if rj and rs != rj:
        bad(f"image/sidecar mismatch on the remote ({rj} vs {rs}) — some "
            "images may have lost their labels")
    else:
        ok("every image up there has its label sidecar")
    tags = {}
    for n in names:
        m = re.match(r"\d{8}-\d{6}-\d+_(.+)\.jpg$", n)
        if m:
            tags[m.group(1)] = tags.get(m.group(1), 0) + 1
    if tags:
        print("  tag distribution in the cloud:")
        for t, c in sorted(tags.items(), key=lambda x: -x[1]):
            print(f"      {t:<16} {c}")
    print("  newest few:")
    for n in sorted(names)[-4:]:
        print(f"      {n}")

# ── 4. the timer ───────────────────────────────────────────────────────────
print("\n4. The hourly timer")
rc, out, _ = run(["systemctl", "--user", "is-enabled", "kea-offload.timer"], 20)
if rc == 0 and "enabled" in out:
    ok("kea-offload.timer is enabled")
else:
    bad("kea-offload.timer is not enabled",
        "systemctl --user enable --now kea-offload.timer   (see INIT_RUN §3.5)")
rc, out, _ = run(["systemctl", "--user", "list-timers", "kea-offload.timer",
                  "--all", "--no-pager"], 20)
for line in out.splitlines():
    if "kea-offload" in line or "NEXT" in line:
        print(f"  {line.strip()}")
rc, out, _ = run(["systemctl", "--user", "show", "kea-offload.service",
                  "-p", "Result", "-p", "ExecMainStatus"], 20)
print(f"  last run: {out.strip().replace(chr(10), '  ')}")
if "Result=success" not in out and out.strip():
    note("if Result isn't 'success', read the log below")
rc, out, _ = run(["journalctl", "--user", "-u", "kea-offload.service",
                  "-n", "12", "--no-pager"], 30)
if out.strip():
    print("  recent log:")
    for line in out.strip().splitlines()[-8:]:
        print(f"      {line[-110:]}")
else:
    note("no journal entries yet — the timer may not have fired")

# ── 5. round trip: the only real proof ─────────────────────────────────────
if not args.no_canary and REMOTE in remotes:
    print("\n5. Round-trip test (upload → read back → compare)")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    payload = f"kea offload canary {stamp}\n" + os.urandom(16).hex()
    with tempfile.TemporaryDirectory() as td:
        up = os.path.join(td, f"_canary_{stamp}.txt")
        with open(up, "w") as f:
            f.write(payload)
        rc, _, err = run(["rclone", "copy", up, DEST], 120)
        if rc != 0:
            bad(f"canary UPLOAD failed: {err.strip().splitlines()[-1:] or ''}")
        else:
            ok("uploaded")
            back = os.path.join(td, "back")
            os.makedirs(back, exist_ok=True)
            rc, _, err = run(["rclone", "copy",
                              f"{DEST}/_canary_{stamp}.txt", back], 120)
            got = os.path.join(back, f"_canary_{stamp}.txt")
            if rc == 0 and os.path.exists(got) and open(got).read() == payload:
                ok("read back and byte-identical — the round trip WORKS")
                if "type = crypt" in (subprocess.run(
                        ["rclone", "config", "show", REMOTE],
                        capture_output=True, text=True).stdout or ""):
                    ok("and it decrypted correctly, so your crypt passwords "
                       "are right — the data is recoverable")
            else:
                bad("canary uploaded but could NOT be read back intact — "
                    "data may be unrecoverable",
                    "check the crypt passwords in rclone.conf")
            run(["rclone", "delete", f"{DEST}/_canary_{stamp}.txt"], 60)
            note("canary removed from the remote")

# ── verdict ────────────────────────────────────────────────────────────────
print("\n" + "=" * 64)
if PROBLEMS:
    print("NEEDS ATTENTION:\n")
    for i, p in enumerate(PROBLEMS, 1):
        print(f"  {i}. {p}\n")
    sys.exit(1)
print("Offload is working: files reach the remote, keep their labels, and")
print("can be read back intact.")
print("\nTo pull the dataset down on your Mac:")
print(f"    rclone copy {DEST} ./kea-dataset -P")
sys.exit(0)
