# Copilot instructions (Kea)

## Project snapshot
- This is a small **Pygame “smart display” app** built around a simple state machine.
- Entry point + state manager live in `src/main.py`.
- Screen sizing + colors are centralized in `src/config.py` (notably `ENVIRONMENT` switches `400x600` staging vs `200x300` production).

## How to run locally
- Preferred: use the Conda env `Kea` (so you don't accidentally run system `python3`).
  - Run (activation): `conda activate Kea && python src/main.py`
  - Run (no activation): `conda run -n Kea python src/main.py`
  - Install dependency (if needed): `conda run -n Kea python -m pip install pygame`

- Manual test controls (wired in `src/main.py`):
  - `1` ambient
  - `2` pomodoro
  - `3` notification
  - `4` street
  - `5` cloud city
  - `6` telegraph
  - `7` airship dock
  - `Esc` quits

## Architecture & conventions
### State machine
- All states subclass `State` from `src/states/base_state.py` and implement any of:
  - `enter()` / `exit()` for transition lifecycle
  - `handle_events(events)` for Pygame input
  - `update(dt)` for time-based logic (`dt` is seconds)
  - `draw(surface)` for rendering
- States transition by calling `self.manager.change_state('<name>')` (see `NotificationState.update` in `src/states/notification_state.py`).
- **Pomodoro Timer Rule:** The Pomodoro timer runs globally. When creating a new scene/state, ensure that no critical UI elements are positioned at the Top Right (`topright=(SCREEN_WIDTH - 5, 5)`), because `main.py` automatically overlays the active Pomodoro timer there.
- To add a new screen:
  1) create `src/states/<name>_state.py`
  2) register it in `StateManager` in `src/main.py`
  3) (optional) add a temporary hotkey in the global KEYDOWN block for quick iteration.

### Ambient rendering (performance-sensitive)
- `src/states/ambient_state.py` is the “heavy” state: procedural city layers + traffic + water reflection + optional weather.
- Performance intent (explicit in code): **avoid per-frame allocations** where possible (targeting Raspberry Pi).
  - Prefer cached/reused `pygame.Surface` instances (e.g., `cached_weather_surf`, `cached_darken_surf`).
  - Prefer pre-rendering static content once in `generate_city()` and then blitting layers.
- When adding new effects, follow the existing pattern: compute in `update(dt)`, render in `draw(surface)`, and keep the draw path mostly “blit + draw primitives”.

### Text/UI pattern
- `GlowText` (`src/ui/glow_text.py`) pre-renders wrapped, glowing text to a surface.
  - Update copy only when the text changes via `GlowText.update_text(...)`.
- The ticker-like feed `CurrentAffairs` (`src/current_affairs.py`) is time-driven: `update(dt)` returns a boolean indicating whether the displayed message changed.

## Assets & generator provenance
- The ambient city generator is a Python translation of an Aseprite script; see `src/animations/aseprite/scripts/city_background.lua` for the original logic and constants.
- Pixel-art source assets live under `assets/` (Aseprite files + pack structure). The runtime currently draws procedurally rather than loading those assets.
