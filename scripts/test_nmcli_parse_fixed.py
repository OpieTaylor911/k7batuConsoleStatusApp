import subprocess

result = subprocess.run(["nmcli", "device", "wifi", "list", "ifname", "wlan0"], capture_output=True, text=True)
lines = result.stdout.strip().split("\n")
aps = []

for i, line in enumerate(lines):
    if i == 0:
        continue
    parts = line.split()
    
    # Handle the * marker on some lines (fields=10 vs fields=9)
    if len(parts) >= 2:
        if parts[0] == '*':
            bssid = parts[1]
            ssid = parts[2] if len(parts) > 2 else ""
        else:
            bssid = parts[0]
            ssid = parts[1] if len(parts) > 1 else ""
    else:
        continue
    
    is_valid_bssid = bssid and len(bssid) == 17 and ':' in bssid
    print(f"Line {i}: valid={is_valid_bssid}, bssid={bssid[:8]}..., ssid={ssid}")
    if is_valid_bssid:
        aps.append((bssid, ssid))

print(f"\nTotal APs: {len(aps)}")
