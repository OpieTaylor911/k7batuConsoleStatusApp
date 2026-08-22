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
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

APP_NAME = "K7BAT uConsole Status App"
APP_VERSION = "1.1.5"
REFRESH_SECONDS = 4
CONFIG_PATH = Path.home() / ".config" / "k7bat-uconsole-status" / "settings.json"
PLUGINS_PATH = Path.home() / ".config" / "k7bat-uconsole-status" / "plugins.json"
PROFILE_SNAPSHOT_PATH = Path.home() / ".config" / "k7bat-uconsole-status" / "profile-snapshot.json"
PROFILE_SNAPSHOT_DIR = Path.home() / ".config" / "k7bat-uconsole-status" / "snapshots"
MISSION_RECORD_DIR = Path.home() / ".config" / "k7bat-uconsole-status" / "missions"
AUTO_SNAPSHOT_KEEP_PER_TAG = 20
APP_ICON_DIR = Path(__file__).resolve().parent / "icons"

DEFAULT_ALERTS = {
    "enabled": True,
    "cpu_temp_c": 78,
    "ram_used_pct": 90,
    "disk_free_pct": 10,
    "battery_pct": 25,
    "require_gps_fix": False,
    "require_wifi": False,
}

PROFILE_PRESETS = {
    "mobile": {
        "label": "Mobile",
        "gps_nav_app": "organicmaps",
        "visible_launchers": [
            "GPS Nav", "Pure Maps", "Organic Maps", "PyGPS", "OSM Scout",
            "ADS-B", "Kismet", "AIO Control",
        ],
        "alerts": {
            "enabled": True,
            "cpu_temp_c": 82,
            "ram_used_pct": 92,
            "disk_free_pct": 10,
            "battery_pct": 35,
            "require_gps_fix": True,
            "require_wifi": False,
        },
    },
    "base": {
        "label": "Base",
        "gps_nav_app": "puremaps",
        "visible_launchers": [
            "GPS Nav", "Pure Maps", "Organic Maps", "PyGPS", "OSM Scout",
            "SDR++", "GQRX", "ADS-B", "Wireshark", "Kismet", "AIO Control",
        ],
        "alerts": {
            "enabled": True,
            "cpu_temp_c": 80,
            "ram_used_pct": 90,
            "disk_free_pct": 8,
            "battery_pct": 20,
            "require_gps_fix": False,
            "require_wifi": False,
        },
    },
    "emergency": {
        "label": "Emergency",
        "gps_nav_app": "navit",
        "visible_launchers": [
            "GPS Nav", "Pure Maps", "Organic Maps", "PyGPS", "OSM Scout", "AIO Control",
        ],
        "alerts": {
            "enabled": True,
            "cpu_temp_c": 76,
            "ram_used_pct": 85,
            "disk_free_pct": 15,
            "battery_pct": 45,
            "require_gps_fix": True,
            "require_wifi": True,
        },
    },
}

GPS_NAV_OPTIONS = [
    {"id": "navit", "label": "Navit", "commands": ["navit"]},
    {
        "id": "puremaps",
        "label": "Pure Maps",
        "commands": [
            "pure-maps",
            "puremaps",
            "flatpak:app.puremaps.PureMaps",
            "flatpak:io.github.rinigus.PureMaps",
        ],
    },
    {
        "id": "organicmaps",
        "label": "Organic Maps",
        "commands": [
            "organicmaps",
            "omaps",
            "OMaps",
            "flatpak:app.organicmaps.desktop",
            "flatpak:com.organicmaps.desktop",
        ],
    },
    {
        "id": "osmscoutserver",
        "label": "OSM Scout Server",
        "commands": [
            "flatpak:io.github.rinigus.OSMScoutServer",
            "flatpak:io.github.rinigus.osmscout_server",
        ],
    },
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
    default = {
        "gps_nav_app": "navit",
        "alerts": dict(DEFAULT_ALERTS),
        "profile": "custom",
    }
    try:
        if not CONFIG_PATH.exists():
            return default
        data = json.loads(CONFIG_PATH.read_text())
        if not isinstance(data, dict):
            return default
        merged = {**default, **data}
        alerts = merged.get("alerts", {})
        if not isinstance(alerts, dict):
            alerts = {}
        merged["alerts"] = {**DEFAULT_ALERTS, **alerts}
        return merged
    except Exception:
        return default

def save_settings(settings):
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(settings, indent=2) + "\n")
    except Exception:
        pass

def load_plugins():
    try:
        if not PLUGINS_PATH.exists():
            return []
        data = json.loads(PLUGINS_PATH.read_text())
        if not isinstance(data, list):
            return []
        out = []
        for item in data:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            command = str(item.get("command", "")).strip()
            if not label or not command:
                continue
            out.append({
                "id": str(item.get("id") or label.lower().replace(" ", "-")),
                "label": label,
                "command": command,
                "check": str(item.get("check", "")).strip(),
                "tooltip": str(item.get("tooltip", "")).strip(),
            })
        return out
    except Exception:
        return []

def save_plugins(plugins):
    try:
        PLUGINS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLUGINS_PATH.write_text(json.dumps(plugins, indent=2) + "\n")
        return True
    except Exception:
        return False

def export_profile_snapshot(settings, plugins):
    payload = build_snapshot_payload(settings, plugins, source="manual", name="latest")
    try:
        PROFILE_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROFILE_SNAPSHOT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
        return True, f"Exported profile to {PROFILE_SNAPSHOT_PATH}"
    except Exception as e:
        return False, f"Profile export failed: {str(e)[:120]}"

def import_profile_snapshot(snapshot_path=None):
    try:
        source = Path(snapshot_path) if snapshot_path else PROFILE_SNAPSHOT_PATH
        if not source.exists():
            return False, None, None, f"Snapshot not found: {source}"
        data = json.loads(source.read_text())
        if not isinstance(data, dict):
            return False, None, None, "Snapshot file is invalid"
        settings = data.get("settings", {})
        plugins = data.get("plugins", [])
        if not isinstance(settings, dict):
            settings = {}
        if not isinstance(plugins, list):
            plugins = []
        return True, settings, plugins, f"Imported profile from {source}"
    except Exception as e:
        return False, None, None, f"Profile import failed: {str(e)[:120]}"

def build_snapshot_payload(settings, plugins, source="manual", name="snapshot", tags=None):
    if not isinstance(tags, list):
        tags = []
    return {
        "name": name,
        "source": source,
        "tags": tags,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "settings": settings,
        "plugins": plugins,
    }

def safe_snapshot_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip())
    cleaned = cleaned.strip("-._")
    return cleaned or "snapshot"

def normalize_snapshot_tags(tags):
    if tags is None:
        return []
    if isinstance(tags, str):
        raw = re.split(r"[\s,]+", tags)
    elif isinstance(tags, (list, tuple, set)):
        raw = [str(t) for t in tags]
    else:
        return []
    out = []
    seen = set()
    for item in raw:
        tag = safe_snapshot_name(str(item).lower())
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out

def save_named_snapshot(settings, plugins, name, source="manual", tags=None):
    try:
        PROFILE_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_name = safe_snapshot_name(name)
        path = PROFILE_SNAPSHOT_DIR / f"{safe_name}-{ts}.json"
        payload = build_snapshot_payload(
            settings,
            plugins,
            source=source,
            name=safe_name,
            tags=normalize_snapshot_tags(tags),
        )
        path.write_text(json.dumps(payload, indent=2) + "\n")
        if source == "auto":
            prune_auto_snapshots(AUTO_SNAPSHOT_KEEP_PER_TAG)
        return True, path
    except Exception:
        return False, None

