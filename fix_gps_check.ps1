import re

# Read the file with UTF-8 encoding
with open(r'y:\uConsoleDev\k7batuConsoleStatusApp\app\k7bat-uconsole-status.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the GPS line - use regex to match exactly
content = re.sub(
    r'(\s+)g = d\.get\("gps", \{\}\)',
    r'\1g = d.get("gps", {}) if isinstance(d.get("gps", {}), dict) else {}',
    content
)

# Write back with UTF-8 encoding
with open(r'y:\uConsoleDev\k7batuConsoleStatusApp\app\k7bat-uconsole-status.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed GPS dict check')
