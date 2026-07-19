"""
logbook_state.py
----------------
THE LOGBOOK — the machine's own history, kept in ink.

Everything Kea has quietly accumulated in ~/.kea_lifebook.json finally
gets a page of its own: garden generations, specimen batches, characters
telegraphed, focus sessions banked, dispatches delivered, boots survived.

An open ledger on a leather desk — aged paper, ruled lines, dot leaders,
a red silk bookmark. A week of focus sessions is plotted as ink bars,
and the foot of the page tracks the next milestone the machine is
working toward, so the numbers are going somewhere.

This is the one screen that gets better the longer the thing runs.
"""

import pygame
import random
import datetime

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from backend import lifebook, vitals
from backend.reminders import ReminderService

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


# ── Palette: oxblood leather, aged paper, iron-gall ink ─────────────────────
LEATHER      = (58, 30, 28)
LEATHER_DARK = (36, 18, 17)
BRASS        = (172, 136, 68)
BRASS_LIT    = (222, 188, 118)
PAPER        = (232, 219, 188)
PAPER_SHADE  = (214, 198, 164)
RULE         = (196, 178, 146)
INK          = (48, 38, 30)
INK_FAINT    = (124, 108, 86)
INK_RED      = (150, 46, 38)
RIBBON       = (168, 40, 40)

MILESTONES = {
    "pomodoros":       ([10, 25, 50, 100, 250, 500, 1000], "FOCUS SESSIONS"),
    "conservatory_gen": ([5, 10, 25, 50, 100, 250], "GARDEN GENERATIONS"),
    "chars_tx":        ([1000, 5000, 10000, 50000, 100000], "CHARACTERS SENT"),
    "boots":           ([10, 25, 50, 100, 500], "AWAKENINGS"),
}


