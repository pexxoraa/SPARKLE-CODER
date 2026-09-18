import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sparkle_coder.agent import Agent
from sparkle_coder.brief import read_brief, save_brief
from sparkle_coder.checks import discover_checks
from sparkle_coder.config import Config
from sparkle_coder.demo import calls, python_command
from sparkle_coder.diagnostics import inspect_setup
from sparkle_coder.provider import Completion
from sparkle_coder.state import Session
from sparkle_coder.verification import proof_summary
from sparkle_coder.webapp import AppService
from sparkle_coder.workspace import Workspace, WorkspaceError
from test_agent import SequenceProvider
import test_web


BRIEF = {"purpose": "A small personal calculator", "requirements": ["Add two numbers", "Preserve existing files"],
         "constraints": "Explain the result in simple words."}


class GuidedWorkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Workspace(Path(self.tmp.name))
        self.config = Config(base_url="http://127.0.0.1:9000/v1")

    def agent(self, required=(), responses=()):
        session = Session.create(self.workspace, "Build a calculator", list(required), {})
        return Agent(self.workspace, session, self.config, SequenceProvider(responses), lambda _: True, emit=lambda _: None)

    def test_brief_conflicts_do_not_overwrite_another_window(self):
        first = save_brief(self.workspace, BRIEF, None)
        with self.assertRaisesRegex(ValueError, "another window"):
            save_brief(self.workspace, {**BRIEF, "requirements": []}, None)
        self.assertEqual(read_brief(self.workspace), first)

    def test_saved_task_keeps_requirements_after_project_brief_changes(self):
        previous = save_brief(self.workspace, BRIEF, None)
        session = self.agent().session
        save_brief(self.workspace, {**BRIEF, "requirements": ["An entirely different task"]}, previous["revision"])
        restored = Session.load(self.workspace, session.id)
        self.assertEqual([item["text"] for item in restored.state["requirements"]], BRIEF["requirements"])
        self.assertEqual(self.agent().session.state["requirements"][0]["text"], "An entirely different task")

    def test_invalid_or_symlinked_brief_is_rejected(self):
        with self.assertRaises(ValueError):
            save_brief(self.workspace, {**BRIEF, "requirements": ["x" * 301]}, None)
        target = self.workspace.root / "untouched.json"
        target.write_text(json.dumps(BRIEF))
        (self.workspace.state_dir / "brief.json").symlink_to(target)
        with self.assertRaises(WorkspaceError):
            read_brief(self.workspace)
        self.assertEqual(json.loads(target.read_text()), BRIEF)

    def test_requirement_status_needs_current_linked_evidence(self):
        save_brief(self.workspace, BRIEF, None)
        agent = self.agent()
        result = agent.tools.verify(python_command("-c", "assert 2 + 2 == 4"))
        identity = result["check_id"]
        requirements = agent.session.state["requirements"]
        self.assertFalse(agent.verify_completion()[0])
        agent.tools.update_delivery("Calculator checks", ["Open the project"], [], [{"feature": "Add numbers",
            "check_ids": [identity], "requirement_ids": [requirements[0]["id"]]}])
        proof = proof_summary(agent.session.state)
        self.assertEqual([item["status"] for item in proof["requirements"]], ["passed", "not_checked"])
        self.assertFalse(agent.verify_completion()[0])
        agent.tools.update_delivery("Calculator checks", ["Open the project"], [], [{"feature": "Observed behaviors",
            "check_ids": [identity], "requirement_ids": [item["id"] for item in requirements]}])
        self.assertTrue(agent.verify_completion()[0])
        agent.tools.write_file("changed.py", "value = 3\n")
        self.assertEqual(proof_summary(agent.session.state)["requirements"][0]["status"], "needs_recheck")

    def test_agent_cannot_invent_requirement_or_check_ids(self):
        save_brief(self.workspace, BRIEF, None)
        agent = self.agent()
        for feature in ({"feature": "Invented", "check_ids": ["nonexistent"]},
                        {"feature": "Invented", "check_ids": [], "requirement_ids": ["nonexistent"]}):
            result = agent.tools.execute("update_delivery", {"summary": "Done", "how_to_use": [],
                                         "limitations": [], "features": [feature]})
            self.assertFalse(result["ok"])
        self.assertEqual([item["text"] for item in agent.session.state["requirements"]], BRIEF["requirements"])

    def test_passing_required_command_cannot_mask_another_active_failure(self):
        agent = self.agent([python_command("-c", "assert 2 + 2 == 4")])
        agent.tools.verify(python_command("-c", "assert False, 'Broken feature'"))
        passed, _ = agent.verify_completion()
        self.assertFalse(passed)
        self.assertEqual(proof_summary(agent.session.state)["failed"], 1)

    def test_environment_command_invalidates_previously_passing_checks(self):
        agent = self.agent()
        command = python_command("-c", "from pathlib import Path; assert not Path('node_modules/changed').exists()")
        agent.tools.verify(command)
        self.assertTrue(agent.verify_completion()[0])
        agent.tools.run_command(python_command("-c", "from pathlib import Path; Path('node_modules').mkdir(); Path('node_modules/changed').touch()"))
        self.assertEqual(proof_summary(agent.session.state)["needs_recheck"], 1)
        self.assertFalse(agent.verify_completion()[0])
        self.assertEqual([check["ok"] for check in agent.session.state["checks"]], [True, False])

    def test_passing_required_command_cannot_skip_discovered_project_tests(self):
        (self.workspace.root / "test_behavior.py").write_text(
            "import unittest\nclass Broken(unittest.TestCase):\n def test_behavior(self): self.assertEqual(1, 2)\n")
        agent = self.agent([python_command("-c", "assert 1 == 1")])
        self.assertFalse(agent.verify_completion()[0])
        self.assertTrue(any(check.get("source") == "discovered" and not check["ok"] for check in agent.session.state["checks"]))

    def test_repeated_failed_check_records_a_source_and_setup_review_once(self):
        (self.workspace.root / "calculator.py").write_text("def add(a, b):\n    return a - b\n")
        command = python_command("-c", "from calculator import add; assert add(2, 3) == 5")
        responses = [calls(("verify", {"command": command})) for _ in range(3)]
        responses.extend([Completion("Done", [], {}) for _ in range(4)])
        agent = self.agent(responses=responses)
        self.assertEqual(agent.run(), "needs_input")
        history = agent.session.state["repair_history"]
        self.assertEqual(len(history), 1)
        self.assertIn("calculator.py", history[0]["files"])
        self.assertEqual(history[0]["kind"], "expectation")
        self.assertNotIn("Traceback", agent.session.state["summary"])
        self.assertIn("project_overview", json.dumps(agent.context()))

    def test_inspection_does_not_execute_project_code_or_count_as_a_pass(self):
        (self.workspace.root / "package.json").write_text(json.dumps({"packageManager": "pnpm@10.0.0",
            "scripts": {"postinstall": "touch MUST_NOT_EXIST", "test": "node test.js"}}))
        (self.workspace.root / "yarn.lock").touch()
        with patch("subprocess.Popen", side_effect=AssertionError("No process may run")), \
                patch("sparkle_coder.diagnostics.shutil.which", return_value=None):
            report = inspect_setup(self.workspace, self.config)
        self.assertFalse((self.workspace.root / "MUST_NOT_EXIST").exists())
        self.assertTrue(any(item["id"] == "tool:pnpm" and item["status"] == "attention" for item in report["items"]))
        self.assertEqual(report["checks"][0]["command"], "pnpm run test")
        self.assertEqual(discover_checks(self.workspace)["checks"], report["checks"])
        agent = self.agent()
        agent.tools.execute("inspect_setup", {})
        self.assertEqual(proof_summary(agent.session.state)["total"], 0)

    def test_docker_report_does_not_mistake_host_tools_for_container_tools(self):
        (self.workspace.root / "Cargo.toml").write_text('[package]\nname = "sample"\n')
        self.config.execution = "docker"
        with patch("sparkle_coder.diagnostics.shutil.which", return_value="/usr/bin/found"):
            report = inspect_setup(self.workspace, self.config)
        self.assertFalse(any(item["id"] == "tool:cargo" for item in report["items"]))
        container = next(item for item in report["items"] if item["id"] == "container-tools")
        self.assertEqual(container["status"], "info")

    def test_scan_ignores_secrets_and_symlinks_and_handles_broken_manifest(self):
        (self.workspace.root / ".env").write_text("SECRET=do-not-read")
        (self.workspace.root / "package.json").write_text("[")
        outside = self.workspace.state_dir / "private.py"
        outside.write_text("DO_NOT_INCLUDE")
        (self.workspace.root / "linked.py").symlink_to(outside)
        report = inspect_setup(self.workspace, self.config)
        self.assertEqual(report["overview"]["file_count"], 1)
        self.assertNotIn("DO_NOT_INCLUDE", json.dumps(report))
        self.assertTrue(any(item["id"] == "manifest:package.json" for item in report["items"]))

    def test_guided_build_must_link_evidence_before_completion(self):
        save_brief(self.workspace, {**BRIEF, "requirements": ["Add two numbers"]}, None)
        session = self.agent().session
        class Provider:
            phase = 0
            missing_seen = False
            def complete(inner, messages, schemas):
                phase = inner.phase
                inner.phase += 1
                if phase == 0:
                    return calls(("write_file", {"path": "calculator.py", "content": "def add(a, b):\n    return a + b\n"}))
                if phase == 1:
                    return calls(("verify", {"command": python_command("-c", "from calculator import add; assert add(2, 3) == 5")}))
                if phase == 2:
                    return Completion("Done", [], {})
                if phase == 3:
                    inner.missing_seen = any("requirements still lack" in item.get("content", "") for item in messages)
                    return calls(("update_delivery", {"summary": "A working addition function", "how_to_use": ["Open calculator.py"],
                        "limitations": [], "features": [{"feature": "Add two numbers", "check_ids": [session.state["checks"][-1]["id"]],
                                                         "requirement_ids": [session.state["requirements"][0]["id"]]}]}))
                return Completion("The addition check passed.", [], {})
        provider = Provider()
        agent = Agent(self.workspace, session, self.config, provider, lambda _: True, emit=lambda _: None)
        self.assertEqual(agent.run(), "checked")
        self.assertTrue(provider.missing_seen)
        self.assertEqual(proof_summary(session.state)["requirements_passed"], 1)
        self.assertIn("Your requirements", (session.directory / "report.md").read_text())


