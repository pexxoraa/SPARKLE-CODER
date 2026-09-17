import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch

from sparkle_coder.agent import Agent
from sparkle_coder.checks import discover_checks
from sparkle_coder.config import Config
from sparkle_coder.demo import calls, python_command
from sparkle_coder.provider import Completion, ModelError, NemotronClient
from sparkle_coder.state import Session
from sparkle_coder.webapp import AppService
from sparkle_coder.workspace import Workspace
from test_agent import SequenceProvider
from test_provider import endpoint
import test_web


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Workspace(Path(self.tmp.name))

    def agent(self, responses, checks=(), mode="build", approve=lambda _: True):
        session = Session.create(self.workspace, "Implement the requested change", list(checks), {})
        session.state["task_mode"] = mode
        return Agent(self.workspace, session, Config(), SequenceProvider(responses), approve, emit=lambda _: None)

    def test_six_real_repair_rounds_complete_without_a_run_attempt_cap(self):
        responses = []
        previous = None
        for value in range(6):
            text = f"value = {value}\n"
            args = {"path": "counter.py", "content": text}
            if previous:
                args["expected_sha256"] = hashlib.sha256(previous.encode()).hexdigest()
            responses.extend([calls(("write_file", args)), Completion("Ready for checking.", [], {})])
            previous = text
        agent = self.agent(responses, [python_command("-c", "import counter; assert counter.value == 5")])
        self.assertEqual(agent.run(), "checked")
        self.assertEqual([c["ok"] for c in agent.session.state["checks"]], [False] * 5 + [True])
        self.assertEqual(agent.session.state["usage"]["calls"], 12)

    def test_same_verification_command_runs_again_after_code_is_fixed(self):
        (self.workspace.root / "value.py").write_text("value = 0\n")
        command = python_command("-c", "import value; assert value.value == 1")
        responses = [calls(("verify", {"command": command})) for _ in range(3)]
        responses += [calls(("write_file", {"path": "value.py", "content": "value = 1\n",
            "expected_sha256": hashlib.sha256(b"value = 0\n").hexdigest()})),
            calls(("verify", {"command": command})), Completion("Fixed.", [], {})]
        agent = self.agent(responses)
        self.assertEqual(agent.run(), "checked")
        self.assertEqual([c["ok"] for c in agent.session.state["checks"]], [False, False, False, True])

    def test_existing_python_tests_are_discovered_and_run_before_completion(self):
        folder = self.workspace.root / "tests"
        folder.mkdir()
        (folder / "test_feature.py").write_text(
            "import unittest\nclass Feature(unittest.TestCase):\n def test_answer(self): self.assertEqual(6 * 7, 42)\n")
        approved = []
        agent = self.agent([Completion("Implemented.", [], {})], approve=lambda command: approved.append(command) or True)
        self.assertEqual(agent.run(), "checked")
        self.assertEqual(len(approved), 1)
        self.assertIn("Ran 1 test", agent.session.state["checks"][0]["output"])
        self.assertFalse(agent.session.state["checks"][0]["required"])

    def test_denied_check_is_not_repeated_but_can_be_approved_on_resume(self):
        (self.workspace.root / "test_example.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n def test_it(self): self.assertTrue(True)\n")
        requested = []
        agent = self.agent([Completion("Done.", [], {}) for _ in range(4)],
                           approve=lambda command: requested.append(command) and False)
        self.assertEqual(agent.run(), "needs_input")
        self.assertEqual(len(requested), 1)
        resumed = Agent(self.workspace, agent.session, Config(),
                        SequenceProvider([Completion("Please check again.", [], {})]), lambda _: True, emit=lambda _: None)
        self.assertEqual(resumed.run(), "checked")
        self.assertTrue(resumed.session.state["checks"][-1]["ok"])

    def test_environment_repair_invalidates_failed_acceptance_cache(self):
        check = python_command("-c", "from pathlib import Path; assert Path('node_modules/ready').exists()")
        install = python_command("-c", "from pathlib import Path; Path('node_modules').mkdir(); Path('node_modules/ready').touch()")
        agent = self.agent([Completion("Check now.", [], {}), calls(("run_command", {"command": install})),
                            Completion("Check after setup.", [], {})], [check])
        self.assertEqual(agent.run(), "checked")
        self.assertEqual([c["ok"] for c in agent.session.state["checks"]], [False, True])

    def test_discovery_handles_a_command_denied_before_any_verification_record(self):
        (self.workspace.root / "package.json").write_text(json.dumps({"scripts": {"test": "node test.js"}}))
        agent = self.agent([calls(("run_command", {"command": "npm run test"}))] +
                           [Completion("Please finish.", [], {}) for _ in range(4)], approve=lambda _: False)
        self.assertEqual(agent.run(), "needs_input")
        self.assertIn("declined", agent.session.state["recovery"]["message"])
        self.assertEqual(len(agent.session.state["checks"]), 1)
        self.assertTrue(agent.session.state["checks"][0]["denied"])

    def test_ask_mode_is_enforced_and_finishes_without_build_checks(self):
        agent = self.agent([calls(("write_file", {"path": "should-not-exist", "content": "no"}),
                                 ("run_command", {"command": "echo should-not-run"})),
                            Completion("Here is how this project works.", [], {})], mode="ask")
        self.assertEqual(agent.run(), "answered")
        self.assertFalse((self.workspace.root / "should-not-exist").exists())
        self.assertFalse(agent.session.state["checks"])
        self.assertTrue(all(not action["ok"] for action in agent.session.state["actions"]))
        self.assertNotIn("run_command", [s["function"]["name"] for s in agent.schemas])

    def test_input_request_saves_a_specific_next_step_and_skips_remaining_actions(self):
        agent = self.agent([calls(("request_input", {"question": "Which database should this use?", "next_step": "Choose SQLite or PostgreSQL."}),
                                 ("write_file", {"path": "never.txt", "content": "no"}))])
        self.assertEqual(agent.run(), "needs_input")
        self.assertIn("SQLite", agent.session.state["recovery"]["message"])
        self.assertFalse((self.workspace.root / "never.txt").exists())
        self.assertEqual(len([m for m in agent.session.state["messages"] if m["role"] == "tool"]), 2)

    def test_large_latest_tool_result_is_compacted_only_in_request_copy(self):
        agent = self.agent([])
        agent.config.context_chars = 16000
        call = calls(("run_command", {"command": "large-build-output"})).calls[0]
        output = "START\n" + "build output\n" * 20000 + "END"
        agent.session.state["messages"].extend([
            {"role": "assistant", "content": "", "tool_calls": [call]},
            {"role": "tool", "tool_call_id": call["id"], "content": output}])
        context = agent.context()
        self.assertLessEqual(len(json.dumps(context)), 16000)
        self.assertEqual(agent.session.state["messages"][-1]["content"], output)
        self.assertIn("shortened", context[-1]["content"])
        self.assertIn("END", context[-1]["content"])

    def test_a_zero_test_suite_does_not_count_as_passing_verification(self):
        agent = self.agent([])
        result = agent.tools.verify(python_command("-m", "unittest", "discover"))
        self.assertFalse(result["ok"])
        self.assertIn("No tests were collected", result["output"])

    def test_large_project_freshness_no_longer_returns_none(self):
        (self.workspace.root / "large.txt").write_bytes(b"x" * 30_000_001)
        before = self.workspace.fingerprint()
        self.assertIsNotNone(before)
        with (self.workspace.root / "large.txt").open("ab") as file:
            file.write(b"y")
        self.assertNotEqual(self.workspace.fingerprint(), before)

    def test_node_discovery_uses_real_scripts_and_skips_watch_and_placeholder_tests(self):
        folder = self.workspace.root / "frontend"
        folder.mkdir()
        (folder / "pnpm-lock.yaml").touch()
        (folder / "package.json").write_text(json.dumps({"scripts": {
            "dev": "vite", "test": "echo no test specified && exit 1", "build": "vite build",
            "typecheck": "tsc --noEmit", "check": "tsc --watch"}}))
        checks = discover_checks(self.workspace)["checks"]
        self.assertEqual({(c["command"], c["cwd"]) for c in checks},
                         {("pnpm run build", "frontend"), ("pnpm run typecheck", "frontend")})


