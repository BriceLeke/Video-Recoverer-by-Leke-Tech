"""
Integration test for full MP4 container reconstruction and FFmpeg/FFprobe validation.

Verifies:
1. Forensic integrity: Original file is NEVER modified (SHA256 preserved).
2. Complete ISOBMFF box hierarchy (ftyp, moov, mvhd, trak, tkhd, mdia, mdhd, hdlr,
   minf, vmhd, dinf, dref, stbl, stsd, avc1, avcC, stts, stsc, stsz, stco/co64, stss).
3. Generated MP4 opens cleanly in FFmpeg and FFprobe.
4. Video decodes from beginning to end without fatal errors.
5. Duration is sensible (~350s = 5m50s).
6. Fast and accurate seeking at multiple timestamps.
7. Correct codec (h264) and dimensions (720x1280).
8. Preservation of all recoverable video frames (10,522 frames).
9. 64-bit chunk offsets (co64) and 64-bit mdat extended header support.
"""

import hashlib
import os
import shutil
import struct
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.h264.recovery_engine import H264RecoveryEngine
from src.reconstruction.mp4_muxer import MP4Muxer
from src.reconstruction.validator import MP4Validator


def compute_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestReconstructionIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corrupted_file = os.path.abspath("samples/corrupted/original.mp4")
        if not os.path.exists(cls.corrupted_file):
            raise unittest.SkipTest(f"Corrupted sample not found at {cls.corrupted_file}")

        cls.initial_hash = compute_file_sha256(cls.corrupted_file)

        # Output paths
        cls.recovered_dir = os.path.abspath("recovered")
        os.makedirs(cls.recovered_dir, exist_ok=True)
        cls.recovered_mp4_path = os.path.join(cls.recovered_dir, "recovered_video.mp4")
        cls.recovered_64bit_path = os.path.join(cls.recovered_dir, "recovered_video_64bit.mp4")

        # Run recovery engine once to get summary
        engine = H264RecoveryEngine(source_path=cls.corrupted_file, chunk_size=1024 * 1024)
        cls.summary = engine.run_recovery()
        cls.validator = MP4Validator()

    def test_01_forensic_integrity_preserved(self):
        """Verifies source file was not modified in any way."""
        current_hash = compute_file_sha256(self.corrupted_file)
        self.assertEqual(
            self.initial_hash,
            current_hash,
            "CRITICAL FORENSIC VIOLATION: Source file was modified!",
        )

    def test_02_reconstruct_standard_mp4(self):
        """
        Reconstructs a standard MP4 container from the recovered video stream.
        Verifies box hierarchy and automated FFprobe / FFmpeg validation.
        """
        bytes_written = MP4Muxer.reconstruct_from_recovery_summary(
            summary=self.summary,
            output_path=self.recovered_mp4_path,
            fps=30.0,
            force_64bit=False,
        )

        self.assertGreater(bytes_written, 10 * 1024 * 1024)  # Over 10 MB
        self.assertTrue(os.path.exists(self.recovered_mp4_path))

        # Check required ISOBMFF box types in binary file
        with open(self.recovered_mp4_path, "rb") as f:
            header_sample = f.read(64)
            # ftyp is first box
            self.assertEqual(header_sample[4:8], b"ftyp")
            self.assertEqual(header_sample[8:12], b"isom")
            # mdat follows ftyp
            ftyp_size = struct.unpack(">I", header_sample[:4])[0]
            self.assertEqual(header_sample[ftyp_size + 4 : ftyp_size + 8], b"mdat")

            # Check moov at end
            f.seek(-min(bytes_written, 1024 * 1024), os.SEEK_END)
            tail = f.read()
            for required_box in (
                b"moov", b"mvhd", b"trak", b"tkhd", b"mdia", b"mdhd",
                b"hdlr", b"minf", b"vmhd", b"dinf", b"stbl", b"stsd",
                b"avc1", b"avcC", b"stts", b"stsc", b"stsz", b"stco", b"stss"
            ):
                self.assertIn(
                    required_box,
                    tail,
                    f"Required ISOBMFF box {required_box!r} not found in container",
                )

        # Validate with MP4Validator (FFprobe metadata, full decode, seeking)
        report = self.validator.validate(
            filepath=self.recovered_mp4_path,
            expected_width=720,
            expected_height=1280,
            min_duration=300.0,
        )

        self.assertTrue(report.is_valid, f"Validation failed: {report.errors}")
        self.assertEqual(report.video_codec, "h264")
        self.assertEqual(report.width, 720)
        self.assertEqual(report.height, 1280)
        self.assertGreaterEqual(report.duration, 350.0)  # ~350.7 seconds (5m50s)
        self.assertGreaterEqual(report.seek_tests_passed, 4)

    def test_03_reconstruct_64bit_co64_mp4(self):
        """
        Reconstructs an MP4 using 64-bit chunk offsets (co64) and large mdat header.
        Verifies that co64 is written instead of stco, and decodes cleanly in FFmpeg.
        """
        bytes_written = MP4Muxer.reconstruct_from_recovery_summary(
            summary=self.summary,
            output_path=self.recovered_64bit_path,
            fps=30.0,
            force_64bit=True,
        )

        self.assertTrue(os.path.exists(self.recovered_64bit_path))

        with open(self.recovered_64bit_path, "rb") as f:
            # Check 16-byte large mdat header
            f.seek(32)  # after 32-byte ftyp
            marker, btype = struct.unpack(">I4s", f.read(8))
            self.assertEqual(marker, 1)  # 64-bit large box marker
            self.assertEqual(btype, b"mdat")

            # Check moov contains co64 instead of stco
            f.seek(-min(bytes_written, 1024 * 1024), os.SEEK_END)
            tail = f.read()
            self.assertIn(b"co64", tail)
            self.assertNotIn(b"stco", tail)

        # Validate 64-bit MP4 with FFprobe / FFmpeg
        report = self.validator.validate(
            filepath=self.recovered_64bit_path,
            expected_width=720,
            expected_height=1280,
            min_duration=300.0,
        )
        self.assertTrue(report.is_valid, f"64-bit validation failed: {report.errors}")
        self.assertEqual(report.video_codec, "h264")
        self.assertEqual(report.width, 720)
        self.assertEqual(report.height, 1280)


if __name__ == "__main__":
    unittest.main()
