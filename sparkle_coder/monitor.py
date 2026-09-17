"""Observable background work, bounded persistent logs, approvals and pause gates."""

import json
import os
import threading
import time
import uuid

from .state import now
from .workspace import Redactor, clean_terminal


ACTIVE = ("queued", "running", "approval", "pausing", "paused_by_user", "stopping")


class Run:
    def __init__(self, project_id, mode, key=""):
        self.id = uuid.uuid4().hex[:12]
        self.project_id, self.mode = project_id, mode
        self.session_id = None
        self.status = "queued"
        self.events = []
        self.sequence = 0
        self.lock = threading.RLock()
        self.stop, self.decision, self.pause_requested = threading.Event(), threading.Event(), threading.Event()
        self.approval = None
        self.approved = False
        self.thread = None
        self.error = None
        self.started = time.monotonic()
        self.created = now()
        self.finished = None
        self.current_action = "Starting task"
        self.log_path = None
        self.log_bytes = 0
        self.log_truncated = False
        self.redactor = Redactor((key,))

    def bind(self, session):
        self.session_id = session.id
        self.log_path = session.directory / ("run-" + self.id + ".jsonl")
        if self.log_path.exists() or self.log_path.is_symlink():
            raise ValueError("Run log already exists.")

    def record(self, kind, data=None):
        data = self.redactor.value(data or {})
        with self.lock:
            self.sequence += 1
            event = {"sequence": self.sequence, "at": now(), "kind": kind,
                     "elapsed": round(time.monotonic() - self.started, 1), **data}
            if "text" in event:
                event["text"] = clean_terminal(event["text"])
            if kind == "model_start":
                self.current_action = "Waiting for Nemotron response"
            elif kind == "model_retry":
                self.current_action = f"Reconnecting in {data['delay']}s · attempt {data['attempt']} · {data['reason']}"
            elif kind == "verification_start":
                self.current_action = "Checking: " + data["command"]
            elif kind == "repair":
                self.current_action = "Diagnosing check failures and continuing repairs"
            elif kind == "tool_start":
                self.current_action = data.get("tool", "Tool") + ": " + str(data.get("path") or data.get("command") or "project")
            elif kind == "command_start":
                self.current_action = "Running: " + data["command"]
            elif kind in ("command_end", "tool_end", "model_end"):
                self.current_action = "Processing the result"
            self.events.append(event)
            self.events = self.events[-600:]
            if self.log_path and not self.log_truncated:
                line = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
                self.log_bytes += len(line)
                if self.log_bytes > 5 * 1024 * 1024:
                    self.log_truncated = True
                    line = json.dumps({"kind": "log_limit", "at": now(),
                                       "text": "Run log reached 5 MiB. Later events remain in the live window only."}).encode() + b"\n"
                if self.log_path.is_symlink():
                    raise ValueError("Run log must not be a symlink.")
                fd = os.open(self.log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
                with os.fdopen(fd, "ab") as stream:
                    stream.write(line)

    def emit(self, text):
        self.record("message", {"text": text})

    def checkpoint(self):
        if not self.pause_requested.is_set() or self.stop.is_set():
            return
        with self.lock:
            self.status = "paused_by_user"
            self.current_action = "Paused before the next action"
            self.record("paused", {"text": "Paused. Resume to allow the next action."})
        while self.pause_requested.is_set() and not self.stop.wait(0.1):
            pass
        with self.lock:
            self.status = "stopping" if self.stop.is_set() else "running"
            if not self.stop.is_set():
                self.record("resumed", {"text": "Resumed by you."})

    def pause(self):
        with self.lock:
            if self.status not in ACTIVE or self.stop.is_set():
                raise ValueError("Only an active task can be paused.")
            self.pause_requested.set()
            if self.status != "approval":
                self.status = "pausing"
            self.record("pause_requested", {"text": "Pause requested. The current operation may finish first."})

    def resume(self):
        with self.lock:
            if not self.pause_requested.is_set() or self.stop.is_set():
                raise ValueError("This task is not waiting to resume.")
            self.pause_requested.clear()
            if self.status != "approval":
                self.status = "running"

    def request_approval(self, request):
        self.checkpoint()
        if self.stop.is_set():
            return False
        with self.lock:
            self.decision.clear()
            self.approved = False
            self.approval = {"id": uuid.uuid4().hex[:12], **self.redactor.value(request)}
            self.status = "approval"
            self.current_action = "Waiting for your " + request["kind"] + " approval"
            self.record("approval_requested", {"text": self.current_action,
                                                "path": request.get("path"), "command": request.get("command")})
        while not self.decision.wait(0.1):
            if self.stop.is_set():
                break
        with self.lock:
            accepted = self.approved and not self.stop.is_set()
            self.approval = None
            self.status = "stopping" if self.stop.is_set() else "running"
        self.checkpoint()
        return accepted and not self.stop.is_set()

    def approve(self, command):
        return self.request_approval({"kind": "command", "command": clean_terminal(command)})

    def approve_edit(self, request):
        return self.request_approval({"kind": "file edit", **request})

    def answer(self, approval_id, allowed):
        with self.lock:
            if not self.approval or self.approval["id"] != approval_id or self.decision.is_set():
                raise ValueError("This approval is no longer pending.")
            if type(allowed) is not bool:
                raise ValueError("Approval must be true or false.")
            self.approved = allowed
            self.record("approval_decision", {"text": "Allowed by you." if allowed else "Denied by you.", "allowed": allowed})
            self.decision.set()

    def cancel(self):
        with self.lock:
            if self.status not in ACTIVE:
                return
            self.stop.set()
            self.status = "stopping"
            self.current_action = "Stopping current work"
            self.record("stop_requested", {"text": "Stop requested by you."})
            self.decision.set()

    def finish(self, status, summary=""):
        with self.lock:
            self.status = status
            self.finished = time.monotonic()
            self.current_action = {"needs_input": "Work saved · ready for your next step", "answered": "Answer ready",
                                   "checked": "Checks passed", "interrupted": "Stopped · work saved"}.get(status, "Task finished: " + status)
            self.record("finished", {"text": self.current_action, "status": status, "summary": summary[:4000]})

    def public(self, after=0):
        with self.lock:
            return {"id": self.id, "project_id": self.project_id, "session_id": self.session_id,
                    "mode": self.mode, "status": self.status, "approval": self.approval,
                    "events": [e for e in self.events if e["sequence"] > after], "error": self.error,
                    "created": self.created, "elapsed_seconds": round((self.finished or time.monotonic()) - self.started, 1),
                    "current_action": self.current_action, "pause_requested": self.pause_requested.is_set(),
                    "last_activity": self.events[-1]["at"] if self.events else self.created,
                    "events_truncated": bool(self.events and after and after < self.events[0]["sequence"] - 1),
                    "log_truncated": self.log_truncated}


def session_events(session, limit=200):
    events = []
    for path in sorted(session.directory.glob("run-*.jsonl"), key=lambda p: p.stat().st_mtime):
        if path.is_symlink():
            continue
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
                if len(events) > limit:
                    del events[:len(events) - limit]
    return events
