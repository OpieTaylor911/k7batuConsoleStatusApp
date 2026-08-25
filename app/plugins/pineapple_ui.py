#!/usr/bin/env python3
"""
Hak5 Pineapple Module UI Integration

This module provides the GTK3 UI for managing and executing Hak5 Pineapple modules.
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

# Add app directory to path for imports
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

# Use absolute import after path is set
try:
    from plugins.pineapple_loader import PineappleModuleLoader
except ImportError:
    from pineapple_loader import PineappleModuleLoader


class PineappleModuleManager:
    """Manage Hak5 Pineapple modules with GTK3 UI integration."""
    
    def __init__(self, app_instance):
        """
        Initialize the module manager.
        
        Args:
            app_instance: The main App window instance
        """
        self.app = app_instance
        self.loader = PineappleModuleLoader()
        self.modules_dir = self.loader.modules_dir
        
        # UI components
        self.notebook = None
        self.module_list_box = None
        self.output_text_view = None
        self.action_combo = None
        self.input_entry = None
        self.status_label = None
        
    def create_tab(self) -> Gtk.Box:
        """
        Create the Pineapple Modules tab page.
        
        Returns:
            Gtk.Box containing the UI
        """
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_border_width(12)
        
        # Header
        header = self._create_header()
        main_box.pack_start(header, False, False, 0)
        
        # Main content area (split pane)
        split_pane = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split_pane.set_position(300)
        
        # Left side: Module list
        left_panel = self._create_module_list()
        split_pane.pack1(left_panel, True, False)
        
        # Right side: Action controls and output
        right_panel = self._create_action_panel()
        split_pane.pack2(right_panel, True, False)
        
        main_box.pack_start(split_pane, True, True, 0)
        
        # Status bar
        status_bar = self._create_status_bar()
        main_box.pack_end(status_bar, False, False, 0)
        
        # Populate initial data
        GLib.idle_add(self.refresh_module_list)
        
        return main_box
    
    def _create_header(self) -> Gtk.Box:
        """Create the header section with title and buttons."""
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        title_label = Gtk.Label(label=" Hak5 Pineapple Modules")
        title_label.set_xalign(0)
        title_label.get_style_context().add_class("h2")
        
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        refresh_btn.set_tooltip_text("Refresh module list")
        refresh_btn.connect("clicked", lambda _b: self.refresh_module_list())
        
        install_btn = Gtk.Button(label="Install Module")
        install_btn.connect("clicked", lambda _b: self.show_install_dialog())
        
        header.pack_start(title_label, True, True, 0)
        header.pack_end(refresh_btn, False, False, 0)
        header.pack_end(install_btn, False, False, 0)
        
        return header
    
    def _create_module_list(self) -> Gtk.ScrolledWindow:
        """Create the module list panel."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(300)
        
        self.module_list_box = Gtk.ListBox()
        self.module_list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.module_list_box.connect("row-activated", self.on_module_selected)
        
        scrolled.add(self.module_list_box)
        
        return scrolled
    
    def _create_action_panel(self) -> Gtk.Box:
        """Create the action control panel."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        
        # Module info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.module_info_label = Gtk.Label(label="Select a module to view details")
        self.module_info_label.set_xalign(0)
        self.module_info_label.set_line_wrap(True)
        self.module_info_label.get_style_context().add_class("subtle")
        info_box.pack_start(self.module_info_label, False, False, 0)
        main_box.pack_start(info_box, False, False, 0)
        
        # Action controls
        action_frame = Gtk.Frame(label=" Action ")
        action_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        action_box.set_border_width(8)
        
        # Action dropdown
        action_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_label = Gtk.Label(label="Action:")
        action_label.set_xalign(0)
        self.action_combo = Gtk.ComboBoxText()
        self.action_combo.connect("changed", self.on_action_changed)
        
        action_row.pack_start(action_label, False, False, 0)
        action_row.pack_start(self.action_combo, True, True, 0)
        action_box.pack_start(action_row, False, False, 0)
        
        # Input field
        input_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_label = Gtk.Label(label="Input:")
        input_label.set_xalign(0)
        self.input_entry = Gtk.Entry()
        self.input_entry.set_placeholder_text("Enter user input...")
        input_row.pack_start(input_label, False, False, 0)
        input_row.pack_start(self.input_entry, True, True, 0)
        action_box.pack_start(input_row, False, False, 0)
        
        # Execute button
        execute_btn = Gtk.Button(label="Execute Action")
        execute_btn.set_margin_top(8)
        execute_btn.connect("clicked", self.on_execute_clicked)
        action_box.pack_start(execute_btn, False, False, 0)
        
        action_frame.add(action_box)
        main_box.pack_start(action_frame, False, False, 0)
        
        # Output display
        output_frame = Gtk.Frame(label=" Output ")
        output_scrolled = Gtk.ScrolledWindow()
        output_scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        output_scrolled.set_min_content_height(200)
        
        self.output_text_view = Gtk.TextView()
        self.output_text_view.set_monospace(True)
        self.output_text_view.set_editable(False)
        output_buffer = self.output_text_view.get_buffer()
        output_buffer.set_text("Action output will appear here...")
        
        output_scrolled.add(self.output_text_view)
        output_frame.add(output_scrolled)
        main_box.pack_start(output_frame, True, True, 0)
        
        return main_box
    
    def _create_status_bar(self) -> Gtk.Box:
        """Create the status bar."""
        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_xalign(0)
        status.pack_start(self.status_label, True, True, 0)
        
        return status
    
    def refresh_module_list(self):
        """Refresh the list of available modules."""
        if not self.module_list_box:
            return
            
        # Clear existing items
        for child in self.module_list_box.get_children():
            self.module_list_box.remove(child)
            
        # Get modules
        modules = self.loader.discover_modules()
        
        if not modules:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label="No modules installed. Click 'Install Module' to add one.")
            label.set_xalign(0)
            row.add(label)
            self.module_list_box.add(row)
        else:
            for module in modules:
                row = self._create_module_row(module)
                self.module_list_box.add(row)
                
        self.module_list_box.show_all()
        
    def _create_module_row(self, module: Dict) -> Gtk.ListBoxRow:
        """Create a list box row for a module."""
        row = Gtk.ListBoxRow()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_border_width(4)
        
        title_label = Gtk.Label(label=module.get('title', module.get('name', 'Unknown')))
        title_label.set_xalign(0)
        title_label.get_style_context().add_class("bold")
        
        desc_label = Gtk.Label(label=module.get('description', 'No description'))
        desc_label.set_xalign(0)
        desc_label.set_line_wrap(True)
        desc_label.get_style_context().add_class("subtle")
        
        version_label = Gtk.Label(label=f"v{module.get('version', '?')} - {module.get('author', 'Unknown')}")
        version_label.set_xalign(0)
        version_label.get_style_context().add_class("dim-label")
        
        box.pack_start(title_label, False, False, 0)
        box.pack_start(desc_label, False, False, 0)
        box.pack_start(version_label, False, False, 0)
        
        row.add(box)
        row.set_data('module', module)
        
        return row
    
    def on_module_selected(self, list_box: Gtk.ListBox, row: Gtk.ListBoxRow):
        """Handle module selection."""
        if not row:
            return
            
        module = row.get_data('module')
        if not module:
            return
            
        # Update info label
        self.module_info_label.set_text(
            f"Name: {module.get('name', 'N/A')}\n"
            f"Title: {module.get('title', 'N/A')}\n"
            f"Version: {module.get('version', 'N/A')}\n"
            f"Author: {module.get('author', 'N/A')}\n"
            f"Description: {module.get('description', 'N/A')}"
        )
        
        # Load available actions
        self.action_combo.remove_all()
        
        module_name = module.get('name')
        if module_name:
            module_instance = self.loader.load_module(module_name)
            
            if module_instance and hasattr(module_instance, 'handles_action'):
                actions = module_instance.handles_action
                for action_name in sorted(actions.keys()):
                    self.action_combo.append_text(action_name)
                    
                if self.action_combo.get_n_items() > 0:
                    self.action_combo.set_active(0)
        
    def on_action_changed(self, combo: Gtk.ComboBoxText):
        """Handle action selection change."""
        # Clear input when changing actions
        self.input_entry.set_text("")
        
    def on_execute_clicked(self, button: Gtk.Button):
        """Execute the selected action."""
        row = self.module_list_box.get_selected_row()
        if not row:
            self.status_label.set_text("Please select a module first")
            return
            
        module = row.get_data('module')
        if not module:
            return
            
        action = self.action_combo.get_active_text()
        user_input = self.input_entry.get_text()
        
        if not action:
            self.status_label.set_text("Please select an action to execute")
            return
            
        # Disable controls during execution
        self.action_combo.set_sensitive(False)
        self.input_entry.set_sensitive(False)
        button.set_sensitive(False)
        
        # Clear output buffer
        output_buffer = self.output_text_view.get_buffer()
        output_buffer.set_text(f"Executing {action}...\n\n")
        
        # Execute in background thread
        threading.Thread(
            target=self._execute_action_background,
            args=(module, action, user_input),
            daemon=True
        ).start()
        
    def _execute_action_background(self, module: Dict, action: str, user_input: str):
        """Execute action in background thread."""
        module_name = module.get('name')
        
        result = self.loader.execute_action(module_name, action, user_input)
        
        # Update UI on main thread
        GLib.idle_add(self._update_output, result, module, action)
        
    def _update_output(self, result: Dict, module: Dict, action: str):
        """Update output display with result."""
        output_buffer = self.output_text_view.get_buffer()
        
        # Re-enable controls
        self.action_combo.set_sensitive(True)
        self.input_entry.set_sensitive(True)
        
        # Find the execute button by iterating through children
        for child in self.module_info_label.get_ancestors():
            if isinstance(child, Gtk.Button) and "Execute" in str(child.get_label()):
                child.set_sensitive(True)
                break
        
        # Format and display result
        output_buffer.insert(
            output_buffer.get_end_iter(),
            f"[{action}]\n"
        )
        
        if 'error' in result:
            output_buffer.insert(
                output_buffer.get_end_iter(),
                f"ERROR: {result['error']}\n"
            )
        else:
            # Pretty print the result
            output_buffer.insert(
                output_buffer.get_end_iter(),
                json.dumps(result, indent=2) + "\n"
            )
            
        output_buffer.insert(
            output_buffer.get_end_iter(),
            f"\nExecuted: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        self.status_label.set_text(f"Executed {action} on {module.get('name', 'unknown')}")
        
    def show_install_dialog(self):
        """Show dialog to install a new module."""
        dlg = Gtk.Dialog(title="Install Pineapple Module", transient_for=self.app, flags=0)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Install", Gtk.ResponseType.OK)
        
        content = dlg.get_content_area()
        content.set_spacing(12)
        
        # Source selection
        source_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        source_label = Gtk.Label(label="Source URL:")
        source_label.set_xalign(0)
        self.install_entry = Gtk.Entry()
        self.install_entry.set_placeholder_text("https://github.com/hak5/pineapple-modules.git")
        
        source_box.pack_start(source_label, False, False, 0)
        source_box.pack_start(self.install_entry, False, False, 0)
        content.pack_start(source_box, False, False, 0)
        
        # Info label
        info_label = Gtk.Label(
            label="Note: This will clone the entire repository. "
                  "Only modules with Python backend (module.py) can be used."
        )
        info_label.set_xalign(0)
        info_label.set_line_wrap(True)
        info_label.get_style_context().add_class("subtle")
        content.pack_start(info_label, False, False, 0)
        
        content.show_all()
        
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            url = self.install_entry.get_text().strip()
            if url:
                threading.Thread(
                    target=self._install_module_background,
                    args=(url,),
                    daemon=True
                ).start()
                
        dlg.destroy()
        
    def _install_module_background(self, url: str):
        """Install module from URL in background."""
        self.status_label.set_text(f"Installing from {url}...")
        
        try:
            # Clone the repository
            repo_name = Path(url).stem
            
            if not os.path.exists(str(self.modules_dir.parent / "pineapple-modules")):
                result = os.system(f'git clone "{url}" "{self.modules_dir.parent / "pineapple-modules"}" 2>&1')
                
                if result == 0:
                    # Copy specific modules
                    source_repo = self.modules_dir.parent / "pineapple-modules"
                    
                    for item in source_repo.iterdir():
                        if item.is_dir() and (item / "module.json").exists():
                            dest = self.modules_dir / item.name
                            
                            if not dest.exists():
                                import shutil
                                shutil.copytree(item, dest)
                                self.status_label.set_text(f"Installed: {item.name}")
                    else:
                        self.status_label.set_text("Installation failed")
                        
        except Exception as e:
            GLib.idle_add(self._show_error, f"Installation failed: {str(e)}")
            
    def _show_error(self, message: str):
        """Show error dialog."""
        dlg = Gtk.MessageDialog(
            transient_for=self.app,
            flags=0,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dlg.run()
        dlg.destroy()


class PineappleWindow(Gtk.Window):
    """Full-screen window for Hak5 Pineapple Modules."""
    
    def __init__(self, app_instance=None):
        super().__init__(title="Hak5 Pineapple Modules")
        self.set_default_size(1024, 768)
        self.set_position(Gtk.WindowPosition.CENTER)
        
        # Store reference to parent app if provided
        self.app = app_instance
        
        # Create main layout
        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(outer_box)
        
        # Header with title and exit button
        header = Gtk.HeaderBar()
        header.set_show_close_button(False)  # We'll add our own close button
        
        title_label = Gtk.Label(label="Hak5 Pineapple Modules")
        title_label.get_style_context().add_class("title")
        header.pack_start(title_label)
        
        # Exit button
        exit_btn = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.BUTTON)
        exit_btn.set_tooltip_text("Exit to main app")
        exit_btn.connect("clicked", self.on_exit_clicked)
        header.pack_end(exit_btn)
        
        outer_box.pack_start(header, False, False, 0)
        
        # Main content (reuse the module manager UI)
        manager = PineappleModuleManager(self)
        self.pineapple_manager = manager
        
        main_content = manager.create_tab()
        outer_box.pack_start(main_content, True, True, 0)
        
        self.show_all()
    
    def on_exit_clicked(self, button):
        """Handle exit button click."""
        if self.app:
            # Return focus to parent app
            self.app.present()
        self.destroy()


def register_plugin(app_instance):
    """
    Register the Pineapple Module plugin with the main app.
    
    Args:
        app_instance: The main App window instance
        
    Returns:
        Tuple of (tab_label, tab_content) for adding to notebook
    """
    manager = PineappleModuleManager(app_instance)
    tab_content = manager.create_tab()
    
    # Create tab label with icon
    tab_label = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    icon = Gtk.Image.new_from_icon_name("network-wireless-symbolic", Gtk.IconSize.MENU)
    label = Gtk.Label(label=" Pineapple Modules")
    
    tab_label.pack_start(icon, False, False, 0)
    tab_label.pack_start(label, False, False, 0)
    tab_label.show_all()
    
    return tab_label, tab_content
