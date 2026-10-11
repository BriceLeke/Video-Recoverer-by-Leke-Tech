"""
Unit tests for malformed or truncated final NAL units handling.
"""

import unittest
import io
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.h264.recovery_engine import H264RecoveryEngine
from src.h264.nalu import NALU, NALUType


class TestMalformedFinalFrame(unittest.TestCase):
    def test_truncated_payload_at_eof(self):
        """
        Tests when a NAL unit's 4-byte length prefix claims 10,000 bytes,
        but physical EOF is encountered after only 150 bytes.
        """
        stream_data = bytearray()

        # Frame 0: Valid IDR frame of 100 bytes
        stream_data.extend((100).to_bytes(4, "big"))
        stream_data.append(0x65)
        stream_data.extend(b"\x88\x80\x00\x00" + b"\x00" * 95)

        # Frame 1: Valid P-frame of 80 bytes
        stream_data.extend((80).to_bytes(4, "big"))
        stream_data.append(0x41)
        stream_data.extend(b"\x9a\x00\x02\x00" + b"\x00" * 75)

        # Frame 2: Violently truncated! Length says 50,000 bytes, but file ends after 150 bytes
        stream_data.extend((50000).to_bytes(4, "big"))
        stream_data.append(0x41)
        stream_data.extend(b"\x9a\x00\x04\x00" + b"\xAA" * 145)

        bio = io.BytesIO(bytes(stream_data))
        engine = H264RecoveryEngine(stream=bio, chunk_size=256)
        summary = engine.run_recovery()

        # Engine must not crash and must recover the complete frames plus the truncated frame
        self.assertGreaterEqual(summary.total_access_units, 2)
        # Check that the last recovered AU is marked as truncated
        last_au = engine.access_units[-1]
        self.assertTrue(last_au.is_truncated)
        self.assertLess(last_au.confidence, 1.0)

    def test_partial_length_prefix_at_eof(self):
        """
        Tests when EOF occurs in the middle of the 4-byte length prefix (e.g. only 2 bytes exist).
        """
        stream_data = bytearray()

        # Frame 0: Valid IDR frame of 50 bytes
        stream_data.extend((50).to_bytes(4, "big"))
        stream_data.append(0x65)
        stream_data.extend(b"\x88\x80\x00\x00" + b"\x00" * 45)

        # Truncated length prefix at EOF (only 2 bytes)
        stream_data.extend(b"\x00\x10")

        bio = io.BytesIO(bytes(stream_data))
        engine = H264RecoveryEngine(stream=bio, chunk_size=128)
        summary = engine.run_recovery()

        self.assertEqual(summary.total_access_units, 1)
        self.assertEqual(engine.access_units[0].index, 0)
        self.assertFalse(engine.access_units[0].is_truncated)

    def test_garbage_bytes_at_eof(self):
        """
        Tests when trailing noise/audio bytes at EOF do not form a valid NALU.
        """
        stream_data = bytearray()

        # Valid frame
        stream_data.extend((60).to_bytes(4, "big"))
        stream_data.append(0x65)
        stream_data.extend(b"\x88\x80" + b"\x00" * 57)

        # 30 bytes of audio noise at EOF
        stream_data.extend(b"\xFF\xAA\x55\x12" * 7 + b"\x01\x02")

        bio = io.BytesIO(bytes(stream_data))
        engine = H264RecoveryEngine(stream=bio, chunk_size=64)
        summary = engine.run_recovery()

        self.assertEqual(summary.total_access_units, 1)
        self.assertTrue(summary.access_units[0].is_idr if hasattr(summary, "access_units") else engine.access_units[0].is_idr)


if __name__ == "__main__":
    unittest.main()
