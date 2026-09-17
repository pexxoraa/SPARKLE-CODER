# Optional command-line reference

A terminal coding agent for your own projects. It uses NVIDIA Nemotron through
an OpenAI-compatible endpoint, edits real files, executes development commands,
remembers project decisions, and repairs failures from actual test output.

The browser interface is documented in [START_HERE.md](START_HERE.md).
These optional commands remain available in version **0.3.2**.

## Included

- One-shot tasks and an interactive conversation.
- Configurable Nemotron model and endpoint.
- Native function calls, plus explicit JSON tool mode for chat-only servers.
- File listing, text search, reading, creation, exact edits, and deletion.
- Current-file hashes to prevent overwriting intervening user edits.
- Saved plans, bounded project memory, full conversation state, and session resume.
- Context trimming at complete tool-exchange boundaries; original goals and recent
  user corrections remain in a separate checkpoint.
- Terminal commands for installed language toolchains.
- User-owned acceptance commands, a failed-check repair loop, and honest
  checked/unverified/blocked states.
- Per-command approval by default; optional Docker execution.
- Bounded command output and command timeouts. Model-call, elapsed-time, and
  total-token caps are unlimited unless you set them explicitly.
- Conflict-aware undo for changes made through file tools.
- An offline demonstration and automated tests.

There is no account system, public website, telemetry collector, or subscription
layer in this code. Hosted inference still sends the selected context to the
model provider and is subject to that provider's terms and usage limits.

## Scope across software types

The tools do not enforce a programming-language whitelist or a fixed application
template. Capability depends on the selected model and your environment.

| Target | What your environment also needs |
| --- | --- |
| Python tools, automation, services | Python and project dependencies |
| Websites and JavaScript/TypeScript apps | Node.js and the project's build/test tools |
| Native C/C++, Rust, or Go software | Its compiler, dependencies, and platform SDK |
| Java or .NET applications | JDK or .NET SDK |
| Android applications | Android SDK, suitable JDK, emulator/device as needed |
| iOS/macOS applications | A Mac, Xcode, and signing/device access as needed |
| Games | Appropriate engine, assets, and engine-specific validation |
| Embedded or GPU software | Target SDK/toolchain and appropriate hardware for full validation |

Python, JavaScript, and C command execution were tested in this build.
That does not establish model quality across those languages. Mobile SDKs,
games, GPU workloads, and device testing were not available here.

## Installation

Python 3.11+ is sufficient for the agent itself. From this folder:

```bash
python3 -m sparkle_coder --help
python3 -m sparkle_coder demo --workspace ../nemotron-demo
```

Optional installation:

```bash
python3 -m pip install -e .
sparkle-coder --help
```

The supplied source runs without installation while your terminal is in this
folder. On Windows, use the Python launcher `py -m`, or the installed
`sparkle-coder` command. The implementation includes Windows process handling,
but only Linux was exercised here.

## NVIDIA-hosted models

Default endpoint: `https://integrate.api.nvidia.com/v1`.
Default model: `nvidia/nemotron-3-super-120b-a12b`.

The hosted route runs the model remotely; the agent does not need a local GPU.
Provide the key through the `NVIDIA_API_KEY` environment variable and create
project configuration. Never put the key in `nemotron.toml` or commit it:

```bash
python3 -m sparkle_coder init --workspace ../my-app
python3 -m sparkle_coder doctor --workspace ../my-app --connect
python3 -m sparkle_coder models --workspace ../my-app
```

Set the environment variable before launching. On macOS/Linux:

```bash
export NVIDIA_API_KEY="paste-your-key-here"
```

On Windows PowerShell:

```powershell
$env:NVIDIA_API_KEY = "paste-your-key-here"
```

The browser launcher also accepts the key in **Connect Nemotron → API key**;
it keeps that value in memory only and clears it when the app quits.

Use the exact model ID returned by your endpoint. These are documented family
members; availability and access must be checked against your account:

