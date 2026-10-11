"""
H.264 Bitstream Utilities.

Implements bit-level reading and writing with support for:
- Standard Exp-Golomb coded syntax elements: ue(v) and se(v)
- Arbitrary bit-width integer reading/writing: u(n)
- RBSP unescaping (stripping 0x000003 emulation prevention bytes)
- RBSP escaping (inserting 0x000003 emulation prevention bytes)
- rbsp_trailing_bits handling
"""

from typing import List, Tuple


def unescape_rbsp(data: bytes) -> bytes:
    """
    Remove emulation prevention bytes (0x03 inside 0x000003 sequences)
    to convert raw NAL unit byte stream (EBSP) into Raw Byte Sequence Payload (RBSP).
    """
    length = len(data)
    if length < 3:
        return data

    res = bytearray()
    i = 0
    while i < length:
        if i + 2 < length and data[i] == 0 and data[i + 1] == 0 and data[i + 2] == 3:
            res.append(0)
            res.append(0)
            i += 3
        else:
            res.append(data[i])
            i += 1
    return bytes(res)


def escape_rbsp(data: bytes) -> bytes:
    """
    Insert emulation prevention bytes (0x03) wherever 0x000000, 0x000001,
    0x000002, or 0x000003 would otherwise appear.
    Converts RBSP into EBSP.
    """
    res = bytearray()
    zeros = 0
    for byte in data:
        if zeros >= 2 and byte <= 3:
            res.append(3)
            zeros = 0
        res.append(byte)
        if byte == 0:
            zeros += 1
        else:
            zeros = 0
    return bytes(res)


class BitReader:
    """
    Sequential bit reader operating over a byte buffer.
    Supports standard ISO/IEC 14496-10 syntax elements.
    """

    def __init__(self, data: bytes):
        self.data = data
        self.total_bytes = len(data)
        self.byte_pos = 0
        self.bit_pos = 0  # 0 to 7, MSB first

    @property
    def bits_remaining(self) -> int:
        return (self.total_bytes - self.byte_pos) * 8 - self.bit_pos

    @property
    def has_more_rbsp_data(self) -> bool:
        """
        Implements more_rbsp_data() per H.264 section 7.2.
        Returns True if more data precedes the rbsp_trailing_bits.
        """
        if self.bits_remaining <= 0:
            return False

        # Look ahead from current bit position:
        # If the remaining bits consist of a '1' followed only by zeros, no more RBSP data.
        remaining = self.bits_remaining
        if remaining == 0:
            return False

        # Save state
        saved_byte = self.byte_pos
        saved_bit = self.bit_pos

        # Check if next bit is 1 and all subsequent bits are 0
        bit = self.read_bit()
        if bit == 1:
            all_zeros = True
            while self.bits_remaining > 0:
                if self.read_bit() != 0:
                    all_zeros = False
                    break
            self.byte_pos = saved_byte
            self.bit_pos = saved_bit
            return not all_zeros
        else:
            self.byte_pos = saved_byte
            self.bit_pos = saved_bit
            return True

    def read_bit(self) -> int:
        """Read a single bit (0 or 1)."""
        if self.byte_pos >= self.total_bytes:
            raise EOFError("Premature end of bitstream in BitReader")
        bit = (self.data[self.byte_pos] >> (7 - self.bit_pos)) & 1
        self.bit_pos += 1
        if self.bit_pos == 8:
            self.bit_pos = 0
            self.byte_pos += 1
        return bit

    def read_bits(self, n: int) -> int:
        """Read n bits as an unsigned integer (MSB first)."""
        if n < 0:
            raise ValueError(f"Cannot read negative number of bits: {n}")
        if n == 0:
            return 0
        if n > self.bits_remaining:
            raise EOFError(
                f"Requested {n} bits, but only {self.bits_remaining} bits remaining"
            )
        val = 0
        for _ in range(n):
            val = (val << 1) | self.read_bit()
        return val

    def read_ue(self) -> int:
        """Read an unsigned Exp-Golomb coded integer: ue(v)."""
        leading_zeros = 0
        while self.read_bit() == 0:
            leading_zeros += 1
            if leading_zeros > 32:
                raise ValueError("Excessive leading zeros (>32) in ue(v) decoding")
        if leading_zeros == 0:
            return 0
        suffix = self.read_bits(leading_zeros)
        return (1 << leading_zeros) - 1 + suffix

    def read_se(self) -> int:
        """Read a signed Exp-Golomb coded integer: se(v)."""
        code_num = self.read_ue()
        sign = -1 if (code_num % 2 == 0) else 1
        return sign * ((code_num + 1) // 2)

    def read_bool(self) -> bool:
        """Read 1 bit as a boolean: u(1)."""
        return self.read_bit() == 1

    def byte_align(self) -> None:
        """Align reader to next byte boundary."""
        if self.bit_pos != 0:
            self.bit_pos = 0
            self.byte_pos += 1


class BitWriter:
    """
    Sequential bit writer for synthesizing standard H.264 syntax elements.
    """

    def __init__(self):
        self._bits: List[int] = []

    @property
    def bit_count(self) -> int:
        return len(self._bits)

    def write_bit(self, b: int) -> None:
        """Write a single bit (0 or 1)."""
        self._bits.append(1 if b else 0)

    def write_bits(self, val: int, n: int) -> None:
        """Write an integer as n bits (MSB first)."""
        if n < 0:
            raise ValueError(f"Cannot write negative bit length: {n}")
        for i in reversed(range(n)):
            self.write_bit((val >> i) & 1)

    def write_bool(self, b: bool) -> None:
        """Write a boolean as 1 bit."""
        self.write_bit(1 if b else 0)

    def write_ue(self, val: int) -> None:
        """Write an unsigned integer using Exp-Golomb coding: ue(v)."""
        if val < 0:
            raise ValueError(f"Cannot encode negative integer with ue(v): {val}")
        v = val + 1
        bit_len = v.bit_length()
        # bit_len - 1 leading zeros
        for _ in range(bit_len - 1):
            self.write_bit(0)
        self.write_bits(v, bit_len)

    def write_se(self, val: int) -> None:
        """Write a signed integer using Exp-Golomb coding: se(v)."""
        if val <= 0:
            code_num = -2 * val
        else:
            code_num = 2 * val - 1
        self.write_ue(code_num)

    def write_rbsp_trailing_bits(self) -> None:
        """
        Appends rbsp_trailing_bits: one '1' bit followed by zero '0' bits
        until reaching the byte boundary.
        """
        self.write_bit(1)
        while len(self._bits) % 8 != 0:
            self.write_bit(0)

    def to_rbsp_bytes(self) -> bytes:
        """
        Return raw bytes without emulation prevention.
        Pads with zero bits if not byte aligned.
        """
        total = len(self._bits)
        padded_len = (total + 7) & ~7
        bits_copy = list(self._bits)
        while len(bits_copy) < padded_len:
            bits_copy.append(0)

        res = bytearray()
        for i in range(0, len(bits_copy), 8):
            b = 0
            for j in range(8):
                b = (b << 1) | bits_copy[i + j]
            res.append(b)
        return bytes(res)

    def to_ebsp_bytes(self) -> bytes:
        """
        Finalizes with trailing bits and returns escaped EBSP bytes.
        """
        self.write_rbsp_trailing_bits()
        rbsp = self.to_rbsp_bytes()
        return escape_rbsp(rbsp)
