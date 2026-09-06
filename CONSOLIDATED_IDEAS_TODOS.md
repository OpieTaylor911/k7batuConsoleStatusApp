# K7BAT Consolidated Ideas & Todos
**Last Updated:** 2026-09-06  
**Purpose:** Complete overview of all sidekick and app projects across workspaces

---

## 📋 OVERVIEW

This document consolidates all active ideas, todos, and project directions for:
1. **k7batuConsoleStatusApp** - Main uConsole dashboard application
2. **tabler-icons-main** - Icon library (standalone)
3. **k7bat_sidekick** - ESP32 firmware projects for multiple boards

---

## 🎯 MAIN APP TODO LIST (Priority Order)

### ✅ COMPLETED (v1.0.0 - v2.0.1)

| Feature | Status | Details |
|---------|--------|---------|
| Smart Alert Engine | ✅ Complete | Configurable thresholds for CPU/RAM/disk/battery/GPS/Wi-Fi |
| One-Tap Radio Profiles | ✅ Complete | Mobile/Base/Emergency/Custom presets with persistence |
| Service Health Center | ✅ Complete | Live status and restart controls for gpsd, bluetooth, readsb |
| Plugin Button Row | ✅ Complete | Custom plugin launchers via JSON configuration |
| Mission Recorder | ✅ Complete | Session telemetry capture and post-run summaries |
| GitHub Release Check | ✅ Complete | Auto-detect new versions with popup notifications |
| Advanced GPS Quality View | ✅ Complete | Sats-used, DOP (HDOP/VDOP/PDOP), confidence score, trend history |
| Tactical Connectivity Pane | ✅ Complete | Scan/connect/disconnect/forget helpers, failover status |
| Touch Mode UI | ✅ Complete | CSS classes for larger buttons and high contrast themes |
| Secure Remote Assist | ⚠️ Partial | Bundle generation complete; upload token flow remaining |
| Auto-Update & Rollback | ✅ Complete | Backup/restore workflow with channel selection |
| Snapshot Manager | ✅ Complete | Named save/load/delete with tags and retention policy |
| Hak5 Pineapple Loader | ✅ Complete | Module loading infrastructure in `app/plugins/pineapple_loader.py` |
| Hak5 Pineapple UI | ✅ Complete | GTK3 module management dialog |

### 🔄 PARTIALLY COMPLETE

| Feature | Current State | Remaining Work |
|---------|---------------|----------------|
| Touch-First Field UI Mode | CSS classes implemented | Final UI polish and testing |
| WiFiPineapple Interface | Separate attack windows exist | Unified Pineapple-style interface with categories |
| Secure Remote Assist | Diagnostics bundle working | Tokenized upload endpoint integration |

### 🚧 NOT STARTED / PENDING

#### High Priority (Current Focus)
1. **Secure Remote Assist - Upload Token Flow**
   - Already have bundle generation; just need upload integration
   
2. **BLE Spam Detection & Foxhunt**
   - Defensive security feature
   - Conference environment protection
   - Repository: https://github.com/ChiefGyk3D/Skid-Finder (⭐ 7 stars)
   
3. **APRS Beacon + Position Logging**
   - Field operations enhancement

#### Lower Priority / Future
4. **WiFi Pineapple Unified Interface** ⬅️ *Lower priority*
   - Current state: Separate WiFi attack windows exist (Passive Survey, Active Attacks, Network Attacks, Monitor Mode, Firmware Analysis)
   - Goal: Unified Pineapple-style interface with tool categories and quick-action buttons
   
5. **Hak5 Pineapple Modules UI Integration**
   - Scope: Add "Hak5 Pineapple Modules" button to plugin row that opens module management dialog
   - Current: Loader and UI classes created in `app/plugins/`, integrated into main App class

6. **Offline Map Panel**
   - Purpose: Navigation without internet connectivity
   - Status: Not started (larger scope project)

7. **Tactical Wi-Fi Defensive Audit**
   - Scope: Rogue AP indicators, auth/reconnect anomaly checks, WPA/PMF visibility
   - Note: Safe RF/security checks without packet injection

#### Future / Research
8. **uConsole Cloud Design Inspiration**
    - Repository: https://github.com/mikevitelli/uconsole-cloud (⭐ 5 stars)
    - Features to reference:
      - Next.js 16 App Router with Server Components
      - Tailwind CSS v4 utility-first styling
      - Live gauges with 1-second refresh
      - TUI launcher in curses format
      - WiFi Radio Mode picker for dual-radio management
      - Antenna Array monitor with RSSI visualization
      - Hardware dashboard (AIO v2 telemetry, GPS globe, Meshtastic map)
      - uconsole CLI tool (`setup`, `link`, `push`, `status`, `doctor`)
      - Self-signed TLS via nginx + mDNS at `https://uconsole.local`
      - Fallback AP mode when no known WiFi available
    - ⚠️ Note: Not directly compatible (different framework/stack)

