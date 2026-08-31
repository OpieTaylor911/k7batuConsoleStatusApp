# Changelog

## 2.0.1 - 2026-08-31 (pre-release)

- Rebuilt the main app UI after a v2.0.0 regression left the window created but never shown/populated (missing `show_all()`, missing dashboard widget wiring)
- Restored a full tabbed dashboard: Status (System/Power & Radios/Services/Network), GPS, Launchers, Plugins — fullscreen by default with Exit button, F11 fullscreen toggle, Escape to quit
- Added Power & Radios controls (GPS/SDR/LORA/USB-AC1200 toggles, Bluetooth toggle) wired to `aiov2_ctl` and systemd
- Added Settings tab to start/stop the Sidekick status API server, with autostart-on-launch option
- Added `status_api.py` real GPS status reporting (was a hardcoded placeholder) and a new `/api/sidekick` plain-text endpoint for the ESP32 Sidekick
- Added the K7BAT Sidekick ESP32 companion display integration:
  - Serial Wi-Fi provisioning protocol (`SETWIFI=`, `GETWIFI`, `GETIP`, `CLEARWIFI`, `GETVERSION`) with on-device `BOARD=`/`VERSION=` self-reporting
  - New standalone "Sidekick Setup" app/plugin: serial port picker, Wi-Fi provisioning with saved SSID/password, live serial log with auto-scroll
  - Firmware flashing via `esptool` (`--no-stub`, working around a Debian packaging gap missing ESP32/S2/S3 stub flashers)
  - Firmware download from a releases server: `index.json` → per-version `release.json`/`manifest.json` (ESP Web Tools schema) resolution, latest-version auto-detection, single merged-image flashing
- Various UI polish: tabler-icons-based white icons, tighter spacing/compact fonts for small-screen fit, services laid out as a wide 2-column grid

## 1.2.0 - 2026-08-23

- Added auto-update with rollback capability
- Implemented backup system: `create_backup()` and `get_available_backups()`
- Added update download/installation: `apply_update()` and `download_release_assets()` with tarball fallback
- Implemented rollback functionality: `rollback_to_backup()`
- Added settings schema with `update_channel` field (stable/beta)
- Enhanced release popup with channel selection and Download & Install button
- Added helper methods: `_download_and_install_update()`, `on_update_complete()`, `restart_app()`, `show_rollback_dialog()`
- Updated deployment script to auto-restart app after sync
- Added SDR++ compatibility fixes and WiFi toolkit scripts

## 1.1.9 - 2026-08-22

- Added startup GitHub release check against the configured repository.
- Added new-version popup when a release newer than the local app version is detected.
- Added one-click `Open Release` action from the popup for fast update navigation.
- Added per-version popup dismissal tracking to avoid repeated alerts for the same release.
- Added settings persistence for release-check controls and repository target metadata.

## 1.1.8 - 2026-08-22

- Added USB AIO radio power control and relabeled it as `USB/AC1200` in the HackerGadgets control row.
- Replaced per-radio ON/OFF buttons with single toggle switches while keeping dot-based state indicators.
- Moved Bluetooth power control into the HackerGadgets toggle row and removed the separate BT ON action button.
- Added AC1200 dependency gating: Bluetooth and AC1200-dependent actions are dimmed/blocked when USB/AC1200 power is off, with contextual hover hint text.
- Restyled service health row (`Svc:`) to compact dot+label indicators for gpsd, bluetooth, and readsb.
- Added `BT Ctrl` visibility in Network/Wireless to show detected controller identity (for example `hci0`).
- Moved plugin launcher buttons to the right-side controls area under `Updated:`.
- Added bundled starter plugin defaults with fallback loading when user `plugins.json` is not present.
- Hardened service actions to use non-interactive `sudo -n systemctl` flow and installer-managed passwordless policy support.

## 1.1.7 - 2026-08-21

- Added Tactical Connectivity rows in Network panel: Active Link, Wi-Fi Trend, Failover, and Hotspot Watchdog.
- Added live Wi-Fi signal trend history (dBm) for quick link quality checks.
- Added active-link failover status updates to highlight path changes (Wi-Fi/Ethernet/Offline).
- Added hotspot watchdog status to flag repeated offline checks.

## 1.1.6 - 2026-08-21

- Expanded GPS panel with quality metrics: satellites used, HDOP, VDOP, PDOP, and computed GPS confidence score.
- Added lightweight history trends for satellites and PDOP to improve at-a-glance GPS quality diagnosis.
- Enriched GPS parser to read SKY DOP fields and used-satellite counts when available.

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
- Added installer support for shipping SVG icon packs from `assets/icons` into `/home/bcaddy/uconsole-k7bat/icons`.
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
