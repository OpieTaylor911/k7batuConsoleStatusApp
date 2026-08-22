# Changelog

## 1.1.5 - 2026-08-21

- Added Mission Recorder with right-panel Record/Stop controls for session capture.
- Records periodic telemetry samples (GPS, services, Wi-Fi, and system metrics) to JSONL files.
- Generates an automatic mission summary JSON on stop, including duration, sample count, GPS fix uptime, Wi-Fi uptime, and metric extremes.
- Stores mission artifacts under `~/.config/k7bat-uconsole-status/missions`.

## 1.1.4 - 2026-08-21

- Added quick tag chips in Snapshot Manager to rapidly populate common tags.
- Added automatic retention cleanup for auto snapshots, keeping recent history per auto tag context.
- Retention policy defaults to keeping the latest 20 auto snapshots per context key.

## 1.1.3 - 2026-08-21

- Added snapshot tags stored in snapshot metadata for better grouping and quick recovery workflows.
- Extended Snapshot Manager with tag-aware manual saves using a comma-separated Tags field.
- Added one-click `Restore Latest Auto` action with optional tag filter to recover the newest automatic snapshot fast.
- Tagged automatic snapshots by source and context (for example: auto/profile/mobile, auto/settings, auto/plugins).

## 1.1.2 - 2026-08-21

- Added snapshot manager workflow with named snapshots and in-app load/delete controls.
- Added automatic snapshots on profile apply and manual settings/plugin edits.
- Added dedicated Snapshot Manager button in the profile controls area.
- Added GPS app location helper script (`find-gps-apps`) and expanded runtime app detection for Flatpak variants.
- Improved GPS nav resolver to discover installed Flatpak IDs for Pure Maps, Organic Maps, and OSM Scout when command names differ.

## 1.1.1 - 2026-08-21

- Refined layout to a compact two-column design with right-side operational controls, status, profile controls, and logo stack.
- Enabled default maximized launch for improved usability on the uConsole display.
- Added profile presets (Mobile, Base, Emergency, Custom) with persisted profile selection.
- Added per-profile launcher visibility and hotkeys:
- `Alt+1` Mobile
- `Alt+2` Base
- `Alt+3` Emergency
- `Alt+0` Custom
- `Ctrl+G` launches GPS Nav
- Added profile export/import snapshot workflow including plugin state.
- Added SVG icon framework for labels, sections, and launch buttons with graceful fallback when icons are missing.
- Added installer support for shipping SVG icon packs from `assets/icons` into `/opt/k7bat-uconsole-status/icons`.
- Hardened deployment script line-ending normalization with `dos2unix` fallback handling and explicit executable bit for launcher scripts.

## 1.1.0 - 2026-08-21

- Added a phased operations upgrade:
- Phase 1: Smart alert engine with configurable thresholds for CPU temperature, RAM usage, disk free, battery, and optional GPS/Wi-Fi checks.
- Phase 2: Service Health Center with live status and restart controls for gpsd, gpsd.socket, bluetooth, readsb, and NetworkManager.
- Phase 3: Custom plugin launcher row with editable JSON-based plugin definitions in Settings.
- Added dedicated alert panel and richer settings controls for alert management.
- Added plugins persistence file support at ~/.config/k7bat-uconsole-status/plugins.json.

## 1.0.1 - 2026-08-21

- Added a settings dialog to choose which app GPS Nav launches.
- Persisted GPS Nav launcher selection per user.
- Added launcher compatibility checks for Pure Maps, Organic Maps, Navit, and PyGPSClient.

## 1.0.0 - 2026-08-20

Initial public release.

- GTK3 native uConsole dashboard.
- Debian Trixie / labwc / Wayland support.
- Fresh install and upgrade-safe installer.
- Dynamic desktop-user detection.
- Start-menu and desktop integration.
- GPS via gpsd.
- Dynamic Wi-Fi detection with MT7921U / AC1200 recognition.
- HackerGadgets AIO V2 GPS, SDR and LoRa controls through aiov2_ctl.
- Green/gray/amber radio status indicators.
- Optional application launch buttons.
- Uninstall and diagnostics scripts.
