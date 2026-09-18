# SPARKLE CODER personal workspace roadmap

This is a staged implementation of the agreed feature proposal, using Nemotron
and device-based PROJECTS storage. A feature below is not available until marked
implemented and validated. More application features do not establish better
model reasoning or the ability to build every kind of software.

## Stage 1 — guided, observable work (implemented in 0.6.0)

- Saved project purpose, requirements, and constraints, with snapshots per task.
- Read-only tool and manifest inspection, and a setup help action.
- Completion gates for active checks and the saved requirement checklist.
- Freshness across source changes and environment commands.
- Automatic source/setup review for repeated failures, plus readable repair history.
- Simple and advanced views, with persisted preference.

Automated acceptance: missing requirement evidence prevents completion; a passing
required command cannot hide another failed check; a setup command invalidates
old passes; later brief edits cannot remove a saved task's requirements; setup
inspection never executes project code. Live Nemotron effectiveness remains to
be measured. See TEST_REPORT.md.

## Stage 2 — run and inspect the delivered app (planned)

Managed development servers, live preview, browser interaction tests, screenshots,
visual feedback, and usage walkthroughs. Native software needs target-specific
execution; a web preview cannot validate every software type.

Acceptance: open a generated app, test a real user flow, reproduce a visible
failure, repair it, save evidence, and stop all managed processes reliably.

## Stage 3 — work on larger projects (planned)

An editor with suggestions; GitHub branches, diffs, commits and pull requests;
specialist agents in isolated working copies; combined-result tests; stronger
file checkpoints. Database and external side effects need separate recovery.

Acceptance: independent changes can be integrated without losing user edits;
conflicts and failing checks remain visible; published changes match the reviewed
diff; larger tasks show whether parallel work actually improves time or quality.

## Stage 4 — broader personal workflows (planned)

Document and spreadsheet tools, sourced research, MCP connections and reusable
workflows, queued/scheduled tasks, voice input, and authenticated private remote
access. Background work needs a running device or an optional private server.

Acceptance: artifacts can be opened and used; schedules survive restart; remote
access requires authentication; external actions honor the user's permissions.

## Evaluate each stage

Use the same real project and requirements across versions. Record completed
requirements, defects, manual interventions, elapsed time, and provider token
usage/cost when available. Scripted test providers validate orchestration, not
live coding quality. Run Windows and macOS checks on those systems before
claiming verified platform support. Provider quotas and hardware limits remain.
