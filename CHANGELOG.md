# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-10

### Added
- **Core Recovery Engine**: Fully bespoke H.264 (AVC) NALU recovery engine capable of reference-free extraction.
- **Dynamic Parameter Inference**: Automatically guesses video resolution and frames per second based on bitstream heuristics if `moov` is missing.
- **AVCC Support**: Native decoding of explicit `avcC` decoder configuration records when recovering partially truncated files.
- **Robust Validation**: Integrates FFmpeg natively for internal validation of recovered MP4 structural integrity.
- **Graphical User Interface (GUI)**: Clean, PyQt6-based desktop UI for non-technical users featuring drag-and-drop support.
- **Diagnostic Reports**: Privacy-preserving export feature for generating GitHub-ready technical reports on failed recoveries.
- **Standalone Build**: Zero-dependency `VideoRecoverer.exe` build utilizing PyInstaller and bundled FFmpeg.

### Changed
- Shifted architecture away from `untrunc` dependency to an in-house bitstream analysis pipeline.
- Audio recovery has been disabled/dropped to ensure consistent video-framerate playback across VFR Android sources.

### Fixed
- Addressed a crash where container atoms (like `moof` or `mdat`) in fragmented MP4s were misidentified as NAL length prefixes.
- Eliminated all rigid slice-header `0x88/0x9A` constraints, significantly broadening encoder compatibility.
