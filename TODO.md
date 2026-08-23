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
- [ ] Advanced GPS Quality View
  - Current: fix/sat/device/speed/track plus sats-used, DOP (HDOP/VDOP/PDOP), confidence score, and lightweight trend history are shown.
  - Remaining: optional graphical sparkline rendering.
- [ ] Tactical Connectivity Pane
  - Current: Wi-Fi details plus Active Link, Wi-Fi trend history, failover state, and hotspot watchdog are shown.
  - Remaining: scan-and-connect helper actions.
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

## Recommended Next Build Order

- [ ] Tactical Connectivity Pane (add scan/connect helpers)
- [ ] Advanced GPS Quality View (add sparkline/mini-graph)
- [ ] Auto-Update and Rollback (in-app apply + rollback)
- [ ] Touch-First Field UI Mode (high contrast + larger hit targets)
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

- [ ] Add on-demand detail popups for advanced diagnostics (GPS quality, connectivity, services) so the main panel stays compact for normal use.

## Current Validation Items

- [ ] Decide whether to keep or remove the temporary `Check Updates` button after update-popup testing is complete.
