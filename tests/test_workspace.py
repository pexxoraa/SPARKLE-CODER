import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sparkle_coder.config import Config, load_config
from sparkle_coder.state import Session
from sparkle_coder.tools import ToolSet
from sparkle_coder.workspace import Redactor, Workspace, WorkspaceError, sha256


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Workspace(Path(self.tmp.name) / "project")
        self.session = Session.create(self.workspace, "Test task", [], {})
        self.tools = ToolSet(self.workspace, self.session, Config(), lambda _: False)

    def test_paths_cannot_escape_or_access_secrets(self):
        for path in ("../outside", "/tmp/file", "a/../../file", r"C:\outside",
                     ".git/config", ".nemotron/memory.json", ".env", ".env.production",
                     "nested/credentials.json", "key.pem", "nemotron.toml"):
            with self.subTest(path=path):
                self.assertFalse(self.tools.execute("write_file", {"path": path, "content": "bad"})["ok"])
        self.assertFalse((Path(self.tmp.name) / "outside").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_cannot_escape_workspace(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (self.workspace.root / "link").symlink_to(outside, target_is_directory=True)
        result = self.tools.execute("write_file", {"path": "link/bad.py", "content": "bad"})
        self.assertFalse(result["ok"])
        self.assertFalse((outside / "bad.py").exists())

    def test_stale_hash_preserves_user_changes(self):
        result = self.tools.execute("write_file", {"path": "main.py", "content": "original"})
        (self.workspace.root / "main.py").write_text("user's intervening change")
        failed = self.tools.execute("write_file", {"path": "main.py", "content": "agent overwrite",
                                                  "expected_sha256": result["sha256"]})
        self.assertFalse(failed["ok"])
        self.assertEqual((self.workspace.root / "main.py").read_text(), "user's intervening change")

    def test_ambiguous_edit_rejected(self):
        created = self.tools.execute("write_file", {"path": "a.ts", "content": "value value"})
        result = self.tools.execute("edit_file", {"path": "a.ts", "old_text": "value",
                                                 "new_text": "other", "expected_sha256": created["sha256"]})
        self.assertFalse(result["ok"])

    def test_undo_restores_original_and_removes_new_file(self):
        path = self.workspace.root / "existing.rs"
        path.write_text("original")
        first = self.tools.execute("write_file", {"path": "existing.rs", "content": "edit one",
                                                  "expected_sha256": sha256(b"original")})
        self.tools.execute("write_file", {"path": "existing.rs", "content": "edit two",
                                          "expected_sha256": first["sha256"]})
        self.tools.execute("write_file", {"path": "new.go", "content": "package main"})
        self.session.undo()
        self.assertEqual(path.read_text(), "original")
        self.assertFalse((self.workspace.root / "new.go").exists())

    def test_undo_checks_all_conflicts_before_writing(self):
        for name in ("a.py", "b.py"):
            self.tools.execute("write_file", {"path": name, "content": "agent"})
        (self.workspace.root / "b.py").write_text("user edit")
        with self.assertRaises(WorkspaceError):
            self.session.undo()
        self.assertEqual((self.workspace.root / "a.py").read_text(), "agent")
        self.assertEqual((self.workspace.root / "b.py").read_text(), "user edit")

    def test_delete_is_recoverable(self):
        path = self.workspace.root / "old.c"
        path.write_text("int main() { return 0; }\n")
        content = path.read_bytes()
        self.tools.execute("delete_file", {"path": "old.c", "expected_sha256": sha256(content)})
        self.assertFalse(path.exists())
        self.session.undo()
        self.assertEqual(path.read_bytes(), content)

    def test_memory_survives_sessions(self):
        self.tools.execute("remember", {"key": "tests", "fact": "Use unittest.", "source": "README.md"})
        loaded = ToolSet(self.workspace, Session.load(self.workspace, self.session.id), Config(), lambda _: False)
        self.assertEqual(loaded.memory()["tests"]["fact"], "Use unittest.")

    def test_nested_guidance_is_returned(self):
        (self.workspace.root / "AGENTS.md").write_text("Root rule")
        (self.workspace.root / "src").mkdir()
        (self.workspace.root / "src" / "AGENTS.md").write_text("Nested rule")
        (self.workspace.root / "src" / "main.py").write_text("pass")
        info = self.tools.execute("read_file", {"path": "src/main.py"})
        self.assertIn("Root rule", info["instructions"])
        self.assertIn("Nested rule", info["instructions"])

    def test_noninteractive_command_denial_has_no_side_effect(self):
        result = self.tools.execute("run_command", {"command": "touch forbidden"})
        self.assertTrue(result["denied"])
        self.assertFalse((self.workspace.root / "forbidden").exists())

    def test_invalid_tool_arguments_are_observable_failures(self):
        for name, args in (("not_a_tool", {}), ("read_file", {}), ("write_file", []),
                           ("list_files", {"limit": True}), ("update_plan", {"steps": [{}]})):
            self.assertFalse(self.tools.execute(name, args)["ok"])

    def test_second_process_cannot_lock_same_workspace(self):
        with self.workspace.lock():
            with self.assertRaises(WorkspaceError):
                with self.workspace.lock():
                    self.fail("Second lock was acquired")
        self.assertFalse((self.workspace.state_dir / "workspace.lock").exists())

    def test_known_environment_keys_are_redacted(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key-that-must-not-leak"}):
            result = Redactor().value({"output": ["test-key-that-must-not-leak"]})
        self.assertEqual(result["output"][0], "[REDACTED]")

    def test_configuration_rejects_overrides_of_tool_protocol(self):
        with self.assertRaises(ValueError):
            Config(extra_body={"messages": []}).validate()
        with self.assertRaises(ValueError):
            Config(auto_approve="false").validate()
        with self.assertRaises(ValueError):
            Config(temperature="high").validate()
        with self.assertRaises(ValueError):
            Config(base_url="http://untrusted.example/v1").validate()
        Config(base_url="http://127.0.0.1:8000/v1").validate()

    def test_config_and_environment_precedence(self):
        (self.workspace.root / "nemotron.toml").write_text('model = "from-file"\n')
        with patch.dict(os.environ, {"NEMOTRON_MODEL": "from-environment"}):
            self.assertEqual(load_config(self.workspace.root).model, "from-environment")
            self.assertEqual(load_config(self.workspace.root, {"model": "from-cli"}).model, "from-cli")
