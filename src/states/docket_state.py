"""
docket_state.py
---------------
THE DISPATCH DOCKET — reminders as paper, guilt as patina.

Reminders posted from your phone (via ntfy, see backend/reminders.py)
arrive down a pneumatic tube as paper docket cards. Cards age through
urgency stamps — POSTED, BOARDING, FINAL CALL, OVERDUE (blinking) —
and the oldest waits in the NOW SERVING slot. The GREEN hardware
button slams a DELIVERED stamp onto it. Done is satisfying; undone
is visible. That's the whole trick.

When the docket is empty, the office sleeps and shows the ntfy
address to post to.
"""

import pygame
import random
import math
import time
import datetime

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from backend.reminders import ReminderService, stage_for, TOPIC

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


BG        = (17, 13, 10)
WOOD      = (42, 31, 21)
WOOD_DARK = (30, 22, 15)
BRASS     = (152, 120, 58)
PAPER     = (233, 217, 178)
PAPER_OLD = (214, 194, 150)
INK       = (62, 45, 28)
INK_FAINT = (130, 110, 84)
STAMP_RED = (186, 48, 36)
DONE_GRN  = (98, 168, 88)

STAGE_COLORS = {
    "POSTED":     (110, 150, 120),
    "BOARDING":   (170, 140, 70),
    "FINAL CALL": (216, 140, 40),
    "OVERDUE":    (200, 60, 45),
}


def age_str(age_s):
    if age_s < 3600:
        return f"{int(age_s // 60)}M AGO"
    if age_s < 86400:
        return f"{int(age_s // 3600)}H AGO"
    return f"{int(age_s // 86400)}D AGO"


