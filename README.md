# K7BAT uConsole Status App v1.0.0

A GTK/Wayland desktop status and launcher application for the **ClockworkPi uConsole**, created by **K7BAT**.

It is designed primarily for Raspberry Pi Compute Module 4/5 uConsole builds and works especially well with the **HackerGadgets AIO V2** and **HackerGadgets AC1200 (MediaTek MT7921U)**.

## Features

- Native GTK3 desktop application for Wayland/labwc and X11-capable Debian desktops.
- CPU temperature, RAM, NVMe/root filesystem space and battery status when exposed by the kernel.
- GPS status through `gpsd`: fix type, satellites, device, position, speed and heading.
- Dynamic Wi-Fi interface detection.
- Friendly recognition for common uConsole adapters including:
  - HackerGadgets AC1200 / MediaTek `mt7921u`
  - TP-Link AC600 / Realtek 8821AU-family adapters
  - CM4/CM5 onboard Wi-Fi when detectable
- Wi-Fi mode, SSID, channel and signal strength.
- Ethernet, Bluetooth, IP, `gpsd` and `readsb` status.
- HackerGadgets AIO V2 radio controls through `aiov2_ctl`.
- Radio state indicators:
  - **Green** = ON
  - **Gray** = OFF
  - **Amber** = state could not be determined
- Optional launcher buttons for Navit, PyGPSClient, SDR++, GQRX, ADS-B/tar1090, Wireshark, Kismet and AIO Control.
- Start-menu entry and desktop shortcut.
- Fresh-install and upgrade-safe installer.
- Uninstaller and diagnostics script.

## Supported platform

Recommended:

- ClockworkPi uConsole
- Debian 13 "Trixie"
- Raspberry Pi CM4 or CM5
- labwc/Wayland desktop
- HackerGadgets AIO V2 optional
- HackerGadgets AC1200 optional

The application is defensive about missing hardware and optional tools; it can still run without AIO V2, GPS, SDR or extra Wi-Fi adapters.

## Install

Extract the release and run:

```bash
cd K7BAT-uConsole-Status-App-v1.0.0
chmod +x install.sh uninstall.sh scripts/*.sh
sudo ./install.sh
```

The installer:

1. Detects the desktop user instead of assuming a username.
2. Installs required Debian packages.
3. Installs the application under `/opt/k7bat-uconsole-status`.
4. Installs `/usr/local/bin/k7bat-uconsole-status`.
5. Adds the application to the Start/Application menu.
6. Creates a desktop shortcut for the detected GUI user.
7. Detects `aiov2_ctl` if present.
8. Preserves an existing gpsd device configuration.
9. If gpsd is not configured, attempts a conservative NMEA serial-device detection and configures gpsd only after observing valid NMEA output.

## Upgrade

Run the new release's installer again:

```bash
sudo ./install.sh
```

Application files and launchers are replaced. User/system GPS configuration is preserved unless gpsd has no configured device and a valid NMEA device is positively detected.

## Run

Launch **K7BAT uConsole Status App** from the desktop or Start menu.

From a graphical terminal:

```bash
k7bat-uconsole-status
```

## AIO V2 controls

When `aiov2_ctl` is installed, the dashboard exposes:

- GPS ON / OFF
- SDR ON / OFF
- LoRa ON / OFF
- AIO Control GUI

The app invokes `aiov2_ctl` rather than directly manipulating GPIO pins so AIO controller behavior remains owned by the HackerGadgets software.

## GPS

The dashboard consumes GPS data from `gpsd`; it does not directly seize the GPS UART during normal operation.

Check GPS from a terminal with:

```bash
cgps -s
```

On some CM5 + AIO V2 systems the GNSS UART is `/dev/ttyAMA0`, but the public installer does **not** blindly assume that.

## Wireless

Inspect all wireless adapters:

```bash
iw dev
nmcli device status
```

Inspect a specific adapter driver:

```bash
ethtool -i wlan1
```

The HackerGadgets AC1200 commonly appears with:

```text
driver: mt7921u
```

## Diagnostics

If something does not appear correctly:

```bash
sudo ./scripts/diagnostics.sh
```

When posting support information, review the output first because it may contain local network names or addresses.

## Uninstall

```bash
sudo ./uninstall.sh
```

The uninstaller removes K7BAT application files and shortcuts but intentionally does **not** uninstall shared Debian packages or rewrite gpsd configuration.

## Optional tools

The dashboard automatically enables launch buttons when the corresponding command exists. Examples:

```bash
sudo apt install navit wireshark kismet gqrx-sdr
```

Other tools such as SDR++ and PyGPSClient may come from HackerGadgets packages or other installation sources.

## Development pipeline notes

For contributor-facing workflow notes, see `dev_readme.template.md`.

For machine-local operational notes, use `dev_readme.md`.
That file is intentionally git-ignored and is not meant to be committed.

## Security

AIO power controls run through the locally installed `aiov2_ctl`. The app does not provide network authentication, remote command execution or an HTTP service.

For remote access to the uConsole, use a separately secured VNC/WayVNC or SSH configuration.

## License

MIT License. See `LICENSE`.

## Credits

Created by **K7BAT** for the ClockworkPi/uConsole community.
