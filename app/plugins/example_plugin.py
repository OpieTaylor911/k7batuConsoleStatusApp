#!/usr/bin/env python3
"""
Example Plugin Template - Show how to implement a new plugin

This template demonstrates the proper way to structure a uConsole plugin
with the new configuration system.
"""

from typing import List

# ============================================================================
# Plugin Metadata (required for plugin system)
# ============================================================================

PLUGIN_NAME: str = "Your Plugin Name"
PLUGIN_VERSION: str = "1.0.0"
REQUIRES_SUDO: bool = False  # Set to True if plugin needs root privileges
INSTALL_PACKAGES: List[str] = []  # List of packages that should be installed
SETUP_INSTRUCTIONS: str = ""  # Multi-line string with setup steps for the user
PERMISSION_COMMANDS: List[str] = []  # List of shell commands to fix permissions

# ============================================================================
# Plugin Implementation Class
# ============================================================================


class YourPlugin:
    """Your plugin implementation."""
    
    def __init__(self):
        """Initialize your plugin."""
        pass
    
    def run(self):
        """Main plugin functionality."""
        print(f"Running {PLUGIN_NAME} v{PLUGIN_VERSION}")
        # Your plugin code here


# ============================================================================
# Utility Functions
# ============================================================================

def get_plugin_info() -> dict:
    """Get plugin metadata as dictionary."""
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "requires_sudo": REQUIRES_SUDO,
        "install_packages": INSTALL_PACKAGES,
        "setup_instructions": SETUP_INSTRUCTIONS,
        "permission_commands": PERMISSION_COMMANDS
    }


def check_dependencies() -> tuple[bool, List[str]]:
    """
    Check if all required dependencies are installed.
    
    Returns:
        Tuple of (all_ok: bool, missing_packages: list)
    """
    import subprocess
    
    missing = []
    for package in INSTALL_PACKAGES:
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f='${Status}'", package],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "install ok installed" not in result.stdout.lower():
                missing.append(package)
        except Exception:
            # If we can't check, assume it's installed (best effort)
            pass
    
    return len(missing) == 0, missing


def show_setup_dialog() -> None:
    """Show a GTK dialog with plugin setup instructions."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, Gdk
        
        # Create dialog
        dialog = Gtk.Dialog(
            title=f"{PLUGIN_NAME} - Setup Instructions",
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
        title_label.set_markup(f"<b>{PLUGIN_NAME} v{PLUGIN_VERSION}</b>")
        title_label.set_justify(Gtk.Justification.CENTER)
        content.pack_start(title_label, False, False, 0)
        
        # Requirements section
        if INSTALL_PACKAGES:
            req_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            req_title = Gtk.Label()
            req_title.set_markup("<b>Required Packages:</b>")
            req_box.pack_start(req_title, False, False, 0)
            
            for pkg in INSTALL_PACKAGES:
                pkg_label = Gtk.Label(label=f"  • {pkg}")
                req_box.pack_start(pkg_label, False, False, 0)
            
            content.pack_start(req_box, False, False, 8)
        
        # Sudo warning
        if REQUIRES_SUDO:
            warn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            icon = Gtk.Image.new_from_icon_name("dialog-warning", Gtk.IconSize.MENU)
            warn_label = Gtk.Label(label="This plugin requires root privileges to run.")
            warn_box.pack_start(icon, False, False, 0)
            warn_box.pack_start(warn_label, False, False, 0)
            content.pack_start(warn_box, False, False, 8)
        
        # Instructions
        if SETUP_INSTRUCTIONS.strip():
            instructions_label = Gtk.Label()
            instructions_label.set_markup("<b>Setup Instructions:</b>")
            content.pack_start(instructions_label, False, False, 4)
            
            instructions_text = Gtk.Label(label=SETUP_INSTRUCTIONS)
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
        if PERMISSION_COMMANDS:
            perm_label = Gtk.Label()
            perm_label.set_markup("<b>Permission Fix Commands:</b>")
            content.pack_start(perm_label, False, False, 4)
            
            for cmd in PERMISSION_COMMANDS:
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
                copy_btn.connect("clicked", lambda b, t=cmd: _copy_to_clipboard(t))
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


def run_permission_fixes() -> tuple[bool, str]:
    """
    Execute permission fix commands.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    import subprocess
    
    if not PERMISSION_COMMANDS:
        return True, "No permission fixes required"
    
    try:
        for cmd in PERMISSION_COMMANDS:
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


# ============================================================================
# Main Entry Point (for standalone testing)
# ============================================================================

def main():
    """Main entry point for the plugin."""
    print(f"Plugin: {PLUGIN_NAME} v{PLUGIN_VERSION}")
    print(f"Requires Sudo: {REQUIRES_SUDO}")
    print(f"Install Packages: {', '.join(INSTALL_PACKAGES) if INSTALL_PACKAGES else 'None'}")
    
    # Check dependencies
    ok, missing = check_dependencies()
    if ok:
        print("✓ All dependencies satisfied")
    else:
        print(f"✗ Missing packages: {', '.join(missing)}")
        print("\nTo install missing packages, run:")
        for pkg in missing:
            print(f"  sudo apt install {pkg}")
    
    # Show setup dialog (uncomment to test)
    # show_setup_dialog()
    
    # Run the plugin
    plugin = YourPlugin()
    plugin.run()


if __name__ == "__main__":
    main()
