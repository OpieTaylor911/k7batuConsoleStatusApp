# K7BAT uConsole Status API v1.1.0

HTTP API for Arduino and other devices to query and post status information.

## Features

- RESTful HTTP API on port 8080
- GET endpoints for status data (system, Wi-Fi, GPS, radio)
- POST endpoints for commands and data submission
- JSON responses
- Thread-safe data access
- CORS enabled for web-based clients
- **Remote app launching** - Launch Python apps, plugins, and tools remotely
- **Radio control** - Turn SDR radios on/off, set frequency
- **Arduino button/touchscreen support** - Event queue for hardware controls

## Endpoints

### GET Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` or `/api/status` | Full status object |
| `/api/status/system` | System information only |
| `/api/status/wifi` | Wi-Fi status only |
| `/api/status/gps` | GPS status only |
| `/api/status/radio` | Radio/SDR status only |
| `/api/apps/list` | List available and running apps |
| `/api/events` | Get pending Arduino events (button presses, etc.) |
| `/api/health` | Health check |
| `/api/version` | API version info |

### POST Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/command` | Send system commands (reboot, shutdown) |
| `/api/data` | Post sensor/device data |
| `/api/event` | Record Arduino button/touch event |
| `/api/apps/launch` | Launch app by ID (e.g., `{\"app_id\": \"battery-diag\"}`) |
| `/api/apps/stop` | Stop running app |
| `/api/radio/toggle` | Toggle radio on/off |
| `/api/radio/frequency` | Set radio frequency in Hz |

## Updated Status Data Structure

```json
{
  "system": {
    "cpu_load": 0.5,
    "memory_used": "256MB",
    "memory_total": "1024MB",
    "disk_usage": "45%",
    "uptime": "2h 30m",
    "hostname": "uconsole",
    "os_version": "Debian GNU/Linux 12"
  },
  "wifi": {
    "status": "connected",
    "interface": "wlan0",
    "ssid": "MyNetwork",
    "ip_address": "192.168.1.100",
    "signal_strength": -65,
    "connected_devices": []
  },
  "gps": {
    "status": "no_fix",
    "latitude": null,
    "longitude": null,
    "altitude": null,
    "satellites": 0,
    "speed": null
  },
  "radio": {
    "enabled": true,
    "status": "active",
    "frequency": 433000000,
    "mode": "FM"
  },
  "apps": {
    "running": ["battery-diag", "wifi-assessment"],
    "available": [
      {"id": "battery-diag", "label": "Battery Diag"},
      {"id": "wifi-assessment", "label": "Wi-Fi Assessment"}
    ]
  },
  "timestamp": "2024-01-01T12:00:00"
}
```

## Usage Examples

### Arduino Example (ESP32/ESP8266)

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "your_network";
const char* password = "your_password";
const char* apiHost = "192.168.1.100"; // uConsole IP

// Button pins
const int POWER_BUTTON_PIN = 4;
const int VOLUME_UP_PIN = 5;
const int VOLUME_DOWN_PIN = 6;

void setup() {
  WiFi.begin(ssid, password);
  
  pinMode(POWER_BUTTON_PIN, INPUT_PULLUP);
  pinMode(VOLUME_UP_PIN, INPUT_PULLUP);
  pinMode(VOLUME_DOWN_PIN, INPUT_PULLUP);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  
  Serial.println("Connected to Wi-Fi");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    
    // Check button presses
    checkButton(&http, "power", POWER_BUTTON_PIN);
    checkButton(&http, "volume_up", VOLUME_UP_PIN);
    checkButton(&http, "volume_down", VOLUME_DOWN_PIN);
    
    // Ping the API every 5 seconds to keep connection alive
    http.begin(apiHost, 8080, "/api/arduino/ping");
    int httpResponseCode = http.GET();
    
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println(response);
    }
    
    http.end();
  }
  
  delay(100); // Check buttons frequently
}

