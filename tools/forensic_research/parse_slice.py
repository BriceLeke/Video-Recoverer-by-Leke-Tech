# Bit reader for Exp-Golomb decoding
class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.byte_pos = 0
        self.bit_pos = 0  # 0 to 7, MSB first

    def read_bit(self) -> int:
        if self.byte_pos >= len(self.data):
            raise EOFError("BitReader EOF")
        bit = (self.data[self.byte_pos] >> (7 - self.bit_pos)) & 1
        self.bit_pos += 1
        if self.bit_pos == 8:
            self.bit_pos = 0
            self.byte_pos += 1
        return bit

    def read_bits(self, n: int) -> int:
        val = 0
        for _ in range(n):
            val = (val << 1) | self.read_bit()
        return val

    def read_ue(self) -> int:
        leading_zeros = 0
        while self.read_bit() == 0:
            leading_zeros += 1
            if leading_zeros > 32:
                raise ValueError("Too many leading zeros in ue(v)")
        if leading_zeros == 0:
            return 0
        suffix = self.read_bits(leading_zeros)
        return (1 << leading_zeros) - 1 + suffix

    def read_se(self) -> int:
        code_num = self.read_ue()
        sign = -1 if (code_num % 2 == 0) else 1
        return sign * ((code_num + 1) // 2)

# Unescape emulation prevention bytes (0x000003 -> 0x0000)
def unescape_nalu(data: bytes) -> bytes:
    res = bytearray()
    i = 0
    while i < len(data):
        if i + 2 < len(data) and data[i] == 0 and data[i+1] == 0 and data[i+2] == 3:
            res.append(0)
            res.append(0)
            i += 3
        else:
            res.append(data[i])
            i += 1
    return bytes(res)

with open('samples/corrupted/original.mp4', 'rb') as f:
    f.seek(0x54) # NAL header byte of first IDR frame
    raw_nalu = f.read(100)

rbsp = unescape_nalu(raw_nalu[1:]) # skip NAL header 0x45
reader = BitReader(rbsp)
first_mb_in_slice = reader.read_ue()
slice_type = reader.read_ue()
pps_id = reader.read_ue()

print(f"IDR Frame 0:")
print(f"  first_mb_in_slice: {first_mb_in_slice}")
print(f"  slice_type: {slice_type} (slice_type % 5 = {slice_type % 5})") # 2 = I-slice, 7 = all I-slice
print(f"  pic_parameter_set_id: {pps_id}")
