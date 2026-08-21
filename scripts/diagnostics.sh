#!/usr/bin/env bash
set +e
echo "K7BAT uConsole Status App - Diagnostics"
echo "======================================="
echo
echo "OS:"
cat /etc/os-release 2>/dev/null | grep -E '^(PRETTY_NAME|VERSION_CODENAME)='
echo
echo "Hardware:"
tr -d '\0' </proc/device-tree/model 2>/dev/null; echo
echo
echo "GUI sessions:"
loginctl list-sessions 2>/dev/null
echo
echo "Wayland:"
ls -l /run/user/*/wayland-* 2>/dev/null
echo
echo "AIO controller:"
command -v aiov2_ctl || true
aiov2_ctl --help 2>/dev/null | head -40
echo
echo "Network:"
ip -br link
echo
echo "Wi-Fi:"
iw dev
echo
echo "Drivers:"
for i in /sys/class/net/wlan*; do
  [[ -e "$i" ]] || continue
  n="$(basename "$i")"
  echo "--- $n ---"
  ethtool -i "$n" 2>/dev/null
done
echo
echo "USB:"
lsusb
echo
echo "GPSD:"
systemctl status gpsd --no-pager -l 2>/dev/null
echo
echo "GPS sample:"
timeout 3 gpspipe -w -n 8 2>/dev/null
echo
echo "readsb:"
systemctl status readsb --no-pager -l 2>/dev/null

exit 0
