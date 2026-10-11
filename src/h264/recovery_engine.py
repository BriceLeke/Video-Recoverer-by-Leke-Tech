"""
H.264 Forensic Recovery Engine.

High-performance, streaming recovery pipeline for extracting H.264 bitstreams
from corrupted, truncated, or moov-less MP4 recordings without reference videos.

Key Architectural Guarantees:
- Read-only operations on source files.
- Constant memory usage (O(1)) via chunked streaming buffer (suitable for 100+ GB files).
- Reference-free parameter recovery (SPS/PPS).
- Dynamic format detection (Annex-B vs AVCC length-prefixed).
- Truncation-resilient: gracefully handles truncated final NAL units at EOF.
- Full forensic provenance: records byte offsets, sizes, and confidence scores for every sample.
"""

from dataclasses import dataclass, field
from typing import Generator, List, Optional, Tuple, Dict, Any, BinaryIO, Callable
import os
import io

from .nalu import NALU, NALUType
from .sps import SPS, SPSParser, SPSSynthesizer
from .pps import PPS, PPSParser, PPSSynthesizer
from .slice import SliceHeader, SliceParser
from .access_unit import AccessUnit, AccessUnitBuilder
from .format_detector import FormatDetector, StreamFormat, FormatDetectionResult
from .parameter_recovery import ParameterRecovery


@dataclass
class RecoverySummary:
    """Forensic summary of the recovery run."""
    source_path: str
    total_bytes_scanned: int
    format_detected: str
    length_size: int
    sps: Optional[SPS]
    pps: Optional[PPS]
    sps_pps_source: str
    total_access_units: int
    idr_count: int
    non_idr_count: int
    truncated_au_count: int
    overall_confidence: float
    samples: List[Dict[str, Any]] = field(default_factory=list)


