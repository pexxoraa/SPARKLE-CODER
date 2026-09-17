"""Terminal interface for a personal Nemotron coding agent."""

import argparse
import json
from pathlib import Path
import shutil
import sys

from . import __version__
from .agent import Agent
from .config import CONFIG_TEMPLATE, load_config
from .provider import ModelError, NemotronClient
from .state import Session
from .workspace import Redactor, Workspace, atomic_write, clean_terminal


EXIT_CODES = {"checked": 0, "paused": 2, "blocked": 2, "unverified": 3, "interrupted": 130}


def approve(command: str) -> bool:
    print("\nCommand awaiting approval:\n" + clean_terminal(command))
    if not sys.stdin.isatty():
        print("Noninteractive input: denied. Explicitly use --auto-approve for trusted automation.")
        return False
    try:
        return input("Run this command? [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def add_workspace(parser):
    parser.add_argument("--workspace", "-w", default=".", help="Project directory to create or work in")


def add_runtime(parser):
    add_workspace(parser)
    parser.add_argument("--model", help="Exact Nemotron model ID exposed by your endpoint")
    parser.add_argument("--base-url", help="OpenAI-compatible API base URL, including /v1")
    parser.add_argument("--tool-format", choices=("native", "json"))
    parser.add_argument("--execution", choices=("local", "docker"))
    parser.add_argument("--auto-approve", action="store_true", default=None,
                        help="Approve all model-generated shell commands for this invocation")
    parser.add_argument("--max-steps", type=int, help="Optional model-call cap; omit for unlimited")
    parser.add_argument("--max-seconds", type=int, help="Optional elapsed-time cap; omit for unlimited")
    parser.add_argument("--max-total-tokens", type=int,
                        help="Optional total token cap; omit for unlimited")
    parser.add_argument("--max-tokens", type=int, help="Maximum output tokens per model response")


def parser():
    p = argparse.ArgumentParser(prog="sparkle-coder",
        description="Personal Nemotron coding agent: inspect, edit, run, repair, and verify.")
    p.add_argument("--version", action="version", version=__version__)
    commands = p.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create configuration and project guidance")
    add_workspace(init)
    run = commands.add_parser("run", help="Execute a software task")
    add_runtime(run)
    run.add_argument("goal", help="Concrete task and acceptance criteria")
    run.add_argument("--verify", action="append", help="Required acceptance command; repeat for multiple checks")
    resume = commands.add_parser("resume", help="Continue saved work without replaying uncertain actions")
    add_runtime(resume)
    resume.add_argument("session")
    resume.add_argument("--message", help="Additional instructions or answer to a blocking question")
    resume.add_argument("--verify", action="append", help="Add a required check; existing checks remain")
    chat = commands.add_parser("chat", help="Interactive task conversation")
    add_runtime(chat)
    chat.add_argument("--verify", action="append")
    sessions = commands.add_parser("sessions", help="List this project's saved runs")
    add_workspace(sessions)
    report = commands.add_parser("report", help="Print a saved run report")
    add_workspace(report)
    report.add_argument("session")
    undo = commands.add_parser("undo", help="Undo this session's file-tool edits if there are no conflicts")
    add_workspace(undo)
    undo.add_argument("session")
    undo.add_argument("--yes", action="store_true", help="Apply the displayed rollback without a prompt")
    undo.add_argument("--dry-run", action="store_true", help="Check conflicts and list files without changing them")
    doctor = commands.add_parser("doctor", help="Inspect configuration and installed toolchains")
    add_runtime(doctor)
    doctor.add_argument("--connect", action="store_true", help="Check API access via GET /models")
    models = commands.add_parser("models", help="List Nemotron model IDs served by the configured endpoint")
    add_runtime(models)
    models.add_argument("--all", action="store_true")
    demo = commands.add_parser("demo", help="Offline scripted plumbing test; does NOT use a real model")
    demo.add_argument("--workspace", "-w", default="./nemotron-demo", help="Empty destination for the offline demo")
    return p


def runtime_config(args, workspace):
    names = ("model", "base_url", "tool_format", "execution", "auto_approve",
             "max_steps", "max_seconds", "max_total_tokens", "max_tokens")
    return load_config(workspace.root, {name: getattr(args, name, None) for name in names})


def show_doctor(workspace, config):
    print(f"SPARKLE CODER {__version__} | Python {sys.version.split()[0]}")
    print("Workspace:", workspace.root)
    print("Endpoint:", config.base_url)
    print("Model:", config.model)
    print(f"API credential: {'configured' if config.api_key else 'not set'} ({config.api_key_env})")
    print("Execution:", config.execution)
    print("Shell approval:", "automatic" if config.auto_approve else "per command")
    for executable in ("git", "rg", "python3", "node", "npm", "go", "cargo", "rustc",
                       "java", "javac", "dotnet", "cc", "cmake", "docker", "xcodebuild", "adb"):
        print(f"  {executable:12} {'available' if shutil.which(executable) else 'not installed'}")
    print("Only installed toolchains can run locally. Writing another language needs no plugin.")


def init(workspace):
    config = workspace.root / "nemotron.toml"
    if config.exists() or config.is_symlink():
        raise ValueError("nemotron.toml already exists; edit it directly.")
    atomic_write(config, CONFIG_TEMPLATE.encode(), 0o600)
    guide = workspace.root / "AGENTS.md"
    if not guide.exists() and not guide.is_symlink():
        atomic_write(guide, (
            "# Project instructions\n\n"
            "- Keep implementations complete and maintainable.\n"
            "- Preserve existing behavior outside the requested change.\n"
            "- Read nested AGENTS.md files before editing their directories.\n"
            "- Run meaningful tests and report any unverified requirements.\n"
            "- Prefer file tools for edits so they can be reviewed and undone.\n"
            "- Do not commit, push, or deploy unless explicitly requested.\n\n"
            "Add this project's architecture, conventions, and test commands here.\n"
        ).encode(), 0o644)
    ignored = workspace.root / ".gitignore"
    if ignored.is_symlink():
        raise ValueError("Refusing to update a symlinked .gitignore.")
    text = ignored.read_text("utf-8") if ignored.exists() else ""
    additions = [line for line in (".nemotron/", ".env", "nemotron.toml")
                 if line not in text.splitlines()]
    if additions:
        atomic_write(ignored, (text.rstrip() + "\n" + "\n".join(additions) + "\n").lstrip("\n").encode(), 0o644)
    print("Project configured:", workspace.root)
    print("Set NVIDIA_API_KEY locally, then run a concrete task with --verify.")
    return 0


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "demo":
            from .demo import run_demo
            return run_demo(Path(args.workspace))
        workspace = Workspace(Path(args.workspace))
        if args.command == "init":
            with workspace.lock():
                return init(workspace)
        if args.command == "sessions":
            directory = workspace.state_dir / "sessions"
            if directory.is_symlink():
                raise ValueError("Session directory must not be a symlink.")
            for path in sorted(directory.glob("*/state.json"), key=lambda x: x.stat().st_mtime, reverse=True):
                session = Session.load(workspace, path.parent.name)
                state = session.state
                print(clean_terminal(f"{session.id}  {state['status']:12}  {state['updated']}  {state['goal'][:90]}"))
            return 0
        if args.command == "report":
            session = Session.load(workspace, args.session)
            path = session.directory / "report.md"
            if path.is_symlink():
                raise ValueError("Report must not be a symlink.")
            if not path.exists():
                print("No report yet. Session status:", session.state["status"])
            else:
                print(clean_terminal(path.read_text("utf-8")))
            return 0
        if args.command == "undo":
            with workspace.lock():
                session = Session.load(workspace, args.session)
                preview = session.undo_preview()
                print("File-tool rollback:", ", ".join(r["path"] for r in preview) or "(no changes)")
                print("Shell commands and external side effects are not undone.")
                if args.dry_run:
                    return 0
                if not args.yes and not approve("Apply the file rollback listed above"):
                    return 2
                print("Restored:", ", ".join(session.undo()))
                return 0
        config = runtime_config(args, workspace)
        provider = NemotronClient(config)
        if args.command == "doctor":
            show_doctor(workspace, config)
            if args.connect:
                config.require_credentials()
                available = provider.models()
                print("Endpoint reachable. Requested model:", "listed" if config.model in available else "not listed")
                return 0 if config.model in available else 2
            return 0
        if args.command == "models":
            config.require_credentials()
            ids = provider.models()
            for model in ids:
                if args.all or "nemotron" in model.lower():
                    print(clean_terminal(model))
            return 0
        config.require_credentials()
        redactor = Redactor((config.api_key,))
        if config.execution == "local":
            print("Local shell commands run with your OS permissions; this is not an OS sandbox.")
        with workspace.lock():
            if args.command == "resume":
                session = Session.load(workspace, args.session)
                if session.state.get("undone"):
                    raise ValueError("An undone session cannot be resumed; start a new task.")
                session.repair_interrupted_calls()
                if args.message:
                    message = redactor.text(args.message)
                    session.state["messages"].append({"role": "user", "content": message})
                    session.state.setdefault("user_requests", [session.state["goal"]]).append(message)
                for check in args.verify or []:
                    if check not in session.state["required_checks"]:
                        session.state["required_checks"].append(check)
                session.state["model"] = config.public_info()
            elif args.command == "run":
                if len(args.goal) > 12000:
                    raise ValueError("Task exceeds 12000 characters; put supporting details in a project file.")
                session = Session.create(workspace, redactor.text(args.goal),
                                         args.verify if args.verify is not None else config.verify,
                                         config.public_info())
            else:  # Interactive chat.
                session = None
                while True:
                    try:
                        goal = input("\nTask (/quit to exit): ").strip()
                    except (EOFError, KeyboardInterrupt):
                        break
                    if goal in ("/quit", "/exit"):
                        break
                    if not goal:
                        continue
                    goal = redactor.text(goal)
                    if session is None:
                        session = Session.create(workspace, goal, args.verify or config.verify, config.public_info())
                    else:
                        session.repair_interrupted_calls()
                        session.state["messages"].append({"role": "user", "content": goal})
                        session.state.setdefault("user_requests", [session.state["goal"]]).append(goal)
                    Agent(workspace, session, config, provider, approve).run()
                return 0
            status = Agent(workspace, session, config, provider, approve).run()
            return EXIT_CODES[status]
    except (OSError, ValueError, ModelError) as exc:
        print("Error: " + clean_terminal(Redactor().text(str(exc))), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
