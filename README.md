# SPARKLE CODER — personal edition

A local browser app for your personal NVIDIA Nemotron coding agent.
Chat with the agent, select projects, approve commands, inspect file changes,
review checks, and resume saved tasks without using a terminal interface.

Version **0.6.3**. Open **OPEN_FIRST.html** or read [START_HERE.md](START_HERE.md).
Running from source requires Python **3.11+**; there are no third-party runtime packages.
Launchers are included for Windows, macOS, and Linux.

## Packaged-app repairs and hosted interface in 0.6.3

- Packaged builds use an installed project Python interpreter for checks and
  demos. The executable's bundled interpreter runs the app itself. Project
  virtual environments take priority; missing Python gets a setup explanation.
- Moving the app and its PROJECTS folder reconnects existing managed projects
  without creating folders at the old computer's saved paths.
- The native folder picker returns its result through a temporary file, so a
  Windows app without console output can receive the selection.
- Optional cloud balance requests have a three-second deadline with no retries.
  NVIDIA and ordinary custom endpoints do not receive balance requests.
- A single `SPARKLE_GATEWAY_URL` setting supplies the cloud preset and access
  link. The separate gateway backend was not supplied and is not deployed here.
- The light/dark redesign from the supplied update is retained.
- **Connect website** pairs one hosted interface with the local engine. The
  website runs on the same computer's browser; keep the local app running.
  Reconnecting or restarting revokes the previous connection. Projects, command
  execution and approval prompts continue to use the local engine.

The Vercel build publishes only the interface assets. This is not an always-on
cloud coding engine or phone remote access. See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
for publishing and connecting the website, and [TEST_REPORT.md](TEST_REPORT.md)
for the validation limits. No live deployment is claimed until Vercel returns
a successful deployment and a verified URL.

## Startup lock repair in 0.6.2

The migration no longer treats every leftover lock file as an active task.
SPARKLE recovers a lock when its recorded process has exited. A project with an
active or uncertain lock stays at its original location while the app opens an
available project or a separate new one. Choose **Review project move → Retry
project move** after finishing the task and quitting the older app.

Original project files and saved history are retained. Copies exclude runtime
locks, and source projects stay locked while being copied. Damaged, linked, or
unverifiable locks are kept for review. Do not delete lock files to force a move.

## Startup repair in 0.6.1

A missing old project folder no longer prevents the app from opening. Available
projects still migrate into PROJECTS; missing entries retain their names and old
paths. Choose **Find folder → Browse → Reconnect project** to select a moved or
restored folder. Reconnecting uses existing files; it cannot restore deleted files.
If all saved folders are unavailable, a separate new project opens so you can
keep working. The app never silently recreates a missing registered folder.

## Guided work in 0.6.0

- **Project brief** saves your purpose, a plain-language checklist, and preferences.
  Each new task receives a snapshot. Editing the brief cannot remove requirements
  from an existing task; start a new task when your scope changes.
- **Check setup** identifies project types, locates tools, and explains missing
  setup. It reads settings without running commands or installing anything.
  A tool found on PATH is not a compatibility or behavior test. Docker's internal
  tools and installed project dependencies remain unverified by this scan.
- **Your requirements** links the saved checklist to actual check results. An
  unchecked requirement prevents a completion pass. The model proposes coverage
  links; the runtime validates IDs and results, not their semantic completeness.
- Completion considers every active recorded and discovered check, even when
  user-required commands already pass. Setup commands also invalidate earlier
  evidence through an environment revision, including changes in ignored folders.
- Repeated failed checks or completion claims trigger a source and setup review.
  **What SPARKLE investigated** shows the inspected files and next investigation.
  The agent can still need another attempt; this is not a guarantee of repair.
- **Simple view** is the default. Activity, changes, and checks remain available
  through the details button and Run monitor. Switch to advanced view in the sidebar.

This is the first release of the staged expansion. Live previews, browser
automation, a code editor, parallel agents, a GitHub panel, document tools,
plugins, scheduling, and remote access are **not implemented in this release**.
See [ROADMAP.md](ROADMAP.md) for the remaining stages and acceptance criteria.

## Simple explanations and project folders retained from 0.5.0

- Problems now say **what happened, what it means, and what to do next**.
  Long commands and tracebacks sit inside optional technical details.
