"""
Unit tests for H.264 Picture Parameter Set (PPS) parser and synthesizer.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.h264.pps import PPS, PPSParser, PPSSynthesizer


class TestPPS(unittest.TestCase):
    def test_pps_synthesis_and_parsing_cabac(self):
        """Tests synthesizing and parsing a CABAC PPS."""
        pps_bytes = PPSSynthesizer.synthesize(
            pic_parameter_set_id=0,
            seq_parameter_set_id=0,
            entropy_coding_mode=True,  # CABAC
            transform_8x8_mode=True,
            deblocking_filter_control=True,
        )

        self.assertGreater(len(pps_bytes), 2)
        self.assertEqual(pps_bytes[0] & 0x1F, 8)  # NAL unit type 8 (PPS)

        pps = PPSParser.parse(pps_bytes)
        self.assertEqual(pps.pic_parameter_set_id, 0)
        self.assertEqual(pps.seq_parameter_set_id, 0)
        self.assertTrue(pps.entropy_coding_mode_flag)
        self.assertEqual(pps.entropy_coding_name, "CABAC")
        self.assertTrue(pps.deblocking_filter_control_present_flag)
        self.assertTrue(pps.transform_8x8_mode_flag)

    def test_pps_synthesis_and_parsing_cavlc(self):
        """Tests synthesizing and parsing a CAVLC PPS."""
        pps_bytes = PPSSynthesizer.synthesize(
            pic_parameter_set_id=1,
            seq_parameter_set_id=0,
            entropy_coding_mode=False,  # CAVLC
            transform_8x8_mode=False,
            deblocking_filter_control=False,
        )

        pps = PPSParser.parse(pps_bytes)
        self.assertEqual(pps.pic_parameter_set_id, 1)
        self.assertFalse(pps.entropy_coding_mode_flag)
        self.assertEqual(pps.entropy_coding_name, "CAVLC")

    def test_pps_short_payload_error(self):
        """Ensures that invalid/short PPS payload raises an error."""
        with self.assertRaises(ValueError):
            PPSParser.parse(b"\x68")


if __name__ == "__main__":
    unittest.main()
