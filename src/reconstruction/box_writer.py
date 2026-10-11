"""
Low-level ISOBMFF (ISO Base Media File Format) Box Serialization Utilities.

Implements byte-exact serialization for standard boxes, 64-bit large boxes,
full boxes (with version and flags), fixed-point numbers, and transformation matrices.
ISO/IEC 14496-12 compliant.
"""

import struct
from typing import List, Tuple, Union


class BoxWriter:
    """
    Utility class for writing binary ISOBMFF boxes.
    """

    @staticmethod
    def box(box_type: Union[str, bytes], payload: bytes) -> bytes:
        """
        Creates a standard 32-bit ISOBMFF box:
        [4 bytes: total_size][4 bytes: type][payload]
        """
        if isinstance(box_type, str):
            box_type = box_type.encode("ascii")
        if len(box_type) != 4:
            raise ValueError(f"Box type must be exactly 4 bytes, got {box_type!r}")

        total_size = 8 + len(payload)
        if total_size >= 0x100000000:
            raise ValueError(
                f"Box {box_type!r} size {total_size} exceeds 32-bit capacity. Use large_box."
            )
        return struct.pack(">I4s", total_size, box_type) + payload

    @staticmethod
    def large_box(box_type: Union[str, bytes], payload: bytes) -> bytes:
        """
        Creates a 64-bit ISOBMFF box (used when size >= 4 GB or for 64-bit compliance):
        [4 bytes: 0x00000001][4 bytes: type][8 bytes: total_size_uint64][payload]
        """
        if isinstance(box_type, str):
            box_type = box_type.encode("ascii")
        if len(box_type) != 4:
            raise ValueError(f"Box type must be exactly 4 bytes, got {box_type!r}")

        total_size = 16 + len(payload)
        return struct.pack(">I4sQ", 1, box_type, total_size) + payload

    @staticmethod
    def full_box(
        box_type: Union[str, bytes], version: int, flags: int, payload: bytes
    ) -> bytes:
        """
        Creates a FullBox:
        Standard box whose payload begins with [1 byte version][3 bytes flags].
        """
        if not (0 <= version <= 255):
            raise ValueError(f"FullBox version must be 0..255, got {version}")
        if not (0 <= flags <= 0xFFFFFF):
            raise ValueError(f"FullBox flags must be 0..0xFFFFFF, got {flags}")

        header = struct.pack(">B", version) + flags.to_bytes(3, "big")
        return BoxWriter.box(box_type, header + payload)

    @staticmethod
    def fixed_point_16_16(value: float) -> bytes:
        """Encodes float as 32-bit 16.16 fixed-point number."""
        integer_part = int(value)
        fractional_part = int((value - integer_part) * 65536.0)
        packed = ((integer_part & 0xFFFF) << 16) | (fractional_part & 0xFFFF)
        return struct.pack(">I", packed)

    @staticmethod
    def fixed_point_8_8(value: float) -> bytes:
        """Encodes float as 16-bit 8.8 fixed-point number (e.g. audio volume)."""
        integer_part = int(value)
        fractional_part = int((value - integer_part) * 256.0)
        packed = ((integer_part & 0xFF) << 8) | (fractional_part & 0xFF)
        return struct.pack(">H", packed)

    @staticmethod
    def unity_matrix() -> bytes:
        """
        Standard 36-byte unity display transformation matrix:
        [1.0, 0, 0,
         0, 1.0, 0,
         0, 0, 16384.0 (fixed 2.30 = 0x40000000)]
        """
        return struct.pack(
            ">9I",
            0x00010000, 0, 0,
            0, 0x00010000, 0,
            0, 0, 0x40000000,
        )

    @staticmethod
    def language_code(lang: str = "und") -> bytes:
        """
        Encodes 3-character ISO-639-2/T language code as packed 16-bit int.
        'und' = undefined = 0x55C4.
        """
        if len(lang) != 3:
            lang = "und"
        chars = [ord(c) - 0x60 for c in lang.lower()]
        val = ((chars[0] & 0x1F) << 10) | ((chars[1] & 0x1F) << 5) | (chars[2] & 0x1F)
        return struct.pack(">H", val)
