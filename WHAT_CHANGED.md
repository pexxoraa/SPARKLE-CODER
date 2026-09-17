# SPARKLE CODER 0.5.0 — simple explanations and PROJECTS

The recovery screen explains what happened, what it means and the next action.
Commands and tracebacks are collapsed under optional details. **Try fixing it**
continues a repair; **Explain this simply** asks for a read-only explanation.
Command approval also shows its purpose, when supplied by the agent, with the
exact command available for inspection.

The reported “Expected vocab 36, got 54” incident has a dedicated explanation:
the test expected 36 text symbols and the program produced 54. The count alone
does not establish which is wrong. The agent now receives instructions to
inspect training data, normalization and special symbols, and to split independent
checks instead of stopping all testing at the first assertion.

A new **revise_check** tool handles mistaken agent-created checks. It requires
existing check IDs, a current source file read, its matching hash, a reason, and
a passing replacement command. Earlier failures remain in history. Required
commands and discovered project commands cannot be retired with this tool.
This records evidence and accountability; it does not formally prove that the
agent's reasoning or replacement test is correct.

**What works and what is left** provides a result explanation, usage steps,
limitations and feature checks. The runtime derives check status from recorded
results and file freshness. The feature-to-check mapping is authored by the
model and may be incomplete. Untested features stay marked as untested.

Default storage is now **PROJECTS** and **APP_DATA** inside the SPARKLE CODER
application folder. Managed projects and saved tasks from older app data are
copied automatically on the first default launch. Originals remain as backups;
externally registered projects stay in place. Partial migration failures do not
commit new settings, and existing destination projects are never overwritten.
Checks that name the old project location cannot accidentally test the backup.

Quit the old app before upgrading. Use a writable app folder, and preserve
**PROJECTS** and **APP_DATA** when updating program files in future. Open **Device
storage → Open PROJECTS folder** to find the actual project location.

A simple offline to-do list is now the first starter suggestion. API keys still
go in **Connect Nemotron → API key → Test connection → Save connection**. Keys
stay in memory until the engine quits. Runs retain the unlimited defaults and
optional user caps introduced earlier.

These additions address opaque failures, mistaken tests and unclear completion.
They have not been benchmarked against other agents and are not claimed to be
exclusive inventions. See **TEST_REPORT.md** for validation and remaining limits.

## Retained from 0.4.0 — repairs and resumable work

This update removes premature completion cutoffs, adds automatic check discovery,
and continues repairs while the code or check evidence changes. The agent now
requests a specific next step when it actually needs help. Failures remain visible.

Build/Ask modes separate implementation from read-only project questions.
Temporary API/network failures retry with visible progress. Slow model requests
can be stopped without waiting for their response to execute any actions.

Connect Nemotron now includes **Show**/**Remove configured key**, connection
status that survives saving, optional API timeouts and **Remove all run caps**.
Commands have no default deadline. Existing standard two-minute command settings
migrate to unlimited; custom caps remain editable. The app cannot change provider
context/output limits, rate limits or account quota.

Large tool output is compacted only in the model request; full saved history stays
on the device. Large projects can now have current content-based verification.
The same failing command can run again after a repair. Denied commands do not
keep requesting approval in one run, but can be retried after you resume.

## Earlier improvements

Version 0.3.1 renamed the app, package, browser branding, icon and launchers to
SPARKLE CODER. Existing device data is detected automatically. The file transfer
and monitoring improvements from 0.3 are retained.

Version 0.3.2 removes the default model-call, elapsed-time, and total-token run
caps. Leave the optional cap fields blank for an open-ended run; use **Stop** to
end it yourself. API keys are entered in **Connect Nemotron → API key** and
remain memory-only.

| Need | Control | Behavior |
| --- | --- | --- |
| Bring files from your device | Project files → Import files / Import folder | Preserves folder paths; duplicate names create new copies |
| Paste or drop files | Project files drop area | Imports browser-supported clipboard/drop files |
| Copy generated code | Copy code on chat blocks; Copy text on a selected file | Copies to the system clipboard, with a browser fallback |
| Copy a file inside the project | Duplicate | Preserves the original and refuses to overwrite an existing file |
| Download a file | Download file | Transfers exact bytes, including supported binary assets |
| Download completed software | Download ZIP | Includes project source and build outputs, excluding credentials/dependencies/state |
| Copy into a device folder | Copy to folder | Creates a new folder without overwriting an existing project |
| Inspect what is happening | Run monitor | Shows model requests, tools, paths, commands, results, elapsed time and real emitted output |
| Review edits before they happen | Review each file edit | Shows file-tool diffs for one-use approval |
| Pause work | Pause / Resume | Holds the next action after the current operation finishes |
| End a run | Stop | Stops the local run promptly; an already submitted provider request may finish remotely |
| Keep evidence | Save report / Save log | Downloads summaries/checks and persistent JSONL activity |
| Choose where data lives | Device storage | Copies managed data to an empty device folder and remembers the choice |
| Configure model access | Connect Nemotron | Paste a hosted NVIDIA key in **API key**; the value is cleared when the app quits |
| Keep a task running | Connect Nemotron → Remove all run caps | Clears model-call, elapsed-time, total-token and command-duration caps; Save connection applies it |

File-tool approval and undo do not cover changes made by an approved shell
command. Commands remain individually reviewable. No tool can guarantee that
generated software is correct solely because a model says it is finished.

Transfers are bounded to 20 MiB per file; ZIP/folder project exports support
100 MiB and 3000 files. Browser import selections support 500 files/100 MiB.
Files above these limits can be copied in your file manager using Open folder.
The live window retains recent events; saved logs hold up to 5 MiB per run,
and Save log supports up to 20 MiB of combined task logs. A report includes
up to 200 recent events. Command programs may buffer output before emitting it.

## First check after upgrading

1. Quit the previous app, extract this version, and open its launcher.
2. Run the offline demo and inspect Run monitor and the recorded checks.
3. Import a small file, duplicate it, and download it again. Confirm the contents.
4. Choose an empty device data folder. Quit and reopen the app; confirm your
   project and history remain available.
5. Connect your Nemotron endpoint, run a small task with edit review enabled,
   and exercise Pause, Resume, and one file-edit approval.

Automated behavior is tested on Linux. Windows/macOS launch, visual browser
interaction, clipboard/file-manager integration, and live Nemotron generation
still require checks on your machine. No comparative benchmark against other
coding agents has been run; this release adds concrete control and visibility.
