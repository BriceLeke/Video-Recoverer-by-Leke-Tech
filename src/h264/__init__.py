"""
H.264 Forensic Recovery Subsystem.

A modular, reference-free recovery library for damaged and truncated H.264 bitstreams.
"""

from .bitstream import BitReader, BitWriter, unescape_rbsp, escape_rbsp
from .nalu import NALU, NALUType
from .sps import SPS, SPSParser, SPSSynthesizer
from .pps import PPS, PPSParser, PPSSynthesizer
from .slice import SliceHeader, SliceParser
from .access_unit import AccessUnit, AccessUnitBuilder
from .format_detector import FormatDetector, StreamFormat, FormatDetectionResult
from .parameter_recovery import ParameterRecovery
from .recovery_engine import H264RecoveryEngine, RecoverySummary

__all__ = [
    "BitReader",
    "BitWriter",
    "unescape_rbsp",
    "escape_rbsp",
    "NALU",
    "NALUType",
    "SPS",
    "SPSParser",
    "SPSSynthesizer",
    "PPS",
    "PPSParser",
    "PPSSynthesizer",
    "SliceHeader",
    "SliceParser",
    "AccessUnit",
    "AccessUnitBuilder",
    "FormatDetector",
    "StreamFormat",
    "FormatDetectionResult",
    "ParameterRecovery",
    "H264RecoveryEngine",
    "RecoverySummary",
]
