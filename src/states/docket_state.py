"""
docket_state.py
---------------
THE DOCKET — does anything need me? Answered without reading.

This is the calm one. Big status word, a count, the next deadline, and
nothing else. When there is nothing owed it says ALL CLEAR and means it,
which turned out to be the part worth keeping from the original screen:
a board that can tell you you are finished is doing something a list
cannot.

    ENCODER press   open ALERTS and go through them
    ENCODER turn    also opens ALERTS
    GREEN           complete the most urgent one, without leaving
    HOME button     back to Nexus

WHY THIS IS SEPARATE FROM ALERTS

They answer different questions. "Is there anything?" should be
answerable from across the desk, in one glance, with no reading. "What
is it and what do I do about it?" needs the whole screen for one message
at a time. Collapsing both into one screen is what produced the original
Docket: several cards, small type, and no clear answer to either
question. So: Docket for the answer, ALERTS for the detail, and the
dispatch interrupt (states/alert_state.py) for when it cannot wait.

The status word is the whole design. If you have to count pips or read a
number to know whether you are clear, it has failed.
"""

import time

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from ui import palette as pal
from backend.reminders import ReminderService, stage_for, TOPIC

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


# Worst stage present -> (word, colour). Ordered most urgent first, and
# the first match wins, so one overdue thing outranks nine scheduled ones.
VERDICTS = [
    (("OVERDUE",),              "OVERDUE",   pal.BLOOD),
    (("DUE NOW", "FINAL CALL"), "DUE NOW",   pal.MAGENTA),
    (("DUE SOON",),             "DUE SOON",  pal.AMBER),
    (("TODAY", "BOARDING"),     "TODAY",     pal.ICE),
    (("SCHEDULED", "POSTED"),   "STANDING",  pal.CYAN),
]


