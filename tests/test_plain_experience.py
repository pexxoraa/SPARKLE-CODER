"""Real failing commands, saved evidence, and portable folder migrations."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sparkle_coder.agent import Agent
from sparkle_coder.config import Config
from sparkle_coder.demo import python_command
from sparkle_coder.explanations import explain_checks, simple_recovery
from sparkle_coder.provider import Completion
from sparkle_coder.state import Session
from sparkle_coder.storage import migrate_legacy
from sparkle_coder.verification import active_checks, proof_summary
from sparkle_coder.webapp import AppService, default_app_dir
from sparkle_coder.workspace import Workspace
from test_agent import SequenceProvider


# This fixture deliberately produces the user's observed count. It is not a
# copy of their unavailable model project and makes no claim about that code.
TOKENIZER = '''import string

def create_sample_data():
    return string.ascii_letters

class CharTokenizer:
    special_tokens = ["<pad>", "<unk>"]
    def train(self, text):
        self.symbols = self.special_tokens + sorted(set(text))
        self.vocab_size = len(self.symbols)
    def encode(self, text):
        return [self.symbols.index(c) if c in self.symbols else 1 for c in text]
    def decode(self, ids):
        return "".join(self.symbols[i] for i in ids)
'''
WRONG = '''from tokenizer import CharTokenizer, create_sample_data
t = CharTokenizer()
t.train(create_sample_data())
assert t.vocab_size == 36, f'Expected vocab 36, got {t.vocab_size}'
assert t.decode(t.encode('Hello')) == 'Hello'
'''
CORRECT = '''from tokenizer import CharTokenizer, create_sample_data
text = create_sample_data()
t = CharTokenizer()
t.train(text)
expected_symbols = set(text) | set(t.special_tokens)
assert set(t.symbols) == expected_symbols
assert t.vocab_size == len(expected_symbols)
assert len(set(t.symbols)) == t.vocab_size
assert t.decode(t.encode('Hello')) == 'Hello'
assert t.decode(t.encode('!')) == '<unk>'
print('Vocabulary, round trip and unknown-symbol behavior passed')
'''


class PlainRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Workspace(Path(temporary.name))
        (self.workspace.root / "tokenizer.py").write_text(TOKENIZER)
        session = Session.create(self.workspace, "Build a small text model", [], {})
        self.agent = Agent(self.workspace, session, Config(), SequenceProvider([]), lambda _: True, emit=lambda _: None)
        self.tools = self.agent.tools
        self.state = session.state

    def failed_check(self, script=WRONG):
        result = self.tools.verify(python_command("-c", script))
        self.assertFalse(result["ok"])
        return result["check_id"]

    def revision(self, ids, script=CORRECT, read=True):
        if read:
            digest = self.tools.execute("read_file", {"path": "tokenizer.py"})["sha256"]
        else:
            digest = hashlib.sha256(TOKENIZER.encode()).hexdigest()
        return {"check_ids": ids, "command": python_command("-c", script),
                "label": "Text reader behavior", "reason":
                "The sample data includes upper and lower case letters plus two special symbols. "
                "The replacement derives the expected symbols from those inputs and still checks a round trip.",
                "evidence_path": "tokenizer.py", "expected_sha256": digest}

    def test_observed_error_is_explained_without_guessing_which_side_is_wrong(self):
        self.failed_check()
        self.failed_check(WRONG.replace("Hello", "Once"))
        issues = explain_checks(self.state)
        self.assertEqual(len(issues), 1)
        self.assertEqual(len(issues[0]["check_ids"]), 2)
        recovery = simple_recovery(self.state)
        self.assertIn("expected 36", recovery["what_happened"])
        self.assertIn("counted 54", recovery["what_happened"])
        self.assertIn("cannot tell us which", recovery["meaning"])
        self.assertNotIn("Traceback", recovery["message"])
        self.assertNotIn("assert", recovery["message"])

    def test_corrected_assumption_supersedes_both_failed_variants_and_completes(self):
        ids = [self.failed_check(), self.failed_check(WRONG.replace("Hello", "Once"))]
        self.state["delivery"] = {"features": [{"feature": "Read text", "check_ids": ids}]}
        result = self.tools.execute("revise_check", self.revision(ids))
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["superseded"])
        self.assertEqual(len(self.state["checks"]), 3)
        self.assertEqual([c["ok"] for c in self.state["checks"]], [False, False, True])
        self.assertEqual([c["id"] for c in active_checks(self.state)], [result["check_id"]])
        self.assertEqual(proof_summary(self.state)["features"][0]["status"], "passed")
        self.assertTrue(self.agent.verify_completion()[0])
        restored = Session.load(self.workspace, self.agent.session.id)
        self.assertEqual(restored.state["check_revisions"][0]["old_ids"], ids)
        self.assertIn("still checks a round trip", restored.state["check_revisions"][0]["reason"])

    def test_unread_or_stale_evidence_cannot_retire_a_failure(self):
        check_id = self.failed_check()
        result = self.tools.execute("revise_check", self.revision([check_id], read=False))
        self.assertFalse(result["ok"])
        self.assertIn("Read the current evidence", result["error"])
        args = self.revision([check_id])
        (self.workspace.root / "tokenizer.py").write_text(TOKENIZER + "\n# changed after reading\n")
        result = self.tools.execute("revise_check", args)
        self.assertFalse(result["ok"])
        self.assertEqual(len(self.state["checks"]), 1)
        self.assertFalse(self.state.get("check_revisions"))

    def test_later_user_requirement_overrides_a_previous_agent_correction(self):
        identity = self.failed_check()
        self.tools.execute("revise_check", self.revision([identity]))
        self.state["required_checks"] = [python_command("-c", WRONG)]
        self.state["delivery"] = {"features": [{"feature": "Read text", "check_ids": [identity]}]}
        self.assertFalse(self.agent.verify_completion()[0])
        self.assertEqual(proof_summary(self.state)["features"][0]["status"], "needs_fix")
        self.assertEqual(proof_summary(self.state)["failed"], 1)

    def test_failed_replacement_preserves_the_original_check(self):
        check_id = self.failed_check()
        result = self.tools.execute("revise_check", self.revision([check_id], CORRECT + "assert False, 'still broken'\n"))
        self.assertFalse(result["ok"])
        self.assertFalse(result["superseded"])
        self.assertEqual(len(active_checks(self.state)), 2)
        self.assertFalse(self.state.get("check_revisions"))

    def test_user_and_existing_project_checks_cannot_be_retired(self):
        command = python_command("-c", WRONG)
        self.state["required_checks"] = [command]
        user_check = self.tools.verify(command, trusted=True)["check_id"]
        result = self.tools.execute("revise_check", self.revision([user_check]))
        self.assertFalse(result["ok"])
        self.assertIn("cannot be replaced", result["error"])
        (self.workspace.root / "test_project.py").write_text(
            "import unittest\nclass Test(unittest.TestCase):\n def test_it(self): self.fail('bug')\n")
        candidate = self.tools.discover_checks()["checks"][0]
        # Even an explicitly agent-selected invocation of this project command
        # must remain protected by discovery.
        check = self.tools.verify(candidate["command"], candidate["cwd"])
        result = self.tools.execute("revise_check", self.revision([check["check_id"]]))
        self.assertFalse(result["ok"])
        self.assertIn("cannot be replaced", result["error"])

    def test_delivery_uses_recorded_checks_and_becomes_stale_after_edits(self):
        check = self.tools.verify(python_command("-c", CORRECT))
        payload = {"summary": "A text reader", "how_to_use": ["Open the project folder."],
                   "limitations": ["Model training has not been tested."], "features": [
                       {"feature": "Read text", "check_ids": [check["check_id"]]},
                       {"feature": "Train a model", "check_ids": []}]}
        self.assertTrue(self.tools.execute("update_delivery", payload)["ok"])
        self.assertEqual([f["status"] for f in proof_summary(self.state)["features"]], ["passed", "not_checked"])
        payload["features"][0]["check_ids"] = ["invented-pass"]
        self.assertFalse(self.tools.execute("update_delivery", payload)["ok"])
        self.tools.execute("write_file", {"path": "readme.txt", "content": "Changed project"})
        self.assertEqual(proof_summary(self.state)["features"][0]["status"], "needs_recheck")

    def test_repeated_completion_claims_trigger_source_inspection_and_plain_recovery(self):
        self.failed_check()
        self.agent.provider = SequenceProvider([Completion("Finished", [], {}) for _ in range(4)])
        self.assertEqual(self.agent.run(), "needs_input")
        self.assertIn("tokenizer.py", self.state["read_evidence"])
        self.assertTrue(any("fresh source evidence" in m.get("content", "") for m in self.state["messages"]))
        self.assertIn("counted 54", self.state["summary"])
        self.assertNotIn("Traceback", self.state["summary"])
        self.assertNotIn('"command"', self.state["summary"])
        self.assertIn("Expected vocab 36", self.state["technical_summary"])

    def test_a_migrated_check_cannot_accidentally_test_the_backup_folder(self):
        self.state["previous_workspaces"] = [str(self.workspace.root / "old-project")]
        command = python_command("-c", "from pathlib import Path; Path('should-not-run').touch() # " + self.state["previous_workspaces"][0])
        result = self.tools.verify(command)
        self.assertFalse(result["ok"])
        self.assertEqual(result["explanation"]["kind"], "moved_project")
        self.assertFalse((self.workspace.root / "should-not-run").exists())

    def test_old_checks_receive_stable_ids_after_reopening(self):
        self.failed_check()
        for key in ("id", "key", "source"):
            self.state["checks"][0].pop(key)
        self.agent.session.save()
        first = Session.load(self.workspace, self.agent.session.id)
        second = Session.load(self.workspace, self.agent.session.id)
        self.assertEqual(first.state["checks"][0]["id"], second.state["checks"][0]["id"])
        self.assertEqual(first.state["checks"][0]["source"], "agent")


class PortableProjectsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.app_root = self.parent / "SPARKLE-CODER"
        self.legacy = self.parent / "old-config"
        self.root_patch = patch("sparkle_coder.webapp.application_root", return_value=self.app_root)
        self.legacy_patch = patch("sparkle_coder.webapp.legacy_app_dirs", return_value=(self.legacy, self.parent / "older"))
        self.root_patch.start()
        self.legacy_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.legacy_patch.stop)

    def open_app(self, directory=None):
        app = AppService(directory or default_app_dir())
        self.addCleanup(app.close)
        return app

    def old_project(self):
        old = self.open_app(self.legacy)
        project_id = old.data["selected_project"]
        workspace = old.project(project_id)[1]
        (workspace.root / "saved.txt").write_text("My work")
        session = Session.create(workspace, "Old task", [], {})
        session.state.pop("workspace_root", None)  # A pre-0.5 saved task.
        session.save()
        return old, project_id, workspace, session

    def test_new_install_creates_projects_inside_the_application(self):
        app = self.open_app()
        self.assertEqual(app.directory, self.app_root / "APP_DATA")
        self.assertEqual(app.projects_directory, self.app_root / "PROJECTS")
        self.assertEqual(app.project(app.data["selected_project"])[1].root.parent, app.projects_directory)
        self.assertEqual(app.state()["storage"]["projects_path"], str(app.projects_directory))

    def test_migration_preserves_history_originals_and_external_projects(self):
        old, identity, workspace, session = self.old_project()
        external = old.add_project("External", str(self.parent / "external"))
        app = self.open_app()
        new = app.project(identity)[1]
        self.assertEqual(new.root.parent, self.app_root / "PROJECTS")
        self.assertEqual((new.root / "saved.txt").read_text(), "My work")
        self.assertTrue((workspace.root / "saved.txt").exists())
        self.assertEqual(app.project(external["id"])[1].root, self.parent / "external")
        migrated_session = Session.load(new, session.id)
        self.assertIn(str(workspace.root), migrated_session.state["previous_workspaces"])
        self.assertIsNone(migrated_session.state["verification_fingerprint"])
        self.assertIn("backups", app.state()["storage"]["migration"]["message"])
        self.assertEqual(self.open_app().project(identity)[1].root, new.root)

    def test_migration_reads_previous_custom_storage_pointer(self):
        old, identity, _, _ = self.old_project()
        custom = self.parent / "custom-device-folder"
        old.storage(str(custom))
        app = self.open_app()
        self.assertEqual(app.project(identity)[1].read("saved.txt")[0], "My work")
        self.assertEqual(app.data["storage_migration"]["from"], str(custom))

    def test_name_collision_keeps_both_folders(self):
        _, identity, workspace, _ = self.old_project()
        occupied = self.app_root / "PROJECTS" / workspace.root.name
        occupied.mkdir(parents=True)
        (occupied / "keep.txt").write_text("Do not replace")
        app = self.open_app()
        self.assertNotEqual(app.project(identity)[1].root, occupied)
        self.assertEqual((occupied / "keep.txt").read_text(), "Do not replace")
        self.assertTrue((workspace.root / "saved.txt").exists())

    def test_copy_failure_does_not_commit_settings_and_can_be_retried(self):
        old, identity, workspace, _ = self.old_project()
        old.add_project("Second", "")
        import shutil
        real_copy = shutil.copytree
        count = [0]
        def copying(*args, **kwargs):
            # shutil.copytree recursively invokes itself; count only its two
            # outer managed-project copies.
            if Path(args[0]).parent == old.projects_directory:
                count[0] += 1
                if count[0] == 2:
                    raise OSError("disk full")
            return real_copy(*args, **kwargs)
        with patch("sparkle_coder.storage.shutil.copytree", side_effect=copying):
            with self.assertRaisesRegex(ValueError, "original files remain"):
                self.open_app()
        self.assertFalse((default_app_dir() / "settings.json").exists())
        self.assertEqual(list((self.app_root / "PROJECTS").iterdir()), [])
        self.assertEqual((workspace.root / "saved.txt").read_text(), "My work")
        self.assertEqual(self.open_app().project(identity)[1].read("saved.txt")[0], "My work")

    def test_sibling_projects_move_with_selected_storage_and_remain_resumable(self):
        app = self.open_app()
        identity = app.data["selected_project"]
        workspace = app.project(identity)[1]
        (workspace.root / "saved.txt").write_text("Portable project")
        session = Session.create(workspace, "Resume me", [], {})
        target = self.parent / "selected-data"
        app.storage(str(target))
        new = app.project(identity)[1]
        self.assertEqual(new.root.parent, target / "PROJECTS")
        self.assertTrue((workspace.root / "saved.txt").exists())
        self.assertIn(str(workspace.root), Session.load(new, session.id).state["previous_workspaces"])
        self.assertEqual(self.open_app().project(identity)[1].read("saved.txt")[0], "Portable project")

    def test_storage_cannot_copy_into_its_own_projects(self):
        app = self.open_app()
        with self.assertRaisesRegex(ValueError, "outside the current PROJECTS"):
            app.storage(str(app.projects_directory / "nested"))
        self.assertFalse((app.projects_directory / "nested").exists())

    def test_opening_old_failure_uses_simple_recovery_and_detects_later_manual_edits(self):
        app = self.open_app()
        identity = app.data["selected_project"]
        workspace = app.project(identity)[1]
        (workspace.root / "tokenizer.py").write_text(TOKENIZER)
        session = Session.create(workspace, "Read text", [], {})
        agent = Agent(workspace, session, Config(), SequenceProvider([]), lambda _: True, emit=lambda _: None)
        agent.tools.verify(python_command("-c", WRONG))
        session.state.update(status="needs_input", summary="Checks need repair. " + json.dumps(session.state["checks"]),
                             recovery={"action": "checks", "message": "Long old error"})
        session.save()
        snapshot = app.snapshot(identity, session.id)
        self.assertIn("counted 54", snapshot["recovery"]["what_happened"])
        self.assertNotIn("Traceback", snapshot["recovery"]["message"])
        passed = agent.tools.verify(python_command("-c", CORRECT))
        session.state["status"] = "checked"
        session.save()
        self.assertEqual(app.snapshot(identity, session.id)["proof"]["passed"], 1)
        (workspace.root / "manual.txt").write_text("A later user edit")
        snapshot = app.snapshot(identity, session.id)
        self.assertEqual(snapshot["proof"]["passed"], 0)
        self.assertEqual(snapshot["proof"]["needs_recheck"], 1)


if __name__ == "__main__":
    unittest.main()
