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

The app boots into **NEXUS**, the home hub: clock, System Protocol greeting, live weather, and **every screen as a card on a 4×3 rail**. It recommends a world for the current **day phase** — garden at sunrise → neon city for work → weather at lunch → orbital afternoons → aerodrome → telegraph at dusk → bio-lab evenings → starport at night → the abyss after 23:00 — with a rain override and a docket override when reminders go overdue. Press `A` on the hub to enable **auto-pilot**: Nexus dispatches to the recommended world automatically.

Run `python3 tools/smoke_test.py` after changes: it renders every state headlessly and verifies each Nexus card and day phase points at a registered state.

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
- `R` dispatch docket (your phone reminders as aging paper cards)
- `O` the orrery (clockpunk — live 3D solar system at today's real planetary positions)
- `S` starport bay 94 (twin-sun desert dock; dispatches arrive as a hologram)
- `L` the logbook (the machine's own history, kept in ink)

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
- **Turn** — on Nexus, browses the world rail; anywhere else, tunes straight through the worlds like a radio dial
- **Press** — on Nexus, enters the highlighted world; anywhere else, returns home
- **Toggle** — auto-pilot on/off (or voice mute with `KEA_TOGGLE_ROLE=mute`)
- Desktop stand-ins: `←`/`→` turn, `Enter` press, `T` toggle
- Not wired yet? `KEA_ENCODER=0` / `KEA_TOGGLE=0` keeps floating pins quiet

**Hardware Buttons:**
- **Blue Button:** BCM GPIO 21 (Cycles through all available states)
- **Red Button:** BCM GPIO 20 (Assigned to action `2` / pomodoro)
- **Green Button:** BCM GPIO 26 (Assigned to action `3` / notification)

*(Note: Hardware buttons are tied to ground with pull-up resistors enabled)*
