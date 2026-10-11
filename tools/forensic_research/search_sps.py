import os

def search_sps_and_pps(filepath):
    filesize = os.path.getsize(filepath)
    print(f"File size: {filesize}")
    
    with open(filepath, 'rb') as f:
        data = f.read()
        
    print(f"Read {len(data)} bytes.")
    
    # In H.264:
    # NAL header: forbidden_zero_bit (1 bit = 0), nal_ref_idc (2 bits), nal_unit_type (5 bits)
    # For SPS: nal_unit_type == 7.
    # Typically nal_ref_idc is 3 (11 in binary), but could be 1, 2, or 3.
    # So header byte is 0x67, 0x47, 0x27, or 0x07 (though 0x07 would have ref_idc=0 which is invalid for SPS in spec, but let's check all (b & 0x1f) == 7).
    #
    # Following the NAL header byte:
    # profile_idc: 66 (Baseline), 77 (Main), 88 (Extended), 100 (High), 110 (High 10), 122 (High 4:2:2), 244 (High 4:4:4)
    # constraint_set0..5_flag + reserved_zero_2bits
    # level_idc: 10, 11, 12, 13, 20, 21, 22, 30, 31, 32, 40, 41, 42, 50, 51, 52
    # seq_parameter_set_id: ue(v) (usually 0 -> '1' bit)
    
    # Let's search for (b & 0x1F) == 7 where next byte is a known profile_idc!
    profiles = {66, 77, 88, 100, 110, 122, 244}
    levels = {10, 11, 12, 13, 20, 21, 22, 30, 31, 32, 40, 41, 42, 50, 51, 52}
    
    found_sps = []
    for i in range(len(data) - 4):
        b = data[i]
        if (b >> 7) == 0 and (b & 0x1F) == 7:
            p_idc = data[i+1]
            if p_idc in profiles:
                l_idc = data[i+3]
                if l_idc in levels:
                    found_sps.append((i, b, p_idc, data[i+2], l_idc))
                    
    print(f"Total potential SPS byte positions: {len(found_sps)}")
    for pos, hdr, prof, cflags, lev in found_sps:
        prefix = data[max(0, pos-4):pos]
        surrounding = data[pos:pos+32]
        print(f"  Pos: 0x{pos:X} ({pos}): Hdr=0x{hdr:02x}, Profile={prof}, Level={lev}, Prefix={prefix.hex()}, Content={surrounding.hex()}")

search_sps_and_pps('samples/corrupted/original.mp4')
