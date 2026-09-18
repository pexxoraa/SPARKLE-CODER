import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from sparkle_coder.agent import Agent
from sparkle_coder.config import Config
from sparkle_coder.demo import calls, python_command
from sparkle_coder.execution import CommandRunner
from sparkle_coder.provider import Completion
from sparkle_coder.state import Session
from sparkle_coder.web import LocalServer
from sparkle_coder.webapp import AppService
from sparkle_coder.workspace import Workspace


class FakeProvider:
    """Explicitly scripted responses; tests never contact a real model."""
    def __init__(self, config):
        self.config = config

    def models(self):
        return [self.config.model]

    def complete(self, messages, schemas):
        return Completion("This is a scripted reply, without verification.", [], {})


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"NVIDIA_API_KEY": "", "LOCAL_MODEL_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)
        self.app = AppService(Path(self.tmp.name), provider_factory=FakeProvider)
        self.server = LocalServer(("127.0.0.1", 0), self.app)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.app.close()
        for job in self.app.jobs.values():
            if job.thread:
                job.thread.join(4)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, path, body=None, *, headers=None, auth=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=8)
        request_headers = {"X-Sparkle-Token": self.server.token} if auth else {}
        payload = None
        if body is not None:
            request_headers["Content-Type"] = "application/json"
            payload = json.dumps(body)
        request_headers.update(headers or {})
        try:
            connection.request("GET" if body is None else "POST", path,
                               body=payload, headers=request_headers)
            response = connection.getresponse()
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if "application/json" in response.getheader("Content-Type", "") else raw
            return response.status, parsed, dict(response.getheaders())
        finally:
            connection.close()

    def api(self, path, body=None):
        status, result, _ = self.request(path, body)
        self.assertEqual(status, 200, result)
        return result

    def await_run(self, run_id, statuses):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = self.api("/api/runs/" + run_id)
            if result["status"] in statuses:
                return result
            if result["status"] in ("blocked", "needs_input"):
                self.fail(str(result))
            time.sleep(0.03)
        self.fail("Run did not reach expected status: " + str(result))

    def start_demo(self):
        data = self.api("/api/demo", {})
        return data, self.await_run(data["run"]["id"], {"approval"})

    def finish_demo(self):
        data, waiting = self.start_demo()
        self.api("/api/runs/" + waiting["id"] + "/approval",
                 {"approval_id": waiting["approval"]["id"], "allow": True})
        return data, self.await_run(waiting["id"], {"checked"})

    def test_api_requires_launch_token_and_rejects_cross_origin_requests(self):
        self.assertEqual(self.request("/api/state", auth=False)[0], 401)
        self.assertEqual(self.request("/api/state", headers={"X-Sparkle-Token": "wrong"})[0], 401)
        self.assertEqual(self.request("/api/state", headers={"X-Sparkle-Token": "é"})[0], 401)
        self.assertEqual(self.request("/api/state", headers={"Origin": "https://hostile.example"})[0], 403)
        self.assertEqual(self.request("/api/state", headers={"Host": "hostile.example"})[0], 403)
        self.assertEqual(self.request("/api/state", headers={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertTrue(self.api("/api/state")["projects"])

    def test_assets_are_served_with_csp_and_only_whitelisted_files_are_exposed(self):
        for path, expected in (("/", "app.js"), ("/app.js", "startTask"),
                               ("/app.css", ".composer"), ("/favicon.svg", "<svg")):
            status, content, headers = self.request(path, auth=False)
            self.assertEqual(status, 200)
            self.assertIn(expected, content)
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
            self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.request("/../settings.json", auth=False)[0], 404)
        self.assertEqual(self.request("/sparkle_coder/webapp.py", auth=False)[0], 404)

    def test_keys_are_memory_only_and_bound_to_the_selected_endpoint(self):
        key = "this-is-a-test-key-never-persist-it"
        settings = self.api("/api/settings", {"api_key": key})
        self.assertTrue(settings["key_configured"])
        self.assertNotIn(key, json.dumps(self.api("/api/state")))
        self.assertNotIn(key, self.app.settings_path.read_text())
        self.assertEqual(self.app.config().api_key, key)
        self.assertTrue(self.api("/api/connect", {})["connected"])
        self.api("/api/settings", {"base_url": "http://127.0.0.1:8000/v1", "model": "local-nemotron"})
        self.assertEqual(self.app.config().api_key, "")
        self.assertFalse(self.api("/api/state")["settings"]["connected"])
        self.api("/api/settings", {"base_url": "https://integrate.api.nvidia.com/v1"})
        self.assertEqual(self.app.config().api_key, key)
        reopened = AppService(Path(self.tmp.name))
        self.assertEqual(reopened.config().api_key, "")
        self.assertFalse(reopened.state()["settings"]["key_configured"])

    def test_invalid_settings_do_not_replace_working_configuration(self):
        before = self.app.settings_path.read_bytes()
        for payload in ({"max_steps": -1}, {"max_steps": True}, {"max_seconds": -1},
                        {"max_total_tokens": -1},
                        {"base_url": "http://remote.example/v1"},
                        {"auto_approve": True}, {"api_key": "key\nInjected: header"}):
            self.assertEqual(self.request("/api/settings", payload)[0], 400)
        self.assertEqual(self.app.settings_path.read_bytes(), before)
        self.assertEqual(self.request("/api/settings", {}, headers={"Content-Type": "text/plain"})[0], 415)

    def test_run_caps_are_unlimited_when_blank(self):
        settings = self.api("/api/settings", {
            "max_steps": None, "max_seconds": None, "max_total_tokens": None})
        self.assertIsNone(settings["max_steps"])
        self.assertIsNone(settings["max_seconds"])
        self.assertIsNone(settings["max_total_tokens"])
        self.assertIsNone(self.app.config().max_steps)
        self.assertIsNone(self.app.config().max_seconds)
        self.assertIsNone(self.app.config().max_total_tokens)

    def test_demo_approval_real_repair_history_diff_and_undo_through_http(self):
        data, run = self.finish_demo()
        project_id = data["project"]["id"]
        prefix = "/api/projects/" + project_id
        session = run["session"]
        self.assertEqual([c["ok"] for c in session["checks"]], [False, True])
        self.assertEqual(session["model"]["model"], "OFFLINE-SCRIPTED-DEMO")
        self.assertIn("calculator.py", self.api(prefix + "/files")["files"])
        self.assertIn("return a + b", self.api(prefix + "/file?path=calculator.py")["content"])
        self.assertEqual(self.api(prefix + "/sessions")["sessions"][0]["id"], run["session_id"])
        session_url = prefix + "/sessions/" + run["session_id"]
        changes = self.api(session_url + "/changes")["changes"]
        self.assertIn("calculator.py", [c["path"] for c in changes])
        self.assertIn("+    return a + b", next(c["diff"] for c in changes if c["path"] == "calculator.py"))
        preview = self.api(session_url + "/undo")
        self.assertIn("calculator.py", preview["paths"])
        self.assertFalse(preview["applied"])
        self.assertEqual(self.request(session_url + "/undo", {})[0], 400)
        self.assertTrue(self.api(session_url + "/undo", {"confirm": True})["applied"])
        self.assertNotIn("calculator.py", self.api(prefix + "/files")["files"])
        self.assertEqual(self.api(session_url)["status"], "undone")

    def test_stopping_at_approval_cancels_run_and_releases_workspace(self):
        _, waiting = self.start_demo()
        self.assertEqual(self.request("/api/demo", {})[0], 400)
        self.api("/api/runs/" + waiting["id"] + "/stop", {})
        stopped = self.await_run(waiting["id"], {"interrupted"})
        self.assertIsNone(stopped["approval"])
        self.assertIsNone(self.app.active())
        self.assertFalse(stopped["session"]["checks"])
        self.assertEqual(self.request("/api/runs/" + waiting["id"] + "/approval",
                         {"approval_id": waiting["approval"]["id"], "allow": True})[0], 400)
        # A delayed second click must not turn a completed job back into an active one.
        again = self.api("/api/runs/" + waiting["id"] + "/stop", {})
        self.assertEqual(again["status"], "interrupted")
        self.assertIsNone(self.app.active())

    def test_denied_command_does_not_run_and_approval_cannot_be_replayed(self):
        data, waiting = self.start_demo()
        body = {"approval_id": waiting["approval"]["id"], "allow": False}
        self.api("/api/runs/" + waiting["id"] + "/approval", body)
        run = self.await_run(waiting["id"], {"checked"})
        actions = [a for a in run["session"]["actions"] if a["tool"] == "run_command"]
        self.assertEqual(len(actions), 1)
        self.assertFalse(actions[0]["ok"])
        self.assertFalse((Path(data["project"]["path"]) / "__pycache__").exists())
        self.assertEqual(self.request("/api/runs/" + waiting["id"] + "/approval", body)[0], 400)

    def test_undo_refuses_to_destroy_a_later_manual_edit(self):
        data, run = self.finish_demo()
        path = Path(data["project"]["path"]) / "calculator.py"
        path.write_text("# My later edit\n")
        url = "/api/projects/" + run["project_id"] + "/sessions/" + run["session_id"] + "/undo"
        self.assertEqual(self.request(url, {"confirm": True})[0], 400)
        self.assertEqual(path.read_text(), "# My later edit\n")

    def test_project_registration_preserves_files_and_file_access_stays_confined(self):
        folder = Path(self.tmp.name) / "existing-project"
        folder.mkdir()
        (folder / "notes.txt").write_text("Keep this file.")
        (folder / ".env").write_text("PASSWORD=secret")
        project = self.api("/api/projects", {"name": "Existing", "path": str(folder)})
        self.assertEqual((folder / "notes.txt").read_text(), "Keep this file.")
        self.assertEqual(self.api("/api/projects", {"name": "Again", "path": str(folder)})["id"], project["id"])
        prefix = "/api/projects/" + project["id"]
        self.assertNotIn(".env", self.api(prefix + "/files")["files"])
        self.assertEqual(self.request(prefix + "/file?path=../settings.json")[0], 400)
        self.assertEqual(self.request(prefix + "/file?path=.env")[0], 400)
        self.assertEqual(self.request("/api/projects", {"name": "Bad", "path": "../relative"})[0], 400)

    def test_saved_task_can_resume_after_reopening_application(self):
        self.api("/api/settings", {"base_url": "http://127.0.0.1:8000/v1", "model": "scripted"})
        project_id = self.app.data["selected_project"]
        run = self.api("/api/runs", {"project_id": project_id, "goal": "Explain the project."})
        first = self.await_run(run["id"], {"needs_input"})
        reopened = AppService(Path(self.tmp.name), provider_factory=FakeProvider)
        self.assertEqual(reopened.history(project_id)[0]["id"], first["session_id"])
        followup = reopened.start(project_id, "Also explain the tests.", session_id=first["session_id"])
        job = reopened.job(followup["id"])
        job.thread.join(5)
        self.assertEqual(job.status, "needs_input")
        saved = reopened.snapshot(project_id, first["session_id"])
        self.assertIn("Also explain the tests.", [m["content"] for m in saved["messages"]])
        reopened.close()


class CancellationTests(unittest.TestCase):
    def test_stop_kills_running_command_before_it_can_write_later(self):
        with tempfile.TemporaryDirectory() as folder:
            workspace = Workspace(Path(folder))
            stop = threading.Event()
            runner = CommandRunner(workspace, Config(auto_approve=True), lambda _: True, stop.is_set)
            result = {}
            command = python_command("-c", "import time; from pathlib import Path; "
                                     "Path('started').write_text('yes'); time.sleep(10); "
                                     "Path('must-not-exist').write_text('bad')")
            thread = threading.Thread(target=lambda: result.update(runner.run(command)))
            thread.start()
            deadline = time.monotonic() + 5
            while not (workspace.root / "started").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            stop.set()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertTrue(result["cancelled"])
            self.assertFalse(result["ok"])
            self.assertFalse((workspace.root / "must-not-exist").exists())

    def test_cancel_during_model_request_prevents_returned_edits(self):
        stop = threading.Event()

        class StopsWhileThinking:
            def complete(self, messages, schemas):
                stop.set()
                return calls(("write_file", {"path": "must-not-exist", "content": "bad"}))

        with tempfile.TemporaryDirectory() as folder:
            workspace = Workspace(Path(folder))
            session = Session.create(workspace, "A cancellable task", [], {})
            agent = Agent(workspace, session, Config(), StopsWhileThinking(), lambda _: True,
                          emit=lambda _: None, should_stop=stop.is_set)
            self.assertEqual(agent.run(), "interrupted")
            self.assertFalse((workspace.root / "must-not-exist").exists())


class LauncherTests(unittest.TestCase):
    def test_graphical_entry_point_opens_engine_and_quits_cleanly(self):
        # Isolated app lifecycle test, without launching or automating a browser.
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            env = dict(os.environ)
            env["XDG_CONFIG_HOME"] = str(directory / "config")
            env["LOCALAPPDATA"] = str(directory / "config")
            process = subprocess.Popen(
                [sys.executable, str(root / "Open_SPARKLE_CODER.pyw"),
                 "--state-dir", str(directory / "app"), "--no-open"],
                cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                instance = directory / "app" / "instance.json"
                deadline = time.monotonic() + 8
                while not instance.exists() and time.monotonic() < deadline and process.poll() is None:
                    time.sleep(0.02)
                self.assertTrue(instance.exists(), "The graphical entry point did not start.")
                info = json.loads(instance.read_text())
                port = int(info["origin"].rsplit(":", 1)[1])
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
                try:
                    connection.request("GET", "/api/state", headers={"X-Sparkle-Token": info["token"]})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["version"], "0.6.1")
                    connection.request("POST", "/api/quit", body="{}", headers={
                        "X-Sparkle-Token": info["token"], "Content-Type": "application/json"})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.loads(response.read())["stopped"])
                finally:
                    connection.close()
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0, stderr.decode())
                self.assertFalse(instance.exists())
                self.assertNotIn(info["token"].encode(), stdout + stderr)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
