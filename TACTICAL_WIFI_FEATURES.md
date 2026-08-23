# Tactical WiFi Attack Tools Interface

## Overview

Full-screen tactical interface for WiFi security assessment tools on k7bat-uconsole-status app.

## Features

### Primary Interface (Top Band)

**Replaced "Updates" button with "WiFi Attacks" button:**
- Opens full-screen tactical interface
- Shows all WiFi attack tools in organized grid
- Displays real-time status of WiFi hardware (wlan1, MT7921AUN)

### Tactical WiFi Attack Tools Grid

#### Row 1: Passive Survey & Analysis
- **Kismet RF Survey** - Start Kismet for RF environment mapping
- **Wireshark GUI** - Launch Wireshark packet analysis GUI  
- **Tshark Capture** - Command-line packet capture tool

#### Row 2: Active WPA/WPS Attacks
- **Reaver (WPS)** - WPS PIN brute force attack tool
- **Bully (WPS)** - Alternative WPS cracking tool
- **Cowpatty (Offline)** - Offline dictionary attacks for WPA-PSK

#### Row 3: Network Infrastructure Attacks  
- **MDK4 (DoS/PenTest)** - IEEE 802.11 DoS and penetration testing
- **Hostapd (Rogue AP)** - Create rogue access points
- **Dnsmasq (Rogue DHCP)** - Rogue DHCP/DNS server

#### Row 4: Monitor Mode Control
- **Start Monitor (k7mon0)** - Creates monitor interface on wlan1
- **Stop Monitor** - Removes k7mon0 interface

#### Row 5: Firmware Analysis
- **Binwalk (Extract)** - Firmware extraction/decompression tool
- **Scapy (Packet Mani)** - Python packet manipulation library
- **PyShark (Wireshark)** - Python Wireshark integration

### Status Display

**Header Section:**
- Current status indicator ("WiFi Attack Tools Ready")
- Interface info: wlan1
- PHY info: phy1 (MT7921AUN)

## Usage

1. Launch k7bat-uconsole-status app
2. Click "Tactical WiFi" button in top band
3. Full-screen interface opens with all tools organized by category
4. Click any tool to launch it
5. Monitor mode controls for creating/removing k7mon0 interface
6. Close button returns to main dashboard

## Tactical Workflow

### Passive Assessment
1. Start Kismet for RF survey
2. Analyze networks with Wireshark
3. Capture packets with Tshark

### Active Testing (Authorized Networks Only)
1. Create monitor mode: Click "Start Monitor"
2. Launch Reaver/Bully for WPS attacks
3. Use Cowpatty for offline dictionary attacks
4. Deploy MDK4 for DoS testing
5. Set up rogue infrastructure with Hostapd/Dnsmasq

### Firmware Analysis
1. Extract firmware with Binwalk
2. Analyze packets with Scapy
3. Integrate Wireshark data with PyShark

## Implementation Details

**File Modified:** `app/k7bat-uconsole-status.py`

**New Methods:**
- `open_tactical_wifi_attacks_fullscreen()` - Main interface builder
- `launch_kismet()` - Launch Kismet RF survey
- `launch_wireshark()` - Launch Wireshark GUI  
- `launch_tshark()` - Tshark capture tool info
- `launch_tool(tool_name)` - Generic tool launcher with terminal
- `launch_python_tool(tool_name)` - Python security tools launcher
- `launch_monitor_mode()` - Create k7mon0 monitor interface
- `stop_monitor_mode()` - Remove k7mon0 interface

**UI Components:**
- Full-screen window (1024x600 minimum)
- 5-row grid layout with categorized tools
- Status header with hardware info
- Color-coded buttons with icons
- Close button for exit

## Hardware Integration

**Target Device:** ClockworkPi uConsole CM5 + HackerGadgets AC1200
**Wireless Chipset:** MediaTek MT7921AUN (wlan1, phy1)
**Monitor Mode Interface:** k7mon0 (created via k7bat-monitor-start)

## Security Notes

⚠️ **Use only on networks and RF environments you own or are explicitly authorized to assess.**

All tools launched in this interface should comply with local laws and regulations regarding wireless security testing.
