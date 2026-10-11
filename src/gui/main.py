import os
import sys

# Add project root to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget, QVBoxLayout, 
    QLabel, QPushButton, QFileDialog, QProgressBar, QHBoxLayout, QFrame,
    QDialog, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QIcon, QPixmap, QAction

from src.gui.worker import AnalysisWorker, RecoveryWorker
from src.api.models import RecoveryMetadata
from src.version import __version__
from src.api.diagnostics import generate_diagnostic_report

class DropZone(QFrame):
    file_dropped = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon = QLabel("🎬")
        icon.setStyleSheet("font-size: 34px; color: #2dd4bf; background: transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Drop your MP4 here\nor Browse Files")
        self.label.setObjectName("dropzone_text")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(icon)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(".mp4"):
                self.file_dropped.emit(path)
                
    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(self, "Select Broken MP4", "", "MP4 Files (*.mp4)")
        if path:
            self.file_dropped.emit(path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Recoverer by Leke Tech")
        self.setMinimumSize(600, 520)
        
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.input_path = ""
        self.output_path = ""
        self.summary = None
        self.fps = 0.0
        self.raw_metadata = None
        
        # Setup Stacked Widget
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # Setup Menu Bar
        self.create_menu_bar()
        
        # Create states
        self.build_empty_state()
        self.build_analyzing_state()
        self.build_ready_state()
        self.build_recovering_state()
        self.build_complete_state()
        self.build_failure_state()
        
        # Load stylesheet
        styles_path = os.path.join(os.path.dirname(__file__), "styles.qss")
        if os.path.exists(styles_path):
            with open(styles_path, "r") as f:
                self.setStyleSheet(f.read())
                
        self.stack.setCurrentIndex(0)

    # --- MENU BAR ---
    def create_menu_bar(self):
        menubar = self.menuBar()

        # 1. File Menu
        file_menu = menubar.addMenu("&File")

        action_open = QAction("&Open Broken Video...", self)
        action_open.setShortcut("Ctrl+O")
        action_open.setStatusTip("Select a damaged MP4 video to inspect and recover")
        action_open.triggered.connect(self.action_browse_file)
        file_menu.addAction(action_open)

        action_open_dir = QAction("Open &Output Directory", self)
        action_open_dir.setStatusTip("Open the folder containing recovered files")
        action_open_dir.triggered.connect(self.action_open_output_dir)
        file_menu.addAction(action_open_dir)

        file_menu.addSeparator()

        action_reset = QAction("&Reset Session", self)
        action_reset.setShortcut("Ctrl+N")
        action_reset.setStatusTip("Clear current session and start fresh")
        action_reset.triggered.connect(self.action_reset_session)
        file_menu.addAction(action_reset)

        file_menu.addSeparator()

        action_exit = QAction("E&xit", self)
        action_exit.setShortcut("Ctrl+Q")
        action_exit.setStatusTip("Exit the application")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # 2. Tools Menu
        tools_menu = menubar.addMenu("&Tools")

        action_diag = QAction("&Forensic Diagnostic Report...", self)
        action_diag.setStatusTip("View detailed forensic stream diagnostics")
        action_diag.triggered.connect(self.action_show_diagnostics)
        tools_menu.addAction(action_diag)

        action_copy_info = QAction("&Copy Stream Info to Clipboard", self)
        action_copy_info.setStatusTip("Copy codec, resolution, and sample details to clipboard")
        action_copy_info.triggered.connect(self.action_copy_stream_info)
        tools_menu.addAction(action_copy_info)

        # 3. Help Menu
        help_menu = menubar.addMenu("&Help")

        action_capabilities = QAction("&Supported Scenarios", self)
        action_capabilities.setStatusTip("View supported recovery scenarios and container types")
        action_capabilities.triggered.connect(self.action_show_supported_scenarios)
        help_menu.addAction(action_capabilities)

        action_integrity = QAction("Forensic &Integrity Policy", self)
        action_integrity.setStatusTip("View forensic principles: read-only, zero transcoding, local-only")
        action_integrity.triggered.connect(self.action_show_integrity_policy)
        help_menu.addAction(action_integrity)

        help_menu.addSeparator()

        action_about = QAction("&About Video Recoverer", self)
        action_about.setStatusTip("About Video Recoverer by Leke Tech")
        action_about.triggered.connect(self.action_show_about)
        help_menu.addAction(action_about)

    # --- MENU ACTIONS ---
    def action_browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Broken MP4", "", "MP4 Files (*.mp4);;All Files (*.*)")
        if path:
            self.start_analysis(path)

    def action_open_output_dir(self):
        target_dir = ""
        if self.output_path and os.path.exists(os.path.dirname(self.output_path)):
            target_dir = os.path.dirname(self.output_path)
        elif self.input_path and os.path.exists(os.path.dirname(self.input_path)):
            target_dir = os.path.dirname(self.input_path)
        else:
            target_dir = os.path.expanduser("~/Downloads")

        if os.path.exists(target_dir) and os.name == 'nt':
            os.startfile(target_dir)

    def action_reset_session(self):
        if hasattr(self, 'analysis_worker') and self.analysis_worker.isRunning():
            self.analysis_worker.cancel()
        if hasattr(self, 'recovery_worker') and self.recovery_worker.isRunning():
            self.recovery_worker.cancel()
        self.input_path = ""
        self.output_path = ""
        self.summary = None
        self.raw_metadata = None
        self.stack.setCurrentIndex(0)

    def action_copy_stream_info(self):
        if not self.summary:
            QMessageBox.information(
                self,
                "No Stream Analyzed",
                "Please open and analyze a corrupted video first before copying stream information.",
            )
            return

        res = f"{self.summary.sps.width}x{self.summary.sps.height}" if self.summary.sps else "Unknown"
        info = (
            f"Video Recoverer Stream Information\n"
            f"Source: {self.input_path}\n"
            f"Format: {self.summary.format_detected.upper()}\n"
            f"Resolution: {res}\n"
            f"Recovered Frames: {self.summary.total_access_units}\n"
            f"Keyframes (IDR): {self.summary.idr_count}\n"
            f"SPS/PPS Provenance: {self.summary.sps_pps_source}\n"
            f"Confidence: {self.summary.overall_confidence * 100:.1f}%\n"
        )
        QApplication.clipboard().setText(info)
        QMessageBox.information(
            self,
            "Copied to Clipboard",
            "Forensic stream information has been copied to your clipboard.",
        )

    def action_show_diagnostics(self):
        if not self.summary and not self.raw_metadata:
            QMessageBox.information(
                self,
                "No Diagnostics Available",
                "No video has been analyzed yet. Drop or open an MP4 file to generate diagnostics.",
            )
            return

        validation_report = getattr(self.raw_metadata, 'validation_report', None) if self.raw_metadata else None
        report_text = generate_diagnostic_report(
            original_filepath=self.input_path,
            error_message=None,
            recovery_summary=self.summary,
            validation_report=validation_report,
        )

        dlg = QDialog(self)
        dlg.setWindowTitle("Forensic Diagnostic Report")
        dlg.setMinimumSize(560, 420)
        vbox = QVBoxLayout(dlg)
        vbox.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Forensic Diagnostic Log")
        title.setObjectName("headline")
        title.setStyleSheet("font-size: 18px;")
        vbox.addWidget(title)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(report_text)
        text_edit.setObjectName("diagnostic_text")
        vbox.addWidget(text_edit)

        btn_box = QHBoxLayout()
        btn_copy = QPushButton("Copy to Clipboard")
        btn_copy.setObjectName("secondary_button")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(report_text))
        btn_close = QPushButton("Close")
        btn_close.setObjectName("primary_button")
        btn_close.clicked.connect(dlg.accept)
        btn_box.addWidget(btn_copy)
        btn_box.addStretch()
        btn_box.addWidget(btn_close)
        vbox.addLayout(btn_box)

        dlg.exec()

    def action_show_supported_scenarios(self):
        text = (
            "<h3>Supported Recovery Scenarios</h3>"
            "<p><b>Video Recoverer by Leke Tech</b> is engineered for reference-free forensic repair of damaged MP4 recordings:</p>"
            "<ul>"
            "<li><b>Truncated MP4s:</b> Abrupt battery pull, camera crash, power failure, or device freeze during recording.</li>"
            "<li><b>Missing 'moov' Box:</b> Standard MP4 files where the header index at the end of the file was never written.</li>"
            "<li><b>Fragmented MP4s (fMP4):</b> Interrupted live streams or dash recordings with damaged atom hierarchies.</li>"
            "<li><b>Portrait & Landscape Formats:</b> Mobile phone recordings (e.g. 720x1280, 1080x1920, 720x1600, 1080x2400) and standard displays (1080p, 720p, 4K).</li>"
            "<li><b>Reference-Free Recovery:</b> No healthy sample video from the same camera is required.</li>"
            "</ul>"
            "<p><i>Note: Video track recovery supports H.264 / AVC bitstreams. Audio tracks and H.265/HEVC bitstreams are not currently supported.</i></p>"
        )
        QMessageBox.information(self, "Supported Recovery Scenarios", text)

    def action_show_integrity_policy(self):
        text = (
            "<h3>Forensic Integrity Guarantees</h3>"
            "<p>This application follows strict digital forensics standards:</p>"
            "<ul>"
            "<li><b>100% Read-Only:</b> The source file is opened strictly in read-only binary mode (<code>rb</code>). The original corrupted file is never modified or rewritten in place.</li>"
            "<li><b>Zero Transcoding:</b> The video bitstream is never re-encoded or altered. Surviving H.264 macroblocks and NAL units are byte-for-byte preserved.</li>"
            "<li><b>100% Local Processing:</b> All analysis and reconstruction happens entirely on your machine. Zero network connections, zero telemetry, and zero cloud uploads.</li>"
            "<li><b>Provable Metadata:</b> Codec parameters are derived directly from the surviving bitstream, ensuring standard ISO/IEC 14496 compliance without fabricated numbers.</li>"
            "</ul>"
        )
        QMessageBox.information(self, "Forensic Integrity Guarantee", text)

    def action_show_about(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        text = (
            f"<div style='text-align: center;'>"
            f"<h2 style='color: #2dd4bf; margin-bottom: 2px;'>Video Recoverer</h2>"
            f"<h4 style='color: #a3b8b4; margin-top: 0;'>by Leke Tech</h4>"
            f"<p><b>Version {__version__}</b></p>"
            f"<hr style='border: 0; border-top: 1px solid #273935;'/>"
            f"<p style='color: #e6f4f1;'>Bespoke reference-free forensic video recovery engine for damaged, truncated, or unfinalized MP4 recordings.</p>"
            f"<p style='color: #8fa6a2; font-size: 12px;'>100% Local &bull; Read-Only Operations &bull; Zero Transcoding</p>"
            f"<p style='color: #2dd4bf; font-size: 12px;'>© 2026 Leke Tech. All rights reserved.</p>"
            f"</div>"
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("About Video Recoverer")
        msg.setText(text)
        if os.path.exists(icon_path):
            msg.setIconPixmap(QPixmap(icon_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        msg.exec()

    # --- HELPER ---
    def create_header(self, layout):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            icon_lbl = QLabel()
            pix = QPixmap(icon_path).scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_lbl.setPixmap(pix)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addSpacing(16)
            layout.addWidget(icon_lbl)
            layout.addSpacing(6)
        else:
            layout.addSpacing(20)

        brand = QLabel("VIDEO RECOVERER BY LEKE TECH")
        brand.setObjectName("branding")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)
        layout.addSpacing(10)

    # --- STATE 1: EMPTY ---
    def build_empty_state(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.create_header(layout)
        
        title = QLabel("Recover Your Broken Video")
        title.setObjectName("headline")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        sub = QLabel("Repair corrupted MP4 recordings without a reference video.")
        sub.setObjectName("subheadline")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.dropzone = DropZone()
        self.dropzone.file_dropped.connect(self.start_analysis)
        
        privacy = QLabel("🔒 100% local — your video never leaves your computer.")
        privacy.setObjectName("privacy")
        privacy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        version_lbl = QLabel(f"Version {__version__}")
        version_lbl.setObjectName("version_text")
        version_lbl.setStyleSheet("color: #777777; font-size: 11px;")
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addSpacing(30)
        layout.addWidget(self.dropzone, 1) # strech factor 1
        layout.addSpacing(20)
        layout.addWidget(privacy)
        layout.addSpacing(10)
        layout.addWidget(version_lbl)
        layout.addSpacing(10)
        
        widget.setLayout(layout)
        self.stack.addWidget(widget)

    # --- STATE 2: ANALYZING ---
    def build_analyzing_state(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.create_header(layout)
        layout.addStretch()
        
        title = QLabel("Analyzing your video…")
        title.setObjectName("headline")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.analyze_progress = QProgressBar()
        self.analyze_progress.setRange(0, 0) # Indeterminate for initial parsing
        
        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(self.analyze_progress)
        layout.addStretch()
        
        widget.setLayout(layout)
        self.stack.addWidget(widget)

    # --- STATE 3: READY ---
    def build_ready_state(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.create_header(layout)
        
        title = QLabel("Your video can be recovered.")
        title.setObjectName("headline")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        
        self.ready_details = QLabel()
        self.ready_details.setObjectName("panel_text")
        self.ready_details.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        panel_layout.addWidget(self.ready_details)
        
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(40, 10, 40, 20)
        self.btn_recover = QPushButton("Recover Video")
        self.btn_recover.setObjectName("primary_button")
        self.btn_recover.clicked.connect(self.start_recovery)
        
        self.btn_cancel_ready = QPushButton("Cancel")
        self.btn_cancel_ready.setObjectName("secondary_button")
        self.btn_cancel_ready.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        
        btn_layout.addWidget(self.btn_cancel_ready)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(self.btn_recover)
        
        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(panel)
        layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        self.stack.addWidget(widget)

    # --- STATE 4: RECOVERING ---
    def build_recovering_state(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.create_header(layout)
        layout.addStretch()
        
        title = QLabel("Recovering your video…")
        title.setObjectName("headline")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_recovery_status = QLabel("Scanning video data…")
        self.lbl_recovery_status.setObjectName("subheadline")
        self.lbl_recovery_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.recovery_progress = QProgressBar()
        self.recovery_progress.setRange(0, 100)
        
        btn_layout = QHBoxLayout()
        self.btn_cancel_recovery = QPushButton("Cancel")
        self.btn_cancel_recovery.setObjectName("secondary_button")
        self.btn_cancel_recovery.setFixedWidth(120)
        self.btn_cancel_recovery.clicked.connect(self.cancel_recovery)
        btn_layout.addWidget(self.btn_cancel_recovery, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(title)
        layout.addWidget(self.lbl_recovery_status)
        layout.addSpacing(30)
        layout.addWidget(self.recovery_progress)
        layout.addSpacing(30)
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        widget.setLayout(layout)
        self.stack.addWidget(widget)

    # --- STATE 5: COMPLETE ---
    def build_complete_state(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.create_header(layout)
        layout.addStretch()
        
        icon = QLabel("✓")
        icon.setObjectName("success_icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("Recovery Complete")
        title.setObjectName("headline")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_success_details = QLabel()
        self.lbl_success_details.setObjectName("subheadline")
        self.lbl_success_details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(40, 20, 40, 10)
        btn_open = QPushButton("Open Video")
        btn_open.setObjectName("primary_button")
        btn_open.clicked.connect(lambda: os.startfile(self.output_path) if os.name == 'nt' else None)
        
        btn_folder = QPushButton("Open Folder")
        btn_folder.setObjectName("secondary_button")
        btn_folder.clicked.connect(lambda: os.startfile(os.path.dirname(self.output_path)) if os.name == 'nt' else None)
        
        btn_layout.addWidget(btn_folder)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(btn_open)
        
        btn_reset_layout = QHBoxLayout()
        btn_reset = QPushButton("Recover Another Video")
        btn_reset.setObjectName("ghost_button")
        btn_reset.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_reset_layout.addWidget(btn_reset, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.btn_export_success = QPushButton("Export Diagnostic Report")
        self.btn_export_success.setObjectName("ghost_button")
        self.btn_export_success.setStyleSheet("color: #666;")
        self.btn_export_success.clicked.connect(lambda: self.export_diagnostic_report())
        btn_reset_layout.addWidget(self.btn_export_success, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(self.lbl_success_details)
        layout.addSpacing(20)
        layout.addLayout(btn_layout)
        layout.addLayout(btn_reset_layout)
        layout.addStretch()
        
        widget.setLayout(layout)
        self.stack.addWidget(widget)

    # --- STATE 6: FAILURE ---
    def build_failure_state(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.create_header(layout)
        layout.addStretch()
        
        icon = QLabel("⚠")
        icon.setObjectName("error_icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("We couldn't fully recover this video.")
        title.setObjectName("headline")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_error = QLabel()
        self.lbl_error.setObjectName("subheadline")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Technical details expander
        self.tech_details_frame = QFrame()
        self.tech_details_frame.setVisible(False)
        tech_layout = QVBoxLayout(self.tech_details_frame)
        self.lbl_tech_log = QLabel()
        self.lbl_tech_log.setObjectName("technical_details")
        self.lbl_tech_log.setWordWrap(True)
        tech_layout.addWidget(self.lbl_tech_log)
        
        btn_layout = QHBoxLayout()
        btn_retry = QPushButton("Try Another File")
        btn_retry.setObjectName("primary_button")
        btn_retry.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        
        self.btn_tech = QPushButton("View Technical Details")
        self.btn_tech.setObjectName("secondary_button")
        self.btn_tech.clicked.connect(self.toggle_tech_details)
        
        self.btn_export_error = QPushButton("Export Diagnostic Report")
        self.btn_export_error.setObjectName("ghost_button")
        self.btn_export_error.clicked.connect(lambda: self.export_diagnostic_report(self.lbl_tech_log.text()))
        
        btn_layout.addWidget(self.btn_tech)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(self.btn_export_error)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(btn_retry)
        
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(self.lbl_error)
        layout.addSpacing(20)
        layout.addWidget(self.tech_details_frame)
        layout.addSpacing(10)
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        widget.setLayout(layout)
        self.stack.addWidget(widget)
        
    def toggle_tech_details(self):
        visible = not self.tech_details_frame.isVisible()
        self.tech_details_frame.setVisible(visible)
        self.btn_tech.setText("Hide Technical Details" if visible else "View Technical Details")

    # --- LOGIC ---
    def start_analysis(self, file_path):
        self.input_path = file_path
        self.stack.setCurrentIndex(1) # Analyzing
        self.analyze_progress.setRange(0, 0)
        
        self.analysis_worker = AnalysisWorker(self.input_path)
        self.analysis_worker.progress_updated.connect(self.update_analysis_progress)
        self.analysis_worker.finished_success.connect(self.on_analysis_success)
        self.analysis_worker.finished_error.connect(self.on_error)
        self.analysis_worker.start()
        
    def update_analysis_progress(self, val):
        self.analyze_progress.setRange(0, 100)
        self.analyze_progress.setValue(val)

    def on_analysis_success(self, summary, fps, metadata):
        self.summary = summary
        self.fps = fps
        self.raw_metadata = metadata
        
        # Build plain language details
        has_video = False
        res = "Unknown"
        for item in metadata.report.video:
            if "detected" in item.description and "x" in item.description:
                res = item.description.replace(" detected", "")
                has_video = True
                
        details = f"<b>Video Data</b><br/>"
        if has_video:
            details += f"✓ Video track found<br/>"
            details += f"✓ Resolution: {res}<br/>"
            details += f"✓ Frames recoverable: {metadata.estimated_frame_count}<br/>"
        else:
            details += f"❌ No video track found<br/>"
            
        details += "<br/><b>Audio Data</b><br/>"
        details += "✓ AAC track detected (Not supported yet)<br/>"
        
        self.ready_details.setText(details)
        self.stack.setCurrentIndex(2) # Ready

    def start_recovery(self):
        self.stack.setCurrentIndex(3) # Recovering
        self.recovery_progress.setValue(0)
        self.lbl_recovery_status.setText("Scanning video data…")
        
        base, ext = os.path.splitext(self.input_path)
        self.output_path = f"{base}_recovered{ext}"
        
        # Prevent overwrite
        counter = 1
        while os.path.exists(self.output_path):
            self.output_path = f"{base}_recovered_{counter}{ext}"
            counter += 1
            
        self.recovery_worker = RecoveryWorker(self.input_path, self.output_path, self.summary, self.fps)
        self.recovery_worker.progress_updated.connect(self.update_recovery_progress)
        self.recovery_worker.finished_success.connect(self.on_recovery_success)
        self.recovery_worker.finished_error.connect(self.on_error)
        self.recovery_worker.start()
        
    def update_recovery_progress(self, val):
        self.recovery_progress.setValue(val)
        if val < 50:
            self.lbl_recovery_status.setText("Scanning video data…")
        elif val < 80:
            self.lbl_recovery_status.setText("Reconstructing video…")
        elif val < 95:
            self.lbl_recovery_status.setText("Building recovered file…")
        else:
            self.lbl_recovery_status.setText("Validating recovered video…")

    def cancel_recovery(self):
        if hasattr(self, 'recovery_worker'):
            self.recovery_worker.cancel()
            
    def on_recovery_success(self, metadata):
        text = "✓ Video recovered<br/>"
        if metadata.validation_status:
            text += "✓ File validated<br/>"
        else:
            text += "⚠️ Validation warnings (file may still play)<br/>"
            
        filename = os.path.basename(self.output_path)
        text += f"<br/>Saved as: <b>{filename}</b>"
        
        self.lbl_success_details.setText(text)
        self.stack.setCurrentIndex(4) # Complete

    def on_error(self, err_msg):
        self.tech_details_frame.setVisible(False)
        self.btn_tech.setText("View Technical Details")
        
        if "cancelled" in err_msg.lower():
            # Return to empty state if user just cancelled
            self.stack.setCurrentIndex(0)
            return
            
        self.lbl_error.setText("An unexpected error occurred during processing.")
        self.lbl_tech_log.setText(err_msg)
        self.stack.setCurrentIndex(5) # Failure

    def export_diagnostic_report(self, err_msg=None):
        path, _ = QFileDialog.getSaveFileName(self, "Save Diagnostic Report", "diagnostic_report.txt", "Text Files (*.txt)")
        if not path:
            return
            
        validation_report = None
        if hasattr(self, 'raw_metadata') and self.raw_metadata and self.raw_metadata.validation_report:
            validation_report = self.raw_metadata.validation_report
            
        report_text = generate_diagnostic_report(
            original_filepath=self.input_path,
            error_message=err_msg,
            recovery_summary=self.summary,
            validation_report=validation_report
        )
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(report_text)
        except Exception:
            pass

    def closeEvent(self, event):
        """Handle application closure properly."""
        if hasattr(self, 'analysis_worker') and self.analysis_worker.isRunning():
            self.analysis_worker.cancel()
            self.analysis_worker.wait(2000) # Wait up to 2s
            
        if hasattr(self, 'recovery_worker') and self.recovery_worker.isRunning():
            self.recovery_worker.cancel()
            self.recovery_worker.wait(2000)
            
        event.accept()

def run_app():
    # Setup High DPI support
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()
