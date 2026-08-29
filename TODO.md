# K7BAT uConsole Status App TODO

Updated: 2026-08-26

## Enhancement Tracker (Original 12)

### Completed
- [x] Smart Alert Engine
- [x] One-Tap Radio Profiles
- [x] Service Health Center
- [x] Plugin Button Row
- [x] Mission Recorder
- [x] GitHub new-version popup check

### Partially Complete
- [x] Advanced GPS Quality View
  - Current: fix/sat/device/speed/track plus sats-used, DOP (HDOP/VDOP/PDOP), confidence score, and trend history are shown.
  - Completed: on-demand GPS Quality popup with mini graphical trend rendering for satellites and PDOP.
- [x] Tactical Connectivity Pane
  - Current: Wi-Fi details plus Active Link, Wi-Fi trend history, failover state, and hotspot watchdog are shown.
  - Completed: tactical scan/connect/disconnect/forget helper actions and on-demand connectivity detail popup.
- [ ] Touch-First Field UI Mode
  - Current: compact two-column layout and maximized start.
  - Completed: dedicated touch mode toggle button with "Touch Mode" label (moved to Settings dialog)
  - Completed: CSS classes `.touch-mode` for larger buttons (min-height 48px, font-size 18px)
  - Completed: high-contrast toggle button with "High Contrast" label (moved to Settings dialog)
  - Completed: day/night theme selection in Settings dialog
  - Completed: all three UI mode settings apply CSS classes to window for visual changes
  - Completed: settings persist across app restarts
- [x] Secure Remote Assist Mode
  - Current: baseline diagnostics script exists.
  - Completed: temporary diagnostics bundle workflow with comprehensive system collection (system info, network, GPS, AIO, services, USB, hardware monitors, app logs, config files, filesystem status)
  - Completed: Python module `app/plugins/remote_assist.py` with DiagnosticsBundle class
  - Completed: "Remote Assist" button added to plugin row in main window
  - Remaining: tokenized upload path integration (upload endpoint configuration, token input dialog, progress indicator)
- [x] Auto-Update and Rollback
  - Current: startup release detection and popup with GitHub tag fallback are implemented.
  - Completed: backup/restore workflow, channel selection, and one-click in-app apply (requires passwordless sudo).
- [ ] WiFiPineapple-Type Interface for WiFi Tools
  - Current: separate WiFi attack windows (Passive Survey, Active Attacks, Network Attacks, Monitor Mode, Firmware Analysis).
  - Remaining: unified WiFiPineapple-style interface with tool categories, quick-action buttons, and centralized configuration panel.
### Completed
- [x] Hak5 Pineapple Module Loader Plugin System
  - Created `app/plugins/pineapple_loader.py` with core module loading infrastructure
  - Supports module discovery from directory, metadata parsing from `module.json`, Python action execution
  - Created `app/plugins/pineapple_ui.py` with GTK3 UI for module management

### Not Started
- [ ] WiFiPineapple Integration - Wifite2 Automated Attacks
  - Scope: Integrate Wifite2 as automated attack framework with GUI controls for target selection, wordlists, and progress monitoring.
- [ ] WiFiPineapple Integration - Bettercap MITM Caplets
  - Scope: Create GUI interface to launch Bettercap HTTPAuth, DNS Spoof, SSLStrip caplets with configurable targets.
- [ ] WiFiPineapple Integration - Rogue AP / Evil Portal
  - Scope: Interface for creating rogue access points using hostapd/dnsmasq for phishing/lure attacks.
  - Hardware: Already supported (HackerGadgets AC1200 MT7921AUN supports monitor mode + AP mode).
- [ ] WiFiPineapple Integration - EAPHammer WPA2-Enterprise Evil Twin
  - Scope: Target corporate WPA2-Enterprise networks with credential stealing and hostile portal attacks.
  - Hardware: Already supported (MT7921 driver supports 802.11ac + AP mode for rogue APs).
- [ ] WiFiPineapple Integration - Responder/NTLM Hash Capture
  - Scope: Monitor and display NTLMv2 hashes captured via bettercap MITM or Responder integration.
- [ ] Hak5 Pineapple Modules UI Integration
  - Scope: Add "Hak5 Pineapple Modules" button to plugin row that opens module management dialog
  - Current: Loader and UI classes created in `app/plugins/`, integrated into main App class
  - Task: Modified `app/k7bat-uconsole-status.py` to register plugin button and handle clicks ✅

## Hardware Requirements for WiFiPineapple Features

| Feature | Current Hardware | Additional Required |
|---------|-----------------|---------------------|
| **Passive Survey** (Kismet) | ✅ HackerGadgets AC1200 (MT7921AUN) | None - already supported |
| **Monitor Mode** | ✅ HackerGadgets AC1200 | None - mt7921 driver supports it |
| **Rogue AP / Evil Portal** | ✅ HackerGadgets AC1200 | None - AP mode supported in hostapd |
| **WPA2-Enterprise Evil Twin** | ✅ HackerGadgets AC1200 | None - EAPHammer works with mt7921 |
| **Packet Injection** | ✅ HackerGadgets AC1200 | None - aircrack-ng works out of box |
| **Wifite2 Automation** | ✅ Existing tools installed | None - Python framework only |

### Hardware Summary
Your current uConsole with **HackerGadgets AC1200 (MT7921AUN)** has all the hardware needed for:
- Passive wireless surveying
- Monitor mode packet capture
- Rogue AP / Evil Portal creation
- WPA2-Enterprise evil twin attacks
- Packet injection & cracking

No additional hardware required! 🎉
- [ ] APRS Beacon + Position Logging
- [ ] Offline Map Panel
- [ ] Tactical Wi-Fi Defensive Audit
  - Scope: rogue AP indicators, auth/reconnect anomaly hints, and security posture checks (WPA/PMF visibility) without packet injection.

## Recommended Next Build Order

- [x] Tactical Connectivity Pane (scan/connect helpers delivered)
- [x] Advanced GPS Quality View (sparkline/mini-graph delivered)
- [ ] Auto-Update and Rollback (in-app apply + rollback)
- [ ] Touch-First Field UI Mode (high contrast + larger hit targets)
- [ ] Tactical Wi-Fi Defensive Audit (safe RF/security checks)
- [ ] APRS Beacon + Position Logging (field integration)
- [ ] Secure Remote Assist Mode (diagnostics bundle + upload token flow)
- [ ] Offline Map Panel (larger scope)

## Already Delivered Beyond Original 12

- [x] Snapshot Manager (named save/load/delete)
- [x] Snapshot tags and quick tag chips
- [x] Restore Latest Auto snapshot
- [x] Auto snapshot retention policy (per-context)
- [x] Flatpak-aware GPS app discovery improvements
- [x] USB/AC1200 toggle and Bluetooth toggle integration in AIO controls
- [x] AC1200 dependency gating and contextual hints for dependent actions
- [x] Service-row compact dot indicators and BT controller visibility (`BT Ctrl`)
- [x] Bundled starter plugin defaults with fallback loading
- [x] README modernization with screenshots and architecture/connection diagrams

## Future UX Pattern

- [ ] Add on-demand detail popups for advanced diagnostics (services) so the main panel stays compact for normal use.
  - Current: connectivity and GPS quality detail popups are implemented in Tactical tools.

## Current Validation Items

- [ ] Decide whether to keep or remove the temporary `Check Updates` button after update-popup testing is complete.

## Additional Ideas not yet planned but in the works.
- [ ] Make sure the scripts are well documented, what they do, what they fix, how to uninstall what they did.
- [ ] Support for FlipperZero with some image on it to do other attacks connected vi usb.