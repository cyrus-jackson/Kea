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

import json
import os
import threading
import time
import urllib.request

TOPIC = os.getenv("KEA_NTFY_TOPIC", "kea-dispatch-" +
                  os.getenv("KEA_USER", "cyrus").lower())
ENABLED = os.getenv("KEA_FEEDS", "1").strip().lower() not in {"0", "false", "off"}
PATH = os.path.join(os.path.expanduser("~"), ".kea_reminders.json")
POLL_EVERY = 30.0

# urgency stages by age (seconds -> label); the board colors these
STAGES = [
    (0,          "POSTED"),
    (3600,       "BOARDING"),
    (4 * 3600,   "FINAL CALL"),
    (24 * 3600,  "OVERDUE"),
]


def stage_for(age_s):
    label = STAGES[0][1]
    for threshold, name in STAGES:
        if age_s >= threshold:
            label = name
    return label


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
        if not ENABLED:
            return
        self._poll_timer -= dt
        if self._poll_timer <= 0 and not self._busy:
            self._poll_timer = POLL_EVERY
            self._busy = True
            threading.Thread(target=self._poll, daemon=True).start()

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
                    self.reminders.append(
                        {"id": mid, "text": text, "ts": ts, "done_ts": None})
                    self.since = max(self.since, ts)
                    new.append(text)
                if new:
                    self._save()
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
                if stage_for(now - r["ts"]) in ("FINAL CALL", "OVERDUE")]

    def complete(self, rid):
        """Stamp a reminder DONE. Returns its text, or None."""
        with ReminderService._lock:
            for r in self.reminders:
                if r["id"] == rid and r["done_ts"] is None:
                    r["done_ts"] = int(time.time())
                    self._save()
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
