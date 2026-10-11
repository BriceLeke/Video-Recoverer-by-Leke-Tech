with open('samples/corrupted/original.mp4', 'rb') as f:
    data = f.read()

print("Scanning all 4-byte length prefixes for type 7 (SPS) and type 8 (PPS)...")
sps_found = []
pps_found = []

for i in range(len(data) - 8):
    length = int.from_bytes(data[i:i+4], 'big')
    if 4 <= length <= 500: # SPS/PPS are small, usually 10-100 bytes
        hdr = data[i+4]
        if (hdr >> 7) == 0:
            nal_type = hdr & 0x1F
            if nal_type == 7:
                sps_found.append((i, length, hdr, data[i+4:i+4+length]))
            elif nal_type == 8:
                pps_found.append((i, length, hdr, data[i+4:i+4+length]))

print(f"SPS candidates with 4-byte length: {len(sps_found)}")
for s in sps_found:
    print(f"  Pos 0x{s[0]:X}: len={s[1]}, hdr=0x{s[2]:02x}, data={s[3].hex()}")

print(f"PPS candidates with 4-byte length: {len(pps_found)}")
for p in pps_found:
    print(f"  Pos 0x{p[0]:X}: len={p[1]}, hdr=0x{p[2]:02x}, data={p[3].hex()}")
