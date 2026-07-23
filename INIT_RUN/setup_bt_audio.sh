#!/bin/bash
# ============================================================
# Kea — make a Bluetooth speaker auto-connect on boot and become
# the default audio output. Run ONCE on the Pi:
#
#     bash INIT_RUN/setup_bt_audio.sh                 # uses the JBL Go 4
#     bash INIT_RUN/setup_bt_audio.sh AA:BB:CC:DD:EE:FF   # another speaker
#
# It: trusts + connects the speaker, tells PulseAudio to switch to a
# speaker whenever it connects, and installs a small user service that
# keeps it connected (and reconnects if it drops).
# ============================================================
set -e
MAC="${1:-E8:26:CF:E5:FE:45}"          # default: your JBL Go 4
echo "Bluetooth speaker: $MAC"

# 1) trust (permanent) + connect now
bluetoothctl trust "$MAC"
bluetoothctl connect "$MAC" || true

# 2) PulseAudio: auto-switch to a speaker when it connects
mkdir -p "$HOME/.config/pulse"
[ -f "$HOME/.config/pulse/default.pa" ] || cp /etc/pulse/default.pa "$HOME/.config/pulse/default.pa"
grep -q module-switch-on-connect "$HOME/.config/pulse/default.pa" || \
  echo "load-module module-switch-on-connect" >> "$HOME/.config/pulse/default.pa"
pulseaudio -k || true                  # restart PulseAudio (respawns)

# 3) keep-connected loop
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/kea-bt-speaker.sh" <<EOF
#!/bin/bash
MAC=$MAC
while true; do
  bluetoothctl info "\$MAC" | grep -q "Connected: yes" || bluetoothctl connect "\$MAC"
  sleep 15
done
EOF
chmod +x "$HOME/.local/bin/kea-bt-speaker.sh"

# 4) user service that runs it on login/boot
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/kea-bt-speaker.service" <<EOF
[Unit]
Description=Keep Kea's Bluetooth speaker connected
After=bluetooth.target

[Service]
ExecStart=$HOME/.local/bin/kea-bt-speaker.sh
Restart=always

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now kea-bt-speaker.service
sudo loginctl enable-linger "$USER" || true   # run even before a GUI login

echo
echo "Done. Reboot to test — the speaker should connect on its own and grab the audio."
