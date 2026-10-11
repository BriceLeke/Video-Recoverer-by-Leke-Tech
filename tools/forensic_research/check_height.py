import subprocess
import os
import re
from test_sps_pps import create_sps, create_pps

FFMPEG = r'C:\Users\LEKE_TECH\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'

with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0x47)
    length = int.from_bytes(f.read(4), 'big')
    idr_nalu = f.read(length)

annex_b = b'\x00\x00\x00\x01'

# We will test heights with step of 16 pixels (1 macroblock) from 1200 to 1700
# Galaxy A41 screen is 20:9 -> 720 x 1600 (aspect ratio 20:9 is 1600 / 720 = 2.222 = 20 / 9!)
for h in [1280, 1440, 1520, 1560, 1600]:
    sps = create_sps(720, h)
    pps = create_pps()
    stream = annex_b + bytes([0x67]) + sps + annex_b + bytes([0x68]) + pps + annex_b + idr_nalu
    with open('test_frame.h264', 'wb') as tf:
        tf.write(stream)
    cmd = [FFMPEG, '-debug', 'mb_type', '-v', 'debug', '-i', 'test_frame.h264', '-vframes', '1', '-f', 'null', '-']
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    # Check if there are any warnings/errors or MB counts in output
    mbs = [line for line in res.stderr.splitlines() if 'mb' in line.lower() or 'slice' in line.lower() or 'error' in line.lower()]
    print(f"Height {h}: total lines={len(res.stderr.splitlines())}, relevant lines={len(mbs)}")
    for line in mbs[-5:]:
        print(f"   {line}")

if os.path.exists('test_frame.h264'):
    os.remove('test_frame.h264')
