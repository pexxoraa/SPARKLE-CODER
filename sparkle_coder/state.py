"""Durable sessions and conflict-aware undo for changes made through file tools."""

from datetime import datetime, timezone
import json
import re
import stat
import uuid

from .workspace import Workspace, WorkspaceError, atomic_write, sha256, write_json
from .verification import identify_checks
from .brief import read_brief, task_requirements


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Session:
    def __init__(self, workspace: Workspace, state: dict):
        self.workspace = workspace
        self.state = state
        identify_checks(state)
        previous = state.get("workspace_root")
        if previous and previous != str(workspace.root):
            state["previous_workspaces"] = list(dict.fromkeys(state.get("previous_workspaces", []) + [previous]))
            state["verification_fingerprint"] = None
        state["workspace_root"] = str(workspace.root)
        self.id = state["id"]
        self.directory = workspace.state_dir / "sessions" / self.id
        for p in (workspace.state_dir / "sessions", self.directory):
            if p.is_symlink():
                raise WorkspaceError("Session directories must not be symlinks.")
            p.mkdir(parents=True, exist_ok=True, mode=0o700)

    @classmethod
    def create(cls, workspace: Workspace, goal: str, verify: list[str], model: dict):
        brief = read_brief(workspace)["brief"]
        session = cls(workspace, {
            "version": 1, "id": uuid.uuid4().hex[:12], "created": now(),
            "goal": goal, "user_requests": [goal], "status": "running", "model": model, "required_checks": verify,
            "messages": [{"role": "user", "content": goal}],
            "plan": [], "actions": [], "journal": [], "checks": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0},
            "summary": "",
            "project_brief": brief, "requirements": task_requirements(brief), "repair_history": [],
        })
        session.save()
        return session

    @classmethod
    def load(cls, workspace: Workspace, session_id: str):
        if not re.fullmatch(r"[a-f0-9]{12}", session_id):
            raise ValueError("Session ID must be the 12-character ID printed by the agent.")
        path = workspace.state_dir / "sessions" / session_id / "state.json"
        if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
            raise WorkspaceError("Session paths must not be symlinks.")
        state = json.loads(path.read_text("utf-8"))
        if state.get("version") != 1 or state.get("id") != session_id:
            raise ValueError("Unsupported or invalid session state.")
        return cls(workspace, state)

    def save(self):
        self.state["updated"] = now()
        path = self.directory / "state.json"
        if path.is_symlink():
            raise WorkspaceError("Session state must not be a symlink.")
        write_json(path, self.state)

    def event(self, name: str, details: dict):
        self.state["actions"].append({"at": now(), "tool": name, **details})
        self.state["actions"] = self.state["actions"][-200:]
        self.save()

    def mutate(self, relative: str, data: bytes | None, expected: str | None):
        self.state["verification_fingerprint"] = None
        path = self.workspace.path(relative)
        exists = path.exists()
        before = path.read_bytes() if exists else None
        if exists and (expected is None or sha256(before) != expected):
            raise WorkspaceError("File changed or hash was omitted. Read the file and retry with its current sha256.")
        if not exists and expected is not None:
            raise WorkspaceError("The expected file no longer exists.")
        if data is None and not exists:
            raise WorkspaceError("Cannot delete a file that does not exist.")
        if before == data:
            return {"path": relative, "sha256": sha256(data) if data is not None else None,
                    "changed": False}
        index = len(self.state["journal"])
        backup = f"before-{index}.bin" if before is not None else None
        mode = stat.S_IMODE(path.stat().st_mode) if exists else 0o644
        if backup:
            atomic_write(self.directory / backup, before, 0o600)
        record = {"path": relative, "before": sha256(before) if before is not None else None,
                  "after": sha256(data) if data is not None else None, "backup": backup,
                  "mode": mode, "applied": False}
        self.state["journal"].append(record)
        self.save()  # If interrupted, undo treats this as uncertain instead of guessing.
        if data is None:
            path.unlink()
        else:
            atomic_write(path, data, mode)
        record["applied"] = True
        self.save()
        return {"path": relative, "sha256": record["after"], "changed": True}

    def repair_interrupted_calls(self):
        """Never automatically replay an action whose completion is unknown."""
        messages = self.state["messages"]
        for i, message in enumerate(list(messages)):
            if message["role"] != "assistant" or not message.get("tool_calls"):
                continue
            following = []
            j = i + 1
            while j < len(messages) and messages[j]["role"] == "tool":
                following.append(messages[j].get("tool_call_id"))
                j += 1
            missing = [c for c in message["tool_calls"] if c["id"] not in following]
            if missing:
                if j != len(messages):
                    raise ValueError("Invalid saved tool-call ordering; inspect session state.")
                for call in missing:
                    messages.append({"role": "tool", "tool_call_id": call["id"],
                                     "content": json.dumps({"ok": False, "error":
                                         "Interrupted before the result was saved. The action may "
                                         "have run. Inspect current files/state before retrying."})})
        self.save()

    def undo_preview(self) -> list[dict]:
        if self.state.get("undone"):
            raise WorkspaceError("This session's file edits have already been undone.")
        records = self.state["journal"]
        if any(not r["applied"] for r in records):
            raise WorkspaceError("A file change was interrupted; inspect it manually before undo.")
        first, last = {}, {}
        for r in records:
            first.setdefault(r["path"], r)
            last[r["path"]] = r
        result = []
        for relative, final in last.items():
            path = self.workspace.path(relative)
            current = sha256(path.read_bytes()) if path.exists() else None
            if current != final["after"]:
                raise WorkspaceError(f"Undo refused: {relative} has later changes. Preserve or reconcile them first.")
            original = first[relative]
            if original["backup"]:
                backup = self.directory / original["backup"]
                if backup.is_symlink() or sha256(backup.read_bytes()) != original["before"]:
                    raise WorkspaceError("Undo backup is missing or was modified.")
            result.append(original)
        return result

    def undo(self) -> list[str]:
        records = self.undo_preview()  # Check every conflict before making any change.
        restored = []
        for record in records:
            path = self.workspace.path(record["path"])
            if record["backup"]:
                atomic_write(path, (self.directory / record["backup"]).read_bytes(), record["mode"])
            else:
                path.unlink(missing_ok=True)
            restored.append(record["path"])
        self.state["undone"] = True
        self.state["status"] = "undone"
        self.state["verification_fingerprint"] = None
        self.save()
        return restored
