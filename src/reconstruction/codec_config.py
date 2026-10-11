"""
Codec Configuration and Sample Entry Box Builders.

Implements ISO/IEC 14496-15 compliant AVCDecoderConfigurationRecord (avcC),
avc1 VisualSampleEntry, mp4a AudioSampleEntry, and esds MPEG-4 Audio descriptor.
"""

import struct
from dataclasses import dataclass, field
from typing import List, Optional

from .box_writer import BoxWriter


@dataclass
class H264CodecConfig:
    """
    H.264 / AVC Codec Configuration.
    Holds SPS and PPS parameter sets and geometric properties.
    """
    sps: bytes
    pps: bytes
    width: int
    height: int
    profile_idc: int = 100  # High Profile default
    level_idc: int = 31     # Level 3.1 default
    profile_compatibility: int = 0
    nal_length_size: int = 4  # 4-byte length prefix (AVCC)

    def build_avcC(self) -> bytes:
        """
        Constructs the 'avcC' (AVC Configuration) box according to ISO/IEC 14496-15.
        """
        # Ensure SPS/PPS do not have Annex-B start codes in avcC record
        sps_clean = self._strip_start_code(self.sps)
        pps_clean = self._strip_start_code(self.pps)

        payload = bytearray()
        # configurationVersion = 1
        payload.append(1)
        # AVCProfileIndication
        payload.append(self.profile_idc)
        # profile_compatibility
        payload.append(self.profile_compatibility)
        # AVCLevelIndication
        payload.append(self.level_idc)

        # 6 bits reserved ('111111' = 0xFC) | 2 bits lengthSizeMinusOne
        length_size_minus_one = (self.nal_length_size - 1) & 0x03
        payload.append(0xFC | length_size_minus_one)

        # 3 bits reserved ('111' = 0xE0) | 5 bits numOfSequenceParameterSets (1)
        payload.append(0xE0 | 1)

        # sequenceParameterSetLength (uint16) + SPS NAL unit bytes
        payload.extend(struct.pack(">H", len(sps_clean)))
        payload.extend(sps_clean)

        # numOfPictureParameterSets (uint8 = 1)
        payload.append(1)

        # pictureParameterSetLength (uint16) + PPS NAL unit bytes
        payload.extend(struct.pack(">H", len(pps_clean)))
        payload.extend(pps_clean)

        return BoxWriter.box(b"avcC", bytes(payload))

    def build_avc1(self) -> bytes:
        """
        Constructs the 'avc1' (VisualSampleEntry) box according to ISO/IEC 14496-12.
        Contains video geometry, color depth, and the child 'avcC' box.
        """
        payload = bytearray()
        # 6 bytes reserved = 0
        payload.extend(b"\x00" * 6)
        # data_reference_index = 1 (uint16)
        payload.extend(struct.pack(">H", 1))

        # pre_defined = 0, reserved = 0, pre_defined[3] = 0 (total 16 bytes)
        payload.extend(b"\x00" * 16)

        # width (uint16), height (uint16)
        payload.extend(struct.pack(">HH", self.width, self.height))

        # horizresolution = 72 dpi (0x00480000), vertresolution = 72 dpi (0x00480000)
        payload.extend(struct.pack(">II", 0x00480000, 0x00480000))

        # reserved = 0 (uint32)
        payload.extend(struct.pack(">I", 0))

        # frame_count = 1 (uint16: 1 frame per sample)
        payload.extend(struct.pack(">H", 1))

        # compressorname: 32 bytes (1 byte length prefix + padded string)
        # "\x0aAVC Coding" padded to 32 bytes total
        comp_name = b"\x0aAVC Coding" + (b"\x00" * (32 - 11))
        payload.extend(comp_name)

        # depth = 0x0018 (24 bpp color with no alpha), pre_defined = -1 (0xFFFF)
        payload.extend(struct.pack(">Hh", 0x0018, -1))

        # Child box: avcC
        payload.extend(self.build_avcC())

        return BoxWriter.box(b"avc1", bytes(payload))

    @staticmethod
    def _strip_start_code(data: bytes) -> bytes:
        """Strips Annex-B start code if present."""
        if data.startswith(b"\x00\x00\x00\x01"):
            return data[4:]
        if data.startswith(b"\x00\x00\x01"):
            return data[3:]
        return data