class DocketState(State):
    """The overview. One word, one number, one deadline."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()
        self.font_title = pygame.font.Font(None, s(24))
        self.font_verdict = pygame.font.Font(None, s(78))
        self.font_count = pygame.font.Font(None, s(34))
        self.font_line = pygame.font.Font(None, s(22))
        self.font_meta = pygame.font.Font(None, s(17))
        self.font_hint = pygame.font.Font(None, s(15))

        self.service = ReminderService.instance()
        self.t = 0.0
        self.flash = ""
        self.flash_t = 0.0
        self._bg = None

    # ── lifecycle ──────────────────────────────────────────────────────
    def enter(self):
        self.t = 0.0

    # ── controls ───────────────────────────────────────────────────────
    def move_cursor(self, direction):
        """Claims the dial — turning it opens the list rather than
        walking you into another world, which is what it used to do."""
        self._open_alerts()
        return True

    def activate(self):
        self._open_alerts()
        return True

    def on_green_button(self):
        """Clear the most urgent thing without leaving the overview."""
        items = self._sorted()
        if not items:
            self._flash("NOTHING OWED")
            return True
        rec = items[0]
        try:
            self.service.complete(rec["id"])
            from backend import alerts
            alerts.instance().completed(rec["id"])
        except Exception:                                   # noqa: BLE001
            pass
        self._flash("DELIVERED")
        return True

    def toggle_label(self):
        return ""

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._open_alerts()
                elif e.key == pygame.K_g:
                    self.on_green_button()

    def _open_alerts(self):
        if self.manager and "alerts" in getattr(self.manager, "states", {}):
            self.manager.change_state("alerts")

    def _flash(self, text):
        self.flash, self.flash_t = text, 1.4

    # ── data ───────────────────────────────────────────────────────────
    def _sorted(self):
        try:
            rs = self.service.active()
        except Exception:                                   # noqa: BLE001
            return []
        return sorted(rs, key=lambda r: (r.get("due_ts") is None,
                                         r.get("due_ts") or 0, r["ts"]))

    def _verdict(self, items, now):
        stages = {stage_for(max(0.0, now - r.get("ts", now)),
                            r.get("due_ts"), now) for r in items}
        for names, word, colour in VERDICTS:
            if stages & set(names):
                return word, colour
        return "STANDING", pal.CYAN

    # ── update ─────────────────────────────────────────────────────────
    def update(self, dt):
        self.t += dt
        self.service.update(dt)
        if self.flash_t > 0:
            self.flash_t = max(0.0, self.flash_t - dt)

    # ── drawing ────────────────────────────────────────────────────────
    def draw(self, surface):
        w, h = surface.get_size()
        if self._bg is None or self._bg.get_size() != (w, h):
            self._bg = self._make_bg((w, h))
        surface.blit(self._bg, (0, 0))

        now = time.time()
        items = self._sorted()
        if not items:
            self._draw_clear(surface, now)
        else:
            self._draw_owed(surface, items, now)

        if self.flash_t > 0:
            f = self.font_line.render(self.flash, True, pal.ACID)
            surface.blit(f, ((w - f.get_width()) // 2, h - s(58)))
        hint = ("PRESS OPENS ALERTS" if items
                else f"POST TO  ntfy.sh/{TOPIC}")
        g = self.font_hint.render(hint, True, pal.INK_DIM)
        surface.blit(g, ((w - g.get_width()) // 2, h - s(34)))

    def _draw_clear(self, surface, now):
        """The screen worth keeping: it can tell you that you are done."""
        w, h = surface.get_size()
        cy = int(h * 0.36)
        pulse = 0.5 + 0.5 * pygame.math.Vector2(1, 0).rotate(self.t * 40).x
        surface.blit(pal.halo(s(78), pal.ACID, int(40 + 26 * pulse)),
                     (w // 2 - s(78), cy - s(78)))
        pygame.draw.circle(surface, pal.mix(pal.ACID, pal.VOID, 0.72),
                           (w // 2, cy), s(46))
        pygame.draw.circle(surface, pal.ACID, (w // 2, cy), s(46), 2)
        tick = [(w // 2 - s(18), cy), (w // 2 - s(5), cy + s(14)),
                (w // 2 + s(19), cy - s(14))]
        pygame.draw.lines(surface, pal.ACID, False, tick, s(5))

        g = pal.glow_text(self.font_verdict, "ALL CLEAR", pal.ACID, radius=3)
        gy = cy + s(58)
        surface.blit(g, ((w - g.get_width()) // 2, gy))
        # Positioned from the glow's real height, not a guessed offset —
        # at 78 pt the glyphs plus bloom are taller than the gap I had
        # picked and the subtitle sat on top of them.
        sub = self.font_line.render("NOTHING NEEDS YOU", True, pal.INK_DIM)
        surface.blit(sub, ((w - sub.get_width()) // 2, gy + g.get_height() + s(4)))

    def _draw_owed(self, surface, items, now):
        w, h = surface.get_size()
        word, colour = self._verdict(items, now)

        g = pal.glow_text(self.font_verdict, word, colour, radius=3)
        surface.blit(g, ((w - g.get_width()) // 2, int(h * 0.16)))

        n = len(items)
        cnt = self.font_count.render(
            f"{n} OPEN" if n != 1 else "1 OPEN", True, pal.INK)
        surface.blit(cnt, ((w - cnt.get_width()) // 2, int(h * 0.34)))

        # The single most urgent one, named. A count alone tells you there
        # is work; the name tells you whether it is the work you feared.
        top = items[0]
        text = (top.get("text", "") or "")[:34]
        t = self.font_line.render(text, True, pal.INK_DIM)
        surface.blit(t, ((w - t.get_width()) // 2, int(h * 0.45)))

        from states.alerts_state import due_text
        due = due_text(top.get("due_ts"), now)
        if due:
            d = self.font_meta.render(due, True, colour)
            surface.blit(d, ((w - d.get_width()) // 2, int(h * 0.52)))

        # one bar per reminder, worst first, so the shape of the day reads
        bar_y = int(h * 0.62)
        bw = min(s(40), (w - s(40)) // max(1, n))
        x = (w - n * bw) // 2
        for r in items:
            st = stage_for(max(0.0, now - r.get("ts", now)),
                           r.get("due_ts"), now)
            c = dict(zip([v[1] for v in VERDICTS],
                         [v[2] for v in VERDICTS])).get(
                {"OVERDUE": "OVERDUE", "DUE NOW": "DUE NOW",
                 "FINAL CALL": "DUE NOW", "DUE SOON": "DUE SOON",
                 "TODAY": "TODAY", "BOARDING": "TODAY"}.get(st, "STANDING"),
                pal.CYAN)
            pygame.draw.rect(surface, c, (x + s(2), bar_y, bw - s(4), s(8)),
                             border_radius=s(2))
            x += bw

    def _make_bg(self, size):
        w, h = size
        bg = pygame.Surface(size)
        bg.fill(pal.VOID)
        bg.blit(pal.grid((w, h), step=s(22), glow_every=4), (0, 0))
        head = pygame.Rect(0, 0, w, s(34))
        pygame.draw.rect(bg, pal.PANEL, head)
        pygame.draw.line(bg, pal.CYAN, (0, s(34)), (w, s(34)), 2)
        pal.blit_glow(bg, self.font_title, "DISPATCH DOCKET", pal.CYAN,
                      (s(14), s(9)))
        return bg

    def draw_pomodoro(self, surface, time_left, mode):
        m, sec = divmod(max(0, int(time_left)), 60)
        col = pal.AMBER if mode == "work" else pal.ACID
        g = self.font_meta.render(f"{m:02d}:{sec:02d}", True, col)
        surface.blit(g, (surface.get_width() - g.get_width() - s(16), s(42)))
