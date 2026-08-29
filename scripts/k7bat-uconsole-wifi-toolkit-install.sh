#!/usr/bin/env bash
#
# K7BAT uConsole Wireless Assessment Toolkit
# Target: ClockworkPi uConsole CM5 + HackerGadgets AC1200 (MediaTek MT7921AUN)
# OS: Debian 13 "Trixie" arm64
#
# Intended only for networks and RF environments you own or are explicitly
# authorized to assess.
#
set -Eeuo pipefail

LOG="/var/log/k7bat-wifi-install.log"
K7DIR="/home/bcaddy/uconsole-k7bat/wifi"
BINDIR="/usr/local/bin"
CONFDIR="/etc/k7bat-wifi"
CAPDIR="/var/lib/k7bat-wifi/captures"

if [[ $EUID -ne 0 ]]; then
  echo "Run this installer with sudo:"
  echo "  sudo $0"
  exit 1
fi

exec > >(tee -a "$LOG") 2>&1

echo "============================================================"
echo " K7BAT uConsole Wireless Assessment Toolkit"
echo " Debian Trixie / CM5 / HackerGadgets MT7921AUN"
echo " Tactical White Hat Security Evaluation Suite"
echo "============================================================"
echo

TARGET_USER="${SUDO_USER:-}"
if [[ -z "$TARGET_USER" || "$TARGET_USER" == "root" ]]; then
  TARGET_USER="$(getent passwd 1000 | cut -d: -f1 || true)"
fi
if [[ -z "$TARGET_USER" ]]; then
  echo "WARNING: Could not determine desktop user; group membership steps skipped."
fi

echo "[1/10] Checking OS and architecture..."
. /etc/os-release
echo "OS: ${PRETTY_NAME:-unknown}"
echo "Arch: $(dpkg --print-architecture)"
if [[ "${VERSION_CODENAME:-}" != "trixie" ]]; then
  echo "WARNING: This script was written for Debian Trixie."
fi

echo
echo "[2/10] Updating package metadata..."
apt-get update

echo
echo "[3/15] Installing base wireless/security tooling..."
export DEBIAN_FRONTEND=noninteractive
apt-get install -y \
  ca-certificates \
  curl \
  wget \
  gnupg \
  jq \
  pciutils \
  usbutils \
  ethtool \
  iw \
  rfkill \
  wireless-tools \
  iproute2 \
  net-tools \
  procps \
  lsof \
  tcpdump \
  tshark \
  wireshark \
  aircrack-ng \
  hcxdumptool \
  hcxtools \
  bettercap \
  bettercap-caplets \
  wavemon \
  python3 \
  python3-venv \
  python3-pip

echo
echo "[5/15] Installing additional security testing tools..."
apt-get install -y \
  reaver \
  bully \
  cowpatty \
  mdk4 \
  hostapd \
  dnsmasq || true

echo
echo "[6/15] Installing firmware analysis tools (from pip)..."
pip3 install --break-system-packages \
  binwalk \
  scapy \
  pyshark || true
install -d -m 0755 /usr/share/keyrings
rm -f /usr/share/keyrings/kismet-archive-keyring.gpg
wget -qO- https://www.kismetwireless.net/repos/kismet-release.gpg.key \
  | gpg --dearmor \
  > /usr/share/keyrings/kismet-archive-keyring.gpg

cat > /etc/apt/sources.list.d/kismet.list <<'EOF'
deb [signed-by=/usr/share/keyrings/kismet-archive-keyring.gpg] https://www.kismetwireless.net/repos/apt/release/trixie trixie main
EOF

apt-get update
apt-get install -y kismet

echo
echo "[7/15] Installing Python security packages..."
pip3 install --break-system-packages \
  scapy \
  pyshark \
  requests \
  beautifulsoup4
install -d -m 0755 "$K7DIR" "$CONFDIR"
install -d -m 0775 "$CAPDIR"

if [[ -n "$TARGET_USER" ]]; then
  chown -R "$TARGET_USER:$TARGET_USER" "$CAPDIR"
fi

