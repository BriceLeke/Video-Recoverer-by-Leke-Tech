import time

start_t = time.time()

with open('samples/corrupted/original.mp4', 'rb') as f:
    data = f.read(108142592)

print(f"Read file in {time.time() - start_t:.2f}s")

# Let's scan using our fast, exact NALU validator
pos = 0x47 # mdat start
total_len = len(data)
frames = []

while pos < total_len - 8:
    length = int.from_bytes(data[pos:pos+4], 'big')
    if 10 < length < 2000000 and (pos + 4 + length) <= total_len:
        hdr = data[pos+4]
        ntype = hdr & 0x1F
        if (hdr >> 7) == 0 and ntype in (1, 5):
            # Check slice header validation
            first_byte = data[pos+5] if pos+5 < total_len else 0
            is_valid_slice = False
            if ntype == 5 and (first_byte == 0x88): # IDR slice with first_mb=0, slice_type=7, pps=0
                is_valid_slice = True
            elif ntype == 1 and (first_byte == 0x9A): # P slice with first_mb=0, slice_type=5, pps=0
                is_valid_slice = True
            elif (first_byte & 0x80) != 0: # first_mb == 0
                is_valid_slice = True
                
            if is_valid_slice:
                frames.append((pos, length, ntype, hdr))
                # Advance directly to the end of this frame!
                end_pos = pos + 4 + length
                # Search for the next frame starting from end_pos
                # Look ahead up to 20,000 bytes
                found_next = False
                for search_off in range(0, min(20000, total_len - end_pos - 8)):
                    p = end_pos + search_off
                    l = int.from_bytes(data[p:p+4], 'big')
                    if 10 < l < 2000000 and (p + 4 + l) <= total_len:
                        h = data[p+4]
                        nt = h & 0x1F
                        if (h >> 7) == 0 and nt in (1, 5):
                            fb = data[p+5]
                            if (nt == 5 and fb == 0x88) or (nt == 1 and fb == 0x9A):
                                pos = p
                                found_next = True
                                break
                if found_next:
                    continue
                else:
                    pos = end_pos
                    continue
    pos += 1

print(f"Fast scan completed in {time.time() - start_t:.2f}s!")
print(f"Total video frames found: {len(frames)}")
idr_count = sum(1 for f in frames if f[2] == 5)
p_count = sum(1 for f in frames if f[2] == 1)
print(f"IDR frames: {idr_count}, P frames: {p_count}")
print(f"First frame at 0x{frames[0][0]:X}, length={frames[0][1]}")
print(f"Last frame at 0x{frames[-1][0]:X}, length={frames[-1][1]}")
