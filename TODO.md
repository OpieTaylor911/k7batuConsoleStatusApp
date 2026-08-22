# K7BAT uConsole Status App TODO

Updated: 2026-08-21

## Enhancement Tracker (Original 12)

### Completed
- [x] Smart Alert Engine
- [x] One-Tap Radio Profiles
- [x] Service Health Center
- [x] Plugin Button Row
- [x] Mission Recorder

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

### Not Started
- [ ] APRS Beacon + Position Logging
- [ ] Offline Map Panel
- [ ] Auto-Update and Rollback

## Recommended Next Build Order

- [ ] Advanced GPS Quality View (high operational visibility)
- [ ] Tactical Connectivity Pane (communications reliability)
- [ ] APRS Beacon + Position Logging (field integrations)
- [ ] Touch-First Field UI Mode (usability hardening)
- [ ] Secure Remote Assist Mode (support workflow)
- [ ] Offline Map Panel (larger scope)
- [ ] Auto-Update and Rollback (release workflow hardening)

## Already Delivered Beyond Original 12

- [x] Snapshot Manager (named save/load/delete)
- [x] Snapshot tags and quick tag chips
- [x] Restore Latest Auto snapshot
- [x] Auto snapshot retention policy (per-context)
- [x] Flatpak-aware GPS app discovery improvements

## Future UX Pattern

- [ ] Add on-demand detail popups for advanced diagnostics (GPS quality, connectivity, services) so the main panel stays compact for normal use.
