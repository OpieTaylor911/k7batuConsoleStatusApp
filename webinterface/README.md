# K7BAT uConsole Web Interface

A complete web-based interface for the uConsole Status App with payload loader and plugin system.

## Components

### 1. Web Server (`server.py`)
- Flask-based REST API server
- WebSocket support for real-time updates
- Built-in HTTP server for captive portals

### 2. Frontend (`www/`)
- Modern dashboard with two-column layout
- Real-time system monitoring
- WiFi tool controls
- Payload upload & management

### 3. Payload Loader (`payloads/`)
- Upload and manage attack payloads
- Template-based payload creation
- Execution history tracking

### 4. Plugin System (`plugins/`)
- Dynamic plugin loading
- Plugin metadata system
- Plugin lifecycle management

## Installation

```bash
pip install -r requirements.txt
python3 server.py
```

## Features

- **Dashboard**: Real-time CPU, RAM, network stats
- **WiFi Tools**: Launch Kismet, bettercap, aircrack-ng
- **Payloads**: Upload and execute payloads
- **Plugins**: Extend functionality via plugins
- **Captive Portal**: Built-in portal for phishing attacks

## Security Notes

⚠️ Only use on networks you own or are explicitly authorized to test.
