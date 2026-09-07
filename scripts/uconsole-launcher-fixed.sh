#!/usr/bin/env bash
# Do not use `set -e` here: it would abort before we can log a failure's exit code.
set -uo pipefail

APP_PY="/home/bcaddy/uconsole-k7bat/app/k7bat-uconsole-status.py"
LOG_DIR="/home/bcaddy/.local/share/k7bat-uconsole-status"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/launcher.log"

{
  echo "=== launcher start $(date -Is) ==="
  echo "USER=${USER:-$(id -un)}"
  echo "HOME=${HOME:-/home/bcaddy}"
  echo "PWD=${PWD}"
  echo "ARGV=$*"
  echo "APP_PY=$APP_PY"
  echo "APP_PY exists: $([ -f "$APP_PY" ] && echo yes || echo NO)"
  echo "python3: $(command -v python3 2>&1 || echo NOT_FOUND)"
  echo "python3 --version: $(python3 --version 2>&1 || true)"
  echo "python3 gi module: $(python3 -c 'import gi; print(gi.__file__)' 2>&1 || true)"
  env | sort | grep -E '^(DISPLAY|WAYLAND_DISPLAY|XDG_|DBUS_|GDK_BACKEND|XAUTHORITY|DESKTOP_SESSION|XDG_SESSION_TYPE)=' || true
} >> "$LOG_FILE" 2>&1

# Try to get DISPLAY from bcaddy's environment
if [ -z "${DISPLAY:-}" ]; then
  # Check if we can get display from bcaddy's session
  if [ -f /tmp/.X11-unix/X0 ] || [ -d /run/user/1000 ]; then
    export DISPLAY=":0"
    export GDK_BACKEND="x11"
  fi
fi

if [ -n "${WAYLAND_DISPLAY:-}" ]; then
  export GDK_BACKEND=wayland
elif [ -n "${DISPLAY:-}" ]; then
  export GDK_BACKEND=x11
fi

# Run as bcaddy user with correct environment
su - bcaddy -c "DISPLAY=${DISPLAY:-:0} GDK_BACKEND=${GDK_BACKEND:-x11} /usr/bin/python3 $APP_PY" >> "$LOG_FILE" 2>&1
status=$?
echo "=== launcher exit code=$status at $(date -Is) ===" >> "$LOG_FILE" 2>&1
exit "$status"
