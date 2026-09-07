import re

# Read the file
with open('app/k7bat-uconsole-status.py', 'r') as f:
    content = f.read()

# Find and replace extract_wifi_signal_dbm function
old_func = '''    def extract_wifi_signal_dbm(self, wifi_rows):
        best = None
        for _iface, detail in wifi_rows:
            m = re.search(r"(-?\\d+(?:\\.\\d+)?)\\s*dBm", detail)
            if not m:
                continue
            try:
                val = float(m.group(1))
            except Exception:
                continue
            if best is None or val > best:
                best = val
        return best'''

new_func = '''    def extract_wifi_signal_dbm(self, wifi_rows):
        best = None
        # Handle list format: [(iface, detail), ...]
        if isinstance(wifi_rows, list):
            for _iface, detail in wifi_rows:
                m = re.search(r"(-?\\d+(?:\\.\\d+)?)\\s*dBm", detail)
                if not m:
                    continue
                try:
                    val = float(m.group(1))
                except Exception:
                    continue
                if best is None or val > best:
                    best = val
        # Handle dict format: {"signal_strength": 70}
        elif isinstance(wifi_rows, dict):
            signal = wifi_rows.get("signal_strength")
            if isinstance(signal, (int, float)):
                # Convert to dBm approximation
                best = -100 + (signal * 0.7)
        return best'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open('app/k7bat-uconsole-status.py', 'w') as f:
        f.write(content)
    print("Fixed extract_wifi_signal_dbm")
else:
    print("Function not found - may already be fixed or different format")

# Also fix update_connectivity_labels to handle dict
old_line = '''        wifi_rows = data.get("wifi", []) if isinstance(data.get("wifi", []), list) else []
        dbm = self.extract_wifi_signal_dbm(wifi_rows)'''

new_line = '''        wifi_data = data.get("wifi")
        # Handle both dict and list formats for Wi-Fi
        if isinstance(wifi_data, dict):
            wifi_rows = wifi_data  # Pass dict directly to extract function
        elif isinstance(wifi_data, list):
            wifi_rows = wifi_data
        else:
            wifi_rows = []
        dbm = self.extract_wifi_signal_dbm(wifi_rows)'''

if old_line in content:
    content = content.replace(old_line, new_line)
    with open('app/k7bat-uconsole-status.py', 'w') as f:
        f.write(content)
    print("Fixed update_connectivity_labels")
else:
    print("update_connectivity_labels line not found")
