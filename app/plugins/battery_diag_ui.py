#!/usr/bin/env python3
"""
Battery Diagnostic Tool for uConsole Status App

Provides in-depth battery diagnostics including:
- Charge/discharge status
- Power draw analysis
- Battery health metrics
- System power consumption breakdown
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango, Gdk
from pathlib import Path
import time
import os

APP_DIR = Path(__file__).resolve().parent


def get_battery_info():
    """Get detailed battery information from sysfs."""
    battery_data = {}
    
    for p in Path("/sys/class/power_supply").glob("*"):
        try:
            if (p / "type").read_text().strip().lower() == "battery":
                name = p.name
                capacity = int((p / "capacity").read_text().strip())
                status = (p / "status").read_text().strip()
                
                # Get additional metrics if available
                voltage = None
                current = None
                power = None
                charge_full = None
                charge_design = None
                
                try:
                    voltage = int((p / "voltage_now").read_text().strip()) / 1_000_000  # Convert to V
                except: pass
                
                try:
                    current_raw = (p / "current_now").read_text().strip()
                    current = int(current_raw) / 1_000_000  # Convert to A
                except: pass
                
                try:
                    power_raw = (p / "power_now").read_text().strip()
                    power = int(power_raw) / 1_000_000  # Convert to W
                except: pass
                
                try:
                    charge_full = int((p / "charge_full").read_text().strip())
                except: pass
                
                try:
                    charge_design = int((p / "charge_design_capacity").read_text().strip())
                except: pass
                
                battery_data[name] = {
                    "name": name,
                    "capacity": capacity,
                    "status": status,
                    "voltage_v": voltage,
                    "current_a": current,
                    "power_w": power,
                    "charge_full_mah": charge_full,
                    "charge_design_mah": charge_design,
                }
            elif (p / "type").read_text().strip().lower() == "mains":
                # AC adapter information
                name = p.name
                online = (p / "online").read_text().strip()
                
                try:
                    voltage = int((p / "voltage_now").read_text().strip()) / 1_000_000 if (p / "voltage_now").exists() else None
                except: voltage = None
                
                try:
                    current = int((p / "current_now").read_text().strip()) / 1_000_000 if (p / "current_now").exists() else None
                except: current = None
                
                battery_data[f"ac_{name}"] = {
                    "name": f"AC Adapter ({name})",
                    "type": "ac_adapter",
                    "online": online == "1",
                    "voltage_v": voltage,
                    "current_a": current,
                    "power_w": round((voltage or 0) * (current or 0), 2),
                }
        except Exception as e:
            pass
    
    return battery_data


def get_system_power_info():
    """Get system-level power information."""
    system_info = {}
    
    # Check AIO V2 status if available
    aio_path = Path("/sys/class/hwmon")
    if aio_path.exists():
        for hwmon in aio_path.glob("hwmon*"):
            try:
                name = (hwmon / "name").read_text().strip()
                if "aio" in name.lower() or "gpio" in name.lower():
                    # Look for power-related sensors
                    system_info["aio_detected"] = True
                    
                    # Try to get GPIO-based power readings if available
                    for sensor in hwmon.glob("input*"):
                        try:
                            label = (sensor / "label").read_text().strip()
                            value = (sensor / "in_input").read_text().strip()
                            system_info[f"gpio_{label}"] = f"{value}V"
                        except: pass
            except: pass
    
    return system_info


def calculate_battery_health(battery_data):
    """Calculate battery health percentage based on design vs full capacity."""
    for name, data in battery_data.items():
        # Skip AC adapters - they don't have charge_full_mah or charge_design_mah
        if data.get("type") == "ac_adapter":
            data["health_pct"] = None
            continue
        
        # Check if we have the required fields
        charge_full = data.get("charge_full_mah")
        charge_design = data.get("charge_design_mah")
        
        if charge_full and charge_design:
            health = (charge_full / charge_design) * 100
            data["health_pct"] = round(health, 1)
        else:
            # Health not available, show N/A
            data["health_pct"] = None
    
    return battery_data


def get_usb_power_draw():
    """Get USB port power draw information."""
    details = []
    
    # Check for USB devices and their power consumption
    try:
        import subprocess
        result = subprocess.run(["lsusb", "-v"], capture_output=True, text=True, timeout=5)
        usb_devices = result.stdout
        
        # Parse USB device power info
        current_power = None
        device_name = None
        
        for line in usb_devices.splitlines():
            if "idVendor" in line and "idProduct" in line:
                # Extract vendor and product IDs
                parts = line.strip().split()
                if len(parts) >= 4:
                    vendor = parts[1]
                    product = parts[3]
                    device_name = f"USB Device ({vendor}:{product})"
            elif "MaxPower" in line:
                try:
                    power_ma = int(line.split("=")[1].strip().replace("mA", ""))
                    if device_name and current_power is None:
                        details.append(f"{device_name}: {power_ma}mA")
                        current_power = power_ma
                except: pass
    
    except Exception as e:
        # Fallback: try reading from sysfs USB power directories
        try:
            usb_path = Path("/sys/bus/usb/devices")
            if usb_path.exists():
                for dev_dir in usb_path.glob("*/power"):
                    try:
                        if (dev_dir / "autosuspend_delay_ms").exists():
                            # Get device info
                            parent = dev_dir.parent
                            if (parent / "idVendor").exists():
                                vendor = (parent / "idVendor").read_text().strip()
                                product = (parent / "idProduct").read_text().strip()
                                if (parent / "speed").exists():
                                    speed = (parent / "speed").read_text().strip()
                                    details.append(f"USB {speed}M: Vendor={vendor}, Product={product}")
                    except: pass
        except: pass
    
    return details


def get_power_draw_details():
    """Get detailed power consumption breakdown."""
    details = []
    
    # CPU power estimation (based on load and frequency)
    try:
        with open("/sys/devices/cpu/cpufreq/scaling_cur_freq", "r") as f:
            freq_mhz = int(f.read().strip()) / 1000
            details.append(f"CPU Frequency: {freq_mhz:.1f} GHz")
    except: pass
    
    # Display power (estimate based on backlight if available)
    try:
        for backlight in Path("/sys/class/backlight").glob("*"):
            brightness = int((backlight / "brightness").read_text().strip())
            max_brightness = int((backlight / "max_brightness").read_text().strip())
            pct = (brightness / max_brightness) * 100
            details.append(f"Display Brightness: {pct:.0f}%")
            break
    except: pass
    
    return details


class BatteryDiagWindow(Gtk.Window):
    """Full-screen battery diagnostic window."""
    
    def __init__(self, parent_app=None):
        Gtk.Window.__init__(self, title="Battery Diagnostic Tool")
        self.set_default_size(800, 600)
        
        # Set transient for parent if provided
        if parent_app:
            self.set_transient_for(parent_app)
        
        self.connect("destroy", lambda w: None)  # Don't quit main loop on destroy
        
        # Make it full screen
        self.fullscreen()
        
        # Set dark theme for better visibility in tactical situations
        css_provider = Gtk.CssProvider()
        css = """
        .battery-panel {
            background-color: #1a1a2e;
            color: #eee;
            border-radius: 8px;
            padding: 10px;
        }
        .metric-label {
            font-weight: bold;
            font-size: 14px;
            color: #00d4ff;
        }
        .metric-value {
            font-family: monospace;
            font-size: 16px;
            color: #fff;
        }
        .status-good { color: #00ff88; }
        .status-warning { color: #ffaa00; }
        .status-critical { color: #ff4444; }
        .section-title {
            font-weight: bold;
            font-size: 18px;
            margin-top: 15px;
            margin-bottom: 10px;
            color: #fff;
            border-bottom: 1px solid #333;
            padding-bottom: 5px;
        }
        """
        css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        
        # Header
        header = Gtk.Label(label="[BATTERY] Battery Diagnostic Tool")
        header.get_style_context().add_class("section-title")
        header.set_xalign(0)
        main_box.pack_start(header, False, False, 0)
        
        # Batteries section - plain text display
        batteries_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.batteries_label = Gtk.Label(label="Batteries:")
        self.batteries_label.get_style_context().add_class("section-title")
        self.batteries_label.set_xalign(0)
        batteries_box.pack_start(self.batteries_label, False, False, 0)
        
        # Plain text label for battery info
        self.battery_text = Gtk.Label(label="")
        self.battery_text.set_line_wrap(True)
        self.battery_text.set_xalign(0)
        self.battery_text.modify_font(Pango.FontDescription("Monospace 12"))
        batteries_box.pack_start(self.battery_text, True, True, 0)
        main_box.pack_start(batteries_box, False, False, 0)
        
        # Power draw section - plain text display
        power_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.power_label = Gtk.Label(label="Power Consumption:")
        self.power_label.get_style_context().add_class("section-title")
        self.power_label.set_xalign(0)
        power_box.pack_start(self.power_label, False, False, 0)
        
        # Plain text label for power info
        self.power_text = Gtk.Label(label="")
        self.power_text.set_line_wrap(True)
        self.power_text.set_xalign(0)
        self.power_text.modify_font(Pango.FontDescription("Monospace 12"))
        power_box.pack_start(self.power_text, True, True, 0)
        main_box.pack_start(power_box, False, False, 0)
        
        # System details section
        system_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.system_label = Gtk.Label(label="System Details:")
        self.system_label.get_style_context().add_class("section-title")
        self.system_label.set_xalign(0)
        system_box.pack_start(self.system_label, False, False, 0)
        self.system_text = Gtk.Label(label="")
        self.system_text.set_line_wrap(True)
        self.system_text.set_xalign(0)
        system_box.pack_start(self.system_text, True, True, 0)
        main_box.pack_start(system_box, True, True, 0)
        
        # Refresh button
        refresh_btn = Gtk.Button(label="Refresh Data")
        refresh_btn.connect("clicked", self.on_refresh)
        refresh_btn.set_margin_top(15)
        
        # Add icon to refresh button
        try:
            from gi.repository import GdkPixbuf
            app_dir = Path(__file__).resolve().parent.parent
            icons_dir = app_dir / "icons"
            refresh_icon_path = icons_dir / "battery.svg"
            if refresh_icon_path.exists():
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(refresh_icon_path), width=16, height=16, preserve_aspect_ratio=True)
                image = Gtk.Image.new_from_pixbuf(pix)
                refresh_btn.set_image(image)
                refresh_btn.set_image_position(Gtk.PositionType.LEFT)
        except Exception:
            pass
        
        main_box.pack_end(refresh_btn, False, False, 0)
        
        # Close button (small, in corner) with X icon
        close_btn = Gtk.Button(label="Close")
        close_btn.connect("clicked", lambda w: self.destroy())
        close_btn.set_halign(Gtk.Align.END)
        close_btn.set_valign(Gtk.Align.START)
        close_btn.set_margin_top(10)
        close_btn.set_margin_end(10)
        
        # Add X icon to close button
        try:
            from gi.repository import GdkPixbuf
            app_dir = Path(__file__).resolve().parent.parent
            icons_dir = app_dir / "icons"
            close_icon_path = icons_dir / "power.svg"
            if close_icon_path.exists():
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(close_icon_path), width=16, height=16, preserve_aspect_ratio=True)
                image = Gtk.Image.new_from_pixbuf(pix)
                close_btn.set_image(image)
                close_btn.set_image_position(Gtk.PositionType.LEFT)
        except Exception:
            pass
        
        main_box.pack_end(close_btn, False, False, 0)
        
        # Add to window
        self.add(main_box)
        
        # Show all widgets
        self.show_all()
        
        # Initial data load
        GLib.timeout_add_seconds(1, self.update_data)
    
    def update_data(self):
        """Update all battery and power data."""
        try:
            import time
            log_file = "/tmp/battery_diag.log"
            
            battery_data = get_battery_info()
            battery_data = calculate_battery_health(battery_data)
            
            # Build plain text battery display
            battery_lines = []
            for name, data in battery_data.items():
                if data.get("type") == "ac_adapter":
                    continue
                
                battery_lines.append(f"=== {name} ===")
                battery_lines.append(f"  Capacity: {data['capacity']}%")
                
                status_value = data.get("status", "Unknown")
                battery_lines.append(f"  Status: {status_value}")
                
                voltage_val = data["voltage_v"] if data["voltage_v"] else 0
                current_val = data["current_a"] if data["current_a"] else 0
                power_val = data["power_w"] if data["power_w"] else 0
                
                battery_lines.append(f"  Voltage: {voltage_val:.2f}V")
                battery_lines.append(f"  Current: {abs(current_val):.2f}A")
                battery_lines.append(f"  Power: {abs(power_val):.2f}W")
                
                if data["health_pct"] is not None:
                    battery_lines.append(f"  Health: {data['health_pct']}%")
                
                battery_lines.append("")
            
            if not battery_lines:
                battery_lines = ["No batteries detected", ""]
            
            self.battery_text.set_text("\n".join(battery_lines))
            
            # Build plain text power display
            total_power = sum(d["power_w"] for d in battery_data.values() if d.get("power_w") and d.get("type") != "ac_adapter")
            
            power_lines = []
            power_lines.append(f"Total Power Draw: {abs(total_power):.2f}W")
            power_lines.append("")
            
            # USB power details
            usb_power = get_usb_power_draw()
            if usb_power:
                power_lines.append("USB Devices:")
                for device in usb_power:
                    power_lines.append(f"  {device}")
            
            self.power_text.set_text("\n".join(power_lines))
            
            # System details
            system_info = []
            for name, data in battery_data.items():
                if data.get("type") == "ac_adapter":
                    continue
                    
                status_value = data.get("status", "Unknown")
                status_text = f"{status_value} at {data['capacity']}%"
                if data["health_pct"]:
                    status_text += f" (Health: {data['health_pct']}%)"
                system_info.append(f"[BATTERY] {name}: {status_text}")
            
            any_charging = any(d.get("status", "Unknown") == "Charging" for d in battery_data.values() if d.get("type") != "ac_adapter")
            if any_charging:
                system_info.append("[CHARGING] Battery is charging")
            elif battery_data:
                discharging = [d for d in battery_data.values() if d.get("status", "Unknown") == "Discharging" and d.get("type") != "ac_adapter"]
                if discharging:
                    system_info.append("[DISCHARGING] Battery is discharging")
            
            self.system_text.set_text("\n".join(system_info))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.battery_text.set_text(error_msg)
            self.power_text.set_text("")
            self.system_text.set_text(error_msg)
        
        return GLib.SOURCE_CONTINUE
    
    def on_refresh(self, button):
        """Manual refresh button handler."""
        self.update_data()


    """Main entry point."""
    # This module is designed to be imported by the main app, not run standalone.
    # The main app handles GTK initialization and window management.
