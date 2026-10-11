import os
import shutil
import threading
from typing import Callable, Optional
from .models import RecoveryState, RecoveryOptions, RecoveryMetadata, RecoveryError, RecoveryCancelledError, ReportItem
from ..h264.recovery_engine import H264RecoveryEngine
from ..reconstruction.mp4_muxer import MP4Muxer
from ..reconstruction.validator import MP4Validator

class RecoveryTask:
    """
    A unified, higher-level facade for executing an MP4 recovery.
    Manages state, cancellation, temp file cleanup, and progress reporting.
    """
    def __init__(self, input_path: str, output_path: str, options: Optional[RecoveryOptions] = None):
        self.input_path = input_path
        self.output_path = output_path
        self.options = options or RecoveryOptions()
        self._cancel_flag = threading.Event()
        self.metadata = RecoveryMetadata()
        self.state = RecoveryState.ANALYZING

    def cancel(self):
        """Signals the task to abort processing."""
        self._cancel_flag.set()

    def analyze(self, progress_callback: Optional[Callable[[RecoveryState, float, RecoveryMetadata], None]] = None):
        """
        Phase 1: Analyzes the file and builds the recovery summary without writing output.
        Returns (summary, target_fps).
        """
        try:
            self._update_state(RecoveryState.ANALYZING, 0.0, progress_callback)
            
            if not os.path.exists(self.input_path):
                raise RecoveryError(f"Input file not found: {self.input_path}")
            
            input_size = os.path.getsize(self.input_path)
            if input_size == 0:
                raise RecoveryError("Input file is completely empty (0 bytes).")
            self.metadata.input_size = input_size
            
            if not os.access(self.input_path, os.R_OK):
                raise RecoveryError("Insufficient permissions to read the input file.")
                
            engine = H264RecoveryEngine(source_path=self.input_path, chunk_size=self.options.chunk_size)
            def engine_progress(progress: float):
                if self._cancel_flag.is_set():
                    raise RecoveryCancelledError("Recovery cancelled by user")
                self._update_state(RecoveryState.ANALYZING, progress, progress_callback)
            
            summary = engine.run_recovery(
                progress_callback=engine_progress,
                cancel_token=self._cancel_flag.is_set
            )
            
            if self._cancel_flag.is_set():
                raise RecoveryCancelledError("Recovery cancelled by user")

            self.metadata.estimated_frame_count = summary.total_access_units
            
            # Populate Report and infer properties
            self.metadata.report.video.append(ReportItem("H.264 detected", "OK"))
            
            if summary.sps:
                self.metadata.resolution = f"{summary.sps.width}x{summary.sps.height}"
                self.metadata.detected_video_codec = "h264"
                if summary.sps_pps_source == "explicit_stream_nalus":
                    self.metadata.report.video.append(ReportItem("SPS recovered explicitly", "OK"))
                    self.metadata.report.video.append(ReportItem("PPS recovered explicitly", "OK"))
                else:
                    self.metadata.report.video.append(ReportItem("SPS inferred from bitstream", "WARN"))
                    self.metadata.report.video.append(ReportItem("PPS inferred from bitstream", "WARN"))
                self.metadata.report.video.append(ReportItem(f"{self.metadata.resolution} detected", "OK"))
            else:
                self.metadata.report.video.append(ReportItem("SPS/PPS recovery failed", "FAIL"))

            # Determine FPS
            target_fps = self.options.fps
            if target_fps is None:
                if summary.sps and summary.sps.timing_info_present_flag and summary.sps.num_units_in_tick and summary.sps.time_scale:
                    calc_fps = summary.sps.time_scale / (2.0 * summary.sps.num_units_in_tick)
                    target_fps = calc_fps
                    self.metadata.report.video.append(ReportItem(f"{calc_fps:.2f} FPS detected from VUI", "OK"))
                else:
                    target_fps = 30.0
                    self.metadata.report.video.append(ReportItem(f"{target_fps} FPS inferred (default)", "WARN"))
            else:
                self.metadata.report.video.append(ReportItem(f"{target_fps} FPS explicitly requested", "OK"))

            self.metadata.report.video.append(ReportItem(f"{summary.total_access_units} samples recovered", "OK"))

            # Note: Audio is currently not supported
            self.metadata.report.audio.append(ReportItem("Audio recovery not yet implemented", "FAIL"))
                
            if summary.total_access_units == 0:
                raise RecoveryError("No recoverable video frames found in the bitstream.")
            
            self._update_state(RecoveryState.ANALYZING, 1.0, progress_callback)
            return summary, target_fps
            
        except RecoveryCancelledError as e:
            self.state = RecoveryState.CANCELLED
            self._update_state(RecoveryState.CANCELLED, 0.0, progress_callback)
            raise e
        except Exception as e:
            self.state = RecoveryState.FAILED
            self._update_state(RecoveryState.FAILED, 0.0, progress_callback)
            raise RecoveryError(f"Analysis failed: {str(e)}") from e

    def reconstruct(self, summary, target_fps: float, progress_callback: Optional[Callable[[RecoveryState, float, RecoveryMetadata], None]] = None) -> RecoveryMetadata:
        """
        Phase 2: Reconstructs the MP4 file based on the analysis summary.
        """
        try:
            self._update_state(RecoveryState.RECOVERING, 0.0, progress_callback)
            
            if os.path.abspath(self.input_path) == os.path.abspath(self.output_path):
                raise RecoveryError("Output path cannot be the same as the input path. Overwriting is forbidden.")
            
            # Pre-flight check: Disk space and output path
            out_dir = os.path.dirname(os.path.abspath(self.output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
                if not os.access(out_dir, os.W_OK):
                    raise RecoveryError("Insufficient permissions to write to the output directory.")
                
                total, used, free = shutil.disk_usage(out_dir)
                # Ensure at least 110% of the input size is available, or 100MB minimum
                required_space = max(self.metadata.input_size * 1.1, 100 * 1024 * 1024)
                if free < required_space:
                    raise RecoveryError(f"Insufficient disk space. Needed: {required_space/1e6:.1f} MB, Available: {free/1e6:.1f} MB.")

            self._update_state(RecoveryState.RECOVERING, 0.5, progress_callback)

            # Reconstruct MP4
            bytes_written = MP4Muxer.reconstruct_from_recovery_summary(
                summary=summary,
                output_path=self.output_path,
                fps=target_fps,
                timescale=self.options.timescale,
                force_64bit=self.options.force_64bit
            )
            self.metadata.output_size = bytes_written
            
            self._update_state(RecoveryState.VALIDATING, 0.8, progress_callback)
            
            if self.options.validate:
                validator = MP4Validator()
                report = validator.validate(self.output_path)
                self.metadata.validation_status = report.is_valid
                self.metadata.validation_report = report
                self.metadata.duration = report.duration
                if not report.is_valid:
                    self.metadata.errors.extend(report.errors)
                    self.metadata.warnings.extend(report.warnings)
            
            self.state = RecoveryState.COMPLETE
            self._update_state(RecoveryState.COMPLETE, 1.0, progress_callback)
            return self.metadata
            
        except RecoveryCancelledError as e:
            self.state = RecoveryState.CANCELLED
            self._update_state(RecoveryState.CANCELLED, 0.0, progress_callback)
            self._cleanup()
            raise e
        except Exception as e:
            self.state = RecoveryState.FAILED
            self._update_state(RecoveryState.FAILED, 0.0, progress_callback)
            self._cleanup()
            raise RecoveryError(f"Recovery failed: {str(e)}") from e

    def run(self, progress_callback: Optional[Callable[[RecoveryState, float, RecoveryMetadata], None]] = None) -> RecoveryMetadata:
        summary, target_fps = self.analyze(progress_callback)
        return self.reconstruct(summary, target_fps, progress_callback)

    def _update_state(self, state: RecoveryState, progress: float, callback: Optional[Callable]):
        self.state = state
        if callback:
            try:
                callback(state, progress, self.metadata)
            except Exception:
                pass

    def _cleanup(self):
        """Removes partial output files if recovery fails or is cancelled."""
        for path in [self.output_path, f"{self.output_path}.tmp"]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

def recover(input_path: str, output_path: str, options: Optional[RecoveryOptions] = None, progress_callback: Optional[Callable] = None) -> RecoveryMetadata:
    """Convenience wrapper for RecoveryTask."""
    task = RecoveryTask(input_path, output_path, options)
    return task.run(progress_callback)
