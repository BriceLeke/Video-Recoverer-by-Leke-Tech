from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Any

class RecoveryState(Enum):
    ANALYZING = "ANALYZING"
    RECOVERING = "RECOVERING"
    VALIDATING = "VALIDATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

@dataclass
class RecoveryOptions:
    force_64bit: bool = False
    fps: Optional[float] = None
    timescale: int = 90000
    validate: bool = True
    chunk_size: int = 1024 * 1024

@dataclass
class ReportItem:
    description: str
    status: str  # "OK", "WARN", "FAIL"
@dataclass
class RecoveryReport:
    video: List[ReportItem] = field(default_factory=list)
    audio: List[ReportItem] = field(default_factory=list)
    container: List[ReportItem] = field(default_factory=list)

@dataclass
class RecoveryMetadata:
    input_size: int = 0
    detected_video_codec: Optional[str] = None
    resolution: Optional[str] = None
    estimated_frame_count: int = 0
    audio_detected: bool = False
    output_size: int = 0
    duration: float = 0.0
    validation_status: bool = False
    validation_report: Optional[Any] = None # Will hold the ValidationReport object
    report: RecoveryReport = field(default_factory=RecoveryReport)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

class RecoveryError(Exception):
    """Base exception for recovery errors."""
    pass

class RecoveryCancelledError(RecoveryError):
    """Raised when recovery is cancelled by the user."""
    pass
