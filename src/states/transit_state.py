"""
transit_state.py
----------------
THE BOARD — a split-flap departure board wired to real trams.

Kea already had two departure boards that departed from nowhere: the
Aerodrome tows banners across the sky, Bay 94 lands the same freighter on
a loop. This is the same idiom pointed at the actual Stuttgart network,
so the clacking means something.

The screen answers ONE question, in the largest type it can manage:

    DO I NEED TO STAND UP?

Not "when is the next tram" — a phone does that better, and by the time
you have unlocked it you could have walked to the stop. What you cannot
get from a phone without asking is the number that already accounts for
the walk. A tram six minutes out is not six minutes away if the platform
is a five minute walk: it is one minute away, and it is about to become
a sprint. So the big number is LEAVE IN, it counts the walk, and it goes
amber then red as it runs out.

Everything else on the board is deliberately small: the following two
departures, the delay, the platform. Reference, not the headline.

    ENCODER turn    switch between your configured routes
    ENCODER press   back to Nexus
    GREEN           refresh now
    TOGGLE          ALL LINES — ignore the line filter and show
                    everything leaving this stop

CONFIGURATION

    KEA_VVS_ROUTES='de:08111:6118|Hbf|U6,U7|Flughafen|7'
                    stop id      label lines direction  walk minutes

Find the ids, the exact line names and the destination spellings with:

    python3 tools/find_stop.py "your stop" --departures

Unconfigured, the screen says so and tells you that command rather than
sitting blank — see UI_GUIDELINES §8.
"""

import datetime
import random

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from backend import vvs

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


# ── palette: an enamelled station board ─────────────────────────────────────
CASE = (26, 27, 32)
CASE_HI = (44, 46, 54)
FLAP = (18, 19, 23)
FLAP_HI = (34, 36, 42)
SPLIT = (10, 10, 13)
INK = (238, 236, 228)
INK_DIM = (128, 132, 142)
AMBER = (250, 186, 60)
GREEN_OK = (120, 214, 132)
RED_GO = (232, 88, 72)
BRASS = (168, 138, 74)

REFRESH = 60.0          # seconds between fetches
FLAP_TIME = 0.42        # how long a character tumbles when it changes
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -:/."


class Flaps:
    """A row of split-flap cells.

    Only cells whose character actually changed tumble, and only for
    FLAP_TIME. A board where every cell animates every frame would eat
    the Pi's budget for nothing — the charm is in the few that move.
    """

    def __init__(self, font, cells, cw, ch):
        self.font = font
        self.n = cells
        self.cw = cw
        self.ch = ch
        self.text = " " * cells
        self.target = " " * cells
        self.t = [0.0] * cells
        self._rng = random.Random(7)
        self._glyphs = {}

    def set(self, text):
        text = (text or "")[:self.n].ljust(self.n)
        if text == self.target:
            return
        for i, (a, b) in enumerate(zip(self.target, text)):
            if a != b:
                self.t[i] = FLAP_TIME
        self.target = text

    def update(self, dt):
        for i in range(self.n):
            if self.t[i] > 0:
                self.t[i] = max(0.0, self.t[i] - dt)
        self.text = self.target

    def _glyph(self, ch, colour):
        key = (ch, colour)
        g = self._glyphs.get(key)
        if g is None:
            g = self.font.render(ch, True, colour)
            if len(self._glyphs) > 300:
                self._glyphs.clear()
            self._glyphs[key] = g
        return g

    def draw(self, surf, x, y, colour=INK):
        for i in range(self.n):
            cx = x + i * (self.cw + s(2))
            cell = pygame.Rect(cx, y, self.cw, self.ch)
            pygame.draw.rect(surf, FLAP, cell, border_radius=s(2))
            pygame.draw.rect(surf, FLAP_HI, cell, 1, border_radius=s(2))

            ch = self.target[i]
            if self.t[i] > 0:                     # mid-tumble: garbage
                ch = self._rng.choice(ALPHABET)
            if ch != " ":
                g = self._glyph(ch, colour)
                surf.blit(g, g.get_rect(center=cell.center))

            # the hinge line across the middle, which is the whole look
            my = cell.centery
            pygame.draw.line(surf, SPLIT, (cell.x, my), (cell.right, my), 1)
            if self.t[i] > 0:                     # the flap falling
                k = self.t[i] / FLAP_TIME
                h = int(self.ch * 0.5 * k)
                if h > 0:
                    pygame.draw.rect(surf, FLAP_HI,
                                     (cell.x, my, self.cw, h))
                    pygame.draw.line(surf, SPLIT, (cell.x, my + h),
                                     (cell.right, my + h), 1)


