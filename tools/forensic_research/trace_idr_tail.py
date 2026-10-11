from parse_slice import BitReader, unescape_nalu

with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0x4B)
    raw = f.read(30)

rbsp = unescape_nalu(raw[1:])
r = BitReader(rbsp)
print("first_mb:", r.read_ue())
print("slice_type:", r.read_ue())
print("pps_id:", r.read_ue())
print("frame_num (16 bits):", r.read_bits(16))
print("idr_pic_id:", r.read_ue())

# Let's inspect the next bits!
remaining_bits = []
for _ in range(64):
    remaining_bits.append(str(r.read_bit()))
print("Next 64 bits:", ''.join(remaining_bits))
