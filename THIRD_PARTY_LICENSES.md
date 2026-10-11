# Third-Party Licenses

Video Recoverer incorporates or links to the following third-party software components in binary distributions:

---

### 1. FFmpeg & FFprobe
- **Homepage**: [https://ffmpeg.org](https://ffmpeg.org)
- **License**: GNU General Public License (GPL) v3 / GNU Lesser General Public License (LGPL) v2.1+
- **Usage**: Used for bitstream inspection, internal sample verification, and MP4 container health validation.
- **Notice**: Standalone binary distributions bundle static FFmpeg binaries built from source according to the GPL license. The full license text for the bundled build is included in `bin/FFmpeg_LICENSE.txt` and is available at [https://www.gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html). Source code for FFmpeg can be downloaded from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html).

---

### 2. PyQt6
- **Homepage**: [https://riverbankcomputing.com/software/pyqt/](https://riverbankcomputing.com/software/pyqt/)
- **License**: GNU General Public License (GPL) v3
- **Usage**: Provides the desktop graphical user interface (GUI) widgets, layouts, and event loop.
- **Notice**: PyQt6 is copyright Riverbank Computing Limited. Full GPLv3 license terms apply to distributed binaries.

---

### 3. Python Runtime
- **Homepage**: [https://www.python.org](https://www.python.org)
- **License**: Python Software Foundation (PSF) License
- **Usage**: Core application runtime environment and standard library.
- **Notice**: Python is copyright Python Software Foundation. Terms available at [https://docs.python.org/3/license.html](https://docs.python.org/3/license.html).

---

### 4. PyInstaller
- **Homepage**: [https://pyinstaller.org](https://pyinstaller.org)
- **License**: GPL v2 with special exception for generated binaries
- **Usage**: Packaging tool used to produce standalone Windows executables.