def list_profile_snapshots(limit=100):
    if not PROFILE_SNAPSHOT_DIR.exists():
        return []
    files = sorted(
        PROFILE_SNAPSHOT_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    out = []
    for p in files:
        label = p.stem
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict):
                nm = data.get("name")
                src = data.get("source")
                when = data.get("exported_at")
                tags = normalize_snapshot_tags(data.get("tags", []))
                if nm:
                    label = f"{nm}"
                if src:
                    label += f" ({src})"
                if tags:
                    label += f" [{' '.join([f'#{t}' for t in tags])}]"
                if when:
                    label += f" {when}"
                out.append({
                    "path": str(p),
                    "label": label,
                    "name": nm or p.stem,
                    "source": src or "",
                    "tags": tags,
                    "exported_at": when or "",
                })
                continue
        except Exception:
            pass
        out.append({
            "path": str(p),
            "label": label,
            "name": p.stem,
            "source": "",
            "tags": [],
            "exported_at": "",
        })
    return out

def find_latest_auto_snapshot(tag=None):
    tag_filter = normalize_snapshot_tags([tag]) if tag else []
    want_tag = tag_filter[0] if tag_filter else None
    snaps = list_profile_snapshots(limit=500)
    for snap in snaps:
        if snap.get("source") != "auto":
            continue
        if want_tag and want_tag not in normalize_snapshot_tags(snap.get("tags", [])):
            continue
        return snap.get("path")
    return None

def auto_snapshot_retention_key(snapshot):
    tags = normalize_snapshot_tags(snapshot.get("tags", []))
    if "profile" in tags:
        for t in tags:
            if t not in ("auto", "profile"):
                return f"profile:{t}"
        return "profile"
    for t in tags:
        if t != "auto":
            return t
    return "auto"

def prune_auto_snapshots(max_per_key=AUTO_SNAPSHOT_KEEP_PER_TAG):
    if max_per_key < 1:
        return 0
    snaps = list_profile_snapshots(limit=2000)
    seen = {}
    removed = 0
    for snap in snaps:
        if snap.get("source") != "auto":
            continue
        key = auto_snapshot_retention_key(snap)
        count = seen.get(key, 0)
        if count >= max_per_key:
            if delete_profile_snapshot(snap.get("path")):
                removed += 1
            continue
        seen[key] = count + 1
    return removed

def mission_profile_hint(profile_id):
    if profile_id in PROFILE_PRESETS:
        return profile_id
    return "custom"

def delete_profile_snapshot(snapshot_path):
    try:
        p = Path(snapshot_path)
        if p.exists() and p.is_file():
            p.unlink()
            return True
    except Exception:
        pass
    return False

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
    val = cpu_temp_value()
    return f"{val:.0f} °C" if val is not None else "—"

def cpu_temp_value():
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
    if not vals:
        return None
    return max(vals)

def memory():
    used, total = memory_usage_bytes()
    if used is None or total is None:
        return "—"
    return f"{human_gib(used)} / {human_gib(total)}"

def memory_usage_bytes():
    try:
        d = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            d[k] = int(v.strip().split()[0]) * 1024
        used = d["MemTotal"] - d["MemAvailable"]
        return used, d["MemTotal"]
    except Exception:
        return None, None

def disk():
    free, total = disk_usage_bytes()
    if free is None or total is None:
        return "—"
    return f"{human_gib(free)} free / {human_gib(total)}"

def disk_usage_bytes():
    try:
        d = shutil.disk_usage("/")
        return d.free, d.total
    except Exception:
        return None, None

def battery():
    text, _, _ = battery_info()
    return text

def battery_info():
    for p in Path("/sys/class/power_supply").glob("*"):
        try:
            if (p / "type").read_text().strip().lower() == "battery":
                cap = (p / "capacity").read_text().strip()
                stat = (p / "status").read_text().strip()
                cap_val = int(cap)
                return f"{cap}% ({stat})", cap_val, stat
        except Exception:
            pass
    return "Not exposed", None, None

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

def launch_target_available(check):
    if not check:
        return True
    if isinstance(check, (list, tuple)):
        return resolve_first_command(check) is not None
    if isinstance(check, str) and check.startswith("flatpak:"):
        app_id = check.split(":", 1)[1]
        return flatpak_app_installed(app_id)
    return command_exists(check)

def flatpak_app_installed(app_id):
    if not command_exists("flatpak"):
        return False
    # Check both scopes because users may install flatpaks as system or user apps.
    for scope in ("--system", "--user"):
        rc, _ = run_rc(f"flatpak info {scope} {app_id}", timeout=4)
        if rc == 0:
            return True
    return False

def candidate_label(candidate):
    if not candidate:
        return "command"
    if isinstance(candidate, (list, tuple)):
        return ", ".join(candidate_label(c) for c in candidate[:3])
    if candidate.startswith("flatpak:"):
        return candidate.split(":", 1)[1]
    return candidate

def resolve_first_command(candidates):
    for candidate in candidates:
        if candidate.startswith("flatpak:"):
            app_id = candidate.split(":", 1)[1]
            if flatpak_app_installed(app_id):
                return f"flatpak run {app_id}"
            continue
        if command_exists(candidate):
            return candidate
    return None

def discover_flatpak_app_id(patterns):
    if not command_exists("flatpak"):
        return None
    out = run_stdout("flatpak list --app --columns=application,name", timeout=6)
    if not out:
        return None
    pats = [p.lower() for p in patterns]
    for line in out.splitlines():
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if not parts:
            continue
        app_id = parts[0]
        hay = line.lower()
        if any(p in hay or p in app_id.lower() for p in pats):
            return app_id
    return None

def resolve_gps_option_command(option):
    cmd = resolve_first_command(option["commands"])
    if cmd:
        return cmd

    oid = option.get("id")
    if oid == "puremaps":
        discovered = discover_flatpak_app_id(["puremaps", "pure maps", "rinigus.pure"])
        if discovered:
            return f"flatpak run {discovered}"
    if oid == "organicmaps":
        discovered = discover_flatpak_app_id(["organicmaps", "organic maps"])
        if discovered:
            return f"flatpak run {discovered}"
    if oid == "osmscoutserver":
        discovered = discover_flatpak_app_id(["osmscout", "rinigus.osm"])
        if discovered:
            return f"flatpak run {discovered}"
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
    min-height: 26px;
    border-radius: 8px;
}

.title {
    font-size: 24px;
    font-weight: 800;
}

