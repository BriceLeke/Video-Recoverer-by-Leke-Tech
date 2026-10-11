"""
Movie (moov) and Movie Header (mvhd) Box Builder.

Implements ISO/IEC 14496-12 compliant moov generation:
moov -> mvhd, trak (video), trak (audio).
"""

import struct
from typing import Dict, List

from .box_writer import BoxWriter
from .track import Track


class MoovBuilder:
    """
    Constructs the top-level 'moov' container and movie header 'mvhd'.
    """

    @staticmethod
    def build_mvhd(
        duration: int, timescale: int = 1000, next_track_id: int = 2
    ) -> bytes:
        """
        Builds the 'mvhd' (Movie Header) box.
        ISO/IEC 14496-12 Section 8.2.2.
        """
        payload = bytearray()
        # creation_time (0), modification_time (0)
        payload.extend(struct.pack(">II", 0, 0))
        # timescale (uint32)
        payload.extend(struct.pack(">I", timescale))
        # duration (uint32 in movie timescale units)
        payload.extend(struct.pack(">I", duration))
        # rate = 1.0 (0x00010000), volume = 1.0 (0x0100)
        payload.extend(struct.pack(">Ih", 0x00010000, 0x0100))
        # reserved = 0 (10 bytes: uint16 = 0, uint32[2] = 0)
        payload.extend(b"\x00" * 10)
        # matrix (36 bytes unity matrix)
        payload.extend(BoxWriter.unity_matrix())
        # pre_defined = 0 (uint32[6] = 24 bytes)
        payload.extend(b"\x00" * 24)
        # next_track_id (uint32)
        payload.extend(struct.pack(">I", next_track_id))

        return BoxWriter.full_box(b"mvhd", 0, 0, bytes(payload))

    @classmethod
    def build_moov(
        cls,
        tracks: List[Track],
        chunk_offsets_by_track: Dict[int, List[int]],
        chunk_samples_by_track: Dict[int, List[int]],
        movie_timescale: int = 1000,
        force_64bit: bool = False,
    ) -> bytes:
        """
        Assembles the complete 'moov' box containing 'mvhd' and all track boxes.
        """
        # Calculate total movie duration as maximum duration across all tracks
        movie_duration = 0
        max_track_id = 0
        for track in tracks:
            dur = track.get_duration_in_movie_timescale(movie_timescale)
            if dur > movie_duration:
                movie_duration = dur
            if track.track_id > max_track_id:
                max_track_id = track.track_id

        payload = bytearray()
        # 1. Movie Header
        payload.extend(
            cls.build_mvhd(
                duration=movie_duration,
                timescale=movie_timescale,
                next_track_id=max_track_id + 1,
            )
        )

        # 2. Tracks
        for track in tracks:
            offsets = chunk_offsets_by_track.get(track.track_id, [])
            samples_per_chunk = chunk_samples_by_track.get(track.track_id, [])
            trak_box = track.build_trak(
                chunk_offsets=offsets,
                chunk_sample_counts=samples_per_chunk,
                movie_timescale=movie_timescale,
                force_64bit=force_64bit,
            )
            payload.extend(trak_box)

        return BoxWriter.box(b"moov", bytes(payload))
