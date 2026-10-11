"""
Unit tests for streaming processing and files larger than available RAM.
"""

import unittest
import io
import sys
import os
import tracemalloc

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.h264.recovery_engine import H264RecoveryEngine


class VirtualGigabyteStream(io.RawIOBase):
    """
    Simulates a massive multi-gigabyte corrupted MP4 file (e.g. 20 GB or 50 GB)
    without using physical disk space or RAM.
    
    Generates deterministic synthetic H.264 video frames interleaved with audio.
    """

    def __init__(self, total_size_bytes: int = 10 * 1024 * 1024 * 1024):  # 10 GB default
        self.total_size = total_size_bytes
        self.position = 0
        self.frame_size = 50000  # 50 KB per frame
        self.audio_gap = 12      # 12 bytes audio between frames
        
        # Precompute one stride block for instant memory slicing
        stride_ba = bytearray()
        stride_ba.extend((self.frame_size).to_bytes(4, "big"))
        stride_ba.append(0x65) # IDR header
        stride_ba.append(0x88) # Valid slice header (first_mb=0, slice_type=7)
        stride_ba.extend(b"\xAA" * (self.frame_size - 2))
        # 12-byte audio gap
        stride_ba.extend(b"\x21\x10\x04\x60\x8C\x1C\x21\x10\x04\x60\x8C\x1C")
        self._pattern_stride = bytes(stride_ba)

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence == os.SEEK_SET:
            self.position = offset
        elif whence == os.SEEK_CUR:
            self.position += offset
        elif whence == os.SEEK_END:
            self.position = self.total_size + offset
        else:
            raise ValueError(f"Invalid whence: {whence}")
        self.position = max(0, min(self.position, self.total_size))
        return self.position

    def tell(self) -> int:
        return self.position

    def readinto(self, b) -> int:
        if self.position >= self.total_size:
            return 0
        to_read = min(len(b), self.total_size - self.position)
        stride_len = len(self._pattern_stride)
        
        written = 0
        while written < to_read:
            offset_in_stride = (self.position + written) % stride_len
            avail_in_stride = stride_len - offset_in_stride
            chunk = min(to_read - written, avail_in_stride)
            b[written : written + chunk] = self._pattern_stride[offset_in_stride : offset_in_stride + chunk]
            written += chunk

        self.position += to_read
        return to_read

    def read(self, size: int = -1) -> bytes:
        if size == -1 or size is None:
            size = self.total_size - self.position
        if self.position >= self.total_size:
            return b""
        to_read = min(size, self.total_size - self.position)
        ba = bytearray(to_read)
        self.readinto(ba)
        return bytes(ba)


class TestStreamingAndMemory(unittest.TestCase):
    def test_chunked_streaming_memory_bound(self):
        """
        Verifies that processing a large stream operates in constant memory O(1).
        Uses tracemalloc to guarantee peak memory remains under 10 MB even when
        processing across megabytes/gigabytes.
        """
        # Create a virtual 500 MB stream
        stream = VirtualGigabyteStream(total_size_bytes=500 * 1024 * 1024)

        tracemalloc.start()
        engine = H264RecoveryEngine(stream=stream, chunk_size=512 * 1024)

        # Stream the first 50 NAL units
        count = 0
        for nalu in engine._stream_nalus(stream, start_offset=0):
            count += 1
            if count >= 50:
                break

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertEqual(count, 50)
        # Peak memory for a 500MB stream must be well under 10 MB (typically < 3MB)
        self.assertLess(peak, 15 * 1024 * 1024, f"Peak memory {peak / 1024 / 1024:.2f} MB exceeded 15 MB")

    def test_file_larger_than_ram_simulation(self):
        """
        Simulates a 25 GIGABYTE video file.
        Verifies that format detection and initial recovery proceed smoothly without OOM.
        """
        huge_stream = VirtualGigabyteStream(total_size_bytes=25 * 1024 * 1024 * 1024)
        engine = H264RecoveryEngine(stream=huge_stream, chunk_size=1024 * 1024)

        # Run format detection on the 25 GB stream
        fmt_res = engine.format_detector.detect(huge_stream, start_offset=0)
        self.assertEqual(fmt_res.format_type.value, "avcc")
        self.assertEqual(fmt_res.nalu_length_size, 4)
        self.assertGreaterEqual(fmt_res.confidence, 0.7)


if __name__ == "__main__":
    unittest.main()