void checkButton(HTTPClient* http, const char* buttonId, int pin) {
  static bool lastState[3] = {true, true, true};
  
  bool currentState = digitalRead(pin);
  
  if (currentState != lastState[pin]) {
    if (currentState == LOW) { // Button pressed
      String eventUrl = String(apiHost) + ":8080/api/event";
      
      http->begin(eventUrl.c_str());
      http->addHeader("Content-Type", "application/json");
      
      String payload = String("{\"type\":\"button_press\",\"data\":{\"id\":\"") 
                     + buttonId + string("\",\"action\":\"short_click\"}}");
      
      int respCode = http->POST(payload);
      
      if (respCode > 0) {
        Serial.println("Button event sent: " + String(buttonId));
      } else {
        Serial.println("Failed to send button event");
      }
      
      http->end();
    }
    
    lastState[pin] = currentState;
    delay(50); // Debounce
  }
}
```

### Remote App Launching (Python)

```python
def launch_app(app_id):
    """Launch an app remotely via API"""
    response = requests.post(
        f"{API_URL}/api/apps/launch",
        json={"app_id": app_id}
    )
    return response.json()

def stop_app(app_id):
    """Stop a running app"""
    response = requests.post(
        f"{API_URL}/api/apps/stop",
        json={"app_id": app_id}
    )
    return response.json()

# Launch battery diagnostic
result = launch_app("battery-diag")
print(f"Launched: {result['message']}")

# Stop the app later
stop_result = stop_app("battery-diag")
print(f"Stopped: {stop_result['message']}")
```

### Radio Control (Python)

```python
def toggle_radio(enabled):
    """Turn radio on/off"""
    response = requests.post(
        f"{API_URL}/api/radio/toggle",
        json={"enabled": enabled}
    )
    return response.json()

def set_frequency(freq_mhz):
    """Set radio frequency in MHz"""
    freq_hz = int(freq_mhz * 1_000_000)
    response = requests.post(
        f"{API_URL}/api/radio/frequency",
        json={"frequency": freq_hz}
    )
    return response.json()

# Turn radio on
toggle_radio(True)

# Set frequency to 146.52 MHz (2m ham band)
set_frequency(146.52)
```

### Python Example

```python
import requests
import json

API_URL = "http://192.168.1.100:8080"

def get_status():
    """Get full status from API"""
    response = requests.get(f"{API_URL}/api/status")
    return response.json()

def get_wifi_status():
    """Get Wi-Fi status only"""
    response = requests.get(f"{API_URL}/api/status/wifi")
    return response.json()

def send_command(command):
    """Send a command to the uConsole"""
    response = requests.post(
        f"{API_URL}/api/command",
        json={"command": command}
    )
    return response.json()

def post_sensor_data(data):
    """Post sensor data to the API"""
    response = requests.post(
        f"{API_URL}/api/data",
        json=data
    )
    return response.json()

# Example usage
if __name__ == "__main__":
    # Get status
    status = get_status()
    print(json.dumps(status, indent=2))
    
    # Get Wi-Fi only
    wifi = get_wifi_status()
    print(f"Wi-Fi: {wifi['wifi']['status']} - {wifi['wifi']['ssid']}")
    
    # Send command
    result = send_command("reboot")
    print(result)
```

### Arduino Remote App Launching & Radio Control

```cpp
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>

const char* ssid = "your_network";
const char* password = "your_password";
const char* apiHost = "192.168.1.100"; // uConsole IP

void setup() {
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  
  Serial.println("Connected to Wi-Fi");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    
    // Launch an app remotely
    launchApp(&http, "battery-diag");
    delay(3000); // Wait 3 seconds
    
    // Stop the app
    stopApp(&http, "battery-diag");
    delay(3000);
    
    // Toggle radio on/off
    toggleRadio(&http, true);
    delay(2000);
    toggleRadio(&http, false);
    delay(5000); // Wait 5 seconds before repeating
  }
}

