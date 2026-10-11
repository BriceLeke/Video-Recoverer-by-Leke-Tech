import subprocess
import os
import time
from src.h264.sps import SPSSynthesizer
from src.h264.pps import PPSSynthesizer

FFMPEG = r'C:\Users\LEKE_TECH\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'

t0 = time.time()
with open('samples/corrupted/original.mp4', 'rb') as f:
    data = f.read(108142592)

pos = 0x47
total_len = len(data)
frames = []
while pos < total_len - 8:
    length = int.from_bytes(data[pos:pos+4], 'big')
    if 10 < length < 2000000 and (pos + 4 + length) <= total_len:
        hdr = data[pos+4]
        ntype = hdr & 0x1F
        if (hdr >> 7) == 0 and ntype in (1, 5):
            fb = data[pos+5]
            if (ntype == 5 and fb == 0x88) or (ntype == 1 and fb == 0x9A):
                frames.append((pos+4, length))
                end_pos = pos + 4 + length
                found_next = False
                for search_off in range(0, min(20000, total_len - end_pos - 8)):
                    p = end_pos + search_off
                    l = int.from_bytes(data[p:p+4], 'big')
                    if 10 < l < 2000000 and (p + 4 + l) <= total_len:
                        h = data[p+4]
                        nt = h & 0x1F
                        if (h >> 7) == 0 and nt in (1, 5):
                            if (nt == 5 and data[p+5] == 0x88) or (nt == 1 and data[p+5] == 0x9A):
                                pos = p
                                found_next = True
                                break
                if found_next:
                    continue
                else:
                    pos = end_pos
                    continue
    pos += 1

print(f"Scan took {time.time() - t0:.2f}s. Total frames: {len(frames)}")

# Export to full_test.h264
annex_b = b'\x00\x00\x00\x01'
sps_nal = SPSSynthesizer.synthesize(width=720, height=1280)
pps_nal = PPSSynthesizer.synthesize()

with open('full_test.h264', 'wb') as out_f:
    out_f.write(annex_b + sps_nal)
    out_f.write(annex_b + pps_nal)
    for p, l in frames:
        out_f.write(annex_b + data[p:p+l])

filesize = os.path.getsize('full_test.h264')
print(f"Exported full_test.h264: {filesize:,} bytes ({filesize / 1024 / 1024:.2f} MB)")

# Run FFmpeg to verify full decode
t1 = time.time()
cmd = [FFMPEG, '-v', 'error', '-i', 'full_test.h264', '-f', 'null', '-']
res = subprocess.run(cmd, capture_output=True, text=True)
print(f"FFmpeg decoding completed in {time.time() - t1:.2f}s")
print(f"FFmpeg exit code: {res.returncode}")
err_msg = res.stderr.strip()
print(f"FFmpeg stderr length: {len(err_msg)}")
if err_msg:
    print(f"Stderr: {err_msg[:500]}")
