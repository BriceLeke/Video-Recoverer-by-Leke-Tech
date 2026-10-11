# Desktop Architecture

## 1. GUI Technology Choice
**Decision:** `PyQt6` (or `PySide6`)
**Reasoning:**
*   **Lightweight & Native:** Unlike Electron, it does not require shipping a full Chromium browser engine, saving hundreds of megabytes in memory and disk footprint.
*   **Python Native:** Our recovery engine is written in Python. Using a Python-native GUI framework allows us to directly import and instantiate the `RecoveryTask` API without building local HTTP servers, IPC bridges, or WebSockets.
*   **Concurrency:** PyQt's `QThread` and Signals/Slots mechanism is perfectly suited for managing the long-running video recovery process in the background while keeping the UI responsive.
*   **Packaging:** Easily bundled into a single standalone `.exe` using `PyInstaller`.

## 2. System Architecture

The application is divided into three distinct layers:

### 2.1. Presentation Layer (GUI Thread)
*   **Technology:** PyQt6 Widgets (`QMainWindow`, `QStackedWidget`, `QProgressBar`).
*   **Responsibility:** Rendering the UI, handling drag-and-drop events, capturing button clicks, and updating progress bars.
*   **Rule:** The GUI thread must **never** perform file I/O or heavy computation. It must remain perfectly responsive.

### 2.2. Coordination Layer (QThread / Worker)
*   **Technology:** PyQt6 `QThread` + Custom Signals.
*   **Responsibility:** Acts as the bridge between the UI and the Recovery Engine.
*   **Flow:**
    1. UI requests recovery.
    2. A `RecoveryWorker` (inheriting `QThread`) is spawned.
    3. The worker instantiates the core `RecoveryTask`.
    4. The worker attaches a callback to the `RecoveryTask` that emits a PyQt Signal (`progress_updated.emit(percentage)`).
    5. When the task finishes, the worker emits `finished.emit(metadata)`.
    6. If the user clicks Cancel, the worker calls `RecoveryTask.cancel()`.

### 2.3. Core Engine Layer (Existing Codebase)
*   **Technology:** Pure Python (`src/api/engine.py`).
*   **Responsibility:** Fast, zero-copy, memory-efficient bitstream parsing and MP4 container reconstruction.
*   **Independence:** The core engine remains completely oblivious to PyQt6. It only knows about standard Python callbacks and data classes (`RecoveryOptions`, `RecoveryMetadata`).

## 3. Directory Structure Addition

```text
src/
  ├── api/              # Existing programmatic API
  ├── h264/             # Existing parsing logic
  ├── reconstruction/   # Existing MP4 muxer
  └── gui/              # NEW: Desktop application components
      ├── main.py       # Application entry point
      ├── worker.py     # QThread integration for background recovery
      ├── styles.qss    # Dark mode CSS-like styling
      └── widgets/      # Individual screen components
          ├── dropzone.py
          ├── progress.py
          └── success.py
```
