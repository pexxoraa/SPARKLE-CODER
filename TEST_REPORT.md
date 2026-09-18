# Validation report — SPARKLE CODER 0.6.0

Validated on Linux with Python 3.12.14 on 2026-09-18.

**128 automated Python tests passed, with no failures, errors, or skips.**
The complete output is in [TEST_RESULTS.txt](TEST_RESULTS.txt). Both JavaScript
scripts passed: `tests/test_ui_client.js` and `tests/test_ui_explanations.js`.
Model replies in tests are scripted; no live NVIDIA key or inference server was available.

## New guided-work workflows

Seventeen new Python tests exercise the following behavior:

- A saved brief supplies requirements to new tasks. Later brief edits do not
  remove requirements from saved tasks. Concurrent edits reject stale revisions.
  Invalid, oversized, and symlinked briefs are rejected.
- Requirements without current passing check evidence prevent completion.
  Invented requirement IDs and check IDs are rejected. Edited files make old
  evidence stale. The model still chooses coverage links; these tests do not
  establish semantic completeness of those links.
- A scripted build writes and runs a real Python addition function. Its first
  completion claim is rejected because the requirement is not linked to evidence.
  The task completes only after supplying the valid link to the passing check.
- A passing required command cannot hide another active failure or skip a failing
  discovered project suite. An environment command invalidates earlier passing
  checks even when it only changes an ignored dependency folder.
- Repeated unchanged failures trigger one source/setup review for that evidence.
  The saved repair history names inspected files and preserves the failure.
- Setup inspection locates tools and reads manifests without executing processes
  or project code. It ignores excluded secrets and symlinks, handles malformed
  package JSON, respects the declared package manager, and records no test pass.
- Docker inspection keeps host availability separate from unverified container
  tools. Installed project dependencies and compatible tool versions are not
  established by this read-only scan.
- HTTP setup and brief endpoints require the launch token. Known API keys are
  redacted, active work protects brief edits, and display preferences persist
  across app restarts. Invalid preference values preserve the existing value.

## Existing workflows retained

The complete suite also exercises the 36-versus-54 tokenizer failure fixture,
evidence-backed check correction, protected required/discovered checks,
source freshness, six real repair rounds, native/JSON model protocols, network
retry/cancellation, file import/copy/download/export, device storage migration,
PROJECTS placement, run history, approval, pause/resume/stop, logs, diffs,
conflict-aware file-tool undo, API origin checks, and the graphical launcher.
The tokenizer case is a synthetic reproduction; the user's original PyTorch
project was not available in this environment.

The JavaScript tests run actual rendering and API-helper functions with a small
DOM double. They cover plain recovery, collapsed technical details, follow-up
modes, requirement evidence, repair history, and setup labels that distinguish
finding tools from verifying software. They do not validate visual layout.

## Static and packaging checks

- Python source/test AST parsing and JavaScript syntax checks passed.
- 186 generated UI IDs are unique; no literal ID references are missing.
- Linux and macOS launcher shell syntax and macOS plist version checks passed.
- An offline package build and isolated install succeeded with no runtime
  dependencies. Installed source and UI files match the validated source.
- The installed 0.6.0 package imports successfully in isolated Python.
- `git diff --check` passed.

## Remaining limits

Live Nemotron task quality, provider cost, and model selection were not benchmarked.
The available Playwright installation has no Chromium executable, so visual browser,
clipboard, and native folder-picker behavior were not exercised. Windows/macOS
launches, Docker execution, mobile SDKs, GPU/embedded targets, and performance on
large real projects need testing in their actual environments.

A passing test proves only its assertions. The agent can still write incomplete
checks, mislabel their coverage, or require further investigation. Repeated
unchanged completion claims save the task with a recovery action; they do not
create a passing result. Provider quotas and hardware limits still apply.

This release implements Stage 1 in [ROADMAP.md](ROADMAP.md). Managed app previews,
browser automation, editor suggestions, parallel agents, GitHub UI, document tools,
plugins, scheduling, voice, and private remote access remain planned.
