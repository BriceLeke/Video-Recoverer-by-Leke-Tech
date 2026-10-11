# Current Architecture: Forensic MP4 Recovery Engine

## Project Structure
The project is organized into modular components to process corrupted MP4 recordings and reconstruct them into valid ISOBMFF containers without modifying the original file.

*   **`src/h264/`**: Core video bitstream analysis and parsing logic.
    *   `recovery_engine.py`: The orchestrator for format detection, parameter recovery, and access unit reconstruction.
    *   `format_detector.py`: Detects Annex-B vs AVCC bitstreams.
    *   `parameter_recovery.py`: Infers SPS/PPS configurations directly from the corrupted bitstream.
    *   `access_unit.py`, `nalu.py`, `slice.py`, `sps.py`, `pps.py`: Parsers for fundamental H.264 structures.
*   **`src/reconstruction/`**: Modules for synthesizing a valid MP4 file from the recovered bitstream.
    *   `mp4_muxer.py`: Multiplexes the video stream into an MP4 container, writing boxes like `ftyp`, `mdat`, `moov`, and building sample tables.
    *   `moov_builder.py`: Synthesizes the critical `moov` atom required for playback.
    *   `validator.py`: Calls out to FFprobe/FFmpeg to validate the reconstructed MP4.
*   **`tests/integration/`**: Contains the main integration tests, notably `test_reconstruction_integration.py`, which is currently used to run the end-to-end recovery pipeline on the sample video.
*   **`samples/corrupted/`**: Stores the original, truncated MP4 file (`original.mp4`).
*   **`recovered/`**: Destination for reconstructed outputs (`recovered_video.mp4`, `recovered_video_64bit.mp4`, etc.).

## Recovery Pipeline
The recovery process strictly adheres to a read-only policy on the corrupted source file. The pipeline steps are:

1.  **Format Detection**: The `FormatDetector` analyzes the initial bytes of the bitstream to determine if it uses Annex-B start codes or AVCC length prefixes.
2.  **Parameter Recovery**: The `ParameterRecovery` module scans for explicit SPS/PPS headers. If missing (common in corrupted files), it infers them by identifying an IDR frame and synthetically generating a compliant SPS/PPS structure (testing candidates against `ffmpeg` decoder if necessary).
3.  **Bitstream Streaming (NALU Parsing)**: `H264RecoveryEngine` streams through the file in chunks (O(1) memory), identifying NAL Units and grouping them into `AccessUnit`s. It parses slice headers to recover `frame_num` and `poc` (Picture Order Count).
4.  **Container Multiplexing**: `MP4Muxer.reconstruct_from_recovery_summary` creates a new MP4. It writes the `ftyp` and streams data into `mdat` (healing truncated frames at EOF). It then builds the missing `moov` atom (including `stbl` sample tables) and writes it to the end of the file.
5.  **Validation**: Finally, `MP4Validator` verifies the output using FFmpeg/FFprobe to ensure dimensions, duration, decodability, and seek-ability are correct.

## Dependencies
*   **Python Standard Library**: The core engine avoids third-party dependencies (no `untrunc`, `ffmpeg-python`, etc.).
*   **External Binaries**: 
    *   **FFmpeg & FFprobe**: Required for validation (`validator.py`) and resolution inference (`parameter_recovery.py`). The paths will be inferred from the system `PATH` or common `/usr/bin/` directories.

## Input/Output Behavior
*   **Input**: Takes a corrupted MP4 (`samples/corrupted/original.mp4`). It opens this file strictly in `rb` (read-binary) mode.
*   **Output**: Generates a healthy MP4 (`recovered_video.mp4` and `recovered_video_64bit.mp4`) and/or a raw H.264 stream (`recovered_stream.h264`) in the `recovered/` directory.

## Known Limitations & Security/Reliability Risks
*   **Audio Recovery**: The current pipeline ignores audio tracks (skips interleaved audio chunks) and recovers a video-only MP4.
*   **Hardcoded FFmpeg Path**: `parameter_recovery.py` and `test_engine_run.py` have hardcoded paths to the user's specific FFmpeg installation. This will break on other machines.
*   **Missing Error Resilience on Validation**: The validator tests rely on FFmpeg subprocess calls which might timeout or crash on improperly formed commands or non-existent files.

## Assumptions (Specific to Samsung A41 / Current Test File)
*   **Dimensions**: `parameter_recovery.py` falls back to `720x1280` as the primary default resolution candidate if it can't find `ffmpeg` to verify the resolution.
*   **Framerate**: The integration test explicitly hardcodes `fps=30.0` and `timescale=90000` when invoking the MP4 muxer.
*   **Duration**: The integration test strictly asserts that the recovered video is at least 350 seconds long (specific to the corrupted sample).
*   **File Paths**: Paths like `samples/corrupted/original.mp4` and `recovered/recovered_video.mp4` are hardcoded in test scripts.

## Temporary/Debug Code
*   `analyze_forensics.py`: A simple script that performs a heuristic fast count of valid NALUs to estimate video samples.
*   `decode_idr.py`: A scratch script to manually test slice header parsing on a specific hardcoded offset (`0x4B`).
*   `test_engine_run.py`: A debug script that runs the recovery engine but only exports an Annex-B `.h264` stream instead of generating a full `.mp4`.

## Generated Artifacts (Do Not Commit)
*   `recovered/`: All files within this directory (`*.mp4`, `*.h264`, `*.png`).
*   `__pycache__/` and `.pytest_cache/` directories.
*   `samples/corrupted/original.mp4` (assuming it's a large, sensitive media file).
