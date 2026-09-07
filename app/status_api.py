#!/usr/bin/env python3
"""
K7BAT uConsole Status API v1.1.0
HTTP API for Arduino and other devices to query and post status information.

Features:
- RESTful HTTP API on port 8080
- GET endpoints for status data (system, Wi-Fi, GPS, radio)
- POST endpoints for commands/data submission
- JSON responses
- Thread-safe data access
- Remote app launching support
- Radio control (on/off, frequency, mode)
- Button/touchscreen event handling
- Plugin system integration

Usage:
    python3 status_api.py [--port 8080] [--host 0.0.0.0]
"""

import sys
import os
import json
import re
import shutil
import signal
import threading
import subprocess
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Add app directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sidekick_apikey import load_or_create_api_key
except ImportError:
    # Try relative import for local development (when run from scripts/utils)
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir.endswith('scripts/utils'):
            sys.path.insert(0, script_dir)
            from sidekick_apikey import load_or_create_api_key
        else:
            # Try to import from scripts/utils relative to app directory
            app_dir = os.path.dirname(script_dir)
            utils_path = os.path.join(app_dir, 'scripts', 'utils')
            if os.path.exists(os.path.join(utils_path, 'sidekick_apikey.py')):
                sys.path.insert(0, utils_path)
                from sidekick_apikey import load_or_create_api_key
            # Also check if sidekick_apikey.py is in the same directory as status_api.py
            elif os.path.exists(os.path.join(script_dir, 'sidekick_apikey.py')):
                sys.path.insert(0, script_dir)
                from sidekick_apikey import load_or_create_api_key
            else:
                load_or_create_api_key = None
    except ImportError:
        load_or_create_api_key = None

# Import plugins configuration
try:
    from plugins.plugin_manager import PluginManager
except ImportError:
    PluginManager = None

# Persistent API key (see ideas/API_Auth.md) used to authenticate
# /api/sidekick/control requests from provisioned Sidekick devices.
API_KEY = load_or_create_api_key(os.path.dirname(os.path.abspath(__file__)))

# Status data storage
_status_data = {
    "system": {
        "cpu_load": 0.0,
        "memory_used": "0MB",
        "memory_total": "0MB",
        "disk_usage": "0%",
        "uptime": "0s",
        "hostname": "",
        "os_version": ""
    },
    "wifi": {
        "status": "disconnected",
        "interface": "",
        "ssid": "",
        "ip_address": "",
        "signal_strength": 0,
        "connected_devices": []
    },
    "gps": {
        "status": "no_fix",
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "satellites": 0,
        "speed": None
    },
    "devices": [],
    "radio": {
        "status": "idle",
        "frequency": None,
        "mode": ""
    },
    "hardware": {},
    "apps": {
        "running": [],
        "available": []
    },
    "timestamp": datetime.now().isoformat()
}

_status_lock = threading.Lock()

# How often the background thread re-collects status. Must stay comfortably
# under the Sidekick's API_STALE_TIMEOUT_MS (15s).
STATUS_REFRESH_INTERVAL_S = 5.0

# Event queue for Arduino buttons/touchscreen events
_events_queue = []
_events_lock = threading.Lock()

# Active processes tracking
_active_processes = {}
_process_lock = threading.Lock()

# API call tracking - last caller and timestamp
_api_call_tracking = {
    "last_caller": "",
    "last_call_time": "",
    "total_calls": 0
}
_api_track_lock = threading.Lock()


def get_system_info():
    """Collect system information."""
    try:
        import subprocess
        # CPU load
        with open('/proc/loadavg', 'r') as f:
            cpu_load = f.read().split()[0]
        
        # Memory info
        mem_info = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(':')
                    mem_info[key] = int(parts[1]) * 1024  # Convert to bytes
        
        mem_total = mem_info.get('MemTotal', 0)
        mem_available = mem_info.get('MemAvailable', 0)
        mem_used = mem_total - mem_available
        
        # Disk usage
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        disk_lines = result.stdout.strip().split('\n')
        disk_usage = disk_lines[1].split()[4] if len(disk_lines) > 1 else "0%"
        
        # Uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
        
        # OS version
        os_version = ""
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        os_version = line.split('=', 1)[1].strip('"\'')
                        break
        except FileNotFoundError:
            os_version = "Unknown"
        
        return {
            "cpu_load": float(cpu_load),
            "memory_used": f"{mem_used // (1024*1024)}MB",
            "memory_total": f"{mem_total // (1024*1024)}MB",
            "disk_usage": disk_usage,
            "uptime": f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m",
            "hostname": os.uname().nodename,
            "os_version": os_version
        }
    except Exception as e:
        return {"error": str(e)}


