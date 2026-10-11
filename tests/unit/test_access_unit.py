"""
Unit tests for H.264 Access Unit (AU) reconstruction.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.h264.nalu import NALU, NALUType
from src.h264.access_unit import AccessUnit, AccessUnitBuilder


class TestAccessUnit(unittest.TestCase):
    def test_single_slice_access_unit(self):
        """Tests that a single VCL slice constitutes an Access Unit."""
        builder = AccessUnitBuilder()

        nalu1 = NALU(
            offset=100,
            payload_offset=104,
            length=5000,
            header_byte=0x65,
            nal_ref_idc=3,
            nal_unit_type=NALUType.IDR,
            forbidden_zero_bit=0,
            confidence=1.0,
        )

        au = builder.add_nalu(nalu1)
        self.assertIsNone(au)  # Still accumulating

        # Finalize
        completed_au = builder.finalize()
        self.assertIsNotNone(completed_au)
        self.assertEqual(completed_au.index, 0)
        self.assertEqual(completed_au.offset, 100)
        self.assertEqual(completed_au.total_size, 5000)
        self.assertTrue(completed_au.is_idr)
        self.assertTrue(completed_au.is_keyframe)
        self.assertEqual(completed_au.vcl_nalu_count, 1)

    def test_multi_nalu_access_unit(self):
        """Tests an Access Unit composed of AUD + SPS + PPS + IDR slice."""
        builder = AccessUnitBuilder()

        aud = NALU(offset=0, payload_offset=4, length=2, header_byte=0x09, nal_ref_idc=0, nal_unit_type=NALUType.AUD, forbidden_zero_bit=0)
        sps = NALU(offset=6, payload_offset=10, length=25, header_byte=0x67, nal_ref_idc=3, nal_unit_type=NALUType.SPS, forbidden_zero_bit=0)
        pps = NALU(offset=35, payload_offset=39, length=5, header_byte=0x68, nal_ref_idc=3, nal_unit_type=NALUType.PPS, forbidden_zero_bit=0)
        idr = NALU(offset=44, payload_offset=48, length=12000, header_byte=0x65, nal_ref_idc=3, nal_unit_type=NALUType.IDR, forbidden_zero_bit=0)

        builder.add_nalu(aud)
        builder.add_nalu(sps)
        builder.add_nalu(pps)
        builder.add_nalu(idr)

        # Now add next frame's slice: should trigger completion of previous AU
        next_slice = NALU(offset=12048, payload_offset=12052, length=4000, header_byte=0x41, nal_ref_idc=2, nal_unit_type=NALUType.NON_IDR, forbidden_zero_bit=0)
        completed_au = builder.add_nalu(next_slice)

        self.assertIsNotNone(completed_au)
        self.assertEqual(completed_au.index, 0)
        self.assertEqual(len(completed_au.nalus), 4)
        self.assertTrue(completed_au.is_idr)
        self.assertTrue(completed_au.has_parameter_sets)
        self.assertEqual(completed_au.total_size, 2 + 25 + 5 + 12000)

        # Finalize the second AU
        second_au = builder.finalize()
        self.assertIsNotNone(second_au)
        self.assertEqual(second_au.index, 1)
        self.assertFalse(second_au.is_idr)
        self.assertEqual(second_au.total_size, 4000)


if __name__ == "__main__":
    unittest.main()
