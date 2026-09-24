# Validation report — SPARKLE CODER 0.6.3

Validated on Linux with Python 3.12 on 2026-09-24.

**174 Python tests pass.** The full output is in [TEST_RESULTS.txt](TEST_RESULTS.txt).
All four JavaScript scripts pass through `npm test`. The static website builds
with `npm run build`. `git diff --check` passes.

## Repairs verified

- A simulated frozen application completes the scripted demo using a separate
  Python interpreter. Discovered checks use that interpreter, not the GUI binary.
  A project virtual environment takes precedence. Missing Python is explained
  through setup diagnostics.
- Moving an app reconnects existing managed projects inside its current PROJECTS
  directory. Old Linux and Windows paths, unavailable external folders, saved
  history and existing recovery behavior are covered.
- The folder picker returns the selected path when stdout is unavailable. Cancel
  and helper failure remain distinct, and the private temporary result is removed.
  These are mocked windowless/Tk tests, not native Windows GUI validation.
- Optional balance calls use a three-second deadline, make no retry, and tolerate
  missing/invalid responses. NVIDIA and custom endpoints skip this optional call.
  A configured gateway supplies the URL used by the preset and access link.
- The release workflow grants `contents: write` only to its release job. All three
  platform jobs now invoke the packaged executable smoke check before upload.

## Website-to-engine HTTP boundary

Six dedicated hosted-interface tests exercise actual loopback HTTP requests:

- Only an authenticated local-origin request can pair a website.
- The paired website can create a project, read files and download a file.
- The exact approved origin and its separate random token are both required.
- Preflight responses permit only expected methods/headers for the approved site.
- Re-pairing and disconnecting revoke previous tokens; the local app stays usable.
- Website addresses containing credentials, extra paths, malformed ports or
  insecure remote origins are rejected.

The JavaScript hosted-interface test covers loopback-only engine addresses,
authenticated request/download routing, configured gateway links and the
unpaired state. DOM doubles do not establish browser rendering or network policy.

## Actual Linux executable

Built `dist/SparkleCoder` using PyInstaller and ran
`python3 scripts/smoke_packaged.py dist/SparkleCoder` successfully.

The script copies the executable into a disposable directory and verifies:

1. The packaged application starts, reports version 0.6.3 and stores PROJECTS
   beside its executable.
2. Pairing supplies a separate website token and the expected preflight headers.
3. The demo waits for command approval, runs real Python, records its deliberate
   failing check, repairs the calculator, then records a passing check.
4. The paired client reads the repaired file and saved task history and downloads
   both the file and a project ZIP containing the repair.
5. Disconnecting rejects the old website token. Local control and graceful
   shutdown still work; the instance marker is removed.

The first smoke attempt could not use this environment's default temporary
location. The fixture now supplies an explicitly writable temporary directory.
No application permission or security control was disabled.

Model responses are scripted. This check validates the executable, commands and
HTTP integration, not live Nemotron quality or browser CORS enforcement. The
available build environment could not resolve its Tcl/Tk shared libraries, so
native dialogs were not verified in the produced artifact. Do not distribute it
as a tested native-dialog build; build and check the target platform artifacts.

## Retained regression coverage

The suite also covers startup with missing folders and abandoned/live locks,
process concurrency, project migration and reconnection, session preservation,
file import/export/undo, command approval/cancellation, requirements and briefs,
setup scans, repair reviews, stale evidence, the 36-versus-54 test correction,
protected required checks, retries and saved-session recovery.

## Build and deployment state

The web output contains exactly index.html, app.js, app.css, favicon.svg and
robots.txt. A separate prepared deployment folder adds only vercel.json.
No PROJECTS, APP_DATA, keys, private settings, logs or engine code is included.
A credential-pattern scan of the web assets found no matches; the explicit file
allowlist is the primary control for excluding runtime data.

**No live Vercel deployment has been verified.** The initial unspecified deploy
was rejected by automatic approval review. A narrowed request for only the
reviewed static assets reached the connected service, which returned
`Tool deploy_to_vercel not found`. No authenticated Vercel CLI is configured in
this workspace. The connected account returned no teams or projects.

The cloud browser blocked the local URL with `net::ERR_BLOCKED_BY_CLIENT`.
Visual layout, browser network permissions and actual HTTPS-to-loopback pairing
remain unverified. HTTP tests are not a substitute for that browser check.

## Remaining limits

- Windows/macOS executables and native folder selection require real-platform
  checks. The updated GitHub build workflow has not yet run for this release.
- Live Nemotron task quality, provider cost, model choice and GPU behavior were
  not benchmarked. No live inference credentials were used.
- The separate Sparkle Cloud gateway backend was absent. Authentication,
  metering, payment handling and live NVIDIA forwarding were not validated.
- The website needs a running local engine on the same computer. This release
  adds neither an always-on cloud engine nor phone remote access.
- Live app preview, automated browser tests for generated projects, editor
  suggestions, parallel agents and the remaining roadmap stages are still planned.

Passing tests establish the assertions above, not feature parity with other
coding platforms or superior model intelligence.
