with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0x14A29)
    length = int.from_bytes(f.read(4), 'big')
    raw_nalu = f.read(100)

from parse_slice import BitReader, unescape_nalu

hdr = raw_nalu[0]
print(f"Frame at 0x14A29: length={length}, hdr=0x{hdr:02x}, type={hdr & 0x1f}, ref={(hdr>>5)&3}")
rbsp = unescape_nalu(raw_nalu[1:])
reader = BitReader(rbsp)
first_mb_in_slice = reader.read_ue()
slice_type = reader.read_ue()
pps_id = reader.read_ue()
print(f"  first_mb_in_slice: {first_mb_in_slice}")
print(f"  slice_type: {slice_type} (slice_type % 5 = {slice_type % 5})")
print(f"  pic_parameter_set_id: {pps_id}")
frame_num = reader.read_bits(4) # assuming log2_max_frame_num_minus4 = 0 (4 bits)
print(f"  frame_num (first 4 bits): {frame_num}")
