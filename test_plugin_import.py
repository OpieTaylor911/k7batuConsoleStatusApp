#!/usr/bin/env python3
from pathlib import Path
import sys

APP_DIR = Path('/home/bcaddy/uconsole-k7bat/app/plugins/sidekick_setup_ui.py').resolve().parent.parent
CONSOLE_APP_DIR = APP_DIR.parent

print(f'CONSOLE_APP_DIR: {CONSOLE_APP_DIR}')
print(f'Checking for .apikey at: {CONSOLE_APP_DIR}/.apikey')

sys.path.insert(0, str(CONSOLE_APP_DIR))
try:
    from scripts.utils.sidekick_apikey import load_or_create_api_key
    print('Import succeeded')
    
    key = load_or_create_api_key(str(CONSOLE_APP_DIR))
    print(f'API Key returned: "{key}"')
except ImportError as e:
    print(f'Import failed: {e}')
    import traceback
    traceback.print_exc()