def update_api_tracker(client_ip, path):
    """Track the last API caller and timestamp."""
    with _api_track_lock:
        _api_call_tracking["last_caller"] = f"{client_ip}:{path}"
        _api_call_tracking["last_call_time"] = datetime.now().strftime("%H:%M:%S")
        _api_call_tracking["total_calls"] += 1


def get_api_tracker():
    """Get current API tracking data."""
    with _api_track_lock:
        return dict(_api_call_tracking)


def get_wifi_status():
    """Get Wi-Fi status."""
    try:
        import subprocess
        
        # Check if wlan0 exists and is active
        result = subprocess.run(['ip', 'link', 'show', 'wlan0'], capture_output=True, text=True)
        is_active = 'UP' in result.stdout
        
        if not is_active:
            return {
                "status": "disabled",
                "interface": "wlan0",
                "ssid": "",
                "ip_address": "",
                "signal_strength": 0,
                "connected_devices": []
            }
        
        # Get IP address
        result = subprocess.run(['ip', 'addr', 'show', 'wlan0'], capture_output=True, text=True)
        ip_address = ""
        for line in result.stdout.split('\n'):
            if 'inet ' in line:
                ip_address = line.split()[1].split('/')[0]
                break
        
        # Get SSID (requires wireless-tools or iw)
        ssid = ""
        try:
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
            ssid = result.stdout.strip()
        except FileNotFoundError:
            ssid = "Unknown"
        
        # Signal strength
        signal_strength = 0
        try:
            result = subprocess.run(['cat', '/proc/net/wireless'], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 3:
                parts = lines[2].split()
                if len(parts) >= 4:
                    # Convert to float first, then int (handles values like "70." properly)
                    signal_strength = int(float(parts[2]))
        except FileNotFoundError:
            pass
        
        return {
            "status": "connected" if ssid else "connected_no_ssid",
            "interface": "wlan0",
            "ssid": ssid,
            "ip_address": ip_address,
            "signal_strength": signal_strength,
            "connected_devices": []
        }
    except Exception as e:
        return {"error": str(e)}


def run_stdout(cmd, timeout=3):
    """Run a shell command and return its stripped stdout, or '' on failure."""
    # start_new_session puts the shell and its children in their own process
    # group so a timeout can kill the whole group. Without it, killing /bin/sh
    # leaves grandchildren like `gpspipe` running forever.
    proc = None
    try:
        proc = subprocess.Popen(
            cmd, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        out, _ = proc.communicate(timeout=timeout)
        return (out or "").strip()
    except Exception:
        if proc is not None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.communicate(timeout=1)
            except Exception:
                pass
        return ""


def get_gps_status():
    """Get GPS status by querying gpsd directly via gpspipe."""
    result = {
        "fix": "gpsd off", "sats": "—", "pos": "—",
        "speed": "—", "track": "—", "device": "—",
        "hdop": "—", "vdop": "—", "pdop": "—",
        "sats_used": "—", "confidence": "—",
        "confidence_pct": None,
        "quality_grade": "unknown",
        "quality_note": "No GPS sample",
        "sample_time": "—",
        "hdop_val": None, "vdop_val": None, "pdop_val": None,
    }

    gpsd_up = service_active("gpsd") or service_active("gpsd.socket")
    if not gpsd_up:
        return result

    raw = run_stdout("gpspipe -w -n 12", timeout=3)
    tpv, dev = {}, None
    sats = None
    sats_used = None
    hdop = None
    vdop = None
    pdop = None
    
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
            if sats is None and isinstance(j.get("satellites"), list):
                sats = len(j.get("satellites"))
            if isinstance(j.get("satellites"), list):
                used = [s for s in j.get("satellites", []) if isinstance(s, dict) and s.get("used")]
                sats_used = len(used)
            hdop = j.get("hdop") if isinstance(j.get("hdop"), (int, float)) else hdop
            vdop = j.get("vdop") if isinstance(j.get("vdop"), (int, float)) else vdop
            pdop = j.get("pdop") if isinstance(j.get("pdop"), (int, float)) else pdop

    mode = tpv.get("mode", 0)
    result["fix"] = {0:"NO DATA",1:"NO FIX",2:"2D FIX",3:"3D FIX"}.get(mode, str(mode))
    result["sats"] = str(sats) if sats is not None else "—"
    result["sats_used"] = str(sats_used) if sats_used is not None else "—"
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
    
    sample_time = str(tpv.get("time", "")).strip()
    if sample_time:
        result["sample_time"] = sample_time

    result["hdop"] = str(hdop) if isinstance(hdop, (int, float)) else "—"
    result["vdop"] = str(vdop) if isinstance(vdop, (int, float)) else "—"
    result["pdop"] = str(pdop) if isinstance(pdop, (int, float)) else "—"
    result["hdop_val"] = float(hdop) if isinstance(hdop, (int, float)) else None
    result["vdop_val"] = float(vdop) if isinstance(vdop, (int, float)) else None
    result["pdop_val"] = float(pdop) if isinstance(pdop, (int, float)) else None

    # Calculate confidence and quality grade
    try:
        confidence = estimate_gps_confidence(mode, sats_used, pdop)
        result["confidence"] = f"{confidence}%"
        result["confidence_pct"] = confidence
        grade, note = evaluate_gps_quality(mode, sats_used, pdop, confidence)
        result["quality_grade"] = grade
        result["quality_note"] = note
    except Exception:
        pass
    
    return result


def get_radio_status():
    """Get radio/SDR status."""
    # Placeholder - implement based on your SDR setup
    return {
        "enabled": False,
        "status": "idle",
        "frequency": None,
        "mode": ""
    }


def launch_app(app_id, app_config):
    """Launch an application by ID."""
    try:
        cmd = app_config.get('command', '')
        if not cmd:
            # Try Python module
            module = app_config.get('module', '')
            if module:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                module_base = module.split('.')[0]
                # Build command with proper escaping for bash -c
                import_cmd = 'import sys'
                path_cmd = f'sys.path.insert(0, \'{script_dir}\')'
                from_cmd = f'from {module_base} import *'
                exec_cmd = f'{module.replace(".", ".")}()'
                cmd = f'python3 -c "{import_cmd}; {path_cmd}; {from_cmd}; {exec_cmd}"'
        
        if cmd:
            process = subprocess.Popen(
                ['bash', '-c', cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            with _process_lock:
                _active_processes[app_id] = {
                    'pid': process.pid,
                    'started_at': datetime.now().isoformat(),
                    'config': app_config
                }
            
            return True, f"Launched {app_id} (PID: {process.pid})"
        else:
            return False, "No command or module defined for app"
    except Exception as e:
        return False, str(e)


def stop_app(app_id):
    """Stop a running application."""
    try:
        with _process_lock:
            if app_id in _active_processes:
                import psutil
                pid = _active_processes[app_id]['pid']
                process = psutil.Process(pid)
                process.terminate()
                process.wait(timeout=5)
                del _active_processes[app_id]
                return True, f"Stopped {app_id}"
            else:
                return False, f"{app_id} is not running"
    except Exception as e:
        return False, str(e)


def toggle_radio(enabled):
    """Toggle radio on/off."""
    try:
        if enabled:
            # Start SDR software
            subprocess.run(['systemctl', 'start', 'sdrpp'], check=False)
            status = "active"
        else:
            # Stop SDR software
            subprocess.run(['systemctl', 'stop', 'sdrpp'], check=False)
            status = "idle"
        
        return True, {"status": status, "enabled": enabled}
    except Exception as e:
        return False, str(e)


def set_radio_frequency(freq_hz):
    """Set radio frequency in Hz."""
    try:
        # Convert to MHz for display
        freq_mhz = freq_hz / 1_000_000
        
        # Command SDR software (adjust based on your setup)
        # This is a placeholder - implement based on your SDR interface
        return True, {"frequency": freq_hz, "freqency_mhz": round(freq_mhz, 2)}
    except Exception as e:
        return False, str(e)


def run_rc(cmd, timeout=10):
    """Run a shell command, returning (returncode, combined stdout+stderr)."""
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()
    except Exception as e:
        return -1, str(e)


# Sidekick touch-control targets that map to an AIO V2 power rail via aiov2_ctl.
# Device names must match the case aiov2_ctl expects (see the GUI app's radio_command()).
_AIO_RAIL_TARGETS = {"SDR", "LORA", "USB", "GPS"}

# Sidekick touch-control targets that map to a systemd service start/stop/restart.
# ADSB/READ/TAR are separate dashboard tiles but all reflect the same readsb service.
_SERVICE_TARGETS = {
    "GPSD": "gpsd",
    "BT": "bluetooth",
    "ADSB": "readsb",
    "READ": "readsb",
    "TAR": "readsb",
    "VNC": "vncserver-x11-serviced",
}


def control_aio_power(target, value):
    """Toggle an AIO V2 power rail (SDR/LORA/USB/GPS) via aiov2_ctl."""
    if value not in ("on", "off"):
        return False, f"invalid power value: {value}"
    if not shutil.which("aiov2_ctl"):
        return False, "aiov2_ctl not available on this system"
    rc, out = run_rc(f"aiov2_ctl {target} {value}", 10)
    if rc == 0:
        return True, f"{target} power {value} requested"
    return False, (out.splitlines()[-1][:150] if out else f"{target} {value} failed")


def control_service(service_name, action):
    """Start/stop/restart a systemd service using the same sudo -n pattern as the GUI app."""
    if action not in ("start", "stop", "restart"):
        return False, f"invalid service action: {action}"
    rc, out = run_rc(f"sudo -n systemctl {action} {service_name}", 12)
    if rc == 0:
        return True, f"{service_name} {action} requested"
    low = out.lower()
    if "password" in low or "authentication" in low or "sudoers" in low:
        return False, f"{service_name} {action} blocked: passwordless sudo not configured for systemctl"
    return False, (out.splitlines()[-1][:150] if out else f"{service_name} {action} failed")


def control_sdrpp(action):
    """Start/stop the SDR++ systemd service (SDR+ tile)."""
    if action not in ("start", "stop"):
        return False, f"invalid action: {action}"
    success, result = toggle_radio(action == "start")
    if success:
        return True, "SDR+ start requested" if action == "start" else "SDR+ stop requested"
    return False, str(result)


def handle_sidekick_control(data):
    """Dispatch a Sidekick touch-control request. Returns (http_status, response_dict)."""
    target = str(data.get("target", "")).strip().upper()
    command = str(data.get("command", "")).strip().lower()
    value = str(data.get("value", "")).strip().lower()

    if not target or not command or not value:
        return 400, {"ok": False, "error": "target, command, and value are required"}

    if command == "power" and target in _AIO_RAIL_TARGETS:
        success, message = control_aio_power(target, value)
    elif target == "SDR+" and command == "service":
        success, message = control_sdrpp(value)
    elif command == "service" and target in _SERVICE_TARGETS:
        success, message = control_service(_SERVICE_TARGETS[target], value)
    else:
        return 400, {"ok": False, "error": f"unsupported target/command: {target}/{command}"}

    response = {"ok": success, "target": target, "command": command, "requested": value}
    response["message" if success else "error"] = message
    return (200 if success else 500), response


def add_event(event_type, data=None):
    """Add an event to the queue (for Arduino button/touchscreen events)."""
    with _events_lock:
        _events_queue.append({
            "type": event_type,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        })


def get_events():
    """Get and clear all pending events."""
    with _events_lock:
        events = list(_events_queue)
        _events_queue.clear()
        return events


def load_plugins_config():
    """Load available plugins/apps from configuration."""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'plugins.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading plugins: {e}")
    
    return []


def service_active(name):
    """Check if a systemd service is active."""
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", name], stderr=subprocess.DEVNULL, text=True, timeout=3
        ).strip()
        return out == "active"
    except Exception:
        return False


def read_cpu_temp_c():
    """Read CPU temperature in Celsius, or None if unavailable."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return None


def read_battery_pct():
    """Read battery percentage from the first power_supply with a capacity file, or None."""
    try:
        base = "/sys/class/power_supply"
        for name in os.listdir(base):
            cap_path = os.path.join(base, name, "capacity")
            if os.path.exists(cap_path):
                with open(cap_path) as f:
                    return int(f.read().strip())
    except Exception:
        pass
    return None


def command_output(args, timeout=3):
    """Return command stdout without raising when optional system tools are absent."""
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception:
        return ""


def read_text_file(path):
    try:
        with open(path) as handle:
            return handle.read().strip()
    except Exception:
        return None


def aio_power_states():
    states: dict[str, bool | None] = {
        "gps": None,
        "sdr": None,
        "lora": None,
        "usb_ac1200": None,
    }
    if not shutil.which("aiov2_ctl"):
        return states
    output = run_stdout("aiov2_ctl --status", timeout=3) or run_stdout("aiov2_ctl --power", timeout=3)
    for key, label in (("gps", "GPS"), ("sdr", "SDR"), ("lora", "LORA"), ("usb_ac1200", "USB")):
        for line in output.splitlines():
            if label.lower() not in line.lower():
                continue
            low = line.lower()
            if re.search(r"\b(on|enabled|high)\b", low):
                states[key] = True
            elif re.search(r"\b(off|disabled|low)\b", low):
                states[key] = False
    return states


def network_interfaces():
    result = {}
    for name in os.listdir("/sys/class/net"):
        if name == "lo":
            continue
        result[name] = {
            "operstate": read_text_file(f"/sys/class/net/{name}/operstate"),
            "mac": read_text_file(f"/sys/class/net/{name}/address"),
            "rx_bytes": read_text_file(f"/sys/class/net/{name}/statistics/rx_bytes"),
            "tx_bytes": read_text_file(f"/sys/class/net/{name}/statistics/tx_bytes"),
        }
    return result


def collect_hardware_status():
    """Collect detailed hardware state for future Sidekick board layouts."""
    battery = {}
    for name in os.listdir("/sys/class/power_supply") if os.path.isdir("/sys/class/power_supply") else []:
        base = f"/sys/class/power_supply/{name}"
        if read_text_file(f"{base}/type") == "Battery":
            battery = {
                "name": name,
                "percent": read_text_file(f"{base}/capacity"),
                "state": read_text_file(f"{base}/status"),
                "voltage_uv": read_text_file(f"{base}/voltage_now"),
                "current_ua": read_text_file(f"{base}/current_now"),
                "power_uw": read_text_file(f"{base}/power_now"),
                "cycle_count": read_text_file(f"{base}/cycle_count"),
            }
            break

    meminfo = {}
    for line in (read_text_file("/proc/meminfo") or "").splitlines():
        parts = line.replace(":", "").split()
        if len(parts) >= 2:
            meminfo[parts[0]] = int(parts[1]) * 1024

    disk = shutil.disk_usage("/")
    nvme = {}
    for path in glob_paths("/sys/class/nvme/nvme*/device/model"):
        controller = path.split("/")[-3]
        nvme[controller] = {"model": read_text_file(path)}

    processes = command_output(["ps", "-eo", "comm="]).splitlines()
    return {
        "aio": aio_power_states(),
        "battery": battery,
        "cpu": {
            "temperature_c": read_cpu_temp_c(),
            "loadavg": (read_text_file("/proc/loadavg") or "").split()[:3],
            "governor": read_text_file("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
        },
        "memory": {"total_bytes": meminfo.get("MemTotal"), "available_bytes": meminfo.get("MemAvailable")},
        "storage": {"root_total_bytes": disk.total, "root_used_bytes": disk.used, "root_free_bytes": disk.free, "nvme": nvme},
        "network": {"interfaces": network_interfaces(), "default_route": command_output(["ip", "route", "show", "default"])},
        "services": {name: service_active(name) for name in ("gpsd", "readsb", "bluetooth", "NetworkManager", "ssh", "vncserver-x11-serviced")},
        "applications": {name: name in processes for name in ("sdrpp", "gqrx", "kismet", "wireshark", "navit")},
    }


def glob_paths(pattern):
    import glob
    return glob.glob(pattern)


def build_sidekick_line():
    """Build the K=V;K=V;...\\n status line expected by the ESP32 sidekick firmware."""
    with _status_lock:
        wifi_status = _status_data.get("wifi", {}).get("status")
        gps_status = _status_data.get("gps", {}).get("status")
        hardware = _status_data.get("hardware", {})

    net = "G" if wifi_status == "connected" else "R"
    if gps_status in ("2d_fix", "3d_fix"):
        gps = "G"
    elif gps_status == "gpsd_off":
        gps = "X"
    else:
        gps = "Y"

    gpsd_ok = service_active("gpsd")
    readsb_ok = service_active("readsb")
    bt_ok = service_active("bluetooth")
    vnc_ok = service_active("vncserver-x11-serviced") or service_active("vncserver-virtuald")

    temp_c = read_cpu_temp_c()
    if temp_c is None:
        temp = "X"
    elif temp_c < 70:
        temp = "G"
    elif temp_c < 80:
        temp = "Y"
    else:
        temp = "R"

    batt_pct = read_battery_pct()
    battery_state = str(hardware.get("battery", {}).get("state") or "").lower()
    if batt_pct is None:
        bat, pwr, charging = "X", "X", "0"
    else:
        pwr = "G"
        bat = "G" if batt_pct > 30 else ("Y" if batt_pct > 15 else "R")
        charging = "1" if battery_state == "charging" else "0"

    aio = hardware.get("aio", {})
    interfaces = hardware.get("network", {}).get("interfaces", {})
    ethernet_up = any(
        name.startswith("eth") and data.get("operstate") == "up"
        for name, data in interfaces.items()
    )
    active_link = net == "G" or ethernet_up

    fields = {
        "SDR": "G" if aio.get("sdr") is True else ("X" if aio.get("sdr") is False else "Y"),
        "GPS": gps,
        "NET": net,
        "AIO": (
            "G" if any(value is True for value in aio.values())
            else "X" if any(value is False for value in aio.values())
            else "Y"
        ),
        "BAT": bat,
        "BATPCT": batt_pct if batt_pct is not None else "",
        "CHG": charging,
        "SDR+": "X",
        "ADSB": "G" if readsb_ok else "X",
        "GPSD": "G" if gpsd_ok else "X",
        "VNC": "G" if vnc_ok else "X",
        "RVR": "X",
        "READ": "G" if readsb_ok else "X",
        "TAR": "G" if readsb_ok else "X",
        "BT": "G" if bt_ok else "X",
        "TEMP": temp,
        "PWR": pwr,
        "LORA": "G" if aio.get("lora") is True else ("X" if aio.get("lora") is False else "Y"),
        "USB": "G" if aio.get("usb_ac1200") is True else ("X" if aio.get("usb_ac1200") is False else "Y"),
        "ETH": "G" if ethernet_up else "X",
        "INTERNET": "G" if active_link else "R",
        "SYS": "OK",
    }
    return ";".join(f"{k}={v}" for k, v in fields.items()) + ";"


def _refresh_status_once():
    """Collect fresh status.

    Every collector below shells out and can take seconds (gpspipe alone is
    ~2.4s), so they run OUTSIDE _status_lock and only the final assignment
    takes it. Holding the lock across collection made concurrent pollers queue
    up faster than they drained.
    """
    system = get_system_info()
    wifi = get_wifi_status()
    gps = get_gps_status()
    radio = get_radio_status()
    hardware = collect_hardware_status()

    with _process_lock:
        running = list(_active_processes.keys())

    try:
        plugins = load_plugins_config()
        available = [
            {"id": p.get("id"), "label": p.get("label")}
            for p in plugins if p.get("id") and p.get("label")
        ]
    except Exception:
        available = []

    with _status_lock:
        _status_data["system"] = system
        _status_data["wifi"] = wifi
        _status_data["gps"] = gps
        _status_data["radio"] = radio
        _status_data["hardware"] = hardware
        _status_data["apps"]["running"] = running
        _status_data["apps"]["available"] = available
        _status_data["timestamp"] = datetime.now().isoformat()


def _status_refresh_loop():
    while True:
        try:
            _refresh_status_once()
        except Exception as e:
            print(f"Status refresh error: {e}")
        time.sleep(STATUS_REFRESH_INTERVAL_S)


def start_status_refresher():
    """Collect once synchronously, then keep refreshing in the background."""
    _refresh_status_once()
    threading.Thread(target=_status_refresh_loop, daemon=True).start()


def update_status_data(force=False):
    """Serve the cached snapshot; refreshing is the background thread's job.

    Request handlers call this on every request, so it must stay cheap -- the
    Sidekick firmware times out at 3s.
    """
    if force:
        _refresh_status_once()


class StatusAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Status API."""
    
    def log_message(self, format, *args):
        """Override to suppress default logging."""
        pass

    def _control_authorized(self):
        """Bearer-token check for /api/sidekick/control against the persistent .apikey."""
        return self.headers.get("Authorization", "") == f"Bearer {API_KEY}"
    
    def send_json_response(self, data, status_code=200):
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)
        
        # Update status data on each request for fresh data
        update_status_data()
        
        if path == '/api/status' or path == '/':
            # Return full status
            with _status_lock:
                self.send_json_response(_status_data)
        
        elif path.startswith('/api/status/'):
            # Return specific section
            section = path.split('/')[-1]
            with _status_lock:
                if section in _status_data:
                    self.send_json_response({section: _status_data[section]})
                else:
                    self.send_json_response({"error": f"Unknown section: {section}"}, 404)
        
        elif path == '/api/health':
            # Health check endpoint
            self.send_json_response({
                "status": "healthy",
                "timestamp": datetime.now().isoformat()
            })
        
        elif path == '/api/sidekick':
            # Plain-text K=V;K=V;... line for the ESP32 sidekick firmware
            line = build_sidekick_line()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(line.encode())
        
        elif path == '/api/version':
            self.send_json_response({
                "version": "1.0.0",
                "name": "K7BAT uConsole Status API"
            })
        
        else:
            self.send_json_response({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Handle POST requests."""
        content_length = int(self.headers.get('Content-Length', 0))
        
        if content_length > 0:
            body = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self.send_json_response({"error": "Invalid JSON"}, 400)
                return
        else:
            data = {}
        
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/api/command':
            # Handle commands from Arduino or other devices
            command = data.get('command', '')
            
            response = {
                "status": "ok",
                "command_received": command,
                "timestamp": datetime.now().isoformat()
            }
            
            # Process specific commands
            if command == 'reboot':
                import subprocess
                threading.Thread(target=lambda: subprocess.run(['sudo', 'reboot'])).start()
                response["message"] = "Reboot initiated"
            
            elif command == 'shutdown':
                import subprocess
                threading.Thread(target=lambda: subprocess.run(['sudo', 'shutdown', '-h', 'now'])).start()
                response["message"] = "Shutdown initiated"
            
            elif command == 'update_status':
                update_status_data()
                response["message"] = "Status updated"
            
            self.send_json_response(response)
        
        elif path == '/api/data':
            # Accept data from Arduino (e.g., sensor readings)
            with _status_lock:
                for key, value in data.items():
                    if key in ['system', 'wifi', 'gps', 'radio']:
                        _status_data[key].update(value)
            
            update_status_data()
            self.send_json_response({
                "status": "ok",
                "message": "Data received",
                "received_keys": list(data.keys()),
                "timestamp": datetime.now().isoformat()
            })
        
        elif path == '/api/arduino/ping':
            # Arduino ping endpoint
            self.send_json_response({
                "status": "online",
                "timestamp": datetime.now().isoformat(),
                "api_version": "1.1.0"
            })
        
        elif path == '/api/apps/launch':
            # Launch an application by ID
            app_id = data.get('app_id', '')
            
            if not app_id:
                self.send_json_response({"error": "app_id is required"}, 400)
                return
            
            plugins = load_plugins_config()
            app_config = None
            for p in plugins:
                if p.get('id') == app_id:
                    app_config = p
                    break
            
            if not app_config:
                self.send_json_response({"error": f"App '{app_id}' not found"}, 404)
                return
            
            success, message = launch_app(app_id, app_config)
            
            update_status_data()
            
            if success:
                self.send_json_response({
                    "status": "ok",
                    "message": message,
                    "app_id": app_id
                })
            else:
                self.send_json_response({"error": message}, 500)
        
        elif path == '/api/apps/stop':
            # Stop a running application by ID
            app_id = data.get('app_id', '')
            
            if not app_id:
                self.send_json_response({"error": "app_id is required"}, 400)
                return
            
            success, message = stop_app(app_id)
            
            update_status_data()
            
            if success:
                self.send_json_response({
                    "status": "ok",
                    "message": message,
                    "app_id": app_id
                })
            else:
                self.send_json_response({"error": message}, 500)
        
        elif path == '/api/apps/list':
            # List all available and running apps
            update_status_data()
            
            with _status_lock:
                self.send_json_response({
                    "available": _status_data["apps"]["available"],
                    "running": _status_data["apps"]["running"]
                })
        
        elif path == '/api/radio/toggle':
            # Toggle radio on/off
            enabled = data.get('enabled', True)
            
            success, result = toggle_radio(enabled)
            
            update_status_data()
            
            if success:
                self.send_json_response({
                    "status": "ok",
                    "radio": result
                })
            else:
                self.send_json_response({"error": result}, 500)
        
        elif path == '/api/radio/frequency':
            # Set radio frequency in Hz
            freq_hz = data.get('frequency', None)
            
            if freq_hz is None:
                self.send_json_response({"error": "frequency (Hz) is required"}, 400)
                return
            
            success, result = set_radio_frequency(freq_hz)
            
            update_status_data()
            
            if success:
                self.send_json_response({
                    "status": "ok",
                    "radio": result
                })
            else:
                self.send_json_response({"error": result}, 500)
        
        elif path == '/api/sidekick/control':
            # Touchscreen-initiated hardware control (AIO power rails, services, SDR+)
            if not self._control_authorized():
                self.send_json_response({"ok": False, "error": "unauthorized"}, 401)
                return
            
            status_code, response = handle_sidekick_control(data)
            update_status_data()
            self.send_json_response(response, status_code)
        
        elif path == '/api/events':
            # Get pending events (Arduino button/touchscreen events)
            events = get_events()
            self.send_json_response({
                "events": events,
                "count": len(events),
                "timestamp": datetime.now().isoformat()
            })
        
        elif path == '/api/event':
            # Add a single event (for Arduino to send button presses)
            event_type = data.get('type', 'unknown')
            
            add_event(event_type, data.get('data'))
            
            self.send_json_response({
                "status": "ok",
                "message": f"Event '{event_type}' recorded"
            })
        
        else:
            self.send_json_response({"error": "Not found"}, 404)


class ThreadedHTTPServer(HTTPServer):
    """HTTP server that handles requests in separate threads."""
    
    def process_request(self, request, client_address):
        """Start a new thread to handle the request."""
        thread = threading.Thread(target=self.process_request_thread,
                                  args=(request, client_address))
        thread.daemon = True
        thread.start()
    
    def process_request_thread(self, request, client_address):
        """Process request in a thread."""
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def main(port=8080, host='0.0.0.0'):
    """Start the Status API server."""
    print(f"K7BAT uConsole Status API v1.1.0")
    print(f"Starting HTTP server on {host}:{port}")
    print()
    print("GET Endpoints:")
    print("  GET  /                    - Full status")
    print("  GET  /api/status          - Full status")
    print("  GET  /api/status/system   - System info only")
    print("  GET  /api/status/wifi     - Wi-Fi status only")
    print("  GET  /api/status/gps      - GPS status only")
    print("  GET  /api/status/radio    - Radio status only")
    print("  GET  /api/apps/list       - List available and running apps")
    print("  GET  /api/health          - Health check")
    print("  GET  /api/version         - API version")
    print()
    print("POST Endpoints:")
    print("  POST /api/command         - Send commands (reboot, shutdown)")
    print("  POST /api/data            - Post sensor/device data")
    print("  POST /api/event           - Record Arduino button/touch event")
    print("  POST /api/events          - Get pending events queue")
    print()
    print("App Control:")
    print("  POST /api/apps/launch     - Launch app by ID (e.g., {\"app_id\": \"battery-diag\"})")
    print("  POST /api/apps/stop       - Stop running app (e.g., {\"app_id\": \"battery-diag\"})")
    print()
    print("Radio Control:")
    print("  POST /api/radio/toggle    - Toggle radio (e.g., {\"enabled\": true})")
    print("  POST /api/radio/frequency - Set frequency Hz (e.g., {\"frequency\": 433000000})")
    print()
    
    # Prime the cache, then keep it fresh off the request path
    start_status_refresher()
    
    # Start server
    server = ThreadedHTTPServer((host, port), StatusAPIHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='K7BAT uConsole Status API')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on (default: 8080)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    
    args = parser.parse_args()
    main(args.port, args.host)

