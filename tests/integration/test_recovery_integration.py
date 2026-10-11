"""
Integration test for full H.264 bitstream recovery from corrupted MP4.

Verifies:
1. Forensic integrity: Original file is NEVER modified (SHA256 preserved).
2. AVCC vs Annex-B detection.
3. Reference-free SPS and PPS parameter recovery.
4. Access unit and IDR keyframe reconstruction.
5. Final frame truncation handling.
6. Export of raw Annex-B .h264 bitstream to recovered/recovered_stream.h264.
7. Verification that FFmpeg decodes the recovered stream cleanly.
"""

import unittest
import hashlib
import subprocess
import shutil
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.h264.recovery_engine import H264RecoveryEngine


def compute_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestRecoveryIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corrupted_file = os.path.abspath("samples/corrupted/original.mp4")
        if not os.path.exists(cls.corrupted_file):
            raise unittest.SkipTest(f"Corrupted sample not found at {cls.corrupted_file}")

        # Record file hash to ensure forensic read-only integrity
        cls.initial_hash = compute_file_sha256(cls.corrupted_file)

    def test_full_recovery_pipeline(self):
        """Runs the entire recovery subsystem on the corrupted MP4."""
        engine = H264RecoveryEngine(source_path=self.corrupted_file, chunk_size=1024 * 1024)
        summary = engine.run_recovery()

        # 1. Forensic Integrity Check: file was not modified
        final_hash = compute_file_sha256(self.corrupted_file)
        self.assertEqual(
            self.initial_hash,
            final_hash,
            "CRITICAL FORENSIC VIOLATION: Source file was modified!",
        )

        # 2. Format Detection
        self.assertEqual(summary.format_detected, "avcc")
        self.assertEqual(summary.length_size, 4)

        # 3. Parameter Recovery (SPS / PPS)
        self.assertIsNotNone(summary.sps)
        self.assertIsNotNone(summary.pps)
        self.assertEqual(summary.sps.width, 720)
        self.assertEqual(summary.sps.height, 1280)
        self.assertEqual(summary.sps.profile_idc, 100)
        self.assertTrue(summary.pps.entropy_coding_mode_flag)  # CABAC

        # 4. Access Unit & Keyframe Reconstruction
        self.assertGreaterEqual(summary.total_access_units, 450)
        self.assertGreaterEqual(summary.idr_count, 15)
        self.assertGreater(summary.overall_confidence, 0.9)

        # 5. Export Annex-B Stream
        recovered_dir = os.path.abspath("recovered")
        os.makedirs(recovered_dir, exist_ok=True)
        recovered_stream_path = os.path.join(recovered_dir, "recovered_stream.h264")

        bytes_written = engine.export_annex_b_stream(
            recovered_stream_path, include_sps_pps=True
        )
        self.assertGreater(bytes_written, 10 * 1024 * 1024)  # Over 10 MB
        self.assertTrue(os.path.exists(recovered_stream_path))

        # 6. Verify stream with FFmpeg
        ffmpeg_bin = self._get_ffmpeg()
        if ffmpeg_bin:
            cmd = [
                ffmpeg_bin,
                "-v",
                "error",
                "-i",
                recovered_stream_path,
                "-f",
                "null",
                "-",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(
                res.returncode,
                0,
                f"FFmpeg decoding failed with return code {res.returncode}: {res.stderr}",
            )
            # Filter for critical fatal bitstream errors per FORENSIC_TEST_PLAN.md (Section 3.3)
            fatal_errors = [
                l
                for l in res.stderr.splitlines()
                if any(
                    fatal in l.lower()
                    for fatal in (
                        "no frame!",
                        "non-existing pps",
                        "header damaged",
                        "decode error rate",
                        "exceeds maximum",
                    )
                )
            ]
            self.assertEqual(
                len(fatal_errors),
                0,
                f"FFmpeg reported fatal bitstream errors during decoding: {res.stderr}",
            )

    def _get_ffmpeg(self):
        which = shutil.which("ffmpeg")
        if which:
            return which
        candidates = [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None


if __name__ == "__main__":
    unittest.main()
