import json
from pathlib import Path
import tempfile
import unittest

from sparkle_coder.agent import Agent
from sparkle_coder.config import Config
from sparkle_coder.demo import DemoProvider, calls, python_command
from sparkle_coder.provider import Completion
from sparkle_coder.state import Session
from sparkle_coder.workspace import Workspace


class SequenceProvider:
    def __init__(self, sequence):
        self.sequence = iter(sequence)

    def complete(self, messages, schemas):
        return next(self.sequence)


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Workspace(Path(self.tmp.name))
        self.config = Config(auto_approve=True, max_steps=12)

    def agent(self, provider, verify=None):
        session = Session.create(self.workspace, "Build the requested program", verify or [], {})
        return Agent(self.workspace, session, self.config, provider, lambda _: True, lambda _: None)

    def test_failing_acceptance_forces_repair_before_completion(self):
        check = python_command("-m", "unittest", "discover", "-s", "tests", "-v")
        agent = self.agent(DemoProvider(), [check])
        self.assertEqual(agent.run(), "checked")
        checks = agent.session.state["checks"]
        self.assertEqual([c["ok"] for c in checks], [False, True])
        self.assertIn("return a + b", (self.workspace.root / "calculator.py").read_text())
        self.assertTrue((agent.session.directory / "report.md").exists())

    def test_final_claim_cannot_bypass_failed_acceptance(self):
        provider = SequenceProvider([Completion("Everything works perfectly.", [], {}) for _ in range(3)])
        agent = self.agent(provider, [python_command("-c", "raise SystemExit(9)")])
        self.assertEqual(agent.run(), "blocked")
        self.assertEqual(len(agent.session.state["checks"]), 3)
        self.assertTrue(all(c["exit_code"] == 9 for c in agent.session.state["checks"]))

    def test_no_checks_means_unverified(self):
        provider = SequenceProvider([Completion("Done.", [], {}), Completion("Done.", [], {})])
        self.assertEqual(self.agent(provider).run(), "unverified")

    def test_checks_are_stale_after_a_file_change(self):
        agent = self.agent(SequenceProvider([]))
        written = agent.tools.execute("write_file", {"path": "code.py", "content": "value = 1\n"})
        checked = agent.tools.execute("verify", {"command": python_command("-c", "import code; assert code.value == 1")})
        self.assertTrue(checked["ok"])
        self.assertTrue(agent.verify_completion()[0])
        agent.tools.execute("write_file", {"path": "code.py", "content": "value = 2\n",
                                           "expected_sha256": written["sha256"]})
        self.assertFalse(agent.verify_completion()[0])

    def test_call_budget_pauses_and_keeps_work(self):
        agent = self.agent(SequenceProvider([
            calls(("write_file", {"path": "saved.go", "content": "package main\n"}))]))
        agent.config.max_steps = 1
        self.assertEqual(agent.run(), "paused")
        restored = Session.load(self.workspace, agent.session.id)
        self.assertEqual(restored.state["status"], "paused")
        self.assertTrue((self.workspace.root / "saved.go").exists())

    def test_resume_marks_unknown_command_without_replaying(self):
        agent = self.agent(SequenceProvider([]))
        call = calls(("run_command", {"command": "touch must-not-run"})).calls[0]
        agent.session.state["messages"].append({"role": "assistant", "content": "", "tool_calls": [call]})
        agent.session.save()
        restored = Session.load(self.workspace, agent.session.id)
        restored.repair_interrupted_calls()
        result = restored.state["messages"][-1]
        self.assertEqual(result["role"], "tool")
        self.assertEqual(result["tool_call_id"], call["id"])
        self.assertIn("may have run", result["content"])
        self.assertFalse((self.workspace.root / "must-not-run").exists())

    def test_context_trims_whole_tool_exchanges_and_preserves_correction(self):
        agent = self.agent(SequenceProvider([]))
        agent.config.context_chars = 18000
        state = agent.session.state
        state["user_requests"].append("Do not change the payment API.")
        for i in range(12):
            call = calls(("list_files", {})).calls[0]
            call["id"] = f"call_{i}"
            state["messages"] += [
                {"role": "assistant", "content": "", "tool_calls": [call]},
                {"role": "tool", "tool_call_id": call["id"], "content": "x" * 6000}]
        context = agent.context()
        self.assertLessEqual(len(json.dumps(context)), agent.config.context_chars)
        self.assertIn("Do not change the payment API.", json.dumps(context))
        known_ids = set()
        for message in context:
            if message["role"] == "assistant":
                known_ids.update(c["id"] for c in message.get("tool_calls", []))
            if message["role"] == "tool":
                self.assertIn(message["tool_call_id"], known_ids)
        self.assertEqual(context[-1]["tool_call_id"], "call_11")

    def test_truncated_generation_cannot_execute_a_partial_action(self):
        response = calls(("write_file", {"path": "bad.py", "content": "partial"}))
        response.finish_reason = "length"
        agent = self.agent(SequenceProvider([response]))
        agent.config.max_steps = 1
        self.assertEqual(agent.run(), "paused")
        self.assertFalse((self.workspace.root / "bad.py").exists())

    def test_agent_cannot_invoke_internal_python_methods_as_tools(self):
        agent = self.agent(SequenceProvider([]))
        result = agent.tools.execute("memory", {})
        self.assertFalse(result["ok"])
