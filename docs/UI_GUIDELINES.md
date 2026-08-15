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

## 1b. The rail is for instruments, not for everything

**A screen with nothing to do in it does not get a card.** The Nexus rail
grew to sixteen cards — five across, four rows, scrolling — and nine of
them were ambient worlds. Nobody navigates to a fish tank. They belong
behind one card and on an idle timer (`states/drift_state.py`), not in
the hub.

Before adding a card, ask: *would someone reach for this on purpose?*
If the answer is "it's nice to look at", it is a drift station, not a
destination. The smoke test fails the build if the rail exceeds two rows.

Anything hosted inside drift must also be **exitable**: an ambient world
has no controls of its own, so changing straight into one strands you
there. That is why the old per-world keys now call `drift.open_at(name)`
instead of `change_state(name)`.

## 1c. The look: neon on black, and where it comes from

**Kea is dystopian, cyberpunk, a bit Star Wars cockpit, a bit roguelike
terminal, pixel art throughout.** Saturated neon on near-black, hard
edges, glowing type. Nothing pastel, nothing corporate, no grey office
enamel. It is a machine salvaged from somewhere worse than here and it
should look like it.

**Pull every colour from `src/ui/palette.py`.** Screens used to declare
their own at the top — about two hundred hardcoded tuples across
twenty-one files — and that is exactly how a theme dies: each new screen
picks "a nice amber" slightly different from the last nice amber, and
after a dozen screens there is no house style, just twelve opinions. The
Console and the Board had drifted all the way to grey and brass.

```python
from ui import palette as pal

surf.fill(pal.VOID)                       # never pure black
surf.blit(pal.glow_text(font, "READY", pal.CYAN), (x, y))
pal.glow_rect(surf, box, pal.MAGENTA, radius=s(5))
```

If a colour is not in `palette.py` it probably should not be on screen.
Need a new one? Add it there, with a name, so the next screen reuses it.

- `CYAN` is the default accent. `MAGENTA` is hot/danger/night, `ACID` is
  alive/go, `AMBER` is attention, `BLOOD` is stop.
- Use the semantic aliases (`OK`, `WARN`, `DANGER`, `ACCENT`) for
  meaning and the raw names for decoration. Then "what colour is danger"
  changes in one place.
- `pal.cycle(i)` gives the next distinct accent for cards, tags, series.
- **Glow is the look.** Neon without bloom is just bright text. Use
  `glow_text`, `halo`, `glow_rect` — all cached, so a glow costs about
  500x less after the first frame. Never blur per frame.
- Bevelled/clipped corners (`pal.bevel`) read as hardware; plain
  rectangles read as a business dashboard.
- Ambient worlds keep their own identities — the glasshouse is green
  because it is a glasshouse, the abyss is seafoam. The palette governs
  the *instruments*, and gives the worlds their accents.

### Atmosphere never beats legibility

The panel is dim and flat; neon on black that sings on a monitor can be
mush on the real thing. `pal.contrast(fg, bg)` measures the luminance
gap and `pal.readable(fg, bg, small=)` is the check — body text needs
60, text under ~14 px needs 85. `INK_FAINT` is decoration only; never
put words in it. The smoke test enforces this.

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
- [ ] earns its rail card — otherwise it's a drift station
- [ ] every colour comes from `ui/palette.py`, none declared locally
- [ ] bright text glows (`pal.glow_text`), and the glow is cached
- [ ] `pal.readable()` passes for every text/background pair
- [ ] **looked at on the actual panel at 480×320**
