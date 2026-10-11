import subprocess
import os

# Helper to build a standard H.264 SPS
class SPSBuilder:
    def __init__(self):
        self.bits = []

    def write_bit(self, b):
        self.bits.append(1 if b else 0)

    def write_bits(self, val, n):
        for i in reversed(range(n)):
            self.write_bit((val >> i) & 1)

    def write_ue(self, val):
        # Exp-Golomb write
        # val + 1 in binary has (len - 1) leading zeros
        v = val + 1
        length = v.bit_length()
        for _ in range(length - 1):
            self.write_bit(0)
        self.write_bits(v, length)

    def write_se(self, val):
        if val <= 0:
            code_num = -2 * val
        else:
            code_num = 2 * val - 1
        self.write_ue(code_num)

    def build_bytes(self):
        # Add rbsp_trailing_bits: 1 then 0s to byte align
        self.write_bit(1)
        while len(self.bits) % 8 != 0:
            self.write_bit(0)
        
        raw_bytes = bytearray()
        for i in range(0, len(self.bits), 8):
            b = 0
            for j in range(8):
                b = (b << 1) | self.bits[i+j]
            raw_bytes.append(b)
            
        # Escape emulation prevention: 0x000000..03
        escaped = bytearray()
        zeros = 0
        for b in raw_bytes:
            if zeros == 2 and b <= 3:
                escaped.append(3)
                zeros = 0
            escaped.append(b)
            if b == 0:
                zeros += 1
            else:
                zeros = 0
        return bytes(escaped)

def create_sps(width, height, profile=100, level=40):
    # width and height in pixels
    # mb_width = (width + 15) // 16
    # mb_height = (height + 15) // 16
    mb_w = (width + 15) // 16
    mb_h = (height + 15) // 16
    
    crop_right = (mb_w * 16 - width) // 2
    crop_bottom = (mb_h * 16 - height) // 2
    
    b = SPSBuilder()
    b.write_bits(profile, 8) # profile_idc (100 = High)
    b.write_bits(0, 8)       # constraint_set flags + reserved
    b.write_bits(level, 8)   # level_idc (40 = 4.0)
    b.write_ue(0)            # seq_parameter_set_id = 0
    
    if profile in [100, 110, 122, 244]:
        b.write_ue(1)        # chroma_format_idc = 1 (4:2:0)
        b.write_ue(0)        # bit_depth_luma_minus8 = 0
        b.write_ue(0)        # bit_depth_chroma_minus8 = 0
        b.write_bit(0)       # qpprime_y_zero_transform_bypass_flag = 0
        b.write_bit(0)       # seq_scaling_matrix_present_flag = 0
        
    b.write_ue(12)           # log2_max_frame_num_minus4 = 12 (16-bit frame_num!)
    b.write_ue(0)            # pic_order_cnt_type = 0
    b.write_ue(12)           # log2_max_pic_order_cnt_lsb_minus4 = 12 (16-bit POC!)
    b.write_ue(1)            # max_num_ref_frames = 1
    b.write_bit(0)           # gaps_in_frame_num_value_allowed_flag = 0
    b.write_ue(mb_w - 1)     # pic_width_in_mbs_minus1
    b.write_ue(mb_h - 1)     # pic_height_in_map_units_minus1
    b.write_bit(1)           # frame_mbs_only_flag = 1 (progressive)
    b.write_bit(1)           # direct_8x8_inference_flag = 1
    
    if crop_right > 0 or crop_bottom > 0:
        b.write_bit(1)       # frame_cropping_flag = 1
        b.write_ue(0)        # crop_left
        b.write_ue(crop_right) # crop_right
        b.write_ue(0)        # crop_top
        b.write_ue(crop_bottom) # crop_bottom
    else:
        b.write_bit(0)       # frame_cropping_flag = 0
        
    b.write_bit(0)           # vui_parameters_present_flag = 0
    
    return b.build_bytes()

def create_pps(entropy_coding=1):
    b = SPSBuilder()
    b.write_ue(0)            # pic_parameter_set_id = 0
    b.write_ue(0)            # seq_parameter_set_id = 0
    b.write_bit(entropy_coding) # entropy_coding_mode_flag (1=CABAC, 0=CAVLC)
    b.write_bit(0)           # bottom_field_pic_order_in_frame_present_flag = 0
    b.write_ue(0)            # num_slice_groups_minus1 = 0
    b.write_ue(0)            # num_ref_idx_l0_default_active_minus1 = 0
    b.write_ue(0)            # num_ref_idx_l1_default_active_minus1 = 0
    b.write_bit(0)           # weighted_pred_flag = 0
    b.write_bits(0, 2)       # weighted_bipred_idc = 0
    b.write_se(0)            # pic_init_qp_minus26 = 0
    b.write_se(0)            # pic_init_qs_minus26 = 0
    b.write_se(0)            # chroma_qp_index_offset = 0
    b.write_bit(1)           # deblocking_filter_control_present_flag = 1
    b.write_bit(0)           # constrained_intra_pred_flag = 0
    b.write_bit(0)           # redundant_pic_cnt_present_flag = 0
    b.write_bit(1)           # transform_8x8_mode_flag = 1
    b.write_bit(0)           # pic_scaling_matrix_present_flag = 0
    b.write_se(0)            # second_chroma_qp_index_offset = 0
    return b.build_bytes()

print("Created SPS & PPS generators.")
sps = create_sps(1080, 2400)
pps = create_pps(1)
print(f"SPS (1080x2400): 0x67 + {sps.hex()}")
print(f"PPS: 0x68 + {pps.hex()}")
