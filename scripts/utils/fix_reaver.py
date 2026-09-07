import re

# Read the file
with open('/home/bcaddy/uconsole-k7bat/plugins/reaver/reaver_ui.py', 'r') as f:
    lines = f.readlines()

# Fix line 43 and 61 (0-indexed: 42, 60)
for i in range(len(lines)):
    if '"iwconfig", "2>&1"' in lines[i]:
        lines[i] = lines[i].replace('"iwconfig", "2>&1"', '"iwconfig"')

# Write back
with open('/home/bcaddy/uconsole-k7bat/plugins/reaver/reaver_ui.py', 'w') as f:
    f.writelines(lines)

print('Fixed!')
