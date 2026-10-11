"""
H.264 Network Abstraction Layer Unit (NALU) definitions and parser.

Defines:
- Standard H.264 NAL unit types (Table 7-1)
- NALU container object with byte offsets, lengths, diagnostics, and confidence scores
- Header parsing and validation logic
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Dict, Any


class NALUType(IntEnum):
    """H.264 NAL Unit Types per ITU-T H.264 Table 7-1."""
    UNSPECIFIED = 0
    NON_IDR = 1          # Coded slice of a non-IDR picture
    SLICE_PART_A = 2     # Coded slice data partition A
    SLICE_PART_B = 3     # Coded slice data partition B
    SLICE_PART_C = 4     # Coded slice data partition C
    IDR = 5              # Coded slice of an IDR picture
    SEI = 6              # Supplemental enhancement information
    SPS = 7              # Sequence parameter set
    PPS = 8              # Picture parameter set
    AUD = 9              # Access unit delimiter
    END_OF_SEQUENCE = 10 # End of sequence
    END_OF_STREAM = 11   # End of stream
    FILLER = 12          # Filler data
    SPS_EXT = 13         # Sequence parameter set extension
    PREFIX = 14          # Prefix NAL unit
    SUBSET_SPS = 15      # Subset sequence parameter set
    DPS = 16             # Depth parameter set
    RESERVED_17 = 17
    RESERVED_18 = 18
    AUXILIARY_SLICE = 19
    EXTENSION = 20
    RESERVED_21 = 21
    RESERVED_22 = 22
    RESERVED_23 = 23
    UNSPECIFIED_24 = 24
    UNSPECIFIED_25 = 25
    UNSPECIFIED_26 = 26
    UNSPECIFIED_27 = 27
    UNSPECIFIED_28 = 28
    UNSPECIFIED_29 = 29
    UNSPECIFIED_30 = 30
    UNSPECIFIED_31 = 31

    @classmethod
    def is_vcl(cls, nalu_type: int) -> bool:
        """Returns True if the NAL unit is a Video Coding Layer (VCL) NAL unit (types 1 to 5)."""
        return 1 <= nalu_type <= 5

    @classmethod
    def is_parameter_set(cls, nalu_type: int) -> bool:
        """Returns True if NAL unit is SPS, PPS, or subset SPS."""
        return nalu_type in (cls.SPS, cls.PPS, cls.SUBSET_SPS)


@dataclass
class NALU:
    """
    Represents an extracted H.264 NAL unit with forensic provenance.
    """
    offset: int                # Absolute byte offset in source file (points to length prefix or start code)
    payload_offset: int        # Byte offset where the NAL unit header begins
    length: int                # Length of NAL unit in bytes (excluding length prefix or start code)
    header_byte: int           # First byte of the NAL unit
    nal_ref_idc: int           # 2-bit priority indicator (0 = disposable, 1-3 = reference)
    nal_unit_type: int         # 5-bit NAL unit type (1..31)
    forbidden_zero_bit: int    # Must be 0
    is_truncated: bool = False # Set True if NAL unit was cut off by unexpected EOF
    confidence: float = 1.0    # Confidence score [0.0, 1.0]
    detection_method: str = "unknown" # e.g. "avcc_4byte", "annex_b_4byte", "annex_b_3byte"
    raw_data: Optional[bytes] = None  # Full NAL unit payload including header byte (optional in streaming)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_idr(self) -> bool:
        return self.nal_unit_type == NALUType.IDR

    @property
    def is_vcl(self) -> bool:
        return NALUType.is_vcl(self.nal_unit_type)

    @property
    def type_name(self) -> str:
        try:
            return NALUType(self.nal_unit_type).name
        except ValueError:
            return f"UNKNOWN_{self.nal_unit_type}"

    @classmethod
    def parse_header(cls, header_byte: int) -> tuple[int, int, int]:
        """
        Parses NAL unit header byte.
        Returns: (forbidden_zero_bit, nal_ref_idc, nal_unit_type)
        """
        forbidden_zero_bit = (header_byte >> 7) & 1
        nal_ref_idc = (header_byte >> 5) & 3
        nal_unit_type = header_byte & 0x1F
        return forbidden_zero_bit, nal_ref_idc, nal_unit_type

    @classmethod
    def validate_header(cls, header_byte: int) -> tuple[bool, str]:
        """
        Performs forensic sanity checks on a NAL unit header byte.
        Returns (is_valid, reason).
        """
        forbidden, ref_idc, ntype = cls.parse_header(header_byte)
        if forbidden != 0:
            return False, f"forbidden_zero_bit is 1 (header=0x{header_byte:02x})"
        if ntype == 0:
            return False, "nal_unit_type is 0 (unspecified)"
        if ntype == NALUType.IDR and ref_idc == 0:
            return False, f"IDR NAL unit (type 5) cannot have nal_ref_idc == 0"
        if ntype == NALUType.SPS and ref_idc == 0:
            return False, f"SPS NAL unit (type 7) cannot have nal_ref_idc == 0"
        if ntype == NALUType.PPS and ref_idc == 0:
            return False, f"PPS NAL unit (type 8) cannot have nal_ref_idc == 0"
        return True, "Valid"
