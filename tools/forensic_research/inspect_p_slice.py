from parse_slice import BitReader, unescape_nalu

with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0x4DA6)
    raw = f.read(30)

print(f"NAL header at 0x4DA6: 0x{raw[0]:02x}")
rbsp = unescape_nalu(raw[1:])
print("RBSP hex:", rbsp[:20].hex())

for i in range(len(rbsp[:10])):
    print(f"{rbsp[i]:08b}", end=" ")
print()

r = BitReader(rbsp)
print("first_mb:", r.read_ue())
print("slice_type:", r.read_ue())
print("pps_id:", r.read_ue())
# Next bits:
bits = ''.join(str(r.read_bit()) for _ in range(32))
print("Next 32 bits:", bits)
