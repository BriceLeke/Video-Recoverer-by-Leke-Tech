with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0)
    data = f.read(108142592)

print(f"File size: {len(data)}")

# Let's inspect the first 10 video frames starting from 0x50
pos = 0x50
frames = []
for i in range(20):
    if pos + 4 > len(data):
        break
    length = int.from_bytes(data[pos:pos+4], 'big')
    if pos + 4 + length > len(data):
        print(f"Frame {i} at 0x{pos:X}: length={length} goes beyond EOF!")
        break
    hdr = data[pos+4]
    nal_type = hdr & 0x1F
    ref_idc = (hdr >> 5) & 3
    print(f"Frame {i:2d} at 0x{pos:06X}: length={length:6d} (0x{length:04x}), nal_hdr=0x{hdr:02x}, type={nal_type}, ref={ref_idc}")
    frames.append((pos, length, nal_type))
    
    # Check what comes after this frame
    end_of_frame = pos + 4 + length
    # Let's see what is at end_of_frame
    next_pos = None
    # Check if next 4 bytes is another NALU length:
    for test_offset in range(0, 100):
        tp = end_of_frame + test_offset
        if tp + 5 <= len(data):
            t_len = int.from_bytes(data[tp:tp+4], 'big')
            if 10 < t_len < 1000000:
                t_hdr = data[tp+4]
                if (t_hdr >> 7) == 0 and (t_hdr & 0x1F) in [1, 5, 6, 7, 8]:
                    gap = test_offset
                    next_pos = tp
                    gap_bytes = data[end_of_frame:end_of_frame+gap]
                    print(f"   Gap after frame {i}: {gap} bytes: hex={gap_bytes.hex()}")
                    break
    if next_pos is None:
        print(f"   Could not find next frame after 0x{end_of_frame:X} within 100 bytes!")
        break
    pos = next_pos
