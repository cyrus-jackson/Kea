"""
notification_state.py
---------------------
THE ANNUNCIATOR — Kea's master caution panel.

This is what the GREEN button summons: a hard industrial status panel
that triages the whole machine in one glance. No scene, no ticker —
deliberately a different visual language from every world.

It gathers attention from every subsystem that has any:

    DOCKET   open reminders, red when overdue
    WEATHER  live Stuttgart conditions, amber when you'll want a coat
    FOCUS    the pomodoro, running or resting
    UPLINK   how many live protocol feeds are warm
    THERMAL  the Pi's core temperature — it lives in a sealed printed
             cabinet with no fan, so this one earns its lamp
    SYSTEM   uptime and the lifebook's boot count

The worst condition wins the big readout at the top. Press GREEN again
and the panel *routes* you to the screen that can actually resolve it
(overdue reminder -> Docket, rain -> WX.SYS, focus -> Pomodoro). Left
alone it auto-returns to wherever you came from, so the interrupt never
strands you.
"""

import pygame
import time

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from backend.reminders import ReminderService, stage_for
from backend import world_weather, lifebook, vitals
from system_protocol import _FEEDS, FEEDS_ENABLED

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


def lerp_color(a, b, t):
    return tuple(max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


# ── Industrial panel palette ────────────────────────────────────────────────
PANEL      = (26, 27, 31)
PANEL_LIT  = (38, 40, 46)
BEZEL      = (14, 15, 18)
RIB        = (52, 55, 62)
LABEL      = (196, 200, 208)
LABEL_DIM  = (112, 118, 128)

GREEN      = (86, 214, 122)
AMBER      = (248, 176, 52)
RED        = (232, 72, 58)
BLUE       = (108, 186, 246)
OFF        = (52, 56, 64)

SEV_COLOR = {"ok": GREEN, "info": BLUE, "warn": AMBER, "alarm": RED}
SEV_RANK = {"ok": 0, "info": 1, "warn": 2, "alarm": 3}

DWELL_CLEAR = 6.0        # seconds on screen when nothing is wrong
DWELL_ALERT = 14.0       # longer when something wants you


class NotificationState(State):
    """Master caution panel: triage, then route."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.font_head = pygame.font.Font(None, s(22))
        self.font_big = pygame.font.Font(None, s(26))
        self.font_body = pygame.font.Font(None, s(18))
        self.font_lamp = pygame.font.Font(None, s(14))
        self.font_val = pygame.font.Font(None, s(17))

        self.reminders = ReminderService.instance()
        self.timer = 0.0
        self.time_alive = 0.0
        self.return_to = "nexus"
        self.lamps = []
        self.top = None

        # lamp grid: 2 columns x 3 rows, filling the panel to the footer
        self.grid_x = s(10)
        self.grid_y = s(194)
        self.cell_w = (SCREEN_WIDTH - s(20) - s(8)) // 2
        self.cell_h = s(72)

        self._bg = self._build_bg()

    # ══════════════════════════════════════════════════════════════════════
    def _build_bg(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(PANEL)
        # brushed-metal striations
        for y in range(0, SCREEN_HEIGHT, 2):
            shade = 2 if (y // 2) % 3 else -2
            surf.fill((PANEL[0] + shade, PANEL[1] + shade, PANEL[2] + shade),
                      (0, y, SCREEN_WIDTH, 1))
        # header rail with hex bolts
        pygame.draw.rect(surf, BEZEL, (0, 0, SCREEN_WIDTH, s(46)))
        pygame.draw.line(surf, RIB, (0, s(46)), (SCREEN_WIDTH, s(46)), 2)
        for bx in (s(9), SCREEN_WIDTH - s(9)):
            pygame.draw.circle(surf, RIB, (bx, s(12)), s(3))
            pygame.draw.circle(surf, RIB, (bx, s(34)), s(3))
        # footer rail
        pygame.draw.rect(surf, BEZEL, (0, SCREEN_HEIGHT - s(40),
                                       SCREEN_WIDTH, s(40)))
        pygame.draw.line(surf, RIB, (0, SCREEN_HEIGHT - s(40)),
                         (SCREEN_WIDTH, SCREEN_HEIGHT - s(40)), 2)
        return surf

    # ══════════════════════════════════════════════════════════════════════
    # Data gathering
    # ══════════════════════════════════════════════════════════════════════
    def _gather(self):
        """Build the lamp list. Each: (label, severity, value, message, route)."""
        lamps = []

        # DOCKET ────────────────────────────────────────────────────────
        n_open = self.reminders.count()
        overdue = self.reminders.overdue()
        if overdue:
            worst = overdue[0]
            sev = "alarm" if stage_for(time.time() - worst["ts"]) == "OVERDUE" else "warn"
            lamps.append(("DOCKET", sev, str(n_open),
                          worst["text"].upper(), "docket"))
        elif n_open:
            lamps.append(("DOCKET", "info", str(n_open),
                          f"{n_open} DISPATCH{'ES' if n_open > 1 else ''} AWAITING YOU",
                          "docket"))
        else:
            lamps.append(("DOCKET", "ok", "0", "DOCKET CLEAR. NOTHING OWED.", "docket"))

        # WEATHER ───────────────────────────────────────────────────────
        wx = world_weather.conditions()
        if wx["storm"]:
            lamps.append(("WEATHER", "alarm", "STORM",
                          "STORM OVER STUTTGART. STAY IN.", "climate"))
        elif wx["rain"] >= 0.4:
            lamps.append(("WEATHER", "warn", "RAIN",
                          "RAIN INBOUND. TAKE THE UMBRELLA.", "climate"))
        elif wx["wind"] >= 32:
            lamps.append(("WEATHER", "warn", f"{int(wx['wind'])}KH",
                          "HIGH WIND. AIRSHIPS GROUNDED.", "climate"))
        else:
            lamps.append(("WEATHER", "ok", "CLEAR", "SKY CLEAR OVER THE SPRAWL.",
                          "climate"))

        # FOCUS ─────────────────────────────────────────────────────────
        pomo = getattr(self.manager, "states", {}).get("pomodoro")
        if pomo is not None and getattr(pomo, "running", False):
            left = int(getattr(pomo, "time_left", 0))
            mode = getattr(pomo, "mode", "work")
            lamps.append(("FOCUS", "info", f"{left // 60:02d}:{left % 60:02d}",
                          f"{'FOCUS' if mode == 'work' else 'BREAK'} RUNNING — "
                          f"{left // 60} MIN LEFT", "pomodoro"))
        else:
            done = lifebook.get("pomodoros", 0)
            lamps.append(("FOCUS", "ok", "IDLE",
                          f"{done} FOCUS SESSIONS BANKED.", "pomodoro"))

        # UPLINK ────────────────────────────────────────────────────────
        warm = sum(1 for f in _FEEDS.values() if f.value is not None)
        total = len(_FEEDS)
        if not FEEDS_ENABLED:
            lamps.append(("UPLINK", "info", "OFF", "FEEDS DISABLED. LOCAL ONLY.",
                          "greetings"))
        elif warm == 0:
            lamps.append(("UPLINK", "warn", f"0/{total}",
                          "NO UPLINK. RUNNING ON LOCAL PROTOCOL.", "greetings"))
        else:
            sev = "ok" if warm >= total - 1 else "info"
            lamps.append(("UPLINK", sev, f"{warm}/{total}",
                          f"{warm} OF {total} FEEDS LIVE.", "greetings"))

        # THERMAL — the Pi is sealed in a printed cabinet ────────────────
        level = vitals.thermal_level()
        temp = vitals.core_temp_c()
        if level == "hot":
            lamps.append(("THERMAL", "alarm", f"{temp:.0f}C",
                          f"CORE AT {temp:.0f}C — THROTTLING. VENT THE CABINET.",
                          None))
        elif level == "warn":
            lamps.append(("THERMAL", "warn", f"{temp:.0f}C",
                          f"CORE WARM AT {temp:.0f}C. WATCH IT.", None))
        elif level == "nominal":
            lamps.append(("THERMAL", "ok", f"{temp:.0f}C",
                          f"CORE COOL AT {temp:.0f}C.", None))
        else:
            # no sensor (desktop): not a condition, just unreported
            lamps.append(("THERMAL", "ok", "--", "SENSOR NOT PRESENT.", None))

        # SYSTEM ────────────────────────────────────────────────────────
        boots = lifebook.get("boots", 0)
        lamps.append(("SYSTEM", "ok", vitals.uptime_str(),
                      f"UP {vitals.uptime_str()}  ·  BOOT {boots}", "nexus"))

        return lamps

    # ══════════════════════════════════════════════════════════════════════
    def _pick_top(self):
        """Worst condition wins the readout; ties keep gather order. When
        nothing at all wants attention, say so plainly."""
        top = max(self.lamps, key=lambda l: SEV_RANK[l[1]])
        if SEV_RANK[top[1]] == 0:
            return ("ALL STATIONS", "ok", "OK",
                    "ALL SYSTEMS NOMINAL. NOTHING NEEDS YOU.", None)
        return top

    def enter(self):
        self.timer = 0.0
        self.lamps = self._gather()
        self.top = self._pick_top()
        prev = getattr(self.manager, "previous_state_name", None)
        self.return_to = prev if prev and prev != "notification" else "nexus"

    def on_green_button(self):
        """Green again = go where the top alert can be dealt with."""
        self._ensure()
        route = self.top[4]
        if route and route in getattr(self.manager, "states", {}):
            self.manager.change_state(route)
            return True
        self.manager.change_state(self.return_to)
        return True

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_g:
                self.on_green_button()

    def _ensure(self):
        """Panel is usable even if update/draw runs before enter()."""
        if not self.lamps or self.top is None:
            self.lamps = self._gather()
            self.top = self._pick_top()

    def _dwell(self):
        self._ensure()
        return DWELL_ALERT if SEV_RANK[self.top[1]] >= 2 else DWELL_CLEAR

    def update(self, dt):
        self._ensure()
        self.time_alive += dt
        prev_timer = self.timer
        self.timer += dt
        if int(self.timer * 2) != int(prev_timer * 2):
            self.lamps = self._gather()          # refresh twice a second
            self.top = self._pick_top()
        if self.timer >= self._dwell():
            self.manager.change_state(self.return_to)

    # ══════════════════════════════════════════════════════════════════════
    def _wrap(self, text, font, max_w):
        words, lines, cur = text.split(), [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if font.size(test)[0] <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def draw(self, surface):
        surface.blit(self._bg, (0, 0))
        self._ensure()
        t = self.time_alive
        label, sev, value, message, route = self.top
        accent = SEV_COLOR[sev]
        alarmed = SEV_RANK[sev] >= 2
        blink = (not alarmed) or (int(t * 2.6) % 2 == 0)

        # ── header: master caution ──────────────────────────────────────
        mc = pygame.Rect(s(24), s(11), s(24), s(24))
        pygame.draw.rect(surface, accent if blink else lerp_color(accent, BEZEL, 0.72),
                         mc, border_radius=s(4))
        pygame.draw.rect(surface, BEZEL, mc, 1, border_radius=s(4))
        excl = self.font_head.render("!", True, BEZEL)
        surface.blit(excl, excl.get_rect(center=mc.center))
        head = self.font_head.render("ANNUNCIATOR", True, LABEL)
        surface.blit(head, (s(56), s(14)))
        stamp = self.font_lamp.render(
            "MASTER CAUTION" if alarmed else "ADVISORY", True,
            accent if blink else LABEL_DIM)
        surface.blit(stamp, (SCREEN_WIDTH - stamp.get_width() - s(20), s(18)))

        # ── priority readout ────────────────────────────────────────────
        box = pygame.Rect(s(10), s(56), SCREEN_WIDTH - s(20), s(126))
        pygame.draw.rect(surface, PANEL_LIT, box, border_radius=s(6))
        pygame.draw.rect(surface, accent if blink else lerp_color(accent, PANEL, 0.6),
                         box, 2, border_radius=s(6))
        # severity ribbon down the left edge
        pygame.draw.rect(surface, accent if blink else lerp_color(accent, PANEL, 0.55),
                         (box.x + s(4), box.y + s(4), s(4), box.h - s(8)),
                         border_radius=s(2))
        sub = self.font_lamp.render(f"{label}  ·  {sev.upper()}", True, accent)
        surface.blit(sub, (box.x + s(16), box.y + s(9)))

        # message: big font, dropping a size rather than ever truncating
        maxw = box.w - s(30)
        font = self.font_big
        lines = self._wrap(message, font, maxw)
        if len(lines) > 3:
            font = self.font_body
            lines = self._wrap(message, font, maxw)
        ly = box.y + s(32)
        for line in lines[:4]:
            surface.blit(font.render(line, True, LABEL), (box.x + s(16), ly))
            ly += font.get_linesize()

        if route:
            hint = self.font_lamp.render(f"GREEN  >  {route.upper()}", True, accent)
            surface.blit(hint, (box.right - hint.get_width() - s(12),
                                box.bottom - s(17)))

        # ── lamp grid: every subsystem, with its own one-line status ────
        for i, (llabel, lsev, lvalue, lmsg, _r) in enumerate(self.lamps[:6]):
            col, row = i % 2, i // 2
            cell = pygame.Rect(self.grid_x + col * (self.cell_w + s(8)),
                               self.grid_y + row * (self.cell_h + s(8)),
                               self.cell_w, self.cell_h)
            lit = SEV_COLOR[lsev]
            urgent = SEV_RANK[lsev] >= 2
            on = (not urgent) or (int(t * 2.6) % 2 == 0)
            face = lerp_color(PANEL, lit, 0.15 if on else 0.05)
            pygame.draw.rect(surface, face, cell, border_radius=s(4))
            pygame.draw.rect(surface, lerp_color(lit, BEZEL, 0.4 if on else 0.75),
                             cell, 2, border_radius=s(4))
            # lamp strip down the left edge of the cell
            bulb = pygame.Rect(cell.x + s(6), cell.y + s(6), s(7), cell.h - s(12))
            if on and urgent:                       # halo when calling for you
                glow = pygame.Surface((bulb.w + s(8), bulb.h + s(8)), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*lit, 70), glow.get_rect(),
                                 border_radius=s(5))
                surface.blit(glow, (bulb.x - s(4), bulb.y - s(4)))
            pygame.draw.rect(surface, lit if on else lerp_color(lit, OFF, 0.8),
                             bulb, border_radius=s(3))

            tx = cell.x + s(19)
            tw = cell.w - s(25)
            lab = self.font_lamp.render(llabel, True, LABEL)
            surface.blit(lab, (tx, cell.y + s(7)))
            val = self.font_val.render(lvalue, True, lit if on else LABEL_DIM)
            surface.blit(val, (cell.right - val.get_width() - s(7), cell.y + s(6)))
            # short status, wrapped to two tiny lines
            sy_ = cell.y + s(26)
            for line in self._wrap(lmsg, self.font_lamp, tw)[:3]:
                surface.blit(self.font_lamp.render(line, True, LABEL_DIM), (tx, sy_))
                sy_ += self.font_lamp.get_linesize()

        # ── footer: dwell bar + return hint ─────────────────────────────
        fy = SCREEN_HEIGHT - s(40)
        remain = max(0.0, 1.0 - self.timer / self._dwell())
        bar = pygame.Rect(s(10), fy + s(10), SCREEN_WIDTH - s(20), s(5))
        pygame.draw.rect(surface, OFF, bar, border_radius=s(2))
        if remain > 0:
            pygame.draw.rect(surface, accent,
                             (bar.x, bar.y, max(1, int(bar.w * remain)), bar.h),
                             border_radius=s(2))
        back = self.font_lamp.render(
            f"RETURNING TO {self.return_to.upper()}  ·  "
            f"{max(0.0, self._dwell() - self.timer):.0f}S",
            True, LABEL_DIM)
        surface.blit(back, ((SCREEN_WIDTH - back.get_width()) // 2, fy + s(21)))

    def draw_pomodoro(self, surface, time_left, mode):
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = RED if mode == "work" else GREEN
        txt = self.font_lamp.render(f"{mins:02d}:{secs:02d}", True, (245, 245, 245))
        rect = txt.get_rect(midtop=(SCREEN_WIDTH // 2, s(50)))
        box = rect.inflate(s(12), s(6))
        pygame.draw.rect(surface, c, box, border_radius=s(3))
        surface.blit(txt, rect)
