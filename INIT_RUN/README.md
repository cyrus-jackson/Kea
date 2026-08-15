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

# --- camera data collection (these two ARE read by Kea) ---
Environment=KEA_DATA_DIR=/home/pi/kea_data
Environment=KEA_TAGS_FILE=/home/pi/.kea_tags.json

ExecStart=/bin/bash -c '/usr/bin/screen -ls main | grep -q "No Sockets found" && /usr/bin/screen -dmS main'
# ...and actually start Kea in it. Without this you boot to an EMPTY
# screen session and have to type the run command by hand every time.
# The sleep gives X time to come up before SDL tries to open a window.
ExecStartPost=/bin/bash -c 'sleep 10; /home/pi/Kea/tools/kea start'
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable it so it runs at boot:

```bash
sudo systemctl daemon-reload
sudo systemctl enable autoscreen.service
```

> **No upload settings here.** Kea never reads `KEA_RCLONE_*` — only
> `tools/offload.py` does — so those live on the offload service (§ 3.5)
> where they belong. And no credentials live in any unit file: rclone
> keeps them itself (§ 3.8).

## 2. Running Kea — the `kea` command

Install the shortcut once:

```bash
sudo ln -sf ~/Kea/tools/kea /usr/local/bin/kea
```

Then, from anywhere:

```bash
kea              # start it if needed, then attach   (Ctrl-A then D to leave)
kea start        # start, don't attach
kea stop         # Ctrl-C into the session so GPIO/camera release cleanly
kea restart
kea status       # running? what's pending? is the offload timer alive?
kea attach       # just attach
kea log          # last 40 lines Kea printed
```

That replaces the two-step routine of:

```bash
screen -r main
cd /home/pi/Kea && SDL_AUDIODRIVER=pulseaudio python src/main.py
```

It creates the screen session if it's missing, refuses to start a second
copy, and sets `DISPLAY`, `SDL_AUDIODRIVER` and `XDG_RUNTIME_DIR` for you.

Overridable if your layout differs: `KEA_DIR` (default `~/Kea`),
`KEA_SCREEN` (default `main`), `KEA_PYTHON` (default `python3`).

<details>
<summary>Doing it by hand instead</summary>

```bash
screen -S main -X stuff $'cd /home/pi/Kea && SDL_AUDIODRIVER=pulseaudio python src/main.py\n'
```
</details>

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

## 3. Camera data → Backblaze B2 (one-time)

The camera screen writes approved shots to `~/kea_data/pending/`. A timer
moves them to cloud storage with `rclone move`, which deletes the local
copy **only after** a verified upload.

**Why B2 and not OneDrive:** rclone's OneDrive backend asks for
`Files.ReadWrite.All` — your entire drive. B2 application keys can be
locked to a **single bucket**, so the credential sitting on the Pi opens
one bucket of training images and nothing else. That's the point of the
feature, and it costs no extra effort. 10 GB free.

### 3.1 Make a bucket and a key scoped to it

