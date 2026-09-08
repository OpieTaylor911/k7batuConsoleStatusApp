#!/usr/bin/env python3
from pathlib import Path

# When running standalone from plugins directory
print("Running from:", Path(__file__).resolve())
APP_DIR = Path(__file__).resolve().parent.parent
CONSOLE_APP_DIR = APP_DIR.parent
print(f"APP_DIR: {APP_DIR}")
print(f"CONSOLE_APP_DIR: {CONSOLE_APP_DIR}")
