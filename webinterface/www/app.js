// K7BAT uConsole Web Interface - Main Application
let socket = null;
let cpuHistory = [];
let ramHistory = [];

document.addEventListener('DOMContentLoaded', function() {
    initNavigation();
    initWebSocket();
    loadDashboard();
    
    // Load initial data
    refreshSystemStats();
    setInterval(refreshSystemStats, 5000);
});

function initNavigation() {
    const navBtns = document.querySelectorAll('.nav-btn');
    
    navBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remove active class from all buttons
            navBtns.forEach(b => b.classList.remove('active'));
            
            // Add active class to clicked button
            this.classList.add('active');
            
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Show selected tab
            const target = this.getAttribute('data-target');
            document.getElementById(target).classList.add('active');
        });
    });
}

function initWebSocket() {
    socket = io();
    
    socket.on('connect', function() {
        document.getElementById('connection-status').textContent = 'Connected';
        document.getElementById('connection-status').style.color = '#4caf50';
        
        // Request initial data
        socket.emit('system_update', {});
    });
    
    socket.on('disconnect', function() {
        document.getElementById('connection-status').textContent = 'Disconnected';
        document.getElementById('connection-status').style.color = '#f44336';
    });
    
    socket.on('system_update', function(data) {
        updateSystemStats(data);
        updateCharts(data);
    });
}

function updateSystemStats(data) {
    // Update stat boxes
    document.getElementById('cpu-value').textContent = data.cpu + '%';
    document.getElementById('ram-value').textContent = data.ram + '%';
    document.getElementById('disk-value').textContent = data.disk + '%';
    
    // Update network interfaces
    const interfaceList = document.getElementById('interface-list');
    if (data.network && Object.keys(data.network).length > 0) {
        let html = '';
        for (const [iface, stats] of Object.entries(data.network)) {
            const rxMB = (stats.rx_bytes / 1024 / 1024).toFixed(2);
            const txMB = (stats.tx_bytes / 1024 / 1024).toFixed(2);
            html += `
                <div class="interface-item">
                    <span>${iface}</span>
                    <span>↓ ${rxMB} MB ↑ ${txMB} MB</span>
                </div>
            `;
        }
        interfaceList.innerHTML = html;
    } else {
        interfaceList.innerHTML = '<p>No interfaces detected</p>';
    }
    
    // Update WiFi interfaces
    const wifiInterfaceList = document.getElementById('wifi-interface-list');
    if (data.wifi_interfaces && data.wifi_interfaces.length > 0) {
        let html = '';
        data.wifi_interfaces.forEach(iface => {
            html += `
                <div class="interface-item">
                    <span>${iface}</span>
                    <button class="action-btn" style="padding: 0.25rem 0.75rem; font-size: 0.8rem;" 
                            onclick="showToast('Scanning ${iface}...')">Scan</button>
                </div>
            `;
        });
        wifiInterfaceList.innerHTML = html;
    } else {
        wifiInterfaceList.innerHTML = '<p>No WiFi interfaces detected</p>';
    }
}

function updateCharts(data) {
    // Update CPU history
    cpuHistory.push(data.cpu);
    if (cpuHistory.length > 50) cpuHistory.shift();
    
    // Update RAM history
    ramHistory.push(data.ram);
    if (ramHistory.length > 50) ramHistory.shift();
}

function refreshSystemStats() {
    fetch('/api/system')
        .then(response => response.json())
        .then(data => updateSystemStats(data));
}

// Dashboard Functions
function scanWifi() {
    showToast('Scanning for WiFi networks...');
    
    fetch('/api/wifi/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interface: 'wlan0' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.networks) {
            showToast(`Found ${data.count} WiFi networks`);
        }
    })
    .catch(err => {
        showToast('Scan failed: ' + err.message, 'error');
    });
}

function startKismet() {
    const interface = document.getElementById('kismet-interface').value;
    
    if (!interface) {
        showToast('Please select a WiFi interface', 'error');
        return;
    }
    
    fetch('/api/tools/kismet/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interface: interface })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`Kismet started with PID ${data.pid}`);
        } else {
            showToast('Failed to start Kismet', 'error');
        }
    });
}

function startAircrack() {
    const interface = document.getElementById('aircrack-interface').value;
    
    if (!interface) {
        showToast('Please select a WiFi interface', 'error');
        return;
    }
    
    showToast(`Starting monitor mode on ${interface}...`);
    showToast('Use the terminal for full aircrack-ng commands', 'info');
}

function startBettercap() {
    const interface = document.getElementById('bettercap-interface').value;
    
    if (!interface) {
        showToast('Please select a WiFi interface', 'error');
        return;
    }
    
    fetch('/api/tools/bettercap/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interface: interface })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`Bettercap started with PID ${data.pid}`);
        }
    });
}

function stopTool(toolName) {
    showToast(`${toolName} stopped`);
}

function startMonitorMode() {
    const interface = document.getElementById('monitor-interface').value;
    
    if (!interface) {
        showToast('Please select a WiFi interface', 'error');
        return;
    }
    
    showToast(`Enabling monitor mode on ${interface}...`);
}

function stopMonitorMode() {
    showToast('Monitor mode disabled');
}

// Payload Functions
function uploadPayload() {
    const fileInput = document.getElementById('payload-file-input');
    const file = fileInput.files[0];
    
    if (!file) {
        showToast('Please select a file', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    fetch('/api/payloads', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(`Payload uploaded: ${data.message}`);
            loadPayloads();
        }
    });
}

