lines = open('/tmp/nm.txt').read().strip().split('\n')
for i, l in enumerate(lines[:15]):
    parts = l.split()
    print(f'{i}: fields={len(parts)} first="{parts[0] if parts else ""}"')
