"""
Track Model and ISOBMFF Track Hierarchy Builder.

Implements track container generation:
trak -> tkhd, mdia -> mdhd, hdlr, minf -> vmhd/smhd, dinf (dref), stbl.
ISO/IEC 14496-12 compliant.
"""

from enum import Enum
import struct
from typing import List, Optional, Union

from .box_writer import BoxWriter
from .codec_config import H264CodecConfig, AACCodecConfig
from .sample_table import SampleRecord, SampleTableBuilder


class TrackType(Enum):
    VIDEO = "vide"
    AUDIO = "soun"


class Track:
    """
    Represents a single media track (video or audio) in the MP4 container.
    """

    def __init__(
        self,
        track_id: int,
        track_type: TrackType,
        timescale: int,
        codec_config: Union[H264CodecConfig, AACCodecConfig],
        width: int = 0,
        height: int = 0,
        samples: Optional[List[SampleRecord]] = None,
    ):
        self.track_id = track_id
        self.track_type = track_type
        self.timescale = timescale
        self.codec_config = codec_config
        self.width = width
        self.height = height
        self.samples: List[SampleRecord] = samples or []

    @property
    def is_video(self) -> bool:
        return self.track_type == TrackType.VIDEO

    @property
    def is_audio(self) -> bool:
        return self.track_type == TrackType.AUDIO

    def get_duration(self) -> int:
        """Total track duration in media timescale units."""
        return sum(s.duration for s in self.samples)

    def get_duration_in_movie_timescale(self, movie_timescale: int) -> int:
        """Converts media duration to movie timescale units for tkhd."""
        media_dur = self.get_duration()
        if self.timescale == 0:
            return 0
        return int((media_dur * movie_timescale) / self.timescale)

    def build_tkhd(self, movie_timescale: int) -> bytes:
        """
        Builds the 'tkhd' (Track Header) box.
        ISO/IEC 14496-12 Section 8.3.2.
        """
        flags = 0x000007  # TrackEnabled (1) | TrackInMovie (2) | TrackInPreview (4)
        duration_mv = self.get_duration_in_movie_timescale(movie_timescale)
        volume = 0.0 if self.is_video else 1.0

        payload = bytearray()
        # creation_time (uint32 = 0), modification_time (uint32 = 0)
        payload.extend(struct.pack(">II", 0, 0))
        # track_id (uint32)
        payload.extend(struct.pack(">I", self.track_id))
        # reserved = 0 (uint32)
        payload.extend(struct.pack(">I", 0))
        # duration (uint32 in movie timescale)
        payload.extend(struct.pack(">I", duration_mv))
        # reserved[2] = 0 (uint32[2] = 8 bytes)
        payload.extend(struct.pack(">II", 0, 0))
        # layer = 0 (int16), alternate_group = 0 (int16)
        payload.extend(struct.pack(">hh", 0, 0))
        # volume (8.8 fixed point)
        payload.extend(BoxWriter.fixed_point_8_8(volume))
        # reserved = 0 (uint16)
        payload.extend(struct.pack(">H", 0))
        # matrix (36 bytes unity matrix)
        payload.extend(BoxWriter.unity_matrix())
        # width, height (16.16 fixed point)
        payload.extend(BoxWriter.fixed_point_16_16(float(self.width)))
        payload.extend(BoxWriter.fixed_point_16_16(float(self.height)))

        return BoxWriter.full_box(b"tkhd", 0, flags, bytes(payload))

    def build_mdhd(self) -> bytes:
        """
        Builds the 'mdhd' (Media Header) box.
        ISO/IEC 14496-12 Section 8.4.2.
        """
        media_dur = self.get_duration()
        payload = bytearray()
        # creation_time (0), modification_time (0)
        payload.extend(struct.pack(">II", 0, 0))
        # timescale (media timescale, e.g. 90000)
        payload.extend(struct.pack(">I", self.timescale))
        # duration (media duration in media timescale units)
        payload.extend(struct.pack(">I", media_dur))
        # language (packed 16-bit code 'und' = 0x55C4)
        payload.extend(BoxWriter.language_code("und"))
        # pre_defined = 0 (uint16)
        payload.extend(struct.pack(">H", 0))

        return BoxWriter.full_box(b"mdhd", 0, 0, bytes(payload))

    def build_hdlr(self) -> bytes:
        """
        Builds the 'hdlr' (Handler Reference) box.
        ISO/IEC 14496-12 Section 8.4.3.
        """
        handler_type = self.track_type.value.encode("ascii")
        name = b"VideoHandler\x00" if self.is_video else b"SoundHandler\x00"

        payload = bytearray()
        # pre_defined = 0 (uint32)
        payload.extend(struct.pack(">I", 0))
        # handler_type (4 bytes: 'vide' or 'soun')
        payload.extend(handler_type)
        # reserved[3] = 0 (uint32[3] = 12 bytes)
        payload.extend(b"\x00" * 12)
        # name (null-terminated UTF-8 string)
        payload.extend(name)

        return BoxWriter.full_box(b"hdlr", 0, 0, bytes(payload))

    def build_vmhd_or_smhd(self) -> bytes:
        """
        Builds 'vmhd' (Video Media Header) or 'smhd' (Sound Media Header).
        """
        if self.is_video:
            # vmhd: version 0, flags 1 (graphicsmode=0, opcolor=(0,0,0))
            payload = struct.pack(">HHHH", 0, 0, 0, 0)
            return BoxWriter.full_box(b"vmhd", 0, 1, payload)
        else:
            # smhd: version 0, flags 0 (balance=0, reserved=0)
            payload = struct.pack(">hh", 0, 0)
            return BoxWriter.full_box(b"smhd", 0, 0, payload)

    @staticmethod
    def build_dinf() -> bytes:
        """
        Builds 'dinf' (Data Information) box containing 'dref'.
        Points to the same file (self-contained media data).
        """
        # url box with flags = 1 (in-file media)
        url_box = BoxWriter.full_box(b"url ", 0, 1, b"")
        # dref box containing the url box
        dref_payload = struct.pack(">I", 1) + url_box
        dref_box = BoxWriter.full_box(b"dref", 0, 0, dref_payload)
        return BoxWriter.box(b"dinf", dref_box)

    def build_minf(
        self,
        chunk_offsets: List[int],
        chunk_sample_counts: List[int],
        force_64bit: bool = False,
    ) -> bytes:
        """
        Builds 'minf' (Media Information) box containing vmhd/smhd, dinf, and stbl.
        """
        payload = bytearray()
        # 1. Media header (vmhd or smhd)
        payload.extend(self.build_vmhd_or_smhd())

        # 2. Data info (dinf)
        payload.extend(self.build_dinf())

        # 3. Sample table (stbl)
        sample_entries = []
        if isinstance(self.codec_config, H264CodecConfig):
            sample_entries.append(self.codec_config.build_avc1())
        elif isinstance(self.codec_config, AACCodecConfig):
            sample_entries.append(self.codec_config.build_mp4a())

        stbl_box = SampleTableBuilder.build_stbl(
            sample_entries=sample_entries,
            samples=self.samples,
            chunk_offsets=chunk_offsets,
            chunk_sample_counts=chunk_sample_counts,
            is_video=self.is_video,
            force_64bit=force_64bit,
        )
        payload.extend(stbl_box)

        return BoxWriter.box(b"minf", bytes(payload))

    def build_mdia(
        self,
        chunk_offsets: List[int],
        chunk_sample_counts: List[int],
        force_64bit: bool = False,
    ) -> bytes:
        """
        Builds 'mdia' (Media) box containing mdhd, hdlr, and minf.
        """
        payload = bytearray()
        payload.extend(self.build_mdhd())
        payload.extend(self.build_hdlr())
        payload.extend(
            self.build_minf(chunk_offsets, chunk_sample_counts, force_64bit=force_64bit)
        )
        return BoxWriter.box(b"mdia", bytes(payload))

    def build_trak(
        self,
        chunk_offsets: List[int],
        chunk_sample_counts: List[int],
        movie_timescale: int = 1000,
        force_64bit: bool = False,
    ) -> bytes:
        """
        Builds the complete 'trak' box.
        """
        payload = bytearray()
        payload.extend(self.build_tkhd(movie_timescale))
        payload.extend(
            self.build_mdia(chunk_offsets, chunk_sample_counts, force_64bit=force_64bit)
        )
        return BoxWriter.box(b"trak", bytes(payload))
