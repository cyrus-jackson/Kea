"""
gestures.py — what the two servos should be doing, and who wins.

servo.py knows how to move a servo safely. This decides what to move it
*to*, from what is going on in the app. Kept apart so the driver stays a
driver and the policy stays readable.

THE ARM HAS TWO JOBS AND ONE ARM

Two behaviours want it:

    THE MAST     down = nothing owed, 45 deg = something pending,
                 up = overdue. Slow, persistent, the ambient state of
                 your obligations.
    THE GAUGE    the angle *is* the countdown to a tram you can still
                 catch. Fast, transient, and time-critical.

They cannot both have it, so the gauge takes over when a departure is
inside GAUGE_WINDOW minutes and hands back afterwards. That is the right
way round: the mast is information that will still be true in an hour,
the countdown stops being useful the moment you have missed it. The
handover is announced by a distinct double-tap so you never misread a
gauge angle as an obligation level.

THE MONITOR IS ABOUT ATTENTION, NOT STATUS

It only does two things. A **double-take** — a flick and back — when a
dispatch arrives, which is body language rather than a notification. And
**aim**, where the Console's dial physically points the screen, because
sometimes you just want it turned a bit and shoving the chassis is
worse.

WHY MOVEMENT IS RARE BY DESIGN

Not power: one 1-second move costs about 0.056 mAh, so a 4xAA pack is
good for tens of thousands, and even moving every minute all day would
last over a month. It is *noise*. A servo on a desk is loud and pulls
your eye, so a move has to be worth the interruption. Motion is
punctuation, not animation.
"""

import time

from backend import servo

# The gauge only takes the arm when a departure is this close, in minutes.
# Wider and it is holding the arm hostage all day for a tram you are not
# catching; narrower and it moves once and you have already left.
GAUGE_WINDOW = 12.0

MAST_POLL = 5.0          # seconds between checking what is owed
GAUGE_POLL = 20.0        # seconds between recomputing the countdown
DOUBLE_TAKE_DEG = 12.0   # how far the monitor flicks
MIN_STEP_DEG = 4.0       # ignore smaller changes: not worth the noise


