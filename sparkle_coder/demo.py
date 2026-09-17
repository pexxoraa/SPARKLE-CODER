"""Deterministic offline integration demo. This is not a model benchmark."""

import json
from pathlib import Path
import os
import shlex
import subprocess
import sys

from .agent import Agent
from .config import Config
from .provider import Completion
from .state import Session
from .workspace import Workspace


def python_command(*args):
    parts = [sys.executable, *args]
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def calls(*items):
    return Completion("", [{"id": f"demo_{i}", "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments)}} for i, (name, arguments) in enumerate(items)],
        {"prompt_tokens": 0, "completion_tokens": 0}, "tool_calls")


class DemoProvider:
    def __init__(self):
        self.phase = 0

    def complete(self, messages, schemas):
        phase, self.phase = self.phase, self.phase + 1
        if phase == 0:
            return calls(("update_plan", {"steps": [
                {"step": "Implement calculator and independent tests", "status": "in_progress"},
                {"step": "Run checks and repair failures", "status": "pending"}]}))
        if phase == 1:
            return calls(
                ("write_file", {"path": "calculator.py", "content":
                    'def add(a, b):\n    return a - b\n\n\nif __name__ == "__main__":\n    print(add(2, 3))\n'}),
                ("write_file", {"path": "tests/test_calculator.py", "content":
                    "import unittest\nfrom calculator import add\n\n"
                    "class CalculatorTests(unittest.TestCase):\n"
                    "    def test_positive(self):\n        self.assertEqual(add(2, 3), 5)\n"
                    "    def test_negative(self):\n        self.assertEqual(add(-4, 1), -3)\n"
                    "    def test_zero(self):\n        self.assertEqual(add(0, 0), 0)\n"}))
        if phase == 2:
            return Completion("The calculator and tests are ready for acceptance checks.", [], {})
        if phase == 3:
            return calls(("read_file", {"path": "calculator.py"}))
        if phase == 4:
            result = next(json.loads(m["content"]) for m in reversed(messages)
                          if m["role"] == "tool" and '"sha256"' in m["content"])
            return calls(("edit_file", {"path": "calculator.py", "old_text": "return a - b",
                                        "new_text": "return a + b", "expected_sha256": result["sha256"]}))
        if phase == 5:
            return calls(("update_plan", {"steps": [
                {"step": "Implement calculator and independent tests", "status": "completed"},
                {"step": "Run checks and repair failures", "status": "completed"}]}))
        return Completion("Offline demo repaired the deliberate arithmetic bug. "
                          "The real acceptance runner now checks the repaired files.", [], {})


def run_demo(root: Path, emit=print):
    root = root.expanduser().resolve()
    if root.exists() and any(p.name != ".nemotron" for p in root.iterdir()):
        raise ValueError("The demo needs an empty destination; choose a new --workspace.")
    workspace = Workspace(root)
    config = Config(model="OFFLINE-SCRIPTED-DEMO", auto_approve=True, max_steps=12)
    check = python_command("-m", "unittest", "discover", "-s", "tests", "-v")
    emit("OFFLINE DEMO: scripted responses, real file edits and test execution; no API calls.")
    with workspace.lock():
        session = Session.create(workspace, "Create and verify a small calculator.", [check], config.public_info())
        status = Agent(workspace, session, config, DemoProvider(), lambda _: True, emit=emit).run()
    return 0 if status == "checked" else 2
