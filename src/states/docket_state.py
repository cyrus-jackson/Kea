"""
docket_state.py
---------------
THE DISPATCH DOCKET — one reminder at a time, big enough to read.

Reminders posted from your phone (via ntfy, see backend/reminders.py)
land here. One fills the screen; the dial pages through them; a press
marks the one you are looking at as done.

    ENCODER turn    page through open reminders
    ENCODER press   DONE — completes the one on screen
    GREEN           DONE — the same thing, on the button that always did
    RED             skip to the next without completing
    TOGGLE          include completed ones, newest first
    HOME button     back to Nexus

WHY IT WAS REBUILT

It was a board: several cards at once, aged with urgency stamps, drawn
with Font(None, 22) — which is 15 px of actual glyph on a 480 px panel,
the same type scale the transit board uses for *numbers*. Numbers you glance at. Words you read. The result was a
screen made entirely of text that could not comfortably be read, which
is a strange thing for the screen whose whole content is sentences from
your phone.

So: one card, and the message gets as much of the screen as it needs.
Fewer things visible at once is the price, and the counter (2 OF 5) plus
the pip strip pays most of it back.

AND IT LET GO OF THE DIAL

It never implemented move_cursor, so main.py fell through to _tune() and
turning the knob walked you out of the screen into another world —
UI_GUIDELINES 5 says implementing move_cursor is how a screen claims the
dial, and this one never claimed it. It does now, and press acts here
rather than going home; the HOME button still goes home.

Alerts are separate: states/alert_state.py is what interrupts you when
something arrives, and backend/alerts.py decides when it is allowed to.
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


# Stage -> colour. Urgency is the accent, not a stamp graphic.
STAGE_COLOUR = {
    "POSTED": pal.CYAN,
    "BOARDING": pal.AMBER,
    "FINAL CALL": pal.MAGENTA,
    "OVERDUE": pal.BLOOD,
}

# Pygame's font size argument is NOT pixel height: Font(None, 40) renders
# only 27 px tall. The old card used Font(None, 22) — 15 px of actual
# glyph, which is what "I can hardly read it" meant. This ladder is set
# from measured heights, not from nominal numbers, and starts high enough
# to use the card: 80 gives 55 px, twice the old screen's title.
MSG_SIZES = (80, 68, 58, 48, 40, 32, 26)
MAX_LINES = 6


class DocketState(State):
    """One reminder, readable, with the dial paging through them."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()
        self.font_title = pygame.font.Font(None, s(24))
        self.font_stage = pygame.font.Font(None, s(19))
        self.font_meta = pygame.font.Font(None, s(17))
        self.font_count = pygame.font.Font(None, s(30))
        self.font_hint = pygame.font.Font(None, s(15))
        self._msg_fonts = {n: pygame.font.Font(None, s(n)) for n in MSG_SIZES}

        self.service = ReminderService.instance()
        self.sel = 0
        self.show_done = False
        self.t = 0.0
        self.flash = ""
        self.flash_t = 0.0
        self._laid_for = None
        self._lines = []
        self._font = self._msg_fonts[MSG_SIZES[-1]]
        self._bg = None

    # ── data ───────────────────────────────────────────────────────────
    def items(self):
        try:
            if self.show_done:
                with ReminderService._lock:
                    all_r = [dict(r) for r in self.service.reminders]
                return sorted(all_r, key=lambda r: -r["ts"])
            return self.service.active()
        except Exception:                                   # noqa: BLE001
            return []

    def current(self):
        it = self.items()
        if not it:
            return None
        self.sel = max(0, min(len(it) - 1, self.sel))
        return it[self.sel]

    # ── lifecycle ──────────────────────────────────────────────────────
    def enter(self):
        self.t = 0.0
        self.show_done = bool(getattr(self.manager, "toggle_on", False))
        self.sel = 0
        self._laid_for = None

    # ── controls ───────────────────────────────────────────────────────
    def move_cursor(self, direction):
        """Claims the dial. Without this main.py tunes to another world."""
        it = self.items()
        if not it:
            return True
        self.sel = (self.sel + (1 if direction > 0 else -1)) % len(it)
        self._laid_for = None
        return True

    def activate(self):
        """Press = done. Stays on the screen; HOME goes home."""
        self._complete()
        return True

    def on_green_button(self):
        self._complete()
        return True

    def on_red_button(self):
        """Skip without completing — look at the next one."""
        self.move_cursor(1)
        self._flash("NEXT")
        return True

    def on_toggle(self, on):
        self.show_done = on
        self.sel = 0
        self._laid_for = None

    def toggle_label(self):
        return "SHOW DONE"

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_g, pygame.K_RETURN, pygame.K_SPACE):
                    self._complete()
                elif e.key in (pygame.K_RIGHT, pygame.K_DOWN):
                    self.move_cursor(1)
                elif e.key in (pygame.K_LEFT, pygame.K_UP):
                    self.move_cursor(-1)

    def _complete(self):
        rec = self.current()
        if rec is None or rec.get("done_ts") is not None:
            self._flash("NOTHING TO STAMP")
            return
        try:
            self.service.complete(rec["id"])
            from backend import alerts
            alerts.instance().completed(rec["id"])
        except Exception:                                   # noqa: BLE001
            pass
        self._flash("DELIVERED")
        self.sel = max(0, self.sel - 1)
        self._laid_for = None

    def _flash(self, text):
        self.flash, self.flash_t = text, 1.4

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

    def _layout(self, text):
        """Start at 40 px and only step down when the wrap will not fit.

        The old screen picked one size and truncated. Fitting the size to
        the message means a short reminder is enormous and a long one is
        still readable, rather than everything being small so the worst
        case fits.
        """
        if self._laid_for == text:
            return
        self._laid_for = text
        width = SCREEN_WIDTH - s(40)
        room = int(SCREEN_HEIGHT * 0.40)
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

        items = self.items()
        rec = self.current()
        if rec is None:
            self._draw_empty(surface)
            return

        text = rec.get("text", "") or "(no text)"
        self._layout(text)
        done = rec.get("done_ts") is not None
        age = max(0.0, time.time() - rec.get("ts", time.time()))
        stage = "DELIVERED" if done else stage_for(age)
        accent = pal.ACID if done else STAGE_COLOUR.get(stage, pal.CYAN)

        # stage + position
        pal.blit_glow(surface, self.font_stage, stage, accent, (s(16), s(46)))
        cnt = self.font_count.render(f"{self.sel + 1}/{len(items)}", True,
                                     pal.INK_DIM)
        surface.blit(cnt, (w - cnt.get_width() - s(16), s(42)))

        card = pygame.Rect(s(10), s(70), w - s(20), int(h * 0.52))
        pygame.draw.rect(surface, pal.VOID_HI, card, border_radius=s(6))
        pal.glow_rect(surface, card, pal.mix(accent, pal.VOID, 0.5), 1,
                      radius=s(6), spread=2, alpha=50)
        pygame.draw.rect(surface, accent, (card.x, card.y, s(4), card.h),
                         border_radius=s(2))

        y = card.y + (card.h - len(self._lines) * self._font.get_height()) // 2
        for line in self._lines:
            g = self._font.render(line, True,
                                  pal.INK_DIM if done else pal.INK)
            surface.blit(g, (card.x + s(16), y))
            y += self._font.get_height()

        m = self.font_meta.render(self._age_text(age), True, pal.INK_DIM)
        surface.blit(m, (card.x + s(16), card.bottom - s(22)))

        self._draw_pips(surface, items, card.bottom + s(12))

        if self.flash_t > 0:
            f = self.font_stage.render(self.flash, True, pal.ACID)
            surface.blit(f, ((w - f.get_width()) // 2, card.bottom + s(30)))

        hint = "PRESS DONE  ·  DIAL PAGES  ·  RED SKIP"
        g = self.font_hint.render(hint, True, pal.INK_DIM)
        surface.blit(g, ((w - g.get_width()) // 2, h - s(34)))

    def _draw_pips(self, surface, items, y):
        """One pip per reminder, so the card still says how many and where.

        Position was the thing a single-card view loses; this is what buys
        it back without spending the space that made the card readable.
        """
        n = len(items)
        if n <= 1:
            return
        gap = s(9)
        total = n * gap
        x = (surface.get_width() - total) // 2
        for i, r in enumerate(items):
            done = r.get("done_ts") is not None
            st = stage_for(max(0.0, time.time() - r.get("ts", time.time())))
            c = pal.ACID if done else STAGE_COLOUR.get(st, pal.CYAN)
            if i == self.sel:
                pygame.draw.circle(surface, c, (x + i * gap + s(3), y), s(4))
            else:
                pygame.draw.circle(surface, pal.mix(c, pal.VOID, 0.55),
                                   (x + i * gap + s(3), y), s(2))

    def _age_text(self, secs):
        secs = int(secs)
        if secs < 90:
            return "POSTED JUST NOW"
        if secs < 3600:
            return f"POSTED {secs // 60} MIN AGO"
        if secs < 86400:
            return f"POSTED {secs // 3600} HOURS AGO"
        return f"POSTED {secs // 86400} DAYS AGO"

    def _draw_empty(self, surface):
        w, h = surface.get_size()
        cy = int(h * 0.40)
        surface.blit(pal.halo(s(60), pal.ACID, 60), (w // 2 - s(60), cy - s(60)))
        pygame.draw.circle(surface, pal.mix(pal.ACID, pal.VOID, 0.35),
                           (w // 2, cy), s(34))
        pygame.draw.circle(surface, pal.ACID, (w // 2, cy), s(34), 2)
        g = pal.glow_text(self._msg_fonts[MSG_SIZES[1]], "ALL CLEAR", pal.ACID)
        surface.blit(g, ((w - g.get_width()) // 2, cy + s(48)))
        sub = self.font_meta.render("NOTHING OWED", True, pal.INK_DIM)
        surface.blit(sub, ((w - sub.get_width()) // 2, cy + s(84)))
        how = self.font_hint.render(f"POST TO  ntfy.sh/{TOPIC}", True, pal.CYAN)
        surface.blit(how, ((w - how.get_width()) // 2, h - s(44)))

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
        surface.blit(g, (surface.get_width() - g.get_width() - s(16),
                         surface.get_height() - s(32)))
