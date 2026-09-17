"""Application state and background runs for the local graphical workspace."""

import difflib
import json
import os
from pathlib import Path
import re
import threading
import uuid
from urllib.parse import urlsplit

from . import __version__
from .agent import Agent
from .config import Config, load_config
from .demo import DemoProvider, calls, python_command
from .provider import NemotronClient
from .monitor import Run, ACTIVE, session_events
from .files import UserFiles
from .storage import resolve_storage, relocate
from .state import Session, now
from .workspace import Redactor, Workspace, clean_terminal, write_json


def default_app_dir() -> Path:
    if os.name == "nt":
        parent = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        current, legacy = parent / "SparkleCoder", parent / "NemotronWorkspace"
    elif os.sys.platform == "darwin":
        parent = Path.home() / "Library" / "Application Support"
        current, legacy = parent / "SparkleCoder", parent / "NemotronWorkspace"
    else:
        parent = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        current, legacy = parent / "sparkle-coder", parent / "nemotron-workspace"
    # Reuse previous installs so a product rename cannot hide projects or history.
    for directory in (current, legacy):
        if any((directory / name).exists() for name in ("settings.json", "storage-location.json", "instance.json")):
            return directory
    return current


SETTINGS = ("base_url", "model", "tool_format", "execution", "max_steps", "max_tokens",
            "request_timeout", "command_timeout")


class BrowserDemo:
    """Scripted model; one real command deliberately requests browser approval."""
    def __init__(self):
        self.inner = DemoProvider()
        self.offered_command = False

    def complete(self, messages, schemas):
        if self.inner.phase == 2 and not self.offered_command:
            self.offered_command = True
            # Parse without generating a timestamp-based .pyc: rapid same-size edits
            # in this demo must not reuse bytecode from the deliberately broken file.
            script = "import ast; from pathlib import Path; ast.parse(Path('calculator.py').read_text()); print('Syntax check passed')"
            return calls(("run_command", {"command": python_command("-c", script)}))
        return self.inner.complete(messages, schemas)