class RecoveryTransportTests(unittest.TestCase):
    def test_service_unavailable_recovers_with_visible_retry_events(self):
        count = [0]
        def respond(body):
            count[0] += 1
            return (503, {}) if count[0] == 1 else (200, {"choices": [{"message": {"content": "Recovered"}}]})
        with endpoint(respond) as (url, requests):
            client = NemotronClient(Config(base_url=url))
            events = []
            client.bind_runtime(lambda kind, data: events.append((kind, data)), lambda: False)
            with patch("sparkle_coder.provider.time.sleep"):
                self.assertEqual(client.complete([], []).content, "Recovered")
            self.assertEqual(len(requests), 2)
            self.assertEqual(events[0][0], "model_retry")
            self.assertEqual(events[0][1]["attempt"], 2)

    def test_timeout_retries_and_stop_cancels_backoff(self):
        client = NemotronClient(Config())
        stop = threading.Event()
        client.bind_runtime(lambda *_: stop.set(), stop.is_set)
        with patch.object(client.opener, "open", side_effect=TimeoutError) as opened:
            with self.assertRaisesRegex(ModelError, "Stopped"):
                client.complete([], [])
        self.assertEqual(opened.call_count, 1)

    def test_network_error_retries_then_recovers(self):
        client = NemotronClient(Config())
        raw = json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode()
        with patch.object(client, "_read", side_effect=[urllib.error.URLError("offline"), raw]), \
                patch("sparkle_coder.provider.time.sleep"):
            self.assertEqual(client.complete([], []).content, "OK")

    def test_stop_during_slow_response_returns_promptly(self):
        gate, entered, stop = threading.Event(), threading.Event(), threading.Event()
        def respond(body):
            entered.set()
            gate.wait(5)
            return 200, {"choices": [{"message": {"content": "Too late"}}]}
        with endpoint(respond) as (url, _):
            client = NemotronClient(Config(base_url=url))
            client.bind_runtime(lambda *_: None, stop.is_set)
            results = []
            def request():
                try:
                    client.complete([], [])
                except ModelError as exc:
                    results.append(str(exc))
            thread = threading.Thread(target=request)
            thread.start()
            try:
                self.assertTrue(entered.wait(2))
                stop.set()
                thread.join(1)
                self.assertFalse(thread.is_alive())
                self.assertIn("Stopped", results[0])
            finally:
                gate.set()
                thread.join(3)


