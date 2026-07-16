# Kea

A small Pygame “smart display” app driven by a simple state machine.

## Raspberry Pi setup (lightweight)

By default, the app will run fullscreen on Raspberry Pi (and in `production`).
You can override behavior with environment variables:

- `KEA_FULLSCREEN=1` / `0` to force fullscreen on/off
- `KEA_SCALED=1` / `0` to enable/disable scaling the logical resolution to the display
- `KEA_ENVIRONMENT=staging|production` to switch the configured logical size
- `KEA_SCREEN_WIDTH` and `KEA_SCREEN_HEIGHT` to override the logical resolution (e.g. `480`x`320`)

### Option A: Use pip (virtualenv recommended)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
KEA_FULLSCREEN=1 python src/main.py
```

### Option B (often easiest on Pi): Use apt’s prebuilt Pygame

If `pip install` tries to compile and fails (SDL dependencies), install the distro build:

```bash
sudo apt update
sudo apt install -y python3-pygame
python3 src/main.py
```

## Controls

The app boots into **NEXUS**, the home hub: clock, System Protocol greeting, live weather, and all worlds as cards. It recommends a world for the current **day phase** (garden at sunrise → city for work → weather at lunch → orbital afternoons → telegraph at dusk → lab evenings → abyss at night, with a rain override). Press `A` on the hub to enable **auto-pilot**: Nexus dispatches to the recommended world automatically.

**Keyboard:**
- `H` nexus (home hub)
- `1` ambient
- `2` pomodoro
- `3` notification
- `4` street
- `5` cloud city
- `4` orbital control (atompunk radar)
- `5` bio-vat lab (biopunk specimens)
- `6` telegraph
- `7` conservatory (solarpunk garden)
- `8` climate
- `9` greetings
- `0` abyssal station (oceanpunk deep sea)
- `D` aerodrome (dieselpunk airfield — dispatches fly by as towed banners)
- `Esc` quits

**Hardware Buttons:**
- **Blue Button:** BCM GPIO 21 (Cycles through all available states)
- **Red Button:** BCM GPIO 20 (Assigned to action `2` / pomodoro)
- **Green Button:** BCM GPIO 26 (Assigned to action `3` / notification)

*(Note: Hardware buttons are tied to ground with pull-up resistors enabled)*
