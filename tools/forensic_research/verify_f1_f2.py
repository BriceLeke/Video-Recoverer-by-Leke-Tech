from parse_slice import BitReader, unescape_nalu

def analyze_p_slice(pos):
    with open('samples/corrupted/original.mp4', 'rb') as f:
        f.seek(pos)
        length = int.from_bytes(f.read(4), 'big')
        raw = f.read(50)
    rbsp = unescape_nalu(raw[1:])
    r = BitReader(rbsp)
    fmb = r.read_ue()
    st = r.read_ue()
    pps_id = r.read_ue()
    fn = r.read_bits(16)
    poc_lsb = r.read_bits(16)
    print(f"Slice at 0x{pos:X}: len={length}, fmb={fmb}, st={st}, pps={pps_id}, frame_num={fn}, poc_lsb={poc_lsb}")

# Let's check frame 1 at 0x4DA6:
analyze_p_slice(0x4DA6)

# Frame 1 length is 8575:
f1_end = 0x4DA6 + 8575 # 0x6F25
# Find frame 2:
with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(f1_end)
    d = f.read(50)
    print(f"After frame 1 (at 0x{f1_end:X}): {d[:20].hex()}")
    for off in range(30):
        l = int.from_bytes(d[off:off+4], 'big')
        if 10 < l < 100000 and (d[off+4] & 0x1f) in [1, 5]:
            f2_pos = f1_end + off
            print(f"Found frame 2 at 0x{f2_pos:X}")
            analyze_p_slice(f2_pos + 4)
            break
