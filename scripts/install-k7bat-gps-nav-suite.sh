#!/usr/bin/env bash
set -euo pipefail

log(){ printf "\n==> %s\n" "$*"; }
ok(){ printf "[OK] %s\n" "$*"; }
warn(){ printf "[WARN] %s\n" "$*" >&2; }

usage() {
  cat <<'EOF'
Usage: sudo ./scripts/install-k7bat-gps-nav-suite.sh [options]

Options:
  --non-interactive        Do not prompt; use --apps values only.
  --apps LIST              Comma-separated app list: pure,organic,navit,osm
  --status-default ID      Status app default: puremaps,organicmaps,navit,osmscoutserver
  --no-status-default      Skip writing status app settings.json
  -h, --help               Show help

Examples:
  sudo ./scripts/install-k7bat-gps-nav-suite.sh
  sudo ./scripts/install-k7bat-gps-nav-suite.sh --apps pure,organic,osm
  sudo ./scripts/install-k7bat-gps-nav-suite.sh --non-interactive --apps navit --status-default navit
EOF
}

[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }

detect_gui_user() {
  if [[ -n "${K7BAT_GUI_USER:-}" ]] && id "$K7BAT_GUI_USER" >/dev/null 2>&1; then
    echo "$K7BAT_GUI_USER"; return
  fi
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]] && id "$SUDO_USER" >/dev/null 2>&1; then
    echo "$SUDO_USER"; return
  fi
  loginctl list-sessions --no-legend 2>/dev/null | awk '$2 >= 1000 {print $3; exit}'
}

GUI_USER="$(detect_gui_user || true)"
if [[ -z "${GUI_USER}" ]]; then
  warn "Could not detect GUI user. Set K7BAT_GUI_USER=username"
  exit 1
fi
GUI_HOME="$(getent passwd "$GUI_USER" | cut -d: -f6)"

NON_INTERACTIVE=0
APPS_RAW=""
SET_STATUS_DEFAULT=1
STATUS_DEFAULT=""

for arg in "$@"; do
  case "$arg" in
    --non-interactive) NON_INTERACTIVE=1 ;;
    --apps=*) APPS_RAW="${arg#*=}" ;;
    --apps) warn "Use --apps=pure,organic,navit,osm"; exit 1 ;;
    --status-default=*) STATUS_DEFAULT="${arg#*=}" ;;
    --no-status-default) SET_STATUS_DEFAULT=0 ;;
    -h|--help) usage; exit 0 ;;
    *) warn "Unknown option: $arg"; usage; exit 1 ;;
  esac
done

SEL_PURE=0
SEL_ORGANIC=0
SEL_NAVIT=0
SEL_OSM=0

normalize_apps() {
  local list="$1"
  IFS=',' read -r -a items <<< "$list"
  for item in "${items[@]}"; do
    app="$(echo "$item" | tr '[:upper:]' '[:lower:]' | xargs)"
    case "$app" in
      pure) SEL_PURE=1 ;;
      organic) SEL_ORGANIC=1 ;;
      navit) SEL_NAVIT=1 ;;
      osm|osmscout|osmscoutserver) SEL_OSM=1 ;;
      "") ;;
      *) warn "Unknown app in --apps: $item" ;;
    esac
  done
}

ask_yes() {
  local prompt="$1"
  local default_yes="$2"
  local ans=""
  if [[ "$NON_INTERACTIVE" -eq 1 ]]; then
    if [[ "$default_yes" -eq 1 ]]; then return 0; else return 1; fi
  fi
  if [[ "$default_yes" -eq 1 ]]; then
    read -r -p "$prompt [Y/n]: " ans || true
    ans="${ans:-Y}"
  else
    read -r -p "$prompt [y/N]: " ans || true
    ans="${ans:-N}"
  fi
  case "$(echo "$ans" | tr '[:upper:]' '[:lower:]')" in
    y|yes) return 0 ;;
    *) return 1 ;;
  esac
}

if [[ -n "$APPS_RAW" ]]; then
  normalize_apps "$APPS_RAW"
else
  ask_yes "Install Pure Maps (Flatpak)?" 1 && SEL_PURE=1
  ask_yes "Install Organic Maps (Flatpak)?" 1 && SEL_ORGANIC=1
  ask_yes "Install Navit (APT)?" 1 && SEL_NAVIT=1
  ask_yes "Install OSM Scout Server (Flatpak)?" 1 && SEL_OSM=1
fi

if (( SEL_PURE + SEL_ORGANIC + SEL_NAVIT + SEL_OSM == 0 )); then
  warn "No apps selected. Nothing to do."
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
log "Installing base dependencies"
apt-get update
apt-get install -y xdg-utils desktop-file-utils libglib2.0-bin

install_apt_pkg() {
  local pkg="$1"
  if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
    ok "$pkg already installed"
  else
    apt-get install -y "$pkg"
  fi
}

