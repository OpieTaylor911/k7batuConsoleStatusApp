#!/usr/bin/env python3
"""
K7BAT Sidekick Setup Tool

Standalone GTK3 utility for provisioning the ESP32 "Sidekick" companion
display over its USB serial link:

  1. Send Wi-Fi SSID/password and tell it to connect.
  2. Read back the IP address it obtained from the AP.
  3. Send it the uConsole's own IP:port so it knows where to poll
     /api/sidekick for live status.

Can be launched standalone (``python3 sidekick_setup_ui.py``) or as a
plugin from the main K7BAT uConsole Status app.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

import glob
import hashlib
import json
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import serial
except ImportError:
    serial = None

APP_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = Path.home() / ".config" / "k7bat-sidekick-setup"
CONFIG_FILE = CONFIG_DIR / "settings.json"

BAUD_RATE = 115200
SERVER_PORT = 8080
CONNECT_TIMEOUT_S = 20
VERSION_QUERY_TIMEOUT_S = 3
FLASH_BAUD_RATE = 460800


def load_saved_wifi():
    """Return (ssid, password) last used, or ("", "") if none saved."""
    try:
        data = json.loads(CONFIG_FILE.read_text())
        return data.get("ssid", ""), data.get("password", "")
    except Exception:
        return "", ""


def save_saved_wifi(ssid, password):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps({"ssid": ssid, "password": password}))
        CONFIG_FILE.chmod(0o600)
    except Exception:
        pass

DEFAULT_RELEASES_BASE_URL = "https://www.k7bat.com/uconsole/sidekick/releases"
DEFAULT_RELEASE_VERSION = "1.0.0"
FIRMWARE_CACHE_DIR = Path.home() / ".cache" / "k7bat-sidekick-firmware"

# Per-device board profiles. "key" is what the firmware self-reports via
# BOARD= (see SIDEKICK_BOARD in the sketch); "server_id" is the id used in
# the K7BAT server's releases/index.json + release.json "boards" lists,
# which may not always match (e.g. imagespark_wroom is a typo left over
# in the server data for the "ideaspark" board — server_id lets us match
# the real published id without renaming our local key).
#
# All releases are a single merged bootloader+partitions+app image flashed
# at offset 0x0. Separate bootloader/partitions flashing is done manually
# via Arduino IDE, not through this app.
DEVICE_PROFILES = {
    "ideaspark": {
        "label": "IdeaSpark (ESP32-WROOM-32, ST7789)",
        "server_id": "ideaspark_wroom",
        "chip": "esp32",
        "esp_web_tools_chip": "ESP32",
        "merge_offset": "0x0",
    },
    "cyd": {
        "label": "CYD - Cheap Yellow Display (ESP32-WROOM-32)",
        "server_id": "cyd_device",
        "chip": "esp32",
        "esp_web_tools_chip": "ESP32",
        "merge_offset": "0x0",
    },
    "heltec": {
        "label": "Heltec (ESP32-S3)",
        "server_id": "heltec_E290",
        "chip": "esp32s3",
        "esp_web_tools_chip": "ESP32-S3",
        "merge_offset": "0x0",
    },
    "lilygo": {
        "label": "LilyGO (ESP32-S3)",
        "server_id": "lilygo_default",
        "chip": "esp32s3",
        "esp_web_tools_chip": "ESP32-S3",
        "merge_offset": "0x0",
    },
}


def find_esptool():
    """Locate the esptool CLI, whichever name this distro installed it under."""
    for name in ("esptool", "esptool.py"):
        found = shutil.which(name)
        if found:
            return found
    return None


def list_serial_ports():
    """Return candidate serial device paths for the sidekick."""
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    return ports


def get_local_ip():
    """Best-effort LAN IP of this uConsole, for prefilling the server field."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


