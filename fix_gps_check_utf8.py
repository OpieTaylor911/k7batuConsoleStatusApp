import re

# Read the file
with open(r'y:\uConsoleDev\k7batuConsoleStatusApp\app\k7bat-uconsole-status.py', 'r') as f:
    content = f.read()

# Find and replace the GPS line - use regex to match exactly
content = re.sub(
    r'(\s+)g = d\.get\(\
gps\, \{\}\)',
    r'\1g = d.get(\gps\, {}) if isinstance(d.get(\gps\, {}), dict) else {}',
    content
)

# Write back
with open(r'y:\uConsoleDev\k7batuConsoleStatusApp\app\k7bat-uconsole-status.py', 'w') as f:
    f.write(content)

print('Fixed GPS dict check')
