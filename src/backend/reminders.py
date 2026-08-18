"""
reminders.py — your phone's reminders, delivered to the desk.

Transport is ntfy.sh: a free pub/sub topic, no account needed.
On the phone side, anything that can POST to a URL can file a
reminder — the ntfy app share sheet, an iOS Shortcuts automation
("When a Reminder is due -> post to URL"), Tasker, or plain curl:

    curl -d "water the chassis" https://ntfy.sh/<your-topic>

Kea subscribes by polling the topic's JSON endpoint every 30 s
(no push connection to babysit, kind to the Pi). Reminders persist
to disk, age through urgency stages, and stay until stamped DONE.

Set your topic with  KEA_NTFY_TOPIC=<something-unguessable> ;
the default includes the user name but you should pick your own.
Disable with KEA_FEEDS=0.
"""

import datetime
import json
import re
import os
import threading
import time
import urllib.request

TOPIC = os.getenv("KEA_NTFY_TOPIC", "kea-dispatch-" +
                  os.getenv("KEA_USER", "cyrus").lower())
ENABLED = os.getenv("KEA_FEEDS", "1").strip().lower() not in {"0", "false", "off"}
PATH = os.path.join(os.path.expanduser("~"), ".kea_reminders.json")
POLL_EVERY = 30.0

# Urgency by AGE, for reminders with no deadline. A thing you were told
# about four hours ago and have not done is probably slipping.
STAGES = [
    (0,          "POSTED"),
    (3600,       "BOARDING"),
    (4 * 3600,   "FINAL CALL"),
    (24 * 3600,  "OVERDUE"),
]

# Urgency by DEADLINE, for reminders that have one. Seconds REMAINING —
# so the list runs from most to least time, and past the deadline goes
# negative. Age and deadline are different questions: a reminder posted
# a week ago that is due next month is not urgent, and one posted a
# minute ago that is due in five is.
DUE_STAGES = [
    (24 * 3600,  "SCHEDULED"),
    (2 * 3600,   "TODAY"),
    (15 * 60,    "DUE SOON"),
    (0,          "DUE NOW"),
    (-1,         "OVERDUE"),
]


def stage_for(age_s, due_ts=None, now=None):
    """The urgency label. Deadline wins over age when there is one."""
    if due_ts:
        left = float(due_ts) - (now if now is not None else time.time())
        label = DUE_STAGES[-1][1]
        for threshold, name in DUE_STAGES:
            if left >= threshold:
                return name
        return label
    label = STAGES[0][1]
    for threshold, name in STAGES:
        if age_s >= threshold:
            label = name
    return label


# ── deadlines written into the message ──────────────────────────────────────
# You set a reminder from your phone, so the deadline has to be settable
# from your phone. These are the forms that survive being typed one-handed:
#
#     Call the landlord @18:00        today at 18:00 (tomorrow if past)
#     Bins out @tomorrow 07:30        explicit tomorrow
#     Take pill in 45m                relative
#     Renew insurance in 3d
#
# The marker is stripped from the text, so the card shows the reminder and
# the deadline shows as a deadline rather than as noise in the sentence.
_REL = re.compile(r"\bin\s+(\d{1,3})\s*(m|min|mins|minutes|h|hr|hrs|hours|d|days?)\b",
                  re.I)
_AT = re.compile(r"@\s*(tomorrow\s+)?(\d{1,2})[:.](\d{2})", re.I)
_UNIT = {"m": 60, "min": 60, "mins": 60, "minutes": 60,
         "h": 3600, "hr": 3600, "hrs": 3600, "hours": 3600,
         "d": 86400, "day": 86400, "days": 86400}


def parse_due(text, now=None):
    """(cleaned_text, due_ts or None). Never raises on odd input."""
    now = now if now is not None else time.time()
    try:
        m = _AT.search(text)
        if m:
            hh, mm = int(m.group(2)), int(m.group(3))
            if 0 <= hh < 24 and 0 <= mm < 60:
                base = datetime.datetime.fromtimestamp(now)
                due = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if m.group(1):                       # "@tomorrow 07:30"
                    due += datetime.timedelta(days=1)
                elif due.timestamp() <= now:         # already gone: mean tomorrow
                    due += datetime.timedelta(days=1)
                cleaned = " ".join((text[:m.start()] + text[m.end():]).split())
                return cleaned or text, due.timestamp()
        m = _REL.search(text)
        if m:
            n = int(m.group(1))
            unit = _UNIT.get(m.group(2).lower(), 60)
            cleaned = " ".join((text[:m.start()] + text[m.end():]).split())
            return cleaned or text, now + n * unit
    except Exception:                                # noqa: BLE001
        pass
    return text, None


