# K7BAT uConsole Status App v1.0.0

I built a small GTK/Wayland status dashboard for the ClockworkPi uConsole. It is aimed at Debian Trixie systems and has extra integration for the HackerGadgets AIO V2 and AC1200 Wi-Fi adapter.

It displays system resources, GPS/gpsd information, Wi-Fi interfaces and drivers, Ethernet/Bluetooth status, readsb status, and provides AIO V2 GPS/SDR/LoRa power controls through aiov2_ctl. It also provides shortcuts to commonly used uConsole applications when they are installed.

The installer is designed to work on a fresh system and does not assume my local username.

Install:

```bash
unzip K7BAT-uConsole-Status-App-v1.0.0.zip
cd K7BAT-uConsole-Status-App-v1.0.0
chmod +x install.sh
sudo ./install.sh
```

After installation, **K7BAT uConsole Status App** appears in the application menu and a desktop shortcut is created for the detected GUI user.

The app is MIT licensed. The release includes an uninstall script, diagnostics helper, README and checksums.
