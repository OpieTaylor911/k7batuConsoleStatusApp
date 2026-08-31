#!/usr/bin/env bash
# Run this ON THE UCONSOLE'S OWN DESKTOP (open a terminal from the desktop
# session itself, not over SSH) to capture why the app fails to start when
# launched from the desktop shortcut. It writes a full diagnostic bundle to
# ~/.local/share/k7bat-uconsole-status/debug-launch.log and prints it out.
set -uo pipefail

APP_PY="/home/bcaddy/uconsole-k7bat/app/k7bat-uconsole-status.py"
LOG_DIR="${HOME:-/home/bcaddy}/.local/share/k7bat-uconsole-status"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/debug-launch.log"

{
  echo "=== debug-launch $(date -Is) ==="
  echo "--- identity ---"
  id
  echo "--- session env ---"
  env | sort | grep -E '^(DISPLAY|WAYLAND_DISPLAY|XDG_|DBUS_|GDK_BACKEND|XAUTHORITY|DESKTOP_SESSION|XDG_SESSION_TYPE|HOME|USER)=' || true
  echo "--- loginctl session ---"
  loginctl show-session "$(loginctl | awk -v u="$(id -un)" '$3==u{print $1; exit}')" 2>/dev/null || true
  echo "--- compositor/wm processes ---"
  pgrep -af 'labwc|Xorg|weston|sway|kwin|gnome-shell|xfwm|openbox' || true
  echo "--- display sockets ---"
  ls -l /tmp/.X11-unix 2>/dev/null || true
  ls -l "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" 2>/dev/null || true
  echo "--- app file check ---"
  echo "APP_PY=$APP_PY"
  [ -f "$APP_PY" ] && echo "exists: yes" || echo "exists: NO"
  echo "--- python/gtk check ---"
  python3 --version 2>&1 || true
  python3 -c 'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk; print("GTK import OK", Gtk._version)' 2>&1 || true
  echo "--- desktop file ---"
  cat /usr/share/applications/k7bat-uconsole-status.desktop 2>/dev/null || true
  echo "--- launcher script ---"
  cat /usr/local/bin/k7bat-uconsole-status 2>/dev/null || true
  echo "--- direct launch attempt (10s timeout) ---"
  timeout 10s /usr/bin/python3 "$APP_PY"
  echo "direct launch exit code: $?"
} 2>&1 | tee "$LOG_FILE"

echo
echo "Full log saved to: $LOG_FILE"
