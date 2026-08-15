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

The line number sits in that same box, as a signage pill in its mode's
colour — green for S-Bahn, blue for Stadtbahn, violet for a bus. "LEAVE
IN 5 MIN" is only half an answer; you also have to know what you are
running for, and putting that in a different panel means reading the
screen twice.

Everything else is deliberately small: the following departures, the
delay, the platform. Reference, not the headline.

    ENCODER turn    switch between your routes
    ENCODER press   back to Nexus
    GREEN           refresh now
    RED             TRACK / untrack the headline departure
    TOGGLE          SHOW LEGS on a journey; ALL LINES on a stop board

TRACKING

The semaphore arm can point at a countdown, but only at one you have
explicitly armed with RED. It used to gauge whatever the soonest
catchable departure happened to be, which meant the arm was telling you
about a tram you had no intention of taking and you could not tell which
one it meant. Now the arm only moves for a departure you chose, and the
screen says which — the arm and the display never disagree.

A tracked departure is remembered by route and *planned* time, so it
survives a refresh, a delay, and switching routes. It clears itself when
the tram goes, is cancelled, or drops off the board.

CONFIGURATION

Kea ships with three journeys from Universität — Hauptbahnhof, Vaihingen
and Max-Planck-Institute — and needs no configuration to be useful. To
change or extend them:

    KEA_VVS_ROUTES='de:08111:6008>de:08111:6118|HAUPTBAHNHOF|5'
                    origin > destination   label       walk minutes

    KEA_VVS_ROUTES='de:08111:6118|Hbf|U6,U7|Flughafen|7'
                    stop id      label lines direction  walk minutes

Find ids, exact line names and destination spellings with:

    python3 tools/find_stop.py "your stop" --departures