@dataclass
class AACCodecConfig:
    """
    AAC Audio Codec Configuration.
    Constructs 'esds' and 'mp4a' AudioSampleEntry boxes.
    """
    sample_rate: int = 44100
    channels: int = 2
    audio_specific_config: bytes = field(default_factory=bytes)

    def __post_init__(self):
        if not self.audio_specific_config:
            self.audio_specific_config = self._synthesize_audio_specific_config(
                self.sample_rate, self.channels
            )

    @staticmethod
    def _synthesize_audio_specific_config(sample_rate: int, channels: int) -> bytes:
        """
        Synthesizes a 2-byte AudioSpecificConfig for AAC-LC:
        5 bits: audioObjectType (2 = AAC-LC)
        4 bits: samplingFrequencyIndex
        4 bits: channelConfiguration
        3 bits: frameLengthFlag (0) + dependsOnCoreCoder (0) + extensionFlag (0)
        """
        freq_map = {
            96000: 0, 88200: 1, 64000: 2, 48000: 3, 44100: 4,
            32000: 5, 24000: 6, 22050: 7, 16000: 8, 12000: 9,
            11025: 10, 8000: 11, 7350: 12
        }
        freq_idx = freq_map.get(sample_rate, 4)  # Default 44100 Hz

        # 5 bits: object_type=2
        # 4 bits: freq_idx
        # 4 bits: channels
        # 3 bits: 0
        b0 = (2 << 3) | ((freq_idx >> 1) & 0x07)
        b1 = ((freq_idx & 0x01) << 7) | ((channels & 0x0F) << 3)
        return bytes([b0, b1])

    def build_esds(self) -> bytes:
        """
        Constructs the 'esds' (Elementary Stream Descriptor) box.
        ISO/IEC 14496-14 Section 5.6.
        """
        # DecoderSpecificInfo (tag 0x05)
        dsi_payload = bytearray([0x05, len(self.audio_specific_config)])
        dsi_payload.extend(self.audio_specific_config)

        # DecoderConfigDescriptor (tag 0x04)
        # objectTypeIndication = 0x40 (Audio ISO/IEC 14496-3)
        # streamType = 5 (AudioStream) << 2 | upStream=0 | reserved=1 -> 0x15
        # bufferSizeDB = 3 bytes (e.g. 0x000000 or 1536)
        # maxBitrate = 4 bytes (128000)
        # avgBitrate = 4 bytes (128000)
        dcd_body = bytearray([
            0x40,        # Audio ISO/IEC 14496-3
            0x15,        # Audio stream
            0x00, 0x06, 0x00, # 1536 byte buffer size
            0x00, 0x01, 0xF4, 0x00, # maxBitrate 128000
            0x00, 0x01, 0xF4, 0x00, # avgBitrate 128000
        ])
        dcd_body.extend(dsi_payload)
        dcd = bytearray([0x04, len(dcd_body)])
        dcd.extend(dcd_body)

        # SLConfigDescriptor (tag 0x06) - predefined = 2
        sl = bytes([0x06, 0x01, 0x02])

        # ES_Descriptor (tag 0x03)
        # ES_ID = 2 bytes (1)
        # streamDependenceFlag=0, URL_Flag=0, OCRstreamFlag=0, streamPriority=0 -> 0x00
        es_body = bytearray([0x00, 0x01, 0x00])
        es_body.extend(dcd)
        es_body.extend(sl)

        es_desc = bytearray([0x03, len(es_body)])
        es_desc.extend(es_body)

        # esds FullBox (version 0, flags 0)
        return BoxWriter.full_box(b"esds", 0, 0, bytes(es_desc))

    def build_mp4a(self) -> bytes:
        """
        Constructs the 'mp4a' (AudioSampleEntry) box.
        ISO/IEC 14496-12 Section 8.5.2.
        """
        payload = bytearray()
        # 6 bytes reserved = 0
        payload.extend(b"\x00" * 6)
        # data_reference_index = 1
        payload.extend(struct.pack(">H", 1))

        # reserved[2] = 0 (uint32[2] = 8 bytes)
        payload.extend(b"\x00" * 8)

        # channelcount = 2 (uint16)
        payload.extend(struct.pack(">H", self.channels))

        # samplesize = 16 (uint16)
        payload.extend(struct.pack(">H", 16))

        # pre_defined = 0, reserved = 0 (4 bytes)
        payload.extend(b"\x00" * 4)

        # samplerate = uint32 16.16 fixed-point (e.g. 44100 << 16)
        payload.extend(struct.pack(">I", self.sample_rate << 16))

        # Child box: esds
        payload.extend(self.build_esds())

        return BoxWriter.box(b"mp4a", bytes(payload))
