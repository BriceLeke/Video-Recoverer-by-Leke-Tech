# Rules and Guidelines for Forensic MP4 Recovery Engine

These rules apply to all AI agents and automated tools working within this project workspace.

## 1. Forensic Integrity First
*   **Read-Only Operations**: The original corrupted MP4 file must NEVER be modified, truncated, or rewritten in place. All operations on the source file must open it in read-only mode (`rb` in Python, etc.).
*   **No Transcoding**: The media data must not be transcoded, re-encoded, or altered. The original H.264 and AAC bitstreams must be perfectly preserved in the recovered file.
*   **Data Source**: Do not invent, guess, or hard-code critical metadata (resolution, SPS/PPS, sample rate). This information must be extracted or logically inferred from the corrupted bitstream itself.

## 2. Architectural Constraints
*   **No Reference Files**: Do not write code that requires a "healthy reference video" from the same device. The tool must operate in a strictly reference-free context.
*   **No `untrunc` Dependency**: Do not attempt to wrap, invoke, or utilize the open-source tool `untrunc`. We are building a bespoke recovery pipeline optimized for reference-free forensic recovery.
*   **No Magic Numbers**: Avoid hardcoding parameters like `1080x1920`, `30fps`, or `44100Hz` as defaults, unless functioning as an explicit, logged fallback when bitstream parsing definitively proves the data is unrecoverable.

## 3. Engineering Standards
*   **Modularity**: Code should be divided into distinct classes/modules (e.g., `BoxScanner`, `BitstreamParser`, `NaluAnalyzer`, `TableBuilder`). Do not write a single massive parser script.
*   **Error Handling**: Truncated files are inherently malformed. The code must handle sudden EOF (End of File), incomplete NAL units, and garbage bytes gracefully without crashing.
*   **Logging**: All heuristics and decisions (e.g., "Detected 4-byte NALU length prefix", "Inferred framerate as 29.97 based on audio interleave") must be heavily logged. In forensics, explaining *how* the data was recovered is as important as the recovery itself.

## 4. Workspace & Development Workflow
*   **Documentation Phase Only**: Do NOT begin implementation of the engine until the Architecture, Algorithm, and Test Plan documents have been explicitly approved by the Lead Engineer (User).
*   **Test-Driven**: Implementation should begin with the Box Scanner and Bitstream Parser, accompanied by unit tests simulating raw byte buffers of H.264/AAC data.
