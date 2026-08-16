"""
alerts.py — deciding when a reminder is allowed to take the screen.

The Docket was passive. A reminder arrived from your phone, aged quietly
through POSTED to OVERDUE, and none of it reached you unless you happened
to be looking at that one screen. A thing built to stop you forgetting
relied on you remembering to check it.

So: a reminder now interrupts. This module owns *when*, and nothing else
— states/alert_state.py owns what it looks like. Kept apart because the
policy is the part with opinions in it.

THE RULES

1. A new reminder alerts, whatever is on screen.
2. Except during a focus session. That is the one thing Kea protects,
   and an alert is exactly the interruption a Pomodoro exists to prevent.
3. Nothing is dropped. Anything that arrives during a session is HELD,
   and the moment the session ends the queue drains, one after another.
   Silence during focus must not become silence afterwards.
4. An alert hands the screen back by itself after ALERT_SECONDS. It must
   never trap the display — it fires while you are using something else,
   and it can fire while you are not in the room at all.
5. If it is still not done after RENAG_AFTER, it alerts again. Handing
   back is not the same as being dealt with.

The re-nag interval grows each time (RENAG_AFTER, then doubling up to
RENAG_MAX) so a reminder you are deliberately ignoring becomes quieter
rather than a metronome you learn to tune out.
"""

import os
import time


def _num(env, default):
    try:
        return max(1.0, float(os.getenv(env, "")))
    except (TypeError, ValueError):
        return default


ALERT_SECONDS = _num("KEA_ALERT_SECONDS", 20.0)   # before handing back
RENAG_AFTER = _num("KEA_ALERT_RENAG", 300.0)      # first re-alert, 5 min
RENAG_MAX = _num("KEA_ALERT_RENAG_MAX", 3600.0)   # never slower than hourly
SETTLE = 1.5          # gap between consecutive alerts when draining a queue


class Alerts:
    """Watches the reminder service and says what deserves the screen."""

    def __init__(self, manager=None):
        self.manager = manager
        self.enabled = True
        self._known = set()          # reminder ids we have seen at all
        self._queue = []             # ids waiting for their turn
        self._next_at = {}           # id -> when it may alert again
        self._interval = {}          # id -> current re-nag gap
        self._last_shown = 0.0
        self._primed = False         # first pass only learns, never alerts

    # ── the one thing that silences an alert ───────────────────────────
    def in_focus(self):
        """A running WORK session. A break is not focus — an alert during
        a break is fine, and holding one until you are working again would
        be exactly backwards."""
        try:
            p = self.manager.states.get("pomodoro") if self.manager else None
        except Exception:                                   # noqa: BLE001
            return False
        return bool(p is not None and getattr(p, "running", False)
                    and getattr(p, "mode", "work") == "work")

    def _service(self):
        try:
            from backend.reminders import ReminderService
            return ReminderService.instance()
        except Exception:                                   # noqa: BLE001
            return None

    # ── the queue ──────────────────────────────────────────────────────
    def poll(self):
        """Notice arrivals and things that have gone quiet for too long."""
        svc = self._service()
        if svc is None:
            return
        try:
            active = svc.active()
        except Exception:                                   # noqa: BLE001
            return
        now = time.time()
        live = {r["id"] for r in active}

        for r in active:
            rid = r["id"]
            if rid not in self._known:
                self._known.add(rid)
                # The first poll of a run learns what already exists
                # instead of alerting for every open reminder at once —
                # a restart should not empty the whole board at you.
                if self._primed:
                    self._enqueue(rid, now)
                continue
            due = self._next_at.get(rid)
            if due is not None and now >= due and rid not in self._queue:
                self._enqueue(rid, now, renag=True)

        # completed or vanished: forget them entirely
        for rid in list(self._known):
            if rid not in live:
                self._known.discard(rid)
                self._next_at.pop(rid, None)
                self._interval.pop(rid, None)
                if rid in self._queue:
                    self._queue.remove(rid)

        self._primed = True

    def _enqueue(self, rid, now, renag=False):
        if rid in self._queue:
            return
        self._queue.append(rid)
        gap = self._interval.get(rid, RENAG_AFTER)
        if renag:
            gap = min(RENAG_MAX, gap * 2)      # ignored twice? ask less often
        self._interval[rid] = gap
        self._next_at[rid] = now + gap

    def held(self):
        """How many are waiting for focus to end. Shown on the Pomodoro."""
        return len(self._queue) if self.in_focus() else 0

    def next_alert(self):
        """The reminder that should take the screen now, or None.

        Returns the record itself so the alert screen never has to go
        looking, and so a reminder completed between queueing and showing
        simply disappears rather than alerting about nothing.
        """
        if not self.enabled or not self._queue:
            return None
        if self.in_focus():
            return None                     # held, deliberately
        now = time.time()
        if now - self._last_shown < SETTLE:
            return None                     # drain a queue, do not stack it
        svc = self._service()
        if svc is None:
            return None
        try:
            by_id = {r["id"]: r for r in svc.active()}
        except Exception:                                   # noqa: BLE001
            return None
        while self._queue:
            rid = self._queue.pop(0)
            rec = by_id.get(rid)
            if rec is not None:
                self._last_shown = now
                return rec
        return None

    def dismissed(self, rid):
        """Alert closed without completing: it will come back later."""
        gap = self._interval.get(rid, RENAG_AFTER)
        self._next_at[rid] = time.time() + gap

    def completed(self, rid):
        self._known.discard(rid)
        self._next_at.pop(rid, None)
        self._interval.pop(rid, None)
        if rid in self._queue:
            self._queue.remove(rid)


_singleton = None


def instance(manager=None):
    global _singleton
    if _singleton is None:
        _singleton = Alerts(manager)
    elif manager is not None and _singleton.manager is None:
        _singleton.manager = manager
    return _singleton
