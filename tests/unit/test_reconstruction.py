"""
Unit tests for ISOBMFF / MP4 Reconstruction Subsystem.

Tests:
1. Low-level BoxWriter serialization (32-bit, 64-bit large boxes, FullBox, matrices).
2. Codec configuration (avcC, avc1, esds, mp4a).
3. Sample Table builder (stsd, stts, stss, stsc, stsz, stco, co64).
4. Automatic 64-bit offset selection (stco vs co64).
5. Track and Moov hierarchy generation (mvhd, trak, tkhd, mdia, mdhd, hdlr, minf, stbl).
6. Synthetic MP4 muxing and box verification.
7. Safe truncated final frame handling.
"""

import io
import os
import struct
import tempfile
import unittest

from src.reconstruction.box_writer import BoxWriter
from src.reconstruction.codec_config import H264CodecConfig, AACCodecConfig
from src.reconstruction.sample_table import SampleRecord, SampleTableBuilder
from src.reconstruction.track import Track, TrackType
from src.reconstruction.moov_builder import MoovBuilder
from src.reconstruction.mp4_muxer import MP4Muxer


class TestBoxWriter(unittest.TestCase):
    def test_standard_box(self):
        b = BoxWriter.box(b"test", b"\x01\x02\x03\x04")
        self.assertEqual(len(b), 12)
        size, btype = struct.unpack(">I4s", b[:8])
        self.assertEqual(size, 12)
        self.assertEqual(btype, b"test")
        self.assertEqual(b[8:], b"\x01\x02\x03\x04")

    def test_large_box(self):
        payload = b"ABCDEFGH"
        b = BoxWriter.large_box(b"mdat", payload)
        self.assertEqual(len(b), 24)
        size_marker, btype, large_size = struct.unpack(">I4sQ", b[:16])
        self.assertEqual(size_marker, 1)
        self.assertEqual(btype, b"mdat")
        self.assertEqual(large_size, 24)
        self.assertEqual(b[16:], payload)

    def test_full_box(self):
        b = BoxWriter.full_box(b"test", version=1, flags=0x000007, payload=b"DATA")
        self.assertEqual(len(b), 16)
        size, btype, version = struct.unpack(">I4sB", b[:9])
        flags = int.from_bytes(b[9:12], "big")
        self.assertEqual(size, 16)
        self.assertEqual(btype, b"test")
        self.assertEqual(version, 1)
        self.assertEqual(flags, 7)
        self.assertEqual(b[12:], b"DATA")

    def test_fixed_point_and_matrix(self):
        fp16 = BoxWriter.fixed_point_16_16(720.0)
        self.assertEqual(int.from_bytes(fp16, "big"), 720 << 16)

        fp8 = BoxWriter.fixed_point_8_8(1.0)
        self.assertEqual(int.from_bytes(fp8, "big"), 1 << 8)

        matrix = BoxWriter.unity_matrix()
        self.assertEqual(len(matrix), 36)
        self.assertEqual(matrix[:4], (0x00010000).to_bytes(4, "big"))


class TestCodecConfig(unittest.TestCase):
    def test_h264_avcC_and_avc1(self):
        fake_sps = b"\x67\x64\x00\x1f\xac\xd9\x40"
        fake_pps = b"\x68\xee\x3c\x80"
        cfg = H264CodecConfig(
            sps=fake_sps,
            pps=fake_pps,
            width=720,
            height=1280,
            profile_idc=100,
            level_idc=31,
        )

        avcC = cfg.build_avcC()
        self.assertEqual(avcC[4:8], b"avcC")
        # Check configurationVersion = 1, profile = 100, level = 31
        self.assertEqual(avcC[8], 1)
        self.assertEqual(avcC[9], 100)
        self.assertEqual(avcC[11], 31)

        avc1 = cfg.build_avc1()
        self.assertEqual(avc1[4:8], b"avc1")
        # Check width=720, height=1280 in avc1 header (offset 32 and 34)
        w, h = struct.unpack(">HH", avc1[32:36])
        self.assertEqual(w, 720)
        self.assertEqual(h, 1280)
        self.assertIn(b"avcC", avc1)

    def test_aac_esds_and_mp4a(self):
        cfg = AACCodecConfig(sample_rate=44100, channels=2)
        mp4a = cfg.build_mp4a()
        self.assertEqual(mp4a[4:8], b"mp4a")
        self.assertIn(b"esds", mp4a)
        channels = struct.unpack(">H", mp4a[24:26])[0]
        samplerate = struct.unpack(">I", mp4a[32:36])[0]
        self.assertEqual(channels, 2)
        self.assertEqual(samplerate >> 16, 44100)


