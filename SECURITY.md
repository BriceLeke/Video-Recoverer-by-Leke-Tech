# Security Policy

## Supported Versions

Currently, only the latest `main` branch is actively supported with security updates. 

## Reporting a Vulnerability

If you discover a security vulnerability within this project (e.g., path traversal, unsafe file execution, or a vulnerability in how corrupted files are parsed), please **do not open a public issue**.

Instead, please send a report to the maintainers via [leke-tech.com](https://leke-tech.com) or direct contact. 

We consider the following to be high-priority security issues:
- Path traversal vulnerabilities allowing the tool to write outside the intended output directory.
- Buffer overflows or arbitrary code execution triggered by malformed `mdat` chunks.
- Unsafe execution of user-controlled filenames.

We will acknowledge receipt of your vulnerability report as soon as possible and strive to send you regular updates about our progress. If you report a vulnerability, please allow us time to release a patch before disclosing it publicly.
