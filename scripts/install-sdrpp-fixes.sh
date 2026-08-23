#!/usr/bin/env bash
set -euo pipefail

log(){ printf '\n==> %s\n' "$*"; }
ok(){ printf '[OK] %s\n' "$*"; }
warn(){ printf '[WARN] %s\n' "$*" >&2; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/install-sdrpp-fixes.sh"
  exit 1
fi

detect_gui_user() {
  if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]] && id "$SUDO_USER" >/dev/null 2>&1; then
    echo "$SUDO_USER"
    return
  fi

  local user
  user="$(loginctl list-sessions --no-legend 2>/dev/null | awk '$3 ~ /^[0-9]+$/ && $3 >= 1000 && $3 < 65534 {print $4; exit}')"
  if [[ -n "$user" ]] && id "$user" >/dev/null 2>&1; then
    echo "$user"
    return
  fi

  getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 && $7 !~ /(nologin|false)$/ {print $1; exit}'
}

GUI_USER="$(detect_gui_user || true)"
if [[ -n "$GUI_USER" ]]; then
  GUI_HOME="$(getent passwd "$GUI_USER" | cut -d: -f6)"
  ok "Desktop user: $GUI_USER"
else
  warn "No desktop user detected. Per-user SDR++ config will not be patched."
fi

log "Updating package index"
export DEBIAN_FRONTEND=noninteractive
apt-get update

log "Installing SDR++ and runtime dependencies"
if apt-cache show sdrpp >/dev/null 2>&1; then
  apt-get install -y sdrpp
else
  warn "sdrpp package is not available in configured repositories"
fi

apt-get install -y librtaudio7 || true

if [[ -f /usr/lib/sdrpp/plugins/audio_sink.so ]]; then
  if ldd /usr/lib/sdrpp/plugins/audio_sink.so 2>/dev/null | grep -q 'librtaudio.so.6 => not found'; then
    log "Resolving SDR++ RtAudio ABI compatibility (needs librtaudio.so.6)"
    if apt-cache show librtaudio6 >/dev/null 2>&1; then
      apt-get install -y librtaudio6 || warn "Failed to install librtaudio6 from configured repositories"
    else
      RTAUDIO6_DEB="http://deb.debian.org/debian/pool/main/r/rtaudio/librtaudio6_5.2.0~ds1-2_arm64.deb"
      if wget -q --spider "$RTAUDIO6_DEB"; then
        tmp_deb="$(mktemp --suffix=.deb)"
        if wget -q -O "$tmp_deb" "$RTAUDIO6_DEB"; then
          dpkg -i "$tmp_deb" >/dev/null 2>&1 || apt-get -f install -y
        fi
        rm -f "$tmp_deb"
      else
        warn "Could not find a downloadable librtaudio6 package"
      fi
    fi
  fi

  if ldd /usr/lib/sdrpp/plugins/audio_sink.so 2>/dev/null | grep -q 'librtaudio.so.6 => not found'; then
    warn "audio_sink plugin still has unresolved librtaudio.so.6"
  else
    ok "audio_sink plugin runtime looks good"
  fi
fi

if [[ -n "${GUI_USER:-}" && -n "${GUI_HOME:-}" ]]; then
  log "Patching SDR++ user config for audio output"
  cfg_dir="$GUI_HOME/.config/sdrpp"
  cfg_path="$cfg_dir/config.json"
  mkdir -p "$cfg_dir"
  chown -R "$GUI_USER:$GUI_USER" "$cfg_dir"

  if [[ ! -f "$cfg_path" ]]; then
    cat >"$cfg_path" <<'EOF'
{
  "source": "RTL-SDR",
  "streams": {
    "Radio": {
      "muted": false,
      "sink": "Audio",
      "volume": 1.0
    }
  }
}
EOF
    chown "$GUI_USER:$GUI_USER" "$cfg_path"
  fi

  python3 - <<PY
import json
from pathlib import Path
p = Path(${cfg_path@Q})
try:
    data = json.loads(p.read_text())
except Exception:
    data = {}
if not isinstance(data, dict):
    data = {}
streams = data.setdefault("streams", {})
if not isinstance(streams, dict):
    streams = {}
    data["streams"] = streams
radio = streams.setdefault("Radio", {})
if not isinstance(radio, dict):
    radio = {}
    streams["Radio"] = radio
radio["sink"] = "Audio"
radio["muted"] = False
radio["volume"] = float(radio.get("volume", 1.0) or 1.0)
if not data.get("source"):
    data["source"] = "RTL-SDR"
p.write_text(json.dumps(data, indent=4) + "\n")
PY

  chown "$GUI_USER:$GUI_USER" "$cfg_path"
  ok "Patched $cfg_path"
fi

log "Done"
echo "SDR++ fixes applied."
echo "If SDR++ is running, restart it."
echo "When launching SDR++, stop readsb first to avoid tuner contention."
