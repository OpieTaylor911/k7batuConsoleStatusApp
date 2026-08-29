#!/usr/bin/env python3
"""
Plugin Base Class - Defines the interface all plugins must implement.

Each plugin should define these class-level attributes:
- PLUGIN_NAME: Display name for the plugin
- PLUGIN_VERSION: Plugin version string
- REQUIRES_SUDO: Whether the plugin requires root privileges to run
- INSTALL_PACKAGES: List of packages that should be installed
- SETUP_INSTRUCTIONS: Multi-line string with setup steps for the user
- PERMISSION_COMMANDS: List of shell commands to fix permissions
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class PluginBase(ABC):
    """Base class for all uConsole plugins."""
    
    # Class-level attributes that each plugin must define
    PLUGIN_NAME: str = "Unnamed Plugin"
    PLUGIN_VERSION: str = "1.0.0"
    REQUIRES_SUDO: bool = False
    INSTALL_PACKAGES: List[str] = []
    SETUP_INSTRUCTIONS: str = ""
    PERMISSION_COMMANDS: List[str] = []
    
    @abstractmethod
    def main(self) -> None:
        """Main entry point for the plugin."""
        pass
    
    @classmethod
    def get_plugin_info(cls) -> dict:
        """
        Get plugin metadata.
        
        Returns:
            Dictionary with plugin information
        """
        return {
            "name": cls.PLUGIN_NAME,
            "version": cls.PLUGIN_VERSION,
            "requires_sudo": cls.REQUIRES_SUDO,
            "install_packages": cls.INSTALL_PACKAGES,
            "setup_instructions": cls.SETUP_INSTRUCTIONS,
            "permission_commands": cls.PERMISSION_COMMANDS
        }
    
    @classmethod
    def check_dependencies(cls) -> tuple[bool, List[str]]:
        """
        Check if all required dependencies are installed.
        
        Returns:
            Tuple of (all_ok: bool, missing_packages: list)
        """
        missing = []
        for package in cls.INSTALL_PACKAGES:
            # Simple check - can be enhanced with actual package verification
            result = cls._check_package_installed(package)
            if not result:
                missing.append(package)
        
        return len(missing) == 0, missing
    
    @staticmethod
    def _check_package_installed(package_name: str) -> bool:
        """
        Check if a package is installed.
        
        Args:
            package_name: Name of the package to check
            
        Returns:
            True if installed, False otherwise
        """
        import subprocess
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f='${Status}'", package_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "install ok installed" in result.stdout.lower()
        except Exception:
            # If we can't check, assume it's installed (best effort)
            return True
    
    @classmethod
    def show_setup_dialog(cls) -> None:
        """
        Show a GTK dialog with plugin setup instructions.
        """
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk, Gdk
            
            # Create dialog
            dialog = Gtk.Dialog(
                title=f"{cls.PLUGIN_NAME} - Setup Instructions",
                flags=0
            )
            dialog.add_buttons("Close", Gtk.ResponseType.CLOSE)
            
            content = dialog.get_content_area()
            content.set_spacing(12)
            content.set_margin_start(12)
            content.set_margin_end(12)
            content.set_margin_top(12)
            content.set_margin_bottom(12)
            
            # Title
            title_label = Gtk.Label()
            title_label.set_markup(f"<b>{cls.PLUGIN_NAME} v{cls.PLUGIN_VERSION}</b>")
            title_label.set_justify(Gtk.Justification.CENTER)
            content.pack_start(title_label, False, False, 0)
            
            # Requirements section
            if cls.INSTALL_PACKAGES:
                req_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                req_title = Gtk.Label()
                req_title.set_markup("<b>Required Packages:</b>")
                req_box.pack_start(req_title, False, False, 0)
                
                for pkg in cls.INSTALL_PACKAGES:
                    pkg_label = Gtk.Label(label=f"  • {pkg}")
                    req_box.pack_start(pkg_label, False, False, 0)
                
                content.pack_start(req_box, False, False, 8)
            
            # Sudo warning
            if cls.REQUIRES_SUDO:
                warn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                icon = Gtk.Image.new_from_icon_name("dialog-warning", Gtk.IconSize.MENU)
                warn_label = Gtk.Label(label="This plugin requires root privileges to run.")
                warn_box.pack_start(icon, False, False, 0)
                warn_box.pack_start(warn_label, False, False, 0)
                content.pack_start(warn_box, False, False, 8)
            
            # Instructions
            if cls.SETUP_INSTRUCTIONS.strip():
                instructions_label = Gtk.Label()
                instructions_label.set_markup("<b>Setup Instructions:</b>")
                content.pack_start(instructions_label, False, False, 4)
                
                instructions_text = Gtk.Label(label=cls.SETUP_INSTRUCTIONS)
                instructions_text.set_line_wrap(True)
                instructions_text.set_selectable(True)
                # Monospace font for commands
                pango_ctx = instructions_text.get_pango_context()
                font_desc = pango_ctx.get_font_description()
                font_desc.set_family("monospace")
                font_desc.set_size(8 * 1024)  # 8pt in Pango units
                instructions_text.modify_font(font_desc)
                
                content.pack_start(instructions_text, True, True, 4)
            
            # Permission commands (if any)
            if cls.PERMISSION_COMMANDS:
                perm_label = Gtk.Label()
                perm_label.set_markup("<b>Permission Fix Commands:</b>")
                content.pack_start(perm_label, False, False, 4)
                
                for cmd in cls.PERMISSION_COMMANDS:
                    cmd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                    cmd_text = Gtk.Label(label=f"sudo {cmd}")
                    cmd_text.set_selectable(True)
                    # Monospace font
                    pango_ctx = cmd_text.get_pango_context()
                    font_desc = pango_ctx.get_font_description()
                    font_desc.set_family("monospace")
                    font_desc.set_size(8 * 1024)
                    cmd_text.modify_font(font_desc)
                    
                    copy_btn = Gtk.Button.new_with_label("Copy")
                    copy_btn.connect("clicked", lambda b, t=cmd: cls._copy_to_clipboard(t))
                    cmd_box.pack_start(cmd_text, True, True, 0)
                    cmd_box.pack_end(copy_btn, False, False, 0)
                    
                    content.pack_start(cmd_box, False, False, 2)
            
            # Run dialog
            dialog.show_all()
            response = dialog.run()
            dialog.destroy()
            
        except Exception as e:
            import sys
            print(f"Error showing setup dialog: {e}", file=sys.stderr)
    
    @staticmethod
    def _copy_to_clipboard(text: str) -> None:
        """Copy text to clipboard."""
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk
            
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)
            clipboard.store()
        except Exception:
            pass
    
    @classmethod
    def run_permission_fixes(cls) -> tuple[bool, str]:
        """
        Execute permission fix commands.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        import subprocess
        
        if not cls.PERMISSION_COMMANDS:
            return True, "No permission fixes required"
        
        try:
            for cmd in cls.PERMISSION_COMMANDS:
                # Execute with sudo
                full_cmd = ["sudo", "bash", "-c", cmd]
                result = subprocess.run(
                    full_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    return False, f"Failed: {cmd}\n{result.stderr}"
            
            return True, "All permission fixes applied successfully"
            
        except Exception as e:
            return False, str(e)
