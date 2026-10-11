# Forensic Analysis Report

**Target File**: `samples/corrupted/original.mp4`
**File Size**: 108,142,592 bytes (Approx. 108 MB)

## 1. Top-Level Box Structure
The file contains standard ISO Base Media File Format (ISOBMFF) boxes.
*   **`ftyp`**: 
    *   **Offset**: `0x00000000`
    *   **Size**: 32 bytes (`0x20`)
    *   **Major Brand**: `isom`
    *   **Compatible Brands**: `isom`, `iso2`, `avc1`, `mp41`
*   **`free`**: 
    *   **Offset**: `0x00000020`
    *   **Size**: 8 bytes (`0x8`)
*   **`mdat`**: 
    *   **Offset**: `0x00000028`
    *   **Size Header**: `0x0EF426C8` (250,881,736 bytes)
    *   **Actual Payload Start**: `0x00000030`
    *   **Truncation Status**: **TRUNCATED**. The header claims the box extends for 250 MB, but the physical EOF is reached at 108 MB.

## 2. Missing Boxes
*   **`moov`**: Completely missing. It was never written to disk because the recording terminated unexpectedly.
*   **`moof`**: Absent. The file is a standard interleaved MP4, not a fragmented MP4.

## 3. Video Track Analysis
*   **Codec**: H.264 / AVC (indicated by `avc1` brand).
*   **Format**: AVCC Length-Prefixed. NAL units are preceded by 4-byte big-endian length prefixes.
*   **Start Codes**: No Annex B `00 00 00 01` start codes are present.
*   **NAL Unit Distribution**:
    *   **SPS (Type 7)**: 0 NALUs found.
    *   **PPS (Type 8)**: 0 NALUs found.
    *   **IDR (Type 5)**: 22 NALUs found (First IDR at offset `0x3F5D88`).
    *   **Non-IDR (Type 1)**: Approx. 460 NALUs found (First Non-IDR at offset `0x21C317`).
    *   **SEI/AUD**: Absent.
*   **Estimated Video Samples**: ~482 frames.
*   **Reconstruction Strategy**: Video access units can be reconstructed by dynamically scanning for 4-byte lengths pointing to valid NALU types (1, 5).

## 4. Audio Track Analysis
*   **Audio Presence**: Confirmed. The first bytes of the `mdat` payload at `0x30` (`de 02 00 4c 61 76 63 35 39...`) contain the string `Lavc59.37.100`. This is the signature of FFmpeg's native `aac` encoder, which writes its version tag into the first audio frame's ancillary data.
*   **Likely Codec**: AAC (Advanced Audio Coding).
*   **Format**: Raw AAC. No ADTS sync headers (`0xFFF`) are present.
*   **Audio Frame Boundaries**: **Cannot be reliably recovered directly**. Without ADTS headers or the `stsz` table, raw AAC frames appear as contiguous blocks of varying lengths. Boundaries must be guessed or aligned heuristically based on surrounding video NALUs.

## 5. End of File Analysis
*   The final media sample before physical EOF is violently truncated in the middle of a chunk. Any parser must catch `EOFError` gracefully.

## 6. Recovery Assessment

### Recoverable Information (Directly from file)
*   `stco` (Chunk offsets) for video frames.
*   `stsz` (Sample sizes) for video frames.
*   `stss` (Sync Sample indices) by logging IDR frames.
*   `stsc` (Sample-to-chunk) can be synthesized (1-to-1).

### Information that MUST be inferred
*   **SPS / PPS**: Because the encoder only wrote them to memory for the `moov` atom, they do not exist in the surviving bitstream. They MUST be brute-forced or inferred based on standard device profiles (e.g., 1080x2400 for Galaxy A41).
*   **Video Framerate**: No timing tables (`stts`, `ctts`) exist.
*   **Audio Configuration**: Sample rate and channel count must be inferred (e.g., 44.1kHz stereo).

### Impossible to Recover Exactly
*   **Perfect A/V Synchronization**: Interleave timing without `stts` will result in slight drift.
*   **Audio Integrity**: Some AAC frames will be lost or corrupted due to the inability to perfectly delineate raw AAC boundaries inside interleaved chunks.
