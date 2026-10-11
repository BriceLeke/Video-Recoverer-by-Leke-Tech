"""
H.264 Stream Format Detector.

Forensically detects whether the media stream uses:
- Annex-B Byte Stream format (0x000001 or 0x00000001 start codes)
- AVCC format (Length-prefixed NAL units, typically 4-byte big-endian)

Operates in a streaming manner using chunked reads.
"""

from enum import Enum
from typing import BinaryIO, Tuple, Dict, Any
import os

from .nalu import NALU, NALUType


class StreamFormat(str, Enum):
    ANNEX_B = "annex_b"
    AVCC = "avcc"
    UNKNOWN = "unknown"


class FormatDetectionResult:
    def __init__(
        self,
        format_type: StreamFormat,
        nalu_length_size: int = 4,
        confidence: float = 0.0,
        evidence: Dict[str, Any] = None,
    ):
        self.format_type = format_type
        self.nalu_length_size = nalu_length_size
        self.confidence = confidence
        self.evidence = evidence or {}

    def __repr__(self) -> str:
        return (
            f"FormatDetectionResult(format={self.format_type.value}, "
            f"length_size={self.nalu_length_size}, confidence={self.confidence:.2f})"
        )


class FormatDetector:
    """
    Analyzes an input stream to detect NAL unit framing format.
    """

    def __init__(self, chunk_size: int = 2 * 1024 * 1024):
        self.chunk_size = chunk_size

    def detect(self, stream: BinaryIO, start_offset: int = 0) -> FormatDetectionResult:
        """
        Scans a window of the stream starting from start_offset.
        Does NOT load the entire stream into memory.
        """
        stream.seek(start_offset)
        sample_bytes = stream.read(self.chunk_size)
        if not sample_bytes:
            return FormatDetectionResult(StreamFormat.UNKNOWN, confidence=0.0)

        # 1. Test for Annex-B start codes
        annex_b_score, annex_b_info = self._test_annex_b(sample_bytes)

        # 2. Test for AVCC length prefixes (4-byte, 2-byte)
        avcc_4_score, avcc_4_info = self._test_avcc(sample_bytes, length_size=4)
        avcc_2_score, avcc_2_info = self._test_avcc(sample_bytes, length_size=2)

        # Compare scores
        if annex_b_score > avcc_4_score and annex_b_score > avcc_2_score and annex_b_score > 0.4:
            return FormatDetectionResult(
                StreamFormat.ANNEX_B,
                nalu_length_size=0,
                confidence=min(1.0, annex_b_score),
                evidence={"annex_b": annex_b_info, "avcc_4": avcc_4_info},
            )

        if avcc_4_score >= avcc_2_score and avcc_4_score > 0.4:
            return FormatDetectionResult(
                StreamFormat.AVCC,
                nalu_length_size=4,
                confidence=min(1.0, avcc_4_score),
                evidence={"avcc_4": avcc_4_info, "annex_b": annex_b_info},
            )

        if avcc_2_score > 0.4:
            return FormatDetectionResult(
                StreamFormat.AVCC,
                nalu_length_size=2,
                confidence=min(1.0, avcc_2_score),
                evidence={"avcc_2": avcc_2_info, "annex_b": annex_b_info},
            )

        return FormatDetectionResult(
            StreamFormat.UNKNOWN,
            confidence=0.0,
            evidence={
                "annex_b_score": annex_b_score,
                "avcc_4_score": avcc_4_score,
                "avcc_2_score": avcc_2_score,
            },
        )

    def _test_annex_b(self, data: bytes) -> Tuple[float, Dict[str, Any]]:
        """Scans for valid Annex B start codes and checks subsequent NAL headers."""
        valid_start_codes = 0
        total_start_codes = 0
        pos = 0
        data_len = len(data)

        while pos < data_len - 4:
            idx = data.find(b"\x00\x00\x01", pos)
            if idx == -1:
                break

            total_start_codes += 1
            nal_byte = data[idx + 3]
            is_valid, _ = NALU.validate_header(nal_byte)
            if is_valid:
                valid_start_codes += 1
            pos = idx + 3

        if total_start_codes == 0:
            return 0.0, {"total": 0, "valid": 0}

        ratio = valid_start_codes / total_start_codes
        score = (valid_start_codes / 10.0) * ratio if total_start_codes < 10 else ratio
        return min(1.0, score), {"total": total_start_codes, "valid": valid_start_codes}

    def _test_avcc(self, data: bytes, length_size: int = 4) -> Tuple[float, Dict[str, Any]]:
        """
        Scans for valid AVCC length-prefixed NAL units.
        Rewards consecutive valid NAL units and penalties for random noise.
        """
        data_len = len(data)
        if data_len < length_size + 2:
            return 0.0, {}

        valid_chains = 0
        longest_chain = 0
        current_chain = 0
        pos = 0

        # Scan for potential NAL unit start
        while pos < min(data_len - length_size - 1, 500000):
            length = int.from_bytes(data[pos : pos + length_size], "big")
            if 10 <= length <= 500000 and pos + length_size + length <= data_len:
                header_byte = data[pos + length_size]
                is_valid, _ = NALU.validate_header(header_byte)
                if is_valid:
                    current_chain += 1
                    longest_chain = max(longest_chain, current_chain)
                    # Advance to next NALU or audio gap
                    next_pos = pos + length_size + length
                    # Allow up to 100 bytes audio gap between video frames
                    found_next = False
                    for gap in range(0, 100):
                        tp = next_pos + gap
                        if tp + length_size + 1 <= data_len:
                            t_len = int.from_bytes(data[tp : tp + length_size], "big")
                            if 10 <= t_len <= 500000:
                                t_hdr = data[tp + length_size]
                                if NALU.validate_header(t_hdr)[0]:
                                    pos = tp
                                    found_next = True
                                    break
                    if found_next:
                        continue
                    else:
                        valid_chains += 1
                        current_chain = 0
                        pos = next_pos
                        continue
            current_chain = 0
            pos += 1

        confidence = 0.0
        if longest_chain >= 5:
            confidence = min(1.0, 0.7 + (longest_chain * 0.03))
        elif longest_chain >= 2:
            confidence = 0.5 + (longest_chain * 0.05)

        return confidence, {
            "longest_chain": longest_chain,
            "valid_chains": valid_chains,
            "length_size": length_size,
        }
