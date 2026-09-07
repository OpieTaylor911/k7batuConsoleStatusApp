import subprocess

result = subprocess.run(["nmcli", "device", "wifi", "list", "ifname", "wlan0"], capture_output=True, text=True)
lines = result.stdout.strip().split("\n")
aps = []

for i, line in enumerate(lines):
    if i == 0:
        continue
    parts = line.split()
    
    bssid = "N/A"
    ssid = ""
    if len(parts) >= 2:
        bssid = parts[1]
    if len(parts) > 2:
        ssid = parts[2]
    
    is_valid = bssid != "N/A" and len(bssid) == 17
    
    print(f"Line {i}: valid={is_valid}, bssid={bssid[:8]}..., ssid={ssid}")
    if is_valid:
        aps.append((bssid, ssid))

print(f"\nTotal APs: {len(aps)}")
