#!/usr/bin/env bash
set -euo pipefail

log(){ printf "\n==> %s\n" "$*"; }
ok(){ printf "[OK] %s\n" "$*"; }
warn(){ printf "[WARN] %s\n" "$*" >&2; }

[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }

detect_gui_user() {
  if [[ -n "${K7BAT_GUI_USER:-}" ]] && id "$K7BAT_GUI_USER" >/dev/null 2>&1; then echo "$K7BAT_GUI_USER"; return; fi
  if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]] && id "$SUDO_USER" >/dev/null 2>&1; then echo "$SUDO_USER"; return; fi
  loginctl list-sessions --no-legend 2>/dev/null | awk '$2 >= 1000 {print $3; exit}'
}

GUI_USER="$(detect_gui_user)"
[[ -n "$GUI_USER" ]] || { echo "Could not detect GUI user. Set K7BAT_GUI_USER=username"; exit 1; }
GUI_UID="$(id -u "$GUI_USER")"
GUI_HOME="$(getent passwd "$GUI_USER" | cut -d: -f6)"
DESKTOP_DIR="$GUI_HOME/Desktop"

ok "GUI user: $GUI_USER"

export DEBIAN_FRONTEND=noninteractive
apt-get update

install_pkg() {
  local p="$1"
  if dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'install ok installed'; then
    ok "$p already installed"
  elif apt-cache show "$p" >/dev/null 2>&1; then
    apt-get install -y "$p"
  else
    warn "$p unavailable"
  fi
}

log "Installing GPS/navigation packages"
for p in gpsd gpsd-clients geoclue-2.0 flatpak xdg-utils desktop-file-utils libglib2.0-bin navit maptool gpredict; do
  install_pkg "$p"
done

if command -v pygpsclient >/dev/null 2>&1; then
  ok "PyGPSClient already installed"
elif apt-cache show pygpsclient >/dev/null 2>&1; then
  install_pkg pygpsclient
else
  warn "PyGPSClient not in APT; leave HackerGadgets-installed copy in place if present."
fi

log "Configuring Flathub and modern map apps"
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak info app.organicmaps.desktop >/dev/null 2>&1 || flatpak install -y flathub app.organicmaps.desktop
flatpak info io.github.rinigus.PureMaps >/dev/null 2>&1 || flatpak install -y flathub io.github.rinigus.PureMaps

