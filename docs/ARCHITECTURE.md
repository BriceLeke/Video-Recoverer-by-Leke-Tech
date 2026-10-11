# Forensic MP4 Recovery Engine: Architecture

## 1. Introduction
This document outlines the architecture for a reference-free, forensic MP4 recovery tool. The tool is designed to recover fragmented or incomplete MP4 files (specifically those missing the `moov` atom due to unexpected termination) without relying on a healthy reference file. The target use-case is Android screen recordings (e.g., "Screen Recorder Unlimited" on Samsung Galaxy A41), but the system is generalized to avoid hard-coded assumptions.

## 2. Core Architectural Principles
1.  **Forensic Integrity**: The corrupted input file is treated as read-only evidence. It must never be modified in-place.
2.  **Reference-Free Independence**: The system must extract all necessary playback and structural information (codec config, resolution, timing) strictly from the surviving bitstream.
3.  **Heuristic-Driven Analysis**: Rather than assuming standard Android parameters, the engine relies on bitstream heuristics (e.g., NAL unit parsing, ADTS headers, length prefixes) to dynamically reconstruct stream parameters.
4.  **Modular Pipeline**: The recovery process is decoupled into distinct phases: scanning, parsing, reconstruction, and muxing.

## 3. System Modules

### 3.1. Evidence Loader & IO Subsystem
Provides a secure, read-only interface to the corrupted file. Implements buffered seeking and reading to handle large files efficiently without loading the entire payload into memory.

### 3.2. ISOBMFF Box Scanner
Scans the top-level structure of the MP4 file.
*   **Target**: Identifies `ftyp`, `free`/`skip`, and the start of the `mdat` (Media Data) box.
*   **Validation**: Determines the exact bounds of surviving media data.

### 3.3. Stream Demuxer & Bitstream Parser
Operates within the boundaries of the `mdat` box. Since the `moov` atom is missing, there are no chunk offsets (`stco`) or sample sizes (`stsz`). The Demuxer must linearly or heuristically scan the raw interleaved byte stream to differentiate video and audio data.

#### 3.3.1. H.264 (AVC) Analyzer
Android `MediaMuxer` writes video frames into the `mdat` box.
*   **Format Detection**: Detects whether the video uses Annex B start codes (`00 00 00 01`) or AVC length-prefixes (e.g., 4-byte size followed by NALU). Android MP4s heavily favor 4-byte length-prefixed NALUs.
*   **NALU Parsing**: Extracts NAL Units and categorizes them:
    *   `Type 7`: Sequence Parameter Set (SPS) - Contains resolution, profile, and level.
    *   `Type 8`: Picture Parameter Set (PPS).
    *   `Type 5`: IDR Frame (Keyframe).
    *   `Type 1`: Non-IDR Frame.
*   **Codec Configuration**: Attempts to construct the `avcC` (AVC Decoder Configuration Record) strictly from SPS/PPS found in the stream.

#### 3.3.2. AAC Audio Analyzer
If audio is present, it must be disentangled from the video data.
*   **Header Parsing**: Searches for ADTS (Audio Data Transport Stream) sync words (`0xFFF`) or infers raw AAC frames based on predictable frame sizes and interval spacing.
*   **Parameter Extraction**: Determines sample rate and channel count from the audio headers to build the `mp4a` / `esds` configuration.

### 3.4. Timing & Synchronization Engine
Infers Presentation Time Stamps (PTS) and Decode Time Stamps (DTS).
*   **Video Timing**: Analyzes Frame Num gaps, Picture Order Count (POC), and optionally SEI (Supplemental Enhancement Information) timing messages.
*   **Audio Timing**: Uses the constant duration of AAC frames (typically 1024 samples per frame) to establish a baseline clock.
*   **Interleaving Heuristics**: Analyzes the physical layout of video and audio chunks in the `mdat` to estimate interleave ratios and maintain A/V sync.

### 3.5. Table Reconstructor
Synthesizes the missing MP4 Sample Table (`stbl`) boxes for each track:
*   `stco` / `co64`: Chunk offsets.
*   `stsz`: Sample sizes.
*   `stsc`: Sample-to-chunk mapping.
*   `stts`: Time-to-sample mapping (using inferred durations).
*   `stss`: Sync sample table (mapping IDR frames).

### 3.6. Moov Generator & Muxer
Constructs a valid ISO Base Media File Format `moov` atom in memory using the reconstructed tables and codec configurations, appending it to the recovered media data to produce a valid, playable MP4 file.

## 4. Anti-Assumptions (What NOT to Hard-code)
To ensure the tool works forensically and broadly, the following must **not** be hard-coded:
*   **Video Resolution & Framerate**: Must be parsed from SPS and timing analysis. Do not assume 1080p or 60fps.
*   **SPS/PPS Config**: Must not be copied from a generic Android device. If SPS/PPS are completely stripped from the `mdat` (a worst-case scenario), the system should flag this and require user intervention or deep brute-forcing, but it must not silently inject fake SPS/PPS.
*   **NAL Unit Size Length**: Do not assume it is 4 bytes. The parser must dynamically verify this.
*   **Audio Presence/Format**: Do not assume audio exists. The bitstream parser must prove its existence.
*   **Track IDs**: Dynamically assign Track 1 to Video and Track 2 to Audio based on discovery.

## 5. Android Screen Recording Specifics
*   **Muxing Pattern**: Android's `MediaMuxer` typically interleaves data in relatively small chunks (e.g., a few video frames followed by a block of audio frames).
*   **Metadata**: It often writes an `ftyp` box (e.g., `isom`, `mp42`), potentially a `free` box, and then opens the `mdat` box with a 32-bit or 64-bit size. If the recording crashes, the `mdat` size may be written as `0x00000000` (extending to EOF) or it might contain a garbage size.
*   **SPS/PPS Location**: Depending on the MediaCodec configuration (specifically `KEY_I_FRAME_INTERVAL`), SPS/PPS may be periodically inserted before IDR frames, or they may only exist once at the very beginning of the `mdat`, or in worst cases, they might have been held in memory for the `moov` atom and never flushed. The architecture must account for searching the *entire* surviving payload for them.