| Family member | NVIDIA model ID |
| --- | --- |
| Nemotron 3 Super | nvidia/nemotron-3-super-120b-a12b |
| Nemotron 3 Nano | nvidia/nemotron-3-nano-30b-a3b |
| Nemotron 3 Ultra | nvidia/nemotron-3-ultra-550b-a55b |

Choose with `--model MODEL_ID` or the project's `nemotron.toml`. This implementation
does not benchmark or rank the models.

The Super default follows NVIDIA's documented sampling settings and includes
`chat_template_kwargs.force_nonempty_content = true`. The output limit is
16,000 tokens, including any reasoning tokens charged against that limit.
If responses repeatedly exhaust it, raise `max_tokens` within the endpoint's
supported limits or configure the model's documented reasoning options.
Other models/servers may need different settings.

Runs have no default model-call, elapsed-time, or total-token cap. Use
`--max-steps`, `--max-seconds`, or `--max-total-tokens` when you want an
explicit cap for a CLI invocation. The browser has the same optional fields;
leave them blank for unlimited runs. `--max-tokens` remains the per-response
output limit required by the model API.

## Fully local inference

The agent connects to an existing model server. It does not download model
weights, provision GPUs, or install inference runtimes.

1. Serve a Nemotron model with an OpenAI-compatible server such as a compatible
   vLLM, SGLang, or NVIDIA NIM deployment. Choose a model/quantization that fits
   your hardware and follow that model's serving documentation.
2. Edit `nemotron.toml` using `examples/local.nemotron.toml` as a guide. Set
   `base_url`, `model`, and `api_key_env = "LOCAL_MODEL_API_KEY"`. Leave that
   environment variable unset if your local server does not require a key.
3. Run `models --all` to see served IDs and `doctor --connect` to check access.
4. Native tool calls require the server's correct tool parser. If your backend
   only produces text, explicitly select `tool_format = "json"`.

For example:

```toml
base_url = "http://127.0.0.1:8000/v1"
model = "the-exact-id-exposed-by-your-server"
api_key_env = "LOCAL_MODEL_API_KEY"
tool_format = "native"
extra_body = {}
```

Loopback HTTP is allowed. Other HTTP endpoints require explicit
`allow_insecure_http = true`; prefer HTTPS for a remote server.

MoE active parameter counts do not equal the total memory needed to serve the
model. Select local inference after checking RAM/VRAM and the exact model's
deployment requirements.

## Everyday commands

```bash
# Work on an existing project.
sparkle-coder run -w ../app \
  --verify "npm test -- --run" \
  --verify "npm run build" \
  "Fix the failing checkout flow. Preserve the public API and add a regression test."

# Follow-up instructions in the same saved session.
sparkle-coder resume SESSION_ID -w ../app \
  --message "Keep the current database schema; change only the service layer."

# Ongoing interactive work.
sparkle-coder chat -w ../app

# Inspect history and verification.
sparkle-coder sessions -w ../app
sparkle-coder report SESSION_ID -w ../app

# Preview and apply conflict-aware file rollback.
sparkle-coder undo SESSION_ID -w ../app --dry-run
sparkle-coder undo SESSION_ID -w ../app
```

Replace example test commands with commands supported by your project.
If no required checks are configured, the agent can select checks itself.
If it cannot establish current passing checks, its result is explicitly
**unverified**. A passing trivial command or incomplete generated test suite
does not prove a requirement; meaningful user-owned checks are preferable.

User-configured `--verify` commands are authorized by the user and run without
an extra approval prompt. Model-proposed commands require approval unless
`--auto-approve` or `auto_approve = true` is explicitly selected.
Noninteractive runs deny unapproved commands.

## Execution and data boundaries

**Local terminal execution is not an OS sandbox.** Approved commands run with
your operating-system permissions. File-tool path checks do not confine shell
commands or protect files a shell can access. Run against a trusted, backed-up
project or use a disposable environment.

File tools reject parent traversal, symlinks, hard-linked files, agent state,
Git internals, and common credential filenames. Model credentials are excluded
from the child command environment. Known environment secrets are redacted from
model context, visible output, and reports. This is best-effort hygiene, not a
guarantee that arbitrary source files or process output contain no secrets.

