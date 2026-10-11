import os
from PyQt6.QtCore import QThread, pyqtSignal
from src.api.engine import RecoveryTask
from src.api.models import RecoveryState, RecoveryOptions, RecoveryMetadata

class AnalysisWorker(QThread):
    progress_updated = pyqtSignal(int)
    finished_success = pyqtSignal(object, object, RecoveryMetadata) # (summary, fps, metadata)
    finished_error = pyqtSignal(str)

    def __init__(self, input_path: str):
        super().__init__()
        self.input_path = input_path
        self.task = RecoveryTask(input_path, output_path="")
        
    def run(self):
        try:
            def on_progress(state, progress_float, meta):
                self.progress_updated.emit(int(progress_float * 100))
                
            summary, fps = self.task.analyze(progress_callback=on_progress)
            self.finished_success.emit(summary, fps, self.task.metadata)
        except Exception as e:
            self.finished_error.emit(str(e))
            
    def cancel(self):
        self.task.cancel()


class RecoveryWorker(QThread):
    progress_updated = pyqtSignal(int)
    finished_success = pyqtSignal(RecoveryMetadata)
    finished_error = pyqtSignal(str)

    def __init__(self, input_path: str, output_path: str, summary: object, fps: float):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.summary = summary
        self.fps = fps
        self.task = RecoveryTask(input_path, output_path)
        
    def run(self):
        try:
            def on_progress(state, progress_float, meta):
                self.progress_updated.emit(int(progress_float * 100))
                
            metadata = self.task.reconstruct(self.summary, self.fps, progress_callback=on_progress)
            self.finished_success.emit(metadata)
        except Exception as e:
            self.finished_error.emit(str(e))
            
    def cancel(self):
        self.task.cancel()
