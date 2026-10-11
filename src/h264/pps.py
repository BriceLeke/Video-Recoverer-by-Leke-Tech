"""
H.264 Picture Parameter Set (PPS) Parser and Synthesizer.

Implements ISO/IEC 14496-10 Section 7.3.2.2 PPS syntax analysis,
supporting CABAC/CAVLC entropy coding detection, slice group mapping,
weighted prediction, deblocking filter control, and 8x8 transform mode.
"""

from dataclasses import dataclass
from typing import Optional

from .bitstream import BitReader, BitWriter, unescape_rbsp, escape_rbsp


@dataclass
class PPS:
    """Represents a decoded H.264 Picture Parameter Set."""
    pic_parameter_set_id: int
    seq_parameter_set_id: int
    entropy_coding_mode_flag: bool  # False = CAVLC, True = CABAC
    bottom_field_pic_order_in_frame_present_flag: bool = False
    num_slice_groups_minus1: int = 0
    num_ref_idx_l0_default_active_minus1: int = 0
    num_ref_idx_l1_default_active_minus1: int = 0
    weighted_pred_flag: bool = False
    weighted_bipred_idc: int = 0
    pic_init_qp_minus26: int = 0
    pic_init_qs_minus26: int = 0
    chroma_qp_index_offset: int = 0
    deblocking_filter_control_present_flag: bool = True
    constrained_intra_pred_flag: bool = False
    redundant_pic_cnt_present_flag: bool = False
    transform_8x8_mode_flag: bool = False
    pic_scaling_matrix_present_flag: bool = False
    second_chroma_qp_index_offset: int = 0
    raw_bytes: bytes = b""

    @property
    def is_cabac(self) -> bool:
        return self.entropy_coding_mode_flag

    @property
    def entropy_coding_name(self) -> str:
        return "CABAC" if self.entropy_coding_mode_flag else "CAVLC"


class PPSParser:
    """
    Parser for H.264 Picture Parameter Set NAL units.
    """

    @classmethod
    def parse(cls, nalu_data: bytes) -> PPS:
        """
        Parses raw NAL unit bytes (with or without 1-byte NAL header).
        """
        if len(nalu_data) < 2:
            raise ValueError(f"PPS data too short: {len(nalu_data)} bytes")

        if (nalu_data[0] & 0x1F) == 8:
            payload = nalu_data[1:]
        else:
            payload = nalu_data

        rbsp = unescape_rbsp(payload)
        reader = BitReader(rbsp)

        pic_parameter_set_id = reader.read_ue()
        seq_parameter_set_id = reader.read_ue()
        entropy_coding_mode_flag = reader.read_bool()
        bottom_field_pic_order = reader.read_bool()
        num_slice_groups_minus1 = reader.read_ue()

        if num_slice_groups_minus1 > 0:
            slice_group_map_type = reader.read_ue()
            if slice_group_map_type == 0:
                for _ in range(num_slice_groups_minus1 + 1):
                    reader.read_ue()
            elif slice_group_map_type == 2:
                for _ in range(num_slice_groups_minus1):
                    reader.read_ue()
                    reader.read_ue()
            elif slice_group_map_type in (3, 4, 5):
                reader.read_bool()
                reader.read_ue()
            elif slice_group_map_type == 6:
                pic_size_in_map_units_minus1 = reader.read_ue()
                bits = (num_slice_groups_minus1 + 1).bit_length()
                for _ in range(pic_size_in_map_units_minus1 + 1):
                    reader.read_bits(bits)

        num_ref_idx_l0_default = reader.read_ue()
        num_ref_idx_l1_default = reader.read_ue()
        weighted_pred_flag = reader.read_bool()
        weighted_bipred_idc = reader.read_bits(2)
        pic_init_qp_minus26 = reader.read_se()
        pic_init_qs_minus26 = reader.read_se()
        chroma_qp_index_offset = reader.read_se()
        deblocking_filter_control = reader.read_bool()
        constrained_intra_pred = reader.read_bool()
        redundant_pic_cnt_present = reader.read_bool()

        transform_8x8_mode_flag = False
        second_chroma_qp_index_offset = chroma_qp_index_offset

        if reader.has_more_rbsp_data:
            transform_8x8_mode_flag = reader.read_bool()
            pic_scaling_matrix_present = reader.read_bool()
            if pic_scaling_matrix_present:
                scaling_count = 6 + (2 if transform_8x8_mode_flag else 0)
                for i in range(scaling_count):
                    present = reader.read_bool()
                    if present:
                        cls._skip_scaling_list(reader, 16 if i < 6 else 64)
            second_chroma_qp_index_offset = reader.read_se()

        return PPS(
            pic_parameter_set_id=pic_parameter_set_id,
            seq_parameter_set_id=seq_parameter_set_id,
            entropy_coding_mode_flag=entropy_coding_mode_flag,
            bottom_field_pic_order_in_frame_present_flag=bottom_field_pic_order,
            num_slice_groups_minus1=num_slice_groups_minus1,
            num_ref_idx_l0_default_active_minus1=num_ref_idx_l0_default,
            num_ref_idx_l1_default_active_minus1=num_ref_idx_l1_default,
            weighted_pred_flag=weighted_pred_flag,
            weighted_bipred_idc=weighted_bipred_idc,
            pic_init_qp_minus26=pic_init_qp_minus26,
            pic_init_qs_minus26=pic_init_qs_minus26,
            chroma_qp_index_offset=chroma_qp_index_offset,
            deblocking_filter_control_present_flag=deblocking_filter_control,
            constrained_intra_pred_flag=constrained_intra_pred,
            redundant_pic_cnt_present_flag=redundant_pic_cnt_present,
            transform_8x8_mode_flag=transform_8x8_mode_flag,
            second_chroma_qp_index_offset=second_chroma_qp_index_offset,
            raw_bytes=nalu_data,
        )

    @classmethod
    def _skip_scaling_list(cls, reader: BitReader, size: int) -> None:
        last_scale = 8
        next_scale = 8
        for _ in range(size):
            if next_scale != 0:
                delta_scale = reader.read_se()
                next_scale = (last_scale + delta_scale + 256) % 256
            last_scale = last_scale if next_scale == 0 else next_scale