log "Configuring gpsd if not already configured"
GPSD=/etc/default/gpsd
EXISTING="$(sed -n -E 's/^DEVICES="?([^"]*)"?$/\1/p' "$GPSD" 2>/dev/null | head -1 || true)"

detect_nmea() {
  for d in /dev/ttyAMA0 /dev/ttyAMA1 /dev/ttyAMA10 /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyACM0 /dev/ttyACM1; do
    [[ -c "$d" ]] || continue
    for b in 9600 38400 115200; do
      s="$(timeout 3 sh -c "stty -F '$d' '$b' raw -echo 2>/dev/null; head -n 15 < '$d'" 2>/dev/null || true)"
      if printf '%s\n' "$s" | grep -Eq '^\$(GP|GN|GL|GA|GB)(GGA|GLL|GSA|GSV|RMC|VTG|ZDA|TXT)'; then
        echo "$d"; return 0
      fi
    done
  done
  return 1
}

if [[ -z "$EXISTING" ]]; then
  GPS_DEV="$(detect_nmea || true)"
  if [[ -n "$GPS_DEV" ]]; then
    cp -a "$GPSD" "$GPSD.k7bat-backup.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
    cat >"$GPSD" <<EOF
START_DAEMON="true"
USBAUTO="false"
DEVICES="$GPS_DEV"
GPSD_OPTIONS="-n"
OPTIONS=""
EOF
    ok "gpsd configured for $GPS_DEV"
  else
    warn "No live NMEA stream found; gpsd device not forced."
  fi
else
  ok "Preserving existing gpsd device: $EXISTING"
fi

systemctl enable gpsd.socket >/dev/null 2>&1 || true
systemctl restart gpsd.socket >/dev/null 2>&1 || true
systemctl restart gpsd >/dev/null 2>&1 || true

log "Installing gpsd -> GeoClue NMEA bridge"
cat >/usr/local/bin/k7bat-gpsd-geoclue-bridge <<'PY'
#!/usr/bin/env python3
import os,socket,time
PATH="/run/gps-share.sock"
try: os.unlink(PATH)
except FileNotFoundError: pass
srv=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
srv.bind(PATH); os.chmod(PATH,0o666); srv.listen(8)
while True:
    c=g=None
    try:
        c,_=srv.accept()
        g=socket.create_connection(("127.0.0.1",2947),5)
        g.sendall(b'?WATCH={"enable":true,"nmea":true,"raw":1}\n')
        buf=b""
        while True:
            data=g.recv(4096)
            if not data: break
            buf+=data
            while b"\n" in buf:
                line,buf=buf.split(b"\n",1)
                line=line.strip()
                if line.startswith(b"$"): c.sendall(line+b"\r\n")
    except Exception:
        time.sleep(1)
    finally:
        for x in (g,c):
            try:
                if x: x.close()
            except Exception: pass
PY
chmod 755 /usr/local/bin/k7bat-gpsd-geoclue-bridge

cat >/etc/systemd/system/k7bat-gpsd-geoclue-bridge.service <<'EOF'
[Unit]
Description=K7BAT GPSD to GeoClue NMEA Bridge
After=gpsd.socket
Wants=gpsd.socket

[Service]
ExecStart=/usr/local/bin/k7bat-gpsd-geoclue-bridge
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now k7bat-gpsd-geoclue-bridge.service

log "Configuring GeoClue"
CONF=/etc/geoclue/geoclue.conf
cp -a "$CONF" "$CONF.k7bat-backup.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true

python3 - "$CONF" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); t=p.read_text()
if "[network-nmea]" not in t:
    t += "\n[network-nmea]\nenable=true\nnmea-socket=/run/gps-share.sock\n"
else:
    m=re.search(r'(\[network-nmea\][\s\S]*?)(?=\n\[[^\]]+\]|\Z)',t)
    if m:
        s=m.group(1)
        s=re.sub(r'^\s*enable\s*=.*$','enable=true',s,flags=re.M) if re.search(r'^\s*enable\s*=',s,re.M) else s+"\nenable=true"
        s=re.sub(r'^\s*#?\s*nmea-socket\s*=.*$','nmea-socket=/run/gps-share.sock',s,flags=re.M) if re.search(r'^\s*#?\s*nmea-socket\s*=',s,re.M) else s+"\nnmea-socket=/run/gps-share.sock"
        t=t[:m.start()]+s+t[m.end():]
for app in ("app.organicmaps.desktop","io.github.rinigus.PureMaps"):
    if f"[{app}]" not in t:
        t += f"\n\n[{app}]\nallowed=true\nsystem=false\nusers=\n"
p.write_text(t)
PY
systemctl restart geoclue

# Make Flatpak desktop IDs visible to GeoClue if exports exist.
for pair in \
"/var/lib/flatpak/exports/share/applications/app.organicmaps.desktop.desktop:/usr/share/applications/app.organicmaps.desktop.desktop" \
"/var/lib/flatpak/exports/share/applications/io.github.rinigus.PureMaps.desktop:/usr/share/applications/io.github.rinigus.PureMaps.desktop"
do
  src="${pair%%:*}"; dst="${pair##*:}"
  [[ -f "$src" ]] && ln -sfn "$src" "$dst"
done

log "Creating GPS - Nav Start-menu folder"
mkdir -p /usr/share/desktop-directories /etc/xdg/menus/applications-merged

cat >/usr/share/desktop-directories/k7bat-gps-nav.directory <<'EOF'
[Desktop Entry]
Type=Directory
Name=GPS - Nav
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
    <Include><Category>K7BATGPSNav</Category></Include>
  </Menu>
</Menu>
EOF

launcher() {
  local file="$1" name="$2" comment="$3" exec="$4" icon="$5"
  cat >"/usr/share/applications/$file" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$name
Comment=$comment
Exec=$exec
Icon=$icon
Terminal=false
Categories=K7BATGPSNav;
StartupNotify=true
EOF
}

launcher k7bat-organic-maps.desktop "Organic Maps" "Modern offline GPS navigation" \
'env QT_QPA_PLATFORM=wayland flatpak run app.organicmaps.desktop' app.organicmaps.desktop
launcher k7bat-pure-maps.desktop "Pure Maps" "GPS navigation and mapping" \
'env QT_QPA_PLATFORM=wayland flatpak run io.github.rinigus.PureMaps' io.github.rinigus.PureMaps

command -v navit >/dev/null && launcher k7bat-navit.desktop "Navit" "Offline automotive navigation" navit navit
command -v pygpsclient >/dev/null && launcher k7bat-pygpsclient.desktop "PyGPSClient" "GNSS diagnostics" pygpsclient applications-science
command -v gpredict >/dev/null && launcher k7bat-gpredict.desktop "GPredict" "Satellite tracking" gpredict gpredict-icon

log "Creating missing Organic/Pure desktop shortcuts without touching existing ones"
mkdir -p "$DESKTOP_DIR"
chown "$GUI_USER:$GUI_USER" "$DESKTOP_DIR"

desktop_if_missing() {
  local file="$1" name="$2" exec="$3" icon="$4"
  local dst="$DESKTOP_DIR/$file"
  [[ -e "$dst" ]] && { ok "$name desktop shortcut already exists"; return; }
  cat >"$dst" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$name
Exec=$exec
Icon=$icon
Terminal=false
Categories=K7BATGPSNav;
StartupNotify=true
EOF
  chown "$GUI_USER:$GUI_USER" "$dst"
  chmod 755 "$dst"
  if [[ -S /run/user/$GUI_UID/bus ]]; then
    sudo -u "$GUI_USER" XDG_RUNTIME_DIR="/run/user/$GUI_UID" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$GUI_UID/bus" \
      gio set "$dst" metadata::trusted true >/dev/null 2>&1 || true
  fi
}

desktop_if_missing organic-maps.desktop "Organic Maps" \
'env QT_QPA_PLATFORM=wayland flatpak run app.organicmaps.desktop' app.organicmaps.desktop
desktop_if_missing pure-maps.desktop "Pure Maps" \
'env QT_QPA_PLATFORM=wayland flatpak run io.github.rinigus.PureMaps' io.github.rinigus.PureMaps

update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
pkill -u "$GUI_USER" menu-cached >/dev/null 2>&1 || true

log "Complete"
echo "Start menu folder: GPS - Nav"
echo "GPS test: cgps -s"
echo "Organic Maps: flatpak run app.organicmaps.desktop"
echo "Pure Maps: flatpak run io.github.rinigus.PureMaps"
