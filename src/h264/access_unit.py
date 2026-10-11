"""
H.264 Access Unit (AU) representation and reconstruction.

In H.264, an Access Unit represents a single coded picture / video frame.
It is composed of an ordered set of NAL units:
[AUD] -> [SPS] -> [PPS] -> [SEI] -> Primary Coded Slices (VCL) -> [Redundant Slices]
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .nalu import NALU, NALUType


@dataclass
class AccessUnit:
    """
    Represents a reconstructed video sample (frame) composed of one or more NALUs.
    """
    index: int                          # Sequential sample index (0, 1, 2...)
    offset: int                         # Absolute start offset in input file
    total_size: int                     # Total byte length of all NALUs in this AU
    nalus: List[NALU] = field(default_factory=list)
    is_idr: bool = False                # True if AU contains an IDR slice
    is_keyframe: bool = False           # True if AU is an IDR or all-I picture
    slice_type: str = "UNKNOWN"         # 'I', 'P', 'B'
    frame_num: Optional[int] = None     # Decoded H.264 frame_num
    poc: Optional[int] = None           # Picture Order Count
    confidence: float = 1.0             # Diagnostic confidence [0.0, 1.0]
    is_truncated: bool = False          # True if final AU was interrupted by EOF
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    @property
    def vcl_nalu_count(self) -> int:
        return sum(1 for n in self.nalus if n.is_vcl)

    @property
    def has_parameter_sets(self) -> bool:
        return any(NALUType.is_parameter_set(n.nal_unit_type) for n in self.nalus)


class AccessUnitBuilder:
    """
    Builds AccessUnits by accumulating NAL units until picture boundaries are met.
    """

    def __init__(self):
        self._current_nalus: List[NALU] = []
        self._current_index = 0

    @classmethod
    def is_new_access_unit(cls, current_nalus: List[NALU], next_nalu: NALU) -> bool:
        """
        Determines whether next_nalu belongs to a new Access Unit
        per ISO/IEC 14496-10 Section 7.4.1.2.4.
        """
        if not current_nalus:
            return False

        # If next is an AUD, SPS, PPS, or SEI, and we already have VCL slices,
        # it definitely starts a new Access Unit
        has_vcl = any(n.is_vcl for n in current_nalus)
        if has_vcl and next_nalu.nal_unit_type in (
            NALUType.AUD,
            NALUType.SPS,
            NALUType.PPS,
            NALUType.SEI,
        ):
            return True

        # In typical single-slice screen recordings, every VCL slice (type 1 or 5)
        # with first_mb_in_slice == 0 starts a new picture
        if has_vcl and next_nalu.is_vcl:
            # If the next NALU is a slice and we already have a slice, check if next slice
            # is a new frame (e.g. if previous slice had full frame or next slice starts at mb 0)
            return True

        return False

    def add_nalu(self, nalu: NALU) -> Optional[AccessUnit]:
        """
        Adds a NAL unit. If this NAL unit begins a new Access Unit,
        finalizes and returns the previous Access Unit.
        """
        completed_au: Optional[AccessUnit] = None

        if self.is_new_access_unit(self._current_nalus, nalu):
            completed_au = self.finalize()

        self._current_nalus.append(nalu)
        return completed_au

    def finalize(self, is_truncated: bool = False) -> Optional[AccessUnit]:
        """
        Finalizes the current accumulated NAL units into an AccessUnit.
        """
        if not self._current_nalus:
            return None

        first_nalu = self._current_nalus[0]
        start_offset = first_nalu.offset
        total_size = sum(n.length for n in self._current_nalus)

        is_idr = any(n.is_idr for n in self._current_nalus)
        has_vcl = any(n.is_vcl for n in self._current_nalus)
        is_au_truncated = is_truncated or any(n.is_truncated for n in self._current_nalus)

        # Compute aggregate confidence
        confidences = [n.confidence for n in self._current_nalus]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        if is_au_truncated:
            avg_confidence *= 0.5

        # Infer slice type
        slice_type = "IDR" if is_idr else ("VCL" if has_vcl else "NON_VCL")

        au = AccessUnit(
            index=self._current_index,
            offset=start_offset,
            total_size=total_size,
            nalus=list(self._current_nalus),
            is_idr=is_idr,
            is_keyframe=is_idr,
            slice_type=slice_type,
            confidence=round(avg_confidence, 4),
            is_truncated=is_au_truncated,
            diagnostics={
                "nalu_count": len(self._current_nalus),
                "nalu_types": [n.nal_unit_type for n in self._current_nalus],
            },
        )

        self._current_index += 1
        self._current_nalus.clear()
        return au
