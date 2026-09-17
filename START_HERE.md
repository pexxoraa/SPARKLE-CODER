# Open SPARKLE CODER

Version **0.5.0** is a browser interface for your personal coding agent.
Everyday use takes place in the browser: connect a model, select a project,
describe work, approve commands, inspect files, and continue saved tasks.

## Upgrading from the previous version

Use **Quit app** in the old window before opening this updated launcher. Extract
this version into a new application folder; do not overwrite a running app.
On first launch, SPARKLE CODER detects the earlier SPARKLE CODER or Nemotron
Workspace data folder, including an older selected-folder pointer. It copies
managed projects and saved tasks into **PROJECTS** inside this application folder.
Original folders stay as backups. Projects you registered from external folders
stay at those locations. The launcher detects a still-running older version and
tells you to quit it before continuing.

For future updates, quit the app and replace its program files in this same
folder. Keep **PROJECTS** and **APP_DATA**; they contain your work and settings.

## First launch

1. Extract the complete ZIP into a writable folder, such as Documents. Keep all
   its files together. The app needs to create **PROJECTS** and **APP_DATA** here.
2. Install **Python 3.11 or newer** once, if it is not already installed.
   Use [python.org](https://www.python.org/downloads/) on Windows/macOS or your
   Linux software manager. Windows users should include the Python launcher
   and Python file associations. No agent dependencies or pip commands are needed.
3. Open the launcher for your desktop:

| Desktop | Launcher | Notes |
| --- | --- | --- |
| Windows | `Start_Windows.vbs` | Starts without a console window. If VBScript is unavailable, open `Open_SPARKLE_CODER.pyw` with Python. |
| macOS | `SPARKLE_CODER.app` | Keep the app inside the extracted folder. This unsigned personal app may require approval through macOS Privacy & Security. |
| Linux | `Start_Linux.sh` | In Properties → Permissions, allow executing as a program, then open it and choose Run. File-manager labels vary. |

The launcher opens your default browser automatically. Reopening the launcher
reconnects to an existing engine when one is already running. Closing a tab
leaves the engine running; **Quit app** stops it.

You can also open **OPEN_FIRST.html** for a graphical setup guide.
These are source-app launchers, not signed standalone installers; Python is
required. Windows and macOS launch behavior has not been tested here.

## Find your projects

New projects are saved in **SPARKLE-CODER/PROJECTS**. Each project has its own
folder. App settings are saved in **SPARKLE-CODER/APP_DATA**. Open **Device storage
→ Open PROJECTS folder** to see them in your file manager. Your files are stored
on your device, not in browser storage.

## Choose a different device data folder (optional)

Open **Device storage** in the sidebar. Its field shows the current storage
location. Use **Browse** or paste an absolute path to an empty folder, then
click **Copy data and use this folder**. Your settings, managed projects,
history, and logs move to the selected location by copying; the original stays
as a backup. Existing projects outside that data folder stay where they are.
Use **Open current folder** to inspect the saved files in your file manager.

## Try it without a model key

Click **Take it for a test run**. The app creates a separate demo project,
writes a calculator and tests, and asks to run a syntax check. Choose
**Allow once**. It then runs failing acceptance tests, fixes the arithmetic
bug, and reruns the tests. Inspect **Run monitor**, **Changes**, and **Checks**. The demo opens the monitor;
click **Review action** when its command needs approval.

The demo uses clearly labeled scripted responses. File edits, command execution,
test failures, repair, and passing checks are real. It does not call Nemotron.

## Connect Nemotron

Open **Connect Nemotron** in the sidebar.

- **NVIDIA API:** obtain your key from the
  [Nemotron model page](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b),
  paste it into the **API key** field, and use the model ID your account can access.
  Click **Test connection**, then **Save connection**. Hosted inference does
  not require a GPU in this computer; selected project context goes to NVIDIA.
- **Local or custom server:** enter the URL of an already running compatible
  Nemotron server and its exact served model ID. A key is optional for an
  unauthenticated local endpoint. Use **JSON fallback** only if your server
  does not support native tool calls. The app does not install model weights
  or start an inference server.

The connection test checks access and model discovery. Your first real task
also exercises generation and tool calls. A server must expose both
`/v1/models` and `/v1/chat/completions` for the full workflow.

Keys entered in the app are kept in memory, scoped to their endpoint, and
cleared when the engine quits. Reenter them after restarting. Settings and
project paths are saved; passwords are not. Do not put credentials in prompts
or `nemotron.toml`. The optional terminal interface reads `NVIDIA_API_KEY`
(or the configured `api_key_env`) from the environment before launch.

## Choose how to work

Use **Build · edit and verify** for implementation work. Use **Ask · inspect and
explain** for architecture questions or reading code; that mode cannot edit
files or run commands and does not require build checks.

In **Connect Nemotron**, choose **Remove all run caps**, then **Save connection**.
This clears model-call, elapsed-time, total-token and command-duration caps.
Provider context/output limits and account quotas still apply. Use **Stop** to
end a run yourself. The key's **Show** button lets you inspect what you pasted;
**Remove configured key** clears it for this app session.

## Build something

Click **+** beside the project selector. Give your project a name. Leave the
folder blank for a new project, or use **Browse** to select an existing one.
If the native chooser is unavailable, copy the absolute folder path from your
file manager into the field.

For a first real task, try:

> Build a simple offline to-do list. Let me add, complete and delete tasks, and
> keep them after refreshing. Test those actions. Explain how to open and use
> it in simple steps; I do not have programming experience.

Click **Run agent**. Approve commands after reviewing them. Required commands
entered under **Checks** are authorized when you start the task and run
automatically when the agent proposes completion. The agent can also propose
its own checks. Read their results before relying on generated software.

The **Files** page previews text files. **Changes** shows file-tool diffs.
**Run history** lets you open a task and continue it with a follow-up message.
**Stop** cancels commands and releases the run during an API request. A late
model response cannot execute further actions. **Undo** restores file-tool edits after checking for
later manual changes. It cannot reverse shell commands or external actions.

## Recover a task without losing work

Temporary API and network failures retry automatically and appear in Run monitor.
If your key or model access needs attention, use **Connection settings**, fix the
connection, and choose **Resume task**. Problems explain **what happened**, **what
it means**, and **what to do next**. Choose **Try fixing it** to continue a repair,
or **Explain this simply** to ask for an explanation without changing files.
Commands and tracebacks are inside **Technical details (optional)**.

For example, **“Expected vocab 36, got 54”** means a test expected 36 text
symbols but the program found 54. It does not prove whether the program or the
test is wrong. The agent should inspect the text data and special symbols first.
It can correct its own mistaken test after reading source evidence and passing
a replacement check; earlier failures stay in **Earlier checks and corrections**.
It must not simply change the expected number to whatever the program returned.

Build mode continues to repair failed checks while evidence changes. If the agent
keeps proposing completion against the same evidence, it saves the work and asks
for help with a simple explanation. It takes another look at relevant source
files before asking. Saved history retains every recorded pass and failure; the
Checks panel shows recent results and corrections. Questions in
Ask mode finish as **Answer ready** instead of waiting for software verification.

After a build, **What works and what is left** shows recorded checks and the
agent's usage instructions. **Not checked yet** means there is no linked check;
**Needs another check** means files changed since that result. A passed check
only establishes the behavior it actually tested. The model's feature-to-check
mapping can still be incomplete, so a green status is not a guarantee.

## Copy, import, download, and monitor

In **Project files**:

- Use **Import files**, **Import folder**, or drag/paste files onto the drop area.
- Select a text file and choose **Copy text**, **Copy path**, **Duplicate**, or
  **Download file**. Binary files support duplication and download.
- Use **Download ZIP** for a project archive, or **Copy to folder** for a new
  device-folder copy. Existing files are preserved, with new names for clashes.
- Use **Open folder** for your normal file manager, including larger transfers.

Open **Run monitor** while a task runs. It shows the current action, elapsed
time, model calls, plan steps, checks, operation history, and live command output.
Runs have unlimited model calls, elapsed time, and total tokens by default. In
**Connect Nemotron → Run and connection settings**, leave cap fields blank or
enter positive values when you want a cap. Commands have no default deadline. **Pause** waits until the current operation finishes before blocking the next
one. **Resume** releases it. **Stop** cancels commands and further actions.
Use **Save report** and **Save log** to keep readable results and recorded events.

**Review each file edit** is enabled for new real tasks. Inspect the proposed
diff and choose Allow once or Deny. This controls agent file-tool edits;
approved shell commands can also write files. Command review remains enabled.

Imports and full-project exports require an idle engine. Transfers support
20 MiB per file and 100 MiB per project export, with up to 3000 exported files.
A browser import selection supports 500 files/100 MiB at a time. Exports exclude
credentials, dependencies, Git internals, and agent history. Command logs are
saved separately, up to 5 MiB per run; use Save log to export up to 20 MiB of
combined task history. Open the device folder for larger copies.

## Practical scope

This version targets modern Windows, macOS, and Linux desktops. It is a local
web app, so its interface uses a browser while Python runs the coding engine.
It is not an Android/iOS app or a hosted service; phones cannot run this engine
independently. The server only listens on the same computer by default.

The agent can work with different languages and project types. Building and
testing them requires their normal SDKs, compilers, dependencies, and any
target hardware. It cannot guarantee every type of software or outperform
other agents without task-specific evaluation.

See **TEST_REPORT.md** for what was exercised and what still needs validation.
