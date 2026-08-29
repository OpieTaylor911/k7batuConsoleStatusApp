#!/usr/bin/env python3
"""
Wi-Fi Assessment Module UI Integration

This module provides the GTK3 UI for managing and executing Wi-Fi assessment tools.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, Pango

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

# User app directory
USER_APP_DIR = Path("/home/bcaddy/uconsole-k7bat")

# Debug log file location
DEBUG_LOG = USER_APP_DIR / "wifi_assessment_debug.log"

# Add app directory to path for imports
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

# Use absolute import after path is set
try:
    from plugins.wifi_assessment_loader import WifiAssessmentLoader
except ImportError:
    from wifi_assessment_loader import WifiAssessmentLoader

def debug_log(message: str):
    """Write debug message to log file with timestamp."""
    try:
        timestamp = time.strftime("%H:%M:%S")
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        pass  # Don't let logging fail the app

def clear_debug_log():
    """Clear debug log at startup."""
    try:
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_LOG, "w") as f:
            f.write("")
    except Exception as e:
        pass


class WifiAssessmentWindow(Gtk.Window):
    """Wi-Fi Assessment GTK3 UI window."""
    
    def __init__(self, app_instance=None):
        """
        Initialize the Wi-Fi assessment window.
        
        Args:
            app_instance: The main App window instance (optional)
        """
        try:
            debug_log("[DEBUG] WifiAssessmentWindow.__init__ starting...")
            super().__init__(title="Wi-Fi Assessment Tools")
            self.app = app_instance
            # Set full screen for better tool viewing experience
            self.fullscreen()
            self.set_default_size(1024, 768)
            self.set_position(Gtk.WindowPosition.CENTER)
            
            # Initialize loader
            debug_log("[DEBUG] WifiAssessmentWindow initializing...")
            self.loader = WifiAssessmentLoader()
            debug_log(f"[DEBUG] WifiAssessmentLoader created")
            
            # UI state
            self.tools_list = []
            self.selected_tool_id = None
            self.scan_results = []
            
            # Build UI
            self._build_ui()
            
            debug_log("[DEBUG] Calling show_all()...")
            self.show_all()
            debug_log("[DEBUG] WifiAssessmentWindow initialized successfully")
        except Exception as e:
            import traceback
            tb_str = "\n".join(traceback.format_exc().splitlines()[-10:])
            debug_log(f"[DEBUG] WifiAssessmentWindow.__init__ error: {e}\n{tb_str}")
            raise
        
    def _build_ui(self):
        """Build the main UI components."""
        # Main container using Gtk.Box (more modern than VBox/HBox)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        
        # Header
        header_label = Gtk.Label()
        header_label.set_markup("<b><big>Wi-Fi Assessment Tools</big></b>")
        header_label.set_alignment(0, 0.5)
        vbox.pack_start(header_label, False, False, 0)
        
        # Interface selector
        interface_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        interface_label = Gtk.Label("Interface:")
        self.interface_combo = Gtk.ComboBoxText()
        self.interface_combo.append_text("wlan0")
        self.interface_combo.append_text("wlan1")
        self.interface_combo.append_text("eth0")
        self.interface_combo.set_active(0)
        interface_box.pack_start(interface_label, False, False, 0)
        interface_box.pack_start(self.interface_combo, False, False, 0)
        vbox.pack_start(interface_box, False, False, 0)
        
        # Tools list
        tools_frame = Gtk.Frame(label=" Available Tools ")
        tools_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        # Scrollable list
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        
        self.tools_list_store = Gtk.ListStore(str, str)  # id, name
        self.tools_treeview = Gtk.TreeView(self.tools_list_store)
        
        renderer_id = Gtk.CellRendererText()
        column_id = Gtk.TreeViewColumn("ID", renderer_id, text=0)
        self.tools_treeview.append_column(column_id)
        
        renderer_name = Gtk.CellRendererText()
        column_name = Gtk.TreeViewColumn("Name", renderer_name, text=1)
        self.tools_treeview.append_column(column_name)
        
        self.tools_treeview.connect("cursor-changed", self.on_tool_selected)
        
        scrolled_window.add(self.tools_treeview)
        tools_box.pack_start(scrolled_window, True, True, 0)
        tools_frame.add(tools_box)
        vbox.pack_start(tools_frame, True, True, 0)
        
        # Action buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        self.btn_scan = Gtk.Button(label="Scan Networks")
        self.btn_scan.connect("clicked", self.on_scan_clicked)
        
        # Add WiFi icon to scan button
        try:
            from gi.repository import GdkPixbuf
            app_dir = Path(__file__).resolve().parent.parent
            icons_dir = app_dir / "icons"
            scan_icon_path = icons_dir / "wifi.svg"
            if scan_icon_path.exists():
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(scan_icon_path), width=16, height=16, preserve_aspect_ratio=True)
                image = Gtk.Image.new_from_pixbuf(pix)
                self.btn_scan.set_image(image)
                self.btn_scan.set_image_position(Gtk.PositionType.LEFT)
        except Exception:
            pass
        
        action_box.pack_start(self.btn_scan, False, False, 0)
        
        self.btn_execute = Gtk.Button(label="Execute Tool")
        self.btn_execute.connect("clicked", self.on_execute_clicked)
        self.btn_execute.set_sensitive(False)
        
        # Add play icon to execute button
        try:
            from gi.repository import GdkPixbuf
            app_dir = Path(__file__).resolve().parent.parent
            icons_dir = app_dir / "icons"
            execute_icon_path = icons_dir / "player-play.svg"
            if execute_icon_path.exists():
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(execute_icon_path), width=16, height=16, preserve_aspect_ratio=True)
                image = Gtk.Image.new_from_pixbuf(pix)
                self.btn_execute.set_image(image)
                self.btn_execute.set_image_position(Gtk.PositionType.LEFT)
        except Exception:
            pass
        
        action_box.pack_start(self.btn_execute, False, False, 0)
        
        self.btn_refresh = Gtk.Button(label="Refresh Tools")
        self.btn_refresh.connect("clicked", self.on_refresh_clicked)
        
        # Add refresh icon to refresh button
        try:
            from gi.repository import GdkPixbuf
            app_dir = Path(__file__).resolve().parent.parent
            icons_dir = app_dir / "icons"
            refresh_icon_path = icons_dir / "refresh.svg"
            if refresh_icon_path.exists():
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(refresh_icon_path), width=16, height=16, preserve_aspect_ratio=True)
                image = Gtk.Image.new_from_pixbuf(pix)
                self.btn_refresh.set_image(image)
                self.btn_refresh.set_image_position(Gtk.PositionType.LEFT)
        except Exception:
            pass
        
        action_box.pack_start(self.btn_refresh, False, False, 0)
        
        # Exit button with icon
        exit_btn = Gtk.Button(label="Exit")
        exit_btn.connect("clicked", self.on_exit_clicked)
        
        # Add X icon to exit button
        try:
            from gi.repository import GdkPixbuf
            app_dir = Path(__file__).resolve().parent.parent
            icons_dir = app_dir / "icons"
            exit_icon_path = icons_dir / "power.svg"
            if exit_icon_path.exists():
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(exit_icon_path), width=16, height=16, preserve_aspect_ratio=True)
                image = Gtk.Image.new_from_pixbuf(pix)
                exit_btn.set_image(image)
                exit_btn.set_image_position(Gtk.PositionType.LEFT)
        except Exception:
            pass
        
        action_box.pack_start(exit_btn, False, False, 0)
        
        vbox.pack_start(action_box, False, False, 0)
        
        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_line_wrap(True)
        self.status_label.set_alignment(0, 0.5)
        vbox.pack_start(self.status_label, False, False, 0)
        
        # Output text view
        output_frame = Gtk.Frame(label=" Output ")
        output_scrolled = Gtk.ScrolledWindow()
        output_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        
        self.output_textbuffer = Gtk.TextBuffer()
        self.output_textview = Gtk.TextView(buffer=self.output_textbuffer)
        self.output_textview.modify_font(Pango.FontDescription("Monospace 9"))
        self.output_textview.set_editable(False)
        
        output_scrolled.add(self.output_textview)
        output_frame.add(output_scrolled)
        vbox.pack_start(output_frame, True, True, 0)
        
        # Clear button with icon
        clear_btn = Gtk.Button(label="Clear Output")
        clear_btn.connect("clicked", self.on_clear_output_clicked)
        
        # Add trash icon to clear button
        try:
            from gi.repository import GdkPixbuf
            app_dir = Path(__file__).resolve().parent.parent
            icons_dir = app_dir / "icons"
            clear_icon_path = icons_dir / "trash.svg"
            if clear_icon_path.exists():
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(clear_icon_path), width=16, height=16, preserve_aspect_ratio=True)
                image = Gtk.Image.new_from_pixbuf(pix)
                clear_btn.set_image(image)
                clear_btn.set_image_position(Gtk.PositionType.LEFT)
        except Exception:
            pass
        
        vbox.pack_start(clear_btn, False, False, 0)
        
        # Load tools and populate list
        self.load_tools()
        
        # Add to window
        self.add(vbox)
        
    def load_tools(self):
        """Load available tools into the UI."""
        debug_log("[DEBUG] Loading tools...")
        
        # Clear current list
        self.tools_list_store.clear()
        self.tools_list = self.loader.get_available_tools()
        
        for tool in self.tools_list:
            iter = self.tools_list_store.append()
            self.tools_list_store.set(iter, 0, tool["id"], 1, tool["name"])
            
        debug_log(f"[DEBUG] Loaded {len(self.tools_list)} tools")
        GLib.idle_add(self.update_status, f"Loaded {len(self.tools_list)} tools")
        
    def on_tool_selected(self, treeview):
        """Handle tool selection."""
        model, iter = treeview.get_selection().get_selected()
        if iter:
            self.selected_tool_id = model.get_value(iter, 0)
            self.btn_execute.set_sensitive(True)
            debug_log(f"[DEBUG] Tool selected: {self.selected_tool_id}")
            
    def on_scan_clicked(self, button):
        """Handle scan button click."""
        interface = self.interface_combo.get_active_text()
        GLib.idle_add(self.update_status, "Scanning for networks...")
        
        def scan_thread():
            success, output = self.loader.execute_tool("wifi_scan", interface)
            if success:
                # Parse scan results
                self.scan_results = self._parse_scan_output(output)
                GLib.idle_add(self.update_status, f"Found {len(self.scan_results)} networks")
                GLib.idle_add(self.append_output, output)
            else:
                GLib.idle_add(self.update_status, f"Scan failed: {output}")
                
        threading.Thread(target=scan_thread, daemon=True).start()
        
    def _parse_scan_output(self, output):
        """Parse scan output to extract network information."""
        networks = []
        lines = output.split('\n')
        
        for line in lines:
            if "ESSID:" in line:
                try:
                    ssid = line.split('"')[1]
                    networks.append({"ssid": ssid})
                except IndexError:
                    continue
                    
        return networks
        
    def on_execute_clicked(self, button):
        """Handle execute button click."""
        if not self.selected_tool_id:
            GLib.idle_add(self.update_status, "Please select a tool first")
            return
            
        interface = self.interface_combo.get_active_text()
        
        # Build kwargs for the specific tool
        kwargs = {"interface": interface}
        
        if self.selected_tool_id == "handshake_capture":
            # Add default channel
            kwargs["channel"] = 6
            
        GLib.idle_add(self.update_status, f"Executing {self.selected_tool_id}...")
        
        def execute_thread():
            success, output = self.loader.execute_tool(self.selected_tool_id, interface, **kwargs)
            if success:
                GLib.idle_add(self.update_status, "Execution completed successfully")
                GLib.idle_add(self.append_output, output)
            else:
                GLib.idle_add(self.update_status, f"Execution failed: {output}")
                
        threading.Thread(target=execute_thread, daemon=True).start()
        
    def on_refresh_clicked(self, button):
        """Handle refresh button click."""
        self.load_tools()
        
    def on_exit_clicked(self, button):
        """Exit the WiFi Assessment window."""
        self.destroy()
        
    def on_clear_output_clicked(self, button):
        """Clear output text view."""
        self.output_textbuffer.set_text("")
        
    def update_status(self, message: str):
        """Update status label (called from main thread)."""
        self.status_label.set_text(message)
        return False  # Stop GLib.idle_add
        
    def append_output(self, text: str):
        """Append text to output view (called from main thread)."""
        end_iter = self.output_textbuffer.get_end_iter()
        self.output_textbuffer.insert(end_iter, text)
        self.output_textbuffer.insert(end_iter, "\n" + "="*50 + "\n")
        
    def run(self):
        """Run the window."""
        debug_log("[DEBUG] Running window - showing all widgets")
        self.show_all()
        debug_log("[DEBUG] All widgets shown, entering main loop")
        Gtk.main()


def create_window(app_instance=None):
    """
    Create and show the Wi-Fi assessment window.
    
    Args:
        app_instance: The main App window instance (optional)
    """
    clear_debug_log()
    debug_log("[DEBUG] Creating WifiAssessmentWindow...")
    
    window = WifiAssessmentWindow(app_instance)
    window.run()
