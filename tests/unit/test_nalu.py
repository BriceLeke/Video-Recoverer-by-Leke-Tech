"""
Unit tests for H.264 NAL unit header parsing and validation.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.h264.nalu import NALU, NALUType


class TestNALU(unittest.TestCase):
    def test_nalu_header_parsing(self):
        """Tests decoding forbidden_zero_bit, nal_ref_idc, and nal_unit_type."""
        # 0x65 -> binary 0110 0101 -> forbidden=0, ref_idc=3, type=5 (IDR)
        forbidden, ref_idc, ntype = NALU.parse_header(0x65)
        self.assertEqual(forbidden, 0)
        self.assertEqual(ref_idc, 3)
        self.assertEqual(ntype, NALUType.IDR)

        # 0x41 -> binary 0100 0001 -> forbidden=0, ref_idc=2, type=1 (NON_IDR)
        forbidden, ref_idc, ntype = NALU.parse_header(0x41)
        self.assertEqual(forbidden, 0)
        self.assertEqual(ref_idc, 2)
        self.assertEqual(ntype, NALUType.NON_IDR)

        # 0x67 -> binary 0110 0111 -> forbidden=0, ref_idc=3, type=7 (SPS)
        forbidden, ref_idc, ntype = NALU.parse_header(0x67)
        self.assertEqual(forbidden, 0)
        self.assertEqual(ref_idc, 3)
        self.assertEqual(ntype, NALUType.SPS)

    def test_nalu_header_validation(self):
        """Tests forensic validation heuristics."""
        # Valid IDR header
        valid, msg = NALU.validate_header(0x65)
        self.assertTrue(valid)

        # Valid Non-IDR header
        valid, msg = NALU.validate_header(0x41)
        self.assertTrue(valid)

        # Invalid forbidden_zero_bit = 1 (e.g. 0x85)
        valid, msg = NALU.validate_header(0x85)
        self.assertFalse(valid)
        self.assertIn("forbidden_zero_bit", msg)

        # Invalid type = 0
        valid, msg = NALU.validate_header(0x20)
        self.assertFalse(valid)
        self.assertIn("nal_unit_type is 0", msg)

        # Invalid: IDR with nal_ref_idc == 0 (0x05)
        valid, msg = NALU.validate_header(0x05)
        self.assertFalse(valid)
        self.assertIn("nal_ref_idc == 0", msg)

    def test_vcl_classification(self):
        """Tests is_vcl helper function."""
        self.assertTrue(NALUType.is_vcl(NALUType.NON_IDR))
        self.assertTrue(NALUType.is_vcl(NALUType.IDR))
        self.assertFalse(NALUType.is_vcl(NALUType.SPS))
        self.assertFalse(NALUType.is_vcl(NALUType.PPS))
        self.assertFalse(NALUType.is_vcl(NALUType.SEI))
        self.assertFalse(NALUType.is_vcl(NALUType.AUD))


if __name__ == "__main__":
    unittest.main()
