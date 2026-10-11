# GitHub Release Checklist - Version 1.0.0

Use this checklist prior to publishing the GitHub Release for **Video Recoverer by Leke Tech**.

---

## 1. Pre-Release Verification
- [x] Application version set to `1.0.0` in `src/version.py`.
- [x] Automated test suite & QA validation passing (`python qa_run.py` -> 100% PASS).
- [x] Static code inspection: No API keys, credentials, or personal system paths in source code.
- [x] Forensic integrity verified: original corrupted files opened exclusively read-only (`rb`).
- [x] Diagnostic report feature exports sanitized technical information without personal data or media bytes.

## 2. Documentation & Compliance
- [x] `README.md` updated with features, usage, diagnostics, limitations, and credits.
- [x] `CHANGELOG.md` updated with v1.0.0 entry adhering to Keep a Changelog.
- [x] `LICENSE` file verified (MIT License for Leke Tech / Brice Leke).
- [x] `THIRD_PARTY_LICENSES.md` verified (GPLv3 for bundled FFmpeg & PyQt6; PSF for Python).
- [x] `docs/RELEASE_NOTES_v1.0.0.md` created with supported scenarios, privacy guarantee, and limitations.

## 3. Binary Build & Packaging
- [x] FFmpeg and FFprobe static binaries downloaded and bundled in `build_env/bin`.
- [x] PyInstaller clean build executed via `python build.py`.
- [x] Application icon (`icon.ico`) embedded into Windows PE binary.
- [x] Bundled styles (`styles.qss`) and assets included in application resources.
- [ ] Archive created: `VideoRecoverer_v1.0.0_win64.zip` containing `dist/VideoRecoverer/`.
- [ ] SHA-256 checksums calculated and recorded in `CHECKSUMS.txt`.

## 4. Release Publishing (DO NOT PUSH AUTOMATICALLY)
- [ ] Tag git commit as `v1.0.0`.
- [ ] Create GitHub Release titled `Video Recoverer by Leke Tech v1.0.0`.
- [ ] Paste release notes from `docs/RELEASE_NOTES_v1.0.0.md`.
- [ ] Attach `VideoRecoverer_v1.0.0_win64.zip`.
- [ ] Attach `CHECKSUMS.txt`.
- [ ] Publish release once Lead Engineer approves.
