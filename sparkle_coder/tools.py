"""Language-independent project tools exposed to the model."""

import json
import difflib
import re
import uuid

from .checks import discover_checks
from .diagnostics import inspect_setup
from .explanations import check_title, explain_failure
from .execution import CommandRunner
from .state import Session, now
from .workspace import MAX_FILE_BYTES, Redactor, Workspace, WorkspaceError, write_json
from .verification import check_key, identify_checks, replacements


def schema(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": list(required), "additionalProperties": False}}}


S = {"type": "string"}
I = {"type": "integer"}
SCHEMAS = [
    schema("inspect_static_site", "Check plain HTML structure, links and local assets without running commands. Does not test rendered appearance or JavaScript behavior.", {"entry": S}, []),
    schema("inspect_setup", "Inspect project manifests and locate development tools without executing code. "
           "Use to investigate missing dependencies; this is not a verification pass.", {}),
    schema("discover_checks", "Find existing test, typecheck, lint and build commands. Does not execute them.", {}),
    schema("request_input", "Ask the user for a specific missing decision, credential setup, or unavailable dependency "
           "only after useful work is exhausted. Include the exact next step; work will be saved.",
           {"question": S, "next_step": S}, ["question", "next_step"]),
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
           {"command": S, "cwd": S, "timeout": I, "purpose": S}, ["command"]),
    schema("verify", "Run a build/test/check command and record real evidence with a workspace freshness hash. "
           "Use for meaningful behavioral checks, not echo or a claim that tests pass.",
           {"command": S, "cwd": S, "timeout": I, "label": S}, ["command"]),
    schema("revise_check", "Correct an agent-authored check whose assumption is demonstrably wrong. "
           "First read the evidence file. Explain the reason and preserve the behavior being tested. "
           "The old checks are superseded only after the replacement actually passes. User-required and "
           "project-discovered checks cannot be replaced. Never replace a check just to hide a failure.",
           {"check_ids": {"type": "array", "items": S}, "command": S, "cwd": S, "label": S,
            "reason": S, "evidence_path": S, "expected_sha256": S},
           ["check_ids", "command", "label", "reason", "evidence_path", "expected_sha256"]),
    schema("update_delivery", "Explain the delivered result for a person with no programming background. "
           "Give simple steps to use it and honest limitations. Link each feature to actual verify check IDs; "
           "the runtime derives pass/fail status, not your prose. An empty check_ids list means not checked.",
           {"summary": S, "how_to_use": {"type": "array", "items": S},
            "limitations": {"type": "array", "items": S}, "features": {"type": "array", "items": {
                "type": "object", "properties": {"feature": S, "check_ids": {"type": "array", "items": S},
                    "requirement_ids": {"type": "array", "items": S,
                        "description": "IDs from the user-owned requirements checkpoint covered by this feature."}},
                "required": ["feature", "check_ids"], "additionalProperties": False}}},
           ["summary", "how_to_use", "limitations", "features"]),
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
            if self.session.state.get("task_mode") == "ask" and name not in READ_ONLY_TOOLS:
                result = {"ok": False, "error": "Ask mode only allows project inspection. Switch to Build to edit files or run commands."}
            elif self.should_stop():
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
            for key in ("path", "command", "query", "label", "purpose"):
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

    def discover_checks(self):
        return discover_checks(self.workspace, self.runner.config.execution)

    def inspect_setup(self):
        report = inspect_setup(self.workspace, self.runner.config)
        self.session.state["setup"] = self.redactor.value(report)
        return report

    def request_input(self, question, next_step):
        if not question.strip() or not next_step.strip():
            raise ValueError("Give a specific question and a next step.")
        self.session.state["input_request"] = {"question": question[:2000], "next_step": next_step[:2000]}
        return {"waiting_for_user": True, "question": question, "next_step": next_step}

    def read_file(self, path, start_line=1, max_lines=200):
        text, digest = self.workspace.read(path)
        lines = text.splitlines()
        start_line, max_lines = max(1, start_line), min(400, max(1, max_lines))
        selection = lines[start_line - 1:start_line - 1 + max_lines]
        content = "\n".join(f"{i}: {line}" for i, line in enumerate(selection, start_line))
        reads = self.session.state.setdefault("read_evidence", {})
        reads[path] = digest
        if len(reads) > 200:
            del reads[next(iter(reads))]
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

    def run_command(self, command, cwd=".", timeout=None, purpose=""):
        if purpose:
            self.observe("action_context", {"command": command, "purpose": purpose[:800]})
        result = self.runner.run(command, cwd, timeout)
        if result.get("exit_code") is not None:
            self.session.state["verification_fingerprint"] = None
            self.session.state["environment_revision"] = self.session.state.get("environment_revision", 0) + 1
        return result

    def verify(self, command, cwd=".", timeout=None, label="", *, trusted=False, source=None):
        label = label[:160] or check_title(command)
        self.observe("action_context", {"command": command, "purpose": "Check: " + label})
        try:
            if any(previous != str(self.workspace.root) and previous in command
                   for previous in self.session.state.get("previous_workspaces", [])):
                raise ValueError("This check still points to a previous project folder. Use the current project folder or relative paths so the backup copy is not tested by mistake.")
            result = self.runner.run(command, cwd, timeout, trusted=trusted)
        except (OSError, ValueError) as exc:
            result = {"ok": False, "exit_code": None, "output": str(exc)}
        if re.search(r"\bRan 0 tests\b", result.get("output", "")):
            result["ok"] = False
            result["output"] += "\nNo tests were collected. Inspect the test path and run the actual suite."
        record = {"id": "check-" + uuid.uuid4().hex[:12], "key": check_key(command, cwd),
                  "label": label, "source": source or ("user" if trusted else "agent"),
                  "at": now(), "command": command, "cwd": cwd, "required": trusted,
                  "exit_code": result.get("exit_code"), "ok": result["ok"],
                  "denied": result.get("denied", False),
                  "cancelled": result.get("cancelled", False),
                  "timed_out": result.get("timed_out", False),
                  "fingerprint": self.workspace.fingerprint(),
                  "environment_revision": self.session.state.get("environment_revision", 0),
                  "output": result.get("output", "")[-12000:]}
        self.session.state["checks"].append(self.redactor.value(record))
        self.session.state["verification_fingerprint"] = record["fingerprint"]
        self.session.save()
        result.update(check_id=record["id"], label=label)
        if not result["ok"]:
            result["explanation"] = self.redactor.value(explain_failure(record))
        return result

    def inspect_static_site(self, entry="index.html"):
        from .static_checks import inspect_site
        result = inspect_site(self.workspace, entry)
        command = "builtin:static-site " + entry
        record = {"id": "check-" + uuid.uuid4().hex[:12], "key": check_key(command),
                  "label": "Static page structure and links", "source": "builtin", "at": now(),
                  "command": command, "cwd": ".", "required": False, "ok": result["ok"],
                  "exit_code": result["exit_code"], "fingerprint": self.workspace.fingerprint(),
                  "environment_revision": self.session.state.get("environment_revision", 0),
                  "output": result["output"]}
        self.session.state["checks"].append(record)
        self.session.state["verification_fingerprint"] = record["fingerprint"]
        self.session.save()
        return {**result, "check_id": record["id"], "label": record["label"]}

    def revise_check(self, check_ids, command, label, reason, evidence_path, expected_sha256, cwd="."):
        if not check_ids or len(check_ids) > 20 or not all(isinstance(x, str) for x in check_ids):
            raise ValueError("Name the existing check IDs to correct.")
        if not 20 <= len(reason.strip()) <= 2000:
            raise ValueError("Explain which assumption was wrong, what proves it, and which behavior the replacement still checks.")
        state = self.session.state
        identify_checks(state)
        by_id = {c["id"]: c for c in state["checks"]}
        if any(identity not in by_id for identity in check_ids):
            raise ValueError("A check ID was not found in this task.")
        old = [by_id[identity] for identity in check_ids]
        discovered = {check_key(c["command"], c["cwd"]) for c in self.discover_checks()["checks"]}
        for check in old:
            if (check.get("required") or check["command"] in state["required_checks"]
                    or check["source"] != "agent" or check["key"] in discovered):
                raise ValueError("User-required and existing project checks cannot be replaced. Repair the code or ask the user about a conflicting requirement.")
        _, digest = self.workspace.read(evidence_path)
        if digest != expected_sha256 or state.get("read_evidence", {}).get(evidence_path) != digest:
            raise ValueError("Read the current evidence file before correcting the check, and use its exact sha256.")
        old_keys = list(dict.fromkeys(c["key"] for c in old))
        new_key = check_key(command, cwd)
        retired = replacements(state)
        if new_key in old_keys or new_key in retired or any(key in retired for key in old_keys):
            raise ValueError("Use active checks and a genuinely corrected replacement command.")
        result = self.verify(command, cwd, label=label)
        if not result["ok"]:
            return {**result, "superseded": False,
                    "next_step": "The replacement did not pass. Fix the remaining failure, then call revise_check again. The original evidence is retained."}
        # The evidence file may have changed during the command. Do not silently
        # attach an outdated explanation to a correction.
        if self.workspace.read(evidence_path)[1] != digest:
            return {"ok": False, "check_id": result["check_id"], "superseded": False,
                    "error": "The evidence file changed during the replacement check. Read it again and review the explanation."}
        revision = self.redactor.value({"at": now(), "old_ids": check_ids, "old_keys": old_keys,
            "new_id": result["check_id"], "new_key": new_key, "reason": reason,
            "evidence_path": evidence_path, "evidence_sha256": digest, "label": label[:160]})
        state.setdefault("check_revisions", []).append(revision)
        self.session.save()
        self.observe("check_revised", {"text": reason, "path": evidence_path, "label": label[:160]})
        return {**result, "superseded": True, "replaced_check_ids": check_ids,
                "note": "The corrected check passed. Earlier results and the reason for correction remain in the history."}

    def update_delivery(self, summary, how_to_use, limitations, features):
        if not summary.strip() or len(summary) > 2000:
            raise ValueError("Give a short explanation of what was built.")
        for values in (how_to_use, limitations):
            if len(values) > 12 or any(not isinstance(x, str) or not x.strip() or len(x) > 600 for x in values):
                raise ValueError("Use up to 12 short, plain-language items.")
        identify_checks(self.session.state)
        known = {c["id"] for c in self.session.state["checks"]}
        requirements = {item["id"] for item in self.session.state.get("requirements", [])}
        if len(features) > 20:
            raise ValueError("Summarize up to 20 features.")
        for item in features:
            if (not isinstance(item, dict) or not {"feature", "check_ids"} <= set(item)
                    or set(item) - {"feature", "check_ids", "requirement_ids"}
                    or not isinstance(item["feature"], str) or not 1 <= len(item["feature"]) <= 300
                    or not isinstance(item["check_ids"], list)
                    or len(item["check_ids"]) > 40
                    or any(not isinstance(key, str) or key not in known for key in item["check_ids"])
                    or not isinstance(item.get("requirement_ids", []), list)
                    or len(item.get("requirement_ids", [])) > 20
                    or any(not isinstance(key, str) or key not in requirements for key in item.get("requirement_ids", []))):
                raise ValueError("Each feature needs plain text and existing check IDs, or an empty list if not tested.")
        self.session.state["delivery"] = self.redactor.value({"summary": summary, "how_to_use": how_to_use,
                                                             "limitations": limitations, "features": features})
        return {"saved": True, "note": "Feature status is derived from recorded checks and freshness, not from claimed completion."}

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


READ_ONLY_TOOLS = {"list_files", "read_file", "search_files", "discover_checks", "inspect_setup", "request_input", "update_plan"}
