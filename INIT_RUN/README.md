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

## 3. Bluetooth speaker (auto-connect on boot)

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