---

## 📊 SIDEKICK ESP32 FIRMWARE PROJECTS

### Active Board Projects

| Project | Board ID | Display | Touch | Status |
|---------|----------|---------|-------|--------|
| **ESP32-S3_3.5_ST77922** | `es3c35p` | ST77922 480x320 | Capacitive | ✅ Active (v2.2.1) |
| **LilyGO T-Display-S3** | `lilygo` | ST7789 320x170 | Capacitive (CST816) | ✅ Active (v1.3.0) |
| **sidekick_black** | - | Various | Multiple | 🔄 Development |
| **heltec-e290** | `heltec_e290` | E-Ink 2.9" | None | ⚠️ Planned |
| **Hosyond_3.5_320x480** | - | ST7796 320x480 | Capacitive | ⚠️ Planned |
| **lcdwiki-ES3C35P** | - | ST77922 480x320 | Capacitive | ⚠️ Planned |

### Firmware Protocol

All boards implement the same serial API and HTTP polling:

#### Serial Commands (115200 baud)
```
GETVERSION     → VERSION=x.x.x\nBOARD=boardname
GETWIFI        → SSID=... IP=... or WIFI=NONE
GETIP          → IP=<address> or IP=NONE
GETSERVER      → SERVER=<uconsole-ip>:8080
GETSTATUS      → Status report
GETTOUCH       → Touch coordinates if available
POLL           → Request status update

SETWIFI=<ssid>\|<password>
CLEARWIFI
TOKEN=<api-key>
SERVER=<ip:port>
```

#### HTTP Polling
- Endpoint: `http://<uconsole>:8080/api/sidekick`
- Interval: 2-5 seconds
- Response: Semicolon-delimited status packet

Example response:
```
SDR=X;GPS=G;NET=R;AIO=X;BAT=G;SDR+=X;ADSB=G;GPSD=G;VNC=X;
READ=G;TAR=G;BT=G;TEMP=G;PWR=G;SYS=OK;
```

#### Indicator States
| Code | Meaning | Color |
|------|---------|-------|
| `G` | Healthy/active | Green |
| `Y` | Degraded/waiting | Yellow |
| `R` | Fault/unavailable | Red |
| `B` | Informational | Blue |
| `X` | Off/unsupported | Dark gray |

#### Indicator Keys
- `SDR`, `LORA`, `USB`, `GPS` - AIO V2 power rails
- `BAT`, `BATPCT`, `CHG` - Battery status
- `NET`, `ETH`, `INTERNET` - Network connectivity
- `GPSD`, `BT`, `READ`, `TAR` - Service status
- `TEMP` - CPU temperature
- `SYS` - System text message

#### Control API (POST)
```json
{
  "target": "SDR",
  "command": "power",
  "value": "on"
}
```
Requires `Authorization: Bearer <api-key>` header.

---

## 🛠️ DEVELOPMENT PIPELINE

### Local Workspace
- **Path:** `Y:\uConsoleDev\k7batuConsoleStatusApp`
- **Target Device:** uConsole at `192.168.254.226` (SSH alias: `uconsole`)
- **Deployment Script:** `scripts/deploy-uconsole.ps1`

### VS Code Tasks
```json
{
  "uConsole: Deploy + Install + Diagnostics",
  "uConsole: Deploy + Install",
  "uConsole: Diagnostics Only"
}
```

### Local-Only Customizations (NOT in git)
- Navit map setup (`/home/bcaddy/Maps/Navit`)
- Local fallback launcher `/usr/local/bin/k7bat-gps-nav`
- Patched app installation on device

**⚠️ Warning:** Local patches will be overwritten by deploy/install. Re-apply after updates.

---

## 📁 PROJECT FILE STRUCTURE

### k7batuConsoleStatusApp
```
app/
├── k7bat-uconsole-status.py    # Main GTK3 application
├── k7bat-sidekick.py           # Sidekick status API server
├── plugins.json                # Plugin configuration
├── plugins/
│   ├── pineapple_loader.py     # Hak5 Pineapple module loader
│   ├── pineapple_ui.py         # Pineapple UI dialog
│   ├── remote_assist.py        # Diagnostics bundle generator
│   ├── wifi_assessment_loader.py
│   ├── wifi_assessment_ui.py
│   └── plugin_base.py
├── theme.css                   # GTK3 styling
└── widgets/                    # UI components

scripts/
├── deploy-uconsole.ps1         # PowerShell deployment automation
├── install.sh                  # Linux installer
├── uninstall.sh                # Uninstall script
└── ...

sidekick/
├── SideKick_Design.md          # API contract and firmware guidance
└── K7BAT_Sidekick_Preset_System_3.5in_Implementation.md

webinterface/                   # Flask web server (alternative UI)
├── server.py
└── www/

status_api.py                   # HTTP API for Arduino devices
sidekick_apikey.py              # API key generation/storage
```