Conversation state and backups are stored locally under `.nemotron/`. They may
contain source code and task data. Do not commit this directory. Initialization
adds it and the local configuration to the project's Git ignore file.

The agent does not automatically commit, push, or deploy. Its prompt requires
explicit authorization for external actions; command approval and OS/container
boundaries provide the actual execution controls.

## Optional Docker command execution

Build the supplied general development image yourself:

```bash
docker build -t sparkle-coder-tools:local -f containers/Dockerfile .
sparkle-coder run -w ../app --execution docker \
  --verify "python3 -m unittest discover -s tests -v" \
  "Implement the requested changes and regression tests."
```

The model client stays on the host. Commands run in short-lived containers with
the project mounted, dropped capabilities, a read-only root filesystem,
temporary scratch space, resource limits, and networking disabled by default.
The agent state directory is masked from the container.

Workspace files, including any credentials you place in that workspace, are
visible to container commands. Keep credentials outside it. The container can
modify mounted project files. Docker is an isolation option, not an assurance
against every attack or harmful project change.

The default image includes Python, Node.js, C/C++ build tools, Git, and ripgrep.
Add other toolchains to a custom image. For dependencies, prepare the image or
explicitly enable `docker_network = true`. Docker mode was not run in the supplied
environment because Docker is unavailable there.

## Recovery and limits

- Save points occur before a model-requested action and after its result.
- An action interrupted before its result was saved is marked uncertain on
  resume. It is never blindly replayed. The model must inspect current state.
- Undo checks all known file conflicts before restoring originals or removing
  newly created files. It refuses to overwrite later user changes.
- Undo covers file-tool edits only. Shell edits, package installations, database
  changes, deployments, and external side effects require separate recovery.
- A crashed process can leave `.nemotron/workspace.lock`. Check its recorded PID
  and remove the lock only after confirming that the process has stopped.
- Optional run caps bound work when configured, but are not a hard billing
  guarantee: in-flight requests, retries, and estimated token usage can exceed a cap.
- Only foreground commands are supported. Browser/integration test scripts must
  start and stop their own development servers.
- Files over 1 MB are not read through the text tool; one file-tool write is
  limited to 200 KB. Large projects may need narrower searches or adjusted limits.
- Verification freshness hashes exclude common generated and credential paths,
  and are bounded to 5,000 files / 30 MB. They are not whole-system proofs.

## Tests and current validation

```bash
python3 -m unittest discover -s tests -v
```

See TEST_REPORT.md and TEST_RESULTS.txt for the recorded run. The HTTP tests use
a local scripted endpoint with actual protocol serialization, file writes, and
program execution. No live Nemotron generation or performance comparison was
possible here without an API key or running model.

## Source layout

| File | Responsibility |
| --- | --- |
| sparkle_coder/cli.py | Setup, run, resume, chat, history, diagnostics, undo |
| sparkle_coder/provider.py | API requests, native/JSON tool formats, bounded retries |
| sparkle_coder/agent.py | Execution loop, context checkpoint, acceptance gates, reports |
| sparkle_coder/tools.py | Model-facing project tools and memory |
| sparkle_coder/workspace.py | File boundaries, hashes, atomic writes, locking |
| sparkle_coder/execution.py | Foreground processes, output limits, Docker option |
| sparkle_coder/state.py | Sessions, journal, uncertain-action recovery, undo |
| sparkle_coder/demo.py | Clearly labeled offline repair demonstration |

Potential next increments are a live task benchmark and browser-test integration
for projects built by the agent. The current artifact is a usable foundation for
personal coding workflows, not a claim of universal software engineering.

## Primary references checked for this version

- [Nemotron Super API and deployment guidance](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-super-120b-a12b)
- [Nemotron Super hosted model](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b)
- [Nemotron Nano model documentation](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-nano-30b-a3b)
- [Nemotron Ultra model documentation](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-ultra-550b-a55b)

Model IDs, access, and serving requirements can change. The runtime configuration
is intentionally editable.
