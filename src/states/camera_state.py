"""
camera_state.py
---------------
THE PLATE CAMERA — collecting training data, one approved frame at a time.

A field photographer's kit: a dark leather body, a brass lens ring, and a
ground-glass back where the shot appears for you to accept or reject.
Nothing is stored until you say so, and nothing here runs ML — this screen
exists purely to build a clean dataset.

    GREEN   shutter; then in review, APPROVE
    RED     discard the frame under review
    ENCODER turn to choose the tag, press to cycle it too
    TOGGLE  auto-capture: a frame every N seconds, no approval needed
            (N is the CONSOLE's AUTO SHOOT dial, 2-60 s)

Tags come from ~/.kea_tags.json and are re-read every time you open this
screen, so you can add classes as the task takes shape without touching
code or restarting.
"""

import math
import os

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from backend import dataset
from backend.camera import CameraService
from hardware_input import BUTTON_NOTIFICATION_EVENT, BUTTON_POMODORO_EVENT

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


# ── palette: leather, brass, ground glass ───────────────────────────────────
LEATHER = (44, 33, 28)
LEATHER_D = (28, 20, 17)
BRASS = (176, 138, 66)
BRASS_LIT = (232, 198, 126)
BRASS_DK = (92, 70, 30)
GLASS = (168, 180, 176)
CREAM = (238, 230, 210)
DIM = (140, 126, 104)
GREEN_OK = (120, 210, 130)
RED_NO = (206, 84, 70)

def auto_every():
    """Seconds between auto-captures. Live from the Console's third dial,
    so you can change it while shooting; KEA_CAM_AUTO_SECS still wins if
    you'd rather pin it."""
    env = os.getenv("KEA_CAM_AUTO_SECS")
    if env:
        try:
            return max(1.0, float(env))
        except ValueError:
            pass
    try:
        from backend import settings
        return float(settings.get("shoot_every"))
    except Exception:
        return 6.0


