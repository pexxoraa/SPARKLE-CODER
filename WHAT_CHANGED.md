# SPARKLE CODER 0.3.1 — files, supervision, device storage

Version 0.3.1 renames the app, package, browser branding, icon and launchers to
SPARKLE CODER. Existing device data is detected automatically. The file transfer
and monitoring improvements from 0.3 are retained.

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
| End a run | Stop | Cancels commands and prevents subsequent actions; model requests may finish first |
| Keep evidence | Save report / Save log | Downloads summaries/checks and persistent JSONL activity |
| Choose where data lives | Device storage | Copies managed data to an empty device folder and remembers the choice |

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
