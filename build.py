import os
import sys
import urllib.request
import zipfile
import subprocess
import shutil

# This script prepares the release build for Windows.
# It downloads static FFmpeg binaries, extracts them, and runs PyInstaller.

FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
BUILD_DIR = "build_env"
BIN_DIR = os.path.join(BUILD_DIR, "bin")

def download_ffmpeg():
    os.makedirs(BIN_DIR, exist_ok=True)
    ffmpeg_exe = os.path.join(BIN_DIR, "ffmpeg.exe")
    ffprobe_exe = os.path.join(BIN_DIR, "ffprobe.exe")
    license_file = os.path.join(BIN_DIR, "FFmpeg_LICENSE.txt")
    
    if os.path.exists(ffmpeg_exe) and os.path.exists(ffprobe_exe):
        print("FFmpeg already downloaded.")
        return
        
    print("Downloading FFmpeg static build (GPL)...")
    zip_path = os.path.join(BUILD_DIR, "ffmpeg.zip")
    urllib.request.urlretrieve(FFMPEG_URL, zip_path)
    
    print("Extracting FFmpeg...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for member in zip_ref.namelist():
            if member.endswith("ffmpeg.exe"):
                ffmpeg_data = zip_ref.read(member)
                with open(ffmpeg_exe, 'wb') as f:
                    f.write(ffmpeg_data)
            elif member.endswith("ffprobe.exe"):
                ffprobe_data = zip_ref.read(member)
                with open(ffprobe_exe, 'wb') as f:
                    f.write(ffprobe_data)
            elif member.endswith("LICENSE.txt"):
                license_data = zip_ref.read(member)
                with open(license_file, 'wb') as f:
                    f.write(license_data)
                    
    os.remove(zip_path)
    print("FFmpeg downloaded and extracted.")

def build_executable():
    print("Running PyInstaller...")
    # Add binaries, hide console window, set icon if we had one
    # Note: On Windows, separator is ';'
    # Locate pyinstaller path based on global install
    import os
    pyinstaller_path = r"C:\Users\LEKE_TECH\AppData\Roaming\Python\Python313\Scripts\pyinstaller.exe"
    if not os.path.exists(pyinstaller_path):
        pyinstaller_path = "pyinstaller" # fallback to path

    cmd = [
        pyinstaller_path,
        "--noconfirm",
        "--clean",
        "--windowed",
        "--paths", ".",
        "--collect-all", "src",
        "--icon", "icon.ico",
        "--name", "VideoRecoverer",
        "--add-binary", f"{BIN_DIR}/ffmpeg.exe;bin",
        "--add-binary", f"{BIN_DIR}/ffprobe.exe;bin",
        "--add-data", f"{BIN_DIR}/FFmpeg_LICENSE.txt;bin",
        "--add-data", "src/gui/styles.qss;src/gui",
        "--add-data", "src/gui/icon.png;src/gui",
        "run.py"
    ]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    download_ffmpeg()
    build_executable()
    print("Build complete. Output is in the 'dist/VideoRecoverer' folder.")