class CameraState(State):
    """Shoot, review, tag, store. Uploading is the offloader's job."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()
        self.font_title = pygame.font.Font(None, s(26))
        self.font_tag = pygame.font.Font(None, s(30))
        self.font_body = pygame.font.Font(None, s(16))
        self.font_small = pygame.font.Font(None, s(13))

        self.cam = CameraService.instance()
        self.mode = "idle"            # idle | review
        self.preview = None           # pygame surface of the pending shot
        self.pending_path = None      # temp jpeg awaiting approval
        self.pending_meta = {}
        self.tag_i = 0
        self.msg = ""
        self.msg_t = 0.0
        self.t = 0.0
        self.auto = False
        self.auto_t = 0.0
        self.saved = 0
        self._bg = None

    # ── lifecycle ──────────────────────────────────────────────────────────
    def enter(self):
        self.t = 0.0
        self.mode = "idle"
        self._discard()
        dataset.tags()                # re-read the file: new tags appear here
        self.cam.start()
        self.auto = bool(getattr(self.manager, "toggle_on", False))
        self.auto_t = 0.0

    def exit(self):
        self._discard()
        self.cam.stop()               # don't leave the sensor running

    # ── controls ───────────────────────────────────────────────────────────
    def on_green_button(self):
        """Shutter, then approve. Returns True so main.py doesn't also act."""
        if self.mode == "review":
            self._approve()
        else:
            self._shoot()
        return True

    def on_red_button(self):
        if self.mode == "review":
            self._discard()
            self._flash("DISCARDED")
        return True

    def move_cursor(self, direction):
        tg = dataset.tags()
        if tg:
            self.tag_i = (self.tag_i + (1 if direction > 0 else -1)) % len(tg)
        return True

    def activate(self):
        self.move_cursor(1)
        return True

    def on_toggle(self, on):
        self.auto = on
        self.auto_t = 0.0
        self._flash("AUTO CAPTURE ON" if on else "AUTO OFF")

    def toggle_label(self):
        return "AUTO SHOOT"

    def handle_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.on_green_button()
                elif e.key == pygame.K_BACKSPACE:
                    self.on_red_button()
                elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.move_cursor(1 if e.key == pygame.K_RIGHT else -1)
            elif e.type == BUTTON_NOTIFICATION_EVENT:
                self.on_green_button()
            elif e.type == BUTTON_POMODORO_EVENT:
                self.on_red_button()

    # ── the actual work ────────────────────────────────────────────────────
    def _cur_tag(self):
        tg = dataset.tags()
        return tg[self.tag_i % len(tg)] if tg else "untagged"

    def _shoot(self):
        path, meta = self.cam.capture()
        if not path:
            self._flash(f"NO FRAME: {meta}")
            return
        self.pending_path = path
        self.pending_meta = meta if isinstance(meta, dict) else {}
        self.preview = self._thumb(path)
        self.mode = "review"

    def _approve(self):
        if not self.pending_path:
            return
        stored = dataset.save(self.pending_path, self._cur_tag(),
                              extra=self.pending_meta)
        self.pending_path = None
        self.mode = "idle"
        if stored:
            self.saved += 1
            self._flash(f"SAVED  {self._cur_tag()}")
            try:
                from backend import voice
                voice.say("blip")
            except Exception:
                pass
        else:
            self._flash("SAVE FAILED")

    def _discard(self):
        if self.pending_path and os.path.exists(self.pending_path):
            try:
                os.remove(self.pending_path)
            except OSError:
                pass
        self.pending_path = None
        self.preview = None
        self.mode = "idle"

    def _thumb(self, path):
        """Scale the shot down once, for display only."""
        try:
            img = pygame.image.load(path)
            box_w = SCREEN_WIDTH - s(28)
            box_h = int(SCREEN_HEIGHT * 0.42)
            iw, ih = img.get_size()
            k = min(box_w / iw, box_h / ih)
            return pygame.transform.smoothscale(
                img, (max(1, int(iw * k)), max(1, int(ih * k))))
        except Exception:
            return None

    def _flash(self, text):
        self.msg = text
        self.msg_t = 2.2

    # ── update ─────────────────────────────────────────────────────────────
    def update(self, dt):
        self.t += dt
        if self.msg_t > 0:
            self.msg_t = max(0.0, self.msg_t - dt)
        if self.auto and self.mode == "idle":
            self.auto_t += dt
            if self.auto_t >= auto_every():
                self.auto_t = 0.0
                self._shoot()
                if self.pending_path:      # auto mode stores without asking
                    self._approve()

    # ── drawing ────────────────────────────────────────────────────────────
    def draw(self, surface):
        if self._bg is None or self._bg.get_size() != surface.get_size():
            self._bg = self._make_bg(surface.get_size())
        surface.blit(self._bg, (0, 0))
        w, h = surface.get_size()

        # ── ground glass: the frame under review ────────────────────────
        gy = s(56)
        gh = int(h * 0.42)
        plate = pygame.Rect(s(12), gy, w - s(24), gh)
        pygame.draw.rect(surface, (18, 20, 20), plate)
        if self.preview is not None:
            surface.blit(self.preview, self.preview.get_rect(center=plate.center))
        else:
            hint = "READY — GREEN TO SHOOT" if self.cam.available() \
                else f"NO CAMERA: {self.cam.error() or 'not detected'}"
            t = self.font_body.render(hint, True, GLASS if self.cam.available() else RED_NO)
            surface.blit(t, t.get_rect(center=plate.center))
            # faint focusing grid, so it reads as ground glass
            for i in range(1, 3):
                pygame.draw.line(surface, (38, 42, 42),
                                 (plate.x + plate.w * i // 3, plate.y),
                                 (plate.x + plate.w * i // 3, plate.bottom))
                pygame.draw.line(surface, (38, 42, 42),
                                 (plate.x, plate.y + plate.h * i // 3),
                                 (plate.right, plate.y + plate.h * i // 3))
        pygame.draw.rect(surface, BRASS_DK, plate, 2)
        for cx, cy in ((plate.x, plate.y), (plate.right, plate.y),
                       (plate.x, plate.bottom), (plate.right, plate.bottom)):
            pygame.draw.circle(surface, BRASS, (cx, cy), s(4))

        # ── tag selector ────────────────────────────────────────────────
        ty = plate.bottom + s(14)
        tg = dataset.tags()
        cur = self._cur_tag()
        lab = self.font_small.render(
            f"TAG  {self.tag_i + 1}/{len(tg)}   (turn the dial)", True, DIM)
        surface.blit(lab, (s(14), ty))
        val = self.font_tag.render(cur.upper(), True, BRASS_LIT)
        surface.blit(val, (s(14), ty + s(14)))

        # counts, so you can keep the classes balanced while shooting
        cnt = dataset.counts()
        cy2 = ty + s(46)
        for i, tname in enumerate(tg[:6]):
            n = cnt.get(tname, 0)
            on = (tname == cur)
            col = BRASS_LIT if on else DIM
            txt = self.font_small.render(f"{tname[:10]:<10} {n:>4}", True, col)
            surface.blit(txt, (s(14) + (i % 2) * s(150), cy2 + (i // 2) * s(15)))

        # ── status strip ────────────────────────────────────────────────
        n_pend, bytes_pend = dataset.pending_stats()
        sy = h - s(52)
        pygame.draw.line(surface, BRASS_DK, (s(12), sy), (w - s(12), sy))
        info = (f"PENDING {n_pend}  ·  {bytes_pend / 1048576:.1f} MB"
                f"  ·  SAVED THIS RUN {self.saved}")
        surface.blit(self.font_small.render(info, True, DIM), (s(14), sy + s(6)))

        if self.mode == "review":
            hint = "GREEN APPROVE   ·   RED DISCARD"
            col = GREEN_OK
        elif self.auto:
            left = max(0, auto_every() - self.auto_t)
            hint = f"AUTO — NEXT IN {left:0.0f}s"
            col = BRASS_LIT
        else:
            hint = "GREEN SHUTTER"
            col = CREAM
        surface.blit(self.font_body.render(hint, True, col), (s(14), sy + s(22)))

        # transient message
        if self.msg_t > 0:
            a = min(1.0, self.msg_t / 0.6)
            m = self.font_body.render(self.msg, True,
                                      GREEN_OK if "SAVED" in self.msg else CREAM)
            box = m.get_rect(midtop=(w // 2, plate.bottom - s(26)))
            bg = pygame.Surface((box.w + s(16), box.h + s(8)), pygame.SRCALPHA)
            bg.fill((20, 16, 14, int(220 * a)))
            surface.blit(bg, (box.x - s(8), box.y - s(4)))
            surface.blit(m, box)

    def _make_bg(self, size):
        w, h = size
        bg = pygame.Surface(size)
        bg.fill(LEATHER)
        rng = __import__("random").Random(11)
        for _ in range(220):                       # leather grain
            x, y = rng.randint(0, w - 1), rng.randint(0, h - 1)
            bg.set_at((x, y), LEATHER_D)
        head = pygame.Rect(0, 0, w, s(44))
        pygame.draw.rect(bg, LEATHER_D, head)
        pygame.draw.line(bg, BRASS_DK, (0, s(44)), (w, s(44)), 2)
        title = self.font_title.render("PLATE CAMERA", True, BRASS_LIT)
        bg.blit(title, (s(14), s(12)))
        sub = self.font_small.render("DATA COLLECTION", True, DIM)
        bg.blit(sub, (w - sub.get_width() - s(14), s(18)))
        return bg
