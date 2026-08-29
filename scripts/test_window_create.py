#!/usr/bin/env python3
"""Test script to simulate creating the PineappleWindow."""

import sys
sys.path.insert(0, "/home/bcaddy/uconsole-k7bat/app")

# Mock GTK since we're running without display
import os
os.environ['GDK_BACKEND'] = 'x11'  # Force X11 backend

from pathlib import Path

print("Testing PineappleWindow instantiation...")

try:
    from gi.repository import Gtk, GLib
    
    # Add plugins directory to path
    APP_DIR = Path("/home/bcaddy/uconsole-k7bat/app")
    plugins_dir = APP_DIR / "plugins"
    if str(plugins_dir) not in sys.path:
        sys.path.insert(0, str(plugins_dir))
    
    print(f"Plugins dir: {plugins_dir}")
    
    # Import the plugin
    from pineapple_ui import PineappleWindow
    
    print("PineappleWindow imported successfully!")
    
    # Try to create a window (this will fail without display but should show errors)
    try:
        window = PineappleWindow()
        print("PineappleWindow created successfully!")
        window.destroy()
    except Exception as e:
        print(f"Error creating window: {e}")
        import traceback
        traceback.print_exc()
        
except ImportError as e:
    print(f"Import error (expected without display): {e}")
    
    # Still check if the module loads without GTK
    sys.path.insert(0, str(plugins_dir))
    from pineapple_ui import PineappleWindow
    print("PineappleWindow class loaded successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Check debug log
DEBUG_LOG = Path("/home/bcaddy/uconsole-k7bat/pineapple_debug.log")
if DEBUG_LOG.exists():
    print(f"\nDebug log content:\n{DEBUG_LOG.read_text()}")
else:
    print("\nDebug log not found")
