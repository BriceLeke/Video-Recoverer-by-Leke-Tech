import os
import sys
import unittest
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.api.engine import recover
from src.api.models import RecoveryOptions, RecoveryState, RecoveryMetadata

class TestRecoveryAPI(unittest.TestCase):
    """
    Integration and regression test ensuring the new recovery API
    successfully wraps the pipeline and preserves existing behavior.
    """
    def test_api_recovers_playable_mp4(self):
        source_path = os.path.abspath("samples/corrupted/original.mp4")
        output_path = os.path.abspath("recovered/api_regression_recovered.mp4")
        
        if not os.path.exists(source_path):
            self.skipTest(f"Missing corrupted sample for regression test at {source_path}")
            
        print(f"\n[API Regression] Running recovery on {source_path}")
        
        options = RecoveryOptions(fps=None, validate=True)
        
        def on_progress(state: RecoveryState, progress: float, meta: RecoveryMetadata):
            # Print occasionally to avoid spam
            if int(progress * 100) % 25 == 0:
                print(f"[API Progress] {state.value}: {progress*100:.0f}%")

        metadata = recover(
            input_path=source_path,
            output_path=output_path,
            options=options,
            progress_callback=on_progress
        )
        
        # Verify metadata
        self.assertGreater(metadata.estimated_frame_count, 0)
        self.assertGreater(metadata.output_size, 0)
        self.assertTrue(metadata.validation_status, f"Validation failed: {metadata.errors}")
        
        print(f"\n[API Regression] SUCCESS: Recovered MP4 is valid and playable.")
        print(f"[API Regression] Metadata: {metadata.resolution}, {metadata.duration}s, {metadata.estimated_frame_count} frames")
        
        print("\n--- Recovery Report ---")
        for section, items in [("VIDEO", metadata.report.video), ("AUDIO", metadata.report.audio), ("CONTAINER", metadata.report.container)]:
            if items:
                print(f"{section}:")
                for item in items:
                    print(f"{item.status} {item.description}")
        print("-----------------------\n")

if __name__ == '__main__':
    unittest.main(verbosity=2)
