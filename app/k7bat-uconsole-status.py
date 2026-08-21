#!/usr/bin/env python3
"""
K7BAT uConsole Status App
Version 1.0.1

GTK3 dashboard for ClockworkPi uConsole systems, especially Raspberry Pi CM4/CM5
systems equipped with HackerGadgets AIO V2 and AC1200 hardware.

Copyright (c) 2026 K7BAT
Licensed under the MIT License.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

APP_NAME = "K7BAT uConsole Status App"
APP_VERSION = "1.0.1"
REFRESH_SECONDS = 4
CONFIG_PATH = Path.home() / ".config" / "k7bat-uconsole-status" / "settings.json"

GPS_NAV_OPTIONS = [
    {"id": "navit", "label": "Navit", "commands": ["navit"]},
    {"id": "puremaps", "label": "Pure Maps", "commands": ["pure-maps", "puremaps"]},
    {"id": "organicmaps", "label": "Organic Maps", "commands": ["organicmaps", "omaps", "OMaps"]},
    {"id": "pygpsclient", "label": "PyGPSClient", "commands": ["pygpsclient"]},
]

def run(cmd, timeout=2):
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True,
            stderr=subprocess.DEVNULL, timeout=timeout
        ).strip()
    except Exception:
        return ""

def run_rc(cmd, timeout=6):
    try:
        p = subprocess.run(
            cmd, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout
        )
        return p.returncode, p.stdout.strip()
    except Exception as e:
        return 1, str(e)

def load_settings():
    default = {"gps_nav_app": "navit"}
    try:
        if not CONFIG_PATH.exists():
            return default
        data = json.loads(CONFIG_PATH.read_text())
        if not isinstance(data, dict):
            return default
        return {**default, **data}
    except Exception:
        return default

def save_settings(settings):
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(settings, indent=2) + "\n")
    except Exception:
        pass

def run_stdout(cmd, timeout=3):
    try:
        p = subprocess.run(
            cmd, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=timeout
        )
        return p.stdout.strip()
    except subprocess.TimeoutExpired as e:
        out = e.stdout
        if out is None:
            return ""
        if isinstance(out, bytes):
            return out.decode(errors="ignore").strip()
        return str(out).strip()
    except Exception:
        return ""

def human_gib(n):
    try:
        return f"{float(n)/(1024**3):.1f} GB"
    except Exception:
        return "—"

def cpu_temp():
    vals = []
    for p in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            v = float(p.read_text().strip())
            if v > 1000:
                v /= 1000
            if 0 < v < 150:
                vals.append(v)
        except Exception:
            pass
    return f"{max(vals):.0f} °C" if vals else "—"

def memory():
    try:
        d = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            d[k] = int(v.strip().split()[0]) * 1024
        used = d["MemTotal"] - d["MemAvailable"]
        return f"{human_gib(used)} / {human_gib(d['MemTotal'])}"
    except Exception:
        return "—"

def disk():
    try:
        d = shutil.disk_usage("/")
        return f"{human_gib(d.free)} free / {human_gib(d.total)}"
    except Exception:
        return "—"

def battery():
    for p in Path("/sys/class/power_supply").glob("*"):
        try:
            if (p / "type").read_text().strip().lower() == "battery":
                cap = (p / "capacity").read_text().strip()
                stat = (p / "status").read_text().strip()
                return f"{cap}% ({stat})"
        except Exception:
            pass
    return "Not exposed"

def service_state(name):
    return "RUNNING" if run(f"systemctl is-active {name}") == "active" else "OFF"

def ip_info():
    out = run("ip -4 -br addr show up")
    vals = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] != "lo":
            vals.append(f"{parts[0]} {parts[2]}")
    return "  •  ".join(vals) if vals else "—"

def interface_driver(iface):
    return run(f"ethtool -i {iface} 2>/dev/null | awk '/^driver:/ {{print $2}}'") or "unknown"

def friendly_wifi_name(iface, driver_name):
    d = driver_name.lower()
    if d == "mt7921u":
        return "HackerGadgets AC1200 / MediaTek"
    if "8821au" in d or d == "rtl8811au":
        return "TP-Link AC600 / Realtek"
    if iface == "wlan0" and ("brcm" in d or "brcmfmac" in d):
        return "CM4/CM5 onboard Wi-Fi"
    return driver_name

def wifi_interfaces():
    ifaces = []
    for p in sorted(Path("/sys/class/net").glob("wlan*")):
        iface = p.name
        drv = interface_driver(iface)
        friendly = friendly_wifi_name(iface, drv)
        info = run(f"iw dev {iface} info")
        link = run(f"iw dev {iface} link")
        typ = re.search(r"\btype\s+(\S+)", info)
        ch = re.search(r"channel\s+(\d+)", info)
        ssid = re.search(r"SSID:\s*(.+)", link)
        sig = re.search(r"signal:\s*(-?[\d.]+)\s*dBm", link)
        state = run(f"cat /sys/class/net/{iface}/operstate")
        parts = [friendly]
        parts.append(typ.group(1) if typ else state or "unknown")
        if ssid:
            parts.append(ssid.group(1))
        if ch:
            parts.append("ch " + ch.group(1))
        if sig:
            parts.append(sig.group(1) + " dBm")
        ifaces.append((iface, " • ".join(parts)))
    return ifaces

def ethernet():
    vals = []
    for p in sorted(Path("/sys/class/net").iterdir()):
        if p.name.startswith(("eth", "en")):
            vals.append(f"{p.name} {run(f'cat {p}/operstate') or 'unknown'}")
    return ", ".join(vals) if vals else "—"

def bluetooth():
    return "ON" if service_state("bluetooth") == "RUNNING" else "OFF"

def gps_data():
    result = {
        "fix": "gpsd off", "sats": "—", "pos": "—",
        "speed": "—", "track": "—", "device": "—"
    }
    if service_state("gpsd") != "RUNNING" and run("systemctl is-active gpsd.socket") != "active":
        return result

    raw = run_stdout("gpspipe -w -n 12", timeout=3)
    tpv, dev = {}, None
    sats = None
    for line in raw.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get("class") == "TPV":
            tpv.update(j)
            dev = j.get("device") or dev
        elif j.get("class") == "DEVICE":
            dev = j.get("path") or dev
        elif j.get("class") == "SKY":
            sats = j.get("uSat") if j.get("uSat") is not None else j.get("nSat")

    mode = tpv.get("mode", 0)
    result["fix"] = {0:"NO DATA",1:"NO FIX",2:"2D FIX",3:"3D FIX"}.get(mode, str(mode))
    result["sats"] = str(sats) if sats is not None else "—"
    result["device"] = dev or "—"
    lat, lon = tpv.get("lat"), tpv.get("lon")
    if isinstance(lat, (int,float)) and isinstance(lon, (int,float)):
        result["pos"] = f"{lat:.5f}, {lon:.5f}"
    sp = tpv.get("speed")
    if isinstance(sp, (int,float)):
        result["speed"] = f"{sp*2.23694:.1f} mph"
    tr = tpv.get("track")
    if isinstance(tr, (int,float)):
        result["track"] = f"{tr:.0f}°"
    return result

def aio_available():
    return bool(shutil.which("aiov2_ctl"))

def parse_aio_states():
    states = {"GPS": None, "SDR": None, "LORA": None}
    if not aio_available():
        return states
    output = run("aiov2_ctl --status", 3) or run("aiov2_ctl --power", 3)
    for dev in states:
        for line in output.splitlines():
            if dev.lower() in line.lower():
                low = line.lower()
                if re.search(r"\b(on|enabled|high)\b", low):
                    states[dev] = True
                elif re.search(r"\b(off|disabled|low)\b", low):
                    states[dev] = False
    # Useful service-derived fallback for SDR.
    if states["SDR"] is None and service_state("readsb") == "RUNNING":
        states["SDR"] = True
    return states

def command_exists(cmd):
    return bool(shutil.which(cmd))

def resolve_first_command(candidates):
    for cmd in candidates:
        if command_exists(cmd):
            return cmd
    return None

def launch(command):
    try:
        subprocess.Popen(
            ["/bin/sh", "-lc", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

def launch_with_status(app, name, command):
    app.status.set_text(f"Launching {name}…")
    try:
        p = subprocess.Popen(
            ["/bin/sh", "-lc", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        def watcher():
            # If a GUI app dies immediately, report it instead of implying success.
            try:
                p.wait(timeout=2.5)
                if name == "GPS Nav":
                    GLib.idle_add(app.status.set_text, "GPS Nav exited. Navit needs a mapset configured.")
                else:
                    GLib.idle_add(app.status.set_text, f"{name} exited immediately")
            except subprocess.TimeoutExpired:
                GLib.idle_add(app.status.set_text, f"{name} launched")
        threading.Thread(target=watcher, daemon=True).start()
    except Exception as e:
        app.status.set_text(f"{name}: launch failed — {e}")

CSS = b"""
window {
    background: #101318;
    color: #eaf0f7;
}