class RecoveryWebTests(unittest.TestCase):
    setUp = test_web.WebTests.setUp
    close = test_web.WebTests.close
    request = test_web.WebTests.request
    api = test_web.WebTests.api
    await_run = test_web.WebTests.await_run

    def test_saving_tested_connection_preserves_status_until_key_changes(self):
        class Provider:
            def models(self):
                return ["test-model"]
        self.app.provider_factory = lambda _: Provider()
        self.api("/api/settings", {"model": "test-model", "api_key": "test-key-for-memory"})
        self.assertTrue(self.api("/api/connect", {})["connected"])
        self.assertTrue(self.api("/api/settings", {"api_key": "", "max_steps": None})["connected"])
        self.assertFalse(self.api("/api/settings", {"api_key": "replacement-test-key"})["connected"])
        self.assertNotIn("replacement-test-key", self.app.settings_path.read_text())

    def test_ask_mode_roundtrip_and_resume_as_build(self):
        self.api("/api/settings", {"base_url": "http://127.0.0.1:8000/v1", "model": "test-model"})
        self.app.provider_factory = lambda _: SequenceProvider([Completion("Project explanation.", [], {})])
        run = self.api("/api/runs", {"project_id": self.app.data["selected_project"], "goal": "Explain it", "task_mode": "ask"})
        result = self.await_run(run["id"], {"answered"})
        self.assertEqual(result["session"]["task_mode"], "ask")
        self.assertFalse(result["session"]["checks"])
        self.app.provider_factory = lambda _: SequenceProvider([calls(("request_input", {
            "question": "What should this implement?", "next_step": "Describe the desired behavior."}))])
        run = self.api("/api/runs", {"project_id": self.app.data["selected_project"],
            "session_id": result["session_id"], "goal": "Implement it", "task_mode": "build"})
        result = self.await_run(run["id"], {"needs_input"})
        self.assertEqual(result["session"]["task_mode"], "build")
        self.assertEqual(result["session"]["recovery"]["action"], "instructions")

    def test_command_timeout_can_be_unlimited_and_explicit_caps_still_validate(self):
        self.assertIsNone(self.api("/api/settings", {"command_timeout": None})["command_timeout"])
        self.assertEqual(self.api("/api/settings", {"command_timeout": 600})["command_timeout"], 600)
        for value in (0, -1, True):
            self.assertEqual(self.request("/api/settings", {"command_timeout": value})[0], 400)

    def test_unexpected_provider_error_saves_a_recoverable_session(self):
        class BrokenProvider:
            def complete(self, messages, schemas):
                raise RuntimeError("The model server closed unexpectedly.")
        self.api("/api/settings", {"base_url": "http://127.0.0.1:8000/v1", "model": "test-model"})
        self.app.provider_factory = lambda _: BrokenProvider()
        run = self.api("/api/runs", {"project_id": self.app.data["selected_project"], "goal": "Build it"})
        self.app.job(run["id"]).thread.join(2)
        status, result, _ = self.request("/api/runs/" + run["id"])
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "needs_input")
        self.assertEqual(result["session"]["status"], "needs_input")
        self.assertEqual(result["session"]["recovery"]["action"], "retry")
        saved = Session.load(self.app.project(run["project_id"])[1], result["session_id"])
        self.assertEqual(saved.state["status"], "needs_input")


class SettingsMigrationTests(unittest.TestCase):
    def test_v2_command_default_migrates_without_removing_chosen_run_caps(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "settings.json").write_text(json.dumps({"settings_version": 2,
                "settings": {"command_timeout": 120, "max_steps": 40}}))
            app = AppService(path)
            self.addCleanup(app.close)
            self.assertIsNone(app.config().command_timeout)
            self.assertEqual(app.config().max_steps, 40)
            self.assertEqual(json.loads(app.settings_path.read_text())["settings_version"], 3)
