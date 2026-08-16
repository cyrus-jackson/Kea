"""
alert_state.py
--------------
THE ALERT — a reminder taking the screen, in type you can read.

This is the screen Kea shows when something arrives from your phone. It
is deliberately almost empty: one message, as large as it will go, and
two buttons. Everything the Docket knows about stages and ageing and
pneumatic tubes is absent, because an alert has one job and reading it
must take no effort at all.

    GREEN    DONE — completes the reminder
    RED      DISMISS — clears the alert, leaves the reminder open
    anything else returns you to what you were doing

It hands the screen back on its own after ~20 s. An alert that waits
forever is one that traps the display when it fires in an empty room —
see backend/alerts.py, which owns the timing and the re-nag.

TYPE SIZE IS THE FEATURE

The Docket drew its words with Font(None, 22) — which is 15 px of actual
glyph on a 480 px panel, the same scale the transit board uses for
*numbers*. Numbers you glance at; words you read.

Worth knowing, because it caught me out: pygame's size argument is not
pixel height. Font(None, 40) is 27 px tall, Font(None, 80) is 55. The
ladder here is chosen from measured heights and starts at 80, so a short
reminder is 55 px — nearly four times the old card — and only steps down
when the text genuinely will not wrap into the space.
"""

import time

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from ui import palette as pal

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


# The message is fitted by trying these in order — big first, and only
# stepping down when the text genuinely will not wrap into the space.
# Pygame's font size argument is NOT pixel height: Font(None, 40) renders
# only 27 px tall. The old card used Font(None, 22) — 15 px of actual
# glyph, which is what "I can hardly read it" meant. This ladder is set
# from measured heights, not from nominal numbers, and starts high enough
# to use the card: 80 gives 55 px, twice the old screen's title.
MSG_SIZES = (80, 68, 58, 48, 40, 32, 26)
MAX_LINES = 5


