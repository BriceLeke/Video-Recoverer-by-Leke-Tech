# Forensic Test Plan

## 1. Objective
Ensure the reference-free MP4 recovery engine can reliably process and recover truncated Android screen recordings without modifying the original evidence or injecting synthetic/unverified codec parameters.

## 2. Test Data Generation (Simulated Evidence)
Since actual forensic data is sensitive, we will generate controlled corrupted files mimicking the "Screen Recorder Unlimited" app behavior on a Samsung Galaxy A41.
1.  **Baseline Generation**: Record a 30-second screen capture containing video (H.264) and audio (AAC).
2.  **Corruption Simulation 1 (Standard Truncation)**: Intercept the file stream and terminate the process right before the `moov` atom is written. The `mdat` size will likely be incomplete or zeroed.
3.  **Corruption Simulation 2 (Missing SPS/PPS)**: Modify the bitstream to strip the first SPS/PPS to test the engine's ability to locate secondary SPS/PPS further down the stream (e.g., preceding the next keyframe).
4.  **Corruption Simulation 3 (Video Only)**: Generate a screen recording with audio disabled, truncate it, and ensure the engine does not fail when audio heuristics return null.

## 3. Validation Metrics
The recovered output files will be strictly validated against the following criteria.

### 3.1. Structure Validation
*   **Tool**: `ffprobe -v trace <recovered.mp4>`
*   **Criteria**: The output must contain a valid ISOBMFF structure (`ftyp`, `mdat`, `moov`). The `moov` atom must parse cleanly without offsets pointing outside the file bounds.

### 3.2. Forensic Purity Validation
*   **Criteria**: The raw bitstream data inside the recovered `mdat` must be a byte-for-byte exact match to the surviving `mdat` data in the corrupted input. No transcoding or byte-shifting of media data is allowed.

### 3.3. Decode & Playability Validation
*   **Tool**: `ffmpeg -v error -i <recovered.mp4> -f null -`
*   **Criteria**: The file must decode completely without throwing critical bitstream errors (`non-existing PPS`, `no frame!`, `header damaged`). Minor artifacting at the exact truncation boundary is acceptable.

### 3.4. Seeking & Keyframe Accuracy
*   **Automated Seeking Test**: Use FFmpeg to extract frames at 25%, 50%, and 75% of the total duration.
    *   Command: `ffmpeg -ss <timestamp> -i <recovered.mp4> -vframes 1 test_frame.jpg`
*   **Criteria**: The extracted frames must be clean and not exhibit "smearing" (which would indicate the `stss` sync sample table is incorrectly pointing to non-IDR frames).

### 3.5. A/V Synchronization
*   **Test**: Play the file or analyze the A/V offset.
*   **Criteria**: Audio and video must remain in sync throughout the playback. If exact timing cannot be inferred, the drift must be documented and predictable based on the AAC frame count vs. Video frame count.

## 4. Edge Cases to Monitor
*   **Length-Prefixed vs Annex B**: Ensure the parser accurately distinguishes between the two without crashing.
*   **B-Frames**: Though rare in real-time Android screen recordings, if present, ensure POC (Picture Order Count) parsing accurately generates `ctts` (Composition Time to Sample) tables or properly reorders presentation timestamps.
*   **Variable Frame Rate (VFR)**: Android screen recordings are notoriously VFR. The timing inference engine must handle uneven gaps between video access units based on audio interleaving.