frame {
    border-color: #2d3744;
    border-width: 1px;
}

label {
    color: #eaf0f7;
}

button {
    min-height: 32px;
    border-radius: 8px;
}

.title {
    font-size: 24px;
    font-weight: 800;
}

.metric {
    font-size: 17px;
    font-weight: 700;
}

.subtle {
    color: #9aa6b5;
}

.status-on { color: #39d98a; font-weight: 700; }
.status-off { color: #7c8797; }
.status-unknown { color: #f4b740; font-weight: 700; }

.chip {
    border-radius: 12px;
    padding: 3px 8px;
    font-weight: 700;
}

.chip-good {
    background: #143f2c;
    color: #86e4b6;
}

.chip-warn {
    background: #4a3a12;
    color: #ffd27b;
}

.chip-bad {
    background: #4a1f1f;
    color: #ff9a9a;
}

.chip-muted {
    background: #26303b;
    color: #b9c3d1;
}
"""

class App(Gtk.Window):
    def __init__(self):
        super().__init__(title=APP_NAME)
        self.set_default_size(800, 500)
        self.set_border_width(10)
        self.connect("destroy", Gtk.main_quit)
        self.labels = {}
        self.radio_dots = {}
        self.radio_text = {}
        self.chips = {}
        self.settings = load_settings()
        self.launch_actions = {}
        self.launch_buttons = {}

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(outer)

        title = Gtk.Label(label=APP_NAME)
        title.get_style_context().add_class("title")
        outer.pack_start(title, False, False, 0)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        outer.pack_start(header, False, False, 0)

        subtitle = Gtk.Label(label=f"v{APP_VERSION} • K7BAT")
        subtitle.get_style_context().add_class("subtle")
        subtitle.set_xalign(0)
        header.pack_start(subtitle, True, True, 0)

        settings_btn = Gtk.Button(label="Settings")
        settings_btn.connect("clicked", self.open_settings_dialog)
        header.pack_end(settings_btn, False, False, 0)

        chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        outer.pack_start(chips_box, False, False, 0)
        for key, text in [
            ("chip_fix", "GPS: --"),
            ("chip_wifi", "Wi-Fi: --"),
            ("chip_gpsd", "gpsd: --"),
            ("chip_readsb", "readsb: --"),
        ]:
            chip = Gtk.Label(label=text)
            chip.get_style_context().add_class("chip")
            chip.get_style_context().add_class("chip-muted")
            chips_box.pack_start(chip, False, False, 0)
            self.chips[key] = chip

        metrics = Gtk.Grid(column_spacing=22, row_spacing=7)
        outer.pack_start(metrics, False, False, 2)
        for i, (key, label) in enumerate([
            ("cpu","CPU"), ("ram","RAM"), ("disk","NVMe"), ("battery","Battery")
        ]):
            row = Gtk.Box(spacing=8)
            l = Gtk.Label(label=label)
            l.get_style_context().add_class("metric")
            v = Gtk.Label(label="—")
            v.set_xalign(1.0)
            row.pack_start(l, False, False, 0)
            row.pack_end(v, True, True, 0)
            metrics.attach(row, i % 2, i // 2, 1, 1)
            self.labels[key] = v

        panels = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        outer.pack_start(panels, True, True, 2)

        self.gps_box = self.make_frame(panels, "GPS / Services")
        self.net_box = self.make_frame(panels, "Network / Wireless")

        for key, label in [
            ("fix","GPS Fix"), ("sats","Satellites"), ("gpsdev","GPS Device"),
            ("pos","Position"), ("speed","Speed"), ("track","Heading"),
            ("gpsd","gpsd"), ("readsb","readsb")
        ]:
            self.add_row(self.gps_box, key, label)

        self.wifi_rows = []
        self.add_row(self.net_box, "ip", "IP")
        self.add_row(self.net_box, "eth", "Ethernet")
        self.add_row(self.net_box, "bt", "Bluetooth")
        self.add_row(self.net_box, "wifi1", "Wi-Fi 1")
        self.add_row(self.net_box, "wifi2", "Wi-Fi 2")
        self.add_row(self.net_box, "wifi3", "Wi-Fi 3")

        radio_frame = Gtk.Frame(label="HackerGadgets AIO V2 Radio Power")
        outer.pack_start(radio_frame, False, False, 0)
        radio_box = Gtk.Box(spacing=10)
        radio_box.set_border_width(7)
        radio_frame.add(radio_box)

        if aio_available():
            for dev in ("GPS","SDR","LORA"):
                group = Gtk.Box(spacing=5)
                dot = Gtk.Label(label="●")
                text = Gtk.Label(label=f"{dev} ?")
                self.radio_dots[dev] = dot
                self.radio_text[dev] = text
                group.pack_start(dot, False, False, 0)
                group.pack_start(text, False, False, 3)
                for state in ("on","off"):
                    b = Gtk.Button(label=state.upper())
                    b.connect("clicked", lambda _b, d=dev, s=state: self.radio_command(d, s))
                    group.pack_start(b, False, False, 0)
                radio_box.pack_start(group, True, True, 0)
        else:
            lab = Gtk.Label(label="aiov2_ctl not detected — radio controls unavailable")
            lab.get_style_context().add_class("subtle")
            radio_box.pack_start(lab, True, True, 0)

        apps = Gtk.Box(spacing=6)
        outer.pack_start(apps, False, False, 0)
        buttons = [
            ("GPS Nav",None,None),
            ("PyGPS","pygpsclient","pygpsclient"),
            ("SDR++","sdrpp","sdrpp"),
            ("GQRX","gqrx","gqrx"),
            ("ADS-B","xdg-open http://127.0.0.1/tar1090/","xdg-open"),
            ("Wireshark","wireshark","wireshark"),
            ("Kismet","xdg-open http://127.0.0.1:2501/","xdg-open"),
            ("AIO Control","aiov2_ctl --gui","aiov2_ctl"),
        ]
        for name, cmd, check in buttons:
            b = Gtk.Button(label=name)
            if name == "GPS Nav":
                self.launch_buttons[name] = b
                b.connect("clicked", lambda _b, n=name: self.on_launch_clicked(n))
                apps.pack_start(b, True, True, 0)
                continue

            available = command_exists(check)
            b.set_sensitive(available)
            self.launch_actions[name] = cmd
            if available:
                b.set_tooltip_text(f"Launch {name}")
            else:
                b.set_tooltip_text(f"Missing dependency: {check}")
            b.connect("clicked", lambda _b, n=name: self.on_launch_clicked(n))
            apps.pack_start(b, True, True, 0)

        self.status = Gtk.Label(label="Ready")
        self.status.set_xalign(0)
        self.status.get_style_context().add_class("subtle")
        outer.pack_start(self.status, False, False, 0)

        self.last_update = Gtk.Label(label="Updated: --")
        self.last_update.set_xalign(0)
        self.last_update.get_style_context().add_class("subtle")
        outer.pack_start(self.last_update, False, False, 0)

        self.show_all()
        self.refresh_gps_nav_button()
        self.refresh_async()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self.refresh_async)

    def selected_gps_option(self):
        selected = self.settings.get("gps_nav_app", "navit")
        for opt in GPS_NAV_OPTIONS:
            if opt["id"] == selected:
                return opt
        return GPS_NAV_OPTIONS[0]

    def gps_option_by_id(self, option_id):
        for opt in GPS_NAV_OPTIONS:
            if opt["id"] == option_id:
                return opt
        return None

    def gps_option_status(self, option):
        cmd = resolve_first_command(option["commands"])
        return {
            "available": bool(cmd),
            "command": cmd,
            "label": option["label"],
            "check": option["commands"][0],
        }

    def refresh_gps_nav_button(self):
        b = self.launch_buttons.get("GPS Nav")
        if not b:
            return
        option = self.selected_gps_option()
        status = self.gps_option_status(option)
        b.set_label(f"GPS Nav ({option['label']})")
        if status["available"]:
            b.set_sensitive(True)
            b.set_tooltip_text(f"Launch {option['label']}")
            self.launch_actions["GPS Nav"] = status["command"]
        else:
            b.set_sensitive(False)
            b.set_tooltip_text(f"Selected app is not installed: {status['check']}")
            self.launch_actions["GPS Nav"] = None

    def on_launch_clicked(self, name):
        cmd = self.launch_actions.get(name)
        if not cmd:
            self.status.set_text(f"{name}: no launch command configured")
            return
        launch_with_status(self, name, cmd)

    def open_settings_dialog(self, _button):
        dialog = Gtk.Dialog(
            title="Settings",
            transient_for=self,
            flags=0,
        )
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_spacing(8)

        info = Gtk.Label(label="Choose which app the GPS Nav button should launch.")
        info.set_xalign(0)
        info.get_style_context().add_class("subtle")
        content.pack_start(info, False, False, 0)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        content.pack_start(row, False, False, 0)
        row.pack_start(Gtk.Label(label="GPS Nav app:"), False, False, 0)

        combo = Gtk.ComboBoxText()
        current_id = self.selected_gps_option()["id"]
        for opt in GPS_NAV_OPTIONS:
            status = self.gps_option_status(opt)
            suffix = "installed" if status["available"] else f"missing ({status['check']})"
            combo.append(opt["id"], f"{opt['label']} [{suffix}]")
        combo.set_active_id(current_id)
        row.pack_start(combo, True, True, 0)

        dialog.show_all()
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            selected = combo.get_active_id() or "navit"
            self.settings["gps_nav_app"] = selected
            save_settings(self.settings)
            self.refresh_gps_nav_button()
            opt = self.gps_option_by_id(selected)
            if opt:
                self.status.set_text(f"Saved: GPS Nav set to {opt['label']}")
        dialog.destroy()

    def make_frame(self, parent, title):
        f = Gtk.Frame(label=title)
        parent.pack_start(f, True, True, 0)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_border_width(8)
        f.add(box)
        return box

    def add_row(self, parent, key, title):
        row = Gtk.Box(spacing=6)
        name = Gtk.Label(label=title)
        name.set_size_request(115, -1)
        name.set_xalign(0)
        name.get_style_context().add_class("subtle")
        val = Gtk.Label(label="—")
        val.set_xalign(0)
        val.set_line_wrap(True)
        row.pack_start(name, False, False, 0)
        row.pack_start(val, True, True, 0)
        parent.pack_start(row, False, False, 0)
        self.labels[key] = val

    def set_chip(self, key, text, level):
        chip = self.chips.get(key)
        if not chip:
            return
        chip.set_text(text)
        ctx = chip.get_style_context()
        for cls in ("chip-good", "chip-warn", "chip-bad", "chip-muted"):
            ctx.remove_class(cls)
        ctx.add_class({
            "good": "chip-good",
            "warn": "chip-warn",
            "bad": "chip-bad",
            "muted": "chip-muted",
        }.get(level, "chip-muted"))

    def set_radio_visual(self, dev, state):
        dot = self.radio_dots.get(dev)
        text = self.radio_text.get(dev)
        if not dot or not text:
            return
        for cls in ("status-on","status-off","status-unknown"):
            dot.get_style_context().remove_class(cls)
            text.get_style_context().remove_class(cls)
        if state is True:
            dot.set_text("●"); text.set_text(f"{dev} ON")
            dot.get_style_context().add_class("status-on")
            text.get_style_context().add_class("status-on")
        elif state is False:
            dot.set_text("●"); text.set_text(f"{dev} OFF")
            dot.get_style_context().add_class("status-off")
            text.get_style_context().add_class("status-off")
        else:
            dot.set_text("●"); text.set_text(f"{dev} ?")
            dot.get_style_context().add_class("status-unknown")
            text.get_style_context().add_class("status-unknown")

    def radio_command(self, dev, state):
        self.status.set_text(f"{dev}: requesting {state.upper()}…")
        def worker():
            rc, out = run_rc(f"aiov2_ctl {dev} {state}", 10)
            msg = f"{dev}: {state.upper()} requested" if rc == 0 else f"{dev}: command failed"
            if out and rc != 0:
                msg += f" — {out.splitlines()[-1][:90]}"
            GLib.idle_add(self.status.set_text, msg)
            GLib.timeout_add_seconds(1, self.refresh_async)
        threading.Thread(target=worker, daemon=True).start()

    def collect(self):
        g = gps_data()
        w = wifi_interfaces()
        return {
            "cpu": cpu_temp(), "ram": memory(), "disk": disk(), "battery": battery(),
            "gps": g, "ip": ip_info(), "eth": ethernet(), "bt": bluetooth(),
            "gpsd": service_state("gpsd"), "readsb": service_state("readsb"),
            "wifi": w, "aio": parse_aio_states()
        }

    def refresh_async(self):
        if getattr(self, "_refreshing", False):
            return True
        self._refreshing = True
        def worker():
            try:
                data = self.collect()
                GLib.idle_add(self.apply_data, data)
            except Exception as e:
                GLib.idle_add(self.on_refresh_error, str(e))
        threading.Thread(target=worker, daemon=True).start()
        return True

    def on_refresh_error(self, err):
        self._refreshing = False
        self.status.set_text(f"Refresh error: {err[:100]}")
        return False

    def apply_data(self, d):
        self._refreshing = False
        self.labels["cpu"].set_text(d["cpu"])
        self.labels["ram"].set_text(d["ram"])
        self.labels["disk"].set_text(d["disk"])
        self.labels["battery"].set_text(d["battery"])
        g = d["gps"]
        self.labels["fix"].set_text(g["fix"])
        self.labels["sats"].set_text(g["sats"])
        self.labels["gpsdev"].set_text(g["device"])
        self.labels["pos"].set_text(g["pos"])
        self.labels["speed"].set_text(g["speed"])
        self.labels["track"].set_text(g["track"])
        self.labels["gpsd"].set_text(d["gpsd"])
        self.labels["readsb"].set_text(d["readsb"])
        self.labels["ip"].set_text(d["ip"])
        self.labels["eth"].set_text(d["eth"])
        self.labels["bt"].set_text(d["bt"])
        for i, key in enumerate(("wifi1","wifi2","wifi3")):
            if i < len(d["wifi"]):
                iface, detail = d["wifi"][i]
                self.labels[key].set_text(f"{iface}: {detail}")
            else:
                self.labels[key].set_text("—")
        for dev, state in d["aio"].items():
            self.set_radio_visual(dev, state)

        fix_text = g["fix"]
        if "3D" in fix_text or "2D" in fix_text:
            self.set_chip("chip_fix", f"GPS: {fix_text}", "good")
        elif "NO FIX" in fix_text:
            self.set_chip("chip_fix", f"GPS: {fix_text}", "warn")
        else:
            self.set_chip("chip_fix", f"GPS: {fix_text}", "muted")

        wifi_ok = len(d["wifi"]) > 0
        self.set_chip("chip_wifi", f"Wi-Fi: {'OK' if wifi_ok else 'NONE'}", "good" if wifi_ok else "bad")
        self.set_chip("chip_gpsd", f"gpsd: {d['gpsd']}", "good" if d["gpsd"] == "RUNNING" else "warn")
        self.set_chip("chip_readsb", f"readsb: {d['readsb']}", "good" if d["readsb"] == "RUNNING" else "muted")

        self.last_update.set_text("Updated: " + datetime.now().strftime("%H:%M:%S"))
        return False

Gtk.init([])
App()
Gtk.main()
