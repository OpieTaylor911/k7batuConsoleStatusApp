#!/usr/bin/env bash
set -euo pipefail

APP_NAME="K7BAT uConsole Status App"
APP_ID="k7bat-uconsole-status"
PREFIX="/opt/$APP_ID"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo ./install.sh"
  exit 1
fi

log(){ printf '\n==> %s\n' "$*"; }
ok(){ printf '[OK] %s\n' "$*"; }
warn(){ printf '[WARN] %s\n' "$*" >&2; }

detect_gui_user() {
  if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]] && id "$SUDO_USER" >/dev/null 2>&1; then
    echo "$SUDO_USER"; return
  fi

  local u
  while read -r session uid user seat rest; do
    [[ "$uid" =~ ^[0-9]+$ ]] || continue
    if (( uid >= 1000 && uid < 65534 )) && id "$user" >/dev/null 2>&1; then
      if loginctl show-session "$session" -p Type -p Class 2>/dev/null | grep -Eq 'Type=(wayland|x11)|Class=user'; then
        echo "$user"; return
      fi
    fi
  done < <(loginctl list-sessions --no-legend 2>/dev/null || true)

  getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 && $7 !~ /(nologin|false)$/ {print $1; exit}'
}

GUI_USER="$(detect_gui_user || true)"
if [[ -z "$GUI_USER" ]]; then
  warn "No desktop user detected. Application will still be installed system-wide."
else
  GUI_HOME="$(getent passwd "$GUI_USER" | cut -d: -f6)"
  GUI_UID="$(id -u "$GUI_USER")"
  ok "Desktop user: $GUI_USER"
fi

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  ok "OS: ${PRETTY_NAME:-unknown}"
fi
if [[ -r /proc/device-tree/model ]]; then
  MODEL="$(tr -d '\0' </proc/device-tree/model)"
  ok "Hardware: $MODEL"
fi

log "Installing required packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update

REQUIRED=(
  python3
  python3-gi
  gir1.2-gtk-3.0
  librtaudio7
  gpsd
  gpsd-clients
  iproute2
  iw
  ethtool
  bluez
  procps
  usbutils
  desktop-file-utils
  libglib2.0-bin
)

for pkg in "${REQUIRED[@]}"; do
  if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
    ok "$pkg already installed"
  elif apt-cache show "$pkg" >/dev/null 2>&1; then
    apt-get install -y "$pkg"
  else
    warn "$pkg is not available in configured repositories"
  fi
done

if [[ -f "$SCRIPT_DIR/scripts/install-sdrpp-fixes.sh" ]]; then
  log "Applying SDR++ compatibility fixes"
  bash "$SCRIPT_DIR/scripts/install-sdrpp-fixes.sh" || warn "SDR++ fix script returned a warning"
fi

log "Installing application"
mkdir -p "$PREFIX"
install -m 0755 "$SCRIPT_DIR/app/k7bat-uconsole-status.py" "$PREFIX/k7bat-uconsole-status.py"
if [ -f "$SCRIPT_DIR/assets/plugins.default.json" ]; then
  install -m 0644 "$SCRIPT_DIR/assets/plugins.default.json" "$PREFIX/plugins.default.json"
fi
if [ -f "$SCRIPT_DIR/assets/k7bat-callsign-logo.png" ]; then
  install -m 0644 "$SCRIPT_DIR/assets/k7bat-callsign-logo.png" "$PREFIX/k7bat-callsign-logo.png"
fi
if [ -f "$SCRIPT_DIR/assets/k7bat-callsign-logo.svg" ]; then
  install -m 0644 "$SCRIPT_DIR/assets/k7bat-callsign-logo.svg" "$PREFIX/k7bat-callsign-logo.svg"
fi
if [ -d "$SCRIPT_DIR/assets/icons" ]; then
  mkdir -p "$PREFIX/icons"
  find "$SCRIPT_DIR/assets/icons" -maxdepth 1 -type f -name '*.svg' -exec install -m 0644 {} "$PREFIX/icons/" \;
fi
install -m 0755 "$SCRIPT_DIR/scripts/k7bat-uconsole-status" /usr/local/bin/k7bat-uconsole-status
install -m 0755 "$SCRIPT_DIR/scripts/find-gps-apps.sh" /usr/local/bin/find-gps-apps
ln -sfn /usr/local/bin/k7bat-uconsole-status /usr/local/bin/uconsole-dashboard

install -m 0644 "$SCRIPT_DIR/assets/k7bat-uconsole-status.svg" \
  /usr/share/icons/hicolor/scalable/apps/k7bat-uconsole-status.svg
tr -d '\r' < "$SCRIPT_DIR/assets/k7bat-uconsole-status.desktop" \
  > /usr/share/applications/k7bat-uconsole-status.desktop
chmod 0644 /usr/share/applications/k7bat-uconsole-status.desktop

if [[ -n "${GUI_USER:-}" ]]; then
  log "Configuring passwordless service control for $GUI_USER"
  SUDOERS_FILE="/etc/sudoers.d/90-k7bat-uconsole-status"
  TMP_SUDOERS="$(mktemp)"
  cat >"$TMP_SUDOERS" <<EOF
