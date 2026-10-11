from parse_slice import BitReader, unescape_nalu

with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0x47)
    length = int.from_bytes(f.read(4), 'big')
    raw = f.read(50)

print(f"IDR slice at 0x47, length={length}")
hdr = raw[0]
print(f"NAL header: 0x{hdr:02x}")
rbsp = unescape_nalu(raw[1:])
print("RBSP first 16 bytes:", rbsp[:16].hex())

# Let's inspect the bits
bits = []
for b in rbsp[:16]:
    bits.append(f"{b:08b}")
bitstr = ''.join(bits)
print("Bits:", bitstr)

# In slice_header for IDR (nal_unit_type == 5):
# first_mb_in_slice: ue(v)
# slice_type: ue(v)
# pic_parameter_set_id: ue(v)
# frame_num: u(v) (number of bits depends on log2_max_frame_num_minus4 + 4 in SPS)
# idr_pic_id: ue(v)
# if pic_order_cnt_type == 0: pic_order_cnt_lsb: u(v) (log2_max_pic_order_cnt_lsb_minus4 + 4 bits)
# if redundant_pic_cnt_present_flag: redundant_pic_cnt: ue(v)
# slice_qp_delta: se(v)
# if deblocking_filter_control_present_flag:
#    disable_deblocking_filter_idc: ue(v)
#    if disable_deblocking_filter_idc != 1:
#       slice_alpha_c0_offset_div2: se(v)
#       slice_beta_offset_div2: se(v)
