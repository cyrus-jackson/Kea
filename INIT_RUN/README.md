# INIT_RUN

This document explains how to auto-run **Kea** on a Linux device (e.g., Raspberry Pi) at boot using your `autoscreen.service`.

## 1. The autoscreen service

This service ensures a `screen` session named `main` exists at boot. 

```bash
sudo nano /etc/systemd/system/autoscreen.service
```

```ini
[Unit]
Description=Start main screen session at boot
After=network.target

[Service]
Type=forking
User=pi
WorkingDirectory=/home/pi
Environment=DISPLAY=:0
Environment=KEA_ROTATION=90
Environment=SDL_AUDIODRIVER=pulseaudio
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=KEA_START_VOLUME=20
ExecStart=/bin/bash -c '/usr/bin/screen -ls main | grep -q "No Sockets found" && /usr/bin/screen -dmS main'
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## 2. Running Kea inside the screen session

Once the service creates the screen session, you have to run Kea inside of it.

Pass the start command to the screen session:

```bash
screen -S main -X stuff $'cd /home/pi/Kea && SDL_AUDIODRIVER=pulseaudio python src/main.py\n'
```

`SDL_AUDIODRIVER=pulseaudio` forces pygame's audio through PulseAudio so Kea's
voice lands on the default sink — i.e. the Bluetooth speaker (see §3). It's also
set on the service above; here on the run line it's belt-and-suspenders.

**Silent over `screen`/SSH but fine on the Pi's own desktop?** The screen session
(created by the *system* service) has no `XDG_RUNTIME_DIR`, so SDL can't find the
running PulseAudio. `main.py` now sets `XDG_RUNTIME_DIR=/run/user/<uid>`
automatically when that dir exists, and the service sets it explicitly — but if
you launch by hand in an old screen, `export XDG_RUNTIME_DIR=/run/user/1000`
first. (That dir persists across boots because you ran `loginctl enable-linger`
in §3.)

## Manual Test Controls (Buttons)

If you have a keyboard attached to the Raspberry Pi or are forwarding inputs across SSH/screen, you can use these manual controls to test the states:
- `1` - Ambient
- `2` - Pomodoro
- `3` - Notification
- `4` - Street
- `5` - Cloud City
- `6` - Telegraph
- `7` - Airship Dock
- `Esc` - Quits

## Common commands

- **Enable and run at boot:** `sudo systemctl enable --now autoscreen.service`
- **Attach to view the output:** `screen -r main`
- **Detach from screen:** Press `Ctrl+A`, then `D`

## 3. Camera data → OneDrive (one-time)

The camera screen writes approved shots to `~/kea_data/pending/`. A timer
then moves them to OneDrive with `rclone move`, which deletes the local
copy **only after** a verified upload.

### 3.1 Install and authorise rclone

```bash
sudo apt install rclone
```

**The headless catch:** `rclone config` wants a browser, and the Pi hasn't
got a usable one. Do the OAuth on your Mac instead:

```bash
# ON YOUR MAC (rclone installed there too):
rclone authorize "onedrive"
# a browser opens; sign in; it prints a long token — copy the whole thing
```

Then on the Pi:

```bash
rclone config
#  n) New remote
#  name> onedrive
#  Storage> onedrive
#  ... accept defaults ...
#  Use auto config? > n          <-- IMPORTANT, say NO
#  paste the token from your Mac
#  choose your drive (usually 1: OneDrive Personal)
```

Prove it works — this must list your OneDrive folders:

```bash
rclone lsd onedrive:
```

### 3.2 (Recommended) encrypt before upload

These are photos of you and your home. `rclone crypt` encrypts filenames
and contents on the Pi, so OneDrive only ever stores noise:

```bash
rclone config
#  n) New remote  ->  name> onedrive_enc  ->  Storage> crypt
#  remote> onedrive:KeaData
#  encrypt filenames> standard ; set two passwords (keep them safe!)
```

Then point Kea at the encrypted remote:

```bash
export KEA_RCLONE_REMOTE=onedrive_enc
export KEA_RCLONE_PATH=""
```

> Keep those passwords somewhere safe. Lose them and the images are
> unrecoverable — that's the whole point of it.

### 3.3 Upload manually first

```bash
python3 tools/offload.py --status     # what's waiting
python3 tools/offload.py --dry-run    # what would move
python3 tools/offload.py              # actually move it
```

### 3.4 Run it on a timer

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/kea-offload.service <<'EOF'
[Unit]
Description=Upload Kea camera data to OneDrive
After=network-online.target

[Service]
Type=oneshot
Environment=KEA_RCLONE_REMOTE=onedrive
Environment=KEA_RCLONE_PATH=KeaData
ExecStart=/usr/bin/python3 %h/Kea/tools/offload.py --quiet
EOF

cat > ~/.config/systemd/user/kea-offload.timer <<'EOF'
[Unit]
Description=Upload Kea camera data hourly

[Timer]
OnBootSec=10min
OnUnitActiveSec=1h
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now kea-offload.timer
systemctl --user list-timers | grep kea      # confirm it's scheduled
```

Offline or OneDrive unreachable? The script says so and **leaves the files
alone** — they go next time. At ~180 KB a shot, a backlog is harmless.

### 3.5 Tags

Tags live in `~/.kea_tags.json`, created on first run as
`["me", "empty", "other"]`. Edit it freely:

```bash
nano ~/.kea_tags.json      # e.g. add "night", "two_people", "glasses"
```

Kea re-reads the file every time you open the camera screen — no restart.
Images already saved keep the tag they were shot with, so adding tags
never invalidates data you've already collected.

## 4. Bluetooth speaker (auto-connect on boot)

Kea speaks and beeps through the default audio output. To send that to a
Bluetooth speaker (e.g. the JBL Go 4) automatically — so you never re-pair or
re-connect it — pair it once, then run the setup script **once**:

```bash
# pair it first (only needed once, ever):
bluetoothctl
# > power on
# > scan on            (wait for your speaker, note its MAC AA:BB:CC:DD:EE:FF)
# > pair AA:BB:CC:DD:EE:FF
# > exit

# then install auto-connect (default MAC is the JBL Go 4):
bash INIT_RUN/setup_bt_audio.sh                    # or pass a different MAC:
bash INIT_RUN/setup_bt_audio.sh AA:BB:CC:DD:EE:FF
```

The script trusts the speaker, tells PulseAudio to switch to it on connect
(`module-switch-on-connect`), and installs a small **user service**
(`kea-bt-speaker.service`) that keeps it connected and reconnects if it drops.
After running it, reboot and just switch the speaker on — it connects within
~15 s and grabs the audio.

**If Kea's voice doesn't come out of it** (but `paplay` does): pygame is talking
to ALSA directly — launch Kea with `SDL_AUDIODRIVER=pulseaudio` (add it to the
`Environment=` lines of `autoscreen.service`, or the run command).

Useful checks:

- `systemctl --user status kea-bt-speaker.service` — is the keep-alive running
- `pactl list sinks short` — is the `bluez_sink...a2dp_sink` present
- `bluetoothctl info AA:BB:CC:DD:EE:FF` — `Connected: yes` / `Trusted: yes`
