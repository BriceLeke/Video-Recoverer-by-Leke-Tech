import os
import shutil
import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

from src.api.engine import RecoveryTask
from src.api.models import RecoveryError, RecoveryCancelledError, RecoveryOptions
from src.h264.recovery_engine import H264RecoveryEngine

class TestRobustness(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.tmp_dir)
        
    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_missing_input_file(self):
        """Test 1: Missing file raises proper RecoveryError."""
        task = RecoveryTask(str(self.workspace / "nonexistent.mp4"), str(self.workspace / "out.mp4"))
        with self.assertRaisesRegex(RecoveryError, "Input file not found"):
            task.analyze()

    def test_empty_input_file(self):
        """Test 4: Empty file gracefully fails."""
        empty_file = self.workspace / "empty.mp4"
        empty_file.touch()
        
        task = RecoveryTask(str(empty_file), str(self.workspace / "out.mp4"))
        with self.assertRaisesRegex(RecoveryError, "Input file is completely empty"):
            task.analyze()

    def test_insufficient_permissions_on_input(self):
        """Test 12: Insufficient permissions to read."""
        no_perm_file = self.workspace / "noperm.mp4"
        no_perm_file.write_bytes(b"some data")
        
        with patch("os.access", return_value=False):
            task = RecoveryTask(str(no_perm_file), str(self.workspace / "out.mp4"))
            with self.assertRaisesRegex(RecoveryError, "Insufficient permissions to read"):
                task.analyze()

    def test_non_mp4_garbage_data(self):
        """Test 5: Non-MP4 file fails gracefully."""
        garbage = self.workspace / "garbage.mp4"
        garbage.write_bytes(b"\xFF" * 10240) 
        
        task = RecoveryTask(str(garbage), str(self.workspace / "out.mp4"))
        with self.assertRaisesRegex(RecoveryError, "No recoverable video frames found"):
            task.analyze()

    def test_insufficient_disk_space(self):
        """Test 11: Disk becoming full / Insufficient space before recovery."""
        valid_file = self.workspace / "valid.mp4"
        valid_file.write_bytes(b"\x00\x00\x00\x01\x27\x4d\x40\x33" + (b"A" * 1024))
        
        out_file = self.workspace / "out.mp4"
        task = RecoveryTask(str(valid_file), str(out_file), RecoveryOptions(validate=False))
        
        # Mock summary to avoid "No recoverable video frames" error
        class DummySummary:
            total_access_units = 1
        summary = DummySummary()
        fps = 30.0
        task.metadata.input_size = 1000
        
        with patch("shutil.disk_usage", return_value=(1000, 1000, 0)):
            with self.assertRaisesRegex(RecoveryError, "Insufficient disk space"):
                task.reconstruct(summary, fps)

    def test_user_cancellation(self):
        """Test 15: User cancellation during analysis raises correct error."""
        valid_file = self.workspace / "valid.mp4"
        valid_file.write_bytes(os.urandom(1024 * 1024))
        
        task = RecoveryTask(str(valid_file), str(self.workspace / "out.mp4"))
        
        def mock_run_recovery(*args, **kwargs):
            task.cancel()
            if kwargs.get('cancel_token')():
                raise RecoveryCancelledError("Cancelled")
                
        with patch.object(H264RecoveryEngine, "run_recovery", side_effect=mock_run_recovery):
            with self.assertRaises(RecoveryCancelledError):
                task.analyze()

    def test_recovery_failure_cleanup(self):
        """Test 16: Failure midway cleans up .tmp files."""
        valid_file = self.workspace / "valid.mp4"
        valid_file.write_bytes(b"\x00\x00\x00\x01\x27\x4d\x40\x33" + (b"A" * 1024))
        
        out_file = self.workspace / "out.mp4"
        tmp_out = self.workspace / "out.mp4.tmp"
        
        task = RecoveryTask(str(valid_file), str(out_file), RecoveryOptions(validate=False))
        
        class DummySummary:
            total_access_units = 1
        summary = DummySummary()
        fps = 30.0
        task.metadata.input_size = 1000
        
        with patch("src.reconstruction.mp4_muxer.MP4Muxer.reconstruct", side_effect=RuntimeError("Muxing crash")):
            with self.assertRaisesRegex(RecoveryError, "Recovery failed"):
                task.reconstruct(summary, fps)
                
        self.assertFalse(out_file.exists())
        self.assertFalse(tmp_out.exists())

if __name__ == "__main__":
    unittest.main()