class TestSampleTable(unittest.TestCase):
    def test_stts_run_length_compression(self):
        # 10 samples with duration 3000, followed by 5 samples with duration 1500
        samples = [SampleRecord(size=100, duration=3000) for _ in range(10)]
        samples += [SampleRecord(size=100, duration=1500) for _ in range(5)]

        stts = SampleTableBuilder.build_stts(samples)
        self.assertEqual(stts[4:8], b"stts")
        entry_count = struct.unpack(">I", stts[12:16])[0]
        self.assertEqual(entry_count, 2)

        c1, d1, c2, d2 = struct.unpack(">IIII", stts[16:32])
        self.assertEqual((c1, d1), (10, 3000))
        self.assertEqual((c2, d2), (5, 1500))

    def test_stss_sync_samples(self):
        samples = [
            SampleRecord(size=100, duration=3000, is_sync=(i in (0, 5, 10)))
            for i in range(15)
        ]
        stss = SampleTableBuilder.build_stss(samples)
        self.assertIsNotNone(stss)
        self.assertEqual(stss[4:8], b"stss")
        count = struct.unpack(">I", stss[12:16])[0]
        self.assertEqual(count, 3)
        # 1-indexed sample numbers
        syncs = struct.unpack(f">{count}I", stss[16:16 + count * 4])
        self.assertEqual(syncs, (1, 6, 11))

    def test_stco_vs_co64(self):
        # Normal 32-bit offsets (< 4GB)
        offsets_32 = [1000, 2000, 3000]
        stco = SampleTableBuilder.build_stco_or_co64(offsets_32)
        self.assertEqual(stco[4:8], b"stco")

        # Large 64-bit offsets (>= 4GB)
        offsets_64 = [1000, 5 * 1024 * 1024 * 1024]
        co64 = SampleTableBuilder.build_stco_or_co64(offsets_64)
        self.assertEqual(co64[4:8], b"co64")
        count, off1, off2 = struct.unpack(">IQQ", co64[12:32])
        self.assertEqual(count, 2)
        self.assertEqual(off1, 1000)
        self.assertEqual(off2, 5 * 1024 * 1024 * 1024)

        # Forced 64-bit mode
        forced = SampleTableBuilder.build_stco_or_co64(offsets_32, force_64bit=True)
        self.assertEqual(forced[4:8], b"co64")


class TestMP4Muxer(unittest.TestCase):
    def test_synthetic_mp4_generation(self):
        """Muxes a small synthetic video track and validates box structure."""
        fake_sps = b"\x67\x64\x00\x1f\xac\xd9\x40"
        fake_pps = b"\x68\xee\x3c\x80"
        cfg = H264CodecConfig(
            sps=fake_sps,
            pps=fake_pps,
            width=720,
            height=1280,
        )

        samples = []
        sample_data = {}
        # Create 5 synthetic frames
        for i in range(5):
            is_idr = (i == 0)
            payload = b"\x65\x88\x12\x34" if is_idr else b"\x41\x9A\x56\x78"
            avcc_data = len(payload).to_bytes(4, "big") + payload
            s = SampleRecord(
                size=len(avcc_data),
                duration=3000,
                is_sync=is_idr,
            )
            samples.append(s)
            sample_data[id(s)] = avcc_data

        track = Track(
            track_id=1,
            track_type=TrackType.VIDEO,
            timescale=90000,
            codec_config=cfg,
            width=720,
            height=1280,
            samples=samples,
        )

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            temp_path = tf.name

        try:
            muxer = MP4Muxer()
            written = muxer.reconstruct(
                output_path=temp_path,
                video_track=track,
                source_sample_data=sample_data,
            )
            self.assertGreater(written, 100)

            # Scan generated boxes
            with open(temp_path, "rb") as f:
                content = f.read()

            self.assertIn(b"ftyp", content)
            self.assertIn(b"mdat", content)
            self.assertIn(b"moov", content)
            self.assertIn(b"mvhd", content)
            self.assertIn(b"trak", content)
            self.assertIn(b"tkhd", content)
            self.assertIn(b"mdia", content)
            self.assertIn(b"mdhd", content)
            self.assertIn(b"hdlr", content)
            self.assertIn(b"minf", content)
            self.assertIn(b"stbl", content)
            self.assertIn(b"stsd", content)
            self.assertIn(b"avc1", content)
            self.assertIn(b"avcC", content)
            self.assertIn(b"stts", content)
            self.assertIn(b"stss", content)
            self.assertIn(b"stsc", content)
            self.assertIn(b"stsz", content)
            self.assertIn(b"stco", content)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_truncated_final_frame_safe_handling(self):
        """
        Tests when a source file unexpectedly terminates inside the final frame.
        The muxer should safely heal the length prefix to match surviving bytes.
        """
        # Create a mock source stream containing 1 full frame and 1 truncated frame
        mock_source = bytearray()

        # Frame 1: 50 bytes (4-byte len=46 + 46 bytes data)
        f1_payload = b"\x65\x88" + (b"\x11" * 44)
        mock_source.extend((len(f1_payload)).to_bytes(4, "big"))
        mock_source.extend(f1_payload)

        # Frame 2 (Truncated at EOF): Length claims 100 bytes, but only 20 bytes written
        f2_claimed_len = 100
        f2_actual_payload = b"\x41\x9A" + (b"\x22" * 18)  # 20 bytes actual payload
        mock_source.extend(f2_claimed_len.to_bytes(4, "big"))
        mock_source.extend(f2_actual_payload)  # EOF immediately follows

        src_stream = io.BytesIO(bytes(mock_source))

        cfg = H264CodecConfig(
            sps=b"\x67\x64\x00\x1f\xac\xd9\x40",
            pps=b"\x68\xee\x3c\x80",
            width=720,
            height=1280,
        )

        s1 = SampleRecord(size=4 + len(f1_payload), duration=3000, is_sync=True, source_offset=0)
        s2 = SampleRecord(size=4 + f2_claimed_len, duration=3000, is_sync=False, source_offset=len(f1_payload) + 4)

        track = Track(
            track_id=1,
            track_type=TrackType.VIDEO,
            timescale=90000,
            codec_config=cfg,
            width=720,
            height=1280,
            samples=[s1, s2],
        )

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            temp_path = tf.name

        try:
            muxer = MP4Muxer()
            muxer.reconstruct(
                output_path=temp_path,
                video_track=track,
                source_stream=src_stream,
            )

            # Check that s2 was healed to 24 bytes (4 + 20) instead of 104 bytes
            self.assertEqual(track.samples[1].size, 4 + len(f2_actual_payload))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