class GuidedWebTests(unittest.TestCase):
    setUp = test_web.WebTests.setUp
    close = test_web.WebTests.close
    request = test_web.WebTests.request
    api = test_web.WebTests.api

    def test_brief_endpoints_preserve_conflicts_and_redact_known_keys(self):
        project = self.app.data["selected_project"]
        path = "/api/projects/" + project + "/brief"
        key = "nvidia-private-test-key-12345"
        self.api("/api/settings", {"api_key": key})
        result = self.api(path, {"revision": None, "brief": {**BRIEF, "constraints": "Do not store " + key}})
        self.assertNotIn(key, json.dumps(result))
        status, _, _ = self.request(path, {"revision": None, "brief": BRIEF})
        self.assertEqual(status, 400)
        self.assertEqual(self.api(path)["revision"], result["revision"])
        status, _, _ = self.request(path, auth=False)
        self.assertEqual(status, 401)

    def test_setup_is_authenticated_read_only_and_has_no_secret(self):
        project = self.app.data["selected_project"]
        key = "nvidia-private-setup-test-key-12345"
        self.api("/api/settings", {"api_key": key})
        result = self.api("/api/projects/" + project + "/setup")
        self.assertNotIn(key, json.dumps(result))
        self.assertIn("overview", result)
        self.assertFalse(self.app.jobs)
        status, _, _ = self.request("/api/projects/" + project + "/setup", auth=False)
        self.assertEqual(status, 401)

    def test_experience_preference_survives_restart_and_rejects_invalid_values(self):
        self.assertEqual(self.api("/api/state")["experience"], "simple")
        self.api("/api/experience", {"experience": "advanced"})
        reopened = AppService(self.app.bootstrap)
        self.assertEqual(reopened.state()["experience"], "advanced")
        status, _, _ = self.request("/api/experience", {"experience": "anything"})
        self.assertEqual(status, 400)
        self.assertEqual(self.app.data["experience"], "advanced")

    def test_active_task_protects_its_project_brief(self):
        project = self.app.data["selected_project"]
        with patch.object(self.app, "active", return_value=object()):
            status, result, _ = self.request("/api/projects/" + project + "/brief", {"revision": None, "brief": BRIEF})
        self.assertEqual(status, 400)
        self.assertIn("running task", result["error"])
        self.assertIsNone(self.api("/api/projects/" + project + "/brief")["revision"])
