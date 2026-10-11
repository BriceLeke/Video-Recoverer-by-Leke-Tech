with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0x47)
    length = int.from_bytes(f.read(4), 'big')
    print(f"At 0x47: length={length}")
    raw = f.read(30)
    print("Raw bytes:", raw.hex())
    hdr = raw[0]
    print(f"Hdr: 0x{hdr:02x}, type={hdr & 0x1f}, ref={(hdr>>5)&3}")
    
    from parse_slice import BitReader, unescape_nalu
    rbsp = unescape_nalu(raw[1:])
    reader = BitReader(rbsp)
    first_mb = reader.read_ue()
    st = reader.read_ue()
    pps_id = reader.read_ue()
    print(f"first_mb={first_mb}, slice_type={st} ({['P','B','I','SP','SI'][st%5]}), pps_id={pps_id}")
    
    # What comes after length 19787?
    next_pos = 0x47 + 4 + length
    print(f"End of frame at 0x{next_pos:X}")
    f.seek(next_pos)
    after = f.read(20)
    print(f"Bytes at 0x{next_pos:X}: {after.hex()}")