class LogbookState(State):
    """The machine's ledger: tallies, a week of focus, and what's next."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.font_title = pygame.font.Font(None, s(27))
        self.font_row = pygame.font.Font(None, s(18))
        self.font_val = pygame.font.Font(None, s(20))
        self.font_small = pygame.font.Font(None, s(14))

        self.reminders = ReminderService.instance()
        self.time_alive = 0.0
        self.stats = []
        self.week = []
        self.milestone = None

        self.page = pygame.Rect(s(14), s(16), SCREEN_WIDTH - s(28),
                                SCREEN_HEIGHT - s(32))
        self._bg = self._build_bg()

    # ══════════════════════════════════════════════════════════════════════
    def _build_bg(self):
        """Leather desk, then the open page with its rules and foxing."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(LEATHER)
        rng = random.Random(23)
        for _ in range(500):                     # leather grain
            x, y = rng.randint(0, SCREEN_WIDTH - 1), rng.randint(0, SCREEN_HEIGHT - 1)
            surf.set_at((x, y), LEATHER_DARK if rng.random() < 0.5
                        else (68, 38, 34))

        # page with a soft drop shadow
        pygame.draw.rect(surf, (24, 12, 12), self.page.move(s(3), s(4)),
                         border_radius=s(3))
        pygame.draw.rect(surf, PAPER, self.page, border_radius=s(3))
        # foxing / age spots
        for _ in range(120):
            x = rng.randint(self.page.x + 2, self.page.right - 3)
            y = rng.randint(self.page.y + 2, self.page.bottom - 3)
            surf.set_at((x, y), PAPER_SHADE)
        for _ in range(7):                        # tea stains
            x = rng.randint(self.page.x + s(20), self.page.right - s(20))
            y = rng.randint(self.page.y + s(20), self.page.bottom - s(20))
            pygame.draw.circle(surf, PAPER_SHADE, (x, y), rng.randint(s(4), s(11)), 1)

        # brass corner protectors
        for cx, cy, dx, dy in [(self.page.x, self.page.y, 1, 1),
                               (self.page.right, self.page.y, -1, 1),
                               (self.page.x, self.page.bottom, 1, -1),
                               (self.page.right, self.page.bottom, -1, -1)]:
            pygame.draw.line(surf, BRASS, (cx, cy), (cx + dx * s(16), cy), 3)
            pygame.draw.line(surf, BRASS, (cx, cy), (cx, cy + dy * s(16)), 3)

        # header
        title = self.font_title.render("THE LOGBOOK", True, INK)
        surf.blit(title, (self.page.x + s(14), self.page.y + s(12)))
        pygame.draw.line(surf, INK, (self.page.x + s(14), self.page.y + s(38)),
                         (self.page.right - s(14), self.page.y + s(38)), 2)
        pygame.draw.line(surf, INK_FAINT, (self.page.x + s(14), self.page.y + s(41)),
                         (self.page.right - s(14), self.page.y + s(41)), 1)
        return surf

    # ══════════════════════════════════════════════════════════════════════
    def _gather(self):
        done_total = sum(1 for r in self.reminders.reminders if r["done_ts"])
        self.stats = [
            ("GARDEN GENERATIONS", lifebook.get("conservatory_gen", 1)),
            ("SPECIMEN BATCHES", lifebook.get("biolab_batch", 1)),
            ("FOCUS SESSIONS", lifebook.get("pomodoros", 0)),
            ("DISPATCHES DELIVERED", done_total),
            ("CHARACTERS SENT", lifebook.get("chars_tx", 0)),
            ("AWAKENINGS", lifebook.get("boots", 0)),
        ]
        self.week = lifebook.recent_days("focus", 7)

        # next milestone: whichever tally is closest to its next threshold
        best = None
        for key, (steps, label) in MILESTONES.items():
            val = lifebook.get(key, 0)
            nxt = next((x for x in steps if x > val), None)
            if nxt is None:
                continue
            prev = max([x for x in steps if x <= val] + [0])
            span = max(1, nxt - prev)
            progress = (val - prev) / span
            if best is None or progress > best[0]:
                best = (progress, label, val, nxt)
        self.milestone = best

    def enter(self):
        self._gather()

    def update(self, dt):
        prev = self.time_alive
        self.time_alive += dt
        if not self.stats or int(self.time_alive / 5) != int(prev / 5):
            self._gather()               # refresh the tallies every 5 s

    # ══════════════════════════════════════════════════════════════════════
    def draw(self, surface):
        surface.blit(self._bg, (0, 0))
        if not self.stats:
            self._gather()
        t = self.time_alive
        px = self.page.x + s(14)
        pw = self.page.w - s(28)

        # date, written under the rule
        stamp = self.font_small.render(
            datetime.datetime.now().strftime("KEPT SINCE FIRST LIGHT  ·  %d %B %Y").upper(),
            True, INK_FAINT)
        surface.blit(stamp, (px, self.page.y + s(46)))

        # ── the tally, with dot leaders ─────────────────────────────────
        y = self.page.y + s(68)
        for label, value in self.stats:
            lab = self.font_row.render(label, True, INK)
            val = self.font_val.render(f"{value:,}", True, INK)
            surface.blit(lab, (px, y))
            surface.blit(val, (px + pw - val.get_width(), y - s(1)))
            # dot leader between the two
            dx = px + lab.get_width() + s(5)
            dot_end = px + pw - val.get_width() - s(5)
            while dx < dot_end:
                surface.fill(INK_FAINT, (dx, y + s(11), 1, 1))
                dx += s(4)
            y += s(23)

        # ── a week of focus, in ink bars ────────────────────────────────
        chart_y = y + s(10)
        head = self.font_small.render("FOCUS, THIS WEEK", True, INK)
        surface.blit(head, (px, chart_y))
        base = chart_y + s(62)
        pygame.draw.line(surface, INK, (px, base), (px + pw, base), 1)
        peak = max([c for _d, c in self.week] + [1])
        slot = pw / max(1, len(self.week))
        for i, (day, count) in enumerate(self.week):
            bx = px + int(i * slot) + int(slot * 0.22)
            bw = max(s(6), int(slot * 0.56))
            bh = int((count / peak) * s(46)) if count else 0
            if bh:
                bar = pygame.Rect(bx, base - bh, bw, bh)
                pygame.draw.rect(surface, INK, bar)
                pygame.draw.rect(surface, lerp_color(INK, PAPER, 0.35),
                                 (bar.x, bar.y, bar.w, s(2)))
                cnt = self.font_small.render(str(count), True, INK)
                surface.blit(cnt, (bx + bw // 2 - cnt.get_width() // 2,
                                   base - bh - s(13)))
            else:
                pygame.draw.line(surface, INK_FAINT,
                                 (bx, base - 1), (bx + bw, base - 1), 1)
            initial = self.font_small.render(day.strftime("%a")[0].upper(),
                                             True, INK_FAINT)
            surface.blit(initial, (bx + bw // 2 - initial.get_width() // 2,
                                   base + s(4)))

        # ── the next milestone, in red ink ──────────────────────────────
        my = base + s(24)
        pygame.draw.line(surface, INK_FAINT, (px, my), (px + pw, my), 1)
        if self.milestone:
            progress, label, val, nxt = self.milestone
            head = self.font_small.render("WORKING TOWARD", True, INK_FAINT)
            surface.blit(head, (px, my + s(7)))
            goal = self.font_row.render(f"{nxt:,} {label}", True, INK_RED)
            surface.blit(goal, (px, my + s(21)))
            # hand-ruled progress bar
            track = pygame.Rect(px, my + s(42), pw, s(7))
            pygame.draw.rect(surface, PAPER_SHADE, track)
            pygame.draw.rect(surface, INK_RED,
                             (track.x, track.y, int(track.w * progress), track.h))
            pygame.draw.rect(surface, INK, track, 1)
            note = self.font_small.render(f"{val:,} OF {nxt:,}", True, INK_FAINT)
            surface.blit(note, (px + pw - note.get_width(), my + s(24)))
        else:
            done = self.font_row.render("EVERY MILESTONE PASSED.", True, INK_RED)
            surface.blit(done, (px, my + s(16)))

        # ── foot of the page ────────────────────────────────────────────
        foot = self.font_small.render(
            f"UP {vitals.uptime_str()}  ·  THIS VOLUME REMAINS OPEN", True, INK_FAINT)
        surface.blit(foot, (px, self.page.bottom - s(18)))

        # ── silk bookmark, hanging clear of the ledger columns ──────────
        rx = self.page.right - s(8)
        sway = int(2 * SCALE * (1 + 0.5 * (t % 4 - 2)))
        pygame.draw.polygon(surface, RIBBON, [
            (rx, self.page.y), (rx + s(13), self.page.y),
            (rx + s(13) + sway, SCREEN_HEIGHT - s(6)),
            (rx + s(6) + sway, SCREEN_HEIGHT - s(14)),
            (rx + sway, SCREEN_HEIGHT - s(6))])
        pygame.draw.line(surface, lerp_color(RIBBON, (0, 0, 0), 0.3),
                         (rx + s(13), self.page.y),
                         (rx + s(13) + sway, SCREEN_HEIGHT - s(6)), 1)

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = INK_RED if mode == "work" else (40, 110, 60)
        txt = self.font_small.render(f"{mins:02d}:{secs:02d}", True, PAPER)
        rect = txt.get_rect(topright=(self.page.right - s(48), self.page.y + s(14)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, c, box, border_radius=s(3))
        surface.blit(txt, rect)
