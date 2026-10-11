"""
H.264 Sequence Parameter Set (SPS) Parser and Synthesizer.

Implements complete ISO/IEC 14496-10 Section 7.3.2.1.1 SPS syntax analysis,
including profile, level, macroblock width/height, cropping rectangle,
chroma format, scaling lists, and VUI timing parameters.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from .bitstream import BitReader, BitWriter, unescape_rbsp, escape_rbsp


@dataclass
class SPS:
    """Represents a decoded H.264 Sequence Parameter Set."""
    profile_idc: int
    constraint_set0_flag: bool
    constraint_set1_flag: bool
    constraint_set2_flag: bool
    constraint_set3_flag: bool
    constraint_set4_flag: bool
    constraint_set5_flag: bool
    level_idc: int
    seq_parameter_set_id: int
    chroma_format_idc: int = 1  # Default 4:2:0
    separate_colour_plane_flag: bool = False
    bit_depth_luma_minus8: int = 0
    bit_depth_chroma_minus8: int = 0
    qpprime_y_zero_transform_bypass_flag: bool = False
    log2_max_frame_num_minus4: int = 0
    pic_order_cnt_type: int = 0
    log2_max_pic_order_cnt_lsb_minus4: int = 0
    delta_pic_order_always_zero_flag: bool = False
    offset_for_non_ref_pic: int = 0
    offset_for_top_to_bottom_field: int = 0
    num_ref_frames_in_pic_order_cnt_cycle: int = 0
    offset_for_ref_frame: List[int] = field(default_factory=list)
    max_num_ref_frames: int = 1
    gaps_in_frame_num_value_allowed_flag: bool = False
    pic_width_in_mbs_minus1: int = 0
    pic_height_in_map_units_minus1: int = 0
    frame_mbs_only_flag: bool = True
    mb_adaptive_frame_field_flag: bool = False
    direct_8x8_inference_flag: bool = True
    frame_cropping_flag: bool = False
    frame_crop_left_offset: int = 0
    frame_crop_right_offset: int = 0
    frame_crop_top_offset: int = 0
    frame_crop_bottom_offset: int = 0
    vui_parameters_present_flag: bool = False
    timing_info_present_flag: bool = False
    num_units_in_tick: Optional[int] = None
    time_scale: Optional[int] = None
    fixed_frame_rate_flag: Optional[bool] = None
    raw_bytes: bytes = b""

    @property
    def coded_width(self) -> int:
        """Width in pixels prior to cropping (multiple of 16)."""
        return (self.pic_width_in_mbs_minus1 + 1) * 16

    @property
    def coded_height(self) -> int:
        """Height in pixels prior to cropping (multiple of 16)."""
        map_unit_factor = 1 if self.frame_mbs_only_flag else 2
        return (self.pic_height_in_map_units_minus1 + 1) * 16 * map_unit_factor

    @property
    def width(self) -> int:
        """Decoded width in pixels after applying crop rectangle."""
        w = self.coded_width
        if self.frame_cropping_flag:
            # Crop unit in horizontal direction is SubWidthC for 4:2:0/4:2:2 (2 pixels)
            crop_unit_x = 2 if self.chroma_format_idc in (1, 2) else 1
            w -= (self.frame_crop_left_offset + self.frame_crop_right_offset) * crop_unit_x
        return w

    @property
    def height(self) -> int:
        """Decoded height in pixels after applying crop rectangle."""
        h = self.coded_height
        if self.frame_cropping_flag:
            # Crop unit in vertical direction
            map_unit_factor = 1 if self.frame_mbs_only_flag else 2
            crop_unit_y = (2 if self.chroma_format_idc == 1 else 1) * map_unit_factor
            h -= (self.frame_crop_top_offset + self.frame_crop_bottom_offset) * crop_unit_y
        return h

    @property
    def profile_name(self) -> str:
        profiles = {
            66: "Baseline",
            77: "Main",
            88: "Extended",
            100: "High",
            110: "High 10",
            122: "High 4:2:2",
            244: "High 4:4:4 Predictive",
        }
        return profiles.get(self.profile_idc, f"Profile_{self.profile_idc}")

    @property
    def level_string(self) -> str:
        return f"{self.level_idc / 10:.1f}"


class SPSParser:
    """
    Parser for H.264 Sequence Parameter Set NAL units.
    """

    @classmethod
    def parse(cls, nalu_data: bytes) -> SPS:
        """
        Parses raw NAL unit bytes (with or without 1-byte NAL header).
        """
        if len(nalu_data) < 4:
            raise ValueError(f"SPS data too short: {len(nalu_data)} bytes")

        # If first byte is NAL header (0x67, 0x27, etc.)
        if (nalu_data[0] & 0x1F) == 7:
            payload = nalu_data[1:]
        else:
            payload = nalu_data

        rbsp = unescape_rbsp(payload)
        reader = BitReader(rbsp)

        profile_idc = reader.read_bits(8)
        constraint_set0 = reader.read_bool()
        constraint_set1 = reader.read_bool()
        constraint_set2 = reader.read_bool()
        constraint_set3 = reader.read_bool()
        constraint_set4 = reader.read_bool()
        constraint_set5 = reader.read_bool()
        _reserved_zero_2bits = reader.read_bits(2)
        level_idc = reader.read_bits(8)
        seq_parameter_set_id = reader.read_ue()

        chroma_format_idc = 1
        separate_colour_plane_flag = False
        bit_depth_luma_minus8 = 0
        bit_depth_chroma_minus8 = 0
        qpprime_y_zero_transform_bypass_flag = False

        if profile_idc in (100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134):
            chroma_format_idc = reader.read_ue()
            if chroma_format_idc == 3:
                separate_colour_plane_flag = reader.read_bool()
            bit_depth_luma_minus8 = reader.read_ue()
            bit_depth_chroma_minus8 = reader.read_ue()
            qpprime_y_zero_transform_bypass_flag = reader.read_bool()
            seq_scaling_matrix_present_flag = reader.read_bool()
            if seq_scaling_matrix_present_flag:
                scaling_list_count = 12 if chroma_format_idc == 3 else 8
                for i in range(scaling_list_count):
                    seq_scaling_list_present_flag = reader.read_bool()
                    if seq_scaling_list_present_flag:
                        cls._skip_scaling_list(reader, 16 if i < 6 else 64)

        log2_max_frame_num_minus4 = reader.read_ue()
        pic_order_cnt_type = reader.read_ue()

        log2_max_pic_order_cnt_lsb_minus4 = 0
        delta_pic_order_always_zero_flag = False
        offset_for_non_ref_pic = 0
        offset_for_top_to_bottom_field = 0
        num_ref_frames_in_pic_order_cnt_cycle = 0
        offset_for_ref_frame: List[int] = []

        if pic_order_cnt_type == 0:
            log2_max_pic_order_cnt_lsb_minus4 = reader.read_ue()
        elif pic_order_cnt_type == 1:
            delta_pic_order_always_zero_flag = reader.read_bool()
            offset_for_non_ref_pic = reader.read_se()
            offset_for_top_to_bottom_field = reader.read_se()
            num_ref_frames_in_pic_order_cnt_cycle = reader.read_ue()
            for _ in range(num_ref_frames_in_pic_order_cnt_cycle):
                offset_for_ref_frame.append(reader.read_se())

        max_num_ref_frames = reader.read_ue()
        gaps_in_frame_num_value_allowed_flag = reader.read_bool()
        pic_width_in_mbs_minus1 = reader.read_ue()
        pic_height_in_map_units_minus1 = reader.read_ue()
        frame_mbs_only_flag = reader.read_bool()

        mb_adaptive_frame_field_flag = False
        if not frame_mbs_only_flag:
            mb_adaptive_frame_field_flag = reader.read_bool()

        direct_8x8_inference_flag = reader.read_bool()
        frame_cropping_flag = reader.read_bool()

        crop_left = 0
        crop_right = 0
        crop_top = 0
        crop_bottom = 0
        if frame_cropping_flag:
            crop_left = reader.read_ue()
            crop_right = reader.read_ue()
            crop_top = reader.read_ue()
            crop_bottom = reader.read_ue()

        vui_parameters_present_flag = False
        timing_info_present_flag = False
        num_units_in_tick = None
        time_scale = None
        fixed_frame_rate_flag = None

        if reader.has_more_rbsp_data:
            vui_parameters_present_flag = reader.read_bool()
            if vui_parameters_present_flag:
                # We can check for timing_info
                timing_info = cls._parse_vui_timing(reader)
                if timing_info:
                    timing_info_present_flag = True
                    num_units_in_tick, time_scale, fixed_frame_rate_flag = timing_info

        return SPS(
            profile_idc=profile_idc,
            constraint_set0_flag=constraint_set0,
            constraint_set1_flag=constraint_set1,
            constraint_set2_flag=constraint_set2,
            constraint_set3_flag=constraint_set3,
            constraint_set4_flag=constraint_set4,
            constraint_set5_flag=constraint_set5,
            level_idc=level_idc,
            seq_parameter_set_id=seq_parameter_set_id,
            chroma_format_idc=chroma_format_idc,
            separate_colour_plane_flag=separate_colour_plane_flag,
            bit_depth_luma_minus8=bit_depth_luma_minus8,
            bit_depth_chroma_minus8=bit_depth_chroma_minus8,
            qpprime_y_zero_transform_bypass_flag=qpprime_y_zero_transform_bypass_flag,
            log2_max_frame_num_minus4=log2_max_frame_num_minus4,
            pic_order_cnt_type=pic_order_cnt_type,
            log2_max_pic_order_cnt_lsb_minus4=log2_max_pic_order_cnt_lsb_minus4,
            delta_pic_order_always_zero_flag=delta_pic_order_always_zero_flag,
            offset_for_non_ref_pic=offset_for_non_ref_pic,
            offset_for_top_to_bottom_field=offset_for_top_to_bottom_field,
            num_ref_frames_in_pic_order_cnt_cycle=num_ref_frames_in_pic_order_cnt_cycle,
            offset_for_ref_frame=offset_for_ref_frame,
            max_num_ref_frames=max_num_ref_frames,
            gaps_in_frame_num_value_allowed_flag=gaps_in_frame_num_value_allowed_flag,
            pic_width_in_mbs_minus1=pic_width_in_mbs_minus1,
            pic_height_in_map_units_minus1=pic_height_in_map_units_minus1,
            frame_mbs_only_flag=frame_mbs_only_flag,
            mb_adaptive_frame_field_flag=mb_adaptive_frame_field_flag,
            direct_8x8_inference_flag=direct_8x8_inference_flag,
            frame_cropping_flag=frame_cropping_flag,
            frame_crop_left_offset=crop_left,
            frame_crop_right_offset=crop_right,
            frame_crop_top_offset=crop_top,
            frame_crop_bottom_offset=crop_bottom,
            vui_parameters_present_flag=vui_parameters_present_flag,
            timing_info_present_flag=timing_info_present_flag,
            num_units_in_tick=num_units_in_tick,
            time_scale=time_scale,
            fixed_frame_rate_flag=fixed_frame_rate_flag,
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

    @classmethod
    def _parse_vui_timing(cls, reader: BitReader) -> Optional[tuple[int, int, bool]]:
        """Parses VUI parameters looking for timing_info_present_flag."""
        try:
            aspect_ratio_info_present_flag = reader.read_bool()
            if aspect_ratio_info_present_flag:
                aspect_ratio_idc = reader.read_bits(8)
                if aspect_ratio_idc == 255:  # Extended_SAR
                    _sar_width = reader.read_bits(16)
                    _sar_height = reader.read_bits(16)
            overscan_info_present_flag = reader.read_bool()
            if overscan_info_present_flag:
                _overscan_appropriate_flag = reader.read_bool()
            video_signal_type_present_flag = reader.read_bool()
            if video_signal_type_present_flag:
                _video_format = reader.read_bits(3)
                _video_full_range_flag = reader.read_bool()
                colour_description_present_flag = reader.read_bool()
                if colour_description_present_flag:
                    _colour_primaries = reader.read_bits(8)
                    _transfer_characteristics = reader.read_bits(8)
                    _matrix_coefficients = reader.read_bits(8)
            chroma_loc_info_present_flag = reader.read_bool()
            if chroma_loc_info_present_flag:
                _chroma_sample_loc_type_top_field = reader.read_ue()
                _chroma_sample_loc_type_bottom_field = reader.read_ue()
            timing_info_present_flag = reader.read_bool()
            if timing_info_present_flag:
                num_units_in_tick = reader.read_bits(32)
                time_scale = reader.read_bits(32)
                fixed_frame_rate_flag = reader.read_bool()
                return num_units_in_tick, time_scale, fixed_frame_rate_flag
        except (EOFError, ValueError):
            pass
        return None


class SPSSynthesizer:
    """
    Synthesizes standard-compliant H.264 Sequence Parameter Set bitstreams.
    """

    @classmethod
    def synthesize(
        cls,
        width: int,
        height: int,
        profile_idc: int = 100,  # High Profile
        level_idc: int = 40,    # Level 4.0
        log2_max_frame_num_minus4: int = 12,
        pic_order_cnt_type: int = 0,
        log2_max_pic_order_cnt_lsb_minus4: int = 12,
        max_num_ref_frames: int = 1,
        fps: Optional[float] = None,
    ) -> bytes:
        """
        Synthesizes an SPS NAL unit (complete with 0x67 header byte).
        Calculates required macroblock padding and crop units for exact width/height.
        """
        mb_w = (width + 15) // 16
        mb_h = (height + 15) // 16

        crop_right_px = mb_w * 16 - width
        crop_bottom_px = mb_h * 16 - height
        # For 4:2:0 progressive, crop unit is 2 pixels
        crop_right = crop_right_px // 2
        crop_bottom = crop_bottom_px // 2
        has_crop = (crop_right > 0) or (crop_bottom > 0)

        w = BitWriter()
        w.write_bits(profile_idc, 8)
        w.write_bits(0, 8)  # constraint_set flags + reserved_zero_2bits
        w.write_bits(level_idc, 8)
        w.write_ue(0)  # seq_parameter_set_id = 0

        if profile_idc in (100, 110, 122, 244):
            w.write_ue(1)  # chroma_format_idc = 1 (4:2:0)
            w.write_ue(0)  # bit_depth_luma_minus8 = 0
            w.write_ue(0)  # bit_depth_chroma_minus8 = 0
            w.write_bool(False)  # qpprime_y_zero_transform_bypass_flag
            w.write_bool(False)  # seq_scaling_matrix_present_flag

        w.write_ue(log2_max_frame_num_minus4)
        w.write_ue(pic_order_cnt_type)
        if pic_order_cnt_type == 0:
            w.write_ue(log2_max_pic_order_cnt_lsb_minus4)

        w.write_ue(max_num_ref_frames)
        w.write_bool(False)  # gaps_in_frame_num_value_allowed_flag
        w.write_ue(mb_w - 1)  # pic_width_in_mbs_minus1
        w.write_ue(mb_h - 1)  # pic_height_in_map_units_minus1
        w.write_bool(True)   # frame_mbs_only_flag = 1 (progressive)
        w.write_bool(True)   # direct_8x8_inference_flag = 1

        if has_crop:
            w.write_bool(True)  # frame_cropping_flag
            w.write_ue(0)       # frame_crop_left_offset
            w.write_ue(crop_right)  # frame_crop_right_offset
            w.write_ue(0)       # frame_crop_top_offset
            w.write_ue(crop_bottom) # frame_crop_bottom_offset
        else:
            w.write_bool(False)

        if fps is not None and fps > 0:
            w.write_bool(True)  # vui_parameters_present_flag
            w.write_bool(False) # aspect_ratio_info_present_flag
            w.write_bool(False) # overscan_info_present_flag
            w.write_bool(False) # video_signal_type_present_flag
            w.write_bool(False) # chroma_loc_info_present_flag
            w.write_bool(True)  # timing_info_present_flag
            time_scale = int(fps * 2000)
            num_units_in_tick = 1000
            w.write_bits(num_units_in_tick, 32)
            w.write_bits(time_scale, 32)
            w.write_bool(False) # fixed_frame_rate_flag
            w.write_bool(False) # nal_hrd_parameters_present_flag
            w.write_bool(False) # vcl_hrd_parameters_present_flag
            w.write_bool(False) # pic_struct_present_flag
            w.write_bool(False) # bitstream_restriction_flag
        else:
            w.write_bool(False) # vui_parameters_present_flag

        ebsp = w.to_ebsp_bytes()
        # NAL header for SPS: nal_ref_idc = 3, nal_unit_type = 7 -> 0x67
        return bytes([0x67]) + ebsp
