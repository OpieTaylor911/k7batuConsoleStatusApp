orPlace Tabler SVG icons for the status app in this folder.

Expected filenames:
- dashboard.svg
- navigation.svg
- satellite.svg
- map.svg
- radio.svg
- radio-tower.svg
- plane.svg
- wifi.svg
- ethernet.svg
- bluetooth.svg
- battery.svg
- cpu.svg
- memory.svg
- nvme.svg
- temperature.svg
- radar.svg
- network.svg
- terminal.svg
- settings.svg
- power.svg

Deployment/install behavior:
- install.sh copies *.svg from assets/icons/ into /opt/k7bat-uconsole-status/icons/
- The app loads icons from /opt/k7bat-uconsole-status/icons/ at runtime.
- If an icon is missing, the UI falls back to text-only labels/buttons.
