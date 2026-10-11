# MP4 Recovery Algorithm

This document details the step-by-step algorithmic pipeline for recovering the corrupted MP4 file without a reference video.

## Phase 1: Box Structure Analysis
1.  **File Read**: Open the corrupted MP4 file in read-only mode.
2.  **Top-Level Scan**: Iterate through ISOBMFF boxes from byte 0.
    *   Read 4 bytes (Size) and 4 bytes (Type).
    *   If Type == `ftyp`, parse major brand and compatible brands.
    *   If Type == `free` or `skip`, jump over the size.
    *   If Type == `mdat`, mark the absolute offset as `MDAT_START`.
    *   If `mdat` size is 0 (extends to EOF) or suspiciously small/large relative to file size, override `mdat` size to `FILE_SIZE - MDAT_START`.
3.  **Identify Media Bounds**: The surviving media data exists strictly between `MDAT_START` (plus header offset) and `EOF`.

## Phase 2: Codec & Stream Discovery (Heuristic Scan)
1.  **Read Window**: Load the first few megabytes of the `mdat` payload.
2.  **Video Detection (H.264/AVC)**:
    *   Scan for Annex B start codes (`00 00 00 01` or `00 00 01`).
    *   Scan for AVC length-prefixed NALUs (assume 4-byte prefix, read size, jump to next, check if next byte is a valid NALU type).
    *   *Decision*: Lock the parser into either Annex B mode or Length-Prefixed mode based on which pattern consistently validates over multiple consecutive frames.
3.  **Audio Detection (AAC)**:
    *   Scan for ADTS Syncwords (`0xFFF` with AAC MPEG-4 audio profile bits).
    *   If found, parse the ADTS header to extract Sample Rate and Channel Config.

## Phase 3: Bitstream Parsing & Extraction
Initialize empty data structures for Sample Tables: `Video_Chunks`, `Audio_Chunks`.

1.  **Linear Sweep**: Iterate through the `mdat` data linearly from start to finish.
2.  **Audio/Video Disambiguation**:
    *   Since chunks are interleaved, the parser must differentiate a video NALU length-prefix from an audio frame header.
    *   Validate the length prefix: Does it point to a valid NALU type (1, 5, 6, 7, 8)? Does the following length prefix also point to a valid NALU?
    *   If not a valid video NALU, test for audio (ADTS header or raw AAC frame based on expected block sizes).
3.  **NAL Unit Extraction & Access Unit Reconstruction**:
    *   For video, group consecutive NALUs into **Access Units (AUs)** (a single video frame). An AU typically starts with an SPS/PPS/SEI or directly with a VCL NALU (Type 1 or 5).
    *   Record the absolute file offset and size of the Access Unit. This becomes an entry for `stco` and `stsz`.
4.  **Keyframe Detection**:
    *   If the AU contains an IDR NALU (Type 5), flag this sample index in the `stss` (Sync Sample) table list.
5.  **Codec Configuration Recovery**:
    *   If an SPS (Type 7) and PPS (Type 8) are encountered, extract them.
    *   Parse the SPS using Exp-Golomb decoding to extract `pic_width_in_mbs_minus1` and `pic_height_in_map_units_minus1` to calculate actual video resolution.
    *   Save the SPS and PPS for synthesizing the `avcC` box later.

## Phase 4: Timing Inference
Because the `stts` and `ctts` tables are missing, timestamps must be reconstructed.
1.  **Audio Clock**: If AAC is present, it provides a stable clock. Each AAC-LC frame contains 1024 samples. Duration = `1024 / SampleRate`.
2.  **Video Clock**:
    *   Analyze the Picture Order Count (POC) in the slice headers of the H.264 NALUs to determine correct display order (handling B-frames if present).
    *   Estimate framerate by correlating the number of video Access Units interleaved between chunks of audio frames. (e.g., if 30 video frames occur in the same physical byte span as 1 second of audio data, framerate is ~30fps).
    *   Fallback: If no audio exists, prompt for a default framerate (e.g., 30fps) or attempt to parse standard Android screen recording framerates, noting it in the forensic log.
3.  **Table Generation**: Generate the `stts` (Time-to-Sample) entries based on the inferred durations.

## Phase 5: Reconstructing Sample Tables
For each track (Video, Audio):
1.  `stco` (Chunk Offset): Map the file offsets of grouped frames.
2.  `stsz` (Sample Size): Map the exact byte length of every AU / Audio Frame.
3.  `stsc` (Sample-to-Chunk): Define how samples are grouped into chunks (if we treat each AU as a chunk, samples-per-chunk = 1).
4.  `stss` (Sync Sample): List the sample numbers of all IDR frames (Video only).

## Phase 6: Synthesizing the MOOV Atom
1.  Create an overarching `moov` box.
2.  Create `mvhd` (Movie Header) with the calculated total duration and a standard timescale (e.g., 1000 or 90000).
3.  **Video Track (`trak`)**:
    *   Create `tkhd`, `mdia`, `mdhd`, `hdlr` (vide).
    *   Create `minf`, `stbl`.
    *   Create `stsd` -> `avc1` using the resolution parsed from the SPS.
    *   Create `avcC` containing the recovered SPS and PPS.
    *   Append reconstructed tables: `stts`, `stss`, `stsc`, `stsz`, `stco`.
4.  **Audio Track (`trak`)** (if recovered):
    *   Create `tkhd`, `mdia`, `mdhd`, `hdlr` (soun).
    *   Create `stsd` -> `mp4a` -> `esds` using the inferred AAC configuration.
    *   Append reconstructed tables: `stts`, `stsc`, `stsz`, `stco`.

## Phase 7: Final Muxing
1.  Output a new file: `recovered_output.mp4`.
2.  Write standard `ftyp` (e.g., `isom`).
3.  Write the newly synthesized `moov` atom.
4.  Write an `mdat` header.
5.  Copy the surviving media bytes exactly as they were parsed into the new `mdat` payload.
*(Alternatively, leave the `moov` at the end of the file as `ftyp` -> `mdat` -> `moov` to prevent rewriting the massive `mdat` block).*
