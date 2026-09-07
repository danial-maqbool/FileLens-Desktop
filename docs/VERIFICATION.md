# Verification

Run `python scripts/verify.py` to create `docs/test-report.json`. Run `python scripts/browser_check.py --record` to create `docs/browser-report.json` and record the interface. These reports describe the tested source and environment, not an unconditional guarantee.

The release workflow tests the same prepared source on Ubuntu, Windows, and macOS with Python 3.11 and 3.13. Platform reports are saved under `docs/platforms/`. Ubuntu runs with Tesseract and FFmpeg installed. Some native-tool and POSIX permission tests can be skipped on other systems. Every skip is recorded.

The Ubuntu browser test uses direct loopback navigation. It checks the real browser UI against the real backend without allowing unsafe script evaluation. The browser check also tests narrow screens, navigation, output downloads, and absence of external browser requests.

The release workflow also writes `docs/dependency-audit.json`. An audit result describes the dependency advisories available at that run. It is not a permanent security certification.

Read the reports and Actions logs for exact counts and commit IDs. Shared runtime tests run independently in each repository. Do not sum repeated tests as unique security findings.

## Review scope

The security review is a source self-review plus adversarial regression tests. It is not an independent audit. Tests cover selected malformed inputs, path traversal, request boundaries, source changes, database encryption, and supported processing paths. Real desktop permissions and user-login service installation still need validation on the target PC.
