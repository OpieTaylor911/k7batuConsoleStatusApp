import sys
sys.path.insert(0, "/home/bcaddy/uconsole-k7bat/app")
try:
    from plugins.pineapple_loader import PineappleModuleLoader, ACTIVE_MODULES_DIR
    print(f"ACTIVE_MODULES_DIR: {ACTIVE_MODULES_DIR}")
    
    loader = PineappleModuleLoader()
    print(f"Loader modules_dir: {loader.modules_dir}")
    
    # Try to discover modules
    modules = loader.discover_modules()
    print(f"Found {len(modules)} modules")
    for m in modules:
        print(f"  - {m.get('name', 'unknown')}: {m.get('display_name', 'N/A')}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