- **Try fixing it** resumes investigation. **Explain this simply** switches to
  read-only Ask mode without asking you to understand programming errors.
- If an agent-created test contains a mistaken assumption, the agent can record
  a correction after reading source evidence and passing a replacement check.
  Old failures and correction reasons remain visible. Required checks and
  discovered project checks cannot be retired with this tool.
- **What works and what is left** shows recorded evidence, untested features,
  usage steps and limitations. Passed checks become stale after project edits.
  The model describes feature coverage; the runtime derives check status.
- New projects live in **SPARKLE-CODER/PROJECTS**. Settings live in **APP_DATA**.
  Older managed projects and saved tasks are copied in, preserving the originals.
- Repeated completion claims trigger another source inspection. The agent is
  instructed to check the implementation and its test assumptions, and to run
  independent checks separately so one failed assertion does not hide the rest.

These changes target confusing failures and lost progress. They are not a claim
of unique capabilities or better model accuracy than every other agent.

## Reliability features retained from 0.4.0

- Repairs continue while the project or check evidence changes; the old two/three
  completion-attempt cutoff is removed. Unchanged unsuccessful completion claims
  produce a saved task with a specific recovery step, never a fabricated pass.
- Existing Node, Python unittest/pytest, Rust and Go checks can be discovered and
  run with normal approval. The model can use other language tools directly.
- Temporary timeouts, network errors, rate limits and server failures retry with
  visible progress. Stop also releases the run during a slow API response.
- Build mode edits and verifies software. Ask mode inspects files and answers
  project questions; commands and file mutations are disabled in that mode.
- Connection settings provide key visibility, key removal, configurable API
  timeouts, and **Remove all run caps**. Saving a tested connection keeps its status.
- Large tool results are shortened in the model context while full history stays
  saved. Large projects no longer lose check freshness at a fixed size cutoff.

## SPARKLE CODER

The application is now named **SPARKLE CODER**. NVIDIA Nemotron remains the
model family used for inference. The Python package is `sparkle_coder`;
open `Open_SPARKLE_CODER.pyw`, the Windows/Linux launcher, or `SPARKLE_CODER.app`.

The first default launch imports older managed data into this application folder,
including data reached through an older chosen-storage pointer. Explicitly
registered external project folders stay in place. Project state remains in
`.nemotron/` and advanced configuration remains in `nemotron.toml`. Device
storage can change the location after launch.

## Features introduced in 0.3

- Import device files and folders; drag or paste files into Project files.
- Copy code/text to the clipboard, duplicate project files, and download files.
- Download a project ZIP or copy it into another device folder. Binary assets
  and build/dist/target output are included within the documented limits.
- A Run monitor with the current action, elapsed time, model calls, an activity
  timeline, real command output, plan steps, and check results.
- Unlimited model calls, elapsed time, and total tokens by default; optional caps
  remain available in connection settings, with Stop always available.
- Pause/resume between actions, Stop, and optional per-file diff approval.
- Save a task report or its persistent JSONL event logs.
- Choose a device data folder; copy existing managed data there while retaining
  the original folder as a backup. The chosen location survives app restarts.

See [WHAT_CHANGED.md](WHAT_CHANGED.md) for the controls and transfer limits.
Quit the previous app before opening the updated launcher. For future updates,
replace the application files in this folder while keeping **PROJECTS** and
**APP_DATA**. Use a writable location such as Documents.

## In the browser

- Chat, follow-up tasks, a live activity feed, plans, and usage counts.
- NVIDIA-hosted or local Nemotron connection settings and model discovery.
- API-key entry in **Connect Nemotron**; keys stay endpoint-specific and memory-only.
- Project registration, a native folder picker where Tk is available, and
  a manual folder-path fallback. Blank paths create new project folders.
- Text-file previews, file-tool diffs, recorded check output, and run history.
- Allow-once/deny command approval, stop, continue, and conflict-aware undo.
- A clearly labeled offline demo with real edits, failing tests, and repair.
- Responsive layout, keyboard shortcuts, and dark styling with no external
  frontend dependencies or fonts. Ctrl/Command + Enter submits a task;
  Ctrl/Command + K starts a new task when the agent is idle.

### API keys and run length

