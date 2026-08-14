"""
camera.py — stills only, as little compute as possible.

No continuous preview, no ML, no video: the camera is started when you
open the camera screen, produces a single JPEG per shutter press, and is
stopped again on the way out. That keeps a Pi 3B+ almost idle while
you're collecting data.

Capture size is 1280x720 by default. Big enough to crop a face out later
if the task turns out to need one, small enough that 10 000 images is
under 2 GB — you can always downscale, never upscale.

    from backend import camera
    camera.CameraService.instance().capture()   -> (tmp_path, meta) | (None, err)

Off a Pi (no picamera2) it produces a synthetic frame instead, so the
screen and the tests still work on a laptop.
"""

import os
import tempfile
import threading
import time

WIDTH = int(os.getenv("KEA_CAM_WIDTH", "1280"))
HEIGHT = int(os.getenv("KEA_CAM_HEIGHT", "720"))
QUALITY = int(os.getenv("KEA_CAM_QUALITY", "85"))


class CameraService:
    """Singleton around picamera2. Never raises: callers get None + a reason."""

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._cam = None
        self._started = False
        self._real = False
        self._error = None
        self._shots = 0

    # ── lifecycle ──────────────────────────────────────────────────────────
    def start(self):
        """Bring the camera up. Safe to call repeatedly."""
        if self._started:
            return self._real
        try:
            from picamera2 import Picamera2      # noqa: WPS433 (optional dep)
            self._cam = Picamera2()
            cfg = self._cam.create_still_configuration(
                main={"size": (WIDTH, HEIGHT)})
            self._cam.configure(cfg)
            self._cam.start()
            time.sleep(0.4)                      # let AE/AWB settle once
            self._real = True
            self._error = None
        except Exception as e:                   # no camera, no lib, in use…
            self._cam = None
            self._real = False
            self._error = str(e).split("\n")[0][:80]
        self._started = True
        return self._real

    def stop(self):
        if self._cam is not None:
            try:
                self._cam.stop()
                self._cam.close()
            except Exception:
                pass
        self._cam = None
        self._started = False

    # ── state ──────────────────────────────────────────────────────────────
    def available(self):
        return self._real

    def error(self):
        return self._error

    def shots(self):
        return self._shots

    # ── capture ────────────────────────────────────────────────────────────
    def capture(self):
        """Take one still. Returns (temp_jpeg_path, metadata) or (None, reason)."""
        if not self._started:
            self.start()
        fd, path = tempfile.mkstemp(suffix=".jpg", prefix="kea_shot_")
        os.close(fd)
        meta = {"width": WIDTH, "height": HEIGHT, "quality": QUALITY}
        try:
            if self._real and self._cam is not None:
                self._cam.options["quality"] = QUALITY
                self._cam.capture_file(path)
                try:                              # useful for filtering later
                    m = self._cam.capture_metadata()
                    for k in ("ExposureTime", "AnalogueGain", "Lux",
                              "ColourTemperature"):
                        if k in m:
                            meta[k] = m[k]
                except Exception:
                    pass
            else:
                if not self._write_placeholder(path):
                    os.remove(path)
                    return None, (self._error or "no camera")
                meta["synthetic"] = True
            self._shots += 1
            return path, meta
        except Exception as e:
            try:
                os.remove(path)
            except OSError:
                pass
            return None, str(e).split("\n")[0][:80]

    # A recognisable stand-in so the screen and tests work off-Pi.
    def _write_placeholder(self, path):
        try:
            import pygame
            surf = pygame.Surface((WIDTH, HEIGHT))
            for y in range(0, HEIGHT, 4):
                t = y / max(1, HEIGHT)
                surf.fill((int(30 + 60 * t), int(34 + 40 * t), int(48 + 30 * t)),
                          (0, y, WIDTH, 4))
            for i in range(0, WIDTH, 80):
                pygame.draw.line(surf, (70, 80, 96), (i, 0), (i, HEIGHT))
            pygame.image.save(surf, path)
            return True
        except Exception as e:
            self._error = self._error or str(e)[:80]
            return False
