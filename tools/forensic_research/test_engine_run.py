from src.h264.recovery_engine import H264RecoveryEngine
import subprocess
import os
import time

t0 = time.time()
engine = H264RecoveryEngine(source_path='samples/corrupted/original.mp4', chunk_size=1024*1024)
summary = engine.run_recovery()
print(f"Recovery completed in {time.time() - t0:.2f}s")
print(f"Total access units: {summary.total_access_units}")
print(f"IDR count: {summary.idr_count}, Non-IDR count: {summary.non_idr_count}")

# Export
out_path = "recovered/test_stream.h264"
bytes_w = engine.export_annex_b_stream(out_path)
print(f"Exported {bytes_w:,} bytes to {out_path}")

FFMPEG = r'C:\Users\LEKE_TECH\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe'
cmd = [FFMPEG, '-v', 'error', '-i', out_path, '-f', 'null', '-']
res = subprocess.run(cmd, capture_output=True, text=True)
print(f"FFmpeg ret: {res.returncode}")
print(f"FFmpeg stderr length: {len(res.stderr)}")
if res.stderr:
    print(f"Stderr: {res.stderr[:500]}")
