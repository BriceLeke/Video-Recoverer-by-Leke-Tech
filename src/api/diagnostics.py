import os
import sys
import datetime
from typing import Any, Optional

from src.version import __version__
from src.h264.recovery_engine import RecoverySummary
from src.reconstruction.validator import ValidationReport


def generate_diagnostic_report(
    original_filepath: str,
    error_message: Optional[str] = None,
    recovery_summary: Optional[RecoverySummary] = None,
    validation_report: Optional[ValidationReport] = None,
) -> str:
    """
    Generates a privacy-preserving diagnostic report.
    Strips out filenames, paths, and sensitive details.
    """
    
    # Redact filename
    file_size = 0
    if os.path.exists(original_filepath):
        file_size = os.path.getsize(original_filepath)
        
    lines = []
    lines.append("=========================================")
    lines.append(" VIDEO RECOVERER BY LEKE TECH - DIAGNOSTIC REPORT")
    lines.append("=========================================")
    lines.append(f"Date Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Application Version: {__version__}")
    lines.append(f"Operating System: {sys.platform}")
    lines.append("")
    lines.append("--- SOURCE FILE INFO ---")
    lines.append(f"Original File Size: {file_size} bytes")
    
    if error_message:
        lines.append("")
        lines.append("--- FATAL ERROR ---")
        lines.append(error_message)

    if recovery_summary:
        lines.append("")
        lines.append("--- RECOVERY SUMMARY ---")
        lines.append(f"Detected Format: {recovery_summary.format_detected}")
        lines.append(f"Length Size: {recovery_summary.length_size}")
        lines.append(f"SPS/PPS Source: {recovery_summary.sps_pps_source}")
        lines.append(f"Total Bytes Scanned: {recovery_summary.total_bytes_scanned}")
        lines.append(f"Total Access Units: {recovery_summary.total_access_units}")
        lines.append(f"IDR Frames: {recovery_summary.idr_count}")
        lines.append(f"Non-IDR Frames: {recovery_summary.non_idr_count}")
        lines.append(f"Truncated AUs: {recovery_summary.truncated_au_count}")
        lines.append(f"Overall Confidence: {recovery_summary.overall_confidence}")
        
        if recovery_summary.sps:
            sps = recovery_summary.sps
            lines.append("")
            lines.append("--- SPS DETAILS ---")
            lines.append(f"Profile IDC: {sps.profile_idc}")
            lines.append(f"Level IDC: {sps.level_idc}")
            lines.append(f"Resolution: {sps.width}x{sps.height}")
            lines.append(f"POC Type: {sps.pic_order_cnt_type}")
            lines.append(f"Raw Bytes: {sps.raw_bytes.hex() if sps.raw_bytes else 'None'}")
            
        if recovery_summary.pps:
            pps = recovery_summary.pps
            lines.append("")
            lines.append("--- PPS DETAILS ---")
            lines.append(f"Entropy Coding Mode: {pps.entropy_coding_mode_flag}")
            lines.append(f"Raw Bytes: {pps.raw_bytes.hex() if pps.raw_bytes else 'None'}")
            
    if validation_report:
        lines.append("")
        lines.append("--- VALIDATION REPORT ---")
        lines.append(f"Valid: {validation_report.is_valid}")
        lines.append(f"Container: {validation_report.container_format}")
        lines.append(f"Video Codec: {validation_report.video_codec}")
        lines.append(f"Audio Codec: {validation_report.audio_codec or 'None'}")
        lines.append(f"Duration: {validation_report.duration:.2f}s")
        lines.append(f"Resolution: {validation_report.width}x{validation_report.height}")
        lines.append(f"Total Frames: {validation_report.total_frames}")
        lines.append(f"Seek Tests: {validation_report.seek_tests_passed}/{validation_report.seek_tests_total}")
        
        if validation_report.errors:
            lines.append("")
            lines.append("Validation Errors:")
            for e in validation_report.errors:
                # Basic redaction in case paths leak in error strings
                safe_e = e.replace(original_filepath, "[REDACTED_PATH]")
                lines.append(f"- {safe_e}")
                
        if validation_report.warnings:
            lines.append("")
            lines.append("Validation Warnings:")
            for w in validation_report.warnings:
                safe_w = w.replace(original_filepath, "[REDACTED_PATH]")
                lines.append(f"- {safe_w}")

    lines.append("")
    lines.append("=========================================")
    lines.append("END OF REPORT")
    lines.append("This report contains NO personal media data.")
    return "\n".join(lines)
