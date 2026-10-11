# Contributing to Forensic MP4 Recovery Engine

First off, thank you for considering contributing to this project. It's people like you that make open-source tools better.

## How Can I Contribute?

### Reporting Bugs
This tool relies on reverse-engineering corrupted files. If you find a file that should be recoverable but isn't, please open an issue.
- **Do not attach personal or sensitive videos to public issues.**
- Provide the exact device model, OS, and the app used to record the video.
- **Export a Diagnostic Report** from the application's final screen and attach the `.txt` file to your issue. This report contains crucial technical metadata (codecs, byte offsets, errors) without exposing your personal video content.

### Suggesting Enhancements
If you have ideas for how to improve the recovery algorithm (for instance, safely parsing Raw AAC frames), we are highly interested.
- Open an issue describing the proposed enhancement.
- Explain the technical rationale.
- Detail any forensic evidence supporting your approach.

### Pull Requests
1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests to the `tests/` directory.
3. Ensure the test suite passes (`pytest tests/`).
4. Keep the forensic integrity rule: **Never modify the original source file.** All operations must be read-only on the input file.
5. Update documentation if necessary.
6. Submit the PR.

## Development Setup
Check the `README.md` for standard installation instructions. You will need `pytest` installed for running the test suite.

## Styleguides
- **Python**: Follow PEP-8.
- **Architecture**: See the `docs/` folder. This project strictly separates the GUI (`src/gui`) from the recovery engine (`src/api` and `src/reconstruction`).

Thank you!
