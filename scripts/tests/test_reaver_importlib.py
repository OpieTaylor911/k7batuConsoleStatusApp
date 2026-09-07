#!/usr/bin/env python3
import sys
import importlib
from pathlib import Path

# Add plugin paths
sys.path.insert(0, str(Path("/home/bcaddy/uconsole-k7bat/plugins")))
print(f"Added path: /home/bcaddy/uconsole-k7bat/plugins")
print(f"sys.path[0] = {sys.path[0]}")

# Try to import reaver.reaver_ui
try:
    module = importlib.import_module("reaver.reaver_ui")
    print(f"SUCCESS: Imported {module.__file__}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