if (( SEL_NAVIT == 1 )); then
  log "Installing Navit"
  install_apt_pkg navit
  if apt-cache show maptool >/dev/null 2>&1; then
    install_apt_pkg maptool || true
  fi
fi

if (( SEL_PURE == 1 || SEL_ORGANIC == 1 || SEL_OSM == 1 )); then
  log "Installing Flatpak and configuring Flathub"
  install_apt_pkg flatpak
  flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
fi

install_flatpak_app() {
  local app_id="$1"
  if flatpak info "$app_id" >/dev/null 2>&1; then
    ok "$app_id already installed"
  else
    flatpak install -y flathub "$app_id"
  fi
}

if (( SEL_PURE == 1 )); then install_flatpak_app io.github.rinigus.PureMaps; fi
if (( SEL_ORGANIC == 1 )); then install_flatpak_app app.organicmaps.desktop; fi
if (( SEL_OSM == 1 )); then install_flatpak_app io.github.rinigus.OSMScoutServer; fi

log "Configuring K7BAT GPS menu category"
mkdir -p /usr/share/desktop-directories /etc/xdg/menus/applications-merged
cat >/usr/share/desktop-directories/k7bat-gps-nav.directory <<'EOF'
[Desktop Entry]
Type=Directory
Name=K7BAT GPS - Nav
Comment=GPS, maps and navigation
Icon=mark-location-symbolic
EOF

cat >/etc/xdg/menus/applications-merged/k7bat-gps-nav.menu <<'EOF'
<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN"
 "http://www.freedesktop.org/standards/menu-spec/1.0/menu.dtd">
<Menu>
  <Name>Applications</Name>
  <Menu>
    <Name>K7BAT-GPS-Nav</Name>
    <Directory>k7bat-gps-nav.directory</Directory>
    <Include>
      <Category>X-K7BAT-GPSNav</Category>
    </Include>
  </Menu>
</Menu>
EOF

make_launcher() {
  local file="$1" name="$2" comment="$3" exec_cmd="$4" icon="$5"
  cat >"/usr/share/applications/$file" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$name
Comment=$comment
Exec=$exec_cmd
Icon=$icon
Terminal=false
Categories=Utility;Maps;X-K7BAT-GPSNav;
StartupNotify=true
EOF
}

if (( SEL_PURE == 1 )); then
  make_launcher \
    k7bat-pure-maps.desktop \
    "Pure Maps" \
    "GPS navigation and mapping" \
    "env QT_QPA_PLATFORM=wayland flatpak run io.github.rinigus.PureMaps" \
    "io.github.rinigus.PureMaps"
fi

if (( SEL_ORGANIC == 1 )); then
  make_launcher \
    k7bat-organic-maps.desktop \
    "Organic Maps" \
    "Modern offline GPS navigation" \
    "env QT_QPA_PLATFORM=wayland flatpak run app.organicmaps.desktop" \
    "app.organicmaps.desktop"
fi

if (( SEL_OSM == 1 )); then
  make_launcher \
    k7bat-osm-scout-server.desktop \
    "OSM Scout Server" \
    "Offline map and routing backend" \
    "env QT_QPA_PLATFORM=wayland flatpak run io.github.rinigus.OSMScoutServer" \
    "io.github.rinigus.OSMScoutServer"
fi

if (( SEL_NAVIT == 1 )); then
  make_launcher \
    k7bat-navit.desktop \
    "Navit" \
    "Offline automotive navigation" \
    "navit" \
    "navit"
fi

update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
pkill -u "$GUI_USER" menu-cached >/dev/null 2>&1 || true

if [[ "$SET_STATUS_DEFAULT" -eq 1 ]]; then
  if [[ -z "$STATUS_DEFAULT" ]]; then
    if (( SEL_ORGANIC == 1 )); then STATUS_DEFAULT="organicmaps"
    elif (( SEL_PURE == 1 )); then STATUS_DEFAULT="puremaps"
    elif (( SEL_OSM == 1 )); then STATUS_DEFAULT="osmscoutserver"
    elif (( SEL_NAVIT == 1 )); then STATUS_DEFAULT="navit"
    fi
  fi

  if [[ -n "$STATUS_DEFAULT" ]]; then
    log "Linking selection to Status App"
    sudo -u "$GUI_USER" mkdir -p "$GUI_HOME/.config/k7bat-uconsole-status"
    sudo -u "$GUI_USER" python3 - "$GUI_HOME/.config/k7bat-uconsole-status/settings.json" "$STATUS_DEFAULT" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
selected = sys.argv[2]
try:
    data = json.loads(p.read_text()) if p.exists() else {}
    if not isinstance(data, dict):
        data = {}
except Exception:
    data = {}
data["gps_nav_app"] = selected
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"Set gps_nav_app={selected}")
PY
  fi
fi

log "Complete"
echo "Installed GPS app launchers are under category: X-K7BAT-GPSNav"
echo "Status app can launch: navit, puremaps, organicmaps, osmscoutserver"
