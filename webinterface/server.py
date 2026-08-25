#!/usr/bin/env python3
"""
K7BAT uConsole Web Interface Server
Flask-based REST API with WebSocket support for real-time updates
"""

import os
import sys
import json
import subprocess
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

APP_NAME = "K7BAT uConsole Web Interface"
VERSION = "1.3.0"

app = Flask(__name__, 
            static_folder='www', 
            template_folder='www',
            static_url_path='')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAYLOADS_DIR = os.path.join(BASE_DIR, 'payloads')
PLUGINS_DIR = os.path.join(BASE_DIR, 'plugins')

# Ensure directories exist
os.makedirs(PAYLOADS_DIR, exist_ok=True)
os.makedirs(PLUGINS_DIR, exist_ok=True)

# System state
system_stats = {
    "cpu": 0,
    "ram": 0,
    "disk": 0,
    "network": {},
    "wifi_interfaces": [],
    "timestamp": datetime.now().isoformat()
}

def get_system_stats():
    """Get current system statistics"""
    try:
        # CPU usage
        cpu = subprocess.check_output(['cat', '/proc/stat'], text=True)
        cpu_line = cpu.split('\n')[0]
        cpu_values = [int(x) for x in cpu_line.split()[1:]]
        total = sum(cpu_values)
        idle = cpu_values[3]
        cpu_percent = ((total - idle) / total * 100) if total > 0 else 0
        
        # RAM usage
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(':')
                    value = int(parts[1]) * 1024  # Convert to bytes
                    meminfo[key] = value
        
        total_mem = meminfo.get('MemTotal', 0)
        available_mem = meminfo.get('MemAvailable', 0)
        ram_percent = ((total_mem - available_mem) / total_mem * 100) if total_mem > 0 else 0
        
        # Disk usage
        disk = os.statvfs('/')
        disk_total = disk.f_frsize * disk.f_blocks
        disk_free = disk.f_frsize * disk.f_bfree
        disk_percent = ((disk_total - disk_free) / disk_total * 100) if disk_total > 0 else 0
        
        # Network interfaces
        network = {}
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]  # Skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 11:
                        iface = parts[0].rstrip(':')
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[9])
                        network[iface] = {
                            "rx_bytes": rx_bytes,
                            "tx_bytes": tx_bytes
                        }
        except Exception as e:
            print(f"Network error: {e}")
        
        # WiFi interfaces
        wifi_interfaces = []
        try:
            result = subprocess.run(['iw', 'dev'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.strip().startswith('Interface '):
                        iface = line.split()[1]
                        wifi_interfaces.append(iface)
        except Exception as e:
            print(f"WiFi error: {e}")
        
        return {
            "cpu": round(cpu_percent, 2),
            "ram": round(ram_percent, 2),
            "disk": round(disk_percent, 2),
            "network": network,
            "wifi_interfaces": wifi_interfaces,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Stats error: {e}")
        return system_stats

def stats_thread():
    """Background thread for updating system stats"""
    while True:
        global system_stats
        system_stats = get_system_stats()
        socketio.emit('system_update', system_stats, broadcast=True)
        time.sleep(4)

@app.route('/')
def index():
    """Serve the main dashboard"""
    return send_from_directory('www', 'index.html')

@app.route('/api/system')
def api_system():
    """Get current system statistics"""
    return jsonify(system_stats)

@app.route('/api/wifi/interfaces')
def api_wifi_interfaces():
    """List WiFi interfaces"""
    try:
        result = subprocess.run(['iw', 'dev'], capture_output=True, text=True)
        interfaces = []
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.strip().startswith('Interface '):
                    iface = line.split()[1]
                    # Get interface info
                    info_result = subprocess.run(['iw', 'dev', iface, 'info'], 
                                                capture_output=True, text=True)
                    interfaces.append({
                        "name": iface,
                        "type": "unknown",
                        "channel": 0
                    })
        return jsonify({"interfaces": interfaces})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/wifi/scan', methods=['POST'])
def api_wifi_scan():
    """Scan for WiFi networks"""
    try:
        data = request.get_json() or {}
        interface = data.get('interface', 'wlan0')
        
        result = subprocess.run(['iwdev', interface, 'scan'], 
                              capture_output=True, text=True)
        
        networks = []
        current_network = {}
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('BSS '):
                if current_network:
                    networks.append(current_network)
                current_network = {"bssid": line.split()[1]}
            elif line.startswith('SSID:'):
                current_network['ssid'] = line[6:]
            elif line.startswith('freq:'):
                current_network['frequency'] = int(line.split()[1])
            elif line.startswith('signal:'):
                current_network['signal'] = float(line.split()[1])
        
        if current_network:
            networks.append(current_network)
        
        return jsonify({"networks": networks, "count": len(networks)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/payloads', methods=['GET', 'POST'])
def api_payloads():
    """Manage payloads"""
    if request.method == 'GET':
        payloads = []
        for filename in os.listdir(PAYLOADS_DIR):
            filepath = os.path.join(PAYLOADS_DIR, filename)
            payloads.append({
                "name": filename,
                "path": f"/api/payloads/{filename}",
                "size": os.path.getsize(filepath),
                "created": datetime.fromtimestamp(os.path.getctime(filepath)).isoformat()
            })
        return jsonify({"payloads": payloads})
    
    elif request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No filename provided"}), 400
        
        filepath = os.path.join(PAYLOADS_DIR, file.filename)
        file.save(filepath)
        
        return jsonify({
            "success": True,
            "message": f"Payload '{file.filename}' uploaded successfully",
            "path": f"/api/payloads/{file.filename}"
        })

@app.route('/api/payloads/<filename>')
def api_payload_download(filename):
    """Download a payload"""
    return send_from_directory(PAYLOADS_DIR, filename, as_attachment=True)

@app.route('/api/payloads/<filename>', methods=['DELETE'])
def api_payload_delete(filename):
    """Delete a payload"""
    filepath = os.path.join(PAYLOADS_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"success": True, "message": f"Payload '{filename}' deleted"})
    return jsonify({"error": "Payload not found"}), 404

@app.route('/api/payloads/<filename>/execute', methods=['POST'])
def api_payload_execute(filename):
    """Execute a payload"""
    filepath = os.path.join(PAYLOADS_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({"error": "Payload not found"}), 404
    
    try:
        result = subprocess.run(['python3', filepath], 
                              capture_output=True, text=True, timeout=30)
        
        return jsonify({
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Execution timed out"}), 408
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/plugins', methods=['GET'])
def api_plugins():
    """List available plugins"""
    plugins = []
    
    for filename in os.listdir(PLUGINS_DIR):
        if filename.endswith('.py'):
            filepath = os.path.join(PLUGINS_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                
                # Extract plugin metadata from docstring
                plugin_info = {
                    "name": filename[:-3],
                    "path": f"/api/plugins/{filename}",
                    "version": "1.0.0",
                    "author": "Unknown",
                    "description": "No description available"
                }
                
                plugins.append(plugin_info)
            except Exception as e:
                print(f"Error loading plugin {filename}: {e}")
    
    return jsonify({"plugins": plugins, "count": len(plugins)})

@app.route('/api/plugins/<filename>', methods=['GET'])
def api_plugin_get(filename):
    """Get plugin details"""
    filepath = os.path.join(PLUGINS_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "Plugin not found"}), 404
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    return jsonify({
        "name": filename[:-3],
        "content": content,
        "path": f"/api/plugins/{filename}"
    })

@app.route('/api/plugins/<filename>', methods=['POST'])
def api_plugin_upload(filename):
    """Upload a plugin"""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No filename provided"}), 400
    
    # Ensure it's a .py file
    if not filename.endswith('.py'):
        filename += '.py'
    
    filepath = os.path.join(PLUGINS_DIR, filename)
    file.save(filepath)
    
    return jsonify({
        "success": True,
        "message": f"Plugin '{filename}' uploaded successfully"
    })

@app.route('/api/tools/kismet/start', methods=['POST'])
def api_kismet_start():
    """Start Kismet server"""
    try:
        data = request.get_json() or {}
        interface = data.get('interface', 'wlan0')
        
        process = subprocess.Popen(
            ['kismet', '-c', interface],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        return jsonify({
            "success": True,
            "pid": process.pid,
            "message": f"Kismet started on interface {interface}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/tools/bettercap/start', methods=['POST'])
def api_bettercap_start():
    """Start Bettercap"""
    try:
        data = request.get_json() or {}
        interface = data.get('interface', 'wlan0')
        caplet = data.get('caplet', '')
        
        cmd = ['bettercap']
        if caplet:
            cmd.extend(['-module', caplet])
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        return jsonify({
            "success": True,
            "pid": process.pid,
            "message": f"Bettercap started"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connections"""
    print('Client connected')
    emit('system_update', system_stats)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnections"""
    print('Client disconnected')

if __name__ == '__main__':
    # Start stats thread
    threading.Thread(target=stats_thread, daemon=True).start()
    
    print(f"{APP_NAME} v{VERSION}")
    print("Starting web server on http://0.0.0.0:5000")
    print(f"Payloads directory: {PAYLOADS_DIR}")
    print(f"Plugins directory: {PLUGINS_DIR}")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
