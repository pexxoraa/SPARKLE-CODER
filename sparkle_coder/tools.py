"""Language-independent project tools exposed to the model."""

import json
import difflib

from .execution import CommandRunner
from .state import Session, now
from .workspace import MAX_FILE_BYTES, Redactor, Workspace, WorkspaceError, write_json


def schema(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": list(required), "additionalProperties": False}}}


S = {"type": "string"}
I = {"type": "integer"}
SCHEMAS = [
    schema("list_files", "List project files. Common build, dependency, secret, and state paths are excluded.",
           {"pattern": S, "limit": I}),
    schema("read_file", "Read UTF-8 lines, current full-file sha256, and applicable AGENTS.md instructions.",
           {"path": S, "start_line": I, "max_lines": I}, ["path"]),
    schema("search_files", "Find literal text across project files; use a glob to narrow the search.",
           {"query": S, "pattern": S, "limit": I}, ["query"]),
    schema("write_file", "Create or replace a UTF-8 file. Replacing requires the sha256 returned by read_file.",
           {"path": S, "content": S, "expected_sha256": S}, ["path", "content"]),
    schema("edit_file", "Replace one exact, unique text occurrence; requires the current full-file sha256.",
           {"path": S, "old_text": S, "new_text": S, "expected_sha256": S},
           ["path", "old_text", "new_text", "expected_sha256"]),
    schema("delete_file", "Delete one regular file after reading it; saved file-tool changes can be undone.",
           {"path": S, "expected_sha256": S}, ["path", "expected_sha256"]),
    schema("run_command", "Run a finite foreground terminal command in the workspace. May require user approval. "
           "Use installed toolchains for any language; do not start background servers.",
           {"command": S, "cwd": S, "timeout": I}, ["command"]),
    schema("verify", "Run a build/test/check command and record real evidence with a workspace freshness hash. "
           "Use for meaningful behavioral checks, not echo or a claim that tests pass.",
           {"command": S, "cwd": S, "timeout": I}, ["command"]),
    schema("update_plan", "Maintain a short execution checklist. Preserve the user's task and acceptance criteria.",
           {"steps": {"type": "array", "maxItems": 20, "items": {"type": "object",
             "properties": {"step": S, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}},
             "required": ["step", "status"], "additionalProperties": False}}}, ["steps"]),
    schema("remember", "Save a bounded project fact or decision with its evidence. Never store credentials.",
           {"key": S, "fact": S, "source": S}, ["key", "fact", "source"]),
]


