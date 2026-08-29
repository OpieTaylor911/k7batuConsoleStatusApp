#!/usr/bin/env bash
# K7BAT uConsole - Secure Remote Assist Diagnostics Bundle Creator
# Creates a compressed archive of system diagnostics for remote assistance

set -e

BUNDLE_DIR=$(mktemp -d)
BUNDLE_NAME="uconsole-diagnostics-$(date +%Y%m%d-%H%M%S)"
OUTPUT_DIR="${HOME}/Downloads"
OUTPUT_FILE="${OUTPUT_DIR}/${BUNDLE_NAME}.tar.gz"

# Create bundle directory structure
mkdir -p "${BUNDLE_DIR}/${BUNDLE_NAME}"

echo "Creating diagnostics bundle: ${BUNDLE_NAME}"
echo "Output will be saved to: ${OUTPUT_FILE}"
echo ""

# System Information
echo "[1/12] Collecting system information..."
{
    echo "=== OS Information ==="
    cat /etc/os-release 2>/dev/null || echo "Unable to read os-release"
    
    echo ""
    echo "=== Kernel Version ==="
    uname -r
    
    echo ""
    echo "=== Hardware Model ==="
    tr -d '\0' </proc/device-tree/model 2>/dev/null || echo "Unable to read hardware model"
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/system_info.txt"

# Network Configuration
echo "[2/12] Collecting network configuration..."
{
    echo "=== Network Interfaces ==="
    ip -br link show 2>/dev/null || echo "ip command failed"
    
    echo ""
    echo "=== IP Addresses ==="
    ip addr show 2>/dev/null || echo "ip addr failed"
    
    echo ""
    echo "=== Routing Table ==="
    ip route show 2>/dev/null || echo "ip route failed"
    
    echo ""
    echo "=== Wi-Fi Interfaces ==="
    iw dev 2>/dev/null || echo "iw dev failed"
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/network_config.txt"

# Wi-Fi Status
echo "[3/12] Collecting Wi-Fi status..."
{
    echo "=== Active Wi-Fi Connections ==="
    nmcli connection show --active 2>/dev/null || echo "nmcli failed"
    
    echo ""
    echo "=== Wi-Fi Signal Strength ==="
    for iface in $(ip -br link | grep wlan | awk '{print $1}'); do
        echo "--- ${iface} ---"
        cat /proc/net/wireless 2>/dev/null | grep "${iface}:" || echo "No wireless data for ${iface}"
    done
    
    echo ""
    echo "=== Recent Wi-Fi Logs ==="
    journalctl -u NetworkManager --no-pager -n 50 2>/dev/null || echo "Journalctl failed"
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/wifi_status.txt"

# GPS Status
echo "[4/12] Collecting GPS status..."
{
    echo "=== GPSD Status ==="
    systemctl status gpsd --no-pager -l 2>/dev/null || echo "gpsd not running"
    
    echo ""
    echo "=== GPS Position Sample ==="
    timeout 3 gpspipe -w -n 5 2>/dev/null || echo "gpspipe failed"
    
    echo ""
    echo "=== GPS Device Info ==="
    ls -la /dev/ttyACM* /dev/ttyUSB* 2>/dev/null | grep -i gps || echo "No GPS device found"
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/gps_status.txt"

# AIO Controller
echo "[5/12] Collecting AIO controller status..."
{
    echo "=== AIO Controller Status ==="
    aiov2_ctl --status 2>/dev/null || echo "aiov2_ctl failed"
    
    echo ""
    echo "=== AIO Power States ==="
    for device in GPS SDR LORA USB; do
        state=$(aiov2_ctl --get ${device,,} 2>/dev/null || echo "unknown")
        echo "${device}: ${state}"
    done
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/aio_status.txt"

# Running Services
echo "[6/12] Collecting running services..."
{
    echo "=== Active Services ==="
    systemctl list-units --type=service --state=running --no-pager 2>/dev/null | head -30
    
    echo ""
    echo "=== Service Status Details ==="
    for svc in gpsd readsb kismet; do
        echo "--- ${svc} ---"
        systemctl status "${svc}" --no-pager -l 2>/dev/null || echo "${svc} not found"
        echo ""
    done
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/services_status.txt"

# USB Devices
echo "[7/12] Collecting USB device information..."
{
    echo "=== USB Devices ==="
    lsusb -v 2>/dev/null | head -100 || echo "lsusb failed"
    
    echo ""
    echo "=== USB Bus Info ==="
    lsusb -t 2>/dev/null || echo "lsusb -t failed"
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/usb_devices.txt"

# Hardware Monitors
echo "[8/12] Collecting hardware monitors..."
{
    echo "=== CPU Temperature ==="
    cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null || echo "No thermal data"
    
    echo ""
    echo "=== CPU Frequency ==="
    cat /proc/cpuinfo | grep -E "cpu MHz|processor" | head -10
    
    echo ""
    echo "=== Memory Usage ==="
    free -h 2>/dev/null || echo "free failed"
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/hardware_monitors.txt"

# Application Logs
echo "[9/12] Collecting application logs..."
{
    echo "=== uConsole Status App Log ==="
    if [ -f "${HOME}/.local/share/k7bat-uconsole-status/app.log" ]; then
        tail -100 "${HOME}/.local/share/k7bat-uconsole-status/app.log" 2>/dev/null || echo "Unable to read app log"
    else
        echo "No application log found"
    fi
    
    echo ""
    echo "=== Recent System Logs (last 50 lines) ==="
    journalctl --no-pager -n 50 2>/dev/null || echo "journalctl failed"
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/app_logs.txt"

# Configuration Files
echo "[10/12] Collecting configuration files..."
{
    mkdir -p "${BUNDLE_DIR}/${BUNDLE_NAME}/config"
    
    if [ -f "${HOME}/.config/k7bat-uconsole-status/settings.json" ]; then
        cp "${HOME}/.config/k7bat-uconsole-status/settings.json" "${BUNDLE_DIR}/${BUNDLE_NAME}/config/" 2>/dev/null || true
    fi
    
    if [ -f "/etc/network/interfaces" ]; then
        cp /etc/network/interfaces "${BUNDLE_DIR}/${BUNDLE_NAME}/config/" 2>/dev/null || true
    fi
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/config_status.txt"

# File System Status
echo "[11/12] Collecting file system status..."
{
    echo "=== Disk Space ==="
    df -h 2>/dev/null || echo "df failed"
    
    echo ""
    echo "=== Home Directory Size ==="
    du -sh "${HOME}/.config/k7bat-uconsole-status" 2>/dev/null || echo "Unable to calculate config size"
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/filesystem_status.txt"

# Final Summary
echo "[12/12] Creating summary file..."
{
    echo "uConsole Diagnostics Bundle"
    echo "==========================="
    echo ""
    echo "Generated: $(date)"
    echo "Hostname: $(hostname)"
    echo "Bundle Name: ${BUNDLE_NAME}"
    echo ""
    echo "Contents:"
    ls -la "${BUNDLE_DIR}/${BUNDLE_NAME}/" 2>/dev/null || echo "Unable to list bundle contents"
} > "${BUNDLE_DIR}/${BUNDLE_NAME}/SUMMARY.txt"

# Create compressed archive
echo ""
echo "Creating compressed archive..."
mkdir -p "${OUTPUT_DIR}"
tar -czf "${OUTPUT_FILE}" -C "${BUNDLE_DIR}" "${BUNDLE_NAME}"

# Cleanup temp directory
rm -rf "${BUNDLE_DIR}"

echo ""
echo "✓ Diagnostics bundle created successfully!"
echo "Location: ${OUTPUT_FILE}"
echo ""
echo "To upload this bundle, share it with your support contact."
echo "They will provide a token to securely upload the file."

exit 0
