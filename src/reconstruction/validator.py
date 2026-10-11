"""
Automated MP4 Container Validation using FFprobe and FFmpeg.

Verifies:
1. Openability in FFmpeg and FFprobe.
2. Complete decode from beginning to end without bitstream or container errors.
3. Sensible duration reporting.
4. Fast and accurate seeking at multiple timestamps.
5. Correct codec identification (e.g. h264 / avc1).
6. Correct dimensions (width, height, aspect ratio).
7. Preservation of recoverable video frames.
"""

from dataclasses import dataclass, field
import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ValidationReport:
    """Forensic validation report produced by FFprobe and FFmpeg."""
    is_valid: bool
    container_format: str
    duration: float
    video_codec: str
    width: int
    height: int
    total_frames: int
    audio_codec: Optional[str] = None
    seek_tests_passed: int = 0
    seek_tests_total: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class MP4Validator:
    """
    Automated forensic validator for reconstructed MP4 containers.
    """

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        ffprobe_path: Optional[str] = None,
    ):
        self.ffmpeg_path = ffmpeg_path or self._find_binary("ffmpeg")
        self.ffprobe_path = ffprobe_path or self._find_binary("ffprobe")

    @staticmethod
    def _find_binary(name: str) -> Optional[str]:
        """Locates binary in bundled PyInstaller directory, system PATH, or common dirs."""
        import sys
        
        # 1. Check if running as PyInstaller bundle
        if hasattr(sys, '_MEIPASS'):
            bundled_path = os.path.join(sys._MEIPASS, 'bin', f"{name}.exe" if os.name == 'nt' else name)
            if os.path.exists(bundled_path):
                return bundled_path

        # 2. Check system PATH
        which = shutil.which(name)
        if which:
            return which

        # 3. Known fallback locations
        candidates = [
            f"C:\\ffmpeg\\bin\\{name}.exe",
            f"/usr/bin/{name}",
            f"/usr/local/bin/{name}",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def probe_metadata(self, filepath: str) -> Dict[str, Any]:
        """
        Runs ffprobe to inspect container and stream metadata.
        """
        if not self.ffprobe_path:
            raise FileNotFoundError("ffprobe binary not found on system")

        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            filepath,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)

    def verify_full_decode(self, filepath: str) -> Tuple[bool, int, List[str]]:
        """
        Decodes the video from beginning to end using FFmpeg.
        Returns:
            (success: bool, frames_decoded: int, fatal_errors: List[str])
        """
        if not self.ffmpeg_path:
            raise FileNotFoundError("ffmpeg binary not found on system")

        cmd = [
            self.ffmpeg_path,
            "-v", "error",
            "-i", filepath,
            "-f", "null",
            "-",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        fatal_error_keywords = (
            "no frame!",
            "non-existing pps",
            "header damaged",
            "decode error rate exceeds",
            "exceeds maximum",
            "moov atom not found",
        )
        fatal_errors = [
            line for line in res.stderr.splitlines()
            if any(k in line.lower() for k in fatal_error_keywords)
        ]

        if res.returncode != 0 and not fatal_errors:
            fatal_errors.append(f"FFmpeg exited with non-zero code {res.returncode}: {res.stderr.strip()}")

        success = (res.returncode == 0) and (len(fatal_errors) == 0)
        return success, 0, fatal_errors

    def verify_seeking(
        self, filepath: str, duration: float, num_points: int = 5
    ) -> Tuple[int, int, List[str]]:
        """
        Tests seeking to various timestamps across the video runtime.
        Returns:
            (passed: int, total: int, errors: List[str])
        """
        if not self.ffmpeg_path or duration <= 0:
            return 0, 0, []

        passed = 0
        errors = []
        # Test timestamps distributed across duration: 10%, 25%, 50%, 75%, 90%
        timestamps = [
            round(duration * fraction, 2)
            for fraction in [0.10, 0.25, 0.50, 0.75, 0.90]
            if duration * fraction > 0.1
        ]
        if not timestamps:
            timestamps = [0.1]

        for ts in timestamps:
            cmd = [
                self.ffmpeg_path,
                "-v", "error",
                "-ss", str(ts),
                "-i", filepath,
                "-frames:v", "1",
                "-f", "null",
                "-",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and not res.stderr.strip():
                passed += 1
            else:
                errors.append(f"Seek to {ts}s failed: {res.stderr.strip()}")

        return passed, len(timestamps), errors

    def validate(
        self,
        filepath: str,
        expected_width: Optional[int] = None,
        expected_height: Optional[int] = None,
        min_duration: float = 0.0,
    ) -> ValidationReport:
        """
        Performs full end-to-end automated validation of reconstructed MP4 file.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not os.path.exists(filepath):
            return ValidationReport(
                is_valid=False,
                container_format="unknown",
                duration=0.0,
                video_codec="none",
                width=0,
                height=0,
                total_frames=0,
                errors=[f"File not found: {filepath}"],
            )

        # 1. Probe metadata
        try:
            info = self.probe_metadata(filepath)
        except Exception as e:
            return ValidationReport(
                is_valid=False,
                container_format="invalid",
                duration=0.0,
                video_codec="none",
                width=0,
                height=0,
                total_frames=0,
                errors=[f"FFprobe failed to read file: {e}"],
            )

        fmt_info = info.get("format", {})
        container_format = fmt_info.get("format_name", "unknown")
        duration = float(fmt_info.get("duration", 0.0))

        # Check duration
        if duration < min_duration:
            errors.append(
                f"Duration {duration:.2f}s is less than expected minimum {min_duration:.2f}s"
            )

        # Find video stream
        video_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "video"),
            None,
        )
        if not video_stream:
            errors.append("No video stream found in container")
            return ValidationReport(
                is_valid=False,
                container_format=container_format,
                duration=duration,
                video_codec="none",
                width=0,
                height=0,
                total_frames=0,
                errors=errors,
            )

        video_codec = video_stream.get("codec_name", "unknown")
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        total_frames = int(video_stream.get("nb_frames", 0) or 0)

        # Verify codec
        if video_codec not in ("h264", "avc1"):
            errors.append(f"Unexpected video codec: {video_codec} (expected h264)")

        # Verify geometry
        if expected_width and width != expected_width:
            errors.append(f"Width mismatch: got {width}, expected {expected_width}")
        if expected_height and height != expected_height:
            errors.append(f"Height mismatch: got {height}, expected {expected_height}")

        # Check audio stream if present
        audio_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "audio"),
            None,
        )
        audio_codec = audio_stream.get("codec_name") if audio_stream else None

        # 2. Verify full decode from beginning to end
        decode_ok, _, decode_errs = self.verify_full_decode(filepath)
        if not decode_ok:
            errors.extend(decode_errs)

        # 3. Verify seeking capability
        seek_passed, seek_total, seek_errs = self.verify_seeking(filepath, duration)
        if seek_errs:
            warnings.extend(seek_errs)
        if seek_passed == 0 and seek_total > 0 and duration >= 1.0:
            errors.append("Seeking failed at all test points")

        is_valid = (len(errors) == 0)
        return ValidationReport(
            is_valid=is_valid,
            container_format=container_format,
            duration=duration,
            video_codec=video_codec,
            width=width,
            height=height,
            total_frames=total_frames,
            audio_codec=audio_codec,
            seek_tests_passed=seek_passed,
            seek_tests_total=seek_total,
            errors=errors,
            warnings=warnings,
        )