.metric {
    font-size: 15px;
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
        self.set_border_width(6)
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self.on_key_press)
        self.labels = {}
        self.radio_dots = {}
        self.radio_text = {}
        self.chips = {}
        self.settings = load_settings()
        self.alert_settings = self.settings.get("alerts", dict(DEFAULT_ALERTS))
        self._updating_profile_combo = False
        self.launch_actions = {}
        self.launch_buttons = {}
        self.builtin_buttons = {}
        self.plugins = load_plugins()
        self.service_labels = {}
        self.icon_cache = {}
        self.mission_active = False
        self.mission_fp = None
        self.mission_file_path = None
        self.mission_started_at = None
        self.mission_stats = {}

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        outer.set_border_width(4)
        self.add(outer)

        layout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        outer.pack_start(layout, True, True, 0)

        main_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        layout.pack_start(main_col, True, True, 0)

        right_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right_controls.set_size_request(270, -1)
        layout.pack_start(right_controls, False, False, 0)

        logo_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        right_controls.pack_start(logo_row, False, False, 0)

        logo_candidates = [
            Path(__file__).resolve().parent / "k7bat-callsign-logo.png",
            Path(__file__).resolve().parent / "k7bat-callsign-logo.svg",
        ]
        for logo_path in logo_candidates:
            if not logo_path.exists():
                continue
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(logo_path),
                    width=240,
                    height=64,
                    preserve_aspect_ratio=True,
                )
                logo = Gtk.Image.new_from_pixbuf(pix)
                logo_row.pack_start(logo, False, False, 0)
                break
            except Exception:
                continue

        settings_btn = Gtk.Button(label="Settings")
        self.decorate_button(settings_btn, "settings", "Settings")
        settings_btn.connect("clicked", self.open_settings_dialog)
        logo_row.pack_start(settings_btn, False, False, 0)

        _, version_row = self.make_icon_info_row(right_controls, f"v{APP_VERSION} • K7BAT", "dashboard", 14)
        version_row.get_style_context().add_class("subtle")

        profile_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        right_controls.pack_start(profile_row, False, False, 0)
        profile_row.pack_start(self.make_icon_label("Profile:", "power", 14), False, False, 0)
        self.profile_combo = Gtk.ComboBoxText()
        self.profile_combo.append("custom", "Custom")
        for pid, preset in PROFILE_PRESETS.items():
            self.profile_combo.append(pid, preset["label"])
        self.profile_combo.set_active_id(self.settings.get("profile", "custom"))
        self.profile_combo.set_size_request(140, -1)
        self.profile_combo.connect("changed", self.on_profile_changed)
        profile_row.pack_start(self.profile_combo, True, True, 0)

        snapshot_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        right_controls.pack_start(snapshot_row, False, False, 0)

        export_btn = Gtk.Button(label="Export")
        self.decorate_button(export_btn, "dashboard", "Export")
        export_btn.connect("clicked", self.on_export_profile)
        snapshot_row.pack_start(export_btn, True, True, 0)

        import_btn = Gtk.Button(label="Import")
        self.decorate_button(import_btn, "terminal", "Import")
        import_btn.connect("clicked", self.on_import_profile)
        snapshot_row.pack_start(import_btn, True, True, 0)

        snapshots_btn = Gtk.Button(label="Snapshots")
        self.decorate_button(snapshots_btn, "dashboard", "Snapshots")
        snapshots_btn.connect("clicked", self.open_snapshots_dialog)
        snapshot_row.pack_start(snapshots_btn, True, True, 0)

        mission_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        right_controls.pack_start(mission_row, False, False, 0)
        self.mission_start_btn = Gtk.Button(label="Record")
        self.decorate_button(self.mission_start_btn, "radar", "Record")
        self.mission_start_btn.connect("clicked", self.on_start_mission)
        mission_row.pack_start(self.mission_start_btn, True, True, 0)

        self.mission_stop_btn = Gtk.Button(label="Stop")
        self.decorate_button(self.mission_stop_btn, "power", "Stop")
        self.mission_stop_btn.connect("clicked", self.on_stop_mission)
        self.mission_stop_btn.set_sensitive(False)
        mission_row.pack_start(self.mission_stop_btn, True, True, 0)

        self.mission_status, mission_status_row = self.make_icon_info_row(
            right_controls,
            "Mission: idle",
            "dashboard",
            14,
        )
        mission_status_row.get_style_context().add_class("subtle")

        hotkeys_label, hotkeys_row = self.make_icon_info_row(
            right_controls,
            "Hotkeys: Alt+1/2/3 presets • Alt+0 custom",
            "terminal",
            14,
            wrap=True,
        )
        hotkeys_row.get_style_context().add_class("subtle")

        service_header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        right_controls.pack_start(service_header_row, False, False, 0)
        service_header_row.pack_start(self.make_icon_label("Svc:", "network", 14), False, False, 0)

        for svc in ("gpsd", "bluetooth", "readsb"):
            stat = Gtk.Label(label=f"{svc}: --")
            stat.set_xalign(0)
            stat.get_style_context().add_class("subtle")
            self.service_labels[svc] = stat
            service_header_row.pack_start(stat, False, False, 0)

        self.restart_combo = Gtk.ComboBoxText()
        for svc in ("gpsd", "gpsd.socket", "bluetooth", "readsb", "NetworkManager"):
            self.restart_combo.append_text(svc)
        self.restart_combo.set_active(0)
        self.restart_combo.set_size_request(100, -1)
        restart_btn = Gtk.Button(label="Restart")
        self.decorate_button(restart_btn, "power", "Restart")
        restart_btn.connect("clicked", self.on_restart_selected)

        service_action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        service_action_row.pack_start(self.restart_combo, True, True, 0)
        service_action_row.pack_start(restart_btn, False, False, 0)
        right_controls.pack_start(service_action_row, False, False, 0)

        self.header_plugin_info, plugin_row = self.make_icon_info_row(right_controls, "Plugins: loading", "terminal", 14)
        plugin_row.get_style_context().add_class("subtle")

        self.status, status_row = self.make_icon_info_row(right_controls, "Ready", "radar", 14)
        status_row.get_style_context().add_class("subtle")

        self.last_update, update_row = self.make_icon_info_row(right_controls, "Updated: --", "dashboard", 14)
        update_row.get_style_context().add_class("subtle")

        chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        main_col.pack_start(chips_box, False, False, 0)
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

        self.alert_summary = Gtk.Label(label="Alerts: monitoring enabled")
        self.alert_summary.set_xalign(0)
        self.alert_summary.get_style_context().add_class("subtle")
        main_col.pack_start(self.alert_summary, False, False, 0)

        metrics = Gtk.Grid(column_spacing=22, row_spacing=7)
        main_col.pack_start(metrics, False, False, 2)
        for i, (key, label) in enumerate([
            ("cpu","CPU"), ("ram","RAM"), ("disk","NVMe"), ("battery","Battery")
        ]):
            row = Gtk.Box(spacing=8)
            metric_icon = {
                "cpu": "cpu",
                "ram": "memory",
                "disk": "nvme",
                "battery": "battery",
            }.get(key)
            l = self.make_icon_label(label, metric_icon, 15)
            l.get_style_context().add_class("metric")
            v = Gtk.Label(label="—")
            v.set_xalign(1.0)
            row.pack_start(l, False, False, 0)
            row.pack_end(v, True, True, 0)
            metrics.attach(row, i % 2, i // 2, 1, 1)
            self.labels[key] = v

        panels = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        main_col.pack_start(panels, False, False, 2)

        self.gps_box = self.make_frame(panels, "GPS / Services", "satellite")
        self.net_box = self.make_frame(panels, "Network / Wireless", "network")

        for key, label in [
            ("fix","GPS Fix"), ("sats","Satellites"), ("gpsdev","GPS Device"),
            ("pos","Position"), ("speed","Speed"), ("track","Heading"),
            ("gpsd","gpsd"), ("readsb","readsb")
        ]:
            icon_name = {
                "fix": "navigation",
                "sats": "satellite",
                "gpsdev": "terminal",
                "pos": "map",
                "speed": "radar",
                "track": "navigation",
                "gpsd": "radio-tower",
                "readsb": "plane",
            }.get(key)
            self.add_row(self.gps_box, key, label, icon_name)

        self.add_row(self.net_box, "ip", "IP", "network")
        self.add_row(self.net_box, "eth", "Ethernet", "ethernet")
        self.add_row(self.net_box, "bt", "Bluetooth", "bluetooth")
        self.add_row(self.net_box, "wifi", "Wi-Fi", "wifi")

        radio_frame = Gtk.Frame()
        radio_frame.set_label_widget(self.make_icon_label("HackerGadgets AIO V2 Radio Power", "radio", 15))
        main_col.pack_start(radio_frame, False, False, 0)
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

        apps = Gtk.FlowBox()
        apps.set_max_children_per_line(6)
        apps.set_selection_mode(Gtk.SelectionMode.NONE)
        apps.set_column_spacing(6)
        apps.set_row_spacing(6)
        main_col.pack_start(apps, False, False, 0)
        buttons = [
            ("GPS Nav",None,None),
            (
                "Pure Maps",
                ["pure-maps", "puremaps", "flatpak:app.puremaps.PureMaps"],
                ["pure-maps", "puremaps", "flatpak:app.puremaps.PureMaps"],
            ),
            (
                "Organic Maps",
                ["organicmaps", "omaps", "OMaps", "flatpak:app.organicmaps.desktop"],
                ["organicmaps", "omaps", "OMaps", "flatpak:app.organicmaps.desktop"],
            ),
            ("PyGPS","pygpsclient","pygpsclient"),
            ("OSM Scout","flatpak run io.github.rinigus.OSMScoutServer","flatpak:io.github.rinigus.OSMScoutServer"),
            ("SDR++","sdrpp","sdrpp"),
            ("GQRX","gqrx","gqrx"),
            ("ADS-B","xdg-open http://127.0.0.1/tar1090/","xdg-open"),
            ("Wireshark","wireshark","wireshark"),
            ("Kismet","xdg-open http://127.0.0.1:2501/","xdg-open"),
            ("AIO Control","aiov2_ctl --gui","aiov2_ctl"),
        ]
        for name, cmd, check in buttons:
            b = Gtk.Button(label=name)
            launcher_icon = {
                "GPS Nav": "navigation",
                "Pure Maps": "map",
                "Organic Maps": "map",
                "PyGPS": "satellite",
                "OSM Scout": "radar",
                "SDR++": "radio",
                "GQRX": "radio-tower",
                "ADS-B": "plane",
                "Wireshark": "network",
                "Kismet": "wifi",
                "AIO Control": "power",
            }.get(name)
            self.decorate_button(b, launcher_icon, name)
            self.builtin_buttons[name] = b
            if name == "GPS Nav":
                self.launch_buttons[name] = b
                b.connect("clicked", lambda _b, n=name: self.on_launch_clicked(n))
                apps.add(b)
                continue

            if isinstance(cmd, (list, tuple)):
                resolved = resolve_first_command(cmd)
                available = bool(resolved)
                self.launch_actions[name] = resolved
                b.set_sensitive(available)
                if available:
                    b.set_tooltip_text(f"Launch {name}")
                else:
                    b.set_tooltip_text(f"Missing dependency: {candidate_label(check)}")
                b.connect("clicked", lambda _b, n=name: self.on_launch_clicked(n))
                apps.add(b)
                continue

            available = launch_target_available(check)
            b.set_sensitive(available)
            self.launch_actions[name] = cmd
            if available:
                b.set_tooltip_text(f"Launch {name}")
            else:
                b.set_tooltip_text(f"Missing dependency: {candidate_label(check)}")
            b.connect("clicked", lambda _b, n=name: self.on_launch_clicked(n))
            apps.add(b)

        self.plugin_box = Gtk.FlowBox()
        self.plugin_box.set_max_children_per_line(6)
        self.plugin_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.plugin_box.set_column_spacing(6)
        self.plugin_box.set_row_spacing(6)
        main_col.pack_start(self.plugin_box, False, False, 0)
        self.refresh_plugin_buttons()

        self.show_all()
        self.maximize()
        if self.settings.get("profile") in PROFILE_PRESETS:
            self.apply_profile(self.settings.get("profile"), announce=False)
            self._updating_profile_combo = True
            self.profile_combo.set_active_id(self.settings.get("profile"))
            self._updating_profile_combo = False
        else:
            self.refresh_profile_visibility()
        self.refresh_gps_nav_button()
        self.refresh_async()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self.refresh_async)

    def selected_gps_option(self):
        selected = self.settings.get("gps_nav_app", "navit")
        for opt in GPS_NAV_OPTIONS:
            if opt["id"] == selected:
                return opt
        return GPS_NAV_OPTIONS[0]

    def apply_profile(self, profile_id, announce=True):
        preset = PROFILE_PRESETS.get(profile_id)
        if not preset:
            return
        self.settings["gps_nav_app"] = preset.get("gps_nav_app", self.settings.get("gps_nav_app", "navit"))
        self.settings["alerts"] = {**DEFAULT_ALERTS, **preset.get("alerts", {})}
        self.settings["profile"] = profile_id
        self.alert_settings = self.settings["alerts"]
        save_settings(self.settings)
        save_named_snapshot(
            self.settings,
            self.plugins,
            f"auto-profile-{profile_id}",
            source="auto",
            tags=["auto", "profile", profile_id],
        )
        self.refresh_profile_visibility()
        self.refresh_gps_nav_button()
        if announce:
            self.status.set_text(f"Profile applied: {preset['label']}")

    def on_profile_changed(self, combo):
        if self._updating_profile_combo:
            return
        profile_id = combo.get_active_id() or "custom"
        if profile_id == "custom":
            self.settings["profile"] = "custom"
            save_settings(self.settings)
            self.refresh_profile_visibility()
            self.status.set_text("Profile: Custom")
            return
        self.apply_profile(profile_id, announce=True)

    def refresh_profile_visibility(self):
        profile_id = self.settings.get("profile", "custom")
        visible_names = None
        if profile_id in PROFILE_PRESETS:
            visible_names = set(PROFILE_PRESETS[profile_id].get("visible_launchers", []))

        for name, button in self.builtin_buttons.items():
            show = True
            if visible_names is not None:
                show = name in visible_names
            if show:
                button.show()
            else:
                button.hide()

    def on_key_press(self, _widget, event):
        key = Gdk.keyval_name(event.keyval) or ""
        state = event.state
        alt = bool(state & Gdk.ModifierType.MOD1_MASK)
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if alt and key == "1":
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("mobile")
            self._updating_profile_combo = False
            self.apply_profile("mobile", announce=True)
            return True
        if alt and key == "2":
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("base")
            self._updating_profile_combo = False
            self.apply_profile("base", announce=True)
            return True
        if alt and key == "3":
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("emergency")
            self._updating_profile_combo = False
            self.apply_profile("emergency", announce=True)
            return True
        if alt and key == "0":
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("custom")
            self._updating_profile_combo = False
            self.settings["profile"] = "custom"
            save_settings(self.settings)
            self.refresh_profile_visibility()
            self.status.set_text("Profile: Custom")
            return True
        if ctrl and key.lower() == "g":
            self.on_launch_clicked("GPS Nav")
            return True
        return False

    def on_export_profile(self, _button):
        ok, msg = export_profile_snapshot(self.settings, self.plugins)
        if ok:
            name = self.settings.get("profile", "custom")
            save_named_snapshot(
                self.settings,
                self.plugins,
                f"manual-{name}",
                source="manual",
                tags=["manual", name],
            )
        self.status.set_text(msg)

    def on_import_profile(self, _button):
        ok, imported_settings, imported_plugins, msg = import_profile_snapshot()
        if not ok:
            self.status.set_text(msg)
            return

        self.apply_imported_state(imported_settings, imported_plugins, msg)

    def apply_imported_state(self, imported_settings, imported_plugins, status_msg):
        merged = {
            "gps_nav_app": imported_settings.get("gps_nav_app", "navit"),
            "alerts": {**DEFAULT_ALERTS, **(imported_settings.get("alerts", {}) if isinstance(imported_settings.get("alerts", {}), dict) else {})},
            "profile": imported_settings.get("profile", "custom"),
        }
        self.settings = merged
        self.alert_settings = merged["alerts"]
        save_settings(self.settings)

        cleaned_plugins = []
        for item in imported_plugins:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            command = str(item.get("command", "")).strip()
            if not label or not command:
                continue
            cleaned_plugins.append({
                "id": str(item.get("id") or label.lower().replace(" ", "-")),
                "label": label,
                "command": command,
                "check": str(item.get("check", "")).strip(),
                "tooltip": str(item.get("tooltip", "")).strip(),
            })
        self.plugins = cleaned_plugins
        save_plugins(self.plugins)

        self._updating_profile_combo = True
        self.profile_combo.set_active_id(self.settings.get("profile", "custom"))
        self._updating_profile_combo = False

        self.refresh_profile_visibility()
        self.refresh_plugin_buttons()
        self.refresh_gps_nav_button()
        self.status.set_text(status_msg)

    def open_snapshots_dialog(self, _button=None):
        dlg = Gtk.Dialog(title="Snapshot Manager", transient_for=self, flags=0)
        dlg.add_buttons("Close", Gtk.ResponseType.CLOSE)
        content = dlg.get_content_area()
        content.set_spacing(8)

        info = Gtk.Label(label=f"Snapshot folder: {PROFILE_SNAPSHOT_DIR}")
        info.set_xalign(0)
        info.set_line_wrap(True)
        info.get_style_context().add_class("subtle")
        content.pack_start(info, False, False, 0)

        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_row.pack_start(Gtk.Label(label="Name:"), False, False, 0)
        name_entry = Gtk.Entry()
        name_entry.set_text("field")
        name_row.pack_start(name_entry, True, True, 0)
        name_row.pack_start(Gtk.Label(label="Tags:"), False, False, 0)
        tag_entry = Gtk.Entry()
        tag_entry.set_placeholder_text("field-day, mobile")
        name_row.pack_start(tag_entry, True, True, 0)
        save_btn = Gtk.Button(label="Save Named")
        name_row.pack_start(save_btn, False, False, 0)
        content.pack_start(name_row, False, False, 0)

        chip_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        chip_row.pack_start(Gtk.Label(label="Quick tags:"), False, False, 0)
        for tag_name in ["field-day", "mobile", "base", "emergency", "travel", "lab"]:
            chip = Gtk.Button(label=tag_name)
            chip.set_relief(Gtk.ReliefStyle.NONE)
            chip.get_style_context().add_class("subtle")
            chip_row.pack_start(chip, False, False, 0)
        content.pack_start(chip_row, False, False, 0)

        pick_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pick_row.pack_start(Gtk.Label(label="Saved:"), False, False, 0)
        snap_combo = Gtk.ComboBoxText()
        pick_row.pack_start(snap_combo, True, True, 0)
        load_btn = Gtk.Button(label="Load")
        del_btn = Gtk.Button(label="Delete")
        pick_row.pack_start(load_btn, False, False, 0)
        pick_row.pack_start(del_btn, False, False, 0)
        content.pack_start(pick_row, False, False, 0)

        quick_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        restore_auto_btn = Gtk.Button(label="Restore Latest Auto")
        quick_row.pack_start(restore_auto_btn, False, False, 0)
        quick_hint = Gtk.Label(label="Optional tag filter uses the Tags field")
        quick_hint.set_xalign(0)
        quick_hint.get_style_context().add_class("subtle")
        quick_row.pack_start(quick_hint, True, True, 0)
        content.pack_start(quick_row, False, False, 0)

        status = Gtk.Label(label="")
        status.set_xalign(0)
        status.get_style_context().add_class("subtle")
        content.pack_start(status, False, False, 0)

        def refresh_snapshot_list(select_path=None):
            snap_combo.remove_all()
            snaps = list_profile_snapshots(limit=200)
            for s in snaps:
                snap_combo.append(s["path"], s["label"])
            if select_path:
                snap_combo.set_active_id(select_path)
            elif snaps:
                snap_combo.set_active(0)
            return snaps

        def on_save_named(_b):
            name = name_entry.get_text().strip() or "field"
            tags = normalize_snapshot_tags(tag_entry.get_text().strip())
            if "manual" not in tags:
                tags = ["manual"] + tags
            ok, path = save_named_snapshot(self.settings, self.plugins, name, source="manual", tags=tags)
            if ok:
                refresh_snapshot_list(str(path))
                msg = f"Saved snapshot: {Path(path).name}"
                status.set_text(msg)
                self.status.set_text(msg)
            else:
                status.set_text("Failed to save snapshot")

        def on_load_selected(_b):
            path = snap_combo.get_active_id()
            if not path:
                status.set_text("No snapshot selected")
                return
            ok, s, p, msg = import_profile_snapshot(path)
            if not ok:
                status.set_text(msg)
                self.status.set_text(msg)
                return
            self.apply_imported_state(s, p, msg)
            status.set_text(msg)

        def on_delete_selected(_b):
            path = snap_combo.get_active_id()
            if not path:
                status.set_text("No snapshot selected")
                return
            if delete_profile_snapshot(path):
                status.set_text(f"Deleted snapshot: {Path(path).name}")
                refresh_snapshot_list()
            else:
                status.set_text("Failed to delete snapshot")

        def on_restore_latest_auto(_b):
            tags = normalize_snapshot_tags(tag_entry.get_text().strip())
            tag = tags[0] if tags else None
            path = find_latest_auto_snapshot(tag=tag)
            if not path:
                msg = "No matching auto snapshot found"
                status.set_text(msg)
                self.status.set_text(msg)
                return
            ok, s, p, msg = import_profile_snapshot(path)
            if not ok:
                status.set_text(msg)
                self.status.set_text(msg)
                return
            self.apply_imported_state(s, p, f"Restored auto snapshot: {Path(path).name}")
            refresh_snapshot_list(path)
            status.set_text(f"Restored auto snapshot: {Path(path).name}")

        def on_quick_tag(_b, quick_tag):
            current = normalize_snapshot_tags(tag_entry.get_text().strip())
            q = normalize_snapshot_tags([quick_tag])
            if not q:
                return
            tag = q[0]
            if tag in current:
                return
            merged = current + [tag]
            tag_entry.set_text(", ".join(merged))

        save_btn.connect("clicked", on_save_named)
        load_btn.connect("clicked", on_load_selected)
        del_btn.connect("clicked", on_delete_selected)
        restore_auto_btn.connect("clicked", on_restore_latest_auto)
        for chip in chip_row.get_children()[1:]:
            chip.connect("clicked", on_quick_tag, chip.get_label())
        refresh_snapshot_list()

        dlg.show_all()
        dlg.run()
        dlg.destroy()

    def gps_option_by_id(self, option_id):
        for opt in GPS_NAV_OPTIONS:
            if opt["id"] == option_id:
                return opt
        return None

    def gps_option_status(self, option):
        cmd = resolve_gps_option_command(option)
        return {
            "available": bool(cmd),
            "command": cmd,
            "label": option["label"],
            "check": candidate_label(option["commands"][0]),
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

    def refresh_plugin_buttons(self):
        for child in self.plugin_box.get_children():
            self.plugin_box.remove(child)

        if not self.plugins:
            self.header_plugin_info.set_text("Plugins: none configured")
            self.plugin_box.hide()
            return

        self.header_plugin_info.set_text(f"Plugins: {len(self.plugins)} custom launcher(s)")
        self.plugin_box.show()

        for plugin in self.plugins:
            key = f"plugin:{plugin['id']}"
            b = Gtk.Button(label=plugin["label"])
            check = plugin.get("check", "")
            available = launch_target_available(check)
            b.set_sensitive(available)
            self.launch_actions[key] = plugin["command"] if available else None
            if not available:
                b.set_tooltip_text(f"Missing dependency: {candidate_label(check)}")
            elif plugin.get("tooltip"):
                b.set_tooltip_text(plugin["tooltip"])
            else:
                b.set_tooltip_text(f"Launch {plugin['label']}")
            b.connect("clicked", lambda _b, n=key: self.on_launch_clicked(n))
            self.plugin_box.add(b)

        self.plugin_box.show_all()

    def restart_service(self, service):
        self.status.set_text(f"Restarting {service}…")

        def worker():
            rc, out = run_rc(f"sudo -n systemctl restart {service}", 12)
            if rc != 0:
                rc, out = run_rc(f"systemctl restart {service}", 12)
            if rc == 0:
                msg = f"{service} restart requested"
            elif "password" in out.lower() or "authentication" in out.lower():
                msg = f"{service} restart needs sudo rights"
            else:
                tail = out.splitlines()[-1][:90] if out else "unknown error"
                msg = f"{service} restart failed: {tail}"
            GLib.idle_add(self.status.set_text, msg)
            GLib.timeout_add_seconds(1, self.refresh_async)

        threading.Thread(target=worker, daemon=True).start()

    def on_restart_selected(self, _button):
        service = self.restart_combo.get_active_text()
        if not service:
            self.status.set_text("Select a service to restart")
            return
        self.restart_service(service)

    def on_launch_clicked(self, name):
        cmd = self.launch_actions.get(name)
        if not cmd:
            self.status.set_text(f"{name}: no launch command configured")
            return
        launch_with_status(self, name, cmd)

    def on_start_mission(self, _button):
        if self.mission_active:
            self.status.set_text("Mission recorder is already running")
            return
        try:
            MISSION_RECORD_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            profile_hint = mission_profile_hint(self.settings.get("profile", "custom"))
            file_path = MISSION_RECORD_DIR / f"mission-{profile_hint}-{ts}.jsonl"
            fp = file_path.open("a", encoding="utf-8")
            self.mission_fp = fp
            self.mission_file_path = file_path
            self.mission_started_at = datetime.now()
            self.mission_active = True
            self.mission_stats = {
                "samples": 0,
                "fix_good": 0,
                "wifi_up": 0,
                "cpu_max_c": None,
                "ram_max_pct": None,
                "disk_min_free_pct": None,
                "battery_min_pct": None,
            }
            self.mission_start_btn.set_sensitive(False)
            self.mission_stop_btn.set_sensitive(True)
            self.mission_status.set_text(f"Mission: recording {file_path.name}")
            self.status.set_text(f"Mission recorder started: {file_path.name}")
        except Exception as e:
            self.mission_active = False
            self.mission_fp = None
            self.mission_file_path = None
            self.mission_started_at = None
            self.mission_status.set_text("Mission: start failed")
            self.status.set_text(f"Mission recorder failed to start: {str(e)[:100]}")

    def on_stop_mission(self, _button):
        if not self.mission_active:
            self.status.set_text("Mission recorder is not running")
            return
        self.stop_mission_recording(reason="stopped")

    def stop_mission_recording(self, reason="stopped"):
        file_path = self.mission_file_path
        started_at = self.mission_started_at
        stats = dict(self.mission_stats or {})

        try:
            if self.mission_fp is not None:
                self.mission_fp.flush()
                self.mission_fp.close()
        except Exception:
            pass

        self.mission_active = False
        self.mission_fp = None
        self.mission_file_path = None
        self.mission_started_at = None
        self.mission_stats = {}
        self.mission_start_btn.set_sensitive(True)
        self.mission_stop_btn.set_sensitive(False)
        self.mission_status.set_text("Mission: idle")

        if not file_path or not started_at:
            self.status.set_text("Mission recorder stopped")
            return

        ended_at = datetime.now()
        samples = int(stats.get("samples", 0) or 0)
        duration_s = max(1, int((ended_at - started_at).total_seconds()))
        fix_good = int(stats.get("fix_good", 0) or 0)
        wifi_up = int(stats.get("wifi_up", 0) or 0)

        summary = {
            "reason": reason,
            "started_at": started_at.isoformat(timespec="seconds"),
            "ended_at": ended_at.isoformat(timespec="seconds"),
            "duration_seconds": duration_s,
            "samples": samples,
            "sample_interval_seconds": REFRESH_SECONDS,
            "gps_fix_good_rate_pct": round((fix_good / samples) * 100.0, 1) if samples else 0.0,
            "wifi_up_rate_pct": round((wifi_up / samples) * 100.0, 1) if samples else 0.0,
            "cpu_max_c": stats.get("cpu_max_c"),
            "ram_max_pct": stats.get("ram_max_pct"),
            "disk_min_free_pct": stats.get("disk_min_free_pct"),
            "battery_min_pct": stats.get("battery_min_pct"),
            "source_jsonl": str(file_path),
        }

        summary_path = file_path.with_name(file_path.stem + "-summary.json")
        try:
            summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
            self.status.set_text(
                f"Mission saved: {file_path.name} ({samples} samples, {duration_s}s)"
            )
        except Exception as e:
            self.status.set_text(
                f"Mission saved but summary write failed: {str(e)[:90]}"
            )

    def record_mission_sample(self, d):
        if not self.mission_active or self.mission_fp is None:
            return

        try:
            now = datetime.now().isoformat(timespec="seconds")
            metrics = d.get("metrics", {}) if isinstance(d.get("metrics", {}), dict) else {}
            gps = d.get("gps", {}) if isinstance(d.get("gps", {}), dict) else {}
            wifi = d.get("wifi", []) if isinstance(d.get("wifi", []), list) else []
            sample = {
                "ts": now,
                "profile": self.settings.get("profile", "custom"),
                "cpu": d.get("cpu"),
                "ram": d.get("ram"),
                "disk": d.get("disk"),
                "battery": d.get("battery"),
                "metrics": metrics,
                "gps": {
                    "fix": gps.get("fix"),
                    "sats": gps.get("sats"),
                    "pos": gps.get("pos"),
                    "speed": gps.get("speed"),
                    "track": gps.get("track"),
                    "device": gps.get("device"),
                },
                "services": d.get("services", {}),
                "wifi": wifi,
            }
            self.mission_fp.write(json.dumps(sample) + "\n")

            stats = self.mission_stats
            stats["samples"] = int(stats.get("samples", 0) or 0) + 1

            fix_text = str(gps.get("fix", ""))
            if "2D" in fix_text or "3D" in fix_text:
                stats["fix_good"] = int(stats.get("fix_good", 0) or 0) + 1

            if len(wifi) > 0:
                stats["wifi_up"] = int(stats.get("wifi_up", 0) or 0) + 1

            cpu_c = metrics.get("cpu_temp_c")
            if isinstance(cpu_c, (int, float)):
                current = stats.get("cpu_max_c")
                stats["cpu_max_c"] = cpu_c if current is None else max(float(current), float(cpu_c))

            ram_pct = metrics.get("ram_used_pct")
            if isinstance(ram_pct, (int, float)):
                current = stats.get("ram_max_pct")
                stats["ram_max_pct"] = ram_pct if current is None else max(float(current), float(ram_pct))

            disk_free_pct = metrics.get("disk_free_pct")
            if isinstance(disk_free_pct, (int, float)):
                current = stats.get("disk_min_free_pct")
                stats["disk_min_free_pct"] = disk_free_pct if current is None else min(float(current), float(disk_free_pct))

            batt_pct = metrics.get("battery_pct")
            if isinstance(batt_pct, (int, float)):
                current = stats.get("battery_min_pct")
                stats["battery_min_pct"] = batt_pct if current is None else min(float(current), float(batt_pct))

            if stats["samples"] % 10 == 0:
                self.mission_fp.flush()
        except Exception as e:
            self.stop_mission_recording(reason="error")
            self.status.set_text(f"Mission recorder stopped on write error: {str(e)[:100]}")

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

        alerts = self.settings.get("alerts", dict(DEFAULT_ALERTS))
        alerts_frame = Gtk.Frame(label="Alert Engine")
        content.pack_start(alerts_frame, False, False, 0)
        alerts_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        alerts_box.set_border_width(8)
        alerts_frame.add(alerts_box)

        alerts_enabled = Gtk.CheckButton(label="Enable alerts")
        alerts_enabled.set_active(bool(alerts.get("enabled", True)))
        alerts_box.pack_start(alerts_enabled, False, False, 0)

        cpu_spin = Gtk.SpinButton.new_with_range(40, 120, 1)
        cpu_spin.set_value(float(alerts.get("cpu_temp_c", 78)))
        ram_spin = Gtk.SpinButton.new_with_range(50, 100, 1)
        ram_spin.set_value(float(alerts.get("ram_used_pct", 90)))
        disk_spin = Gtk.SpinButton.new_with_range(1, 50, 1)
        disk_spin.set_value(float(alerts.get("disk_free_pct", 10)))
        batt_spin = Gtk.SpinButton.new_with_range(1, 100, 1)
        batt_spin.set_value(float(alerts.get("battery_pct", 25)))

        for label_text, widget in [
            ("CPU max (C):", cpu_spin),
            ("RAM max used (%):", ram_spin),
            ("Disk min free (%):", disk_spin),
            ("Battery min (%):", batt_spin),
        ]:
            srow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            srow.pack_start(Gtk.Label(label=label_text), False, False, 0)
            srow.pack_start(widget, False, False, 0)
            alerts_box.pack_start(srow, False, False, 0)

        require_fix = Gtk.CheckButton(label="Alert when GPS has no 2D/3D fix")
        require_fix.set_active(bool(alerts.get("require_gps_fix", False)))
        alerts_box.pack_start(require_fix, False, False, 0)

        require_wifi = Gtk.CheckButton(label="Alert when Wi-Fi interfaces are missing")
        require_wifi.set_active(bool(alerts.get("require_wifi", False)))
        alerts_box.pack_start(require_wifi, False, False, 0)

        plugin_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        plugin_label = Gtk.Label(label="Custom launchers are loaded from plugins.json")
        plugin_label.set_xalign(0)
        plugin_label.get_style_context().add_class("subtle")
        plugin_btn = Gtk.Button(label="Edit Custom Plugins")
        plugin_btn.connect("clicked", lambda _b: self.open_plugins_dialog(dialog))
        plugin_row.pack_start(plugin_label, True, True, 0)
        plugin_row.pack_end(plugin_btn, False, False, 0)
        content.pack_start(plugin_row, False, False, 0)

        dialog.show_all()
        resp = dialog.run()
        if resp == Gtk.ResponseType.OK:
            selected = combo.get_active_id() or "navit"
            self.settings["gps_nav_app"] = selected
            self.settings["alerts"] = {
                "enabled": alerts_enabled.get_active(),
                "cpu_temp_c": int(cpu_spin.get_value()),
                "ram_used_pct": int(ram_spin.get_value()),
                "disk_free_pct": int(disk_spin.get_value()),
                "battery_pct": int(batt_spin.get_value()),
                "require_gps_fix": require_fix.get_active(),
                "require_wifi": require_wifi.get_active(),
            }
            self.settings["profile"] = "custom"
            save_settings(self.settings)
            save_named_snapshot(
                self.settings,
                self.plugins,
                "auto-settings",
                source="auto",
                tags=["auto", "settings"],
            )
            self.alert_settings = self.settings["alerts"]
            self._updating_profile_combo = True
            self.profile_combo.set_active_id("custom")
            self._updating_profile_combo = False
            self.refresh_gps_nav_button()
            opt = self.gps_option_by_id(selected)
            if opt:
                self.status.set_text(f"Saved: GPS Nav set to {opt['label']}")
            self.refresh_plugin_buttons()
        dialog.destroy()

    def open_plugins_dialog(self, parent_dialog=None):
        dlg = Gtk.Dialog(title="Custom Plugin Launchers", transient_for=self, flags=0)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        content = dlg.get_content_area()
        content.set_spacing(8)

        hint = Gtk.Label(
            label=(
                "JSON list format: [{\"id\":\"apr\",\"label\":\"APRS\","
                "\"command\":\"xterm -e aprx\",\"check\":\"xterm\"}]"
            )
        )
        hint.set_xalign(0)
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("subtle")
        content.pack_start(hint, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(220)
        content.pack_start(scroll, True, True, 0)

        text_view = Gtk.TextView()
        text_view.set_monospace(True)
        scroll.add(text_view)

        buf = text_view.get_buffer()
        buf.set_text(json.dumps(self.plugins, indent=2))

        dlg.show_all()
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            start, end = buf.get_bounds()
            raw = buf.get_text(start, end, True)
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValueError("Top-level JSON must be a list")
                cleaned = []
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    label = str(item.get("label", "")).strip()
                    command = str(item.get("command", "")).strip()
                    if not label or not command:
                        continue
                    cleaned.append({
                        "id": str(item.get("id") or label.lower().replace(" ", "-")),
                        "label": label,
                        "command": command,
                        "check": str(item.get("check", "")).strip(),
                        "tooltip": str(item.get("tooltip", "")).strip(),
                    })
                if save_plugins(cleaned):
                    self.plugins = cleaned
                    self.settings["profile"] = "custom"
                    save_settings(self.settings)
                    save_named_snapshot(
                        self.settings,
                        self.plugins,
                        "auto-plugins",
                        source="auto",
                        tags=["auto", "plugins"],
                    )
                    self._updating_profile_combo = True
                    self.profile_combo.set_active_id("custom")
                    self._updating_profile_combo = False
                    self.refresh_profile_visibility()
                    self.refresh_plugin_buttons()
                    self.status.set_text(f"Saved {len(cleaned)} custom plugin launcher(s)")
                else:
                    self.status.set_text("Failed to write plugins.json")
            except Exception as e:
                self.status.set_text(f"Plugin JSON error: {str(e)[:100]}")
        dlg.destroy()
        if parent_dialog is not None:
            parent_dialog.present()

    def get_icon_image(self, icon_name, size=16):
        if not icon_name:
            return None
        key = f"{icon_name}:{size}"
        cached = self.icon_cache.get(key)
        if cached is not None:
            return Gtk.Image.new_from_pixbuf(cached)

        icon_dirs = [
            APP_ICON_DIR,
            Path(__file__).resolve().parent.parent / "assets" / "icons",
            Path.home() / ".config" / "k7bat-uconsole-status" / "icons",
        ]
        for icon_dir in icon_dirs:
            icon_path = icon_dir / f"{icon_name}.svg"
            if not icon_path.exists():
                continue
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(icon_path),
                    width=size,
                    height=size,
                    preserve_aspect_ratio=True,
                )
                self.icon_cache[key] = pix
                return Gtk.Image.new_from_pixbuf(pix)
            except Exception:
                continue
        return None

    def make_icon_label(self, text, icon_name=None, size=14):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon = self.get_icon_image(icon_name, size=size)
        if icon is not None:
            row.pack_start(icon, False, False, 0)
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        row.pack_start(label, False, False, 0)
        return row

    def make_icon_info_row(self, parent, text, icon_name=None, size=14, wrap=False):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon = self.get_icon_image(icon_name, size=size)
        if icon is not None:
            row.pack_start(icon, False, False, 0)
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_line_wrap(wrap)
        row.pack_start(label, True, True, 0)
        parent.pack_start(row, False, False, 0)
        return label, row

    def decorate_button(self, button, icon_name=None, text=None):
        if not icon_name:
            return
        label_text = text if text is not None else button.get_label()
        existing = button.get_child()
        if existing is not None:
            button.remove(existing)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        icon = self.get_icon_image(icon_name, size=14)
        if icon is not None:
            row.pack_start(icon, False, False, 0)
        label = Gtk.Label(label=label_text)
        row.pack_start(label, False, False, 0)
        button.add(row)
        row.show_all()

    def make_frame(self, parent, title, icon_name=None):
        f = Gtk.Frame()
        if icon_name:
            f.set_label_widget(self.make_icon_label(title, icon_name, 15))
        else:
            f.set_label(title)
        parent.pack_start(f, True, True, 0)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_border_width(8)
        f.add(box)
        return box

    def add_row(self, parent, key, title, icon_name=None):
        row = Gtk.Box(spacing=6)
        name = self.make_icon_label(title, icon_name, 14)
        name.set_size_request(115, -1)
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

    def evaluate_alerts(self, d):
        alerts = []
        cfg = self.alert_settings or dict(DEFAULT_ALERTS)
        if not cfg.get("enabled", True):
            return alerts

        metrics = d.get("metrics", {})
        cpu_c = metrics.get("cpu_temp_c")
        if cpu_c is not None and cpu_c >= cfg.get("cpu_temp_c", 78):
            alerts.append(("warn", f"CPU temp high: {cpu_c:.0f}C"))

        ram_used = metrics.get("ram_used_pct")
        if ram_used is not None and ram_used >= cfg.get("ram_used_pct", 90):
            alerts.append(("warn", f"RAM usage high: {ram_used:.0f}%"))

        disk_free = metrics.get("disk_free_pct")
        if disk_free is not None and disk_free <= cfg.get("disk_free_pct", 10):
            alerts.append(("bad", f"Disk free low: {disk_free:.0f}%"))

        battery_pct = metrics.get("battery_pct")
        battery_state = metrics.get("battery_state") or ""
        if battery_pct is not None and battery_state.lower() != "charging":
            if battery_pct <= cfg.get("battery_pct", 25):
                alerts.append(("bad", f"Battery low: {battery_pct}%"))

        fix = d.get("gps", {}).get("fix", "")
        if cfg.get("require_gps_fix", False) and ("2D" not in fix and "3D" not in fix):
            alerts.append(("warn", f"GPS fix missing: {fix}"))

        wifi_count = len(d.get("wifi", []))
        if cfg.get("require_wifi", False) and wifi_count == 0:
            alerts.append(("warn", "No Wi-Fi interfaces detected"))

        if d.get("gpsd") != "RUNNING":
            alerts.append(("warn", "gpsd is not running"))
        return alerts

    def apply_alerts(self, alerts):
        if not self.alert_settings.get("enabled", True):
            self.alert_summary.set_text("Alerts: disabled (enable in Settings)")
            return

        if not alerts:
            self.alert_summary.set_text("Alerts: all monitored systems nominal")
            return

        critical = any(level == "bad" for level, _ in alerts)
        prefix = "ALERT" if critical else "WARN"
        self.alert_summary.set_text(
            f"{prefix}: " + " | ".join(text for _level, text in alerts[:4])
        )

    def collect(self):
        g = gps_data()
        w = wifi_interfaces()
        mem_used, mem_total = memory_usage_bytes()
        disk_free, disk_total = disk_usage_bytes()
        battery_text, battery_pct, battery_state = battery_info()
        cpu_c = cpu_temp_value()
        service_map = {
            "gpsd": service_state("gpsd"),
            "gpsd.socket": service_state("gpsd.socket"),
            "bluetooth": service_state("bluetooth"),
            "readsb": service_state("readsb"),
            "NetworkManager": service_state("NetworkManager"),
        }
        ram_used_pct = None
        if mem_used is not None and mem_total:
            ram_used_pct = (float(mem_used) / float(mem_total)) * 100.0
        disk_free_pct = None
        if disk_free is not None and disk_total:
            disk_free_pct = (float(disk_free) / float(disk_total)) * 100.0
        return {
            "cpu": cpu_temp(), "ram": memory(), "disk": disk(), "battery": battery_text,
            "gps": g, "ip": ip_info(), "eth": ethernet(), "bt": bluetooth(),
            "gpsd": service_state("gpsd"), "readsb": service_state("readsb"),
            "wifi": w, "aio": parse_aio_states(),
            "services": service_map,
            "metrics": {
                "cpu_temp_c": cpu_c,
                "ram_used_pct": ram_used_pct,
                "disk_free_pct": disk_free_pct,
                "battery_pct": battery_pct,
                "battery_state": battery_state,
            },
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
        if d["wifi"]:
            self.labels["wifi"].set_text(" | ".join(f"{iface}: {detail}" for iface, detail in d["wifi"][:2]))
        else:
            self.labels["wifi"].set_text("—")
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

        for service, label in self.service_labels.items():
            state = d.get("services", {}).get(service, "OFF")
            label.set_text(f"{service}: {state}")
            ctx = label.get_style_context()
            for cls in ("status-on", "status-off", "status-unknown", "subtle"):
                ctx.remove_class(cls)
            if state == "RUNNING":
                ctx.add_class("status-on")
            else:
                ctx.add_class("status-off")

        alerts = self.evaluate_alerts(d)
        self.apply_alerts(alerts)

        self.record_mission_sample(d)

        self.last_update.set_text("Updated: " + datetime.now().strftime("%H:%M:%S"))
        return False

Gtk.init([])
App()
Gtk.main()
