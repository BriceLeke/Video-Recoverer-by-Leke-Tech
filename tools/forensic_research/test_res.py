import os
import subprocess
from test_sps_pps import create_sps, create_pps

FFMPEG = r"C:\Users\LEKE_TECH\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"

# Extract first 10 frames
with open('samples/corrupted/original.mp4', 'rb') as f:
    data = f.read(108142592)

# Start scanning for frames
pos = 0x47
frames = []
while pos < len(data) and len(frames) < 15:
    length = int.from_bytes(data[pos:pos+4], 'big')
    if length <= 0 or pos + 4 + length > len(data):
        break
    hdr = data[pos+4]
    nal_type = hdr & 0x1F
    if nal_type in [1, 5]:
        nalu_data = data[pos+4:pos+4+length]
        frames.append((pos, length, nal_type, nalu_data))
        end = pos + 4 + length
        # find next
        found = False
        for off in range(0, 500):
            p = end + off
            if p + 5 <= len(data):
                l = int.from_bytes(data[p:p+4], 'big')
                if 10 < l < 1000000 and (data[p+4] & 0x1F) in [1, 5] and (data[p+4] >> 7) == 0:
                    pos = p
                    found = True
                    break
        if not found:
            break
    else:
        pos += 1

print(f"Extracted {len(frames)} frames.")
for idx, fr in enumerate(frames):
    print(f"Frame {idx}: at 0x{fr[0]:X}, len={fr[1]}, type={fr[2]}")

# Test candidate resolutions:
candidates = [
    (1080, 2400),
    (720, 1600),
    (1080, 2340),
    (1080, 1920),
    (720, 1280),
    (540, 1200),
    (1080, 2160),
    (1080, 2520),
]

annex_b_prefix = b'\x00\x00\x00\x01'

for w, h in candidates:
    sps = create_sps(w, h)
    pps = create_pps()
    
    stream = bytearray()
    stream.extend(annex_b_prefix + bytes([0x67]) + sps)
    stream.extend(annex_b_prefix + bytes([0x68]) + pps)
    
    for fr in frames:
        stream.extend(annex_b_prefix + fr[3])
        
    test_file = f"test_{w}x{h}.h264"
    with open(test_file, 'wb') as tf:
        tf.write(stream)
        
    # Run ffmpeg to test decoding
    cmd = [FFMPEG, "-v", "error", "-i", test_file, "-f", "null", "-"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(f"Res {w}x{h}: returncode={res.returncode}, stderr='{res.stderr.strip()}'")
    if os.path.exists(test_file):
        os.remove(test_file)
