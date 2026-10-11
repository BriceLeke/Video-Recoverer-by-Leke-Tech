"""
H.264 Slice Header Parser.

Implements ISO/IEC 14496-10 Section 7.3.3 Slice Header syntax parsing.
Used to extract frame_num, slice_type (I/P/B), POC (Picture Order Count),
and PPS references from VCL NAL units.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from .bitstream import BitReader, unescape_rbsp
from .sps import SPS
from .pps import PPS
from .nalu import NALUType


@dataclass
class SliceHeader:
    """Represents decoded fields from an H.264 slice header."""
    first_mb_in_slice: int
    slice_type: int
    pic_parameter_set_id: int
    frame_num: int
    field_pic_flag: bool = False
    bottom_field_flag: bool = False
    idr_pic_id: Optional[int] = None
    pic_order_cnt_lsb: Optional[int] = None
    delta_pic_order_cnt_bottom: Optional[int] = None
    delta_pic_order_cnt0: Optional[int] = None
    delta_pic_order_cnt1: Optional[int] = None
    redundant_pic_cnt: int = 0
    slice_qp_delta: int = 0
    cabac_init_idc: Optional[int] = None
    is_idr: bool = False

    @property
    def slice_type_name(self) -> str:
        names = ["P", "B", "I", "SP", "SI"]
        base = self.slice_type % 5
        return names[base] if 0 <= base < len(names) else f"UNKNOWN_{self.slice_type}"

    @property
    def is_keyframe(self) -> bool:
        """True if this slice is an IDR slice or an all-I slice."""
        return self.is_idr or (self.slice_type % 5 == 2)


class SliceParser:
    """
    Parses H.264 slice headers given NAL unit data and optional SPS/PPS.
    """

    @classmethod
    def parse(
        cls,
        nalu_data: bytes,
        sps: Optional[SPS] = None,
        pps: Optional[PPS] = None,
        fallback_log2_max_frame_num: int = 16,
        fallback_poc_lsb_bits: int = 16,
    ) -> SliceHeader:
        """
        Parses slice header from raw NAL unit data.
        """
        if len(nalu_data) < 2:
            raise ValueError("NAL unit data too short for slice header")

        header_byte = nalu_data[0]
        nal_type = header_byte & 0x1F
        is_idr = (nal_type == NALUType.IDR)

        rbsp = unescape_rbsp(nalu_data[1:])
        reader = BitReader(rbsp)

        first_mb_in_slice = reader.read_ue()
        slice_type = reader.read_ue()
        pic_parameter_set_id = reader.read_ue()

        # Determine frame_num bit width
        if sps is not None:
            fn_bits = sps.log2_max_frame_num_minus4 + 4
        else:
            fn_bits = fallback_log2_max_frame_num

        frame_num = reader.read_bits(fn_bits)

        field_pic_flag = False
        bottom_field_flag = False
        if sps is not None and not sps.frame_mbs_only_flag:
            field_pic_flag = reader.read_bool()
            if field_pic_flag:
                bottom_field_flag = reader.read_bool()

        idr_pic_id = None
        if is_idr:
            idr_pic_id = reader.read_ue()

        pic_order_cnt_lsb = None
        delta_pic_order_cnt_bottom = None
        delta_pic_order_cnt0 = None
        delta_pic_order_cnt1 = None

        poc_type = sps.pic_order_cnt_type if sps is not None else 0
        if poc_type == 0:
            poc_bits = (
                sps.log2_max_pic_order_cnt_lsb_minus4 + 4
                if sps is not None
                else fallback_poc_lsb_bits
            )
            pic_order_cnt_lsb = reader.read_bits(poc_bits)
            bottom_field_pic_order = (
                pps.bottom_field_pic_order_in_frame_present_flag
                if pps is not None
                else False
            )
            if bottom_field_pic_order and not field_pic_flag:
                delta_pic_order_cnt_bottom = reader.read_se()
        elif poc_type == 1:
            delta_always_zero = (
                sps.delta_pic_order_always_zero_flag if sps is not None else False
            )
            if not delta_always_zero:
                delta_pic_order_cnt0 = reader.read_se()
                bottom_field_pic_order = (
                    pps.bottom_field_pic_order_in_frame_present_flag
                    if pps is not None
                    else False
                )
                if bottom_field_pic_order and not field_pic_flag:
                    delta_pic_order_cnt1 = reader.read_se()

        redundant_pic_cnt = 0
        if pps is not None and pps.redundant_pic_cnt_present_flag:
            redundant_pic_cnt = reader.read_ue()

        return SliceHeader(
            first_mb_in_slice=first_mb_in_slice,
            slice_type=slice_type,
            pic_parameter_set_id=pic_parameter_set_id,
            frame_num=frame_num,
            field_pic_flag=field_pic_flag,
            bottom_field_flag=bottom_field_flag,
            idr_pic_id=idr_pic_id,
            pic_order_cnt_lsb=pic_order_cnt_lsb,
            delta_pic_order_cnt_bottom=delta_pic_order_cnt_bottom,
            delta_pic_order_cnt0=delta_pic_order_cnt0,
            delta_pic_order_cnt1=delta_pic_order_cnt1,
            redundant_pic_cnt=redundant_pic_cnt,
            is_idr=is_idr,
        )