echo
echo "[9/15] Configuring user permissions..."
if [[ -n "$TARGET_USER" ]]; then
  getent group wireshark >/dev/null && usermod -aG wireshark "$TARGET_USER" || true
  getent group kismet >/dev/null && usermod -aG kismet "$TARGET_USER" || true
  echo "Added $TARGET_USER to available wireshark/kismet groups."
fi

# Allow dumpcap packet capture for members of the wireshark group.
if command -v setcap >/dev/null 2>&1 && command -v dumpcap >/dev/null 2>&1; then
  setcap cap_net_raw,cap_net_admin=eip "$(command -v dumpcap)" || true
fi

echo
echo "[10/15] Installing AC1200 detection helper..."
cat > "$BINDIR/k7bat-wifi-detect" <<'EOF'
#!/usr/bin/env bash
set -u

echo "=== K7BAT Wireless Hardware Detection ==="
echo

echo "--- USB hardware ---"
lsusb
echo

echo "--- Wireless interfaces ---"
iw dev 2>/dev/null || true
echo

printf "%-12s %-14s %-20s %-20s\n" "INTERFACE" "DRIVER" "PHY" "MAC"
printf "%-12s %-14s %-20s %-20s\n" "---------" "------" "---" "---"

for p in /sys/class/net/*; do
  iface="$(basename "$p")"
  [[ -d "$p/wireless" ]] || continue

  driver="$(ethtool -i "$iface" 2>/dev/null | awk '/driver:/ {print $2}' || true)"
  phy="$(iw dev "$iface" info 2>/dev/null | awk '/wiphy/ {print "phy"$2; exit}' || true)"
  mac="$(cat "$p/address" 2>/dev/null || true)"
  printf "%-12s %-14s %-20s %-20s\n" "$iface" "${driver:-unknown}" "${phy:-unknown}" "$mac"
done

echo
echo "--- MT7921 / HackerGadgets candidate ---"
found=0
for p in /sys/class/net/*; do
  iface="$(basename "$p")"
  [[ -d "$p/wireless" ]] || continue
  driver="$(ethtool -i "$iface" 2>/dev/null | awk '/driver:/ {print $2}' || true)"
  if [[ "$driver" == mt7921* ]]; then
    echo "AC1200 candidate: $iface (driver=$driver)"
    found=1
  fi
done

if [[ $found -eq 0 ]]; then
  echo "No mt7921* wireless interface detected."
  echo "Check: lsusb ; dmesg | grep -Ei 'mt7921|mediatek|firmware'"
fi
EOF
chmod 0755 "$BINDIR/k7bat-wifi-detect"

echo
echo "[11/15] Installing monitor-mode helpers..."

cat > "$BINDIR/k7bat-wifi-ac1200" <<'EOF'
#!/usr/bin/env bash
# Print the interface most likely to be the HackerGadgets MT7921AUN.
set -euo pipefail

# Prefer MediaTek mt7921 USB device.
for p in /sys/class/net/*; do
  iface="$(basename "$p")"
  [[ -d "$p/wireless" ]] || continue
  drv="$(ethtool -i "$iface" 2>/dev/null | awk '/driver:/ {print $2}' || true)"
  if [[ "$drv" == "mt7921u" ]]; then
    echo "$iface"
    exit 0
  fi
done

# Fall back to any mt7921 driver.
for p in /sys/class/net/*; do
  iface="$(basename "$p")"
  [[ -d "$p/wireless" ]] || continue
  drv="$(ethtool -i "$iface" 2>/dev/null | awk '/driver:/ {print $2}' || true)"
  if [[ "$drv" == mt7921* ]]; then
    echo "$iface"
    exit 0
  fi
done

exit 1
EOF
chmod 0755 "$BINDIR/k7bat-wifi-ac1200"

cat > "$BINDIR/k7bat-monitor-start" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-}"
MON="${2:-k7mon0}"

if [[ -z "$BASE" ]]; then
  BASE="$(k7bat-wifi-ac1200 2>/dev/null || true)"
fi

if [[ -z "$BASE" ]]; then
  echo "Could not automatically identify the AC1200 interface."
  echo "Run: k7bat-wifi-detect"
  echo "Then: sudo k7bat-monitor-start <interface>"
  exit 1
fi

if ! iw dev "$BASE" info >/dev/null 2>&1; then
  echo "Wireless interface '$BASE' does not exist."
  exit 1
fi

if iw dev "$MON" info >/dev/null 2>&1; then
  echo "$MON already exists."
  iw dev "$MON" info
  exit 0
fi

PHYNUM="$(iw dev "$BASE" info | awk '/wiphy/ {print $2; exit}')"
PHY="phy${PHYNUM}"

echo "Base interface : $BASE"
echo "Wireless PHY   : $PHY"
echo "Monitor iface  : $MON"
echo

# Do not tear down the user's managed interface.
# Create a second monitor VIF on the AC1200 PHY.
iw phy "$PHY" interface add "$MON" type monitor
ip link set "$MON" up

echo
echo "Monitor interface created:"
iw dev "$MON" info
echo
echo "Capture example:"
echo "  sudo tshark -I -i $MON"
echo
echo "Stop when finished:"
echo "  sudo k7bat-monitor-stop $MON"
EOF
chmod 0755 "$BINDIR/k7bat-monitor-start"

cat > "$BINDIR/k7bat-monitor-stop" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
MON="${1:-k7mon0}"

if ! iw dev "$MON" info >/dev/null 2>&1; then
  echo "$MON does not exist."
  exit 0
fi

ip link set "$MON" down || true
iw dev "$MON" del
echo "Removed monitor interface $MON."
EOF
chmod 0755 "$BINDIR/k7bat-monitor-stop"

cat > "$BINDIR/k7bat-wifi-status" <<'EOF'
#!/usr/bin/env bash
set -u

echo "=== K7BAT Wi-Fi Status ==="
echo "Time: $(date --iso-8601=seconds)"
echo

AC="$(k7bat-wifi-ac1200 2>/dev/null || true)"
if [[ -n "$AC" ]]; then
  echo "AC1200 interface: $AC"
  ethtool -i "$AC" 2>/dev/null | sed 's/^/  /'
else
  echo "AC1200 interface: NOT DETECTED"
fi

echo
echo "--- Interfaces ---"
iw dev 2>/dev/null || true

echo
echo "--- RF kill ---"
rfkill list 2>/dev/null || true

echo
echo "--- Regulatory domain ---"
iw reg get 2>/dev/null || true

echo
echo "--- Routes ---"
ip route
EOF
chmod 0755 "$BINDIR/k7bat-wifi-status"

echo
echo "[12/15] Installing tactical test helpers..."

cat > "$BINDIR/k7bat-survey" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
IFACE="${1:-}"

if [[ -z "$IFACE" ]]; then
  IFACE="$(k7bat-wifi-ac1200 2>/dev/null || true)"
fi

if [[ -z "$IFACE" ]]; then
  echo "AC1200 not detected. Run k7bat-wifi-detect."
  exit 1
fi

echo "Starting Kismet with source: $IFACE"
echo "Kismet web UI is normally available at:"
echo "  http://localhost:2501"
echo
exec kismet -c "$IFACE"
EOF
chmod 0755 "$BINDIR/k7bat-survey"

cat > "$BINDIR/k7bat-capture" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

MON="${1:-k7mon0}"
OUTDIR="/var/lib/k7bat-wifi/captures"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUTDIR/k7bat-${STAMP}.pcapng"

if ! iw dev "$MON" info >/dev/null 2>&1; then
  echo "$MON does not exist; creating it from the AC1200."
  k7bat-monitor-start "" "$MON"
fi

mkdir -p "$OUTDIR"
echo "Passive capture: $MON"
echo "Output: $OUT"
echo "Press Ctrl+C to stop."
exec tshark -I -i "$MON" -w "$OUT"
EOF
chmod 0755 "$BINDIR/k7bat-capture"

cat > "$BINDIR/k7bat-channel" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
MON="${1:-k7mon0}"
CHANNEL="${2:-}"

if [[ -z "$CHANNEL" ]]; then
  echo "Usage: sudo k7bat-channel [monitor-interface] <channel>"
  echo "Example: sudo k7bat-channel k7mon0 36"
  exit 1
fi

iw dev "$MON" set channel "$CHANNEL"
echo "$MON set to channel $CHANNEL"
EOF
chmod 0755 "$BINDIR/k7bat-channel"

# Read-only JSON status helper for a future GUI.
cat > "$BINDIR/k7bat-wifi-json" <<'EOF'
#!/usr/bin/env python3
import json
import os
import re
import subprocess

def run(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

interfaces = []
iw = run(["iw", "dev"])
current = None
for line in iw.splitlines():
    s = line.strip()
    if s.startswith("Interface "):
        current = {"name": s.split()[1]}
        interfaces.append(current)
    elif current and s.startswith("type "):
        current["type"] = s.split()[1]
    elif current and s.startswith("channel "):
        current["channel"] = s.split()[1]

for ent in interfaces:
    name = ent["name"]
    drv = run(["ethtool", "-i", name])
    m = re.search(r"^driver:\s*(.+)$", drv, re.M)
    if m:
        ent["driver"] = m.group(1)
    try:
        ent["mac"] = open(f"/sys/class/net/{name}/address").read().strip()
    except Exception:
        pass

payload = {
    "service": "k7bat-wifi",
    "interfaces": interfaces,
    "rfkill": run(["rfkill", "list"]),
    "regulatory": run(["iw", "reg", "get"]),
}
print(json.dumps(payload, indent=2))
EOF
chmod 0755 "$BINDIR/k7bat-wifi-json"

echo
echo "[10/10] Final validation..."

echo
echo "--- Kernel / driver ---"
uname -a
modinfo mt7921u 2>/dev/null | head -20 || true

echo
echo "--- Installed tools ---"
for cmd in iw aircrack-ng hcxdumptool hcxpcapngtool bettercap kismet tshark wavemon; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf "  [OK] %-18s %s\n" "$cmd" "$(command -v "$cmd")"
  else
    printf "  [!!] %-18s missing\n" "$cmd"
  fi
done

echo
echo "--- Wireless detection ---"
"$BINDIR/k7bat-wifi-detect" || true

cat > "$K7DIR/README.txt" <<'EOF'
K7BAT uConsole Wireless Assessment Toolkit
==========================================

Use only on networks and RF environments you own or are authorized to assess.

Primary commands
----------------
k7bat-wifi-detect
    Detect wireless hardware and identify the HackerGadgets AC1200.

k7bat-wifi-status
    Human-readable radio/interface status.

k7bat-wifi-json
    JSON status output intended for the K7BAT GUI.

sudo k7bat-monitor-start
    Creates k7mon0 as a monitor-mode virtual interface on the AC1200.

sudo k7bat-monitor-stop
    Removes k7mon0.

k7bat-survey
    Starts Kismet using the AC1200. Browse to http://localhost:2501.

sudo k7bat-capture
    Starts a passive pcapng capture on k7mon0.

sudo k7bat-channel k7mon0 36
    Locks the monitor interface to a specific channel.

wavemon
    Interactive RF/signal monitor.

wireshark
    Packet analysis GUI.

Installed assessment tools
--------------------------
Aircrack-ng
Kismet
hcxdumptool
hcxtools
Bettercap + caplets
Wireshark/tshark
tcpdump
wavemon

Notes
-----
Kismet normally manages monitor mode/channel hopping itself, so run
k7bat-survey against the base AC1200 interface rather than k7mon0.

The k7bat-monitor-* helpers deliberately create/remove a separate monitor
VIF and do not automatically disconnect your normal managed Wi-Fi interface.

Active/disruptive test automation is intentionally not configured by this
installer. Keep those tests scoped to an isolated lab or explicitly
authorized network.
EOF

echo
echo "============================================================"
echo " Installation complete"
echo "============================================================"
echo
echo "Useful commands:"
echo "  k7bat-wifi-detect"
echo "  k7bat-wifi-status"
echo "  k7bat-wifi-json"
echo "  sudo k7bat-monitor-start"
echo "  k7bat-survey"
echo "  sudo k7bat-capture"
echo "  sudo k7bat-monitor-stop"
echo
echo "Documentation:"
echo "  $K7DIR/README.txt"
echo
echo "Captures:"
echo "  $CAPDIR"
echo

if [[ -n "$TARGET_USER" ]]; then
  echo "IMPORTANT: Log out and back in once so $TARGET_USER receives"
  echo "the new kismet/wireshark group memberships."
fi
echo
echo "Installer log:"
echo "  $LOG"