class SidekickSetupWindow(Gtk.Window):
    """Serial provisioning UI for the K7BAT ESP32 Sidekick."""

    def __init__(self, parent_app=None):
        super().__init__(title="K7BAT Sidekick Setup")
        self.parent_app = parent_app
        self.set_default_size(1100, 600)
        self.maximize()
        self.set_border_width(12)
        self.connect("destroy", self.on_close)

        self._ser = None
        self._worker_running = False
        # Offset from a manifest download's own reported part offset;
        # None means "use profile's merge_offset default".
        self._firmware_offset = None

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(root)

        title = Gtk.Label(label="Sidekick Wi-Fi Setup")
        title.get_style_context().add_class("title")
        title.set_xalign(0)
        root.pack_start(title, False, False, 0)

        # ---- Two-column layout: connection/Wi-Fi on the left, firmware on the right ----
        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        root.pack_start(columns, False, False, 0)
        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        columns.pack_start(left_col, True, True, 0)
        columns.pack_start(right_col, True, True, 0)

        # ---- Serial port row ----
        port_row = Gtk.Box(spacing=8)
        left_col.pack_start(port_row, False, False, 0)
        port_row.pack_start(Gtk.Label(label="Port:"), False, False, 0)
        self.port_combo = Gtk.ComboBoxText()
        port_row.pack_start(self.port_combo, True, True, 0)
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect("clicked", lambda _b: self.refresh_ports())
        port_row.pack_start(refresh_btn, False, False, 0)
        self.refresh_ports()

        self.firmware_label = Gtk.Label(label="Firmware: (connect to detect)")
        self.firmware_label.set_xalign(0)
        self.firmware_label.get_style_context().add_class("subtle")
        left_col.pack_start(self.firmware_label, False, False, 0)

        # ---- Wi-Fi credentials ----
        form = Gtk.Grid(row_spacing=6, column_spacing=8)
        left_col.pack_start(form, False, False, 0)

        form.attach(Gtk.Label(label="Wi-Fi SSID:", xalign=0), 0, 0, 1, 1)
        self.ssid_entry = Gtk.Entry()
        form.attach(self.ssid_entry, 1, 0, 1, 1)

        form.attach(Gtk.Label(label="Wi-Fi Password:", xalign=0), 0, 1, 1, 1)
        self.pass_entry = Gtk.Entry()
        self.pass_entry.set_visibility(False)
        form.attach(self.pass_entry, 1, 1, 1, 1)

        saved_ssid, saved_password = load_saved_wifi()
        if saved_ssid:
            self.ssid_entry.set_text(saved_ssid)
        if saved_password:
            self.pass_entry.set_text(saved_password)

        show_pass = Gtk.CheckButton(label="Show password")
        show_pass.connect("toggled", lambda b: self.pass_entry.set_visibility(b.get_active()))
        form.attach(show_pass, 1, 2, 1, 1)

        form.attach(Gtk.Label(label="uConsole Server:", xalign=0), 0, 3, 1, 1)
        self.server_entry = Gtk.Entry()
        local_ip = get_local_ip()
        if local_ip:
            self.server_entry.set_text(f"{local_ip}:{SERVER_PORT}")
        form.attach(self.server_entry, 1, 3, 1, 1)

        # ---- Actions ----
        action_row = Gtk.Box(spacing=8)
        left_col.pack_start(action_row, False, False, 0)

        self.connect_btn = Gtk.Button(label="Configure Sidekick")
        self.connect_btn.connect("clicked", self.on_configure_clicked)
        action_row.pack_start(self.connect_btn, False, False, 0)

        exit_btn = Gtk.Button(label="Exit")
        exit_btn.connect("clicked", lambda _b: self.destroy())
        action_row.pack_end(exit_btn, False, False, 0)

        # ---- Status ----
        self.status_label = Gtk.Label(label="Select a port and enter Wi-Fi credentials.")
        self.status_label.set_xalign(0)
        self.status_label.set_line_wrap(True)
        left_col.pack_start(self.status_label, False, False, 0)

        # ---- Firmware update ----
        fw_frame = Gtk.Frame(label=" Firmware Update ")
        right_col.pack_start(fw_frame, False, False, 0)
        fw_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        fw_box.set_border_width(8)
        fw_frame.add(fw_box)

        device_row = Gtk.Box(spacing=8)
        fw_box.pack_start(device_row, False, False, 0)
        device_row.pack_start(Gtk.Label(label="Device:"), False, False, 0)
        self.device_combo = Gtk.ComboBoxText()
        for key, profile in DEVICE_PROFILES.items():
            self.device_combo.append(key, profile["label"])
        self.device_combo.set_active(0)
        device_row.pack_start(self.device_combo, True, True, 0)

        # ---- Download from server ----
        dl_row = Gtk.Box(spacing=8)
        fw_box.pack_start(dl_row, False, False, 0)
        dl_row.pack_start(Gtk.Label(label="Releases URL:"), False, False, 0)
        self.releases_url_entry = Gtk.Entry()
        self.releases_url_entry.set_text(DEFAULT_RELEASES_BASE_URL)
        dl_row.pack_start(self.releases_url_entry, True, True, 0)

        self.use_latest_check = Gtk.CheckButton(label="Use latest (index.json)")
        self.use_latest_check.set_active(True)
        self.use_latest_check.connect(
            "toggled", lambda b: self.release_version_entry.set_sensitive(not b.get_active())
        )
        dl_row.pack_start(self.use_latest_check, False, False, 0)

        dl_row.pack_start(Gtk.Label(label="Version:"), False, False, 0)
        self.release_version_entry = Gtk.Entry()
        self.release_version_entry.set_text(DEFAULT_RELEASE_VERSION)
        self.release_version_entry.set_width_chars(10)
        self.release_version_entry.set_sensitive(False)
        dl_row.pack_start(self.release_version_entry, False, False, 0)
        self.download_btn = Gtk.Button(label="Download")
        self.download_btn.connect("clicked", self.on_download_firmware_clicked)
        dl_row.pack_start(self.download_btn, False, False, 0)

        self.firmware_entries = {}
        row = Gtk.Box(spacing=8)
        fw_box.pack_start(row, False, False, 0)
        label = Gtk.Label(label="Firmware .bin:")
        label.set_size_request(110, -1)
        label.set_xalign(0)
        row.pack_start(label, False, False, 0)
        entry = Gtk.Entry()
        row.pack_start(entry, True, True, 0)
        browse_btn = Gtk.Button(label="Browse…")
        browse_btn.connect("clicked", self.on_browse_firmware_clicked)
        row.pack_start(browse_btn, False, False, 0)
        self.firmware_entries["app"] = entry

        fw_hint = Gtk.Label(
            label="Download resolves releases/index.json → manifest.json and fetches the "
                  "merged firmware image. Separate bootloader/partitions flashing is done "
                  "manually via Arduino IDE, not here."
        )
        fw_hint.set_xalign(0)
        fw_hint.set_line_wrap(True)
        fw_hint.get_style_context().add_class("subtle")
        fw_box.pack_start(fw_hint, False, False, 0)

        self.flash_btn = Gtk.Button(label="Flash Firmware")
        self.flash_btn.connect("clicked", self.on_flash_firmware_clicked)
        fw_box.pack_start(self.flash_btn, False, False, 0)

        # ---- Serial log (full width, below both columns) ----
        log_frame = Gtk.Frame(label=" Serial Log ")
        root.pack_start(log_frame, True, True, 0)
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
        log_frame.add(log_scroll)
        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer)
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_wrap_mode(Gtk.WrapMode.CHAR)
        self.log_view.modify_font(Pango.FontDescription("Monospace 9"))
        log_scroll.add(self.log_view)

    def refresh_ports(self):
        self.port_combo.remove_all()
        ports = list_serial_ports()
        for p in ports:
            self.port_combo.append_text(p)
        if ports:
            self.port_combo.set_active(0)

    def log(self, line):
        def append():
            end_iter = self.log_buffer.get_end_iter()
            self.log_buffer.insert(end_iter, line.rstrip("\n") + "\n")
            self.log_view.scroll_to_iter(self.log_buffer.get_end_iter(), 0.0, False, 0, 0)
            return False
        GLib.idle_add(append)

    def set_status(self, text):
        GLib.idle_add(self.status_label.set_text, text)

    def on_configure_clicked(self, _button):
        if self._worker_running:
            return
        if serial is None:
            self.set_status("pyserial is not installed (pip install pyserial)")
            return

        port = self.port_combo.get_active_text()
        ssid = self.ssid_entry.get_text().strip()
        password = self.pass_entry.get_text()
        server_addr = self.server_entry.get_text().strip()

        if not port:
            self.set_status("No serial port selected.")
            return
        if not ssid:
            self.set_status("Enter the Wi-Fi SSID.")
            return

        save_saved_wifi(ssid, password)

        self.connect_btn.set_sensitive(False)
        self.flash_btn.set_sensitive(False)
        self.download_btn.set_sensitive(False)
        self._worker_running = True
        threading.Thread(
            target=self._provision_worker,
            args=(port, ssid, password, server_addr),
            daemon=True,
        ).start()

    def on_download_firmware_clicked(self, _button):
        if self._worker_running:
            self.set_status("Another operation is already in progress.")
            return

        base_url = self.releases_url_entry.get_text().strip().rstrip("/")
        version = self.release_version_entry.get_text().strip()
        device_key = self.device_combo.get_active_id() or next(iter(DEVICE_PROFILES))
        use_latest = self.use_latest_check.get_active()

        if not base_url or (not use_latest and not version):
            self.set_status("Enter a releases URL and version.")
            return

        self.download_btn.set_sensitive(False)
        self.flash_btn.set_sensitive(False)
        self._worker_running = True
        threading.Thread(
            target=self._download_worker,
            args=(base_url, version, device_key, use_latest),
            daemon=True,
        ).start()

    def _fetch_json(self, url, timeout=10):
        self.log(f"--- GET {url} ---")
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())

    def _resolve_release(self, base_url, version, device_key, use_latest):
        """Read releases/index.json to find the release + board folder path.

        Real schema (as published):
          index.json = {"latest": "1.0.0", "releases": [
              {"version": "1.0.0", "path": "v1_0_0/",
               "boards": [{"id": "...", "name": "...", "path": "v1_0_0/<board>/"}]}
          ]}
        """
        index = self._fetch_json(f"{base_url}/index.json")
        target_version = index.get("latest") if use_latest else version
        if not target_version:
            raise ValueError("index.json has no 'latest' version set.")

        releases = index.get("releases", [])
        release = next((r for r in releases if r.get("version") == target_version), None)
        if release is None:
            available = ", ".join(r.get("version", "?") for r in releases) or "(none)"
            raise ValueError(f"Version '{target_version}' not found in index.json. Available: {available}")

        server_id = DEVICE_PROFILES[device_key].get("server_id", device_key)
        boards = release.get("boards", [])
        board = next((b for b in boards if b.get("id") == server_id), None)
        if board is None:
            available = ", ".join(b.get("id", "?") for b in boards) or "(none)"
            raise ValueError(
                f"Board id '{server_id}' not found in this release. Available: {available}"
            )

        return target_version, release.get("path", ""), board.get("path", "")

    def _download_worker(self, base_url, version, device_key, use_latest):
        try:
            self.set_status("Resolving release from index.json…")
            target_version, release_path, board_path = self._resolve_release(
                base_url, version, device_key, use_latest
            )
            self.log(f"<<< resolved version={target_version} board_path={board_path}")
            GLib.idle_add(self.release_version_entry.set_text, target_version)

            # Optional per-version release.json: not required, just logged if present.
            try:
                release_info = self._fetch_json(f"{base_url}/{release_path}release.json")
                notes = release_info.get("notes", [])
                boards_in_release = [b.get("id") for b in release_info.get("boards", [])]
                self.log(f"<<< release.json: version={release_info.get('version', target_version)} "
                         f"boards={boards_in_release}")
                if notes:
                    for note in notes:
                        self.log(f"    - {note}")
            except Exception:
                pass  # release.json is optional metadata, not required to proceed

            manifest_url = f"{base_url}/{board_path}manifest.json"
            self.set_status(f"Fetching {manifest_url}…")
            manifest = self._fetch_json(manifest_url)
            self.log(f"<<< manifest name={manifest.get('name')} version={manifest.get('version')}")

            profile = DEVICE_PROFILES[device_key]
            builds = manifest.get("builds", [])
            wanted_chip = profile.get("esp_web_tools_chip", "").upper()
            build = next(
                (b for b in builds if str(b.get("chipFamily", "")).upper() == wanted_chip),
                builds[0] if builds else None,
            )
            if build is None:
                self.set_status("Manifest has no builds to flash.")
                return

            parts = sorted(build.get("parts", []), key=lambda p: p.get("offset", 0))
            if not parts:
                self.set_status("Manifest build has no parts to flash.")
                return
            if len(parts) > 1:
                self.log(f"    WARNING: manifest has {len(parts)} parts; only using the "
                          "first (releases are expected to be a single merged image).")
            part = parts[0]

            filename = part.get("path")
            if not filename:
                self.set_status("Manifest part is missing a 'path'.")
                return

            cache_dir = FIRMWARE_CACHE_DIR / target_version / device_key
            cache_dir.mkdir(parents=True, exist_ok=True)

            file_url = f"{base_url}/{board_path}{filename}"
            dest = cache_dir / Path(filename).name
            self.set_status(f"Downloading {filename}…")
            urllib.request.urlretrieve(file_url, dest)

            expected_sha = part.get("sha256")
            if expected_sha:
                actual_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
                if actual_sha.lower() != expected_sha.lower():
                    self.set_status(f"Checksum mismatch for {filename}!")
                    self.log(f"    expected {expected_sha}\n    got      {actual_sha}")
                    return
                self.log(f"    sha256 OK: {filename}")

            offset = part.get("offset", 0)
            offset_str = offset if isinstance(offset, str) else f"0x{offset:x}"
            GLib.idle_add(self.firmware_entries["app"].set_text, str(dest))
            self._firmware_offset = offset_str

            self.set_status(f"Downloaded {manifest.get('version', target_version)} for {device_key}. Ready to flash.")
        except urllib.error.HTTPError as e:
            self.set_status(f"Download failed: HTTP {e.code}")
            self.log(f"ERROR: HTTP {e.code} — {e}")
        except urllib.error.URLError as e:
            self.set_status(f"Download failed: {e.reason}")
            self.log(f"ERROR: {e.reason}")
        except Exception as e:
            self.log(f"ERROR: {e}")
            self.set_status(f"Download error: {e}")
        finally:
            self._worker_running = False
            GLib.idle_add(self.download_btn.set_sensitive, True)
            GLib.idle_add(self.flash_btn.set_sensitive, True)

    def on_browse_firmware_clicked(self, _button):
        dialog = Gtk.FileChooserDialog(
            title="Select firmware .bin",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL,
            "Select", Gtk.ResponseType.OK,
        )
        bin_filter = Gtk.FileFilter()
        bin_filter.set_name("Firmware images (*.bin)")
        bin_filter.add_pattern("*.bin")
        dialog.add_filter(bin_filter)

        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            self.firmware_entries["app"].set_text(path)
            self._firmware_offset = None  # manual pick: use this profile's merge_offset default
        dialog.destroy()

    def on_flash_firmware_clicked(self, _button):
        if self._worker_running:
            self.set_status("Another operation is already in progress.")
            return

        port = self.port_combo.get_active_text()
        device_key = self.device_combo.get_active_id() or next(iter(DEVICE_PROFILES))
        profile = DEVICE_PROFILES[device_key]

        if not port:
            self.set_status("No serial port selected.")
            return

        path = self.firmware_entries["app"].get_text().strip()
        if not path or not Path(path).is_file():
            self.set_status("Select a valid firmware .bin file first.")
            return

        if find_esptool() is None:
            self.set_status("esptool not found (sudo apt install esptool)")
            return

        self.connect_btn.set_sensitive(False)
        self.flash_btn.set_sensitive(False)
        self.download_btn.set_sensitive(False)
        self._worker_running = True
        threading.Thread(
            target=self._flash_worker,
            args=(port, profile, path),
            daemon=True,
        ).start()

    def _flash_worker(self, port, profile, path):
        try:
            esptool_bin = find_esptool()
            offset = self._firmware_offset or profile["merge_offset"]
            cmd = [
                esptool_bin,
                "--chip", profile["chip"],
                "--port", port,
                "--baud", str(FLASH_BAUD_RATE),
                # This Debian's esptool package is missing stub_flasher_32/32s2/32s3.json
                # (only c2/c3/c6/h2/p4/8266 stubs are shipped) — --no-stub avoids that by
                # talking to the ROM bootloader directly. Slightly slower, always works.
                "--no-stub",
                "write_flash",
                offset, path,
            ]

            self.set_status(f"Flashing {profile['label']}…")
            self.log(f"--- {' '.join(cmd)} ---")

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:
                self.log(line)
            proc.wait()

            if proc.returncode == 0:
                self.set_status("Firmware flashed successfully. Power-cycle the Sidekick.")
            else:
                self.set_status(f"Flash failed (exit code {proc.returncode}). See log for details.")
        except Exception as e:
            self.log(f"ERROR: {e}")
            self.set_status(f"Flash error: {e}")
        finally:
            self._worker_running = False
            GLib.idle_add(self.connect_btn.set_sensitive, True)
            GLib.idle_add(self.flash_btn.set_sensitive, True)
            GLib.idle_add(self.download_btn.set_sensitive, True)

    def _read_line(self, ser, deadline):
        """Read one line from serial, or None if nothing arrived before deadline."""
        while time.time() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            self.log(f"<<< {line}")
            return line
        return None

    def _query_firmware_version(self, ser):
        """Query GETVERSION and return (version, board) from the VERSION=/BOARD= replies."""
        ser.reset_input_buffer()
        ser.write(b"GETVERSION\n")
        self.log(">>> GETVERSION")
        version = None
        board = None
        deadline = time.time() + VERSION_QUERY_TIMEOUT_S
        while time.time() < deadline:
            line = self._read_line(ser, deadline)
            if line is None:
                break
            if line.startswith("VERSION="):
                version = line.split("=", 1)[1]
            elif line.startswith("BOARD="):
                board = line.split("=", 1)[1]
            if version and board:
                break
        return version, board

    def _apply_detected_board(self, board):
        if board in DEVICE_PROFILES:
            self.device_combo.set_active_id(board)
        else:
            self.log(f"(BOARD '{board}' has no local DEVICE_PROFILES entry yet)")

    def _provision_worker(self, port, ssid, password, server_addr):
        try:
            self.set_status(f"Opening {port}…")
            self.log(f"--- Opening {port} @ {BAUD_RATE} ---")
            with serial.Serial(port, BAUD_RATE, timeout=1) as ser:
                self._ser = ser
                time.sleep(0.3)

                version, board = self._query_firmware_version(ser)
                if version:
                    label = f"Firmware: v{version}" + (f" (board: {board})" if board else "")
                    self.set_status(f"Sidekick firmware v{version} detected. Connecting…")
                    GLib.idle_add(self.firmware_label.set_text, label)
                    if board:
                        GLib.idle_add(self._apply_detected_board, board)
                else:
                    self.log("(no firmware version response)")
                    GLib.idle_add(self.firmware_label.set_text, "Firmware: unknown")

                ser.reset_input_buffer()
                cmd = f"SETWIFI={ssid}|{password}\n"
                ser.write(cmd.encode())
                self.log(f">>> SETWIFI={ssid}|***")
                self.set_status(f"Requesting connection to '{ssid}'…")

                ip = None
                deadline = time.time() + CONNECT_TIMEOUT_S
                while time.time() < deadline:
                    line = self._read_line(ser, deadline)
                    if line is None:
                        break
                    if line.startswith("IP="):
                        ip = line.split("=", 1)[1]
                    elif line == "WIFI=CONNECTED":
                        continue
                    elif line == "WIFI=FAILED":
                        self.set_status("Sidekick failed to connect to Wi-Fi.")
                        return
                    if ip:
                        break

                if not ip or ip == "NONE":
                    self.set_status("Timed out waiting for Wi-Fi connection.")
                    return

                self.set_status(f"Sidekick connected, IP: {ip}")

                if server_addr:
                    ser.write(f"SERVER={server_addr}\n".encode())
                    self.log(f">>> SERVER={server_addr}")
                    self.set_status(f"Sidekick ready — IP {ip} (server address sent: {server_addr})")
                else:
                    self.set_status(f"Sidekick connected at {ip} (no server address sent).")
        except Exception as e:
            self.log(f"ERROR: {e}")
            self.set_status(f"Error: {e}")
        finally:
            self._ser = None
            self._worker_running = False
            GLib.idle_add(self.connect_btn.set_sensitive, True)
            GLib.idle_add(self.flash_btn.set_sensitive, True)
            GLib.idle_add(self.download_btn.set_sensitive, True)

    def on_close(self, _widget):
        if self.parent_app is None:
            Gtk.main_quit()


if __name__ == "__main__":
    Gtk.init([])
    win = SidekickSetupWindow()
    win.show_all()
    win.present()
    Gtk.main()