### ESP32 Sidekick Firmware
Each board has its own directory with:
- `.ino` sketch file
- Display driver headers (ST77922, ST7789, etc.)
- Touch driver (ST77922_TOUCH, CST816, etc.)
- WiFi provisioning logic
- HTTP polling client

### Tabler Icons
```
icons/          # SVG icon source files
packages/       # Build outputs for multiple frameworks
  ├── icons-react/
  ├── icons-vue/
  ├── icons-svelte/
  └── ...
```

---

## 🔧 HARDWARE REQUIREMENTS

### Current uConsole Setup
- **Compute:** ClockworkPi uConsole (CM4/CM5)
- **OS:** Debian 13 (Trixie) + labwc/Wayland
- **Radio:** HackerGadgets AIO V2 + AC1200 (MT7921AUN)

### WiFi Pineapple Features (All Hardware Already Supported)
| Feature | Hardware Requirement | Status |
|---------|---------------------|--------|
| Passive Survey (Kismet) | MT7921 monitor mode | ✅ Ready |
| Rogue AP / Evil Portal | hostapd + mt7921 AP mode | ✅ Ready |
| WPA2-Enterprise Evil Twin | EAPHammer support | ✅ Ready |
| Packet Injection | aircrack-ng compatibility | ✅ Ready |
| Wifite2 Automation | Python framework only | ⚠️ Not implemented |

### Sidekick ESP32 Boards
All boards need:
- ESP32-S3 or ESP32-WROOM-32
- Display (ST77922, ST7789, E-Ink)
- WiFi capability
- Optional: Touch controller

---

## 📝 RECENT CHANGES (v2.0.1)

### v2.0.1 - 2026-08-31
- Rebuilt UI after v2.0.0 regression
- Full tabbed dashboard restored
- Power & Radios controls wired to `aiov2_ctl`
- Sidekick API server integration
- Serial Wi-Fi provisioning protocol
- Firmware flashing via `esptool`
- Release server integration (`index.json` → `release.json` → `manifest.json`)

### v1.2.0 - 2026-08-23
- Auto-update with rollback
- Backup/restore system
- Channel selection (stable/beta)
- Update download and installation

### v1.1.x Series
- Mission recorder
- Snapshot manager with tags
- Tactical connectivity pane
- GPS quality view enhancements
- Service health center
- Smart alert engine

---

## 🎯 NEXT BUILD PRIORITY ORDER

Based on current state and hardware readiness:

1. **WiFiPineapple Integration - Wifite2 Automated Attacks**
   - Highest value, all hardware ready
   
2. **WiFiPineapple Integration - Bettercap MITM Caplets**
   - Useful for red team operations
   
3. **Secure Remote Assist - Upload Token Flow**
   - Already have bundle generation; just need upload integration
   
4. **BLE Spam Detection & Foxhunt**
   - Defensive security feature
   - Conference environment protection
   
5. **APRS Beacon + Position Logging**
   - Field operations enhancement
   
6. **Tactical Wi-Fi Defensive Audit**
   - Security posture checks without packet injection

---

## 🔗 USEFUL LINKS

### Repositories
- Main App: `Y:\uConsoleDev\k7batuConsoleStatusApp`
- Tabler Icons: `y:\uConsoleDev\tabler-icons-main`
- Sidekick Firmware: `c:\Users\bcaddy\Documents\Arduino\k7bat_sidekick`

### External References
- Skid-Finder (BLE Foxhunt): https://github.com/ChiefGyk3D/Skid-Finder
- uConsole Cloud (design inspiration): https://github.com/mikevitelli/uconsole-cloud

### Documentation
- SideKick_Design.md: API contract and firmware protocol
- CHANGELOG.md: Complete version history
- UPDATE_FEATURE_SUMMARY.md: Auto-update implementation details
- TODO.md: Active todo list (duplicate of consolidated doc)

---

## 📌 NOTES

1. **Development Workflow:** Use VS Code tasks for PowerShell-based deployment to uConsole
2. **Local Customizations:** Navit setup is device-local and will be overwritten by updates
3. **API Authentication:** Sidekick control requires Bearer token from `.apikey` file
4. **Firmware flashing:** Setup app uses ESP Web Tools manifest format with merged binaries
5. **Touch fixes:** ST77922 boards have I2C initialization issues documented in TOUCH_FIXES_SUMMARY.md

---

*This document consolidates all project information across the K7BAT workspace.*
