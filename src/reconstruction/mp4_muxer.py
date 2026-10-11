"""
High-Performance ISOBMFF / MP4 Container Reconstruction Engine.

Assembles fully compliant, reference-free MP4 containers from recovered video
and audio bitstreams, supporting:
- ISO Base Media File Format structures: ftyp, mdat, moov, mvhd, trak, tkhd, mdia,
  mdhd, hdlr, minf, vmhd/smhd, dinf, dref, stbl, stsd, stts, stsc, stsz, stco/co64, stss.
- Reference-free codec configuration (avcC with inferred/recovered SPS/PPS).
- Multi-gigabyte streaming with constant O(1) memory usage.
- 64-bit chunk offsets (co64) and 64-bit mdat extended headers for files > 4 GB.
- Truncated final frame safe termination and length-prefix healing.
- Exact keyframe seeking table (stss) indexing all recovered IDR frames.
"""

import os
import struct
import io
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

from .box_writer import BoxWriter
from .codec_config import H264CodecConfig, AACCodecConfig
from .sample_table import SampleRecord, SampleTableBuilder
from .track import Track, TrackType
from .moov_builder import MoovBuilder


class MP4Muxer:
    """
    Core multiplexer and container reconstructor for ISOBMFF / MP4.
    """

    def __init__(self, chunk_size: int = 1024 * 1024):
        self.chunk_size = chunk_size

    @staticmethod
    def build_ftyp(
        major_brand: bytes = b"isom",
        minor_version: int = 0x00000200,
        compatible_brands: Optional[List[bytes]] = None,
    ) -> bytes:
        """
        Builds the 'ftyp' (File Type) box.
        ISO/IEC 14496-12 Section 4.3.
        """
        if compatible_brands is None:
            compatible_brands = [b"isom", b"iso2", b"avc1", b"mp41"]

        payload = bytearray()
        payload.extend(major_brand)
        payload.extend(struct.pack(">I", minor_version))
        for brand in compatible_brands:
            payload.extend(brand)

        return BoxWriter.box(b"ftyp", bytes(payload))

    def reconstruct(
        self,
        output_path: str,
        video_track: Track,
        audio_track: Optional[Track] = None,
        source_stream: Optional[BinaryIO] = None,
        source_sample_data: Optional[Dict[int, bytes]] = None,
        force_64bit: bool = False,
    ) -> int:
        """
        Reconstructs a new MP4 container from the provided tracks.
        
        Args:
            output_path: File path to save the recovered MP4.
            video_track: Video track containing H.264 configuration and samples.
            audio_track: Optional audio track containing AAC configuration and samples.
            source_stream: Open read-only binary stream to the source file for zero-copy streaming.
            source_sample_data: Optional in-memory sample dictionary mapping id(sample) -> bytes.
            force_64bit: If True, forces 64-bit co64 chunk offsets and large mdat headers.
            
        Returns:
            Total bytes written to the reconstructed MP4 file.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        tracks = [video_track]
        if audio_track:
            tracks.append(audio_track)

        # 1. Determine if we need 64-bit mdat header
        total_media_size = sum(s.size for t in tracks for s in t.samples)
        use_large_mdat = force_64bit or (total_media_size >= 0xFFFFFF00)
        mdat_header_size = 16 if use_large_mdat else 8

        # Cache source file size if source_stream provided
        source_file_len = 0
        if source_stream is not None:
            source_stream.seek(0, os.SEEK_END)
            source_file_len = source_stream.tell()

        # Open output file in binary write mode
        with open(output_path, "wb") as out_f:
            # Step A: Write ftyp box
            ftyp_bytes = self.build_ftyp()
            out_f.write(ftyp_bytes)
            ftyp_size = len(ftyp_bytes)

            # Step B: Write placeholder mdat header
            mdat_offset = ftyp_size
            if use_large_mdat:
                out_f.write(struct.pack(">I4sQ", 1, b"mdat", 0))
            else:
                out_f.write(struct.pack(">I4s", 0, b"mdat"))

            media_data_start = mdat_offset + mdat_header_size

            # Chunk offsets and chunk sample counts per track
            chunk_offsets_by_track: Dict[int, List[int]] = {}
            chunk_samples_by_track: Dict[int, List[int]] = {}

            # Step C: Stream media data into mdat
            for track in tracks:
                track_chunk_offsets: List[int] = []
                track_chunk_samples: List[int] = []
                valid_samples: List[SampleRecord] = []

                for sample in track.samples:
                    if sample.size <= 0:
                        continue

                    # Handle truncated final frame safely
                    actual_sample_size = sample.size
                    is_eof_truncated = sample.is_truncated
                    if not is_eof_truncated and source_stream is not None and source_file_len > 0:
                        if sample.source_offset + sample.size > source_file_len:
                            is_eof_truncated = True

                    if is_eof_truncated:
                        if source_stream is not None and source_file_len > 0:
                            surviving = max(0, source_file_len - sample.source_offset)
                            if surviving <= 4:
                                # Incomplete length prefix or 0 payload at EOF - safely drop
                                continue
                            actual_sample_size = surviving

                    # Record chunk offset (1 sample per chunk)
                    sample_file_offset = out_f.tell()
                    track_chunk_offsets.append(sample_file_offset)
                    track_chunk_samples.append(1)
                    sample.offset = sample_file_offset

                    # Write sample payload
                    if source_sample_data and id(sample) in source_sample_data:
                        out_f.write(source_sample_data[id(sample)])
                        sample.size = len(source_sample_data[id(sample)])
                        valid_samples.append(sample)
                    elif source_stream is not None:
                        if is_eof_truncated:
                            # Heal truncated length prefix: write actual surviving payload length
                            healed_payload_len = actual_sample_size - 4
                            out_f.write(healed_payload_len.to_bytes(4, "big"))
                            source_stream.seek(sample.source_offset + 4)
                            out_f.write(source_stream.read(healed_payload_len))
                            sample.size = actual_sample_size
                        else:
                            source_stream.seek(sample.source_offset)
                            remaining = sample.size
                            while remaining > 0:
                                to_read = min(remaining, self.chunk_size)
                                chunk = source_stream.read(to_read)
                                if not chunk:
                                    break
                                out_f.write(chunk)
                                remaining -= len(chunk)
                        valid_samples.append(sample)
                    else:
                        raise ValueError("Neither source_stream nor source_sample_data provided")

                # Update track with filtered/healed valid samples
                track.samples = valid_samples
                chunk_offsets_by_track[track.track_id] = track_chunk_offsets
                chunk_samples_by_track[track.track_id] = track_chunk_samples

            media_data_end = out_f.tell()
            actual_media_size = media_data_end - media_data_start
            total_mdat_box_size = mdat_header_size + actual_media_size

            # Step D: Patch mdat header with actual total box size
            out_f.seek(mdat_offset)
            if use_large_mdat:
                out_f.write(struct.pack(">I4sQ", 1, b"mdat", total_mdat_box_size))
            else:
                if total_mdat_box_size >= 0x100000000:
                    raise RuntimeError("mdat exceeded 4GB without use_large_mdat enabled")
                out_f.write(struct.pack(">I4s", total_mdat_box_size, b"mdat"))

            # Step E: Build and append 'moov' box
            out_f.seek(media_data_end)
            moov_bytes = MoovBuilder.build_moov(
                tracks=tracks,
                chunk_offsets_by_track=chunk_offsets_by_track,
                chunk_samples_by_track=chunk_samples_by_track,
                movie_timescale=1000,
                force_64bit=force_64bit,
            )
            out_f.write(moov_bytes)
            total_bytes_written = out_f.tell()

        return total_bytes_written

    @classmethod
    def reconstruct_from_recovery_summary(
        cls,
        summary: Any,
        output_path: str,
        fps: float = 30.0,
        timescale: int = 90000,
        force_64bit: bool = False,
    ) -> int:
        """
        Convenience factory to reconstruct an MP4 container directly from a
        RecoverySummary object produced by H264RecoveryEngine.
        
        Args:
            summary: RecoverySummary from H264RecoveryEngine.
            output_path: Destination path for the reconstructed MP4 file.
            fps: Video framerate (default 30.0 fps).
            timescale: Video timescale in Hz (default 90,000 Hz).
            force_64bit: If True, forces 64-bit co64 chunk offsets and large mdat header.
            
        Returns:
            Total bytes written to the reconstructed MP4 file.
        """
        if summary.sps is None or summary.pps is None:
            raise ValueError("RecoverySummary missing SPS or PPS configuration")

        # 1. Build H264CodecConfig
        sps_bytes = summary.sps.raw_bytes
        pps_bytes = summary.pps.raw_bytes
        codec_config = H264CodecConfig(
            sps=sps_bytes,
            pps=pps_bytes,
            width=summary.sps.width,
            height=summary.sps.height,
            profile_idc=summary.sps.profile_idc,
            level_idc=summary.sps.level_idc,
            nal_length_size=summary.length_size or 4,
        )

        # 2. Build Video Sample Records
        frame_duration = int(round(timescale / fps)) if fps > 0 else 3000
        length_size = summary.length_size or 4
        samples: List[SampleRecord] = []

        for sample_info in summary.samples:
            payload_size = sample_info.get("size", 0)
            if payload_size <= 0:
                continue

            is_idr = sample_info.get("is_idr", False)
            source_offset = sample_info.get("offset", 0)
            is_truncated = sample_info.get("is_truncated", False)

            # In AVCC MP4, the sample in mdat includes the 4-byte length prefix
            # plus the NAL unit payload.
            total_sample_size = length_size + payload_size

            sample_rec = SampleRecord(
                size=total_sample_size,
                duration=frame_duration,
                is_sync=is_idr,
                source_offset=source_offset,
                is_truncated=is_truncated,
            )
            samples.append(sample_rec)

        # 3. Build Video Track
        video_track = Track(
            track_id=1,
            track_type=TrackType.VIDEO,
            timescale=timescale,
            codec_config=codec_config,
            width=summary.sps.width,
            height=summary.sps.height,
            samples=samples,
        )

        # 4. Stream and write MP4 container
        muxer = cls()
        with open(summary.source_path, "rb") as src_f:
            bytes_written = muxer.reconstruct(
                output_path=output_path,
                video_track=video_track,
                source_stream=src_f,
                force_64bit=force_64bit,
            )

        return bytes_written