class ToolSet:
    def __init__(self, workspace: Workspace, session: Session, config, approve, should_stop=None,
                 observe=None, checkpoint=None, approve_edit=None):
        self.workspace, self.session = workspace, session
        self.redactor = Redactor((config.api_key,))
        self.observe = lambda kind, data: (observe or (lambda *_: None))(kind, self.redactor.value(data))
        self.checkpoint = checkpoint or (lambda: None)
        self.should_stop = should_stop or (lambda: False)
        self.approve_edit = approve_edit
        self.runner = CommandRunner(workspace, config, approve, should_stop, self.observe, self.checkpoint)

    def mutation_preview(self, name, arguments):
        relative = arguments["path"]
        path = self.workspace.path(relative)
        before, digest = self.workspace.read(relative) if path.exists() else ("", None)
        if path.exists() and arguments.get("expected_sha256") != digest:
            raise ValueError("Stale file hash. Read the file again before proposing a change.")
        if name == "write_file":
            after = arguments["content"]
        elif name == "delete_file":
            after = ""
        else:
            old = arguments["old_text"]
            if not old or before.count(old) != 1:
                raise ValueError("The proposed edit must match one unique occurrence.")
            after = before.replace(old, arguments["new_text"], 1)
        diff = "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                              fromfile="before/" + relative, tofile="after/" + relative, lineterm=""))
        return {"tool": name, "path": relative, "diff": diff[:40000], "truncated": len(diff) > 40000}

    def execute(self, name: str, arguments: dict) -> dict:
        self.checkpoint()
        detail = {"tool": name}
        if isinstance(arguments, dict):
            detail.update({k: str(arguments[k])[:2000] for k in ("path", "command", "query") if k in arguments})
        self.observe("tool_start", detail)
        try:
            self.validate(name, arguments)
            if self.should_stop():
                result = {"ok": False, "cancelled": True, "error": "Stopped before this action."}
            elif self.approve_edit and name in ("write_file", "edit_file", "delete_file") and not self.approve_edit(
                    self.redactor.value(self.mutation_preview(name, arguments))):
                result = {"ok": False, "denied": True, "error": "File edit denied by the user. Do not repeat it or bypass the denial with a command."}
            else:
                result = getattr(self, name)(**arguments)
            result.setdefault("ok", True)
        except (OSError, ValueError, TypeError, UnicodeDecodeError) as exc:
            result = {"ok": False, "error": str(exc)}
        result = self.redactor.value(result)
        details = {"ok": result.get("ok", False)}
        if isinstance(arguments, dict):
            for key in ("path", "command", "query"):
                if key in arguments:
                    details[key] = self.redactor.text(str(arguments[key]))[:600]
        if not result.get("ok"):
            details["error"] = str(result.get("error") or result.get("output") or "Failed")[-1200:]
        self.session.event(name, details)
        self.observe("tool_end", {**detail, **details})
        return result

    @staticmethod
    def validate(name, args):
        definition = next((x["function"] for x in SCHEMAS if x["function"]["name"] == name), None)
        if not definition:
            raise ValueError("Unknown tool.")
        params = definition["parameters"]
        if not isinstance(args, dict) or set(args) - set(params["properties"]):
            raise ValueError("Invalid tool arguments.")
        if set(params["required"]) - set(args):
            raise ValueError("Missing required tool arguments.")
        types = {"string": str, "integer": int, "array": list}
        for key, value in args.items():
            expected = types[params["properties"][key]["type"]]
            if type(value) is not expected:
                raise ValueError(f"{key} must be {expected.__name__}.")

    def list_files(self, pattern="*", limit=300):
        limit = min(1000, max(1, limit))
        files = self.workspace.files(pattern, limit + 1)
        return {"files": files[:limit], "truncated": len(files) > limit}

    def read_file(self, path, start_line=1, max_lines=200):
        text, digest = self.workspace.read(path)
        lines = text.splitlines()
        start_line, max_lines = max(1, start_line), min(400, max(1, max_lines))
        selection = lines[start_line - 1:start_line - 1 + max_lines]
        content = "\n".join(f"{i}: {line}" for i, line in enumerate(selection, start_line))
        return {"path": path, "sha256": digest, "total_lines": len(lines),
                "content": content[:24000], "truncated": len(content) > 24000,
                "instructions": self.workspace.instructions(path)}

    def search_files(self, query, pattern="*", limit=60):
        if not query:
            raise ValueError("Search query must not be empty.")
        matches = []
        limit = min(100, max(1, limit))
        candidates = self.workspace.files(pattern, 2001)
        for relative in candidates[:2000]:
            try:
                text, _ = self.workspace.read(relative)
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if query in line:
                    matches.append({"path": relative, "line": number, "text": line[:500]})
                    if len(matches) >= limit:
                        return {"matches": matches, "truncated": True}
        return {"matches": matches, "truncated": len(candidates) > 2000}

    def write_file(self, path, content, expected_sha256=None):
        data = content.encode("utf-8")
        if len(data) > min(MAX_FILE_BYTES, 200000):
            raise ValueError("Write exceeds 200 KB. Split the implementation into modules.")
        return self.session.mutate(path, data, expected_sha256)

    def edit_file(self, path, old_text, new_text, expected_sha256):
        text, digest = self.workspace.read(path)
        if digest != expected_sha256:
            raise WorkspaceError("Stale file hash. Read the file again.")
        if not old_text or text.count(old_text) != 1:
            raise ValueError("old_text must match exactly one nonempty occurrence.")
        return self.write_file(path, text.replace(old_text, new_text, 1), expected_sha256)

    def delete_file(self, path, expected_sha256):
        return self.session.mutate(path, None, expected_sha256)

    def run_command(self, command, cwd=".", timeout=None):
        return self.runner.run(command, cwd, timeout)

    def verify(self, command, cwd=".", timeout=None, *, trusted=False):
        try:
            result = self.runner.run(command, cwd, timeout, trusted=trusted)
        except (OSError, ValueError) as exc:
            result = {"ok": False, "exit_code": None, "output": str(exc)}
        record = {"at": now(), "command": command, "cwd": cwd, "required": trusted,
                  "exit_code": result.get("exit_code"), "ok": result["ok"],
                  "denied": result.get("denied", False),
                  "fingerprint": self.workspace.fingerprint(),
                  "output": result.get("output", "")[-12000:]}
        self.session.state["checks"].append(self.redactor.value(record))
        self.session.save()
        return result

    def update_plan(self, steps):
        if len(steps) > 20:
            raise ValueError("Use at most 20 plan steps.")
        statuses = ("pending", "in_progress", "completed")
        for step in steps:
            if not isinstance(step, dict) or set(step) != {"step", "status"}:
                raise ValueError("Each step needs only step and status.")
            if not isinstance(step["step"], str) or len(step["step"]) > 500 or step["status"] not in statuses:
                raise ValueError("Invalid plan step.")
        if sum(x["status"] == "in_progress" for x in steps) > 1:
            raise ValueError("Only one plan step may be in progress.")
        self.session.state["plan"] = self.redactor.value(steps)
        return {"plan": steps}

    def memory(self):
        path = self.workspace.state_dir / "memory.json"
        if path.is_symlink():
            raise WorkspaceError("Memory must not be a symlink.")
        return json.loads(path.read_text("utf-8")) if path.exists() else {}

    def remember(self, key, fact, source):
        if len(key) > 80 or len(fact) > 1500 or len(source) > 500:
            raise ValueError("Memory entry is too long.")
        memory = self.memory()
        if len(memory) >= 100 and key not in memory:
            raise ValueError("Project memory is full. Review and remove stale entries manually.")
        memory[key] = self.redactor.value({"fact": fact, "source": source, "updated": now()})
        write_json(self.workspace.state_dir / "memory.json", memory)
        return {"saved": key}
