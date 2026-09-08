#!/usr/bin/env python3
"""Add debug prints to sidekick_setup_ui.py"""

import re

# Read the file
with open('/home/bcaddy/uconsole-k7bat/app/plugins/sidekick_setup_ui.py', 'r') as f:
    content = f.read()

# Find line 169 (self.api_key =) and insert debug before it
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'self.api_key =' in line and i > 165 and i < 175:
        # Insert debug lines before self.api_key
        indent = '        '
        debug_lines = [
            f'{indent}print(f"DEBUG: load_or_create_api_key = {load_or_create_api_key}")',
            f'{indent}print(f"DEBUG: CONSOLE_APP_DIR = {CONSOLE_APP_DIR}")'
        ]
        lines[i:i] = debug_lines
        break

# Write back
with open('/home/bcaddy/uconsole-k7bat/app/plugins/sidekick_setup_ui.py', 'w') as f:
    f.write('\n'.join(lines))

print("Debug added")