class Gestures:
    """Drives both servos from app state. Tick it from the main loop."""

    def __init__(self, manager=None):
        self.manager = manager
        self.enabled = True
        self._mast_t = MAST_POLL
        self._gauge_t = GAUGE_POLL
        self._last_count = None
        self._gauge_active = False
        self._arm_target = None
        self._take = None            # (stage, deadline, home angle)
        self._aim = None             # last aim offset applied

    # ── the arm ────────────────────────────────────────────────────────
    def _mast_fraction(self):
        """0.0 nothing owed .. 1.0 overdue. None if we cannot tell."""
        try:
            from backend.reminders import ReminderService
            svc = ReminderService.instance()
            overdue = len(svc.overdue())
            open_n = svc.count()
        except Exception:                              # noqa: BLE001
            return None
        if overdue:
            return 1.0
        if open_n:
            return 0.5
        return 0.0

    def _gauge_fraction(self):
        """1.0 = go now, 0.0 = GAUGE_WINDOW minutes out. None if no tram.

        Reads whatever the transit screen last fetched rather than making
        its own request — the arm must never be a reason to hit the
        network, and a stale answer is better than a blocking one.
        """
        st = None
        try:
            st = self.manager.states.get("transit") if self.manager else None
        except Exception:                              # noqa: BLE001
            return None
        if st is None or not getattr(st, "rows", None):
            return None
        try:
            from backend import vvs
            now = vvs._now()
            best = None
            for _deps, _err in [st.rows.get(r.label, ([], None))
                                for r in st.routes]:
                for d in _deps:
                    if d.catchable(now):
                        left = d.leave_in(now)
                        if best is None or left < best:
                            best = left
                        break              # soonest per route is enough
            if best is None or best > GAUGE_WINDOW:
                return None
            return max(0.0, min(1.0, 1.0 - best / GAUGE_WINDOW))
        except Exception:                              # noqa: BLE001
            return None

    def _point_arm(self, fraction, why):
        """Move the arm to a fraction of its travel, if it is worth it."""
        arm = servo.flag()
        lo = arm.positions.get(arm.labels[0], arm.lo)
        hi = arm.positions.get(arm.labels[2], arm.hi)
        target = lo + (hi - lo) * max(0.0, min(1.0, fraction))
        if (self._arm_target is not None
                and abs(target - self._arm_target) < MIN_STEP_DEG):
            return False                   # too small to be worth the noise
        self._arm_target = target
        arm.move_to(target)
        return True

    def _handover_tap(self):
        """Two quick taps: the arm has changed what it is telling you.

        Without this a gauge angle and a mast angle look identical, and
        "half raised" would mean either "something pending" or "tram in
        six minutes" with no way to tell.
        """
        arm = servo.flag()
        base = arm.angle if arm.angle is not None else arm.centre_deg
        for _ in range(2):
            arm.write(arm.clamp(base + 8))
            time.sleep(0.09)
            arm.write(arm.clamp(base))
            time.sleep(0.09)

    # ── the monitor ────────────────────────────────────────────────────
    def double_take(self):
        """A flick and back. Queued, not blocking — the render loop is
        30 fps and a servo move takes the better part of a second."""
        mon = servo.monitor()
        home = mon.angle if mon.angle is not None else mon.centre_deg
        self._take = ["out", time.time() + 0.35, home]
        mon.move_to(mon.clamp(home + DOUBLE_TAKE_DEG), speed=8.0)

    def _tick_double_take(self, now):
        if not self._take:
            return
        stage, when, home = self._take
        if now < when:
            return
        mon = servo.monitor()
        if stage == "out":
            mon.move_to(mon.clamp(home - DOUBLE_TAKE_DEG * 0.4), speed=8.0)
            self._take = ["back", now + 0.3, home]
        else:
            mon.move_to(home, speed=8.0)
            self._take = None

    def apply_aim(self):
        """Point the monitor at the Console's AIM dial, if it moved."""
        try:
            from backend import settings
            offset = float(settings.get("aim"))
        except Exception:                              # noqa: BLE001
            return
        if self._aim is not None and abs(offset - self._aim) < 1.0:
            return
        self._aim = offset
        mon = servo.monitor()
        mon.move_to(mon.clamp(mon.centre_deg + offset), speed=6.0)

    # ── the loop ───────────────────────────────────────────────────────
    def update(self, dt):
        """Cheap enough to call every frame. Never raises, never blocks
        for longer than one servo step."""
        if not self.enabled:
            return
        now = time.time()
        try:
            self._tick_double_take(now)
            # The AIM dial is a live control: turning it should move the
            # screen while you watch, so it is checked every tick. The
            # early-out in apply_aim() means that costs one float compare
            # when the dial has not moved.
            self.apply_aim()

            # a dispatch just arrived -> the monitor notices
            try:
                from backend.reminders import ReminderService
                n = ReminderService.instance().count()
            except Exception:                          # noqa: BLE001
                n = None
            if n is not None:
                if self._last_count is not None and n > self._last_count:
                    self.double_take()
                self._last_count = n

            self._gauge_t += dt
            self._mast_t += dt

            if self._gauge_t >= GAUGE_POLL:
                self._gauge_t = 0.0
                g = self._gauge_fraction()
                if g is not None:
                    if not self._gauge_active:
                        self._gauge_active = True
                        self._handover_tap()
                        self._arm_target = None        # force the first move
                    self._point_arm(g, "gauge")
                elif self._gauge_active:
                    self._gauge_active = False         # tram gone: hand back
                    self._handover_tap()
                    self._arm_target = None
                    self._mast_t = MAST_POLL

            if not self._gauge_active and self._mast_t >= MAST_POLL:
                self._mast_t = 0.0
                m = self._mast_fraction()
                if m is not None:
                    self._point_arm(m, "mast")

            servo.update(now)                          # idle-relax both
        except Exception:                              # noqa: BLE001
            pass          # a gesture is never worth taking the screen down


_singleton = None


def instance(manager=None):
    global _singleton
    if _singleton is None:
        _singleton = Gestures(manager)
    elif manager is not None and _singleton.manager is None:
        _singleton.manager = manager
    return _singleton
