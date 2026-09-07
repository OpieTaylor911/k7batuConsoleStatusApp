import sys
sys.path.insert(0, "/home/bcaddy/uconsole-k7bat/app")

from pathlib import Path

# Simulate APP_DIR and PLUGINS_PATH
APP_DIR = Path("/home/bcaddy/uconsole-k7bat/app")
PLUGINS_PATH = APP_DIR / "plugins.json"

print(f"PLUGINS_PATH: {PLUGINS_PATH}")
print(f"File exists: {PLUGINS_PATH.exists()}")

# Load plugins using the same logic as the app (with BOM fix)
if not PLUGINS_PATH.exists():
    print("No plugins file found")
    sys.exit(0)

data = __import__("json").loads(PLUGINS_PATH.read_text(encoding="utf-8-sig"))
print(f"Loaded {len(data)} plugin entries")

for item in data:
    label = str(item.get("label", "")).strip()
    plugin_type = str(item.get("type", "shell")).strip().lower()
    
    if plugin_type == "python":
        module_path = str(item.get("module", "")).strip()
        print(f"  Python plugin: {label} -> {module_path}")
        
        # Try to import the module
        try:
            module_name, class_name = module_path.rsplit('.', 1)
            module = __import__(module_name, fromlist=[class_name])
            print(f"    Module imported successfully")
            
            # Check if class exists
            plugin_class = getattr(module, class_name, None)
            if plugin_class:
                print(f"    Class '{class_name}' found in module")
                
                # Try to instantiate (without GUI)
                try:
                    instance = plugin_class()
                    print(f"    Instance created successfully")
                except Exception as e:
                    print(f"    Instance creation skipped (GUI required): {e}")
            else:
                print(f"    ERROR: Class '{class_name}' not found in module")
        except Exception as e:
            print(f"    Import error: {e}")
            import traceback
            traceback.print_exc()
    else:
        command = str(item.get("command", "")).strip()
        print(f"  Shell plugin: {label}")
