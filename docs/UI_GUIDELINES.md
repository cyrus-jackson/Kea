# Kea — UI guidelines

Rules for any new screen. They exist because each one was learned the hard
way on the real 480×320 panel, not from theory.

---

## 1. The reserved strip (this is the one that keeps biting)

**The bottom ~28 px of the logical canvas belongs to system overlays.**
Kea draws the toggle-label chip and the Pomodoro badge there, on top of
whatever the screen has already drawn.

```
┌────────────────────────────┐
│                            │
│        your screen         │
│                            │
├────────────────────────────┤  ← keep status text ABOVE this line
│ ▲ AUTO SHOOT      overlays │  bottom ~28 px: system overlays
└────────────────────────────┘
```

So:

- **Don't put persistent status text in the bottom-left corner.** Several
  screens did, and the toggle chip sat straight on top of it.
- If a screen needs a footer, keep it **above** the reserved strip, or put
  it top-right.
- Overlays themselves must be **transient**. The toggle chip now shows for
  2.6 s, fades, and leaves only a 3 px pip. Anything permanent in that
  corner will eventually collide with a screen that wants it.

Check on the real panel, not just at 400×600 in the smoke test — at
480×320 there is far less room and collisions appear that don't at desk
size.

## 2. Scale from `SCREEN_HEIGHT`, never hardcode pixels

Every screen starts with:

```python
SCALE = SCREEN_HEIGHT / 480.0
def s(v):
    return max(1, int(v * SCALE))
```

Then `s(14)` everywhere instead of `14`. The staging canvas (400×600) and
the panel (320×480) differ enough that hardcoded values look fine on one
and broken on the other. The `max(1, ...)` matters: at small scales a
1 px line rounds to 0 and vanishes.

## 3. Text must fit or move

A long string that overflows is worse than one that scrolls. Either:

- marquee it (see `nexus_state`'s greeting), or
- shrink to fit, or
- wrap.

Never let it run off the edge — truncation with `...` loses the end of a
message, which on the Telegraph screen is usually the point of it.

## 4. Pre-render anything static

The Pi 3B+ renders every frame. Backgrounds, grids, bezels, card art:
build them **once** into a surface in `__init__` (or on first draw) and
blit that. Gradients drawn per-frame at 30 fps are what makes a screen
feel sluggish.

```python
self._bg = self._make_bg(size)     # once
surface.blit(self._bg, (0, 0))     # every frame
```

Cache per size, and rebuild if the surface size changes.

## 5. Hardware controls are optional, never required

A screen must be fully usable without a knob or button attached — the
keyboard fallbacks in `handle_events` are not decoration, they're how the
screen is tested headlessly.

Implement only what the screen actually uses:

| Method | Meaning |
|---|---|
| `move_cursor(dir)` | the screen owns the encoder; **implementing this takes the dial away from world-tuning** |
| `activate()` | encoder press; return `False` to mean "done, go home" |
| `on_toggle(on)` | the lever's meaning here |
| `toggle_label()` | what the chip says — keep it ≤ 12 chars |
| `on_green_button()` / `on_red_button()` | return `True` if you handled it |

## 6. Colour and legibility on a small TFT

- The panel is dim and low-contrast; **thin mid-grey text disappears**.
  Keep body text well above the background in luminance.
- Antialiased 1 px strokes turn to mush. Use 2 px for anything structural.
- Each screen has its own palette, but keep one accent doing one job.

## 7. Don't block the render loop

No network calls, no `sleep`, no file scans in `draw()` or `update()`.
Fetch on a worker thread and render whatever you have (see
`weather_api`, `voice`). A screen that stalls freezes the whole device,
including the buttons.

## 8. Degrade honestly

If a screen depends on hardware that might be missing — camera, network,
GPIO — say so on the screen in plain words, with the fix if there is one.
`camera_state` prints the actual reason rather than an empty frame.

---

## Checklist for a new screen

- [ ] nothing persistent in the bottom-left / reserved strip
- [ ] every dimension via `s()`
- [ ] long text marquees, shrinks or wraps
- [ ] static layers pre-rendered once
- [ ] keyboard fallbacks for every hardware control
- [ ] no blocking work in `update()` / `draw()`
- [ ] added to `tools/smoke_test.py`
- [ ] if it shouldn't be cycled into, added to `NO_CYCLE`
- [ ] **looked at on the actual panel at 480×320**
