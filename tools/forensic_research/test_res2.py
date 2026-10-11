import subprocess
import os
from test_sps_pps import create_sps, create_pps

FFMPEG = r'C:\Users\LEKE_TECH\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'

with open('samples/corrupted/original.mp4', 'rb') as f:
    data = f.read(108142592)

pos = 0x47
frames = []
while pos < len(data) and len(frames) < 30:
    length = int.from_bytes(data[pos:pos+4], 'big')
    if length <= 0 or pos + 4 + length > len(data): break
    hdr = data[pos+4]
    nal_type = hdr & 0x1F
    if nal_type in [1, 5]:
        frames.append(data[pos+4:pos+4+length])
        end = pos + 4 + length
        found = False
        for off in range(0, 500):
            p = end + off
            if p + 5 <= len(data):
                l = int.from_bytes(data[p:p+4], 'big')
                if 10 < l < 1000000 and (data[p+4] & 0x1F) in [1, 5] and (data[p+4] >> 7) == 0:
                    pos = p
                    found = True
                    break
        if not found: break
    else: pos += 1

annex_b = b'\x00\x00\x00\x01'
candidates = [
    (720, 1280),
    (720, 1600),
    (720, 1560),
    (720, 1520),
    (720, 1440),
    (1080, 2400),
    (1080, 1920),
]

for w, h in candidates:
    sps = create_sps(w, h)
    pps = create_pps()
    stream = annex_b + bytes([0x67]) + sps + annex_b + bytes([0x68]) + pps
    for fr in frames:
        stream += annex_b + fr
    with open('test_try.h264', 'wb') as tf:
        tf.write(stream)
    cmd = [FFMPEG, '-v', 'error', '-i', 'test_try.h264', '-f', 'null', '-']
    res = subprocess.run(cmd, capture_output=True, text=True)
    err = res.stderr.strip()
    print(f"{w}x{h}: ret={res.returncode}, err_len={len(err)}, err='{err[:100]}'")

if os.path.exists('test_try.h264'):
    os.remove('test_try.h264')