class TransitState(State):
    """Real departures, and the only number that matters: LEAVE IN."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()
        self.font_title = pygame.font.Font(None, s(24))
        self.font_huge = pygame.font.Font(None, s(96))
        self.font_unit = pygame.font.Font(None, s(22))
        self.font_row = pygame.font.Font(None, s(19))
        self.font_small = pygame.font.Font(None, s(14))
        self.font_tiny = pygame.font.Font(None, s(12))
        self.font_flap = pygame.font.Font(None, s(20))

        self.routes = vvs.routes_from_env()
        self.idx = 0
        self.rows = {}              # label -> (departures, error)
        self.fetched = None
        self.fetching = False
        self.timer = REFRESH        # force a fetch on first enter
        self.all_lines = False
        self.msg = ""
        self.msg_t = 0.0
        self.t = 0.0

        # Cells are counted from the real panel width rather than picked
        # by eye: hardcoding 16 ran the destination off the edge of a
        # 320 px screen and cut "FLUGHAFEN/MESSE" mid-word. The line badge
        # shares a row with the platform; the destination gets the full
        # width to itself, which is the only way 15 characters fit.
        avail = SCREEN_WIDTH - s(28)
        dcw = s(15)
        self.line_flaps = Flaps(self.font_flap, 4, s(17), s(24))
        self.dest_flaps = Flaps(self.font_flap,
                                max(6, avail // (dcw + s(2))), dcw, s(22))
        self._bg = None

    # ── lifecycle ──────────────────────────────────────────────────────────
    def enter(self):
        self.t = 0.0
        self.all_lines = bool(getattr(self.manager, "toggle_on", False))
        if self.timer >= REFRESH:
            self._refresh()

    # ── controls ───────────────────────────────────────────────────────────
    def move_cursor(self, direction):
        if len(self.routes) > 1:
            self.idx = (self.idx + (1 if direction > 0 else -1)) % len(self.routes)
            self._flash(self._route().label.upper())
        return True

    def activate(self):
        return False                # press = home

    def on_green_button(self):
        self._refresh()
        self._flash("REFRESHING")
        return True

    def on_toggle(self, on):
        self.all_lines = on
        self._refresh()

    def toggle_label(self):
        return "ALL LINES"

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.move_cursor(1 if e.key == pygame.K_RIGHT else -1)
                elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.on_green_button()

    # ── data ───────────────────────────────────────────────────────────────
    def _route(self):
        return self.routes[self.idx % len(self.routes)] if self.routes else None

    def _query_routes(self):
        """With ALL LINES on, drop the filters but keep the walk time."""
        if not self.all_lines:
            return self.routes
        return [vvs.Route(r.stop_id, label=r.label, walk_min=r.walk_min)
                for r in self.routes]

    def _refresh(self):
        if not self.routes or self.fetching:
            return
        self.fetching = True
        self.timer = 0.0
        vvs.fetch(self._query_routes(), self._on_data)

    def _on_data(self, result):
        """Called on the worker thread — only assignment, no drawing."""
        self.rows = {r.label: (deps, err) for r, deps, err in result["routes"]}
        self.fetched = result.get("fetched")
        self.fetching = False

    def _current(self):
        r = self._route()
        if r is None:
            return [], None
        return self.rows.get(r.label, ([], None))

    def _flash(self, text):
        self.msg = text
        self.msg_t = 1.6

    # ── update ─────────────────────────────────────────────────────────────
    def update(self, dt):
        self.t += dt
        self.timer += dt
        if self.msg_t > 0:
            self.msg_t = max(0.0, self.msg_t - dt)
        if self.timer >= REFRESH:
            self._refresh()

        deps, _err = self._current()
        nxt = deps[0] if deps else None
        self.line_flaps.set(nxt.line.upper() if nxt else "")
        self.dest_flaps.set(nxt.towards.upper() if nxt else "")
        self.line_flaps.update(dt)
        self.dest_flaps.update(dt)

    # ── drawing ────────────────────────────────────────────────────────────
    def draw(self, surface):
        if self._bg is None or self._bg.get_size() != surface.get_size():
            self._bg = self._make_bg(surface.get_size())
        surface.blit(self._bg, (0, 0))
        w, h = surface.get_size()

        if not self.routes:
            self._draw_unconfigured(surface)
            return

        route = self._route()
        deps, err = self._current()
        now = vvs._now()

        # stop name + which of your routes this is
        t = self.font_title.render(route.label.upper()[:20], True, INK)
        surface.blit(t, (s(14), s(46)))
        if len(self.routes) > 1:
            pip_x = w - s(14) - len(self.routes) * s(9)
            for i in range(len(self.routes)):
                c = AMBER if i == self.idx else (60, 62, 70)
                pygame.draw.circle(surface, c,
                                   (pip_x + i * s(9), s(54)), s(3))
        sub = f"{route.walk_min} MIN WALK"
        if self.all_lines:
            sub += "  ·  ALL LINES"
        surface.blit(self.font_tiny.render(sub, True, INK_DIM), (s(14), s(66)))

        # ── the headline ────────────────────────────────────────────────
        box = pygame.Rect(s(12), s(84), w - s(24), s(132))
        pygame.draw.rect(surface, (14, 15, 18), box, border_radius=s(6))
        pygame.draw.rect(surface, CASE_HI, box, 1, border_radius=s(6))

        catch = next((d for d in deps if d.catchable(now)), None)
        if err:
            self._headline(surface, box, "?", "NO SIGNAL", INK_DIM,
                           f"{err} — blind, not guessing")
        elif not deps:
            self._headline(surface, box, "·", "NOTHING RUNNING", INK_DIM,
                           "no departures on this route right now")
        elif catch is None:
            self._headline(surface, box, "!", "ALL MISSED", RED_GO,
                           "next one is closer than your walk")
        else:
            left = catch.leave_in(now)
            if left < 1:
                col, word, note = RED_GO, "GO NOW", "you are already walking"
            elif left < 3:
                col, word, note = AMBER, "LEAVE IN", "put your shoes on"
            else:
                col, word, note = GREEN_OK, "LEAVE IN", "no rush"
            self._headline(surface, box, str(int(left)), word, col, note,
                           unit="MIN")

        # ── the split-flap rows: what you are catching, and where to ────
        fy = box.bottom + s(10)
        self.line_flaps.draw(surface, s(14), fy, AMBER)
        head = catch or (deps[0] if deps else None)
        if head is not None:
            bits = []
            if head.platform:
                bits.append(head.platform)
            bits.append(f"{head.estimated:%H:%M}")
            if head.delay_min > 0:
                bits.append(f"+{head.delay_min}")
            g = self.font_small.render("  ·  ".join(bits), True, INK_DIM)
            surface.blit(g, (w - g.get_width() - s(14), fy + s(7)))
        self.dest_flaps.draw(surface, s(14), fy + s(28))

        # ── the following departures ────────────────────────────────────
        ly = fy + s(60)
        surface.blit(self.font_tiny.render("THEN", True, INK_DIM), (s(14), ly))
        pygame.draw.line(surface, CASE_HI, (s(48), ly + s(5)),
                         (w - s(14), ly + s(5)))
        ly += s(14)
        shown = [d for d in deps[:6] if d is not catch][:3]
        if not shown:
            surface.blit(self.font_small.render("—", True, INK_DIM), (s(14), ly))
        for d in shown:
            col = INK_DIM if d.cancelled else INK
            surface.blit(self.font_row.render(f"{d.estimated:%H:%M}", True, col),
                         (s(14), ly))
            surface.blit(self.font_row.render(d.line[:4], True, BRASS), (s(62), ly))
            surface.blit(self.font_small.render(d.towards[:18], True, INK_DIM),
                         (s(98), ly + s(3)))
            if d.cancelled:
                tag, tc = "CANCELLED", RED_GO
            elif d.delay_min > 0:
                tag, tc = f"+{d.delay_min}", AMBER
            else:
                tag, tc = f"{d.leave_in(now):+.0f}", INK_DIM
            g = self.font_small.render(tag, True, tc)
            surface.blit(g, (w - g.get_width() - s(14), ly + s(3)))
            ly += s(22)

        self._draw_footer(surface, now)

    def _headline(self, surface, box, big, word, colour, note, unit=""):
        cx = box.centerx
        lab = self.font_small.render(word, True, colour)
        surface.blit(lab, (cx - lab.get_width() // 2, box.y + s(10)))
        num = self.font_huge.render(big, True, colour)
        nx = cx - num.get_width() // 2
        if unit:
            u = self.font_unit.render(unit, True, colour)
            nx -= u.get_width() // 2
            surface.blit(u, (nx + num.get_width() + s(6),
                             box.y + s(74)))
        surface.blit(num, (nx, box.y + s(26)))
        n = self.font_tiny.render(note[:44], True, INK_DIM)
        surface.blit(n, (cx - n.get_width() // 2, box.bottom - s(20)))

    def _draw_footer(self, surface, now):
        """Kept above the bottom strip, which belongs to the toggle chip."""
        w, h = surface.get_size()
        y = h - s(40)
        pygame.draw.line(surface, CASE_HI, (s(12), y), (w - s(12), y))
        if self.fetching:
            age = "UPDATING..."
        elif self.fetched:
            secs = int((now - self.fetched).total_seconds())
            age = f"UPDATED {secs}s AGO" if secs < 90 else "STALE"
        else:
            age = "NO DATA YET"
        surface.blit(self.font_tiny.render(age, True, INK_DIM), (s(14), y + s(8)))
        hint = "GREEN REFRESH" + ("  ·  DIAL: ROUTE" if len(self.routes) > 1 else "")
        g = self.font_tiny.render(hint, True, INK_DIM)
        surface.blit(g, (w - g.get_width() - s(14), y + s(8)))
        if self.msg_t > 0:
            m = self.font_small.render(self.msg, True, AMBER)
            surface.blit(m, (w // 2 - m.get_width() // 2, y - s(16)))

    def _draw_unconfigured(self, surface):
        """Say what is missing and exactly how to fix it."""
        w, h = surface.get_size()
        lines = [
            (self.font_title, "NO ROUTES SET", AMBER),
            (self.font_small, "", INK),
            (self.font_small, "Find your stop:", INK),
            (self.font_tiny, "python3 tools/find_stop.py", BRASS),
            (self.font_tiny, '    "your stop" --departures', BRASS),
            (self.font_small, "", INK),
            (self.font_small, "Then set:", INK),
            (self.font_tiny, "KEA_VVS_ROUTES=", BRASS),
            (self.font_tiny, "  'stopid|Home|U6,U7|Flughafen|7'", BRASS),
            (self.font_small, "", INK),
            (self.font_tiny, "stop · label · lines · direction · walk", INK_DIM),
        ]
        y = s(112)
        for font, text, col in lines:
            if text:
                g = font.render(text, True, col)
                surface.blit(g, (s(20), y))
                y += g.get_height() + s(7)
            else:
                y += s(10)                    # a deliberate blank line

    def _make_bg(self, size):
        w, h = size
        bg = pygame.Surface(size)
        bg.fill(CASE)
        for y in range(0, h, s(4)):          # brushed enamel
            pygame.draw.line(bg, (CASE[0] + 3, CASE[1] + 3, CASE[2] + 3),
                             (0, y), (w, y))
        head = pygame.Rect(0, 0, w, s(38))
        pygame.draw.rect(bg, (16, 17, 20), head)
        pygame.draw.line(bg, BRASS, (0, s(38)), (w, s(38)), 2)
        title = self.font_title.render("DEPARTURES", True, INK)
        bg.blit(title, (s(14), s(11)))
        tag = self.font_tiny.render("VVS · LIVE", True, BRASS)
        bg.blit(tag, (w - tag.get_width() - s(14), s(16)))
        for cx in (s(8), w - s(8)):          # case screws
            for cy in (s(19), h - s(9)):
                pygame.draw.circle(bg, CASE_HI, (cx, cy), s(3))
        return bg

    def draw_pomodoro(self, surface, time_left, mode):
        m, sec = divmod(max(0, int(time_left)), 60)
        col = AMBER if mode == "work" else GREEN_OK
        g = self.font_small.render(f"{m:02d}:{sec:02d}", True, col)
        surface.blit(g, (surface.get_width() - g.get_width() - s(14), s(46)))
