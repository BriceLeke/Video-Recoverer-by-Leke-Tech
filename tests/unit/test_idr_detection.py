"""
Unit tests for IDR (Instantaneous Decoder Refresh) keyframe detection.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.h264.nalu import NALU, NALUType
from src.h264.slice import SliceParser
from src.h264.sps import SPSSynthesizer, SPSParser
from src.h264.pps import PPSSynthesizer, PPSParser
from src.h264.access_unit import AccessUnit, AccessUnitBuilder


class TestIDRDetection(unittest.TestCase):
    def setUp(self):
        sps_bytes = SPSSynthesizer.synthesize(width=720, height=1280)
        pps_bytes = PPSSynthesizer.synthesize()
        self.sps = SPSParser.parse(sps_bytes)
        self.pps = PPSParser.parse(pps_bytes)

    def test_idr_vs_non_idr_classification(self):
        """Tests identifying IDR (type 5) vs Non-IDR (type 1) NAL units."""
        idr_nalu = NALU(
            offset=100, payload_offset=104, length=1000,
            header_byte=0x65, nal_ref_idc=3, nal_unit_type=NALUType.IDR,
            forbidden_zero_bit=0
        )
        non_idr_nalu = NALU(
            offset=1104, payload_offset=1108, length=500,
            header_byte=0x41, nal_ref_idc=2, nal_unit_type=NALUType.NON_IDR,
            forbidden_zero_bit=0
        )

        self.assertTrue(idr_nalu.is_idr)
        self.assertFalse(non_idr_nalu.is_idr)

    def test_access_unit_keyframe_flag(self):
        """Tests that an AU containing an IDR NAL unit is flagged as a keyframe."""
        builder = AccessUnitBuilder()
        builder.add_nalu(NALU(
            offset=0, payload_offset=4, length=2000,
            header_byte=0x65, nal_ref_idc=3, nal_unit_type=NALUType.IDR,
            forbidden_zero_bit=0
        ))
        au0 = builder.finalize()
        self.assertTrue(au0.is_idr)
        self.assertTrue(au0.is_keyframe)

        builder.add_nalu(NALU(
            offset=2004, payload_offset=2008, length=1500,
            header_byte=0x41, nal_ref_idc=2, nal_unit_type=NALUType.NON_IDR,
            forbidden_zero_bit=0
        ))
        au1 = builder.finalize()
        self.assertFalse(au1.is_idr)
        self.assertFalse(au1.is_keyframe)


if __name__ == "__main__":
    unittest.main()
