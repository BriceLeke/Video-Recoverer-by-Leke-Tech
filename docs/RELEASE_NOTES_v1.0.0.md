# Video Recoverer by Leke Tech v1.0.0

We are excited to announce the first stable release of **Video Recoverer by Leke Tech**, a bespoke forensic tool designed to recover playable MP4 video files that were corrupted during recording.

## What it does
When a recording device (like a phone or a camera) crashes or loses power before a recording is finished, the resulting MP4 file is often missing its container metadata (the `moov` atom). Without this metadata, media players don't know where the frames are and refuse to play the file.

Video Recoverer bypasses the need for standard metadata by forensically analyzing the raw media bitstream, extracting the video frames (NAL units), and re-muxing them into a brand-new, playable MP4.

## Who is it for?
This tool is for general users, drone pilots, screen-recording enthusiasts, and forensic investigators who have unplayable `.mp4` files and want to recover the recorded video without needing command-line technical expertise.

## Supported Recovery Scenarios
- Recordings that crashed before finishing (missing `moov` atom).
- Truncated files from power loss or app crashes.
- Reference-free recovery: Unlike other tools, Video Recoverer **does not** require a "healthy" reference video from the same device to fix your file.
- Currently supports **H.264 (AVC)** video streams inside `.mp4` containers.

## Privacy & Local Processing
Video Recoverer is **100% local**. Your video files never leave your computer. We do not upload your media to the cloud. You do not need an internet connection to run the recovery.

## Supported Platforms
This release provides a standalone binary for **Windows**. You do not need to install Python, FFmpeg, or any other dependencies. Just download the `.exe` and double-click it. 

*(For macOS and Linux, the application can be run seamlessly from source using Python 3.9+).*

## Known Limitations
- **No Guaranteed Recovery:** Recovery success depends entirely on how much media data was successfully written to disk before the crash. If the data isn't there, no tool can recover it.
- **Audio is currently dropped:** AAC audio frames in Android recordings lack explicit length headers. Because of this, audio cannot be reliably boundary-matched without the original index. To ensure smooth video playback, audio tracks are removed during recovery.
- **Constant Framerate Enforcement:** Original Variable Frame Rate (VFR) timestamps are lost when the container index is lost. The recovered video plays back at a constant framerate (inferred from the bitstream), which may cause slight drift if the original recording was heavily variable.

## Reporting Failed Recoveries
If your video isn't fully recovered or plays with severe artifacting, we want to know! 
1. Run your video through the application.
2. Click the **Export Diagnostic Report** button on the final screen.
3. Open a [GitHub Issue](https://github.com/leke-tech/video-recoverer/issues) and attach this text file. 

*Note: The diagnostic report contains only technical data (byte offsets, SPS/PPS codecs, file size). It does not contain your personal video content.*
