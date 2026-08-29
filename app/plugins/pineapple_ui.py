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

# User app directory
USER_APP_DIR = Path("/home/bcaddy/uconsole-k7bat")

# Debug log file location
DEBUG_LOG = USER_APP_DIR / "pineapple_debug.log"

# Add app directory to path for imports
APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

# Use absolute import after path is set
try:
    from plugins.pineapple_loader import PineappleModuleLoader
except ImportError:
    from pineapple_loader import PineappleModuleLoader

# Active modules directory (only selected modules)
ACTIVE_MODULES_DIR = USER_APP_DIR / "pineapple_modules"

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

class PineappleModuleManager:
    """Manage Hak5 Pineapple modules with GTK3 UI integration."""
    
    def __init__(self, app_instance):
        """
        Initialize the module manager.
        
        Args:
            app_instance: The main App window instance
        """
        self.app = app_instance
        # Don't clear debug log - let it accumulate for debugging
        debug_log("[DEBUG] PineappleModuleManager initializing...")
        debug_log(f"[DEBUG] Creating PineappleModuleLoader...")
        self.loader = PineappleModuleLoader()
        debug_log(f"[DEBUG] PineappleModuleLoader created")
        self.modules_dir = ACTIVE_MODULES_DIR
        
        # UI components
        self.notebook = None
        self.module_list_box = None
        self.status_label = None
        
        # Full repo clone directory (for all modules)
        self.full_repo_dir = USER_APP_DIR / "pineapple-modules-full"
        debug_log(f"[DEBUG] Full repo dir: {self.full_repo_dir}")
        # Active modules directory (only selected modules)
        self.active_modules_dir = ACTIVE_MODULES_DIR
        debug_log(f"[DEBUG] Active modules dir: {self.active_modules_dir}")
        
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
        
        # Module list (full width for simpler UI)
        module_list = self._create_module_list()
        main_box.pack_start(module_list, True, True, 0)
        
        # Status bar
        status_bar = self._create_status_bar()
        main_box.pack_end(status_bar, False, False, 0)
        
        debug_log(f"[DEBUG] Before populate: module_list_box={self.module_list_box}")
        
        # Populate initial data
        GLib.idle_add(self.refresh_module_list)
        debug_log("[DEBUG] GLib.idle_add(refresh_module_list) called")
        
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
        # Removed row-activated signal since we use launch buttons instead
        # self.module_list_box.connect("row-activated", self.on_module_selected)
        
        scrolled.add(self.module_list_box)
        
        return scrolled
    
    def _create_status_bar(self) -> Gtk.Box:
        """Create the status bar."""
        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_xalign(0)
        status.pack_start(self.status_label, True, True, 0)
        
        return status
    
    def refresh_module_list(self):
        """Refresh the list of available modules."""
        debug_log(f"[DEBUG] refresh_module_list called")
        if not self.module_list_box:
            debug_log("[DEBUG] refresh_module_list: module_list_box is None, returning early!")
            return
            
        # Clear existing items
        for child in self.module_list_box.get_children():
            self.module_list_box.remove(child)
            
        # Get modules
        modules = self.loader.discover_modules()
        debug_log(f"[DEBUG] Found {len(modules)} modules")
        
        if not modules:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label="No modules installed. Click 'Install Module' to add one.")
            label.set_xalign(0)
            row.add(label)
            self.module_list_box.add(row)
        else:
            debug_log(f"[DEBUG] Starting module row creation loop")
            for module in modules:
                try:
                    debug_log(f"[DEBUG] Creating row for module: {module.get('name', 'unknown')}")
                    row = self._create_module_row(module)
                    self.module_list_box.add(row)
                    debug_log(f"[DEBUG] Added row for {module.get('name', 'unknown')}")
                except Exception as e:
                    import traceback
                    debug_log(f"[ERROR] Failed to create row for module: {e}")
                    debug_log(f"[ERROR] Traceback: {traceback.format_exc()}")
                    
            debug_log(f"[DEBUG] refresh_module_list: showing all rows")
            self.module_list_box.show_all()
        
    def _create_module_row(self, module: Dict) -> Gtk.ListBoxRow:
        """Create a list box row for a module."""
        debug_log(f"[DEBUG] _create_module_row called")
        
        # Convert to regular dict if needed (PyGObject might pass GLib.Dict)
        if not isinstance(module, dict):
            module = dict(module)
            
        debug_log(f"[DEBUG] Module type: {type(module)}")
        
        # Use direct key access instead of .get() to avoid PyGObject issues
        name = module.get('name', 'Unknown') if isinstance(module, dict) else str(module)
        title = module.get('title', name) if isinstance(module, dict) else name
        desc = module.get('description', 'No description') if isinstance(module, dict) else ''
        version = module.get('version', '?') if isinstance(module, dict) else '?'
        author = module.get('author', 'Unknown') if isinstance(module, dict) else 'Unknown'
        
        debug_log(f"[DEBUG] Creating row for: {name}")
        
        row = Gtk.ListBoxRow()
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_border_width(4)
        
        title_label = Gtk.Label(label=title)
        title_label.set_xalign(0)
        title_label.get_style_context().add_class("bold")
        
        desc_label = Gtk.Label(label=desc)
        desc_label.set_xalign(0)
        desc_label.set_line_wrap(True)
        desc_label.get_style_context().add_class("subtle")
        
        version_label = Gtk.Label(label=f"v{version} - {author}")
        version_label.set_xalign(0)
        version_label.get_style_context().add_class("dim-label")
        
        box.pack_start(title_label, False, False, 0)
        box.pack_start(desc_label, False, False, 0)
        box.pack_start(version_label, False, False, 0)
        
        row.add(box)
        
        # Add launch button for web-based modules
        launch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        launch_box.set_halign(Gtk.Align.END)
        
        launch_btn = Gtk.Button(label="Launch in Browser")
        launch_btn.connect("clicked", self.on_launch_clicked, module)
        launch_box.pack_start(launch_btn, False, False, 0)
        
        box.pack_start(launch_box, False, False, 0)
        
        # Use Python attributes instead of GTK's set_data (unsupported in PyGObject)
        row._module = module
        
        debug_log(f"[DEBUG] _create_module_row created row for {name}, returning")
        return row
    
    def _deploy_modules_to_webroot(self):
        """Deploy Pineapple modules to the web server's document root."""
        try:
            # Check if lighttpd is running, start it if not
            result = subprocess.run(
                ['pgrep', '-x', 'lighttpd'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                debug_log("[DEBUG] Starting lighttpd web server...")
                subprocess.run(['sudo', 'service', 'lighttpd', 'start'], check=False)
            
            # Source and destination paths
            source_dir = "/home/bcaddy/.config/k7bat-uconsole-status/pineapple-modules"
            dest_dir = "/var/www/html/modules"
            
            debug_log(f"[DEBUG] Deploying modules from {source_dir} to {dest_dir}")
            
            # Create destination directory if it doesn't exist
            subprocess.run(['sudo', 'mkdir', '-p', dest_dir], check=False)
            
            # Remove existing symlinks and recreate them
            subprocess.run(['sudo', 'rm', '-rf', f"{dest_dir}/*"], check=False)
            
            # Get list of modules
            if os.path.exists(source_dir):
                for module_name in os.listdir(source_dir):
                    module_path = os.path.join(source_dir, module_name)
                    link_path = os.path.join(dest_dir, module_name)
                    
                    if os.path.isdir(module_path):
                        debug_log(f"[DEBUG] Creating symlink for {module_name}")
                        subprocess.run(
                            ['sudo', 'ln', '-sf', module_path, link_path],
                            check=False
                        )
            
            # Set proper permissions
            subprocess.run(['sudo', 'chown', '-R', 'www-data:www-data', dest_dir], check=False)
            
            # Generate index.html for each module (since they're Angular libraries without standalone HTML)
            debug_log("[DEBUG] Generating index.html files for modules")
            for module_name in os.listdir(source_dir):
                module_link = os.path.join(dest_dir, module_name)
                if os.path.islink(module_link):
                    # Get the actual target of the symlink
                    module_dist = os.path.realpath(module_link)
                elif os.path.isdir(module_link):
                    module_dist = module_link
                else:
                    continue
                    
                # Look for dist folder structure: either dist/name/ or just dist/
                if os.path.exists(os.path.join(module_dist, "dist", module_name)):
                    actual_dist = os.path.join(module_dist, "dist", module_name)
                elif os.path.exists(os.path.join(module_dist, "dist")):
                    actual_dist = os.path.join(module_dist, "dist")
                else:
                    debug_log(f"[DEBUG] No dist folder found in {module_link}")
                    continue
                    
                index_path = os.path.join(actual_dist, "index.html")
                if not os.path.exists(index_path):
                        try:
                            # Create a simple HTML wrapper that loads the main bundle
                            index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{module_name.title()}</title>
    <base href=".">
    <style>
        body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .loading {{ display: flex; justify-content: center; align-items: center; height: 100vh; }}
    </style>
</head>
<body>
    <div id="app" class="loading">
        <h2>Loading {module_name}...</h2>
    </div>
    <script src="bundles/runtime.js"></script>
    <script src="bundles/polyfills.js"></script>
    <script src="bundles/main.js"></script>
</body>
</html>"""
                            with open(index_path, 'w') as f:
                                f.write(index_content)
                            debug_log(f"[DEBUG] Created index.html for {module_name}")
                        except Exception as ie:
                            debug_log(f"[DEBUG] Failed to create index.html for {module_name}: {ie}")
            
        except Exception as e:
            debug_log(f"[DEBUG] Error deploying modules: {str(e)}")
    
    def is_module_built(self, module_name: str) -> bool:
        """Check if a module has been built (has dist folder)."""
        module_path = os.path.join(self.full_repo_dir, module_name)
        dist_path = os.path.join(module_path, "dist", module_name)
        return os.path.exists(dist_path)

    def on_launch_clicked(self, button: Gtk.Button, module: Dict):
        """Launch the module's web interface in a browser."""
        module_name = module.get('name', 'unknown')
        debug_log(f"[DEBUG] Launching module: {module_name}")
        
        # Pineapple modules are Angular web applications that need to be built
        # and served by a web server. The URL format is http://localhost/modules/{module_name}
        import subprocess
        
        try:
            # Check if module has been built (look for dist folder in .config location)
            config_modules_dir = Path("/home/bcaddy/.config/k7bat-uconsole-status/pineapple-modules")
            module_path = config_modules_dir / module_name
            dist_path = module_path / "dist" / module_name
            
            if not os.path.exists(dist_path):
                debug_log(f"[DEBUG] Module {module_name} not built yet (looking for {dist_path})")
                if hasattr(self, 'status_label') and self.status_label:
                    self.status_label.set_text(f"Module '{module_name}' needs to be built first. Run: cd /home/bcaddy/.config/k7bat-uconsole-status/pineapple-modules/{module_name} && ./build.sh")
                return
            
            # Deploy modules to web root
            self._deploy_modules_to_webroot()
            
            # Try to open in browser using xdg-open (Linux)
            module_url = f"http://localhost/modules/{module_name}"
            debug_log(f"[DEBUG] Opening URL: {module_url}")
            
            result = subprocess.run(
                ['xdg-open', module_url],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                if hasattr(self, 'status_label') and self.status_label:
                    self.status_label.set_text(f"Launched {module_name} in browser")
                debug_log(f"[DEBUG] Successfully launched {module_name}")
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                debug_log(f"[DEBUG] Failed to launch: {error_msg}")
                if hasattr(self, 'status_label') and self.status_label:
                    self.status_label.set_text(f"Failed to launch {module_name}: {error_msg[:50]}")
                
        except FileNotFoundError:
            # xdg-open not available, try python webbrowser
            import webbrowser
            try:
                module_url = f"http://localhost/modules/{module_name}"
                debug_log(f"[DEBUG] Trying webbrowser.open: {module_url}")
                webbrowser.open(module_url)
                if hasattr(self, 'status_label') and self.status_label:
                    self.status_label.set_text(f"Launched {module_name} in browser")
            except Exception as e:
                debug_log(f"[DEBUG] Failed to launch with webbrowser: {e}")
                if hasattr(self, 'status_label') and self.status_label:
                    self.status_label.set_text(f"Could not launch {module_name}: {str(e)[:50]}")
        except Exception as e:
            debug_log(f"[DEBUG] Launch error: {e}")
            import traceback
            debug_log(f"[DEBUG] Traceback: {traceback.format_exc()}")
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.set_text(f"Launch failed: {str(e)[:50]}")
    
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
        debug_log(f"[DEBUG] Install dialog response: {resp}")
        if resp == Gtk.ResponseType.OK:
            url = self.install_entry.get_text().strip()
            debug_log(f"[DEBUG] Install URL entered: '{url}'")
            if url:
                debug_log("[DEBUG] Starting install thread...")
                threading.Thread(
                    target=self._install_module_background,
                    args=(url,),
                    daemon=True
                ).start()
        else:
            debug_log("[DEBUG] Install dialog cancelled")
        
        dlg.destroy()
        
    def _install_module_background(self, url: str):
        """Install all modules from URL in background."""
        self.status_label.set_text(f"Installing all modules from {url}...")
        
        try:
            import subprocess
            import shutil
            
            # Convert tree URLs to base repo URL for cloning
            if '/tree/' in url:
                clone_url = url.split('/tree/')[0]
            else:
                clone_url = url
            
            # Clone all modules to full_repo_dir
            debug_log(f"[DEBUG] Using clone directory: {self.full_repo_dir}")
            debug_log(f"[DEBUG] Clone dir exists before clone: {self.full_repo_dir.exists()}")
            full_repo_str = str(self.full_repo_dir)
            
            # Remove existing clone if present
            if self.full_repo_dir.exists():
                shutil.rmtree(self.full_repo_dir)
            
            # Clone the repository
            result = subprocess.run(
                ['git', 'clone', clone_url, full_repo_str],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                debug_log(f"[DEBUG] Clone succeeded. Checking for modules in {self.full_repo_dir}")
                # Discover all modules in the cloned repo
                # Modules are structured as: module-name/projects/module-name/src/module.json
                all_modules = []
                
                for item in self.full_repo_dir.iterdir():
                    if item.is_dir():
                        debug_log(f"[DEBUG] Checking directory: {item.name}")
                        # Check for Angular-style structure: projects/name/src/module.json
                        projects_dir = item / "projects"
                        if projects_dir.exists():
                            debug_log(f"[DEBUG] Found projects directory in {item.name}")
                            for project_dir in projects_dir.iterdir():
                                if project_dir.is_dir():
                                    module_json = project_dir / "src" / "module.json"
                                    if module_json.exists():
                                        try:
                                            with open(module_json) as f:
                                                meta = json.load(f)
                                                all_modules.append({
                                                    'name': item.name,
                                                    'title': meta.get('title', item.name),
                                                    'description': meta.get('description', ''),
                                                    'project_dir': project_dir
                                                })
                                                debug_log(f"[DEBUG] Added module: {item.name} ({meta.get('title', item.name)})")
                                        except Exception as e:
                                            debug_log(f"[DEBUG] Error reading {module_json}: {e}")
                        
                        # Also check direct structure for backward compatibility: module.json at root
                        module_json = item / "module.json"
                        if module_json.exists() and not any(m['name'] == item.name for m in all_modules):
                            try:
                                with open(module_json) as f:
                                    meta = json.load(f)
                                    all_modules.append({
                                        'name': item.name,
                                        'title': meta.get('title', item.name),
                                        'description': meta.get('description', ''),
                                        'project_dir': item
                                    })
                                    debug_log(f"[DEBUG] Added module (direct): {item.name} ({meta.get('title', item.name)})")
                            except:
                                pass
                
                debug_log(f"[DEBUG] Found {len(all_modules)} modules total")
                if all_modules:
                    # Show selection dialog
                    GLib.idle_add(self._show_module_selection, all_modules)
                else:
                    GLib.idle_add(self._show_error, "No valid modules found in repository (expected module.json in projects/*/src/)")
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                debug_log(f"[DEBUG] Clone failed with code {result.returncode}")
                GLib.idle_add(self._show_error, f"Git clone failed: {error_msg[:100]}")
                        
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
    
    def _show_module_selection(self, modules):
        """Show dialog to select which modules to install."""
        dlg = Gtk.Dialog(title="Select Modules", transient_for=self.app, flags=0)
        dlg.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Install Selected", Gtk.ResponseType.OK)
        
        content = dlg.get_content_area()
        content.set_spacing(12)
        content.set_border_width(12)
        
        # Instructions
        label = Gtk.Label(
            f"Found {len(modules)} modules. Select which ones to activate:"
        )
        label.set_xalign(0)
        label.set_line_wrap(True)
        content.pack_start(label, False, False, 0)
        
        # List of checkboxes
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_max_content_height(300)
        
        self.module_checkboxes = []
        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        
        for mod in modules:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            
            checkbox = Gtk.CheckButton(label=mod['title'])
            checkbox.set_active(True)  # Default to all active
            checkbox.set_tooltip_text(f"{mod.get('description', 'No description')}\n\nModule: {mod['name']}")
            
            box.pack_start(checkbox, False, False, 0)
            row.add(box)
            list_box.add(row)
            self.module_checkboxes.append((mod['name'], (mod, checkbox)))
        
        scrolled.add(list_box)
        content.pack_start(scrolled, True, True, 0)
        
        # Show all widgets including checkboxes
        for name, (mod, cb) in self.module_checkboxes:
            cb.show_all()
        content.show_all()
        
        debug_log(f"[DEBUG] Dialog showing with {len(modules)} modules")
        resp = dlg.run()
        debug_log(f"[DEBUG] Dialog response: {resp}")
        if resp == Gtk.ResponseType.OK:
            # Get selected modules - unpack correctly: (name, (mod_info, checkbox))
            selected = [name for name, (mod_info, cb) in self.module_checkboxes if cb.get_active()]
            
            debug_log(f"[DEBUG] Selected modules: {selected}")
            debug_log(f"[DEBUG] Full repo dir: {self.full_repo_dir}, exists: {self.full_repo_dir.exists()}")
            debug_log(f"[DEBUG] Active modules dir: {self.active_modules_dir}, exists: {self.active_modules_dir.exists()}")
            
            # Copy selected modules to active_modules_dir
            copied_count = 0
            for name, (module_info, cb) in self.module_checkboxes:
                # module_info contains 'project_dir' which is the source directory
                src = module_info['project_dir']
                dst = self.active_modules_dir / name
                
                debug_log(f"[DEBUG] Checking module: {name}, src exists: {src.exists()}, has json: {(src / 'module.json').exists()}")
                
                if src.exists() and (src / "module.json").exists():
                    if name in selected:
                        if not dst.exists():
                            try:
                                import shutil
                                debug_log(f"[DEBUG] Copying {src} to {dst}")
                                shutil.copytree(src, dst)
                                copied_count += 1
                                debug_log(f"[DEBUG] Copied successfully")
                            except Exception as e:
                                debug_log(f"[DEBUG] Error copying {name}: {e}")
                    else:
                        # Remove if exists but not selected
                        if dst.exists():
                            try:
                                import shutil
                                shutil.rmtree(dst)
                            except Exception as e:
                                debug_log(f"[DEBUG] Error removing {name}: {e}")
            
            debug_log(f"[DEBUG] Total copied: {copied_count}")
            GLib.idle_add(self.status_label.set_text, f"Installed {copied_count} module(s)")
            GLib.idle_add(self.refresh_module_list)
        
        dlg.destroy()


class PineappleWindow(Gtk.Window):
    """Full-screen window for Hak5 Pineapple Modules."""
    
    def __init__(self, app_instance=None):
        try:
            debug_log("[DEBUG] PineappleWindow.__init__ starting...")
            super().__init__(title="Hak5 Pineapple Modules")
            # Set full screen for better module viewing experience
            self.fullscreen()
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
            debug_log("[DEBUG] Creating PineappleModuleManager instance...")
            manager = PineappleModuleManager(app_instance)
            self.pineapple_manager = manager
            
            debug_log("[DEBUG] Calling create_tab()...")
            main_content = manager.create_tab()
            debug_log(f"[DEBUG] create_tab() returned, type: {type(main_content)}")
            
            if not main_content:
                debug_log("[DEBUG] ERROR: create_tab() returned None!")
                return
                
            outer_box.pack_start(main_content, True, True, 0)
            
            debug_log("[DEBUG] Calling show_all()...")
            self.show_all()
            debug_log("[DEBUG] PineappleWindow.show_all() complete")
        except Exception as e:
            import traceback
            tb_str = "\n".join(traceback.format_exc().splitlines()[-10:])
            debug_log(f"[DEBUG] PineappleWindow.__init__ error: {e}\n{tb_str}")
            raise
    
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