class DocketState(State):
    """Dispatch-office reminder board with a stampable NOW SERVING slot."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.service = ReminderService.instance()

        self.font_title = pygame.font.Font(None, s(26))
        self.font_card  = pygame.font.Font(None, s(22))
        self.font_small = pygame.font.Font(None, s(16))
        self.font_stamp = pygame.font.Font(None, s(34))

        self.time_alive = 0.0
        self._last_count = self.service.count()
        self.show_done = False        # toggle flips to the completed pile

        # animations
        self.capsule = None          # y progress of arriving tube capsule
        self.stamp_anim = None       # {"t": 0.., "text": card text}
        self._stamp_surf = None

        self._bg = self._build_bg()

    # ══════════════════════════════════════════════════════════════════════
    def _build_bg(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(BG)
        rng = random.Random(21)
        # wood paneling with grain
        pygame.draw.rect(surf, WOOD, (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        for _ in range(60):
            x = rng.randint(0, SCREEN_WIDTH - 1)
            pygame.draw.line(surf, WOOD_DARK, (x, 0), (x, SCREEN_HEIGHT), 1)
        for gy in range(0, SCREEN_HEIGHT, s(96)):        # plank seams
            pygame.draw.line(surf, (20, 15, 10), (0, gy), (SCREEN_WIDTH, gy), 2)

        # header plate
        plate = pygame.Rect(s(10), s(8), SCREEN_WIDTH - s(20), s(40))
        pygame.draw.rect(surf, WOOD_DARK, plate, border_radius=s(6))
        pygame.draw.rect(surf, BRASS, plate, 2, border_radius=s(6))
        t = self.font_title.render("DISPATCH DOCKET", True, PAPER)
        surf.blit(t, (plate.x + s(12), plate.y + s(6)))

        # pneumatic tube along the right edge
        tx = SCREEN_WIDTH - s(13)
        pygame.draw.line(surf, BRASS, (tx - s(5), s(52)), (tx - s(5), SCREEN_HEIGHT - s(30)), 2)
        pygame.draw.line(surf, BRASS, (tx + s(5), s(52)), (tx + s(5), SCREEN_HEIGHT - s(30)), 2)
        for ty in range(s(70), SCREEN_HEIGHT - s(40), s(50)):   # tube collars
            pygame.draw.rect(surf, BRASS, (tx - s(7), ty, s(14), s(5)), border_radius=2)
        return surf

    def _wrap(self, text, font, max_w, max_lines):
        words, lines, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= max_w:
                cur = test
            else:
                lines.append(cur)
                cur = w
                if len(lines) == max_lines:
                    break
        if cur and len(lines) < max_lines:
            lines.append(cur)
        if len(lines) == max_lines and len(" ".join(lines)) < len(text):
            lines[-1] = lines[-1][: max(1, len(lines[-1]) - 1)] + "…"
        return lines

    # ══════════════════════════════════════════════════════════════════════
    # ── toggle: flip the board over to what you've already done ─────────
    def on_toggle(self, on):
        self.show_done = on

    def toggle_label(self):
        return "SHOW DONE"

    def on_green_button(self):
        """Main routes the green hardware button here. True = consumed."""
        if self.stamp_anim is None and self.service.count() > 0:
            text = self.service.complete_oldest()
            if text:
                self.stamp_anim = {"t": 0.0, "text": text}
                self._stamp_surf = None
            return True
        return False

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_g:
                self.on_green_button()          # desktop stand-in for green

    def update(self, dt):
        self.time_alive += dt
        self.service.update(dt)

        count = self.service.count()
        if count > self._last_count:            # new dispatch -> capsule drop
            self.capsule = 0.0
        self._last_count = count

        if self.capsule is not None:
            self.capsule += dt * 1.4
            if self.capsule >= 1.2:
                self.capsule = None

        if self.stamp_anim is not None:
            self.stamp_anim["t"] += dt
            if self.stamp_anim["t"] > 1.1:
                self.stamp_anim = None

    # ══════════════════════════════════════════════════════════════════════
    def draw(self, surface):
        surface.blit(self._bg, (0, 0))
        t = self.time_alive
        now = time.time()
        active = self.service.active()

        # header count line (under the title, inside the plate)
        info = self.font_small.render(
            f"{len(active)} OPEN  ·  {self.service.done_today()} DONE TODAY",
            True, BRASS)
        surface.blit(info, (s(24), s(32)))

        # capsule arriving down the tube
        if self.capsule is not None:
            cy = s(56) + min(1.0, self.capsule) * (SCREEN_HEIGHT - s(120))
            tx = SCREEN_WIDTH - s(13)
            pygame.draw.rect(surface, PAPER,
                             (tx - s(4), int(cy), s(8), s(18)), border_radius=s(4))
            pygame.draw.rect(surface, BRASS,
                             (tx - s(4), int(cy), s(8), s(18)), 1, border_radius=s(4))

        card_w = SCREEN_WIDTH - s(44)

        # ── toggle view: the completed pile, newest first ───────────────
        if self.show_done:
            done = sorted([r for r in self.service.reminders if r["done_ts"]],
                          key=lambda r: r["done_ts"], reverse=True)
            lbl = self.font_small.render(
                f"DELIVERED · {len(done)} TOTAL", True, DONE_GRN)
            surface.blit(lbl, (s(14), s(64)))
            if not done:
                none = self.font_card.render("NOTHING STAMPED YET.", True, PAPER_OLD)
                surface.blit(none, ((SCREEN_WIDTH - none.get_width()) // 2,
                                    int(SCREEN_HEIGHT * 0.42)))
                return
            for i, r in enumerate(done[:6]):
                card = pygame.Rect(s(12), s(82) + i * s(52), card_w, s(44))
                self._draw_card(surface, card, r["text"], None, now, big=False)
                # struck through, with the time it was cleared
                pygame.draw.line(surface, INK_FAINT,
                                 (card.x + s(16), card.centery - s(4)),
                                 (card.right - s(52), card.centery - s(4)), 1)
                when = datetime.datetime.fromtimestamp(r["done_ts"]).strftime("%H:%M")
                ts = self.font_small.render(when, True, DONE_GRN)
                surface.blit(ts, (card.right - ts.get_width() - s(8),
                                  card.bottom - s(16)))
            return

        if not active and self.stamp_anim is None:
            self._draw_empty(surface, t)
            return

        # ── NOW SERVING slot ─────────────────────────────────────────────
        slot = pygame.Rect(s(12), s(64), card_w, s(126))
        lbl = self.font_small.render("NOW SERVING", True, BRASS)
        surface.blit(lbl, (slot.x + s(2), slot.y - s(14)))

        if self.stamp_anim is not None:
            # keep showing the just-stamped card during the animation
            self._draw_card(surface, slot, self.stamp_anim["text"], None, now, big=True)
            self._draw_stamp(surface, slot)
            rest = active
        else:
            self._draw_card(surface, slot, active[0]["text"], active[0], now, big=True)
            hint = self.font_small.render("GREEN BTN · STAMP DONE", True, BRASS)
            surface.blit(hint, (slot.right - hint.get_width() - s(4),
                                slot.bottom + s(5)))
            rest = active[1:]

        # ── the queue ────────────────────────────────────────────────────
        qy = slot.bottom + s(22)
        if rest:
            lbl = self.font_small.render(f"IN THE RACK · {len(rest)}", True, BRASS)
            surface.blit(lbl, (s(14), qy - s(14)))
        for i, r in enumerate(rest[:4]):
            card = pygame.Rect(s(12) + s(3) * (i % 2), qy + i * s(52), card_w - s(6), s(44))
            self._draw_card(surface, card, r["text"], r, now, big=False)
        if len(rest) > 4:
            more = self.font_small.render(f"+ {len(rest) - 4} MORE BELOW THE RACK",
                                          True, INK_FAINT)
            surface.blit(more, (s(14), qy + 4 * s(52) + s(4)))

        # footer
        foot = self.font_small.render(
            datetime.datetime.now().strftime("%H:%M  ·  THE OFFICE NEVER CLOSES"),
            True, (110, 90, 66))
        surface.blit(foot, ((SCREEN_WIDTH - foot.get_width()) // 2,
                            SCREEN_HEIGHT - s(20)))

    def _draw_card(self, surface, rect, text, reminder, now, big):
        age = (now - reminder["ts"]) if reminder else 0
        stage = stage_for(age) if reminder else "POSTED"
        col = STAGE_COLORS[stage]
        paper = PAPER if age < 4 * 3600 else PAPER_OLD   # old paper yellows

        # drop shadow + paper
        pygame.draw.rect(surface, (10, 8, 6), rect.move(s(3), s(3)), border_radius=s(4))
        pygame.draw.rect(surface, paper, rect, border_radius=s(4))
        pygame.draw.rect(surface, lerp_color(paper, INK, 0.35), rect, 1, border_radius=s(4))
        # punched holes on the left edge (it's filed, after all)
        for hy in range(rect.y + s(10), rect.bottom - s(6), s(14)):
            pygame.draw.circle(surface, WOOD, (rect.x + s(7), hy), s(2))

        if big:
            # try the big font first; if the text wouldn't fit in 3 lines,
            # drop to the small font with 4 lines — never truncate the
            # reminder you're supposed to act on
            font, max_lines = self.font_card, 3
            lines = self._wrap(text, font, rect.w - s(92), max_lines)
            if lines and lines[-1].endswith("…"):
                font, max_lines = self.font_small, 4
                lines = self._wrap(text, font, rect.w - s(92), max_lines)
        else:
            font, max_lines = self.font_small, 1
            lines = self._wrap(text, font, rect.w - s(92), max_lines)
        ty = rect.y + (s(12) if big else s(7))
        for line in lines:
            surface.blit(font.render(line, True, INK), (rect.x + s(16), ty))
            ty += font.get_linesize()

        if reminder:
            # stage chip — OVERDUE blinks
            blink = stage != "OVERDUE" or int(self.time_alive * 2) % 2 == 0
            if blink:
                chip = self.font_small.render(stage, True, (245, 240, 230))
                cw = chip.get_width() + s(10)
                crect = pygame.Rect(rect.right - cw - s(6), rect.y + s(5), cw, s(15))
                pygame.draw.rect(surface, col, crect, border_radius=s(3))
                surface.blit(chip, (crect.x + s(5), crect.y + s(2)))
            if big:
                filed = datetime.datetime.fromtimestamp(reminder["ts"]).strftime("%H:%M")
                meta = self.font_small.render(
                    f"FILED {filed}  ·  {age_str(age)}", True, INK_FAINT)
                surface.blit(meta, (rect.x + s(16), rect.bottom - s(18)))

    def _draw_stamp(self, surface, slot):
        """DELIVERED slams onto the card: big -> settled, slight rotation."""
        at = self.stamp_anim["t"]
        if self._stamp_surf is None:
            base = self.font_stamp.render("· DELIVERED ·", True, STAMP_RED)
            pad = s(8)
            boxed = pygame.Surface((base.get_width() + pad * 2,
                                    base.get_height() + pad * 2), pygame.SRCALPHA)
            pygame.draw.rect(boxed, STAMP_RED, boxed.get_rect(), s(3), border_radius=s(6))
            boxed.blit(base, (pad, pad))
            self._stamp_surf = boxed
        # scale 2.4 -> 1.0 in the first 0.18 s (the slam), then rest
        prog = min(1.0, at / 0.18)
        scale = 2.4 - 1.4 * prog
        stamped = pygame.transform.rotozoom(self._stamp_surf, -12, scale)
        alpha = 255 if at < 0.7 else max(0, int(255 * (1 - (at - 0.7) / 0.4)))
        stamped.set_alpha(alpha)
        surface.blit(stamped, (slot.centerx - stamped.get_width() // 2,
                               slot.centery - stamped.get_height() // 2))

    def _draw_empty(self, surface, t):
        cy = int(SCREEN_HEIGHT * 0.42)
        # wax seal of a clear conscience
        pulse = 0.5 + 0.5 * math.sin(t * 1.5)
        pygame.draw.circle(surface, lerp_color(DONE_GRN, WOOD, 0.35),
                           (SCREEN_WIDTH // 2, cy), s(34))
        pygame.draw.circle(surface, lerp_color(DONE_GRN, (255, 255, 255), 0.2 * pulse),
                           (SCREEN_WIDTH // 2, cy), s(34), 2)
        chk = self.font_stamp.render("ALL CLEAR", True, PAPER)
        surface.blit(chk, ((SCREEN_WIDTH - chk.get_width()) // 2, cy + s(48)))
        sub = self.font_small.render("THE DOCKET SLEEPS. NOTHING OWED.", True, INK_FAINT)
        surface.blit(sub, ((SCREEN_WIDTH - sub.get_width()) // 2, cy + s(74)))
        how = self.font_small.render(f"POST TO  ntfy.sh/{TOPIC}", True, BRASS)
        surface.blit(how, ((SCREEN_WIDTH - how.get_width()) // 2, cy + s(100)))

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = STAMP_RED if mode == "work" else DONE_GRN
        txt = self.font_small.render(f"{mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(24), s(54)))
        box = rect.inflate(s(10), s(6))
        pygame.draw.rect(surface, WOOD_DARK, box, border_radius=s(4))
        pygame.draw.rect(surface, c, box, 1, border_radius=s(4))
        surface.blit(txt, rect)
