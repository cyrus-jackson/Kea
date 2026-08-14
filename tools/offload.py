#!/usr/bin/env python3
"""
offload.py — move collected images to cloud storage, safely.

Uses `rclone move`, which deletes the local file ONLY after the upload has
been verified. Nothing is ever removed on the strength of "probably went
fine". If the network is down it exits quietly and tries again next time;
images just accumulate locally, which at ~180 KB each is harmless.

    python3 tools/offload.py                 # upload what's pending
    python3 tools/offload.py --dry-run       # show what would move
    python3 tools/offload.py --status        # what's waiting, no upload

Backend-agnostic: it only ever runs `rclone move <local> <remote>:<path>`,
so B2, S3, Drive, SFTP or your Mac all work by changing two env vars —
no code change. Setup is in INIT_RUN/README.md § 3.

    rclone config        # create a remote named "b2"
    rclone lsd b2:kea-data

Environment:
    KEA_RCLONE_REMOTE   remote name        (default: b2)
    KEA_RCLONE_PATH     path on it         (default: kea-data/images)
    KEA_DATA_DIR        local root         (default: ~/kea_data)
    KEA_RCLONE_BWLIMIT  e.g. 2M            (default: unset = full speed)
"""

import argparse
import os
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
ROOT = os.getenv("KEA_DATA_DIR", os.path.join(HOME, "kea_data"))
PENDING = os.path.join(ROOT, "pending")
REMOTE = os.getenv("KEA_RCLONE_REMOTE", "b2")
REMOTE_PATH = os.getenv("KEA_RCLONE_PATH", "kea-data/images")
BWLIMIT = os.getenv("KEA_RCLONE_BWLIMIT", "").strip()
MIN_AGE = os.getenv("KEA_RCLONE_MIN_AGE", "2m")   # never grab a file mid-write


def stats():
    n = size = 0
    if os.path.isdir(PENDING):
        for fn in os.listdir(PENDING):
            p = os.path.join(PENDING, fn)
            if fn.endswith(".jpg") and os.path.isfile(p):
                n += 1
                try:
                    size += os.path.getsize(p)
                except OSError:
                    pass
    return n, size


def have_rclone():
    return shutil.which("rclone") is not None


def remote_ok():
    """Is the remote configured AND reachable right now?"""
    try:
        r = subprocess.run(["rclone", "lsd", f"{REMOTE}:", "--max-depth", "1"],
                           capture_output=True, text=True, timeout=45)
        return r.returncode == 0, (r.stderr or "").strip().split("\n")[-1][:160]
    except FileNotFoundError:
        return False, "rclone not installed"
    except subprocess.TimeoutExpired:
        return False, "timed out reaching the remote (offline?)"
    except Exception as e:
        return False, str(e)[:160]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    n, size = stats()
    if a.status or not a.quiet:
        print(f"pending: {n} images, {size / 1048576:.1f} MB in {PENDING}")
        print(f"target : {REMOTE}:{REMOTE_PATH}")
    if a.status:
        return 0

    if n == 0:
        if not a.quiet:
            print("nothing to upload.")
        return 0

    if not have_rclone():
        print("rclone is not installed:  sudo apt install rclone", file=sys.stderr)
        return 2

    ok, why = remote_ok()
    if not ok:
        # Offline is normal and not an error — try again next timer tick.
        print(f"remote '{REMOTE}' unavailable ({why}); leaving files in place.",
              file=sys.stderr)
        return 0

    cmd = ["rclone", "move", PENDING, f"{REMOTE}:{REMOTE_PATH}",
           "--min-age", MIN_AGE,
           "--transfers", "2",
           "--checkers", "2",
           "--retries", "3",
           "--no-traverse",
           "--stats-one-line", "--stats", "10s"]
    if BWLIMIT:
        cmd += ["--bwlimit", BWLIMIT]
    if a.dry_run:
        cmd.append("--dry-run")
    if not a.quiet:
        cmd.append("--progress")

    if not a.quiet:
        print(" ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"rclone exited {r.returncode}; local files kept.", file=sys.stderr)
        return r.returncode

    left, left_sz = stats()
    if not a.quiet:
        moved = n - left
        print(f"uploaded {moved} image(s); {left} still pending "
              f"({left_sz / 1048576:.1f} MB).")
        if left:
            print(f"(files younger than {MIN_AGE} are held back on purpose)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
