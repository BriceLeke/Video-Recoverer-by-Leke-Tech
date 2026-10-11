with open('samples/corrupted/original.mp4', 'rb') as f:
    data = f.read()

import re

# Find ASCII strings of length >= 6
strings = re.findall(b'[A-Za-z0-9_\\-\\.:/]{6,}', data)
print(f"Total strings found: {len(strings)}")
unique_strings = set(strings)
print(f"Unique strings: {len(unique_strings)}")
for s in sorted(unique_strings)[:50]:
    print(" ", s.decode('ascii', errors='ignore'))
