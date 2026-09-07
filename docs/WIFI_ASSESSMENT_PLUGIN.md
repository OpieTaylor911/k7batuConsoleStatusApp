# Wi-Fi Assessment Plugin for uConsole Status App

## Overview

This plugin provides a GTK3 UI interface for Wi-Fi assessment tools, wrapping the functionality from [WIFI-HACK-LINUX](https://github.com/trfahim/WIFI-HACK-LINUX) with proper safeguards and a user-friendly interface.

**Certification**: CEH (ECC532680914) - Feb 2026 to Mar 2029

## Files Created

1. **`app/plugins/wifi_assessment_loader.py`**
   - Core module loader
   - Tool execution wrapper
   - Command-line interface integration

2. **`app/plugins/wifi_assessment_ui.py`**
   - GTK3 UI window
   - Interactive tool selection
   - Real-time output display
   - Status feedback

3. **Updated `app/plugins.json`**
   - Registered new plugin with ID: `wifi-assessment`

4. **Updated `install.sh`**
   - Auto-installs plugin files to `/opt/k7bat-uconsole-status/app/plugins/`

## Available Tools

### 1. Wi-Fi Network Scan
- Scans for nearby networks using `iwlist`
- Displays SSID, signal strength, channel info
- Safe read-only operation

### 2. Monitor Mode Toggle
- Enable monitor mode with `airmon-ng start`
- Disable monitor mode with `airmon-ng stop`
- Required for packet injection attacks

### 3. Deauthentication Test (Lab Only)
- Test deauth frames using `aireplay-ng`
- Targeted testing only - use with caution
- Parameters: target BSSID, client MAC, count

### 4. Handshake Capture
- Capture 4-way handshake using `airodump-ng`
- Saves to `/tmp/handshake-*.cap`
- Requires monitor mode enabled

### 5. Password Crack Test
- Test cracking with wordlist using `aircrack-ng`
- Supports rockyou.txt and custom wordlists
- Only for authorized testing

## Installation

1. Run the install script:
   ```bash
   sudo ./install.sh
   ```

2. The plugin will be installed to:
   - `/opt/k7bat-uconsole-status/app/plugins/wifi_assessment_loader.py`
   - `/opt/k7bat-uconsole-status/app/plugins/wifi_assessment_ui.py`

3. Launch from the uConsole app menu

## Usage

1. Open the uConsole Status App
2. Select "Wi-Fi Assessment" from plugins menu
3. Choose interface (wlan0, wlan1, or eth0)
4. Select a tool from the list
5. Click "Execute Tool" to run

## Safety Features

- **Lab-only mode toggle** - Prevents offensive operations by default
- **Audit logging** - All actions logged to `/home/bcaddy/uconsole-k7bat/wifi_assessment_debug.log`
- **Command timeout** - 30-second max for most commands
- **User confirmation** - Required for destructive operations

## Requirements

- Python 3.x with GTK3 bindings (`python3-gi`)
- Wi-Fi tools: `iw`, `iwlist`, `airmon-ng`, `aireplay-ng`, `airodump-ng`, `aircrack-ng`
- Root/sudo access for wireless operations
- Monitor mode capable Wi-Fi adapter

## CEH Certification Compliance

This plugin is designed for:
- Authorized penetration testing environments
- Educational labs and training
- Network security assessments
- Compliance with CEH v12 curriculum

**Note**: Always ensure you have proper written authorization before testing networks outside your immediate control.

## Sudo Configuration

The plugin uses `sudo` for wireless tool execution. A sudoers configuration has been installed to allow passwordless execution of the following tools:

- `/sbin/iwlist` - Network scanning
- `/usr/sbin/airmon-ng` - Monitor mode control
- `/usr/sbin/aireplay-ng` - Deauthentication testing
- `/usr/sbin/airodump-ng` - Handshake capture
- `/usr/bin/aircrack-ng` - Password cracking

### Sudoers Configuration

The configuration file is located at:
```
/etc/sudoers.d/90-wifi-assessment
```

Content:
```sudoers
# Allow bcaddy to run Wi-Fi assessment tools without password
Cmnd_Alias WIFI_ASSESSMENT_CMDS = \
    /sbin/iwlist, \
    /usr/sbin/airmon-ng, \
    /usr/sbin/aireplay-ng, \
    /usr/sbin/airodump-ng, \
    /usr/bin/aircrack-ng

bcaddy ALL=(root) NOPASSWD: WIFI_ASSESSMENT_CMDS
```

### Testing Sudo Configuration

To verify sudo works without password prompts:
```bash
sudo -n iwlist wlan0 scan
```

## Debugging

Logs are stored at:
```
/home/bcaddy/uconsole-k7bat/wifi_assessment_debug.log
```

To view logs:
```bash
tail -f /home/bcaddy/uconsole-k7bat/wifi_assessment_debug.log
```

## License

Same as original uConsole Status App.

## Support

For issues or questions, refer to the main project documentation or contact the development team.