class PPSSynthesizer:
    """
    Synthesizes standard-compliant H.264 Picture Parameter Set bitstreams.
    """

    @classmethod
    def synthesize(
        cls,
        pic_parameter_set_id: int = 0,
        seq_parameter_set_id: int = 0,
        entropy_coding_mode: bool = True,  # True = CABAC, False = CAVLC
        transform_8x8_mode: bool = True,
        deblocking_filter_control: bool = True,
    ) -> bytes:
        """
        Synthesizes a PPS NAL unit (complete with 0x68 header byte).
        """
        w = BitWriter()
        w.write_ue(pic_parameter_set_id)
        w.write_ue(seq_parameter_set_id)
        w.write_bool(entropy_coding_mode)
        w.write_bool(False)  # bottom_field_pic_order_in_frame_present_flag
        w.write_ue(0)  # num_slice_groups_minus1 = 0
        w.write_ue(0)  # num_ref_idx_l0_default_active_minus1 = 0
        w.write_ue(0)  # num_ref_idx_l1_default_active_minus1 = 0
        w.write_bool(False)  # weighted_pred_flag
        w.write_bits(0, 2)  # weighted_bipred_idc = 0
        w.write_se(0)  # pic_init_qp_minus26 = 0
        w.write_se(0)  # pic_init_qs_minus26 = 0
        w.write_se(0)  # chroma_qp_index_offset = 0
        w.write_bool(deblocking_filter_control)
        w.write_bool(False)  # constrained_intra_pred_flag
        w.write_bool(False)  # redundant_pic_cnt_present_flag

        # Extensions
        w.write_bool(transform_8x8_mode)
        w.write_bool(False)  # pic_scaling_matrix_present_flag
        w.write_se(0)  # second_chroma_qp_index_offset = 0

        ebsp = w.to_ebsp_bytes()
        # NAL header for PPS: nal_ref_idc = 3, nal_unit_type = 8 -> 0x68
        return bytes([0x68]) + ebsp
