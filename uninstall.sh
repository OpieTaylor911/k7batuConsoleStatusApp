#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo ./uninstall.sh"
  exit 1
fi

rm -rf /opt/k7bat-uconsole-status
rm -f /usr/local/bin/k7bat-uconsole-status
if [[ -L /usr/local/bin/uconsole-dashboard ]]; then
  rm -f /usr/local/bin/uconsole-dashboard
fi
rm -f /usr/share/applications/k7bat-uconsole-status.desktop
rm -f /usr/share/icons/hicolor/scalable/apps/k7bat-uconsole-status.svg

for home in /home/* /root; do
  [[ -d "$home" ]] || continue
  rm -f "$home/Desktop/K7BAT-uConsole-Status-App.desktop" 2>/dev/null || true
done

gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
update-desktop-database /usr/share/applications >/dev/null 2>&1 || true

echo "K7BAT uConsole Status App removed."
echo "System packages and gpsd configuration were intentionally left in place."
