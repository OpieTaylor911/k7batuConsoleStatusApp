#!/usr/bin/env python3
"""
Reaver WPS Attack Tool GUI

This module provides a GTK3 UI for managing and executing reaver WPS attack tools.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, Pango

import os
import sys
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict

# User app directory
USER_APP_DIR = Path("/home/bcaddy/uconsole-k7bat")

# Debug log file location
DEBUG_LOG = USER_APP_DIR / "reaver_debug.log"

# Add app directory to path for imports
APP_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(APP_DIR))

# Import plugin base class
from plugin_base import PluginBase

def debug_log(message: str):
    """Write debug message to log file with timestamp."""
    try:
        timestamp = time.strftime("%H:%M:%S")
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        pass

def get_available_interfaces() -> List[str]:
    """Get list of available wireless interfaces."""
    try:
        result = subprocess.run(
            ["iwconfig"],
            capture_output=True,
            text=True
        )
        debug_log(f"[DEBUG] iwconfig stdout: {result.stdout[:500]}")
        interfaces = []
        for line in result.stdout.split('\n'):
            if 'IEEE 802.11' in line:
                interface = line.split()[0]
                interfaces.append(interface)
        debug_log(f"[DEBUG] Found regular interfaces: {interfaces}")
        return interfaces
    except Exception as e:
        debug_log(f"Error getting interfaces: {e}")
        return []

def get_monitor_interfaces() -> List[str]:
    """Get list of monitor mode interfaces."""
    try:
        result = subprocess.run(
            ["iwconfig"],
            capture_output=True,
            text=True
        )
        debug_log(f"[DEBUG] iwconfig for monitor: {result.stdout[:500]}")
        interfaces = []
        for line in result.stdout.split('\n'):
            if 'Mode:Monitor' in line:
                interface = line.split()[0]
                interfaces.append(interface)
        debug_log(f"[DEBUG] Found monitor interfaces: {interfaces}")
        return interfaces
    except Exception as e:
        debug_log(f"Error getting monitor interfaces: {e}")
        return []


class ReaverWindow(Gtk.Window):
    """Reaver WPS Attack Tool GTK3 UI window."""
    
    def __init__(self, app_instance=None):
        """
        Initialize the Reaver window.
        
        Args:
            app_instance: The main App window instance (optional)
        """
        debug_log("[DEBUG] ReaverWindow.__init__ starting...")
        super().__init__(title="Reaver WPS Attack Tool")
        self.app = app_instance
        self.set_default_size(800, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        
        # UI state
        self.target_bssid = ""
        self.target_interface = ""
        self.is_running = False
        self.process = None
        self.custom_pin = ""  # Initialize custom PIN attribute
        
        # Create main layout
        debug_log("[DEBUG] Creating UI...")
        self._create_ui()
        
        debug_log("[DEBUG] ReaverWindow initialization complete")
    
    def _create_ui(self):
        """Create the user interface with split layout."""
        # Main horizontal container (split screen)
        main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        main_hbox.set_border_width(6)
        self.add(main_hbox)
        
        # Left side: Controls and settings
        left_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left_vbox.set_size_request(350, -1)
        left_vbox.set_border_width(6)
        main_hbox.pack_start(left_vbox, False, False, 0)
        
        # Right side: Console output (expands to fill remaining space)
        right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right_vbox.set_vexpand(True)
        right_vbox.set_border_width(6)
        main_hbox.pack_start(right_vbox, True, True, 0)
        
        # Title
        title_label = Gtk.Label(label="<b>Reaver WPS Attack Tool</b>")
        title_label.set_use_markup(True)
        title_label.set_alignment(0.5, 0.5)
        left_vbox.pack_start(title_label, False, False, 0)
        
        # Close button (top right of controls section)
        close_btn = Gtk.Button(label="✕ Close")
        close_btn.connect("clicked", self.on_close)
        left_vbox.pack_start(close_btn, False, False, 0)
        
        # Target BSSID section
        bssid_frame = Gtk.Frame(label="Target Access Point")
        bssid_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bssid_box.set_border_width(6)
        
        bssid_label = Gtk.Label(label="BSSID:")
        self.bssid_combo = Gtk.ComboBoxText()
        self.bssid_combo.set_entry_text_column(0)
        self.bssid_combo.append_text("00:00:00:00:00:00 - APBOB")
        self.bssid_combo.connect("changed", self._on_bssid_changed)
        
        # Scan APs button
        scan_ap_btn = Gtk.Button(label="Scan")
        scan_ap_btn.connect("clicked", self._on_scan_ap_clicked)
        
        bssid_box.pack_start(bssid_label, False, False, 0)
        bssid_box.pack_start(self.bssid_combo, True, True, 0)
        bssid_box.pack_start(scan_ap_btn, False, False, 0)
        bssid_frame.add(bssid_box)
        left_vbox.pack_start(bssid_frame, False, False, 0)
        
        # Interface section
        interface_frame = Gtk.Frame(label="Wireless Interface")
        interface_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        interface_box.set_border_width(6)
        
        interface_label = Gtk.Label(label="Interface:")
        self.interface_combo = Gtk.ComboBoxText()
        self._populate_interfaces()
        
        interface_box.pack_start(interface_label, False, False, 0)
        interface_box.pack_start(self.interface_combo, True, True, 0)
        interface_frame.add(interface_box)
        left_vbox.pack_start(interface_frame, False, False, 0)
        
        # Warning about sudo requirements
        warning_label = Gtk.Label(label="<i>Note: Reaver requires root privileges for PCAP operations. Ensure the user is in the 'netdev' group or has sudo access.</i>")
        warning_label.set_use_markup(True)
        warning_label.set_alignment(0, 0.5)
        warning_label.set_line_wrap(True)
        left_vbox.pack_start(warning_label, False, False, 4)
        
        # PIN section
        pin_frame = Gtk.Frame(label="WPS PIN (Optional)")
        pin_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pin_box.set_border_width(6)
        
        self.use_default_pin = Gtk.RadioButton.new_with_label_from_widget(None, "Use default")
        self.use_custom_pin = Gtk.RadioButton.new_with_label_from_widget(self.use_default_pin, "Custom PIN:")
        self.custom_pin_entry = Gtk.Entry()
        self.custom_pin_entry.set_placeholder_text("12345670")
        self.custom_pin_entry.set_sensitive(False)
        
        self.use_default_pin.connect("toggled", self._on_pin_mode_toggled, False)
        self.use_custom_pin.connect("toggled", self._on_pin_mode_toggled, True)
        self.custom_pin_entry.connect("changed", lambda e: setattr(self, 'custom_pin', e.get_text()))
        
        pin_box.pack_start(self.use_default_pin, False, False, 0)
        pin_box.pack_start(self.use_custom_pin, False, False, 0)
        pin_box.pack_start(self.custom_pin_entry, True, True, 0)
        pin_frame.add(pin_box)
        left_vbox.pack_start(pin_frame, False, False, 0)
        
        # Options section
        options_frame = Gtk.Frame(label="Attack Options")
        options_grid = Gtk.Grid()
        options_grid.set_column_spacing(8)
        options_grid.set_row_spacing(6)
        options_grid.set_border_width(6)
        
        self.check_fixed_channel = Gtk.CheckButton(label="Fixed Channel (no hopping)")
        self.check_5ghz = Gtk.CheckButton(label="5GHz mode")
        self.check_ignore_locks = Gtk.CheckButton(label="Ignore locks")
        self.check_pixiedust = Gtk.CheckButton(label="Pixie Dust attack")
        
        options_grid.attach(self.check_fixed_channel, 0, 0, 1, 1)
        options_grid.attach(self.check_5ghz, 1, 0, 1, 1)
        options_grid.attach(self.check_ignore_locks, 0, 1, 1, 1)
        options_grid.attach(self.check_pixiedust, 1, 1, 1, 1)
        
        options_frame.add(options_grid)
        left_vbox.pack_start(options_frame, False, False, 0)
        
        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_homogeneous(True)
        
        self.start_button = Gtk.Button(label="Start Attack")
        self.start_button.connect("clicked", self._on_start_clicked)
        self.start_button.get_style_context().add_class("suggested-action")
        
        self.stop_button = Gtk.Button(label="Stop")
        self.stop_button.connect("clicked", self._on_stop_clicked)
        self.stop_button.set_sensitive(False)
        
        button_box.pack_start(self.start_button, True, True, 0)
        button_box.pack_start(self.stop_button, True, True, 0)
        left_vbox.pack_start(button_box, False, False, 0)
        
        # Console output section
        console_frame = Gtk.Frame(label="Attack Status")
        right_vbox.pack_start(console_frame, True, True, 0)
        
        self.status_label = Gtk.Label(label="Ready to start")
        self.status_label.set_alignment(0.5, 0.5)
        
        # Log output text view with expand button
        console_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        
        # Console header with expand button
        console_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        status_title_label = Gtk.Label(label="Attack Status:")
        status_title_label.set_use_markup(True)
        status_title_label.set_alignment(0, 0.5)
        
        self.console_expander_button = Gtk.Button(label="▼ Expand Console")
        self.console_expander_button.connect("clicked", self._on_console_expand)
        console_header.pack_start(status_title_label, False, False, 0)
        console_header.pack_end(self.console_expander_button, False, False, 0)
        
        scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window = scrolled_window  # Store as instance variable for expand/collapse
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_vexpand(True)
        
        self.log_text_view = Gtk.TextView()
        self.log_text_view.set_editable(False)
        self.log_buffer = self.log_text_view.get_buffer()
        
        scrolled_window.add(self.log_text_view)
        
        console_container.pack_start(console_header, False, False, 0)
        console_container.pack_start(scrolled_window, True, True, 0)
        console_frame.add(console_container)
        
        debug_log("[DEBUG] UI creation complete")
    
    def _populate_interfaces(self):
        """Populate the interface combo box with available interfaces."""
        debug_log(f"[DEBUG] _populate_interfaces() called")
        interfaces = get_available_interfaces()
        monitor_interfaces = get_monitor_interfaces()
        
        debug_log(f"[DEBUG] Found {len(interfaces)} regular interfaces: {interfaces}")
        debug_log(f"[DEBUG] Found {len(monitor_interfaces)} monitor interfaces: {monitor_interfaces}")
        
        # Add monitor interfaces first (preferred for reaver)
        for iface in monitor_interfaces:
            self.interface_combo.append_text(iface)
        
        # Add regular interfaces
        for iface in interfaces:
            if iface not in monitor_interfaces:
                self.interface_combo.append_text(iface)
        
        debug_log(f"[DEBUG] Combo box items after population: {self.interface_combo.get_active_text()}")
        
        if self.interface_combo.get_active() == -1 and len(interfaces) > 0:
            self.interface_combo.set_active(0)
            debug_log(f"[DEBUG] Set active interface to 0")
    
    def _on_bssid_changed(self, combo):
        """Handle BSSID selection changes."""
        text = combo.get_active_text()
        if text:
            # Extract BSSID from "BSSID - SSID" format
            self.target_bssid = text.split(' - ')[0].strip()
    
    def _on_pin_mode_toggled(self, radio_button, is_custom):
        """Handle PIN mode toggle."""
        self.custom_pin_entry.set_sensitive(is_custom)
    
    def _on_scan_ap_clicked(self, button):
        """Scan for access points using nmcli."""
        interface = self.interface_combo.get_active_text()
        
        if not interface:
            self._show_error("Please select a wireless interface first")
            return
        
        # Show scanning status
        self.status_label.set_text(f"Scanning with {interface}...")
        self.bssid_combo.set_sensitive(False)
        
        # Run nmcli in background thread
        thread = threading.Thread(target=self._scan_access_points, args=(interface,))
        thread.daemon = True
        thread.start()
    
    def _scan_access_points(self, interface):
        """Scan for WiFi access points using nmcli."""
        try:
            result = subprocess.run(
                ["nmcli", "device", "wifi", "list", "ifname", interface],
                capture_output=True,
                text=True
            )
            
            debug_log(f"[DEBUG] nmcli output: {result.stdout[:500]}")
            aps = []
            
            # Parse tabular output - each line is one AP
            lines = result.stdout.strip().split('\n')
            
            # Skip header line
            for i, line in enumerate(lines):
                if i == 0:  # Skip header
                    continue
                    
                if not line.strip():
                    continue
                
                # Split by whitespace to get columns
                parts = line.split()
                
                # Handle the * marker on some lines (fields=10 vs fields=9)
                # When first field is '*', BSSID is at index 1, SSID at index 2
                # Otherwise, BSSID is at index 0, SSID at index 1
                if len(parts) >= 2:
                    if parts[0] == '*':
                        bssid = parts[1]
                        ssid = parts[2] if len(parts) > 2 else ""
                    else:
                        bssid = parts[0]
                        ssid = parts[1] if len(parts) > 1 else ""
                    
                    # Skip entries with empty BSSID and validate MAC format
                    if bssid and len(bssid) == 17 and ':' in bssid:
                        aps.append((bssid, ssid))
            
            debug_log(f"[DEBUG] Found {len(aps)} access points")
            
            # Update UI on main thread
            GLib.idle_add(self._populate_ap_list, aps)
            
        except Exception as e:
            debug_log(f"Scan error: {e}")
            GLib.idle_add(lambda: self._show_error(f"Scan failed: {str(e)}"))
    
    def _populate_ap_list(self, ap_list):
        """Populate BSSID combo box with found access points."""
        # Clear current entries
        self.bssid_combo.remove_all()
        
        if not ap_list:
            self.bssid_combo.append_text("00:00:00:00:00:00 - APBOB")
            self.status_label.set_text("No access points found")
        else:
            # Populate combo box with BSSID - SSID format
            for bssid, ssid in ap_list:
                display_text = f"{bssid} - {ssid}" if ssid else bssid
                self.bssid_combo.append_text(display_text)
            
            # Select the first entry by default
            if len(ap_list) > 0:
                self.bssid_combo.set_active(0)
            
            self.status_label.set_text(f"Found {len(ap_list)} access point(s)")
        
        # Re-enable BSSID combo box
        self.bssid_combo.set_sensitive(True)
    
    def _log_output(self, text: str):
        """Add text to the log buffer."""
        GLib.idle_add(self._do_log, text)
    
    def _do_log(self, text: str):
        """Actually update the log buffer (called from main thread)."""
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, text)
        # Auto-scroll to bottom
        end_iter = self.log_buffer.get_end_iter()
        self.log_text_view.scroll_to_iter(end_iter, 0.0, True, 0.0, 1.0)
        return False
    
    def _on_start_clicked(self, button):
        """Handle start button click."""
        bssid = self.target_bssid.strip()
        interface = self.interface_combo.get_active_text()
        
        if not bssid:
            self._show_error("Please enter a target BSSID")
            return
        
        if not interface:
            self._show_error("Please select an interface")
            return
        
        # Validate BSSID format
        import re
        if not re.match(r'^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$', bssid):
            self._show_error("Invalid BSSID format. Use format: 00:11:22:33:44:55")
            return
        
        # Start reaver in separate thread
        self.is_running = True
        self.start_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        self.status_label.set_text("Starting attack...")
        
        thread = threading.Thread(target=self._run_reaver, args=(bssid, interface))
        thread.daemon = True
        thread.start()
    
    def _run_reaver(self, bssid: str, interface: str):
        """Run reaver command in background."""
        # Use sudo for reaver to get PCAP permissions
        cmd = ["sudo", "reaver", "-i", interface, "-b", bssid]
        
        # Add PIN if specified
        custom_pin_entry_text = self.custom_pin_entry.get_text().strip()
        if custom_pin_entry_text:
            cmd.extend(["-p", custom_pin_entry_text])
        
        # Add options
        if self.check_fixed_channel.get_active():
            cmd.append("-f")
        if self.check_5ghz.get_active():
            cmd.append("-5")
        if self.check_ignore_locks.get_active():
            cmd.append("-L")
        if self.check_pixiedust.get_active():
            cmd.append("-K")
        
        # Add verbose flag for better output
        cmd.append("-vv")
        
        debug_log(f"[DEBUG] Running command: {' '.join(cmd)}")
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Read output line by line
            for line in self.process.stdout:
                if line:
                    self._log_output(line)
            
            return_code = self.process.wait()
            debug_log(f"[DEBUG] Reaver exited with code: {return_code}")
            
            GLib.idle_add(self._on_attack_complete, return_code)
            
        except Exception as e:
            error_msg = f"Error running reaver: {str(e)}\n"
            debug_log(error_msg)
            self._log_output(error_msg)
            GLib.idle_add(self._on_attack_complete, -1)
    
    def _on_attack_complete(self, return_code):
        """Handle attack completion."""
        self.is_running = False
        self.start_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)
        
        if return_code == 0:
            self.status_label.set_text("Attack completed successfully!")
            self._log_output("\n=== Attack Completed Successfully ===\n")
        else:
            self.status_label.set_text(f"Attack exited with code {return_code}")
    
    def _on_stop_clicked(self, button):
        """Handle stop button click."""
        if self.process and self.is_running:
            try:
                self.process.terminate()
                self._log_output("\n=== Attack Stopped by User ===\n")
                self.is_running = False
                self.start_button.set_sensitive(True)
                self.stop_button.set_sensitive(False)
                self.status_label.set_text("Attack stopped")
            except Exception as e:
                debug_log(f"Error stopping process: {e}")
    
    def _on_console_expand(self, button):
        """Toggle console expand/collapse."""
        if self.console_expander_button.get_label() == "▼ Expand Console":
            # Collapse - hide scrolled window
            self.scrolled_window.hide()
            self.console_expander_button.set_label("▲ Collapse Console")
        else:
            # Expand - show scrolled window
            self.scrolled_window.show_all()
            self.console_expander_button.set_label("▼ Expand Console")
    
    def on_close(self, button):
        """Close the window."""
        self.destroy()
    
    def _show_error(self, message: str):
        """Show error dialog."""
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=0,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()


def main():
    """Main entry point for standalone testing."""
    debug_log("[DEBUG] ReaverWindow main() starting...")
    
    window = ReaverWindow()
    window.connect("destroy", Gtk.main_quit)
    window.maximize()  # Maximize window (works better than fullscreen)
    window.show_all()
    
    debug_log("[DEBUG] Starting GTK main loop...")
    Gtk.main()
    debug_log("[DEBUG] GTK main loop ended")


if __name__ == "__main__":
    main()
