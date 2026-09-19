# Validation report — SPARKLE CODER 0.6.2

Validated on Linux with Python 3.12.14 on 2026-09-19.

**152 automated Python tests passed, with no failures, errors, or skips.**
The complete output is in [TEST_RESULTS.txt](TEST_RESULTS.txt). All three JavaScript
scripts passed: `tests/test_ui_client.js`, `tests/test_ui_explanations.js`, and
`tests/test_ui_project_recovery.js`.
Model replies in tests are scripted; no live NVIDIA key or inference server was available.

## Abandoned-lock recovery and startup migration

Fifteen new Python tests exercise the lock-related startup failure:

- A real child process holds a workspace, is terminated by the test, and leaves
  its PID marker. The next run recovers the lock and preserves project files.
- Two independent child processes compete for one stale lock. Exactly one owns
  it; the other is refused until the owner releases it.
- Legacy markers with exited PIDs are recovered. Live, malformed, or unverifiable
  owners remain protected. Permission failures are not treated as dead processes.
- Symlinked and hard-linked markers/guards do not modify their targets. Cleanup
  does not remove a replacement marker.
- A busy legacy project is deferred while startup opens another project. Retrying
  after release copies its files and saved history without changing its ID or
  original settings. Pending entries survive restarting the app.
- Linked task folders and unknown owners stay deferred. Real copy failures retain
  the original files and current settings; a later retry succeeds.
- Source locks remain held during copying. Runtime markers and guards are absent
  from migrated and relocated copies.
- The actual Linux `Open_SPARKLE_CODER.pyw` launcher starts against a temporary
  legacy Nemotron Workspace containing an abandoned lock. Its local HTTP state
  reports recovery, saved history is accessible, and Quit app exits successfully.
- The retry route requires the launch token, rejects another origin, and refuses
  migration during a running task.

The Windows process-handle branch was tested with mocked API results for exited,
live, missing, and inaccessible processes. It was not executed on Windows. Native
Windows/macOS locking and network-filesystem behavior still need platform testing.
PID reuse is conservative: a live PID is not reclaimed even if it belongs to a
different process now. Unknown lock contents are preserved for review.

The recovery UI script also verifies distinct notices for missing folders and
pending moves, in-app retry results, selection after recovery, and active-task
guards. These use a DOM double; native browser rendering was not tested.

## Missing-folder repair retained from 0.6.1

Nine Python tests reproduce and verify the missing-folder startup repair:

- A legacy registration pointing to a missing `Projects/my-project` folder opens
  successfully. Its ID, name, and original path survive. Original settings remain
  byte-for-byte intact. A distinct new project opens, and restarting does not
  create repeated fallback projects.
- Available projects and saved tasks migrate despite missing managed or external
  folders. Real copy failures still abort, preserve originals, and remain retryable.
- Reading or re-adding a missing registered folder cannot silently recreate it.
  Availability updates when its drive or original folder returns.
- Reconnecting a moved folder preserves its project ID, files, saved task history,
  and previous path. Check evidence from the old location becomes stale.
- Invalid, missing, duplicate, locked, and active-task reconnect attempts are
  rejected. A settings-write failure restores the in-memory registration.
- Changing device storage copies available work while preserving missing paths.
- Local HTTP startup state, file and history reads, and reconnection work together.
  The reconnect route rejects requests without a token or from another origin.

The recovery UI script exercises the actual notice, missing-project selection,
inline error, active-task guard, and successful reconnection functions with a DOM
double. The screenshot's filesystem condition was reproduced in temporary test
folders; the user's original device folders are not accessible here.

## Guided-work workflows retained from 0.6.0

Seventeen Python tests exercise the following behavior:

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
- 205 UI IDs, including the HTML shell, are unique; no literal ID references are missing.
- Linux and macOS launcher shell syntax and macOS plist version checks passed.
- An offline package build and isolated install succeeded with no runtime
  dependencies. Installed source and UI files match the validated source.
- The installed 0.6.2 package imports successfully in isolated Python, including
  the new locking module. All 27 installed source/UI files match the source tree.
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
