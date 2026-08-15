"""
gestures.py — what the two servos should be doing, and who wins.

servo.py knows how to move a servo safely. This decides what to move it
*to*, from what is going on in the app. Kept apart so the driver stays a
driver and the policy stays readable.

THREE JOBS, ONE ARM

    THE GAUGE    the angle is the countdown to a departure YOU armed
                 with RED on the Board. Opt-in, time-critical, and the
                 screen shows the same thing so the two never disagree.
    THE FOCUS    during a Pomodoro the angle is how far through you are,
                 and it taps at each quarter — one tap at a quarter, two
                 at half, three at three-quarters, four at the end. You
                 can hear your progress without looking up.
    THE MAST     down = nothing owed, half = something pending, up =
                 overdue. Ambient, slow, the state of your obligations.

Priority is gauge > focus > mast, and the reasoning is about what is
recoverable. Missing a tram cannot be undone and you deliberately armed
it, so it wins. A Pomodoro quarter is worth knowing but nothing breaks
if you learn it thirty seconds late. The mast will still be true in an
hour, so it yields to both.

Every handover is announced by a distinct double-tap, because otherwise
"half raised" means three different things with no way to tell which.

The gauge used to follow whatever departure happened to be soonest,
which was wrong twice over: the arm reported a tram you had no intention
of catching, and you could not tell which one it meant. It now only
tracks a departure you armed.

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
FOCUS_POLL = 10.0        # seconds between updating the focus angle
DOUBLE_TAKE_DEG = 12.0   # how far the monitor flicks
MIN_STEP_DEG = 4.0       # mast: ignore smaller changes, not worth the noise
# The gauge is a continuous readout, so small moves ARE the point. At 20 s
# polls across a 12 min window each step is only about 2 deg on a typical
# arm, which the mast's 4 deg threshold would swallow — the countdown
# would visibly move every 40 s instead of every 20.
GAUGE_MIN_STEP_DEG = 1.5
TAP_GAP = 0.09           # seconds between the two handover taps


class Gestures:
    """Drives both servos from app state. Tick it from the main loop."""

    def __init__(self, manager=None):
        self.manager = manager
        self.enabled = True
        self._mast_t = MAST_POLL
        self._gauge_t = GAUGE_POLL
        self._last_count = None
        self._gauge_active = False
        self._focus_t = FOCUS_POLL
        self._focus_quarter = None   # last quarter announced
        self._owner = None           # "gauge" / "focus" / "mast"
        self._arm_target = None
        self._take = None            # (stage, deadline, home angle)
        self._tap = None             # queued handover taps
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

    def _focus(self):
        """(fraction through the session, quarter 1-4) or None.

        Only while a work session is actually running — a break is rest,
        and an arm ticking through your rest is the opposite of rest.
        """
        try:
            p = self.manager.states.get("pomodoro") if self.manager else None
        except Exception:                              # noqa: BLE001
            return None
        if p is None or not getattr(p, "running", False):
            return None
        if getattr(p, "mode", "work") != "work":
            return None
        try:
            from states.pomodoro_state import WORK_TIME
            total = float(getattr(p, "session_len", None) or WORK_TIME)
            left = float(p.time_left)
        except Exception:                              # noqa: BLE001
            return None
        if total <= 0:
            return None
        done = max(0.0, min(1.0, 1.0 - left / total))
        return done, min(4, int(done * 4) + (1 if done >= 1.0 else 0))

    def _gauge_fraction(self):
        """1.0 = go now, 0.0 = GAUGE_WINDOW minutes out. None if no tram.

        Reads whatever the Board last fetched rather than fetching here:
        the arm must never *block* on the network.

        It used to say "never be a reason to hit the network", which was
        wrong and quietly broke the feature. States only tick while they
        are on screen, so the Board stopped refreshing the moment you
        left it — and the gauge, whose entire point is that you do not
        have to look at the screen, only had data while you were looking
        at the screen. main.py now ticks the Board's background_update()
        off-screen: one route, every five minutes.
        """
        st = None
        try:
            st = self.manager.states.get("transit") if self.manager else None
        except Exception:                              # noqa: BLE001
            return None
        if st is None:
            return None
        try:
            from backend import vvs
            d = st.tracked_departure()     # ONLY what you armed with RED
            if d is None:
                return None
            left = d.leave_in(vvs._now())
            if left > GAUGE_WINDOW:
                return 0.0                 # armed but still far off: flat
            return max(0.0, min(1.0, 1.0 - left / GAUGE_WINDOW))
        except Exception:                              # noqa: BLE001
            return None

    def _point_arm(self, fraction, why):
        """Move the arm to a fraction of its travel, if it is worth it."""
        arm = servo.flag()
        lo = arm.positions.get(arm.labels[0], arm.lo)
        hi = arm.positions.get(arm.labels[2], arm.hi)
        target = lo + (hi - lo) * max(0.0, min(1.0, fraction))
        floor = (GAUGE_MIN_STEP_DEG if why in ("gauge", "focus")
                 else MIN_STEP_DEG)
        if (self._arm_target is not None
                and abs(target - self._arm_target) < floor):
            return False                   # too small to be worth the noise
        self._arm_target = target
        arm.move_to(target)
        return True

    def _claim(self, who):
        """Hand the arm to a new owner, announcing the change."""
        if self._owner == who:
            return
        if self._owner is not None:
            self._handover_tap()       # only announce a real handover
        self._owner = who
        self._arm_target = None        # force the first move of the new job

    def _handover_tap(self):
        """Two quick taps: the arm has changed what it is telling you.

        Without this a gauge angle and a mast angle look identical, and
        "half raised" would mean either "something pending" or "tram in
        six minutes" with no way to tell.

        QUEUED, not slept. The first version did four writes with 0.09 s
        sleeps between them — 0.36 s inside the render loop, eleven
        dropped frames, and a direct violation of UI_GUIDELINES 7. The
        taps are now steps the main loop walks through.
        """
        arm = servo.flag()
        base = arm.angle if arm.angle is not None else arm.centre_deg
        self._tap = [base, 4, 0.0]         # home, steps left, next-step time

    def _tap_n(self, n):
        """n taps, queued. Used for quarters: you can count them by ear."""
        arm = servo.flag()
        base = arm.angle if arm.angle is not None else arm.centre_deg
        self._tap = [base, n * 2, 0.0]

    def _tick_tap(self, now):
        if not self._tap:
            return
        base, left, when = self._tap
        if now < when:
            return
        arm = servo.flag()
        arm.write(arm.clamp(base + (8 if left % 2 == 0 else 0)))
        left -= 1
        self._tap = None if left <= 0 else [base, left, now + TAP_GAP]

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
            self._tick_tap(now)
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
            self._focus_t += dt

            # Who owns the arm right now? gauge > focus > mast, decided
            # by what cannot be recovered if you miss it.
            focus = self._focus()

            if self._gauge_t >= GAUGE_POLL:
                self._gauge_t = 0.0
                g = self._gauge_fraction()
                if g is not None:
                    self._claim("gauge")
                    self._point_arm(g, "gauge")
                elif self._owner == "gauge":
                    self._owner = None     # tram gone: release

            if self._owner != "gauge" and focus is not None:
                done, quarter = focus
                if self._owner != "focus":
                    self._claim("focus")
                    self._focus_quarter = None
                if quarter != self._focus_quarter and quarter >= 1:
                    self._focus_quarter = quarter
                    self._tap_n(quarter)   # 1..4 taps: count them by ear
                    self._arm_target = None
                if self._focus_t >= FOCUS_POLL:
                    self._focus_t = 0.0
                    self._point_arm(done, "focus")
            elif self._owner == "focus" and focus is None:
                self._owner = None
                self._focus_quarter = None

            if self._owner is None and self._mast_t >= MAST_POLL:
                self._mast_t = 0.0
                m = self._mast_fraction()
                if m is not None:
                    if self._owner != "mast":
                        self._claim("mast")
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