class ReminderService:
    """Singleton: polls ntfy, persists reminders until completed."""

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.reminders = []          # [{id, text, ts, done_ts|None}]
        self.since = 0               # ntfy cursor (unix seconds)
        self._load()
        self._poll_timer = 0.0
        self._busy = False
        self._announced = set()      # ids Kea has already fretted about
        self._nag_timer = 0.0

    # -- persistence ---------------------------------------------------------
    def _load(self):
        try:
            with open(PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.reminders = list(d.get("reminders", []))
            self.since = int(d.get("since", 0))
        except Exception:
            self.reminders = []
            self.since = 0

    def _save(self):
        try:
            with open(PATH, "w", encoding="utf-8") as f:
                json.dump({"reminders": self.reminders[-200:],
                           "since": self.since}, f)
        except Exception:
            pass

    # -- polling -------------------------------------------------------------
    def update(self, dt):
        """Call from any state's update(); cheap, never blocks."""
        self._expire(time.time())
        if ENABLED:                       # only fetching needs the network
            self._poll_timer -= dt
            if self._poll_timer <= 0 and not self._busy:
                self._poll_timer = POLL_EVERY
                self._busy = True
                threading.Thread(target=self._poll, daemon=True).start()

        # Kea frets about anything that slips past its deadline, no matter
        # which screen you happen to be looking at — and whether or not the
        # network is up, since these reminders are already on disk.
        self._nag_timer -= dt
        if self._nag_timer <= 0:
            self._nag_timer = 5.0
            now = time.time()
            for r in self.reminders:
                if r["done_ts"] is not None or r["id"] in self._announced:
                    continue
                if stage_for(now - r["ts"]) in ("FINAL CALL", "OVERDUE"):
                    self._announced.add(r["id"])
                    try:
                        from backend import voice
                        voice.say("worried")
                    except Exception:
                        pass
                    break

    def _poll(self):
        try:
            since = self.since if self.since > 0 else "all"
            url = f"https://ntfy.sh/{TOPIC}/json?poll=1&since={since}"
            req = urllib.request.Request(url, headers={"User-Agent": "KeaDisplay/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                lines = r.read().decode().strip().splitlines()
            new = []
            with ReminderService._lock:
                known = {rm["id"] for rm in self.reminders}
                for line in lines:
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if msg.get("event") != "message":
                        continue
                    mid = msg.get("id")
                    text = " ".join(str(msg.get("message", "")).split())[:120]
                    if not mid or not text or mid in known:
                        continue
                    ts = int(msg.get("time", time.time()))
                    text, due = parse_due(text, ts)
                    self.reminders.append(
                        {"id": mid, "text": text, "ts": ts,
                         "due_ts": due, "done_ts": None})
                    self.since = max(self.since, ts)
                    new.append(text)
                if new:
                    self._save()
            if new:
                try:                       # a dispatch just landed
                    from backend import voice
                    voice.say("curious")
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._busy = False

    # -- queries -------------------------------------------------------------
    def active(self):
        """Open reminders, oldest first (the oldest is the most urgent)."""
        with ReminderService._lock:
            return [dict(r) for r in self.reminders if r["done_ts"] is None]

    def count(self):
        return len(self.active())

    def overdue(self):
        now = time.time()
        return [r for r in self.active()
                if stage_for(now - r["ts"], r.get("due_ts"), now)
                in ("FINAL CALL", "OVERDUE", "DUE NOW")]

    def add_local(self, text, ttl_s=None):
        """A reminder Kea raised itself, not one that came from ntfy.

        The watcher uses this to say something moved. Given a ttl it
        self-completes rather than sitting on the Docket forever — "the
        door opened an hour ago" is news that expires, unlike "call the
        landlord", and a board full of stale motion events is a board you
        stop reading.
        """
        now = time.time()
        rid = f"local-{int(now * 1000)}"
        with ReminderService._lock:
            self.reminders.append({
                "id": rid, "text": str(text)[:120], "ts": int(now),
                "due_ts": None, "done_ts": None,
                "expires_ts": (now + ttl_s) if ttl_s else None,
            })
            self._save()
        return rid

    def _expire(self, now):
        """Quietly complete anything past its expiry."""
        changed = False
        with ReminderService._lock:
            for r in self.reminders:
                exp = r.get("expires_ts")
                if exp and r["done_ts"] is None and now >= exp:
                    r["done_ts"] = int(now)
                    changed = True
            if changed:
                self._save()
        return changed

    def set_due(self, rid, due_ts):
        """Set or clear a deadline on the device."""
        with ReminderService._lock:
            for r in self.reminders:
                if r["id"] == rid:
                    r["due_ts"] = due_ts
                    self._save()
                    return r.get("due_ts")
        return None

    def next_due(self):
        """The soonest deadline among open reminders, or None."""
        due = [r["due_ts"] for r in self.active() if r.get("due_ts")]
        return min(due) if due else None

    def complete(self, rid):
        """Stamp a reminder DONE. Returns its text, or None."""
        with ReminderService._lock:
            for r in self.reminders:
                if r["id"] == rid and r["done_ts"] is None:
                    r["done_ts"] = int(time.time())
                    self._announced.discard(rid)
                    self._save()
                    try:                   # Kea is pleased for you
                        from backend import voice
                        voice.say("happy", force=True)
                    except Exception:
                        pass
                    return r["text"]
        return None

    def complete_oldest(self):
        act = self.active()
        return self.complete(act[0]["id"]) if act else None

    def done_today(self):
        cut = time.time() - 86400
        with ReminderService._lock:
            return sum(1 for r in self.reminders
                       if r["done_ts"] and r["done_ts"] > cut)