function loadPayloads() {
    fetch('/api/payloads')
        .then(response => response.json())
        .then(data => {
            const tbody = document.querySelector('#payloads-table tbody');
            let html = '';
            
            data.payloads.forEach(payload => {
                html += `
                    <tr>
                        <td>${payload.name}</td>
                        <td>${formatBytes(payload.size)}</td>
                        <td>${new Date(payload.created).toLocaleString()}</td>
                        <td>
                            <button class="action-btn" style="font-size: 0.75rem;" 
                                    onclick="executePayload('${payload.name}')">Run</button>
                            <button class="action-btn" style="font-size: 0.75rem; background: #f44336;"
                                    onclick="deletePayload('${payload.name}')">Delete</button>
                        </td>
                    </tr>
                `;
            });
            
            tbody.innerHTML = html;
        });
}

function executePayload(name) {
    fetch(`/api/payloads/${name}/execute`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast(`Payload executed successfully`);
                console.log('Output:', data.stdout);
                if (data.stderr) {
                    console.error('Errors:', data.stderr);
                }
            } else {
                showToast(`Execution failed: ${data.error}`, 'error');
            }
        });
}

function deletePayload(name) {
    if (!confirm(`Delete payload "${name}"?`)) return;
    
    fetch(`/api/payloads/${name}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            showToast(data.message);
            loadPayloads();
        });
}

function createTemplate(type) {
    let template = '';
    
    switch (type) {
        case 'wifi-scan':
            template = `#!/usr/bin/env python3
import subprocess

def scan_wifi():
    result = subprocess.run(['iwdev', 'wlan0', 'scan'], 
                          capture_output=True, text=True)
    print(result.stdout)

if __name__ == '__main__':
    scan_wifi()`;
            break;
            
        case 'deauth-attack':
            template = `#!/usr/bin/env python3
import subprocess

def deauth_target(bssid, target, interface='wlan0'):
    cmd = ['aireplay-ng', '--deauth', '10', '-a', bssid, '-c', target, interface]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)

if __name__ == '__main__':
    # Usage: deauth_target('AA:BB:CC:DD:EE:FF', 'GG:HH:II:JJ:KK:LL')
    pass`;
            break;
            
        case 'capture-handshake':
            template = `#!/usr/bin/env python3
import subprocess

def capture_handshake(interface='wlan0mon', bssid='', output='handshake.pcap'):
    cmd = ['airodump-ng', '--bssid', bssid, '-c', '6', 
           '--write', output, interface]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)

if __name__ == '__main__':
    # Usage: capture_handshake('wlan0mon', 'AA:BB:CC:DD:EE:FF')
    pass`;
            break;
            
        case 'mitm-proxy':
            template = `#!/usr/bin/env python3
import http.server
import socketserver

class MITMHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        print(f"GET request: {self.path}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Intercepted!')
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        print(f"POST data: {post_data}")
        self.send_response(200)
        self.end_headers()

if __name__ == '__main__':
    PORT = 8080
    with socketserver.TCPServer(('', PORT), MITMHandler) as httpd:
        print(f'MITM proxy running on port {PORT}')
        httpd.serve_forever()`;
            break;
    }
    
    const blob = new Blob([template], { type: 'text/x-python' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${type}.py`;
    a.click();
    URL.revokeObjectURL(url);
}

// Plugin Functions
function uploadPlugin() {
    const fileInput = document.getElementById('plugin-file-input');
    const file = fileInput.files[0];
    
    if (!file) {
        showToast('Please select a plugin file', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    fetch('/api/plugins/' + file.name, { method: 'POST', body: formData })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast(`Plugin uploaded: ${file.name}`);
                loadPlugins();
            }
        });
}

function loadPlugins() {
    fetch('/api/plugins')
        .then(response => response.json())
        .then(data => {
            const tbody = document.querySelector('#plugins-table tbody');
            let html = '';
            
            data.plugins.forEach(plugin => {
                html += `
                    <tr>
                        <td>${plugin.name}</td>
                        <td>${plugin.version}</td>
                        <td>${plugin.description}</td>
                        <td>
                            <button class="action-btn" style="font-size: 0.75rem;" 
                                    onclick="loadPluginContent('${plugin.name}')">View</button>
                            <button class="action-btn" style="font-size: 0.75rem; background: #f44336;"
                                    onclick="deletePlugin('${plugin.name}')">Delete</button>
                        </td>
                    </tr>
                `;
            });
            
            tbody.innerHTML = html;
        });
}

function loadPluginContent(name) {
    fetch(`/api/plugins/${name}.py`)
        .then(response => response.json())
        .then(data => {
            alert(`Plugin: ${data.name}\n\n${data.content.substring(0, 500)}...`);
        });
}

function deletePlugin(name) {
    if (!confirm(`Delete plugin "${name}"?`)) return;
    
    fetch(`/api/plugins/${name}.py`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            showToast(data.message);
            loadPlugins();
        });
}

// System Functions
function loadSystemInfo() {
    fetch('/api/system')
        .then(response => response.json())
        .then(data => {
            document.getElementById('system-info').textContent = 
                JSON.stringify(data, null, 2);
        });
}

// Helper Functions
function showToast(message, type = 'info') {
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    // Style the toast
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: rgba(0, 0, 0, 0.9);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 4px;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    
    if (type === 'error') {
        toast.style.borderLeft = '4px solid #f44336';
    } else if (type === 'success') {
        toast.style.borderLeft = '4px solid #4caf50';
    }
    
    document.body.appendChild(toast);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// Initialize dashboard
function loadDashboard() {
    // Update uptime
    fetch('/api/system')
        .then(response => response.json())
        .then(data => {
            const uptime = process.uptime ? 
                Math.floor(process.uptime()) : 0;
            
            const hours = Math.floor(uptime / 3600);
            const minutes = Math.floor((uptime % 3600) / 60);
            const seconds = uptime % 60;
            
            document.getElementById('uptime').textContent = 
                `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        });
}

// Override for browser environment
const process = { uptime: () => 0 };
