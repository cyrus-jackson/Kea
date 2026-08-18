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

The app boots into **NEXUS**, the home hub: clock, System Protocol greeting, live weather, and a rail of **instrument cards** — the nine screens you press for a reason, two rows, no scrolling.

The eight ambient worlds are not on the rail. There is nothing to *do* in a neon city or a fish tank, so nobody navigates to them; they are what Kea does when you are not there. They live behind one card, **DRIFT**, and mostly arrive on their own.

### DRIFT — the rounds

Kea keeps a circuit of eight stations and walks it, and the circuit follows the sun:

| | Station | |
|---|---|---|
| 05 | the glasshouse | first light, wet soil |
| 08 | the orrery | brass, the day being wound |
| 11 | orbital control | high noon upstairs |
| 14 | bay 94 | dust and two setting suns |
| 17 | the aerodrome | golden hour, last departure |
| 20 | neon sprawl | the city takes over |
| 22 | the bio-vat lab | everyone's gone, the vats are awake |
| 01 | abyssal station | the small hours, deepest point |

Garden → clockwork → orbit → desert → dusk → city → lab → the deep, and back into the garden at dawn. **Leave Kea alone for a few minutes and it resumes the rounds wherever the hour says it should be** — the glasshouse at 6am, the bottom of the ocean at 3am. Touch anything and you are back where you were; that first press only wakes it, so you never lose a reminder to a button you pressed just to see the screen.

Passages are not cuts and deliberately not dissolves — the outgoing station slides away behind a lit seam to reveal the next one already running, and a **field note** names where you came from ("glass to glass — but this window holds back an ocean"), so the worlds read as one round rather than eight screensavers.

Tune the wait on the Console's **IDLE** dial (1-60 min, default 5); `KEA_DRIFT_HOLD` sets how long each station is held (default 90 s).

The **NOW / NEXT** transit board on Nexus is driven by the same circuit, so it tells you where Kea will be when you stop touching it — with a rain override that promotes WX.SYS and a docket override when reminders go overdue. Press `A` for **auto-pilot**: Nexus hands you to the rounds after a short dwell.

## Is it working?

```bash
python3 tools/doctor.py            # everything passive, ~15 s
python3 tools/doctor.py --slow     # + the encrypted offload round-trip
python3 tools/doctor.py --interactive   # + press every button, move servos
```

One command, one answer. It runs each of the individual `check_*` tools
as a subprocess and takes its exit code as the verdict, so nothing is
duplicated and a check cannot drift from the tool that owns it.

Passive by default: nothing moves and nothing is asked of you, so it is
safe over SSH on a machine you cannot see. Four verdicts — **PASS**,
**WARN** (works, will bite later), **FAIL** (broken, fix printed), and
**SKIP** (cannot be checked here). SKIP is not a soft FAIL: running it on
a laptop should not produce a wall of red for hardware that was never
meant to be attached.

Run `python3 tools/smoke_test.py` after changes: it renders every state headlessly and verifies each Nexus card and day phase points at a registered state.

**Keyboard:**

Choose instruments from Nexus with the dial and press. DRIFT is the first
card; Focus stays on the rail and no longer has a dedicated button or
keyboard shortcut.

