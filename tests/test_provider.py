from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from sparkle_coder.agent import Agent
from sparkle_coder.config import Config
from sparkle_coder.demo import DemoProvider, python_command
from sparkle_coder.provider import ModelError, NemotronClient, parse_completion
from sparkle_coder.state import Session
from sparkle_coder.workspace import Workspace


@contextmanager
def endpoint(responder):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            payload = json.dumps({"data": [{"id": "test-nemotron"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            code, payload = responder(body)
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ProviderTests(unittest.TestCase):
    def test_native_api_roundtrip_includes_real_repair_cycle(self):
        scripted = DemoProvider()
        def respond(body):
            completion = scripted.complete(body["messages"], body.get("tools", []))
            message = {"role": "assistant", "content": completion.content}
            if completion.calls:
                message["tool_calls"] = completion.calls
            return 200, {"choices": [{"message": message, "finish_reason": completion.finish_reason}],
                         "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
        with tempfile.TemporaryDirectory() as tmp, endpoint(respond) as (url, requests):
            config = Config(base_url=url, model="test-nemotron", auto_approve=True)
            workspace = Workspace(Path(tmp))
            client = NemotronClient(config)
            self.assertIn("test-nemotron", client.models())
            check = python_command("-m", "unittest", "discover", "-s", "tests", "-v")
            session = Session.create(workspace, "Build calculator.", [check], config.public_info())
            status = Agent(workspace, session, config, client, lambda _: True, lambda _: None).run()
            self.assertEqual(status, "checked")
            self.assertEqual([c["ok"] for c in session.state["checks"]], [False, True])
            self.assertEqual(session.state["usage"]["prompt_tokens"], 700)
            self.assertTrue(requests[0]["tools"])
            self.assertTrue(requests[0]["chat_template_kwargs"]["force_nonempty_content"])
            self.assertFalse(requests[0]["stream"])

    def test_json_fallback_roundtrip_for_chat_only_servers(self):
        replies = iter([
            {"tool": "write_file", "arguments": {"path": "hello.py", "content": "print(42)\n"}},
            {"final": "Program created and ready for its required check."},
        ])
        def respond(body):
            self.assertNotIn("tools", body)
            self.assertFalse(any(m["role"] == "tool" for m in body["messages"]))
            return 200, {"choices": [{"message": {"content": json.dumps(next(replies))},
                                     "finish_reason": "stop"}]}
        with tempfile.TemporaryDirectory() as tmp, endpoint(respond) as (url, requests):
            config = Config(base_url=url, model="test-nemotron", tool_format="json", auto_approve=True)
            workspace = Workspace(Path(tmp))
            check = python_command("-c", "import subprocess,sys; assert subprocess.check_output([sys.executable,'hello.py']).strip() == b'42'")
            session = Session.create(workspace, "Write hello.", [check], {})
            status = Agent(workspace, session, config, NemotronClient(config), lambda _: True, lambda _: None).run()
            self.assertEqual(status, "checked")
            self.assertEqual(len(requests), 2)

    def test_http_auth_error_is_actionable(self):
        with endpoint(lambda body: (401, {"error": "bad auth"})) as (url, requests):
            client = NemotronClient(Config(base_url=url))
            with self.assertRaisesRegex(ModelError, "HTTP 401.*API key"):
                client.complete([{"role": "user", "content": "hello"}], [])
            self.assertEqual(len(requests), 1)

    def test_rate_limit_retries_are_bounded(self):
        with endpoint(lambda body: (429, {"error": "too many requests"})) as (url, requests):
            with patch("sparkle_coder.provider.time.sleep"):
                with self.assertRaisesRegex(ModelError, "rate-limited"):
                    NemotronClient(Config(base_url=url)).complete([], [])
            self.assertEqual(len(requests), 3)

    def test_malformed_model_output_is_a_controlled_error(self):
        for data in ({}, {"choices": []}, {"choices": [{"message": []}]},
                     {"choices": [{"message": {"content": "not JSON"}}]}):
            with self.subTest(data=data):
                with self.assertRaises(ModelError):
                    parse_completion(data, "json")

    def test_duplicate_tool_ids_are_rejected(self):
        call = {"id": "same", "function": {"name": "list_files", "arguments": "{}"}}
        data = {"choices": [{"message": {"content": "", "tool_calls": [call, call]}}]}
        with self.assertRaises(ModelError):
            parse_completion(data, "native")

    def test_reasoning_is_not_mistaken_for_final_content(self):
        data = {"choices": [{"message": {"reasoning_content": "internal reasoning",
                                        "content": "Final answer"}, "finish_reason": "stop"}]}
        self.assertEqual(parse_completion(data, "native").content, "Final answer")

    def test_no_live_nvidia_key_gives_clear_setup_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "Add an NVIDIA API key"):
                Config().require_credentials()
            Config(base_url="http://127.0.0.1:8000/v1").require_credentials()
