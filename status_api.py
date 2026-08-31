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
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Add app directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import plugins configuration
try:
    from plugins.plugin_manager import PluginManager
except ImportError:
    PluginManager = None

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
    "apps": {
        "running": [],
        "available": []
    },
    "timestamp": datetime.now().isoformat()
}

_status_lock = threading.Lock()

# Event queue for Arduino buttons/touchscreen events
_events_queue = []
_events_lock = threading.Lock()

# Active processes tracking
_active_processes = {}
_process_lock = threading.Lock()


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
                    signal_strength = int(parts[2])
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
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True, stderr=subprocess.DEVNULL, timeout=timeout
        ).strip()
    except Exception:
        return ""


def get_gps_status():
    """Get GPS status by querying gpsd directly via gpspipe."""
    result = {
        "status": "no_fix",
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "satellites": 0,
        "speed": None
    }

    gpsd_up = service_active("gpsd") or service_active("gpsd.socket")
    if not gpsd_up:
        result["status"] = "gpsd_off"
        return result

    raw = run_stdout("gpspipe -w -n 12", timeout=3)
    tpv = {}
    sats = None
    for line in raw.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        if j.get("class") == "TPV":
            tpv.update(j)
        elif j.get("class") == "SKY":
            sats = j.get("uSat") if j.get("uSat") is not None else j.get("nSat")
            if sats is None and isinstance(j.get("satellites"), list):
                sats = len(j.get("satellites"))

    mode = tpv.get("mode", 0)
    result["status"] = {0: "no_fix", 1: "no_fix", 2: "2d_fix", 3: "3d_fix"}.get(mode, "no_fix")
    result["satellites"] = sats or 0
    lat, lon = tpv.get("lat"), tpv.get("lon")
    if isinstance(lat, (int, float)):
        result["latitude"] = lat
    if isinstance(lon, (int, float)):
        result["longitude"] = lon
    result["altitude"] = tpv.get("alt")
    result["speed"] = tpv.get("speed")
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


def build_sidekick_line():
    """Build the K=V;K=V;...\\n status line expected by the ESP32 sidekick firmware."""
    with _status_lock:
        wifi_status = _status_data.get("wifi", {}).get("status")
        gps_status = _status_data.get("gps", {}).get("status")

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
    if batt_pct is None:
        bat, pwr = "X", "X"
    else:
        pwr = "G"
        bat = "G" if batt_pct > 30 else ("Y" if batt_pct > 15 else "R")

    fields = {
        "SDR": "X",
        "GPS": gps,
        "NET": net,
        "AIO": "X",
        "BAT": bat,
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
        "SYS": "OK",
    }
    return ";".join(f"{k}={v}" for k, v in fields.items()) + ";"


def update_status_data():
    """Update all status data."""
    global _status_data
    
    with _status_lock:
        _status_data["system"] = get_system_info()
        _status_data["wifi"] = get_wifi_status()
        _status_data["gps"] = get_gps_status()
        _status_data["radio"] = get_radio_status()
        
        # Update running apps
        with _process_lock:
            _status_data["apps"]["running"] = list(_active_processes.keys())
        
        # Load available plugins/apps
        try:
            plugins = load_plugins_config()
            _status_data["apps"]["available"] = [
                {"id": p.get("id"), "label": p.get("label")}
                for p in plugins if p.get("id") and p.get("label")
            ]
        except Exception:
            _status_data["apps"]["available"] = []
        
        _status_data["timestamp"] = datetime.now().isoformat()


class StatusAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Status API."""
    
    def log_message(self, format, *args):
        """Override to suppress default logging."""
        pass
    
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
    
    # Initial status update
    update_status_data()
    
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