Open **Connect Nemotron** in the sidebar and paste the NVIDIA key into **API
key**. Click **Test connection**, then **Save connection**. The key is held only
in the running app process and is cleared when you quit; it is never written to
`settings.json`, a project, or Git. For the optional terminal interface, set
`NVIDIA_API_KEY` before launching (or set the endpoint's configured
`api_key_env`).

SPARKLE CODER does not stop a run after a fixed number of model calls, seconds,
or total tokens. Commands also have no default deadline. Click **Remove all run
caps**, then **Save connection**, to clear any caps from an older installation.
You can set optional positive caps under **Run and connection settings**. The
agent may choose a timeout for an individual diagnostic command.
The model endpoint still enforces its output/context size, rate limits and
account quota. These provider limits cannot be removed by the app. **Stop** ends
the local run; an already submitted model request may still finish at the provider.

## Agent capabilities

The same agent core handles planning, file search/read/write/exact edits,
foreground development commands, project memory, and saved sessions. Native
function calls and an explicit JSON fallback support compatible model servers.
Context trimming preserves whole tool exchanges and recent user corrections.
Interrupted actions are marked uncertain instead of automatically replayed.

Required acceptance commands run when the model proposes completion. Unchanged
results are reused within that run to avoid repeatedly executing the same check;
file changes and environment commands invalidate the relevant cache. Failing
checks send actual output back for repair. Without required commands, the runtime
uses recorded checks and discovers common project checks. Zero-test unittest
runs do not count as passing verification.

Results distinguish **Checks passed**, **Answer ready**, **Your input needed**,
paused and stopped tasks. A specific missing decision or an unrecoverable
connection error provides a recovery action. Repeated completion claims against
the same failing evidence ask for help; they never erase failures or pretend the
build was verified. Use **Resume task** after correcting the problem. Passing
checks establish only what those checks cover, not universal correctness.

The default is `nvidia/nemotron-3-super-120b-a12b` at
`https://integrate.api.nvidia.com/v1`. Change the model ID in settings to an ID
actually served by your endpoint. The app does not download weights, install
an inference runtime, or benchmark different Nemotron models.

| Software target | Additional tools normally needed |
| --- | --- |
| Python tools and services | Project dependencies |
| Websites and JavaScript/TypeScript apps | Node.js and project build/test tools |
| C/C++, Rust, Go, Java, .NET | Appropriate compilers, runtimes, and platform SDKs |
| Android apps | Android SDK/JDK and an emulator or device for validation |
| iOS/macOS apps | Mac, Xcode, signing/device access as needed |
| Games, embedded, GPU software | Engine or target toolchain, assets, and hardware |

It has no fixed language or app-template whitelist. Capability depends on the
model and installed tools. This implementation does not establish that it can
build every kind of software or beat another coding agent.

## Local execution and data

The default server binds only to `127.0.0.1` on an available port. API requests
require a random per-launch token; Host and Origin checks reject cross-site
requests. The UI loads no external scripts. The access token is placed in the
browser URL fragment on launch, then kept in tab session storage. The engine
stores a local instance record so the launcher can reconnect.

This is a single-user desktop application, not an internet-facing service.
Local commands run with your user permissions; file-tool path restrictions
do not sandbox a shell. Browser mode always requests approval for
agent-proposed commands. Commands supplied by you as required checks are
authorized when you click Run.

The Run monitor displays actual operations and emitted command output. It does
not display private model reasoning. Some programs buffer their output; the
current action and elapsed time remain visible during those waits. Pause takes
effect before the next action, after the current operation finishes. Stop
cancels commands and releases the run during a model request; a late response cannot execute actions.

File-edit approval reviews changes made through the agent's file tools.
Approved shell commands can also modify files; inspect those commands before
allowing them. Those shell changes are not included in the file-tool undo log.

Only foreground commands are supported. Build/test commands finish and return
output; the agent does not manage persistent app servers or provide a live
preview of the software it creates in this version.

The optional Docker mode runs commands in short-lived containers using the
supplied image definition. It requires Docker and a prepared image; setup
details remain in [CLI_REFERENCE.md](CLI_REFERENCE.md). Docker was not
available for validation here.