Cmnd_Alias K7BAT_STATUS_CMDS = /bin/systemctl, /usr/bin/systemctl
$GUI_USER ALL=(root) NOPASSWD: K7BAT_STATUS_CMDS
EOF
  chmod 0440 "$TMP_SUDOERS"
  if visudo -cf "$TMP_SUDOERS" >/dev/null 2>&1; then
    install -m 0440 "$TMP_SUDOERS" "$SUDOERS_FILE"
    ok "Installed sudoers policy: $SUDOERS_FILE"
  else
    warn "sudoers validation failed; skipping passwordless service control setup"
  fi
  rm -f "$TMP_SUDOERS"
fi

gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
update-desktop-database /usr/share/applications >/dev/null 2>&1 || true

if [[ -n "${GUI_USER:-}" ]]; then
  log "Creating desktop shortcut"
  DESKTOP_DIR="$GUI_HOME/Desktop"
  SYSTEM_DESKTOP_FILE="/usr/share/applications/k7bat-uconsole-status.desktop"
  USER_DESKTOP_FILE="$DESKTOP_DIR/K7BAT-uConsole-Status-App.desktop"
  if command -v xdg-user-dir >/dev/null 2>&1; then
    FOUND="$(sudo -u "$GUI_USER" HOME="$GUI_HOME" xdg-user-dir DESKTOP 2>/dev/null || true)"
    [[ -n "$FOUND" ]] && DESKTOP_DIR="$FOUND"
    USER_DESKTOP_FILE="$DESKTOP_DIR/K7BAT-uConsole-Status-App.desktop"
  fi
  mkdir -p "$DESKTOP_DIR"
  rm -f "$USER_DESKTOP_FILE"
  ln -s "$SYSTEM_DESKTOP_FILE" "$USER_DESKTOP_FILE"
  chown -h "$GUI_USER:$GUI_USER" "$USER_DESKTOP_FILE"

  if [[ -S "/run/user/$GUI_UID/bus" ]]; then
    sudo -u "$GUI_USER" \
      XDG_RUNTIME_DIR="/run/user/$GUI_UID" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$GUI_UID/bus" \
      gio set "$USER_DESKTOP_FILE" metadata::trusted true \
      >/dev/null 2>&1 || true
  fi
fi

log "Checking optional HackerGadgets integration"
if command -v aiov2_ctl >/dev/null 2>&1; then
  ok "aiov2_ctl detected: $(command -v aiov2_ctl)"
else
  warn "aiov2_ctl not detected. Dashboard works, but AIO radio controls will be unavailable."
fi

log "GPS setup"
# Preserve an existing gpsd configuration if it already names a device.
EXISTING_GPSD="$(grep -E '^DEVICES=' /etc/default/gpsd 2>/dev/null | sed -E 's/^DEVICES="?(.*?)"?$/\1/' || true)"
if [[ -n "$EXISTING_GPSD" ]]; then
  ok "gpsd already configured: $EXISTING_GPSD"
else
  GPS_DEV=""
  # On CM5/AIO V2 ttyAMA0 is common. Only configure after observing NMEA.
  for dev in /dev/ttyAMA0 /dev/ttyAMA1 /dev/ttyAMA10 /dev/ttyUSB0 /dev/ttyACM0; do
    [[ -c "$dev" ]] || continue
    SAMPLE="$(timeout 2 sh -c "stty -F '$dev' 9600 raw -echo 2>/dev/null; head -n 12 < '$dev'" 2>/dev/null || true)"
    if printf '%s\n' "$SAMPLE" | grep -Eq '^\$(GP|GN|GL|GA|GB)'; then
      GPS_DEV="$dev"; break
    fi
  done

  if [[ -n "$GPS_DEV" ]]; then
    cp -a /etc/default/gpsd "/etc/default/gpsd.k7bat-backup.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
    cat >/etc/default/gpsd <<EOF
START_DAEMON="true"
USBAUTO="false"
DEVICES="$GPS_DEV"
GPSD_OPTIONS="-n"
OPTIONS=""
EOF
    systemctl enable gpsd.socket >/dev/null 2>&1 || true
    systemctl restart gpsd.socket >/dev/null 2>&1 || true
    systemctl restart gpsd >/dev/null 2>&1 || true
    ok "Configured gpsd for detected NMEA device: $GPS_DEV"
  else
    warn "No live NMEA serial stream detected. gpsd installed but existing configuration was left alone."
    warn "If using HackerGadgets AIO V2, enable GPS and configure its UART later."
  fi
fi

log "Installation complete"
echo
echo "$APP_NAME is installed."
echo "Start-menu entry: $APP_NAME"
if [[ -n "${GUI_USER:-}" ]]; then
  echo "Desktop user: $GUI_USER"
fi
echo
echo "Run manually from a graphical terminal with:"
echo "  k7bat-uconsole-status"
echo
echo "Optional application buttons light up automatically when those tools are installed."

# K7BAT GPS / Navigation Suite
if [[ -x "$SCRIPT_DIR/scripts/install-k7bat-gps-nav-suite.sh" ]]; then
    "$SCRIPT_DIR/scripts/install-k7bat-gps-nav-suite.sh"
fi
