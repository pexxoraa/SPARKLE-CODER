# Validation report — SPARKLE CODER 0.4.0

Validated on Linux with Python 3.12.14 on 2026-09-17.

**93 automated Python tests passed. No failures, errors or skipped tests.**
The complete output is in [TEST_RESULTS.txt](TEST_RESULTS.txt). The standalone
JavaScript browser API-helper test also passed. Model responses were scripted;
no live NVIDIA credentials or local inference server were available.

## Reliability workflows exercised

- Six real edit/check/repair rounds finish with passing acceptance checks, beyond
  the old three-attempt cutoff. Identical unsuccessful completion claims request
  help without inventing a pass or repeatedly rerunning unchanged acceptance tests.
- A verification command that failed repeatedly can run again after its source
  is repaired. An environment setup command invalidates cached failed checks.
- Existing Python tests are discovered, approved and executed. Node discovery
  selects real package scripts in a nested project and skips watch/placeholder
  commands. An empty unittest suite does not count as passing verification.
- A denied check is not requested again during that run; resuming can obtain a
  fresh approval. Discovery also handles commands denied before any check record.
- Ask mode rejects file edits and command execution, returns an answer without
  requiring build checks, and can resume as a Build task.
- A request for user input saves a concrete next step and does not execute later
  tool calls from the same response. An unexpected provider exception saves the
  correct recovery status instead of leaving history marked as running.
- HTTP 503 and network errors recover on retry, and retry events are observable.
  Stop cancels retry backoff and releases a run during a slow HTTP response.
  Authentication errors remain actionable and are not blindly retried.
- Large tool output is shortened only in the request copy; original history is
  preserved. A project exceeding the former 30 MB freshness cutoff still obtains
  a content hash that changes after an edit.
- Saving a tested connection retains its status. Changing the key resets it;
  key material is absent from saved settings. Optional command caps validate
  correctly, and older default command caps migrate without removing chosen run caps.

## Existing workflows retained

The suite also exercises native and JSON model protocols, a real local HTTP
browser-app workflow, authenticated file import/download/copy/export, binary
round trips, existing-file preservation, device storage migration, saved run
history and logs, file diffs and undo conflicts, command/edit approval, live
subprocess output, pause/resume/stop, launch-token and origin checks, key
redaction, exact file hashes, guidance, memory, and workspace boundaries.

Real subprocess tests include Python execution, a JavaScript assertion under
Node.js, C compilation and execution, explicit command timeout, and cancellation
of a command without a default timeout. The desktop Python launcher starts an
isolated local engine, serves its API, and shuts down cleanly on Linux.

## Source and package checks

- JavaScript syntax passed. Static markup checks found 162 unique UI element IDs
  with no duplicates or missing literal JavaScript ID references.
- `node tests/test_ui_client.js` exercised the actual browser API helper: a saved
  run error returns resumable run state, while failed HTTP requests and ordinary
  action errors still surface. This guards against endless polling of a failed run.
- Python source parsed, Unix launcher shell syntax passed, and the macOS plist
  identifies version 0.4.0 and its supplied executable.
- The package built and installed into an isolated target with no downloads or
  third-party runtime dependencies. Version 0.4.0, check-discovery code, all four
  UI assets, and the desktop entry point were present.
- Git whitespace checks passed. Temporary app state, test environments, package
  build products and credentials are excluded from the published source.

## Not exercised here

- Live Nemotron generation quality, tool selection, response latency, cost or
  comparative performance against other coding agents.
- Visual browser rendering or complete browser interactions. Playwright is
  installed, but its Chromium executable is absent in this environment. Static
  markup and JavaScript tests do not replace visual, accessibility, clipboard,
  download and native folder-picker testing on your device.
- Windows/macOS execution, Docker, mobile SDKs, game engines, GPU or embedded
  targets, and native installer signing. Their target toolchains still determine
  which software can actually be built and tested on a particular device.

Reproduce: `python -m unittest discover -s tests -v`,
`node tests/test_ui_client.js`, and `node --check sparkle_coder/ui/app.js`.
