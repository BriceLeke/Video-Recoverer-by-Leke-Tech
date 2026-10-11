"""
Sample Table (stbl) Box Builders.

Implements ISO/IEC 14496-12 compliant sample table generation:
- stsd: Sample Description Box
- stts: Time-to-Sample Box (run-length compressed)
- stss: Sync Sample (Keyframe) Box
- stsc: Sample-to-Chunk Box (run-length compressed)
- stsz: Sample Size Box
- stco: 32-bit Chunk Offset Box
- co64: 64-bit Chunk Offset Box (for >4 GB files and large offsets)
- ctts: Composition Time to Sample Box (when B-frames / presentation offsets present)
"""

import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .box_writer import BoxWriter


@dataclass
class SampleRecord:
    """
    Metadata for a single media sample in the reconstructed container.
    """
    size: int
    duration: int
    is_sync: bool = False
    source_offset: int = 0
    offset: int = 0  # Reconstructed target offset in output mdat
    composition_offset: int = 0
    is_truncated: bool = False


class SampleTableBuilder:
    """
    Constructs the 'stbl' container box and all child sample index tables.
    """

    @staticmethod
    def build_stsd(entry_boxes: List[bytes]) -> bytes:
        """
        Builds the 'stsd' (Sample Description) box.
        ISO/IEC 14496-12 Section 8.5.2.
        """
        payload = bytearray(struct.pack(">I", len(entry_boxes)))
        for entry in entry_boxes:
            payload.extend(entry)
        return BoxWriter.full_box(b"stsd", 0, 0, bytes(payload))

    @staticmethod
    def build_stts(samples: List[SampleRecord]) -> bytes:
        """
        Builds the 'stts' (Decoding Time-to-Sample) box.
        Run-length encodes consecutive samples with the same duration.
        ISO/IEC 14496-12 Section 8.6.1.2.
        """
        if not samples:
            return BoxWriter.full_box(b"stts", 0, 0, struct.pack(">I", 0))

        # Run-length compression: (count, delta)
        entries: List[Tuple[int, int]] = []
        current_delta = samples[0].duration
        current_count = 0

        for sample in samples:
            if sample.duration == current_delta:
                current_count += 1
            else:
                entries.append((current_count, current_delta))
                current_delta = sample.duration
                current_count = 1
        if current_count > 0:
            entries.append((current_count, current_delta))

        payload = bytearray(struct.pack(">I", len(entries)))
        for count, delta in entries:
            payload.extend(struct.pack(">II", count, delta))

        return BoxWriter.full_box(b"stts", 0, 0, bytes(payload))

    @staticmethod
    def build_stss(samples: List[SampleRecord]) -> Optional[bytes]:
        """
        Builds the 'stss' (Sync Sample) box for random access / seeking.
        Lists 1-based sample numbers of keyframes (IDR frames).
        ISO/IEC 14496-12 Section 8.6.2.
        Returns None if all samples are sync samples (omitted per spec).
        """
        sync_indices = [
            i + 1 for i, s in enumerate(samples) if s.is_sync
        ]

        if not sync_indices:
            # If no sync samples flagged, mark first sample as sync
            sync_indices = [1]

        # If every sample is sync, stss is optional/omitted in ISOBMFF,
        # but for video with mixed frames, stss is required.
        payload = bytearray(struct.pack(">I", len(sync_indices)))
        for idx in sync_indices:
            payload.extend(struct.pack(">I", idx))

        return BoxWriter.full_box(b"stss", 0, 0, bytes(payload))

    @staticmethod
    def build_stsc(chunk_sample_counts: List[int]) -> bytes:
        """
        Builds the 'stsc' (Sample-to-Chunk) box.
        Run-length encodes consecutive chunks that have the same sample count.
        ISO/IEC 14496-12 Section 8.7.4.
        """
        if not chunk_sample_counts:
            # 1 chunk with 1 sample
            payload = struct.pack(">IIII", 1, 1, 1, 1)
            return BoxWriter.full_box(b"stsc", 0, 0, payload)

        entries: List[Tuple[int, int, int]] = []  # (first_chunk, samples_per_chunk, sample_desc_idx)
        prev_count = -1

        for chunk_idx, count in enumerate(chunk_sample_counts):
            chunk_num = chunk_idx + 1  # 1-indexed
            if count != prev_count:
                entries.append((chunk_num, count, 1))
                prev_count = count

        payload = bytearray(struct.pack(">I", len(entries)))
        for first_chunk, count, desc_idx in entries:
            payload.extend(struct.pack(">III", first_chunk, count, desc_idx))

        return BoxWriter.full_box(b"stsc", 0, 0, bytes(payload))

    @staticmethod
    def build_stsz(samples: List[SampleRecord]) -> bytes:
        """
        Builds the 'stsz' (Sample Size) box.
        ISO/IEC 14496-12 Section 8.7.3.2.
        """
        sample_count = len(samples)
        if sample_count == 0:
            return BoxWriter.full_box(b"stsz", 0, 0, struct.pack(">II", 0, 0))

        # Check if all samples have identical size
        first_size = samples[0].size
        all_same = all(s.size == first_size for s in samples)

        if all_same:
            payload = struct.pack(">II", first_size, sample_count)
        else:
            payload = bytearray(struct.pack(">II", 0, sample_count))
            for s in samples:
                payload.extend(struct.pack(">I", s.size))

        return BoxWriter.full_box(b"stsz", 0, 0, bytes(payload))

    @staticmethod
    def build_stco_or_co64(
        chunk_offsets: List[int], force_64bit: bool = False
    ) -> bytes:
        """
        Builds either 'stco' (32-bit chunk offsets) or 'co64' (64-bit chunk offsets).
        Automatically upgrades to 'co64' if any offset >= 4 GB (0xFFFFFFFF) or if forced.
        ISO/IEC 14496-12 Section 8.7.5 and 8.7.6.
        """
        needs_64bit = force_64bit or any(offset >= 0xFFFFFFFF for offset in chunk_offsets)

        if needs_64bit:
            payload = bytearray(struct.pack(">I", len(chunk_offsets)))
            for offset in chunk_offsets:
                payload.extend(struct.pack(">Q", offset))
            return BoxWriter.full_box(b"co64", 0, 0, bytes(payload))
        else:
            payload = bytearray(struct.pack(">I", len(chunk_offsets)))
            for offset in chunk_offsets:
                payload.extend(struct.pack(">I", offset))
            return BoxWriter.full_box(b"stco", 0, 0, bytes(payload))

    @staticmethod
    def build_ctts(samples: List[SampleRecord]) -> Optional[bytes]:
        """
        Builds the 'ctts' (Composition Time to Sample) box if any sample has
        non-zero composition offset (e.g. B-frames / POC reordering).
        ISO/IEC 14496-12 Section 8.6.1.3.
        """
        has_ctts = any(s.composition_offset != 0 for s in samples)
        if not has_ctts:
            return None

        entries: List[Tuple[int, int]] = []
        cur_offset = samples[0].composition_offset
        cur_count = 0

        for s in samples:
            if s.composition_offset == cur_offset:
                cur_count += 1
            else:
                entries.append((cur_count, cur_offset))
                cur_offset = s.composition_offset
                cur_count = 1
        if cur_count > 0:
            entries.append((cur_count, cur_offset))

        payload = bytearray(struct.pack(">I", len(entries)))
        for count, offset in entries:
            payload.extend(struct.pack(">II", count, offset))

        return BoxWriter.full_box(b"ctts", 0, 0, bytes(payload))

    @classmethod
    def build_stbl(
        cls,
        sample_entries: List[bytes],
        samples: List[SampleRecord],
        chunk_offsets: List[int],
        chunk_sample_counts: List[int],
        is_video: bool = True,
        force_64bit: bool = False,
    ) -> bytes:
        """
        Assembles the complete 'stbl' (Sample Table) box with all child tables.
        """
        payload = bytearray()

        # 1. stsd (Sample Description)
        payload.extend(cls.build_stsd(sample_entries))

        # 2. stts (Time-to-Sample)
        payload.extend(cls.build_stts(samples))

        # 3. stss (Sync Sample / Keyframes) - written for video
        if is_video:
            stss_box = cls.build_stss(samples)
            if stss_box:
                payload.extend(stss_box)

        # 4. ctts (Composition Time) if present
        ctts_box = cls.build_ctts(samples)
        if ctts_box:
            payload.extend(ctts_box)

        # 5. stsc (Sample-to-Chunk)
        payload.extend(cls.build_stsc(chunk_sample_counts))

        # 6. stsz (Sample Sizes)
        payload.extend(cls.build_stsz(samples))

        # 7. stco / co64 (Chunk Offsets)
        payload.extend(cls.build_stco_or_co64(chunk_offsets, force_64bit=force_64bit))

        return BoxWriter.box(b"stbl", bytes(payload))