class AppService:
    def __init__(self, directory: Path, provider_factory=NemotronClient):
        self.bootstrap = directory.expanduser().resolve()
        self.directory = resolve_storage(self.bootstrap)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.settings_path = self.directory / "settings.json"
        if self.settings_path.is_symlink():
            raise ValueError("Application settings must not be a symlink.")
        defaults = {key: getattr(Config(), key) for key in SETTINGS}
        self.data = {"settings": defaults, "projects": [], "selected_project": None}
        if self.settings_path.exists():
            saved = json.loads(self.settings_path.read_text("utf-8"))
            self.data["settings"].update({k: v for k, v in saved.get("settings", {}).items() if k in SETTINGS})
            self.data["projects"] = saved.get("projects", [])
            self.data["selected_project"] = saved.get("selected_project")
        self.lock = threading.RLock()
        self.keys = {}
        self.connected_endpoint = None
        self.jobs = {}
        self.provider_factory = provider_factory
        if not self.data["projects"]:
            self.add_project("My project", str(self.directory / "Projects" / "my-project"))

    def save(self):
        # Deliberately excludes API keys and run access tokens.
        with self.lock:
            write_json(self.settings_path, self.data)

    def config(self, workspace=None):
        with self.lock:
            selected = dict(self.data["settings"])
            config = load_config(workspace.root, selected) if workspace else Config(**selected)
            config.auto_approve = False
            endpoint = config.base_url.rstrip("/")
            if endpoint in self.keys:
                config._runtime_api_key = self.keys[endpoint]
            elif urlsplit(endpoint).hostname != "integrate.api.nvidia.com":
                config._runtime_api_key = os.environ.get("LOCAL_MODEL_API_KEY", "")
            if urlsplit(endpoint).hostname != "integrate.api.nvidia.com" and config.extra_body == Config().extra_body:
                config.extra_body = {}
            config.validate()
            return config

    def public_settings(self):
        config = self.config()
        return {**self.data["settings"], "key_configured": bool(config.api_key),
                "connected": self.connected_endpoint == (config.base_url, config.model)}

    def configure(self, payload):
        if not isinstance(payload, dict) or set(payload) - set(SETTINGS) - {"api_key", "clear_key"}:
            raise ValueError("Invalid settings.")
        with self.lock:
            candidate = {**self.data["settings"], **{k: v for k, v in payload.items() if k in SETTINGS}}
            candidate["base_url"] = candidate["base_url"].rstrip("/")
            config = Config(**candidate)
            config.validate()
            key = payload.get("api_key", "")
            if not isinstance(key, str) or len(key) > 2000 or any(c in key for c in "\r\n"):
                raise ValueError("Invalid API key.")
            if payload.get("clear_key"):
                self.keys[config.base_url] = ""
            elif key:
                self.keys[config.base_url] = key.strip()
            self.data["settings"] = candidate
            self.connected_endpoint = None
            self.save()
            return self.public_settings()

    def connect(self):
        config = self.config()
        config.require_credentials()
        available = self.provider_factory(config).models()
        if config.model not in available:
            return {"connected": False, "models": available,
                    "message": "Endpoint reached, but this model ID was not listed. Choose a served model."}
        self.connected_endpoint = (config.base_url, config.model)
        return {"connected": True, "models": available, "message": "Nemotron is connected."}

    def add_project(self, name="", path=""):
        if not isinstance(name, str) or not isinstance(path, str) or len(name) > 100 or len(path) > 2000:
            raise ValueError("Invalid project name or path.")
        name = name.strip() or "Untitled project"
        if not path.strip():
            slug = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-") or "project"
            path = str(self.directory / "Projects" / (slug + "-" + uuid.uuid4().hex[:6]))
        root = Path(path).expanduser()
        if not root.is_absolute():
            raise ValueError("Use an absolute project folder path, or leave it blank to create a project.")
        workspace = Workspace(root)
        with self.lock:
            existing = next((p for p in self.data["projects"] if p["path"] == str(workspace.root)), None)
            if existing:
                self.data["selected_project"] = existing["id"]
                self.save()
                return existing
            project = {"id": uuid.uuid4().hex[:12], "name": name, "path": str(workspace.root), "created": now()}
            self.data["projects"].append(project)
            self.data["selected_project"] = project["id"]
            self.save()
            return project

    def project(self, project_id):
        with self.lock:
            project = next((p for p in self.data["projects"] if p["id"] == project_id), None)
            if not project:
                raise ValueError("Project not found.")
            return project, Workspace(Path(project["path"]))

    def active(self):
        with self.lock:
            return next((job for job in self.jobs.values()
                         if job.status in ACTIVE), None)

    def state(self):
        with self.lock:
            job = self.active()
            return {"version": __version__, "projects": list(self.data["projects"]),
                    "selected_project": self.data["selected_project"],
                    "settings": self.public_settings(), "active_run": job.public() if job else None,
                    "storage": {"path": str(self.directory), "projects_path": str(self.directory / "Projects")}}

    def snapshot(self, project_id, session_id, include_events=True):
        _, workspace = self.project(project_id)
        session = Session.load(workspace, session_id)
        state = session.state
        user_requests = set(state.get("user_requests", [state["goal"]]))
        messages = [{"role": m["role"], "content": m["content"]}
                    for m in state["messages"]
                    if m.get("content") and (m["role"] == "assistant"
                                            or m["role"] == "user" and m["content"] in user_requests)]
        return {key: state.get(key) for key in
                ("id", "goal", "status", "created", "updated", "plan", "usage", "summary", "model", "undone")} | {
            "messages": messages, "actions": state["actions"][-100:], "checks": state["checks"][-40:],
            "changed_files": sorted({r["path"] for r in state["journal"]}),
            "required_checks": state["required_checks"],
            "events": session_events(session) if include_events else [],
        }

    def history(self, project_id):
        _, workspace = self.project(project_id)
        directory = workspace.state_dir / "sessions"
        if directory.is_symlink():
            raise ValueError("Session directory must not be a symlink.")
        result = []
        for path in directory.glob("*/state.json"):
            try:
                state = Session.load(workspace, path.parent.name).state
                result.append({k: state.get(k) for k in ("id", "goal", "status", "created", "updated", "undone")})
            except (OSError, ValueError):
                continue
        return sorted(result, key=lambda x: x["updated"], reverse=True)[:100]

    def changes(self, project_id, session_id):
        _, workspace = self.project(project_id)
        session = Session.load(workspace, session_id)
        first = {}
        for record in session.state["journal"]:
            first.setdefault(record["path"], record)
        changes = []
        for name, record in first.items():
            before = ""
            if record["backup"]:
                if not re.fullmatch(r"before-\d+\.bin", record["backup"]):
                    raise ValueError("Invalid backup entry.")
                backup = session.directory / record["backup"]
                if backup.is_symlink():
                    raise ValueError("Backup must not be a symlink.")
                before = backup.read_bytes()[:200000].decode("utf-8", errors="replace")
            path = workspace.path(name)
            after = path.read_bytes()[:200000].decode("utf-8", errors="replace") if path.exists() else ""
            lines = list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                             fromfile="before/" + name, tofile="after/" + name, lineterm=""))
            changes.append({"path": name, "added": sum(l.startswith("+") and not l.startswith("+++") for l in lines),
                            "removed": sum(l.startswith("-") and not l.startswith("---") for l in lines),
                            "diff": "\n".join(lines)[:40000], "truncated": len("\n".join(lines)) > 40000})
        return Redactor((self.config().api_key,)).value(changes)

    def start(self, project_id, goal, verify=None, session_id=None, demo=False, review_edits=False):
        if type(review_edits) is not bool:
            raise ValueError("Review edits must be true or false.")
        if not isinstance(goal, str) or len(goal) > 12000 or not goal.strip() and not session_id:
            raise ValueError("Describe a task using 1–12000 characters.")
        verify = verify or []
        if not isinstance(verify, list) or len(verify) > 20 or any(
                not isinstance(c, str) or not c.strip() or len(c) > 10000 for c in verify):
            raise ValueError("Use at most 20 nonempty verification commands.")
        _, workspace = self.project(project_id)
        config = self.config(workspace)
        if demo:
            config.model = "OFFLINE-SCRIPTED-DEMO"
            config.execution = "local"
            config.max_steps = 15
            verify = [python_command("-m", "unittest", "discover", "-s", "tests", "-v")]
        else:
            config.require_credentials()
        goal = Redactor((config.api_key,)).text(goal)
        with self.lock:
            if self.active():
                raise ValueError("A task is already running. Stop it or wait before starting another.")
            job = Run(project_id, "demo" if demo else "nemotron", config.api_key)
            self.jobs[job.id] = job
            self.data["selected_project"] = project_id
            self.save()

            def work():
                try:
                    with workspace.lock():
                        if session_id:
                            session = Session.load(workspace, session_id)
                            if session.state.get("undone"):
                                raise ValueError("This task was undone. Start a new task.")
                            session.repair_interrupted_calls()
                            if goal.strip():
                                session.state["messages"].append({"role": "user", "content": goal})
                                session.state.setdefault("user_requests", [session.state["goal"]]).append(goal)
                            session.state["required_checks"] = list(dict.fromkeys(session.state["required_checks"] + verify))
                            session.state["model"] = config.public_info()
                            session.save()
                        else:
                            session = Session.create(workspace, goal, verify, config.public_info())
                        with job.lock:
                            job.bind(session)
                            job.status = "running"
                        provider = BrowserDemo() if demo else self.provider_factory(config)
                        status = Agent(workspace, session, config, provider, job.approve,
                                       emit=job.emit, should_stop=job.stop.is_set, observe=job.record,
                                       checkpoint=job.checkpoint,
                                       approve_edit=job.approve_edit if review_edits else None).run()
                        with job.lock:
                            job.finish(status, session.state.get("summary", ""))
                except Exception as exc:
                    with job.lock:
                        job.error = clean_terminal(Redactor((config.api_key,)).text(str(exc)))
                        job.emit(job.error)
                        job.finish("blocked", job.error)

            job.thread = threading.Thread(target=work, name="nemotron-task", daemon=True)
            job.thread.start()
            for old_id in list(self.jobs):
                if len(self.jobs) <= 30:
                    break
                if self.jobs[old_id] is not job and not self.jobs[old_id].thread.is_alive():
                    del self.jobs[old_id]
            return job.public()

    def demo(self):
        with self.lock:
            if self.active():
                raise ValueError("Finish or stop the current task before running the demo.")
            project = self.add_project("Demo · calculator", "")
            job = self.start(project["id"], "Build a calculator and verify its behavior.", demo=True)
            return {"project": project, "run": job}

    def job(self, run_id):
        with self.lock:
            if run_id not in self.jobs:
                raise ValueError("Run not found. Its saved session is still available in history.")
            return self.jobs[run_id]

    def file_action(self, project_id, operation, body=None):
        body = body or {}
        with self.lock:
            if self.active():
                raise ValueError("Finish or stop the active task before importing, copying or exporting a project.")
            project, workspace = self.project(project_id)
            files = UserFiles(workspace.root)
            with workspace.lock():
                if operation == "import":
                    return files.import_file(body.get("path"), body.get("data"))
                if operation == "duplicate":
                    return files.duplicate(body.get("source"), body.get("destination"))
                if operation == "export-folder":
                    return files.export_folder(body.get("path"), project["name"])
                if operation == "download-project":
                    return files.archive()
                raise ValueError("Unknown file operation.")

    def storage(self, path):
        with self.lock:
            if self.active():
                raise ValueError("Finish or stop the active task before switching data folders.")
            return relocate(self, path)

    def export_report(self, project_id, session_id):
        snapshot = self.snapshot(project_id, session_id)
        lines = ["# Task report", "", snapshot["goal"], "", "Status: " + snapshot["status"], "",
                 snapshot.get("summary") or "Task has not finished.", "", "## File-tool changes", ""]
        lines += ["- " + path for path in snapshot["changed_files"]]
        lines += ["", "## Checks", ""]
        for check in snapshot["checks"]:
            lines += [("PASS" if check["ok"] else "FAIL") + ": " + check["command"], "", check.get("output", ""), ""]
        lines += ["## Recent activity", "", "The recent activity excerpt contains up to 200 events.", ""]
        for event in snapshot["events"]:
            lines.append(event.get("at", "") + " " + event.get("kind", "") + " " +
                         str(event.get("text") or event.get("output") or event.get("command") or event.get("path") or ""))
        return Redactor(tuple(self.keys.values())).text("\n".join(lines)).encode("utf-8")

    def export_logs(self, project_id, session_id):
        _, workspace = self.project(project_id)
        session = Session.load(workspace, session_id)
        chunks, total = [], 0
        for path in sorted(session.directory.glob("run-*.jsonl"), key=lambda p: p.stat().st_mtime):
            if path.is_symlink():
                raise ValueError("Run logs must not be symlinks.")
            data = path.read_bytes()
            total += len(data)
            if total > 20 * 1024 * 1024:
                raise ValueError("Logs exceed 20 MiB. Open the project folder to copy its session logs directly.")
            chunks.append(data)
        return Redactor(tuple(self.keys.values())).text(b"".join(chunks).decode("utf-8")).encode("utf-8")

    def undo(self, project_id, session_id, apply=False):
        with self.lock:
            if self.active():
                raise ValueError("Stop the running task before undoing files.")
            _, workspace = self.project(project_id)
            with workspace.lock():
                session = Session.load(workspace, session_id)
                paths = [r["path"] for r in session.undo_preview()]
                if apply:
                    session.undo()
                return {"paths": paths, "applied": apply}

    def close(self):
        pending = [job for job in list(self.jobs.values()) if job.thread and job.thread.is_alive()]
        for job in pending:
            job.cancel()
        # Give foreground commands time to terminate before the GUI process exits.
        # In-flight model requests cannot execute actions once cancellation is set.
        for job in pending:
            if job.thread is not threading.current_thread():
                job.thread.join(timeout=3)
        self.keys.clear()
