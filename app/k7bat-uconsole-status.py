#!/usr/bin/env python3
"""
K7BAT uConsole Status App
Version 1.0.0

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
from pathlib import Path

APP_NAME = "K7BAT uConsole Status App"
APP_VERSION = "1.0.0"
REFRESH_SECONDS = 4

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

    raw = run("timeout 2 gpspipe -w -n 12", timeout=3)
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

def launch(command):
    try:
        subprocess.Popen(
            ["/bin/sh", "-lc", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

CSS = b"""
window { background: #15171b; color: #f2f2f2; }
frame { border-color: #3a3d44; }
label { color: #f2f2f2; }
button { min-height: 30px; }
.title { font-size: 22px; font-weight: 700; }
.metric { font-size: 16px; font-weight: 700; }
.subtle { color: #b8bcc5; }
.status-on { color: #32d15d; font-weight: 700; }
.status-off { color: #8b909a; }
.status-unknown { color: #e4a72b; font-weight: 700; }
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

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(outer)

        title = Gtk.Label(label=APP_NAME)
        title.get_style_context().add_class("title")
        outer.pack_start(title, False, False, 0)

        subtitle = Gtk.Label(label=f"v{APP_VERSION} • K7BAT")
        subtitle.get_style_context().add_class("subtle")
        outer.pack_start(subtitle, False, False, 0)

        metrics = Gtk.Grid(column_spacing=18, row_spacing=5)
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

        panels = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
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

        apps = Gtk.Box(spacing=4)
        outer.pack_start(apps, False, False, 0)
        buttons = [
            ("GPS Nav","navit","navit"),
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
            b.set_sensitive(command_exists(check))
            b.connect("clicked", lambda _b, c=cmd: launch(c))
            apps.pack_start(b, True, True, 0)

        self.status = Gtk.Label(label="Ready")
        self.status.set_xalign(0)
        self.status.get_style_context().add_class("subtle")
        outer.pack_start(self.status, False, False, 0)

        self.show_all()
        self.refresh_async()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self.refresh_async)

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
        val = Gtk.Label(label="—")
        val.set_xalign(0)
        val.set_line_wrap(True)
        row.pack_start(name, False, False, 0)
        row.pack_start(val, True, True, 0)
        parent.pack_start(row, False, False, 0)
        self.labels[key] = val

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
            data = self.collect()
            GLib.idle_add(self.apply_data, data)
        threading.Thread(target=worker, daemon=True).start()
        return True

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
        return False

Gtk.init([])
App()
Gtk.main()
