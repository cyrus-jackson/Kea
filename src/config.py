# --- Configuration ---

import os
import platform
import sys

# Environment Setup
ENVIRONMENT = os.getenv("KEA_ENVIRONMENT", "staging")  # "development" | "staging" | "production"


def _truthy_env(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _is_raspberry_pi() -> bool:
    if sys.platform != "linux":
        return False

    machine = platform.machine().lower()
    if "arm" in machine or "aarch64" in machine:
        return True

    try:
        with open("/proc/device-tree/model", "r", encoding="utf-8") as f:
            return "raspberry pi" in f.read().lower()
    except OSError:
        return False

# Screen Sizes
if ENVIRONMENT == "staging":
    SCREEN_WIDTH = 400
    SCREEN_HEIGHT = 600
elif ENVIRONMENT == "production":
    SCREEN_WIDTH = 200
    SCREEN_HEIGHT = 300
else:
    SCREEN_WIDTH = 200
    SCREEN_HEIGHT = 300

# Optional overrides (e.g. Raspberry Pi 480x320 screens)
_env_width = os.getenv("KEA_SCREEN_WIDTH")
_env_height = os.getenv("KEA_SCREEN_HEIGHT")
if _env_width and _env_height:
    try:
        SCREEN_WIDTH = int(_env_width)
        SCREEN_HEIGHT = int(_env_height)
    except ValueError:
        pass

FPS = 60

# Display
# On Raspberry Pi, default to fullscreen for kiosk-like usage.
_fullscreen_override = _truthy_env("KEA_FULLSCREEN")
FULLSCREEN = (
    (ENVIRONMENT == "production" or _is_raspberry_pi())
    if _fullscreen_override is None
    else _fullscreen_override
)

# When using fullscreen, scale the logical resolution to the display size.
_scaled_override = _truthy_env("KEA_SCALED")
SCALED = (FULLSCREEN if _scaled_override is None else _scaled_override)

# --- Colors ---
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DARK_BLUE = (10, 10, 40)
CRIMSON = (150, 0, 0)
YELLOW_BG = (200, 180, 0)
