result = open('/tmp/wlan1_scan.txt').read()
lines = result.strip().split('\n')
aps = []
for i, line in enumerate(lines):
    if i == 0:
        continue
    if not line.strip():
        continue
    parts = line.split()
    if len(parts) >= 2:
        if parts[0] == '*':
            bssid = parts[1]
            ssid = parts[2] if len(parts) > 2 else ''
        else:
            bssid = parts[0]
            ssid = parts[1] if len(parts) > 1 else ''
        if bssid and len(bssid) == 17 and ':' in bssid:
            aps.append((bssid, ssid))
print(f'Found {len(aps)} access points')
if aps:
    print('First 5:')
    for b,s in aps[:5]:
        print(f'  {b}: {s}')
