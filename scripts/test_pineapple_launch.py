#!/usr/bin/env python3
"""Test script to simulate launching the Pineapple plugin from the main app."""

import sys
sys.path.insert(0, "/home/bcaddy/uconsole-k7bat/app")

from pathlib import Path
import json

# Use explicit app dir since __file__ might not be available in all contexts
APP_DIR = Path("/home/bcaddy/uconsole-k7bat/app")
PLUGINS_PATH = APP_DIR / "plugins.json"

print(f"APP_DIR: {APP_DIR}")
print(f"PLUGINS_PATH: {PLUGINS_PATH}")

# Load plugins with BOM fix
data = json.loads(PLUGINS_PATH.read_text(encoding="utf-8-sig"))
print(f"\nLoaded {len(data)} plugin entries")

# Find the pineapple plugin
pineapple_plugin = None
for item in data:
    if str(item.get("id", "")).strip() == "pineapple-modules":
        pineapple_plugin = item
        break

if not pineapple_plugin:
    print("ERROR: Pineapple plugin not found!")
    sys.exit(1)

print(f"\nPineapple plugin config:")
print(json.dumps(pineapple_plugin, indent=2))

# Verify module path
module_path = str(pineapple_plugin.get("module", "")).strip()
print(f"\nModule path: {module_path}")

# Add plugins directory to path (as the app does)
plugins_dir = APP_DIR / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.insert(0, str(plugins_dir))
    print(f"Added plugins dir to path: {plugins_dir}")

# Try to import
try:
    module_name, class_name = module_path.rsplit('.', 1)
    print(f"\nImporting module: {module_name}, class: {class_name}")
    
    module = __import__(module_name, fromlist=[class_name])
    print(f"Module imported successfully!")
    
    plugin_class = getattr(module, class_name)
    print(f"Class '{class_name}' found in module")
    
    # Check if it's the right type
    import inspect
    if inspect.isclass(plugin_class):
        print(f"{class_name} is a class")
        
        # Get parent classes
        bases = [b.__name__ for b in plugin_class.__bases__]
        print(f"Parent classes: {', '.join(bases)}")
        
        # Check if it's a GTK window subclass
        from gi.repository import Gtk
        if issubclass(plugin_class, Gtk.Window):
            print(f"{class_name} IS a Gtk.Window subclass (correct type)")
        else:
            print(f"WARNING: {class_name} is NOT a Gtk.Window subclass")
    else:
        print(f"ERROR: {class_name} is not a class!")
        
except Exception as e:
    print(f"\nImport error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All checks passed!")