| Data | Location |
| --- | --- |
| New managed projects on Windows, macOS and Linux | `<SPARKLE-CODER application folder>/PROJECTS` |
| App settings and launch state | `<SPARKLE-CODER application folder>/APP_DATA` |
| Saved sessions, memory, and file backups | Each project's `.nemotron` folder |
| An explicitly registered existing project | The folder you selected |

The source launchers use the folder you extracted. Both **PROJECTS** contents
and **APP_DATA** are ignored by this repository's Git settings. **Device storage
→ Open PROJECTS folder** opens the actual location. If you explicitly choose
another storage location later, new projects use its **PROJECTS** subfolder.
Keep both folders when updating the app. An old check naming a previous project
location must be corrected before it can run, so it cannot test the backup by mistake.

Keep project session data out of Git: it can contain source code and task
history. Existing projects are registered without rewriting their Git settings.
Keys entered in the browser are excluded from settings and API responses.
The agent also redacts known credentials from tool output and model context;
this cannot identify every secret that might appear in a project.

Use **Device storage** to select an empty folder anywhere writable on your
computer. Settings, managed projects and their histories are copied there;
the previous folder remains a backup. A small location pointer stays in the
original app folder so the launcher can find your chosen location. Registered
projects outside the managed data folder stay where you placed them. Reconnect
an external drive before launching if it holds the selected folder.

App settings override matching project configuration fields. Advanced options
can still be set in a project's `nemotron.toml`; browser mode forces command
approval on. Custom endpoints omit the default NVIDIA-specific template
parameters unless another explicit configuration is supplied.

Undo covers mutations made through the file tools. It refuses to overwrite
later manual edits. Shell changes, installed dependencies, databases, and
external side effects are not part of that undo journal.

## Validation

See [TEST_REPORT.md](TEST_REPORT.md) and [TEST_RESULTS.txt](TEST_RESULTS.txt).
The automated suite exercises real file changes and Python/JavaScript/C
commands, scripted model HTTP interactions, browser API authentication,
settings, approvals, cancellation, history, and undo. Scripted tests do not
establish live Nemotron generation quality.

Visual browser testing was unavailable in the supplied environment. Windows
and macOS launchers are included but were not executed on those operating
systems. This is a source app with desktop launchers, not a signed standalone
installer or a mobile app.

For contributors, run `python3 -m unittest discover -s tests -v`,
`node tests/test_ui_client.js`, `node tests/test_ui_explanations.js`, and
`node --check sparkle_coder/ui/app.js`. The optional terminal interface
remains available in [CLI_REFERENCE.md](CLI_REFERENCE.md).

## Source map

| File | Responsibility |
| --- | --- |
| Open_SPARKLE_CODER.pyw | Graphical entry point and launch errors |
| sparkle_coder/web.py | Local HTTP server, authentication, API routes, launcher reuse |
| sparkle_coder/webapp.py | Settings, projects, background runs, approvals, diffs |
| sparkle_coder/ui/ | Browser interface, styles, and icon |
| sparkle_coder/files.py | User imports, binary downloads, copies, and ZIP exports |
| sparkle_coder/monitor.py | Live events, saved logs, pause/resume, and approvals |
| sparkle_coder/storage.py | Device folder selection and safe storage switching |
| sparkle_coder/picker.py | Optional native folder chooser |
| sparkle_coder/agent.py | Model/tool loop, context, acceptance checks, reports |
| sparkle_coder/provider.py | Model API transport and native/JSON tools |
| sparkle_coder/tools.py | Model-facing project tools and memory |
| sparkle_coder/checks.py | Read-only discovery of common project checks |
| sparkle_coder/explanations.py | Plain-language error and recovery explanations |
| sparkle_coder/verification.py | Check identities, correction history and evidence status |
| sparkle_coder/workspace.py | File boundaries, hashes, atomic writes, locking |
| sparkle_coder/locking.py | Process checks, native lock guards, abandoned-lock recovery |
| sparkle_coder/execution.py | Command execution, cancellation, limits, Docker option |
| sparkle_coder/state.py | Sessions, file journal, recovery, undo |
| tests/ | Behavioral tests with scripted model responses |

NVIDIA's [Nemotron Super API reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-super-120b-a12b)
documents the default endpoint model. Check your endpoint's served models and
current access before starting a real task.
