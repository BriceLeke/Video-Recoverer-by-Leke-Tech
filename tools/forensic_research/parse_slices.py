from parse_slice import BitReader, unescape_nalu

def parse_slice_at(filepath, pos):
    with open(filepath, 'rb') as f:
        f.seek(pos)
        length = int.from_bytes(f.read(4), 'big')
        raw_nalu = f.read(100)
    hdr = raw_nalu[0]
    nal_type = hdr & 0x1f
    rbsp = unescape_nalu(raw_nalu[1:])
    reader = BitReader(rbsp)
    first_mb = reader.read_ue()
    st = reader.read_ue()
    pps_id = reader.read_ue()
    fn = reader.read_bits(4)
    print(f"Pos 0x{pos:06X}: len={length:6d}, type={nal_type}, slice_type={st} ({['P','B','I','SP','SI'][st%5]}), pps={pps_id}, fn={fn}")

for pos in [0x14A29, 0x19BF1, 0x1EECC, 0x23BE1, 0x28A84, 0x2D649]:
    parse_slice_at('samples/corrupted/original.mp4', pos)