void launchApp(HTTPClient* http, const char* appId) {
  String url = String(apiHost) + ":8080/api/apps/launch";
  
  http->begin(url.c_str());
  http->addHeader("Content-Type", "application/json");
  
  String payload = "{\"app_id\":\"" + String(appId) + "\"}";
  int respCode = http->POST(payload);
  
  if (respCode > 0) {
    String response = http->getString();
    Serial.println("Launch result: " + response);
  } else {
    Serial.println("Failed to launch app");
  }
  
  http->end();
}

void stopApp(HTTPClient* http, const char* appId) {
  String url = String(apiHost) + ":8080/api/apps/stop";
  
  http->begin(url.c_str());
  http->addHeader("Content-Type", "application/json");
  
  String payload = "{\"app_id\":\"" + String(appId) + "\"}";
  int respCode = http->POST(payload);
  
  if (respCode > 0) {
    String response = http->getString();
    Serial.println("Stop result: " + response);
  } else {
    Serial.println("Failed to stop app");
  }
  
  http->end();
}

void toggleRadio(HTTPClient* http, bool enabled) {
  String url = String(apiHost) + ":8080/api/radio/toggle";
  
  http->begin(url.c_str());
  http->addHeader("Content-Type", "application/json");
  
  String payload = "{\"enabled\":" + String(enabled ? "true" : "false") + "}";
  int respCode = http->POST(payload);
  
  if (respCode > 0) {
    String response = http->getString();
    Serial.println("Radio toggle result: " + response);
  } else {
    Serial.println("Failed to toggle radio");
  }
  
  http->end();
}
```

### curl Examples

```bash
# Get full status
curl http://192.168.1.100:8080/api/status

# Get system info only
curl http://192.168.1.100:8080/api/status/system

# Health check
curl http://192.168.1.100:8080/api/health

# Send command to reboot
curl -X POST http://192.168.1.100:8080/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "reboot"}'

# Post sensor data
curl -X POST http://192.168.1.100:8080/api/data \
  -H "Content-Type: application/json" \
  -d '{
    "gps": {
      "status": "3d_fix",
      "latitude": 47.6062,
      "longitude": -122.3321
    }
  }'

# Launch an app by ID (e.g., Battery Diag)
curl -X POST http://192.168.1.100:8080/api/apps/launch \
  -H "Content-Type: application/json" \
  -d '{"app_id": "battery-diag"}'

# Stop a running app
curl -X POST http://192.168.1.100:8080/api/apps/stop \
  -H "Content-Type: application/json" \
  -d '{"app_id": "battery-diag"}'

# Toggle radio on/off
curl -X POST http://192.168.1.100:8080/api/radio/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Set radio frequency (433 MHz)
curl -X POST http://192.168.1.100:8080/api/radio/frequency \
  -H "Content-Type: application/json" \
  -d '{"frequency": 433000000}'

# Record Arduino button press
curl -X POST http://192.168.1.100:8080/api/event \
  -H "Content-Type: application/json" \
  -d '{
    "type": "button_press",
    "data": {"id": "power", "action": "short_click"}
  }'
```

## Running the API

### Manual Start

```bash
cd /path/to/app
python3 status_api.py --port 8080 --host 0.0.0.0
```

### Using Startup Script

```bash
./start-status-api.sh
```

### Auto-start on Boot

Add to your startup scripts or create a systemd service:

```ini
[Unit]
Description=K7BAT uConsole Status API
After=network.target

[Service]
Type=simple
User=uconsole
WorkingDirectory=/home/uconsole/app
ExecStart=/usr/bin/python3 /home/uconsole/app/status_api.py --port 8080 --host 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

## Notes

- The API runs on port 8080 by default
- It binds to `0.0.0.0` to accept connections from all interfaces (including USB OTG)
- Status data is refreshed on each GET request
- The API is thread-safe and can handle multiple concurrent requests
- CORS headers are enabled for web-based clients

## Integration with Existing App

The Status API runs alongside your existing GTK UI app:
- Use `status_api.py` for external devices (Arduino, phones, etc.)
- Keep `k7bat-uconsole-status-v2.py` for the local dashboard
- Both can access the same status data (consider shared storage for real sync)

## License

Same as main uConsole project.
