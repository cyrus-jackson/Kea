"""
dataset.py — where captured images and their labels live.

Every approved shot lands in ~/kea_data/pending/ as a JPEG plus a small
JSON sidecar holding its tag and the conditions it was taken in. The
offloader (tools/offload.py) later moves both files to OneDrive and
deletes the local copies, so "pending" means "not yet uploaded".

    from backend import dataset
    dataset.save(tmp_jpeg, "me", extra={"exposure": 1234})

TAGS ARE YOURS TO CHANGE. They live in ~/.kea_tags.json, which is created
on first run with a sensible starting set:

    ["me", "empty", "other"]

Edit that file — add "cyrus_glasses", "night", "two_people", whatever the
task turns out to need — and Kea picks it up the next time you open the
camera screen. No restart, no code change. Old images keep the tag they
were shot with, so adding tags never invalidates what you've collected.
"""

import json
import os
import shutil
import time

HOME = os.path.expanduser("~")
ROOT = os.getenv("KEA_DATA_DIR", os.path.join(HOME, "kea_data"))
PENDING = os.path.join(ROOT, "pending")
TAGS_PATH = os.getenv("KEA_TAGS_FILE", os.path.join(HOME, ".kea_tags.json"))

DEFAULT_TAGS = ["me", "empty", "other"]

_session = time.strftime("%Y%m%d-%H%M%S")
_tags_cache = None
_tags_mtime = 0.0


# ── tags ────────────────────────────────────────────────────────────────────
def tags():
    """The current tag list, re-read whenever the file changes on disk."""
    global _tags_cache, _tags_mtime
    try:
        mt = os.path.getmtime(TAGS_PATH)
    except OSError:
        if _tags_cache is None:
            _write_tags(DEFAULT_TAGS)
            _tags_cache = list(DEFAULT_TAGS)
        return _tags_cache
    if _tags_cache is None or mt != _tags_mtime:
        try:
            with open(TAGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            got = [str(t).strip() for t in data if str(t).strip()]
            _tags_cache = got or list(DEFAULT_TAGS)
            _tags_mtime = mt
        except Exception:
            if _tags_cache is None:
                _tags_cache = list(DEFAULT_TAGS)
    return _tags_cache


def _write_tags(lst):
    try:
        os.makedirs(os.path.dirname(TAGS_PATH) or ".", exist_ok=True)
        with open(TAGS_PATH, "w", encoding="utf-8") as f:
            json.dump(list(lst), f, indent=2)
    except Exception:
        pass


def add_tag(name):
    """Add a tag at runtime (also persists it to the file)."""
    name = str(name).strip()
    if not name:
        return tags()
    cur = list(tags())
    if name not in cur:
        cur.append(name)
        _write_tags(cur)
        global _tags_cache, _tags_mtime
        _tags_cache = cur
        try:
            _tags_mtime = os.path.getmtime(TAGS_PATH)
        except OSError:
            pass
    return _tags_cache


# ── saving ──────────────────────────────────────────────────────────────────
def _ensure():
    os.makedirs(PENDING, exist_ok=True)


def save(tmp_path, tag, extra=None):
    """Move a freshly captured JPEG into the dataset under `tag`.

    Returns the stored path, or None if it couldn't be written. Writes the
    sidecar FIRST so a half-finished pair is never left with an image but
    no label.
    """
    if not tmp_path or not os.path.exists(tmp_path):
        return None
    _ensure()
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(tag))[:32]
    base = f"{stamp}_{safe}"
    img = os.path.join(PENDING, base + ".jpg")
    meta = os.path.join(PENDING, base + ".json")

    record = {
        "file": base + ".jpg",
        "tag": tag,
        "session": _session,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "epoch": time.time(),
    }
    if extra:
        record.update(extra)
    try:
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(record, f)
        shutil.move(tmp_path, img)
        return img
    except Exception:
        for p in (meta, img):
            try:
                os.remove(p)
            except OSError:
                pass
        return None


def save_bytes(jpeg, tag, extra=None):
    """Store a JPEG that arrived as bytes rather than as a file.

    The built-in camera hands us a temp file; a remote node hands us the
    body of an HTTP POST. Same destination, same sidecar, same offload —
    so a frame from the wireless watcher is indistinguishable downstream
    from one Kea took itself, which is the point.

    Written to a temp file first and then moved through save(), so the
    "sidecar before image" ordering is not duplicated in two places.
    """
    if not jpeg:
        return None
    _ensure()
    tmp = os.path.join(PENDING, f".incoming-{int(time.time() * 1000)}.part")
    try:
        with open(tmp, "wb") as f:
            f.write(jpeg)
    except Exception:                                    # noqa: BLE001
        try:
            os.remove(tmp)
        except OSError:
            pass
        return None
    return save(tmp, tag, extra=extra)


# ── stats (so the screen can show balance and backlog) ──────────────────────
def counts():
    """{tag: n} for everything still pending locally."""
    out = {}
    try:
        for fn in os.listdir(PENDING):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(PENDING, fn), encoding="utf-8") as f:
                    out_tag = json.load(f).get("tag", "?")
            except Exception:
                out_tag = "?"
            out[out_tag] = out.get(out_tag, 0) + 1
    except OSError:
        pass
    return out


def pending_stats():
    """(number of images, total bytes) waiting to be uploaded."""
    n = 0
    size = 0
    try:
        for fn in os.listdir(PENDING):
            if fn.endswith(".jpg"):
                n += 1
                try:
                    size += os.path.getsize(os.path.join(PENDING, fn))
                except OSError:
                    pass
    except OSError:
        pass
    return n, size


def session():
    return _session