class AlertState(State):
    """One reminder, big, with two buttons."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()
        self.font_kicker = pygame.font.Font(None, s(20))
        self.font_meta = pygame.font.Font(None, s(17))
        self.font_btn = pygame.font.Font(None, s(22))
        self._msg_fonts = {n: pygame.font.Font(None, s(n)) for n in MSG_SIZES}

        self.record = None
        self.t = 0.0
        self.result = None        # "done" / "dismissed" / None
        self._lines = []
        self._font = self._msg_fonts[MSG_SIZES[-1]]
        self._bg = None

    # ── lifecycle ──────────────────────────────────────────────────────
    def show(self, record):
        """Called before change_state('alert')."""
        self.record = record
        self.result = None
        self._layout()

    def enter(self):
        self.t = 0.0
        self._layout()
        try:
            from backend import voice
            voice.say("question", force=True)   # an alert you can hear
        except Exception:                                   # noqa: BLE001
            pass

    # ── text fitting ───────────────────────────────────────────────────
    def _wrap(self, font, text, width):
        """Word wrap, breaking inside a word when a word is too wide.

        German compounds and URLs do not have spaces in them.
        "Kraftfahrzeughaftpflichtversicherung" is 314 px at the smallest
        size on a 280 px card, so no choice of font size can save it and a
        wrapper that only splits on spaces will always overflow. Falling
        back to a character break is ugly for one line and correct for
        every line after it.
        """
        lines, cur = [], ""
        for w in text.split():
            trial = (cur + " " + w).strip()
            if font.size(trial)[0] <= width:
                cur = trial
                continue
            if cur:
                lines.append(cur)
                cur = ""
            if font.size(w)[0] <= width:
                cur = w
                continue
            for ch in w:                    # the word alone is too wide
                if font.size(cur + ch)[0] > width and cur:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
        if cur:
            lines.append(cur)
        return lines

    def _layout(self):
        """Biggest size whose wrap still fits the space, then stop."""
        text = (self.record or {}).get("text", "") or "(no text)"
        width = SCREEN_WIDTH - s(36)
        room = int(SCREEN_HEIGHT * 0.44)
        for n in MSG_SIZES:
            f = self._msg_fonts[n]
            lines = self._wrap(f, text, width)
            # Width matters as much as height. _wrap() lets a single word
            # overflow rather than dropping it, so a long one ("Anmeldung"
            # at 55 px) ran clean off the card while the line count and
            # total height both said it fitted. Check the widest line.
            widest = max((f.size(l)[0] for l in lines), default=0)
            if (len(lines) <= MAX_LINES
                    and len(lines) * f.get_height() <= room
                    and widest <= width):
                self._font, self._lines = f, lines
                return
        f = self._msg_fonts[MSG_SIZES[-1]]
        self._font = f
        self._lines = self._wrap(f, text, width)[:MAX_LINES]

    # ── controls ───────────────────────────────────────────────────────
    def on_green_button(self):
        """DONE."""
        rid = (self.record or {}).get("id")
        try:
            from backend.reminders import ReminderService
            from backend import alerts
            ReminderService.instance().complete(rid)
            alerts.instance().completed(rid)
        except Exception:                                   # noqa: BLE001
            pass
        self.result = "done"
        self._leave()
        return True

    def on_red_button(self):
        """DISMISS — the reminder stays open and will come back."""
        rid = (self.record or {}).get("id")
        try:
            from backend import alerts
            alerts.instance().dismissed(rid)
        except Exception:                                   # noqa: BLE001
            pass
        self.result = "dismissed"
        self._leave()
        return True

    def move_cursor(self, direction):
        """Claim the dial so it cannot wander off to another world."""
        return True

    def activate(self):
        self._leave()
        return True

    def toggle_label(self):
        return ""

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.on_green_button()
                elif e.key == pygame.K_BACKSPACE:
                    self.on_red_button()

    def _leave(self):
        back = getattr(self.manager, "alert_return", None) or "nexus"
        self.manager.alert_return = None
        self.manager.change_state(back)

    # ── update ─────────────────────────────────────────────────────────
    def update(self, dt):
        self.t += dt
        from backend.alerts import ALERT_SECONDS
        if self.t >= ALERT_SECONDS:
            # Timed out is not dismissed-by-hand, but it must still be
            # rescheduled or a missed alert would never return.
            self.on_red_button()

    # ── drawing ────────────────────────────────────────────────────────
    def draw(self, surface):
        w, h = surface.get_size()
        if self._bg is None or self._bg.get_size() != (w, h):
            self._bg = self._make_bg((w, h))
        surface.blit(self._bg, (0, 0))

        rec = self.record or {}
        # a slow pulse on the frame: alive, not flashing
        k = 0.5 + 0.5 * pygame.math.Vector2(1, 0).rotate(self.t * 90).x
        edge = pal.mix(pal.MAGENTA, pal.VOID, 0.35 + 0.35 * k)
        pygame.draw.rect(surface, edge, (0, 0, w, h), s(3))

        pal.blit_glow(surface, self.font_kicker, "DISPATCH", pal.MAGENTA,
                      (s(18), s(16)))
        age = self._age(rec)
        if age:
            g = self.font_meta.render(age, True, pal.INK_DIM)
            surface.blit(g, (w - g.get_width() - s(18), s(20)))

        y = int(h * 0.26)
        for line in self._lines:
            g = self._font.render(line, True, pal.INK)
            surface.blit(g, ((w - g.get_width()) // 2, y))
            y += self._font.get_height()

        self._button(surface, pygame.Rect(s(12), h - s(56), (w - s(36)) // 2,
                                          s(38)), "GREEN", "DONE", pal.ACID)
        self._button(surface, pygame.Rect(w // 2 + s(6), h - s(56),
                                          (w - s(36)) // 2, s(38)),
                     "RED", "LATER", pal.INK_DIM)

        from backend.alerts import ALERT_SECONDS
        left = max(0.0, ALERT_SECONDS - self.t)
        bar_w = int((w - s(24)) * (left / ALERT_SECONDS))
        pygame.draw.rect(surface, pal.mix(pal.MAGENTA, pal.VOID, 0.6),
                         (s(12), h - s(12), bar_w, s(3)))

    def _age(self, rec):
        try:
            secs = max(0, int(time.time() - rec.get("ts", time.time())))
        except Exception:                                   # noqa: BLE001
            return ""
        if secs < 90:
            return "JUST NOW"
        if secs < 3600:
            return f"{secs // 60} MIN AGO"
        if secs < 86400:
            return f"{secs // 3600} H AGO"
        return f"{secs // 86400} D AGO"

    def _button(self, surface, rect, key, label, colour):
        pygame.draw.rect(surface, pal.mix(colour, pal.VOID, 0.78), rect,
                         border_radius=s(5))
        pygame.draw.rect(surface, colour, rect, 1, border_radius=s(5))
        k = self.font_meta.render(key, True, colour)
        surface.blit(k, (rect.x + s(10), rect.y + s(6)))
        g = self.font_btn.render(label, True, pal.INK)
        surface.blit(g, (rect.right - g.get_width() - s(10), rect.y + s(9)))

    def _make_bg(self, size):
        w, h = size
        bg = pygame.Surface(size)
        bg.fill(pal.VOID)
        bg.blit(pal.grid((w, h), step=s(20), glow_every=4), (0, 0))
        bg.blit(pal.halo(s(90), pal.MAGENTA, 42), (w // 2 - s(90), -s(50)))
        return bg

    def draw_pomodoro(self, surface, time_left, mode):
        pass          # an alert never fires during a session; nothing to draw
