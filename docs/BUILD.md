# Build & Release System

This project is packaged into a standalone, reproducible desktop executable using `PyInstaller`. 

The core design philosophy for our releases is that **non-technical users must be able to run the application immediately after downloading it**, without needing to install Python, FFmpeg, or any development dependencies manually.

## Build Requirements
- Python 3.9+
- `pip install -r requirements.txt` (which should include `pyinstaller`)

## Bundling External Binaries (FFmpeg)
Because this application depends on FFmpeg and FFprobe for resolution inference and output validation, these binaries must be bundled alongside the application.
- The `build.py` script automatically downloads static builds of FFmpeg and bundles them into the PyInstaller payload.
- The application runtime (via `sys._MEIPASS`) dynamically locates these binaries inside the temporary extracted payload directory at runtime.

## Supported Platforms
We actively prioritize and support building for:
1. **Windows (64-bit)**
2. **macOS**
3. **Linux**

*Note: You must run the build script on the target OS you wish to compile for. PyInstaller does not support cross-compilation out of the box.*

## Generating a Release Build (Windows)

1. Open your terminal/PowerShell.
2. Activate your virtual environment.
3. Run the automated build script:
   ```bash
   python build.py
   ```
4. The script will:
   - Download the latest GPL static Windows release of FFmpeg.
   - Extract `ffmpeg.exe`, `ffprobe.exe`, and their `LICENSE.txt`.
   - Run `PyInstaller` in `--windowed` (no console) mode.
   - Bundle the GUI stylesheets and the FFmpeg binaries.
5. The final standalone executable will be located in the `dist/VideoRecoverer` folder.

## Licensing
The `build.py` script specifically downloads the GPL version of FFmpeg. The script extracts and bundles the FFmpeg `LICENSE.txt` inside the binary to comply with GPL redistribution requirements.

## Application Versioning
The application's version is explicitly declared in `src/version.py`. This version is read by the UI and displayed in the main window to aid in support and bug reports.
