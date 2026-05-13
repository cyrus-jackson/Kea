# INIT_RUN

This folder documents how to auto-run **Kea** on a Linux device (e.g., Raspberry Pi) at boot.

The repo is a Pygame “smart display” app. On the Pi you typically want it to launch automatically and restart if it crashes.

## Recommended: systemd runs the app directly (no `screen`)

This is the most robust approach: systemd supervises the Python process, captures logs, and handles restarts.

1) Pick a deploy location and user

- Example repo path: `/home/pi/Kea`
- Example user: `pi`

2) Create a service

```bash
sudo nano /etc/systemd/system/kea.service
```

Example (venv-based):

```ini
[Unit]
Description=Kea smart display
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Kea

# If you use a venv, point ExecStart at it.
# Create venv once:
#   python3 -m venv /home/pi/Kea/.venv
#   /home/pi/Kea/.venv/bin/pip install -r /home/pi/Kea/requirements.txt
ExecStart=/home/pi/Kea/.venv/bin/python /home/pi/Kea/src/main.py

Restart=on-failure
RestartSec=2

# Optional: if running headless framebuffer (no desktop), you may need:
# Environment=SDL_VIDEODRIVER=fbcon
# Environment=SDL_FBDEV=/dev/fb0

[Install]
WantedBy=multi-user.target
```

3) Enable + start

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kea.service
```

4) Check status + logs

```bash
sudo systemctl status kea.service
journalctl -u kea.service -f
```

## If you prefer `screen`: run Kea inside a named screen session

If you like attaching to a long-lived terminal session (e.g., `screen -r main`), you can have systemd start a detached `screen` that runs Kea.

### One-service approach (screen starts + launches app)

```bash
sudo nano /etc/systemd/system/kea-screen.service
```

```ini
[Unit]
Description=Kea inside GNU screen session
After=network.target

[Service]
Type=forking
User=pi
WorkingDirectory=/home/pi/Kea

# Starts a detached session named "main" that runs Kea.
# - Use bash -lc so PATH / profile is loaded if you rely on it.
ExecStart=/bin/bash -lc '/usr/bin/screen -S main -dm bash -lc "cd /home/pi/Kea && /home/pi/Kea/.venv/bin/python src/main.py"'

# Stop command to close the session cleanly.
ExecStop=/bin/bash -lc '/usr/bin/screen -S main -X quit'

Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Enable/start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kea-screen.service
```

Attach later:

```bash
screen -r main
```

Detach:

- Press `Ctrl+A`, then `D`

### Your existing `autoscreen.service`

You shared a service that ensures a `screen` session named `main` exists at boot:

```ini
[Unit]
Description=Start main screen session at boot
After=network.target

[Service]
Type=forking
User=pi
WorkingDirectory=/home/pi
ExecStart=/bin/bash -c '/usr/bin/screen -ls main | grep -q "No Sockets found" && /usr/bin/screen -dmS main'
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

That creates the session, but **does not start Kea** in it.

If you want to keep `autoscreen.service`, you still need to start Kea in that session, for example:

```bash
screen -S main -X stuff $'cd /home/pi/Kea && /home/pi/Kea/.venv/bin/python src/main.py\n'
```

In practice, it’s simpler to use the `kea-screen.service` example above so systemd both creates the session and launches the app.

## Common tweaks

- If Kea needs network availability before starting (e.g., for future features), consider `After=network-online.target` and `Wants=network-online.target`.
- If you’re running under a desktop session and need a display, you may need `Environment=DISPLAY=:0`.
- To restart after changing code: `sudo systemctl restart kea.service` (or `kea-screen.service`).
