# Product Specification: Video Recovery Desktop App

- **Organization:** [Leke Tech](https://leke-tech.com)
- **Product Landing Page:** [leke-tech.com/video-recoverer](https://leke-tech.com/video-recoverer)

## 1. Product Vision
To provide a dead-simple, reliable, and privacy-respecting tool for recovering corrupted MP4 videos (such as interrupted screen recordings or camera crashes) without requiring a "healthy reference file" from the same device. 

**Primary Value Proposition:** "Recover corrupted MP4 videos without a reference file."
**Secondary Message:** "Your video stays on your computer."

## 2. Target Audience
Non-technical users who have lost an important recording and simply want it fixed. They do not understand video codecs, bitstreams, or command-line interfaces. They expect a "magic button" experience.

## 3. Core Principles
*   **Privacy-First:** The application must operate entirely offline. No telemetrics, no cloud processing, no uploads.
*   **Simplicity:** Zero configuration required. The tool automatically infers all necessary parameters.
*   **Non-Destructive:** The original corrupted file is never modified or overwritten.
*   **Robustness:** Capable of processing multi-gigabyte files without exhausting system RAM.

## 4. User Flow
1.  **Launch:** User opens the application.
2.  **Input:** User selects or drag-and-drops a broken `.mp4` file.
3.  **Analysis:** The app quickly parses the file, determining what can be saved (resolution, duration, frame count).
4.  **Confirmation:** The user is presented with the inferred video properties and a "Recover Video" button.
5.  **Processing:** A progress bar is displayed with an option to cancel. The engine streams the bitstream into a new file.
6.  **Validation:** The app silently verifies the reconstructed file using FFprobe/FFmpeg.
7.  **Success/Failure:** 
    *   *Success:* User can immediately open the recovered video in their media player or open the containing folder.
    *   *Failure:* User is given a human-readable error (with the option to view a technical log).

## 5. Non-Goals (Out of Scope for Initial GUI)
*   Batch processing of multiple videos at once.
*   Advanced manual codec configuration (forcing specific SPS/PPS profiles).
*   Video editing/trimming capabilities.
*   Audio recovery (explicitly marked as unsupported/dropped for now).
