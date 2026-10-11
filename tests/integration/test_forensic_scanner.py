import os
import unittest
from src.analyzer.forensic_scanner import ForensicScanner

SAMPLE_PATH = "samples/corrupted/original.mp4"


class TestForensicScanner(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(SAMPLE_PATH):
            self.skipTest("Corrupted sample not found")

    def test_forensic_scanner_top_level(self):
        scanner = ForensicScanner(SAMPLE_PATH)
        boxes = scanner.scan_top_level_boxes()

        types = [b["type"] for b in boxes]
        self.assertIn("ftyp", types)
        self.assertIn("mdat", types)
        self.assertNotIn("moov", types)

        mdat = next(b for b in boxes if b["type"] == "mdat")
        self.assertEqual(mdat["offset"], 0x28)

        # Check truncation detection
        self.assertGreater(mdat["size"], os.path.getsize(SAMPLE_PATH))

    def test_forensic_scanner_video_stats(self):
        scanner = ForensicScanner(SAMPLE_PATH)
        scanner.scan_top_level_boxes()
        stats = scanner.scan_video_nalus()

        # Assert missing SPS/PPS based on forensic findings
        self.assertEqual(stats["sps"], 0)
        self.assertEqual(stats["pps"], 0)

        # Assert presence of video frames
        self.assertGreater(stats["idr"], 0)
        self.assertGreater(stats["non_idr"], 0)


if __name__ == "__main__":
    unittest.main()
