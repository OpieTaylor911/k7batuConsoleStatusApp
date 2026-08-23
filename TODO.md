# K7BAT uConsole Status App TODO

Updated: 2026-08-22

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
  - Remaining: dedicated touch mode toggle, high-contrast mode, and day/night theme.
- [ ] Secure Remote Assist Mode
  - Current: baseline diagnostics script exists.
  - Remaining: temporary diagnostics bundle workflow and tokenized upload path.
- [ ] Auto-Update and Rollback
  - Current: startup release detection and popup with GitHub tag fallback are implemented.
  - Remaining: one-click in-app apply, channel selection, backup/restore workflow, and rollback safety gates.

### Not Started
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