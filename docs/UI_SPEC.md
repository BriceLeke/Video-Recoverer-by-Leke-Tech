# UI Specification

## 1. Visual Language
*   **Style:** Modern, clean, flat design with rounded corners.
*   **Theme:** Dark mode preferred (reduces glare, feels "pro" yet simple).
*   **Jargon:** Absolutely no technical jargon (e.g., moov atoms, SPS/PPS, NAL units) on the main screens. Technical details are hidden behind a collapsible "Technical Details" accordion.

## 2. Screens & States

### 2.1. Home Screen (Dropzone)
*   **Headline:** "Recover corrupted MP4 videos without a reference file."
*   **Subheadline:** "Your video stays on your computer." (with a small local/lock icon).
*   **Main Element:** A large, dashed-border drag-and-drop zone.
*   **Action:** "Drag & Drop broken video here" or a "Browse Files" button.

### 2.2. Analysis Screen (Pre-Recovery)
*   **Headline:** "Video Analyzed"
*   **Details List (Human Readable):**
    *   Resolution: 1920x1080
    *   Estimated Duration: ~5 mins
    *   Recoverable Frames: 10,500
    *   Audio: Dropped (Not supported)
*   **Action (Primary):** "Recover Video" button.
*   **Action (Secondary):** "Cancel" or "Select different file".
*   **Technical Details (Optional Expander):** A small chevron to show the generated `RecoveryReport` (e.g., "SPS inferred", "H.264 detected").

### 2.3. Recovery in Progress
*   **Visual:** A determinate progress bar (0-100%).
*   **Text:** "Rebuilding video timeline... 45%"
*   **Action:** "Cancel" button.

### 2.4. Success Screen
*   **Visual:** Large green Checkmark icon.
*   **Headline:** "Recovery Complete!"
*   **Text:** "Your video has been successfully rebuilt and validated."
*   **Action (Primary):** "Open Video" (Launches default OS media player).
*   **Action (Secondary):** "Show in Folder" (Opens Windows Explorer).
*   **Action (Tertiary):** "Recover Another File" (Returns to Home Screen).

### 2.5. Error Screen
*   **Visual:** Red Warning icon.
*   **Headline:** "Recovery Failed"
*   **Text:** Human-readable reason (e.g., "No recoverable video data was found in this file.").
*   **Action:** "View Technical Log" / "Try Another File".