Desktop shortcuts (useful while developing):
- `H` nexus (home hub)
- `3` notification · `6` telegraph · `8` climate · `9` greetings
- `R` dispatch docket (your phone reminders as aging paper cards)
- `L` the logbook (the machine's own history, kept in ink)
- `K` camera · `C` console · `V` the board (departures)

The rounds — these open **DRIFT** parked at that station, so the circuit carries on from there rather than stranding you in a world with no way out:
- `W` drift (resumes at the current hour's station)
- `7` the glasshouse (solarpunk garden) · `O` the orrery (clockpunk 3D solar system)
- `4` orbital control (atompunk radar) · `S` starport bay 94 (twin-sun desert dock)
- `D` aerodrome (dieselpunk airfield) · `1` neon sprawl (cyberpunk city)
- `5` bio-vat lab (biopunk specimens) · `0` abyssal station (oceanpunk deep sea)

## The Board (real departures)

A split-flap board wired to the live VVS network. It answers one question in
the largest type the panel can manage: **do I need to stand up?**

Not "when is the next tram" — your phone does that better. The number that
matters already counts the walk: a tram six minutes out is not six minutes
away if the platform is a five minute walk, it is **one**. So the headline is
LEAVE IN, green → amber → red as it runs out.

Out of the box it tracks three journeys from **Universität**:

| | | |
|---|---|---|
| HAUPTBAHNHOF | Universität → Hauptbahnhof (tief) | S-Bahn |
| VAIHINGEN | Universität → Vaihingen Bahnhof | S-Bahn |
| MAX-PLANCK | Universität → Max-Planck-Institute | Bus 748, ~4 min |

Walk times are per route — 13 min to the Hauptbahnhof platform, 5 to the
others — because it is the walk to *that* platform, not a property of you.

These are **journeys**, not stop departures, and they have to be. Two of the
three can't be expressed as "departures from Universität filtered by
destination": the 748 to Max-Planck says *Ostelsheim* on the front, and the
S-Bahn into town shows a dozen different terminus names through the day.
Filtering on those strings is guesswork, so Kea asks the journey planner the
question you're actually asking. You get arrival time, duration and change
count, which a platform board can't tell you.

The **dial walks one flat list of every departure on every route**, and
**pressing it tracks** the one you picked — the semaphore arm then points at
that countdown and the screen shows `ARM TRACKING` so the two can never
disagree. GREEN refreshes; the toggle unfolds the legs of the journey. HOME
goes back to Nexus, which is why the press is free for tracking.

A running Pomodoro outranks the arm's tram tracking: the session is what you
started deliberately, and an arm abandoning it to report a tram interrupts
exactly what the session exists to protect.

### Tracking more

```bash
# journeys:  origin>destination | label | walk_min
# stop board: stop_id | label | lines | towards | walk_min
KEA_VVS_ROUTES='de:08111:6008>de:08111:6118|HAUPTBAHNHOF|5 ; de:08111:6118|Hbf|U6,U7|Flughafen|7'
```

Find ids and the exact line/destination spellings:

```bash
python3 tools/find_stop.py "Vaihingen" --departures
```

Setting `KEA_VVS_ROUTES` replaces the defaults entirely; leave it unset to keep
them. `walk_min` is how long it takes *you* to reach the stop — the default is
5 minutes, and it is the one number worth getting right, because it is what
turns a departure time into "leave now".

No API key and no `pip install`: plain `urllib` against the public endpoint.

## Reminders from your phone

Post to your ntfy topic and it arrives on Kea. Three screens, because
"is there anything?" and "what is it?" are different questions:

| | |
|---|---|
| **DOCKET** | the overview. One word — ALL CLEAR, DUE SOON, OVERDUE — a count, and the most urgent item. Answerable from across the desk without reading. GREEN clears the top one; press opens ALERTS. |
| **ALERTS** | one reminder at a time, filling the screen. Dial pages, press completes, RED skips. |
| the interrupt | takes the screen when something arrives — unless you are in a focus session, in which case it is held and the queue drains the moment the session ends. Hands back after 20 s and re-nags, backing off 5 → 10 → 20 → 40 → 60 min. |

### Deadlines

Write the deadline into the message and Kea strips it out:

```
Call the landlord @18:00        today at 18:00 (tomorrow if that has passed)
Bins out @tomorrow 07:30        explicit
Take pill in 45m                relative — m / h / d
Renew insurance in 3d
```

With a deadline the urgency comes from the deadline (SCHEDULED → TODAY →
DUE SOON → DUE NOW → OVERDUE) rather than from how long ago you were
told. Without one it ages exactly as before (POSTED → BOARDING → FINAL
CALL → OVERDUE), so old reminders behave unchanged.

To change a deadline on the device: on ALERTS, flip the toggle to **SET
DUE** and the dial moves it in 15-minute steps instead of paging.

## Living worlds

Real Stuttgart weather (Open-Meteo, 15-min refresh) drives the scenes: rain and lightning in the neon city, gales ground the aerodrome zeppelin and hurry the clouds, and rain streaks down the conservatory glass. The machine also keeps long-term memory in `~/.kea_lifebook.json`: garden generations, specimen batches, telegraph characters, completed pomodoros, dispatches delivered and boots — summarised on the Nexus footer and written out in full on **the Logbook** (`L`), which also charts a week of focus sessions and tracks the next milestone.

## Kea's voice

Kea chirps. Every utterance is synthesised from scratch at startup — no sound files — as pitch-swept tones with vibrato, the astromech recipe. It speaks when things happen, from whichever screen you're on:

| Moment | Sound |
|---|---|
| Boot | `wake` — a pleased rising flourish |
| You change worlds | `blip` — soft acknowledgment |
| A dispatch arrives | `curious` — questioning trill |
| A reminder goes overdue | `worried` — falling warble (once per reminder) |
| You stamp one DONE | `happy` — bright chirp |
| Focus session ends | `focus_done`, or `proud` for a full cycle |
| Break ends | `focus_start` |
| Annunciator opens | `alarm` / `worried` / `question` by severity |

Press `M` to mute (there's a VOICE lamp on the Annunciator). `KEA_VOICE=0` disables it entirely, `KEA_VOICE_VOL=0.4` sets the level. Synthesis runs on a worker thread and adapts to the mixer's real sample rate; with no audio device every call becomes a silent no-op, so it can never take the display down. Utterances are rate-limited (0.35 s floor, 2.5 s per-phrase cooldown) so Kea stays charming rather than chatty.

The **Pomodoro** is an hourglass: sand drains in real time, the stream stops when you pause, and the instrument flips between sessions. Find **FOCUS** on Nexus. Amber for focus, green for rest; three brass studs count the cycle to the long rest. GREEN starts/holds, RED resets.
- `Esc` quits

**Rotary dial (KY-040) & toggle:**
- **Turn** — on Nexus, browses the instrument rail; in DRIFT and instruments with their own dial, adjusts that screen. It never silently switches screens.
- **Press** — on Nexus, enters the highlighted instrument; anywhere else, returns home
- **Toggle** — auto-pilot on/off (or voice mute with `KEA_TOGGLE_ROLE=mute`)
- Desktop stand-ins: `←`/`→` turn, `Enter` press, `T` toggle
- Not wired yet? `KEA_ENCODER=0` / `KEA_TOGGLE=0` keeps floating pins quiet

**Hardware Buttons:**
- **Blue Button:** BCM GPIO 21 (back to the screen that opened this one)
- **Red Button:** BCM GPIO 20 (the current screen's secondary action — reset in Focus)
- **Green Button:** BCM GPIO 26 (Assigned to action `3` / notification)
- **Home Button:** returns to Nexus

*(Note: Hardware buttons are tied to ground with pull-up resistors enabled)*
