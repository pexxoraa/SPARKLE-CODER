# SPARKLE CODER — personal edition

A local browser app for your personal NVIDIA Nemotron coding agent.
Chat with the agent, select projects, approve commands, inspect file changes,
review checks, and resume saved tasks without using a terminal interface.

Version **0.3.1**. Open **OPEN_FIRST.html** or read [START_HERE.md](START_HERE.md).
Python **3.11+** is required once; there are no third-party runtime packages.
Launchers are included for Windows, macOS, and Linux.

## SPARKLE CODER 0.3.1

The application is now named **SPARKLE CODER**. NVIDIA Nemotron remains the
model family used for inference. The Python package is `sparkle_coder`;
open `Open_SPARKLE_CODER.pyw`, the Windows/Linux launcher, or `SPARKLE_CODER.app`.

Existing installations retain access to their original data folder, including
chosen storage locations. Project state remains in `.nemotron/` and advanced
configuration remains in `nemotron.toml` for compatibility. New installations
use the SPARKLE CODER data directories listed below. Device storage can change
the location after launch.

## Features introduced in 0.3

- Import device files and folders; drag or paste files into Project files.
- Copy code/text to the clipboard, duplicate project files, and download files.
- Download a project ZIP or copy it into another device folder. Binary assets
  and build/dist/target output are included within the documented limits.
- A Run monitor with the current action, elapsed time, model calls, an activity
  timeline, real command output, plan steps, and check results.
- Pause/resume between actions, Stop, and optional per-file diff approval.
- Save a task report or its persistent JSONL event logs.
- Choose a device data folder; copy existing managed data there while retaining
  the original folder as a backup. The chosen location survives app restarts.

See [WHAT_CHANGED.md](WHAT_CHANGED.md) for the controls and transfer limits.
Quit the previous app before opening the updated launcher. Your existing
registered projects remain available through the same local settings.

## In the browser

- Chat, follow-up tasks, a live activity feed, plans, and usage counts.
- NVIDIA-hosted or local Nemotron connection settings and model discovery.
- Password input with endpoint-specific, memory-only API keys.
- Project registration, a native folder picker where Tk is available, and
  a manual folder-path fallback. Blank paths create new project folders.
- Text-file previews, file-tool diffs, recorded check output, and run history.
- Allow-once/deny command approval, stop, continue, and conflict-aware undo.
- A clearly labeled offline demo with real edits, failing tests, and repair.
- Responsive layout, keyboard shortcuts, and dark styling with no external
  frontend dependencies or fonts. Ctrl/Command + Enter submits a task;
  Ctrl/Command + K starts a new task when the agent is idle.

## Agent capabilities

The same agent core handles planning, file search/read/write/exact edits,
foreground development commands, project memory, and saved sessions. Native
function calls and an explicit JSON fallback support compatible model servers.
Context trimming preserves whole tool exchanges and recent user corrections.
Interrupted actions are marked uncertain instead of automatically replayed.

Required acceptance commands rerun when the model proposes completion. Failing
checks send their actual output back for repair. Results distinguish checked,
unverified, blocked, paused, and stopped tasks. Passing checks establish only
what those checks cover, not universal correctness.

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
cancels commands and prevents further actions after an in-flight model request.

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
| Windows settings and managed projects | `%LOCALAPPDATA%/SparkleCoder` |
| macOS settings and managed projects | `~/Library/Application Support/SparkleCoder` |
| Linux settings and managed projects | `$XDG_CONFIG_HOME/sparkle-coder`, otherwise `~/.config/sparkle-coder` |
| Saved sessions, memory, and file backups | Each project's `.nemotron` folder |

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

For contributors, run `python3 -m unittest discover -s tests -v` and
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
| sparkle_coder/workspace.py | File boundaries, hashes, atomic writes, locking |
| sparkle_coder/execution.py | Command execution, cancellation, limits, Docker option |
| sparkle_coder/state.py | Sessions, file journal, recovery, undo |
| tests/ | Behavioral tests with scripted model responses |

NVIDIA's [Nemotron Super API reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-super-120b-a12b)
documents the default endpoint model. Check your endpoint's served models and
current access before starting a real task.
