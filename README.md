# Video Recoverer by Leke Tech

[![Official Site](https://img.shields.io/badge/Official_Site-leke--tech.com-2dd4bf?style=flat-square)](https://leke-tech.com)
[![Product Page](https://img.shields.io/badge/Product_Page-leke--tech.com%2Fvideo--recoverer-14b8a6?style=flat-square)](https://leke-tech.com/video-recoverer)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows_x64-blue.svg?style=flat-square)]()

> 🌐 **Official Website:** [leke-tech.com](https://leke-tech.com)  
> 🎬 **Product Page:** [leke-tech.com/video-recoverer](https://leke-tech.com/video-recoverer)

Forensic MP4 recovery tool that restores playable video from corrupted recordings when container metadata is missing or incomplete.

## What is this?
This project is a bespoke, forensic MP4 recovery tool developed by [Leke Tech](https://leke-tech.com). Official downloads, product information, and updates are available at [leke-tech.com/video-recoverer](https://leke-tech.com/video-recoverer). When an Android device, screen recorder, or camera crashes during recording, the resulting MP4 file is often left in an incomplete state (typically missing the `moov` atom, which contains the index of all media samples). Without this index, standard media players cannot play the file. 

This engine scans the raw bitstream of the corrupted file, identifies the video frames (NAL units), and re-muxes them into a new, valid MP4 container.

## Why it exists
Most existing open-source recovery tools (like `untrunc`) require a "healthy reference video" from the exact same device and settings to rebuild the missing metadata. This project was built to operate in a **strictly reference-free context**, automatically inferring the missing parameters (like resolution, SPS/PPS headers, and framerate) purely from the corrupted bitstream.

## Features
- **No Reference Video Required**: Automatically infers SPS/PPS headers and video resolution directly from the corrupted bitstream.
- **100% Local Processing**: Your video never leaves your computer. No cloud uploads, no privacy concerns.
- **Non-Destructive**: The original corrupted MP4 file is never modified or overwritten. Operations are performed in read-only mode.
- **Large File Support**: Processes files cleanly in chunks. Does not load multi-gigabyte videos entirely into RAM.
- **Clean UI**: Comes with a simple, professional desktop graphical interface for non-technical users.

## Supported Formats
Currently, the recovery engine focuses on the most common screen recording and mobile camera formats:
- **Container**: `.mp4`
- **Video Codec**: H.264 (AVC)

## Known Limitations
- **Audio is not supported**: AAC audio frames in Android screen recordings do not use ADTS headers and lack explicit length prefixes. Without the `moov` index, audio boundaries cannot be reliably recovered without a full Huffman bitstream decoder. Audio tracks are currently dropped during recovery.
- **Variable Frame Rate (VFR) drift**: Because the audio track is dropped and exact frame timestamps are lost, the recovered video will use a constant framerate. This may result in slight playback speed anomalies if the original recording had heavy VFR.
- **Recovery is never guaranteed**: The success of the recovery depends entirely on how much of the media data actually survived the crash and made it to the disk.

## Installation

The easiest way to use Video Recoverer is to download the prebuilt standalone application directly from our official product page or GitHub:

1. Visit [leke-tech.com/video-recoverer](https://leke-tech.com/video-recoverer) or go to the [GitHub Releases](https://github.com/leke-tech/video-recoverer/releases) page.
2. Download `VideoRecoverer_v1.0.0_win64.zip` or `VideoRecoverer.exe` (Windows).
3. Double-click to run. You do not need to install Python or FFmpeg—all forensic engines are self-contained.

### Development Setup
If you want to run from source or contribute to the project:
- Python 3.9+

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/video-recoverer.git
   cd video-recoverer
   ```
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Usage

### Running the Desktop Application
If you downloaded the `.exe` file, simply double-click it.

If running from source:
```bash
python -m src.gui.main
```
Simply drag and drop your corrupted MP4 into the window and click "Recover Video".

### Running via Command Line (CLI)
*CLI wrapper is currently under development. You can interface with the core engine programmatically via `src.api.engine.RecoveryEngine`.*

## Reporting a Corrupted-Video Case
If you have a corrupted video that this tool fails to recover, please open an Issue on GitHub. 
1. Provide the exact device model, OS, and recording app used.
2. Run the tool via command line to capture the terminal output and attach it to the issue.
3. **Do not publicly upload personal or sensitive videos.** If a sample is needed, we may request a non-sensitive test recording from the same device.

## Generating a Diagnostic Report
If your video isn't fully recovered or fails to play properly, Video Recoverer allows you to export a **Diagnostic Report**.

1. Run your video through the application.
2. If it fails or produces a partial result, click **Export Diagnostic Report** on the final screen.
3. Save the `.txt` file locally.

**Privacy Note:** The diagnostic report is strictly technical (app version, file size, codec metadata, NALU boundaries, and error codes). It **does not** contain your video data, audio data, or personal file paths.

Please attach this report when opening a [GitHub Issue](https://github.com/leke-tech/video-recoverer/issues). This helps us improve compatibility with additional camera encoders and corruption variants!

## Contributing
We welcome contributions! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests.

Check out the `docs/` folder for a deep dive into the technical recovery approach, including the `RECOVERY_ALGORITHM.md` and `ARCHITECTURE.md`.

## Credits & Attribution
This product was developed by [Leke Tech](https://leke-tech.com) and created by **Brice Leke** (Founder & CEO). 

*   **Official Website:** [leke-tech.com](https://leke-tech.com)
*   **Product Page:** [leke-tech.com/video-recoverer](https://leke-tech.com/video-recoverer)

If you use this tool in an investigative, corporate, or academic setting, or if you integrate its engine into your own products, we kindly ask that you provide attribution to Leke Tech and Brice Leke.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