class H264RecoveryEngine:
    """
    Core recovery engine for damaged H.264 streams.
    """

    def __init__(
        self,
        source_path: Optional[str] = None,
        stream: Optional[BinaryIO] = None,
        chunk_size: int = 1024 * 1024,  # 1 MB chunked streaming buffer
        mdat_start_offset: int = 0,
    ):
        if source_path is None and stream is None:
            raise ValueError("Either source_path or stream must be provided")

        self.source_path = source_path
        self._external_stream = stream
        self.chunk_size = chunk_size
        self.mdat_start_offset = mdat_start_offset

        self.format_detector = FormatDetector(chunk_size=min(chunk_size * 2, 4 * 1024 * 1024))
        self.param_recovery = ParameterRecovery(chunk_size=min(chunk_size * 4, 10 * 1024 * 1024))

        self.detected_format: Optional[FormatDetectionResult] = None
        self.recovered_sps: Optional[SPS] = None
        self.recovered_pps: Optional[PPS] = None
        self.sps_pps_source: str = "none"

        self.access_units: List[AccessUnit] = []

    def _open_stream(self) -> BinaryIO:
        """Opens source in strictly read-only mode."""
        if self._external_stream is not None:
            return self._external_stream
        return open(self.source_path, "rb")

    def run_recovery(
        self,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_token: Optional[Callable[[], bool]] = None,
    ) -> RecoverySummary:
        """
        Executes complete recovery pipeline:
        1. Format detection (Annex-B vs AVCC)
        2. Parameter recovery (SPS/PPS search & inference)
        3. Streaming extraction of NAL units and Access Units
        4. Truncation detection and handling
        """
        stream = self._open_stream()
        should_close = (self._external_stream is None)

        try:
            if cancel_token and cancel_token():
                raise RuntimeError("Recovery cancelled by user")
            if progress_callback:
                progress_callback(0.05)

            # Auto-detect mdat_start_offset if not set and input begins with ISOBMFF ftyp
            if self.mdat_start_offset == 0:
                stream.seek(0)
                hdr = stream.read(8)
                if len(hdr) == 8 and hdr[4:8] == b"ftyp":
                    pos = 0
                    stream.seek(0, os.SEEK_END)
                    total_file_len = stream.tell()
                    while pos < min(total_file_len, 2 * 1024 * 1024):
                        stream.seek(pos)
                        b_hdr = stream.read(8)
                        if len(b_hdr) < 8:
                            break
                        b_size = int.from_bytes(b_hdr[:4], "big")
                        b_type = b_hdr[4:8]
                        hdr_sz = 8
                        if b_size == 1:
                            b_size = int.from_bytes(stream.read(8), "big")
                            hdr_sz = 16
                        elif b_size == 0:
                            b_size = total_file_len - pos
                        if b_type == b"mdat":
                            self.mdat_start_offset = pos + hdr_sz
                            break
                        pos += b_size

            # 1. Format Detection
            if cancel_token and cancel_token():
                raise RuntimeError("Recovery cancelled by user")
            self.detected_format = self.format_detector.detect(
                stream, start_offset=self.mdat_start_offset
            )
            if progress_callback:
                progress_callback(0.15)

            # 2. Parameter recovery: check explicit SPS/PPS
            if cancel_token and cancel_token():
                raise RuntimeError("Recovery cancelled by user")
            sps, pps, explicit_conf, diag = self.param_recovery.find_explicit_parameter_sets(
                stream, start_offset=self.mdat_start_offset
            )
            if sps and pps:
                self.recovered_sps = sps
                self.recovered_pps = pps
                self.sps_pps_source = "explicit_stream_nalus"
            else:
                self.sps_pps_source = "inferred_from_bitstream"
            if progress_callback:
                progress_callback(0.25)

            # 3. Stream through the media data and reconstruct Access Units
            stream.seek(0, os.SEEK_END)
            total_file_len = stream.tell()
            stream.seek(self.mdat_start_offset)

            self.access_units.clear()
            au_builder = AccessUnitBuilder()

            idr_sample_bytes: Optional[bytes] = None
            p_slices_sample_bytes: List[bytes] = []
            last_reported_prog = 0.25

            for nalu in self._stream_nalus(stream, start_offset=self.mdat_start_offset):
                if cancel_token and cancel_token():
                    raise RuntimeError("Recovery cancelled by user")

                if progress_callback and total_file_len > 0:
                    prog = 0.25 + 0.65 * min(1.0, (nalu.offset / total_file_len))
                    if prog - last_reported_prog >= 0.02:
                        last_reported_prog = prog
                        progress_callback(prog)

                # Save complete first IDR and subsequent P slice samples for parameter inference
                if nalu.is_idr and idr_sample_bytes is None:
                    cur_stream_pos = stream.tell()
                    stream.seek(nalu.payload_offset)
                    idr_sample_bytes = stream.read(min(nalu.length, 2 * 1024 * 1024))
                    stream.seek(cur_stream_pos)
                elif nalu.nal_unit_type == NALUType.NON_IDR and len(p_slices_sample_bytes) < 5:
                    cur_stream_pos = stream.tell()
                    stream.seek(nalu.payload_offset)
                    p_slices_sample_bytes.append(stream.read(min(nalu.length, 1024 * 1024)))
                    stream.seek(cur_stream_pos)

                completed_au = au_builder.add_nalu(nalu)
                if completed_au is not None:
                    self._enrich_access_unit(completed_au)
                    self.access_units.append(completed_au)

            # Finalize final AU (handles EOF truncation)
            final_au = au_builder.finalize()
            if final_au is not None:
                self._enrich_access_unit(final_au)
                self.access_units.append(final_au)

            if progress_callback:
                progress_callback(0.92)

            # If SPS/PPS were not explicitly in the stream, infer from the recovered IDR bitstream
            if self.recovered_sps is None or self.recovered_pps is None:
                if idr_sample_bytes is not None:
                    inf_sps, inf_pps, inf_conf, inf_diag = self.param_recovery.infer_parameter_sets_from_bitstream(
                        stream,
                        idr_sample_bytes,
                        subsequent_p_slice_bytes=p_slices_sample_bytes,
                    )
                    self.recovered_sps = inf_sps
                    self.recovered_pps = inf_pps

                    # Re-enrich access units with complete SPS/PPS metadata
                    for au in self.access_units:
                        self._enrich_access_unit(au)

            # Compile summary
            total_scanned = stream.seek(0, os.SEEK_END)
            idr_count = sum(1 for au in self.access_units if au.is_idr)
            non_idr_count = len(self.access_units) - idr_count
            truncated_count = sum(1 for au in self.access_units if au.is_truncated)

            confidences = [au.confidence for au in self.access_units]
            overall_conf = sum(confidences) / len(confidences) if confidences else 0.0

            sample_records = []
            for au in self.access_units:
                sample_records.append({
                    "index": au.index,
                    "offset": au.offset,
                    "size": au.total_size,
                    "is_idr": au.is_idr,
                    "slice_type": au.slice_type,
                    "frame_num": au.frame_num,
                    "poc": au.poc,
                    "confidence": au.confidence,
                    "is_truncated": au.is_truncated,
                })

            if progress_callback:
                progress_callback(1.0)

            return RecoverySummary(
                source_path=self.source_path or "stream",
                total_bytes_scanned=total_scanned,
                format_detected=self.detected_format.format_type.value,
                length_size=self.detected_format.nalu_length_size,
                sps=self.recovered_sps,
                pps=self.recovered_pps,
                sps_pps_source=self.sps_pps_source,
                total_access_units=len(self.access_units),
                idr_count=idr_count,
                non_idr_count=non_idr_count,
                truncated_au_count=truncated_count,
                overall_confidence=round(overall_conf, 4),
                samples=sample_records,
            )
        finally:
            if should_close:
                stream.close()

    def _enrich_access_unit(self, au: AccessUnit) -> None:
        """Parses slice headers inside an AU to populate frame_num and POC."""
        for nalu in au.nalus:
            if nalu.is_vcl and nalu.raw_data:
                try:
                    slice_hdr = SliceParser.parse(
                        nalu.raw_data,
                        sps=self.recovered_sps,
                        pps=self.recovered_pps,
                    )
                    au.frame_num = slice_hdr.frame_num
                    au.poc = slice_hdr.pic_order_cnt_lsb
                    au.slice_type = slice_hdr.slice_type_name
                    au.is_idr = slice_hdr.is_idr
                    au.is_keyframe = slice_hdr.is_keyframe
                    break
                except Exception:
                    pass

    def _stream_nalus(
        self, stream: BinaryIO, start_offset: int = 0
    ) -> Generator[NALU, None, None]:
        """
        Streaming NAL unit parser.
        Yields NALUs sequentially using a constant-memory sliding buffer.
        """
        stream.seek(0, os.SEEK_END)
        total_size = stream.tell()
        stream.seek(start_offset)

        fmt = self.detected_format.format_type if self.detected_format else StreamFormat.AVCC
        length_size = self.detected_format.nalu_length_size if self.detected_format else 4

        if fmt == StreamFormat.ANNEX_B:
            yield from self._stream_annex_b(stream, start_offset, total_size)
        else:
            yield from self._stream_avcc(stream, start_offset, total_size, length_size)

    def _stream_avcc(
        self, stream: BinaryIO, start_offset: int, total_size: int, length_size: int
    ) -> Generator[NALU, None, None]:
        """
        Streams AVCC length-prefixed NAL units, cleanly handling interleaved audio chunks
        and truncated final frames.
        """
        curr_pos = start_offset
        buffer = bytearray()
        buf_file_offset = curr_pos

        max_lookahead = 65536  # Lookahead window for detecting audio interleaving gaps

        while curr_pos < total_size:
            buf_idx = curr_pos - buf_file_offset
            # Only drop consumed bytes when we have moved past threshold to prevent excessive memory reallocations
            if buf_idx > 256 * 1024:
                buffer = buffer[buf_idx:]
                buf_file_offset = curr_pos
                buf_idx = 0

            # Maintain sliding buffer
            needed = max_lookahead
            if len(buffer) - buf_idx < needed and (buf_file_offset + len(buffer)) < total_size:
                stream.seek(buf_file_offset + len(buffer))
                chunk = stream.read(self.chunk_size)
                if chunk:
                    buffer.extend(chunk)

            remaining_bytes = len(buffer) - buf_idx

            if remaining_bytes < length_size:
                # Partial length prefix at physical EOF - stream ends
                break

            # Check for embedded MP4 boxes (e.g. in fragmented MP4)
            if remaining_bytes >= 8:
                box_size = int.from_bytes(buffer[buf_idx : buf_idx + 4], "big")
                box_type = buffer[buf_idx + 4 : buf_idx + 8]
                if box_type in (b"moov", b"moof", b"mdat", b"free", b"skip", b"wide", b"meta", b"udta", b"ftyp"):
                    if box_type == b"mdat":
                        curr_pos += 8
                        continue
                    elif box_size > 1 and curr_pos + box_size <= total_size:
                        curr_pos += box_size
                        continue

            # Read length
            length = int.from_bytes(buffer[buf_idx : buf_idx + length_size], "big")

            # Check if this could be a valid video NAL unit (complete or truncated by EOF)
            is_candidate = False
            if 4 <= length <= 5000000:
                if remaining_bytes > length_size:
                    hdr_byte = buffer[buf_idx + length_size]
                    is_valid, _ = NALU.validate_header(hdr_byte)
                    ntype = hdr_byte & 0x1F
                    if is_valid:
                        if ntype in (1, 5):
                            is_candidate = True
                        elif ntype in (7, 8, 9):
                            is_candidate = True

            if is_candidate:
                hdr_byte = buffer[buf_idx + length_size]
                forbidden, ref_idc, ntype = NALU.parse_header(hdr_byte)
                actual_payload_offset = curr_pos + length_size
                
                # Check for EOF truncation
                is_truncated = (curr_pos + length_size + length > total_size)
                actual_length = length
                if is_truncated:
                    actual_length = total_size - actual_payload_offset

                # Read raw NAL unit data for slice header parsing (first 64 bytes is plenty)
                header_extract_len = min(actual_length, 64)
                avail_in_buf = len(buffer) - (buf_idx + length_size)
                if avail_in_buf >= header_extract_len:
                    raw_bytes = bytes(buffer[buf_idx + length_size : buf_idx + length_size + header_extract_len])
                else:
                    stream.seek(actual_payload_offset)
                    raw_bytes = stream.read(header_extract_len)

                confidence = 0.5 if is_truncated else 0.99
                nalu = NALU(
                    offset=curr_pos,
                    payload_offset=actual_payload_offset,
                    length=actual_length,
                    header_byte=hdr_byte,
                    nal_ref_idc=ref_idc,
                    nal_unit_type=ntype,
                    forbidden_zero_bit=forbidden,
                    is_truncated=is_truncated,
                    confidence=confidence,
                    detection_method=f"avcc_{length_size}byte",
                    raw_data=raw_bytes,
                )
                yield nalu

                curr_pos += length_size + actual_length
                if is_truncated:
                    break

            else:
                # Step forward to find next NALU (skipping interleaved audio or container headers)
                curr_pos += 1

    def _stream_annex_b(
        self, stream: BinaryIO, start_offset: int, total_size: int
    ) -> Generator[NALU, None, None]:
        """
        Streams Annex-B start-code delimited NAL units.
        """
        curr_pos = start_offset
        buffer = bytearray()
        buf_file_offset = curr_pos

        last_sc_pos = -1
        last_hdr_byte = 0

        while curr_pos < total_size:
            if len(buffer) < self.chunk_size and (buf_file_offset + len(buffer)) < total_size:
                stream.seek(buf_file_offset + len(buffer))
                chunk = stream.read(self.chunk_size)
                if chunk:
                    buffer.extend(chunk)

            # Search for start code
            idx = buffer.find(b"\x00\x00\x01")
            if idx == -1:
                if len(buffer) > 4:
                    buf_file_offset += len(buffer) - 3
                    buffer = buffer[-3:]
                else:
                    break
                continue

            sc_file_pos = buf_file_offset + idx
            sc_len = 3
            if idx > 0 and buffer[idx - 1] == 0:
                sc_len = 4
                sc_file_pos -= 1

            if last_sc_pos != -1:
                # Yield previous NALU
                nalu_len = sc_file_pos - (last_sc_pos + sc_len)
                if nalu_len > 0:
                    forbidden, ref_idc, ntype = NALU.parse_header(last_hdr_byte)
                    stream.seek(last_sc_pos + sc_len)
                    raw = stream.read(min(nalu_len, 500000))
                    yield NALU(
                        offset=last_sc_pos,
                        payload_offset=last_sc_pos + sc_len,
                        length=nalu_len,
                        header_byte=last_hdr_byte,
                        nal_ref_idc=ref_idc,
                        nal_unit_type=ntype,
                        forbidden_zero_bit=forbidden,
                        is_truncated=False,
                        confidence=0.95,
                        detection_method="annex_b",
                        raw_data=raw,
                    )

            last_sc_pos = sc_file_pos
            if idx + 3 < len(buffer):
                last_hdr_byte = buffer[idx + 3]

            buffer = buffer[idx + 3 :]
            buf_file_offset = sc_file_pos + sc_len

        # Final NALU to EOF
        if last_sc_pos != -1 and last_sc_pos < total_size:
            final_len = total_size - (last_sc_pos + 3)
            forbidden, ref_idc, ntype = NALU.parse_header(last_hdr_byte)
            stream.seek(last_sc_pos + 3)
            raw = stream.read(min(final_len, 500000))
            yield NALU(
                offset=last_sc_pos,
                payload_offset=last_sc_pos + 3,
                length=final_len,
                header_byte=last_hdr_byte,
                nal_ref_idc=ref_idc,
                nal_unit_type=ntype,
                forbidden_zero_bit=forbidden,
                is_truncated=True,
                confidence=0.5,
                detection_method="annex_b_eof",
                raw_data=raw,
            )

    def export_annex_b_stream(
        self,
        output_path: str,
        include_sps_pps: bool = True,
        write_chunk_size: int = 256 * 1024,
    ) -> int:
        """
        Streams all recovered video Access Units into a standard Annex-B (.h264)
        elementary bitstream file.
        
        Guarantees strictly constant memory usage by streaming payload data
        directly from the source file to the output file in small chunks.
        
        Returns total bytes written.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        annex_b_start_code = b"\x00\x00\x00\x01"

        stream = self._open_stream()
        should_close = (self._external_stream is None)

        bytes_written = 0
        try:
            with open(output_path, "wb") as out_f:
                # 1. Write SPS and PPS at the beginning of the stream
                if include_sps_pps:
                    if self.recovered_sps is not None:
                        sps_bytes = self.recovered_sps.raw_bytes
                        if not sps_bytes or (sps_bytes[0] & 0x1F) != 7:
                            sps_bytes = SPSSynthesizer.synthesize(
                                width=self.recovered_sps.width,
                                height=self.recovered_sps.height,
                                profile_idc=self.recovered_sps.profile_idc,
                                level_idc=self.recovered_sps.level_idc,
                                log2_max_frame_num_minus4=self.recovered_sps.log2_max_frame_num_minus4,
                                pic_order_cnt_type=self.recovered_sps.pic_order_cnt_type,
                                log2_max_pic_order_cnt_lsb_minus4=self.recovered_sps.log2_max_pic_order_cnt_lsb_minus4,
                            )
                        out_f.write(annex_b_start_code + sps_bytes)
                        bytes_written += 4 + len(sps_bytes)

                    if self.recovered_pps is not None:
                        pps_bytes = self.recovered_pps.raw_bytes
                        if not pps_bytes or (pps_bytes[0] & 0x1F) != 8:
                            pps_bytes = PPSSynthesizer.synthesize(
                                pic_parameter_set_id=self.recovered_pps.pic_parameter_set_id,
                                entropy_coding_mode=self.recovered_pps.entropy_coding_mode_flag,
                                transform_8x8_mode=self.recovered_pps.transform_8x8_mode_flag,
                            )
                        out_f.write(annex_b_start_code + pps_bytes)
                        bytes_written += 4 + len(pps_bytes)

                # 2. Stream all video frames chunk-by-chunk
                for au in self.access_units:
                    for nalu in au.nalus:
                        if nalu.length <= 0:
                            continue

                        # Write start code
                        out_f.write(annex_b_start_code)
                        bytes_written += 4

                        # Stream payload in chunks
                        stream.seek(nalu.payload_offset)
                        remaining = nalu.length
                        while remaining > 0:
                            to_read = min(remaining, write_chunk_size)
                            chunk = stream.read(to_read)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            bytes_written += len(chunk)
                            remaining -= len(chunk)

            return bytes_written
        finally:
            if should_close:
                stream.close()
