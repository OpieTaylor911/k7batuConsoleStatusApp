#!/usr/bin/env python3
# Read the file with UTF-8 encoding
with open('app/k7bat-uconsole-status.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find apply_data function
start_idx = None
for i, line in enumerate(lines):
    if 'def apply_data(self, d):' in line:
        start_idx = i
        break

if start_idx is None:
    print("Could not find apply_data")
    exit(1)

print(f"Found apply_data at line {start_idx + 1}")

# Find where try block starts (should be after self._refreshing)
try_start = None
for i in range(start_idx, len(lines)):
    if '        try:' in lines[i]:
        try_start = i
        break

if try_start is None:
    print("Could not find try block")
    exit(1)

print(f"Found first try at line {try_start + 1}")

# Find where except block starts (should be after return False)
except_start = None
for i in range(start_idx, len(lines)):
    if '        except Exception as ex:' in lines[i]:
        except_start = i
        break

if except_start is None:
    print("Could not find except block")
    exit(1)

print(f"Found except at line {except_start + 1}")

# Find where try block should end (before the second try at line ~4937)
try_end = None
for i in range(try_start + 1, except_start):
    if '        try:' in lines[i] and i > try_start + 5:  # Skip the first try
        try_end = i - 1  # Line before second try starts
        break

if try_end is None:
    print("Could not find try end")
    exit(1)

print(f"Found try end at line {try_end + 1}")

# Rebuild the function with one try/except block covering everything
new_lines = lines[:start_idx]  # Everything before apply_data

# Add def and self._refreshing
new_lines.append(lines[start_idx])  # def apply_data(self, d):
new_lines.append(lines[start_idx+1])  # self._refreshing = False
new_lines.append('\n')
new_lines.append('        try:\n')

# Add lines from original try block (up to try_end)
for i in range(try_start + 1, try_end + 1):
    new_lines.append('    ' + lines[i])  # Add extra indent

# Add the except block
new_lines.append('\n')
new_lines.append('        except Exception as ex:\n')
new_lines.append('            import traceback\n')
new_lines.append('            try:\n')
new_lines.append('                debug_log = APP_DIR.parent / "data_debug.txt"\n')
new_lines.append('                with open(debug_log, "a") as f:\n')
new_lines.append('                    f.write(f"\\nEXCEPTION in apply_data: {ex}\\n")\n')
new_lines.append('                    f.write(traceback.format_exc())\n')
new_lines.append('                    f.write("\\n" + "="*60 + "\\n")\n')
new_lines.append('            except Exception:\n')
new_lines.append('                pass\n')
new_lines.append('            return False\n')

# Add everything after apply_data
for i in range(except_start, len(lines)):
    if '        except Exception as ex:' not in lines[i] or i == except_start:
        new_lines.append(lines[i])

# Write back
with open('app/k7bat-uconsole-status.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed apply_data function")
