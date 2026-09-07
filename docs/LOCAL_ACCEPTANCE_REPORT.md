# FileLens-Desktop: current local acceptance report

Status: BLOCKED. Required Windows permissions/session gates remain. This is not full local acceptance.

Run date: 2026-09-08, Asia/Karachi.
Tested current main commit: `7ccea955798374db1f5a423fb1eb16bd5768192c`.
Starting state: main, clean, correct danial-maqbool origin. Fetch and fast-forward pull completed without discarding changes.
Working source diff at test time: empty; SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Environment: Windows 11 Home build 26200, AMD64; project-local Python 3.14.3. Tesseract 5.4.0.20240606 with eng/osd; Poppler pdftoppm 26.07.0. Browser engine 143.0.7499.4.
Current evidence root: ignored `artifacts/local-qa/20260908-final-acceptance-01/`.
Earlier evidence root: ignored `artifacts/local-qa/20260907-acceptance-01/`.
The [previous acceptance report](history/LOCAL_ACCEPTANCE_20260907.md) is preserved verbatim. Earlier failures and blocked checks remain historical evidence.

## Current and retained checks

| Gate | Status | Executions and evidence |
| :--- | :--- | :--- |
| Starting Git state | PASS | `starting-state.json`, `fetch-pull.log`, `tested-source.txt`; main only is the final branch policy. |
| Windows source/vault symlinks | BLOCKED | Fresh disposable-directory creation probe returns WinError 1314. Exact existing tests: 2 run, 0 passed, 2 skipped, 0 failures/errors. `windows-symlinks/result.json`, `windows-symlinks/tests.log`. |
| Windows POSIX ciphertext mode | NOT APPLICABLE | POSIX mode assertions do not apply to Windows. It is not an application failure. |
| Full regression suite | PASS | Retained 2026-09-07 evidence: 128 executions, 125 passed, 0 failures/errors, 3 skipped. Prior `--strict` exited 1 because of skips; no fresh full-suite claim. Earlier `post-ci-fix-suite/test-report.json`. |
| Browser | PASS | Retained 2026-09-07 direct-browser evidence: 22 checks. Earlier `post-ci-fix-browser/browser-report.json`; not rerun. |
| Runtime unchanged | PASS | Compared current main with previously tested source `dc8fe8a16dca423eb9f46b87f09c8445a3d3482a`. Only report/handoff/manifest files differ. `changes-since-tested-source.txt`. No reason to repeat installation or complete feature suites. |

## Project acceptance cases

PASS cases carried from the previous report remain supported by their original dated evidence. Native blockers were reassessed this run.

| Case | Status | Findings | Evidence |
| :--- | :--- | :--- | :--- |
| FL-01 | PASS | Ten synthetic format cases including Office and mixed PDF; preview text, tags, type filters and parser warnings. | Earlier report/evidence: `final-acceptance/results.json; final-browser` |
| FL-02 | PASS | Image/scanned/mixed PDF OCR matches fixture text. Missing executable and language return errors. | Earlier report/evidence: `final-acceptance; missing-native; post-ci-fix-suite` |
| FL-03 | PASS | Keyword, semantic and combined ranking; empty/unknown/punctuation/Unicode queries; built-in LSA/TF-IDF. | Earlier report/evidence: `final-acceptance/results.json; post-ci-fix-suite` |
| FL-04 | PASS | Add/edit/rename/remove rescans leave no stale text or duplicate records. | Earlier report/evidence: `final-acceptance/results.json` |
| FL-05 | PASS | Byte-identical duplicates; saved queries and tags survive encrypted restart. | Earlier report/evidence: `final-acceptance; post-ci-fix-suite` |
| FL-06 | BLOCKED | Worker process, saved enabled/paused settings and watched event pass. Full native service lifecycle needs disposable profile. | Current: `User confirmed no disposable Windows session is available` |
| FL-07 | BLOCKED | Bounds, exclusions, corrupt archives and truncated corpora pass. Windows source symlink is blocked by account privilege; isolated Linux check passes. | Current: `windows-symlinks/result.json` |
| FL-08 | PASS | Encrypted index/backup, wrong password, deletion, failed writes/interruption; network-disabled backend and browser checks. | Earlier report/evidence: `final-acceptance; post-ci-fix-suite; offline-02` |

## Defects, regression tests and verification scope

No application defect required a source-code change during this run. No application regression test was added by this run. No assertion, encryption, consent, source protection or parser limit was weakened. No shared localdesk file changed.

## Native Windows blockers

The user explicitly confirmed that no disposable Windows session is available. No login task, credential-store write, desktop input or window-title capture was attempted on the personal session. Process-restart evidence from the earlier run is not logout/login evidence.
A fresh symlink probe ran only inside disposable synthetic directories. Windows returned error 1314, a required privilege is not held. Both existing source/vault tests were invoked; their skips remain BLOCKED, not PASS. No machine-wide security configuration was changed.

## Commands and evidence

Exact command arguments, start times, exits and durations are in `*.command.json`; native/interpreter versions are in `environment.log`. Raw paths, logs, vaults and synthetic outputs stay ignored. No personal documents, browser databases, credentials or screenshots were used. Only owned test processes were stopped.

Source-manifest verification follows review of report-only changes and is recorded in `final-manifest.log`. Runtime-only installation and prior offline runs are retained evidence and were not repeated. No new network-isolation result is claimed for this run.

GitHub final main workflow results are recorded after the report push in the workspace five-project summary and ignored `final-ci.json`; remote CI does not replace local Windows permissions. No queued or running job is called a pass.

## Exact remaining user actions

1. Supply a disposable Windows environment with symbolic-link creation capability, then run the existing source and vault symlink rejection tests there. No global security setting was changed to obtain that capability.
2. Supply a disposable Windows user/session for the documented per-user service: configure a synthetic watched folder and enabled monitoring, install with a locally entered synthetic passphrase, close the terminal, log out/in, verify a real watched event, pause/disable, restart and verify persisted state, uninstall, and check that only test-created task/credentials were removed.
3. During that service session, verify add/edit/rename/delete updates without stale index records.

## Decision

Overall: BLOCKED by the native Windows capability/session requirements listed above. Other accepted project behavior retains its previous evidence; no new full acceptance claim is made.
