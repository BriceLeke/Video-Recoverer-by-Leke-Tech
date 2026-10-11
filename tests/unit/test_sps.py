"""
Unit tests for H.264 Sequence Parameter Set (SPS) parser and synthesizer.
"""

import unittest
import sys
import os

# Ensure src is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.h264.sps import SPS, SPSParser, SPSSynthesizer
from src.h264.bitstream import BitReader, BitWriter


class TestSPS(unittest.TestCase):
    def test_sps_synthesis_and_parsing_high_profile(self):
        """Tests synthesizing a High Profile 720x1280 SPS and parsing it back."""
        sps_bytes = SPSSynthesizer.synthesize(
            width=720,
            height=1280,
            profile_idc=100,
            level_idc=40,
            log2_max_frame_num_minus4=12,
            pic_order_cnt_type=0,
            log2_max_pic_order_cnt_lsb_minus4=12,
            fps=30.0,
        )

        self.assertGreater(len(sps_bytes), 10)
        self.assertEqual(sps_bytes[0] & 0x1F, 7)  # NAL unit type 7 (SPS)

        sps = SPSParser.parse(sps_bytes)
        self.assertEqual(sps.profile_idc, 100)
        self.assertEqual(sps.level_idc, 40)
        self.assertEqual(sps.width, 720)
        self.assertEqual(sps.height, 1280)
        self.assertEqual(sps.log2_max_frame_num_minus4, 12)
        self.assertEqual(sps.pic_order_cnt_type, 0)
        self.assertEqual(sps.log2_max_pic_order_cnt_lsb_minus4, 12)
        self.assertTrue(sps.frame_mbs_only_flag)
        self.assertEqual(sps.profile_name, "High")
        self.assertEqual(sps.level_string, "4.0")

    def test_sps_cropping_calculation(self):
        """Tests cropping calculations for non-mod16 dimensions (e.g. 1080x1920, 1080x2400)."""
        # 1080 is not a multiple of 16 (67.5 macroblocks -> 68 mbs = 1088, crop_right = 8 px)
        sps_bytes = SPSSynthesizer.synthesize(
            width=1080,
            height=2400,
            profile_idc=100,
        )

        sps = SPSParser.parse(sps_bytes)
        self.assertEqual(sps.coded_width, 1088)
        self.assertEqual(sps.coded_height, 2400)
        self.assertTrue(sps.frame_cropping_flag)
        self.assertEqual(sps.width, 1080)
        self.assertEqual(sps.height, 2400)

    def test_sps_baseline_profile(self):
        """Tests synthesizing and parsing Baseline Profile."""
        sps_bytes = SPSSynthesizer.synthesize(
            width=640,
            height=480,
            profile_idc=66,
            level_idc=30,
        )

        sps = SPSParser.parse(sps_bytes)
        self.assertEqual(sps.profile_idc, 66)
        self.assertEqual(sps.profile_name, "Baseline")
        self.assertEqual(sps.width, 640)
        self.assertEqual(sps.height, 480)

    def test_sps_short_payload_error(self):
        """Ensures that truncated/corrupted SPS bytes raise ValueError."""
        with self.assertRaises(ValueError):
            SPSParser.parse(b"\x67\x42")


if __name__ == "__main__":
    unittest.main()
