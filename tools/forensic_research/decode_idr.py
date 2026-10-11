from parse_slice import BitReader, unescape_nalu

with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0x4B) # NAL header byte 0x65
    raw = f.read(30)

rbsp = unescape_nalu(raw[1:])
print("RBSP hex:", rbsp[:20].hex())

reader = BitReader(rbsp)
# 1. first_mb_in_slice: ue(v)
first_mb = reader.read_ue()
print(f"first_mb_in_slice: {first_mb}")

# 2. slice_type: ue(v)
slice_type = reader.read_ue()
print(f"slice_type: {slice_type} ({['P','B','I','SP','SI'][slice_type%5]})")

# 3. pic_parameter_set_id: ue(v)
pps_id = reader.read_ue()
print(f"pic_parameter_set_id: {pps_id}")

# 4. frame_num: u(v) (how many bits? Let's test 4..16 bits)
# In H.264, log2_max_frame_num_minus4 is between 0 and 12, so frame_num is 4..16 bits.
# For IDR frame, frame_num is ALWAYS 0!
# Let's see what the next bits are:
for fn_len in range(4, 17):
    # reset reader
    r = BitReader(rbsp)
    r.read_ue()
    r.read_ue()
    r.read_ue()
    fn = r.read_bits(fn_len)
    if fn == 0:
        # idr_pic_id: ue(v)
        idr_id = r.read_ue()
        print(f"If frame_num is {fn_len} bits (val={fn}): idr_pic_id={idr_id}")
        # Next: pic_order_cnt_type
        # If pic_order_cnt_type == 0: pic_order_cnt_lsb is u(v)
        # If pic_order_cnt_type == 1: delta_pic_order_cnt[0] is se(v)
        # If pic_order_cnt_type == 2: nothing in slice header for POC!
        # If redundant_pic_cnt_present_flag in PPS: redundant_pic_cnt: ue(v)
        # slice_qp_delta: se(v)