On [backblaze.com](https://www.backblaze.com/) (B2 Cloud Storage):

1. **Create a bucket** — name it e.g. `kea-data`, set it **Private**.
2. **App Keys → Add a New Application Key**:
   - Name: `kea-pi`
   - **Allow access to Bucket(s): `kea-data`** ← the important bit; do
     *not* leave it on "All"
   - Capabilities: tick **listFiles, readFiles, writeFiles, deleteFiles**
     (delete is needed for `move` to clean up; drop it and use `copy`
     instead if you'd rather the key can't delete)
3. Copy the **keyID** and **applicationKey** — the secret is shown **once**.

### 3.2 Configure rclone on the Pi

```bash
sudo apt install rclone
rclone config
#  n) New remote
#  name> b2
#  Storage> b2
#  account> <your keyID>
#  key>     <your applicationKey>
#  hard_delete> false        (keeps a version history; true deletes outright)
#  ... accept the rest ...
```

No browser, no OAuth, no Azure — B2 uses plain keys, so this works fine
headless. Prove it:

```bash
rclone lsd b2:kea-data       # should succeed and list nothing yet
```

Then point Kea at it:

```bash
export KEA_RCLONE_REMOTE=b2
export KEA_RCLONE_PATH=kea-data/images
```

### 3.3 (Recommended) encrypt before upload

These are photos of you and your home. `rclone crypt` encrypts filenames
and contents **on the Pi**, so Backblaze stores only noise:

```bash
rclone config
#  n) New remote  ->  name> b2_enc  ->  Storage> crypt
#  remote> b2:kea-data/images
#  filename_encryption> standard ; set two passwords
```

```bash
export KEA_RCLONE_REMOTE=b2_enc
export KEA_RCLONE_PATH=""
```

> Save those passwords somewhere safe. Without them the images cannot be
> recovered — which is exactly what makes it worth doing.

### 3.4 Upload manually first

```bash
python3 tools/offload.py --status     # what's waiting locally
python3 tools/offload.py --dry-run    # what would move
python3 tools/offload.py              # actually move it
```

### 3.5 Run it on a timer

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/kea-offload.service <<'EOF'
[Unit]
Description=Upload Kea camera data
After=network-online.target

[Service]
Type=oneshot
Environment=KEA_DATA_DIR=%h/kea_data
Environment=KEA_RCLONE_REMOTE=b2_enc
Environment=KEA_RCLONE_PATH=
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
systemctl --user list-timers | grep kea
```

Offline or the remote unreachable? The script says so and **leaves the
files alone** — they go next time. At ~180 KB a shot, a backlog is
harmless.

### 3.6 Switching backends later

`offload.py` only ever calls `rclone move <local> <remote>:<path>`, so any
rclone backend works with **no code change** — just the two env vars.
Google Drive, S3, an SFTP box, your Mac: `KEA_RCLONE_REMOTE` and
`KEA_RCLONE_PATH` are the whole interface.

### 3.7 Tags

Tags live in `~/.kea_tags.json`, created on first run as
`["me", "empty", "other"]`. Edit it freely:

```bash
nano ~/.kea_tags.json      # add "night", "two_people", "glasses", ...
```

Kea re-reads it every time you open the camera screen — no restart.
Images already saved keep the tag they were shot with, so adding tags
never invalidates data you've already collected.

### 3.8 Credentials — rclone keeps them, nothing else needs to

**Nothing goes in any unit file, and there is no secrets file.** When you
create the `b2` and `b2_enc` remotes, `rclone config` writes the B2 key
and both crypt passwords into:

```
~/.config/rclone/rclone.conf
```

which rclone creates **0600 — readable only by you**. `offload.py` runs as
`pi`, rclone finds that file, and it works. That's why the offload service
sets only *which* remote to use, never how to open it.

Confirm the permissions once:

```bash
ls -l ~/.config/rclone/rclone.conf     # want: -rw------- 1 pi pi
chmod 600 ~/.config/rclone/rclone.conf # if it isn't
```

**Be clear-eyed about what that does and doesn't give you.** By default
rclone stores passwords *obscured*, which is reversible — `rclone reveal`
turns them back into plaintext. It stops a shoulder-surfer, not anyone
who can read the file. **The 0600 permission is the actual protection**,
so the meaningful risks are: someone with root on the Pi, someone who
takes the SD card, or an unencrypted backup of your home directory.

For a desk companion on your own network that's a reasonable place to
land — and note the two layers you already have:

- the B2 key only opens **one bucket** (§ 3.1), so a stolen key can't
  reach anything else you own
- `b2_enc` encrypts **before** upload, so Backblaze only ever holds
  ciphertext

**Want the config itself encrypted at rest?** rclone can do that:

```bash
rclone config      # then:  s) Set configuration password
```

The whole file becomes unreadable without the password — but every
non-interactive run then needs `RCLONE_CONFIG_PASS`, so the timer would
need that password stored *somewhere*, and you're back to protecting a
file with 0600. It genuinely helps against a stolen SD card; it doesn't
help against someone who already has your user account. Worth it if the
Pi travels, overkill if it lives on your desk.

Check what a unit will really run with:

```bash
systemctl show autoscreen.service -p Environment
systemctl --user show kea-offload.service -p Environment
```

Neither should ever print a password.

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
