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

Instruments:
- `H` nexus (home hub)
- `2` pomodoro · `3` notification · `6` telegraph · `8` climate · `9` greetings
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

These are **journeys**, not stop departures, and they have to be. Two of the
three can't be expressed as "departures from Universität filtered by
destination": the 748 to Max-Planck says *Ostelsheim* on the front, and the
S-Bahn into town shows a dozen different terminus names through the day.
Filtering on those strings is guesswork, so Kea asks the journey planner the
question you're actually asking. You get arrival time, duration and change
count, which a platform board can't tell you.

The dial switches routes, GREEN refreshes, and the toggle unfolds the legs of
the journey you're about to take (`15:32 S1 → Vaihingen, walk, 15:40 bus 84`).

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

## Reminders from your phone (the Dispatch Docket)

Kea polls a free [ntfy.sh](https://ntfy.sh) topic every 30 s — set `KEA_NTFY_TOPIC` to something unguessable. Post from anywhere:

```bash
curl -d "water the plants" https://ntfy.sh/<your-topic>
```

On iOS, a Shortcuts automation ("When my Reminder is due → Get Contents of URL, POST, body = reminder name") forwards your phone reminders automatically; on Android the ntfy app's share sheet or Tasker does it. Cards age through POSTED → BOARDING → FINAL CALL → OVERDUE; the **green button stamps the oldest one DONE**. Overdue dockets nag you from every world's ticker and take over the Nexus NOW slot until handled.

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

The **Pomodoro** (`2`) is an hourglass: sand drains in real time, the stream stops when you pause, and the instrument flips between sessions. Amber for focus, green for rest; three brass studs count the cycle to the long rest. GREEN starts/holds, RED resets.
- `Esc` quits

**Rotary dial (KY-040) & toggle:**
- **Turn** — on Nexus, browses the instrument rail; in DRIFT, walks the circuit by hand; anywhere else, tunes through the screens like a radio dial
- **Press** — on Nexus, enters the highlighted world; anywhere else, returns home
- **Toggle** — auto-pilot on/off (or voice mute with `KEA_TOGGLE_ROLE=mute`)
- Desktop stand-ins: `←`/`→` turn, `Enter` press, `T` toggle
- Not wired yet? `KEA_ENCODER=0` / `KEA_TOGGLE=0` keeps floating pins quiet

**Hardware Buttons:**
- **Blue Button:** BCM GPIO 21 (Cycles through all available states)
- **Red Button:** BCM GPIO 20 (Assigned to action `2` / pomodoro)
- **Green Button:** BCM GPIO 26 (Assigned to action `3` / notification)

*(Note: Hardware buttons are tied to ground with pull-up resistors enabled)*
