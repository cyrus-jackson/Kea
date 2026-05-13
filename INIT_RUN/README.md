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
ExecStart=/bin/bash -c '/usr/bin/screen -ls main | grep -q "No Sockets found" && /usr/bin/screen -dmS main'
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## 2. Running Kea inside the screen session

Once the service creates the screen session, you have to run Kea inside of it.

Pass the start command to the screen session:

```bash
screen -S main -X stuff $'cd /home/pi/Kea && python src/main.py\n'
```

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