With an empty board the screen says so and prints that command rather
than sitting blank — see UI_GUIDELINES §8.
"""

import datetime
import random

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from backend import vvs
from ui import palette as pal

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


# ── palette ─────────────────────────────────────────────────────────────────
# Every colour comes from ui/palette.py — see UI_GUIDELINES §1c. This
# screen used to be grey office enamel and brass, which is the one thing
# Kea is not supposed to look like.
CASE = pal.PANEL
CASE_HI = pal.EDGE
FLAP = pal.VOID
FLAP_HI = pal.PANEL_HI
SPLIT = pal.SHADOW
INK = pal.INK
INK_DIM = pal.INK_DIM
AMBER = pal.AMBER
GREEN_OK = pal.ACID
RED_GO = pal.BLOOD
BRASS = pal.CYAN            # the board's accent is a terminal, not brass

# Line badges in neon, still mapped to how the network colours them, so
# "which thing am I running for" is answered before you read the number.
PRODUCT_COLOUR = {
    "S":    pal.ACID,        # S-Bahn green
    "U":    pal.CYAN,        # Stadtbahn blue
    "TRAM": pal.AMBER,
    "BUS":  pal.MAGENTA,     # SSB bus violet
    "RE":   pal.BLOOD,
    "IC":   pal.BLOOD,
    "ICE":  pal.BLOOD,
    "ZUG":  pal.BLOOD,
    "WALK": pal.INK_FAINT,
}
BADGE_INK = pal.VOID

REFRESH = 60.0          # seconds between fetches while you are looking
# ...and while you are NOT. The arm's countdown gauge reads what this
# screen last fetched, and states only tick while they are on screen — so
# without a background cadence the gauge would only have data while you
# were watching the Board, which is exactly when you do not need an arm
# to tell you. Slower, and only the selected route, to keep it cheap:
# one ~80 KB response every five minutes rather than three every minute.
BACKGROUND_REFRESH = 300.0
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

            # Hinge and falling flap go down FIRST, character on top.
            # Drawn the other way round the seam cuts the glyph exactly at
            # its waist and an "S" reads as a "C" — which is how a board
            # full of S-Bahn lines becomes unreadable. A real split-flap
            # shows the seam around the letter, not through it.
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

            ch = self.target[i]
            if self.t[i] > 0:                     # mid-tumble: garbage
                ch = self._rng.choice(ALPHABET)
            if ch != " ":
                g = self._glyph(ch, colour)
                surf.blit(g, g.get_rect(center=cell.center))


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
        self.font_badge = pygame.font.Font(None, s(26))

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
        # (route label, planned departure isoformat) — identity that
        # survives a refetch, since Journey objects are rebuilt each time
        # and a delay moves the estimated time but never the planned one.
        self.tracked = None

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

    def on_red_button(self):
        """Arm or disarm the semaphore for the headline departure."""
        d = self.headline()
        if d is None:
            self._flash("NOTHING TO TRACK")
            return True
        key = (self._route().label, d.planned.isoformat())
        if self.tracked == key:
            self.tracked = None
            self._flash("TRACKING OFF")
        else:
            self.tracked = key
            self._flash(f"TRACKING {d.line} {d.planned:%H:%M}")
        return True

    def headline(self):
        """The departure the big number is about — the one RED arms."""
        deps, _err = self._current()
        if not deps:
            return None
        now = vvs._now()
        return next((d for d in deps if d.catchable(now)), deps[0])

    def tracked_departure(self):
        """The armed departure, or None. Read by backend/gestures.py.

        Returns None once it has gone, been cancelled, or fallen off the
        board — so the arm releases itself rather than pointing at a tram
        that no longer exists.
        """
        if not self.tracked:
            return None
        label, planned_iso = self.tracked
        deps, _err = self.rows.get(label, ([], None))
        now = vvs._now()
        for d in deps:
            if d.planned.isoformat() == planned_iso:
                if d.cancelled or d.in_min(now) < 0:
                    self.tracked = None
                    return None
                return d
        return None                    # dropped off the board entirely

    def is_tracked(self, d):
        return (self.tracked is not None and d is not None
                and self.tracked == (self._route().label,
                                     d.planned.isoformat()))

    def on_toggle(self, on):
        self.all_lines = on
        self._refresh()

    def toggle_label(self):
        r = self._route()
        # The lever means something different per mode: a journey has no
        # line filter to drop, but it does have legs worth unfolding.
        return "SHOW LEGS" if (r is not None and r.is_trip) else "ALL LINES"

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
        """With ALL LINES on, drop the filters but keep the walk time.
        Journey routes have no line filter to drop, so they pass through."""
        if not self.all_lines:
            return self.routes
        return [r if r.is_trip
                else vvs.Route(r.stop_id, label=r.label, walk_min=r.walk_min)
                for r in self.routes]

    def _refresh(self, routes=None):
        if not self.routes or self.fetching:
            return
        self.fetching = True
        self.timer = 0.0
        vvs.fetch(routes if routes is not None else self._query_routes(),
                  self._on_data)

    def background_update(self, dt):
        """Ticked by main.py even when this screen is not showing.

        Only the selected route, and only every BACKGROUND_REFRESH, so the
        arm has something recent to point at without this becoming a
        network hog. Kept separate from update() so the on-screen
        behaviour is unchanged.
        """
        self.timer += dt
        if self.timer >= BACKGROUND_REFRESH:
            r = self._route()
            self._refresh([r] if r else None)

    def _on_data(self, result):
        """Called on the worker thread — only assignment, no drawing.

        Merged rather than replaced: a background refresh fetches one
        route, and overwriting the dict would blank the other two.
        """
        self.rows.update({r.label: (deps, err) for r, deps, err in result["routes"]})
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
        now = vvs._now()
        nxt = next((d for d in deps if d.catchable(now)), None) or \
            (deps[0] if deps else None)
        self.line_flaps.set(nxt.line.upper() if nxt else "")
        # On a journey this is where you are actually going. The vehicle's
        # own terminus is useless here — the 748 to Max-Planck says
        # "OSTELSHEIM" on the front.
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
        if route.is_trip:
            # the origin's real name only exists once data has landed
            frm = deps[0].legs[0].frm if deps and deps[0].legs else "…"
            sub = f"FROM {frm.upper()[:18]}  ·  {route.walk_min} MIN WALK"
        else:
            sub = f"{route.walk_min} MIN WALK"
            if self.all_lines:
                sub += "  ·  ALL LINES"
        surface.blit(self.font_tiny.render(sub, True, INK_DIM), (s(14), s(66)))

        # ── the headline ────────────────────────────────────────────────
        box = pygame.Rect(s(12), s(84), w - s(24), s(132))
        pygame.draw.rect(surface, pal.VOID_HI, box, border_radius=s(6))
        pal.glow_rect(surface, box, pal.mix(pal.CYAN, pal.VOID, 0.45), 1,
                      radius=s(6), spread=2, alpha=45)

        catch = next((d for d in deps if d.catchable(now)), None)
        if err:
            self._headline(surface, box, "?", "NO SIGNAL", INK_DIM,
                           f"{err} — blind, not guessing")
        elif not deps:
            self._headline(surface, box, "·", "NOTHING RUNNING", INK_DIM,
                           "no departures on this route right now")
        elif catch is None:
            # Name the next one you *can't quite* make, not one that left
            # ten minutes ago — "the S1 at 15:32" is the useful sentence.
            live = [d for d in deps
                    if not d.cancelled and d.in_min(now) >= 0] \
                or [d for d in deps if not d.cancelled]
            if not live:
                self._headline(surface, box, "!", "ALL CANCELLED", RED_GO,
                               "every service ahead is cancelled")
            else:
                nxt = live[0]
                self._headline(surface, box, "!", "ALL MISSED", RED_GO,
                               "closer than your walk",
                               line=nxt.line, product=nxt.product,
                               depart_at=f"DEPARTS {nxt.estimated:%H:%M}")
        else:
            left = catch.leave_in(now)
            if left < 1:
                col, word, note = RED_GO, "GO NOW", "you are already walking"
            elif left < 3:
                col, word, note = AMBER, "LEAVE IN", "put your shoes on"
            else:
                col, word, note = GREEN_OK, "LEAVE IN", "no rush"
            delay = f"  +{catch.delay_min}" if catch.delay_min > 0 else ""
            self._headline(surface, box, str(int(left)), word, col, note,
                           unit="MIN", line=catch.line,
                           product=catch.product,
                           tracked=self.is_tracked(catch),
                           depart_at=f"DEPARTS {catch.estimated:%H:%M}{delay}")

        # ── the split-flap rows: what you are catching, and where to ────
        fy = box.bottom + s(10)
        self.line_flaps.draw(surface, s(14), fy, AMBER)
        head = catch or (deps[0] if deps else None)
        if head is not None:
            bits = []
            if head.platform:
                bits.append(("PL " if route.is_trip else "") + head.platform)
            bits.append(f"{head.estimated:%H:%M}")
            if route.is_trip:
                # what a journey knows that a departure doesn't
                bits.append(f"PL {head.platform}" if False else
                            f">{head.arrival:%H:%M}")
                bits.append(f"{head.duration_min}m")
                bits.append("DIRECT" if head.changes == 0
                            else f"{head.changes}CH")
            elif head.delay_min > 0:
                bits.append(f"+{head.delay_min}")
            g = self.font_small.render(" · ".join(bits), True, INK_DIM)
            surface.blit(g, (w - g.get_width() - s(14), fy + s(7)))
        self.dest_flaps.draw(surface, s(14), fy + s(28))

        # ── the following departures ────────────────────────────────────
        ly = fy + s(60)
        legs_mode = route.is_trip and self.all_lines and head is not None
        heading = "THIS JOURNEY" if legs_mode else "THEN"
        surface.blit(self.font_tiny.render(heading, True, INK_DIM), (s(14), ly))
        pygame.draw.line(surface, CASE_HI, (s(14) + s(74), ly + s(5)),
                         (w - s(14), ly + s(5)))
        ly += s(14)

        if legs_mode:
            for leg in head.legs[:4]:
                col = INK_DIM if leg.walking else INK
                surface.blit(self.font_row.render(f"{leg.dep:%H:%M}", True, col),
                             (s(14), ly))
                badge = "WALK" if leg.walking else leg.line[:4]
                surface.blit(self.font_row.render(badge, True,
                                                  INK_DIM if leg.walking else BRASS),
                             (s(62), ly))
                surface.blit(self.font_small.render(leg.to[:17], True, INK_DIM),
                             (s(102), ly + s(3)))
                g = self.font_small.render(f"{leg.arr:%H:%M}", True, INK_DIM)
                surface.blit(g, (w - g.get_width() - s(14), ly + s(3)))
                ly += s(22)
        else:
            shown = [d for d in deps[:6] if d is not catch][:3]
            if not shown:
                surface.blit(self.font_small.render("—", True, INK_DIM),
                             (s(14), ly))
            for d in shown:
                col = INK_DIM if d.cancelled else INK
                surface.blit(self.font_row.render(f"{d.estimated:%H:%M}", True, col),
                             (s(14), ly))
                surface.blit(self.font_row.render(d.line[:4], True, BRASS),
                             (s(62), ly))
                if route.is_trip:
                    mid = (f">{d.arrival:%H:%M}  "
                           + ("direct" if d.changes == 0 else f"{d.changes} ch"))
                else:
                    mid = d.towards[:18]
                surface.blit(self.font_small.render(mid, True, INK_DIM),
                             (s(102), ly + s(3)))
                if self.is_tracked(d):
                    pygame.draw.circle(surface, pal.ACID,
                                       (s(8), ly + s(9)), s(3))
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

    def _line_badge(self, surface, x, y, line, product):
        """A signage pill: the line number, in its mode's colour.

        This lives inside the headline box on purpose. "LEAVE IN 5 MIN"
        is only half an answer — you also have to know what you are
        running for, and having that in a different panel means reading
        the screen twice.
        """
        col = PRODUCT_COLOUR.get(product, BRASS)
        txt = self.font_badge.render(line[:5].upper(), True, BADGE_INK)
        pad = s(7)
        rect = pygame.Rect(x, y, txt.get_width() + pad * 2,
                           txt.get_height() + s(5))
        surface.blit(pal.halo(rect.h, col, 90),
                     (rect.centerx - rect.h, rect.centery - rect.h))
        pygame.draw.rect(surface, col, rect, border_radius=s(4))
        pygame.draw.rect(surface, pal.lift(col, 0.5), rect, 1,
                         border_radius=s(4))
        surface.blit(txt, (rect.x + pad, rect.y + s(2)))
        # "S1 · S" and "U6 · U" say the same thing twice; only spell the
        # mode out when the line name does not already imply it, which in
        # practice means buses.
        if (product and product not in ("WALK", "")
                and not line.upper().startswith(product)):
            g = self.font_tiny.render(product, True, INK_DIM)
            surface.blit(g, (rect.right + s(6),
                             rect.centery - g.get_height() // 2))
            return rect.width + s(6) + g.get_width()
        return rect.width

    def _headline(self, surface, box, big, word, colour, note, unit="",
                  line=None, product="", tracked=False, depart_at=""):
        cx = box.centerx
        if line:
            self._line_badge(surface, box.x + s(10), box.y + s(8),
                             line, product)
        # The arm and the screen must never disagree about what is armed.
        if tracked:
            tag = self.font_tiny.render("ARM TRACKING", True, pal.ACID)
            tw = tag.get_width() + s(10)
            tr = pygame.Rect(box.right - tw - s(8), box.y + s(9), tw, s(15))
            pygame.draw.rect(surface, pal.mix(pal.ACID, pal.VOID, 0.75), tr,
                             border_radius=s(3))
            pygame.draw.rect(surface, pal.ACID, tr, 1, border_radius=s(3))
            surface.blit(tag, (tr.x + s(5), tr.y + s(2)))
        lab = self.font_small.render(word, True, colour)
        surface.blit(lab, (cx - lab.get_width() // 2, box.y + s(12)))
        gp = pal.glow_pad(3)
        num = pal.glow_text(self.font_huge, big, colour, radius=3, strength=130)
        nx = cx - (num.get_width() - gp * 2) // 2
        if unit:
            u = self.font_unit.render(unit, True, colour)
            nx -= u.get_width() // 2
            surface.blit(u, (nx + num.get_width() - gp * 2 + s(6),
                             box.y + s(74)))
        surface.blit(num, (nx - gp, box.y + s(26) - gp))
        if depart_at:
            # LEAVE IN answers "do I stand up". This answers "what time is
            # it actually there", which is the number you say out loud and
            # the one you check against a clock on the wall.
            dt_s = self.font_row.render(depart_at, True, colour)
            surface.blit(dt_s, (cx - dt_s.get_width() // 2, box.bottom - s(38)))
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
        hint = ("RED UNTRACK" if self.tracked else "RED TRACK") + "  ·  GREEN REFRESH"
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
        bg.fill(pal.VOID)
        bg.blit(pal.grid((w, h), step=s(22), glow_every=4), (0, 0))
        head = pygame.Rect(0, 0, w, s(38))
        pygame.draw.rect(bg, pal.PANEL, head)
        pygame.draw.line(bg, BRASS, (0, s(38)), (w, s(38)), 2)
        bg.blit(pal.halo(s(30), pal.CYAN, 40), (0, s(38) - s(30)))
        pal.blit_glow(bg, self.font_title, "DEPARTURES", pal.CYAN,
                      (s(14), s(11)))
        tag = self.font_tiny.render("VVS · LIVE", True, pal.MAGENTA)
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
