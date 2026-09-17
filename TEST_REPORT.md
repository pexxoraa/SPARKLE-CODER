# Validation report — SPARKLE CODER 0.3.2

Validated on Linux with Python 3.12.14.

**72 automated tests passed. Zero failures, zero errors, zero skipped tests.**
The complete final output is in TEST_RESULTS.txt. Responses from model providers
in these tests were scripted; no live Nemotron generation was performed.

## Rename and storage compatibility

Two additional tests verify that the new SPARKLE CODER storage path is used for
new installations, while existing settings, storage pointers, projects, and
history remain discoverable in the previous Nemotron Workspace location.
Existing SPARKLE CODER settings take precedence when both installations exist.

Three run-loop tests verify that model-call, elapsed-time, and total-token caps
are optional, unlimited by default, and still enforce a positive cap when one is
explicitly configured. The browser settings accept blank values as unlimited.

## New file, supervision, and storage behaviors exercised

Sixteen additional behavioral tests passed:

- Binary import/download preserves exact bytes, with authenticated downloads.
- Imports and duplication preserve existing content and create distinct copies.
- ZIP exports include built artifacts and exclude credentials, dependencies,
  and agent state. Project-folder exports create new copies without overwrites.
- Imports reject parent traversal, protected paths, and malformed payloads.
- Imports and full-project exports are blocked while a task owns the workspace.
- Storage switching preserves files, session history, logs, and undo records,
  and the selected location persists after application restart.
- Nonempty destinations are refused. External projects keep their original
  locations. A failed copy leaves the original storage selection intact.
- A proposed file-tool edit does not execute before its diff is approved;
  denial leaves the project unchanged.
- Pause blocks an action returned by the model until Resume. Stop while paused
  exits without applying that pending action.
- Model/tool/command/approval events are recorded and survive reopening.
  Reports and full saved logs download through the authenticated API.
- Real subprocess output is observable before the process ends.
- A fake API key split across separate process writes is redacted from live output.

## Browser-app behaviors retained

- An actual local HTTP API workflow: create a demo project, wait for graphical
  command approval, allow a command, run failing tests, repair the code, pass
  checks, read files and diffs, inspect history, and undo file edits.
- Approval denial, one-use approval IDs, stop while awaiting approval, refusal
  to start a second active task, and safe handling of a repeated Stop request.
- Cancellation kills a running subprocess before it can perform a delayed file
  write. Cancellation during a model call prevents the returned edit executing.
- The graphical Python entry point starts an isolated local engine, serves its
  authenticated API, handles Quit, and removes its instance record on exit.
  This lifecycle test does not open or automate a browser.
- Launch-token authentication, wrong Host/Origin rejection, cross-site request
  rejection, strict JSON settings requests, static-asset allowlisting, and CSP.
- API keys are not returned to the UI or persisted in settings. Switching
  endpoints does not reuse a different endpoint's key. Restarting clears keys.
- Invalid settings leave the previous configuration intact. Model discovery
  is checked through a scripted provider.
- Existing project files are preserved. File reads reject protected credential
  paths and parent traversal. A saved task can resume after reopening the app.
- Undo refuses to overwrite a manual edit made after the agent's changes.

## Existing agent behaviors retained

- Real file-edit and command-execution workflows with failing acceptance tests,
  repair, and current passing checks.
- Compatible native-tool HTTP requests and JSON fallback through local scripted
  model endpoints, including real file changes and command execution.
- Model discovery, authentication errors, bounded rate-limit retries, malformed
  responses, duplicate tool-call IDs, and separate reasoning content.
- Real Python execution, a JavaScript assertion under Node.js, and C compilation
  followed by execution of the compiled program.
- Command timeouts, output limits, denial without side effects, and removal of
  model credentials from the child-process environment.
- File boundaries, secret-file protection, symlink rejection, stale-hash edit
  protection, exact-edit ambiguity, and rejecting internal Python tool names.
- Project memory, nested guidance, workspace locks, saved state, and recovery
  without blindly replaying actions that may already have run.
- Context trimming without orphaned tool messages, recent user corrections,
  stale verification rejection, failed-check gates, unverified results, and
  resumable optional run caps.

## Build and source checks

- JavaScript passed Node's syntax check. Static DOM checks found 154 unique UI
  element IDs and no missing literal JavaScript ID references.
- Python files parsed successfully. Unix launcher shell syntax passed; macOS
  Info.plist parsed and references its supplied executable.
- The package built and installed into an isolated target without downloading
  dependencies. Version 0.3.2, all four UI assets, and the graphical entry point
  were present in the installed package.
- Repository checks confirm that the source includes UI assets, launchers,
  setup guides, tests, and recorded results, excluding temporary application
  state, session keys, caches, and build output.

## Not validated here

- Visual browser behavior, layout, accessibility, clipboard integration, native
  folder-picker behavior, and click-through interactions:
  the environment's supervised browser preview service was unavailable. API
  integration tests do not substitute for visual and browser-interaction QA.
- Real Nemotron generation, latency, tool-call quality, and model cost. No NVIDIA
  key or running local inference server was provided.
- Windows and macOS launches. Platform-specific launchers and Windows process
  handling are supplied, but this environment runs Linux.
- Docker execution, mobile SDKs, game engines, embedded targets, GPU workloads,
  standalone phone/tablet execution, or native installer signing.
- Relative performance against other coding agents.

The next practical check is to open the supplied launcher on your desktop,
run the offline demo, and then run one small task against your Nemotron endpoint.
